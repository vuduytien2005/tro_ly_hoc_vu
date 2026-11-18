"""Lập chỉ mục các văn bản khai báo trong data/van_ban/danh_muc.csv.

Cột CSV: ten_tep,ten,loai,phien_ban,ap_dung_tu_khoa,ap_dung_den_khoa,ngay_hieu_luc
         [,chien_luoc_chunk]
  - ap_dung_tu_khoa / ap_dung_den_khoa: số khóa 2 chữ số (21 = K21); để trống = không giới hạn.
  - loai: quy_che | so_tay | quy_dinh | huong_dan | thong_bao
  - chien_luoc_chunk (tùy chọn): theo_dieu (mặc định) | co_dinh | ngu_nghia

Chạy từ thư mục backend/:
    python scripts/ingest_folder.py                       # tất cả dòng trong danh mục
    python scripts/ingest_folder.py --tep quy_che_2023.pdf
    python scripts/ingest_folder.py --chien-luoc co_dinh  # ghi đè chiến lược (thực nghiệm)
    python scripts/ingest_folder.py --embedder hashing    # không tải mô hình (thử nhanh)
Chạy lại không bị trùng: văn bản cùng (ten, loai, phien_ban) được lập chỉ mục lại.
"""

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

from src.rag.chunker import STRATEGIES
from src.rag.embedder import Embedder, HashingEmbedder, get_embedder
from src.rag.indexer import DocumentMeta, index_document, mark_failed
from src.rag.loader import SUPPORTED_SUFFIXES
from src.rag.store import VectorStore
from src.shared.config import PROJECT_ROOT, get_settings
from src.shared.db import assistant_session_factory

LOAI = {"quy_che", "so_tay", "quy_dinh", "huong_dan", "thong_bao"}
REQUIRED_COLUMNS = {"ten_tep", "ten", "loai", "phien_ban"}


def _optional_int(value: str | None, column: str, line: int) -> int | None:
    value = (value or "").strip().upper().removeprefix("K")
    if not value:
        return None
    if not value.isdigit() or not 0 <= int(value) <= 99:
        raise ValueError(f"dòng {line}: {column} phải là số khóa 2 chữ số (vd 22), nhận '{value}'")
    return int(value)


