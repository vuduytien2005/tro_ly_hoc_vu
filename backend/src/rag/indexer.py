"""Lập chỉ mục một văn bản: đọc -> làm sạch -> chia đoạn -> embedding -> ghi CSDL + ChromaDB.

- Văn bản nhận diện theo (ten, loai, phien_ban). Lập chỉ mục lại cùng văn bản: xóa đoạn + vector cũ
  rồi ghi mới -> chạy lại bao nhiêu lần cũng không bị trùng.
- Thứ tự an toàn: ghi `doan_van_ban` (flush, CHƯA commit) -> upsert Chroma -> người gọi commit.
  Nếu commit lỗi, vector "mồ côi" trong Chroma bị retriever bỏ qua (chỉ nhận vector có đoạn tương
  ứng thuộc văn bản `da_lap_chi_muc`) và bị ghi đè ở lần lập chỉ mục sau (cùng vector_id).
- Không commit trong hàm; `mark_failed` dùng cho người gọi ghi trạng thái lỗi.
"""

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.assistant_api.models import DoanVanBan, VanBan
from src.rag import cleaner, loader
from src.rag.chunker import Chunk, DocumentInfo, chunk_document
from src.rag.embedder import Embedder
from src.rag.store import OPEN_FROM, OPEN_TO, VectorStore
from src.shared.time import now, to_db


@dataclass(frozen=True)
class DocumentMeta:
    ten: str
    loai: str
    phien_ban: str
    ten_tep: str
    duong_dan_tep: str
    ap_dung_tu_khoa: int | None = None
    ap_dung_den_khoa: int | None = None
    ngay_hieu_luc: date | None = None
    chien_luoc_chunk: str = "theo_dieu"


@dataclass(frozen=True)
class IndexResult:
    van_ban_id: int
    so_trang: int
    so_doan: int
    chien_luoc: str
    giay_doc: float
    giay_chia: float
    giay_embedding: float
    giay_tong: float


def vector_id(van_ban_id: int, thu_tu: int) -> str:
    return f"vb{van_ban_id}_d{thu_tu}"


def _touch(van_ban: VanBan) -> None:
    # Ghi updated_at tường minh (trigger tôn trọng giá trị này) -> retriever thấy dữ liệu đổi
    van_ban.updated_at = to_db(now())
    flag_modified(van_ban, "updated_at")


def find_document(db: Session, meta: DocumentMeta) -> VanBan | None:
    return db.scalar(
        select(VanBan).where(
            VanBan.ten == meta.ten, VanBan.loai == meta.loai, VanBan.phien_ban == meta.phien_ban
        )
    )


def _upsert_document(db: Session, meta: DocumentMeta) -> VanBan:
    van_ban = find_document(db, meta)
    if van_ban is None:
        van_ban = VanBan(ten=meta.ten, loai=meta.loai, phien_ban=meta.phien_ban)
        db.add(van_ban)
    van_ban.ten_tep = meta.ten_tep
    van_ban.duong_dan_tep = meta.duong_dan_tep
    van_ban.ap_dung_tu_khoa = meta.ap_dung_tu_khoa
    van_ban.ap_dung_den_khoa = meta.ap_dung_den_khoa
    van_ban.ngay_hieu_luc = meta.ngay_hieu_luc
    van_ban.chien_luoc_chunk = meta.chien_luoc_chunk
    van_ban.trang_thai = "dang_xu_ly"
    van_ban.loi = None
    db.flush()
    return van_ban


def index_document(
    db: Session,
    store: VectorStore,
    embedder: Embedder,
    path: Path,
    meta: DocumentMeta,
    *,
    max_tokens: int = 512,
) -> IndexResult:
    """Lập chỉ mục 1 tệp. Không commit."""
    t0 = time.perf_counter()
    pages = cleaner.clean_pages(loader.load(path))
    t1 = time.perf_counter()

    chunks, used_strategy = chunk_document(
        pages,
        DocumentInfo(meta.ten, meta.phien_ban),
        meta.chien_luoc_chunk,
        max_tokens=max_tokens,
        count_tokens=embedder.count_tokens,
    )
    if not chunks:
        raise ValueError("Không trích được nội dung nào từ tệp.")
    t2 = time.perf_counter()

    van_ban_id = index_chunks(db, store, embedder, chunks, meta)
    t3 = time.perf_counter()

    return IndexResult(
        van_ban_id=van_ban_id,
        so_trang=len(pages),
        so_doan=len(chunks),
        chien_luoc=used_strategy,
        giay_doc=t1 - t0,
        giay_chia=t2 - t1,
        giay_embedding=t3 - t2,
        giay_tong=t3 - t0,
    )


def index_chunks(
    db: Session, store: VectorStore, embedder: Embedder, chunks: list[Chunk], meta: DocumentMeta
) -> int:
    """Ghi các đoạn đã chia sẵn (thay toàn bộ đoạn + vector cũ) -> `da_lap_chi_muc`. Dùng chung cho
    tệp (`index_document`) và kho hỏi đáp (đoạn dựng từ CSDL, không có tệp). Không commit.
    Trả van_ban_id."""
    if not chunks:
        raise ValueError("Không có đoạn nào để lập chỉ mục.")
    van_ban = _upsert_document(db, meta)
    db.execute(delete(DoanVanBan).where(DoanVanBan.van_ban_id == van_ban.id))
    store.delete_document(van_ban.id)

    rows = [
        DoanVanBan(
            van_ban_id=van_ban.id,
            thu_tu=c.thu_tu,
            chuong=c.chuong[:255] if c.chuong else None,
            dieu=c.dieu[:255] if c.dieu else None,
            khoan=c.khoan,
            trang=c.trang,
            noi_dung=c.noi_dung,
            so_token=c.so_token,
            vector_id=vector_id(van_ban.id, c.thu_tu),
        )
        for c in chunks
    ]
    db.add_all(rows)
    db.flush()

    embeddings = embedder.embed_documents([r.noi_dung for r in rows])
    store.upsert(
        ids=[r.vector_id for r in rows],
        embeddings=embeddings,
        documents=[r.noi_dung for r in rows],
        metadatas=[
            {
                "van_ban_id": van_ban.id,
                "doan_id": r.id,
                "loai": meta.loai,
                "phien_ban": meta.phien_ban,
                "ap_dung_tu": meta.ap_dung_tu_khoa
                if meta.ap_dung_tu_khoa is not None
                else OPEN_FROM,
                "ap_dung_den": meta.ap_dung_den_khoa
                if meta.ap_dung_den_khoa is not None
                else OPEN_TO,
                "dieu": r.dieu or "",
                "trang": r.trang or 0,
            }
            for r in rows
        ],
    )

    van_ban.trang_thai = "da_lap_chi_muc"
    van_ban.so_doan = len(rows)
    _touch(van_ban)
    db.flush()
    return van_ban.id


def mark_failed(db: Session, meta: DocumentMeta, message: str) -> None:
    """Ghi trạng thái lỗi (gọi sau khi đã rollback lần lập chỉ mục hỏng). Không commit."""
    van_ban = _upsert_document(db, meta)
    van_ban.trang_thai = "loi"
    van_ban.loi = message[:4000]
    _touch(van_ban)
    db.flush()


def delete_document(db: Session, store: VectorStore, van_ban_id: int) -> bool:
    """Xóa văn bản (đoạn bị xóa theo ON DELETE CASCADE) + vector. Không commit."""
    van_ban = db.get(VanBan, van_ban_id)
    if van_ban is None:
        return False
    db.delete(van_ban)
    db.flush()
    store.delete_document(van_ban_id)
    return True