def read_catalog(catalog: Path, folder: Path, strategy_override: str | None) -> list[DocumentMeta]:
    with catalog.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{catalog.name} thiếu cột: {', '.join(sorted(missing))}")
        metas: list[DocumentMeta] = []
        for line, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            if not row.get("ten_tep"):
                continue
            if row["loai"] not in LOAI:
                raise ValueError(
                    f"dòng {line}: loai '{row['loai']}' không hợp lệ ({', '.join(sorted(LOAI))})"
                )
            strategy = strategy_override or row.get("chien_luoc_chunk") or "theo_dieu"
            if strategy not in STRATEGIES:
                raise ValueError(f"dòng {line}: chien_luoc_chunk '{strategy}' không hợp lệ")
            path = (folder / row["ten_tep"]).resolve()
            ngay = row.get("ngay_hieu_luc")
            metas.append(
                DocumentMeta(
                    ten=row["ten"],
                    loai=row["loai"],
                    phien_ban=row["phien_ban"],
                    ten_tep=row["ten_tep"],
                    duong_dan_tep=_display_path(path),
                    ap_dung_tu_khoa=_optional_int(
                        row.get("ap_dung_tu_khoa"), "ap_dung_tu_khoa", line
                    ),
                    ap_dung_den_khoa=_optional_int(
                        row.get("ap_dung_den_khoa"), "ap_dung_den_khoa", line
                    ),
                    ngay_hieu_luc=date.fromisoformat(ngay) if ngay else None,
                    chien_luoc_chunk=strategy,
                )
            )
    return metas


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _khoa_range(meta: DocumentMeta) -> str:
    tu = f"K{meta.ap_dung_tu_khoa}" if meta.ap_dung_tu_khoa is not None else "…"
    den = f"K{meta.ap_dung_den_khoa}" if meta.ap_dung_den_khoa is not None else "…"
    return f"{tu}–{den}"


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Lập chỉ mục văn bản quy chế cho RAG")
    parser.add_argument("--thu-muc", type=Path, default=settings.upload_dir)
    parser.add_argument(
        "--danh-muc", type=Path, default=None, help="mặc định <thu-muc>/danh_muc.csv"
    )
    parser.add_argument("--tep", help="chỉ lập chỉ mục tệp này (theo cột ten_tep)")
    parser.add_argument("--chien-luoc", choices=STRATEGIES, help="ghi đè chiến lược chia đoạn")
    parser.add_argument("--embedder", choices=["model", "hashing"], default="model")
    args = parser.parse_args()

    folder: Path = args.thu_muc
    catalog: Path = args.danh_muc or folder / "danh_muc.csv"
    if not catalog.exists():
        print(f"Không thấy danh mục {catalog}", file=sys.stderr)
        return 1
    try:
        metas = read_catalog(catalog, folder, args.chien_luoc)
    except ValueError as exc:
        print(f"Lỗi danh mục: {exc}", file=sys.stderr)
        return 1
    if args.tep:
        metas = [m for m in metas if m.ten_tep == args.tep]
    if not metas:
        print(f"Danh mục {catalog.name} chưa có văn bản nào (cần ít nhất 1 dòng dưới tiêu đề).")
        return 1

    embedder: Embedder = HashingEmbedder() if args.embedder == "hashing" else get_embedder()
    store = VectorStore(settings.chroma_dir, embedder.name)
    print(f"Mô hình embedding : {embedder.name}")
    print(f"ChromaDB          : {settings.chroma_dir} (collection {store.name})")
    print(f"Số văn bản        : {len(metas)}\n")

    header = (
        f"{'Tệp':<28} {'Phiên bản':<10} {'Khóa':<9} {'Trang':>5} {'Đoạn':>5} {'Chia':<9} "
        f"{'Đọc':>6} {'Chia':>6} {'Embed':>7} {'Tổng':>7}"
    )
    print(header)
    print("-" * len(header))
    started = time.perf_counter()
    ok = failed = total_chunks = 0
    factory = assistant_session_factory()
    for meta in metas:
        path = folder / meta.ten_tep
        label = f"{meta.ten_tep[:28]:<28} {meta.phien_ban[:10]:<10} {_khoa_range(meta):<9}"
        if not path.exists():
            message = f"Không tìm thấy tệp {path}"
        elif path.suffix.lower() not in SUPPORTED_SUFFIXES:
            message = f"Định dạng {path.suffix} không được hỗ trợ"
        else:
            message = ""
        with factory() as db:
            try:
                if message:
                    raise FileNotFoundError(message)
                r = index_document(
                    db, store, embedder, path, meta, max_tokens=settings.chunk_max_tokens
                )
                db.commit()
            except Exception as exc:  # ghi lỗi vào van_ban rồi xử lý tệp tiếp theo
                db.rollback()
                mark_failed(db, meta, str(exc))
                db.commit()
                failed += 1
                print(f"{label} LỖI: {exc}")
                continue
        ok += 1
        total_chunks += r.so_doan
        print(
            f"{label} {r.so_trang:>5} {r.so_doan:>5} {r.chien_luoc:<9} "
            f"{r.giay_doc:>5.1f}s {r.giay_chia:>5.1f}s "
            f"{r.giay_embedding:>6.1f}s {r.giay_tong:>6.1f}s"
        )

    print("-" * len(header))
    print(
        f"Hoàn tất: {ok} văn bản, {total_chunks} đoạn, lỗi {failed}; "
        f"tổng thời gian {time.perf_counter() - started:.1f}s. "
        f"Chroma hiện có {store.count()} vector."
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
