"""TN1 — Chất lượng truy xuất (Hit@1/3/5, MRR) theo cấu hình R1..R6. KHÔNG gọi LLM (miễn phí).

    python evaluation\\run_rag_retrieval.py   # R1..R4 (+R5/R6 nếu mô hình đã có)
    python evaluation\\run_rag_retrieval.py --configs R4 R5 --cho-phep-tai
    ... --limit 5 --embedder hashing     # chạy thử nhanh, không cần mô hình

Mỗi cấu hình: lập chỉ mục bộ văn bản vào Chroma tạm + CSDL trong transaction rollback
(không đụng dữ liệu thật), rồi truy xuất từng câu hỏi.
Câu "ngoai_pham_vi" không có nguồn đúng -> không tính Hit/MRR.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import (  # noqa: E402
    bootstrap,
    dataset_path,
    load_config,
    markdown_table,
    model_cached,
    new_run_dir,
    progress,
    read_jsonl,
    save_configs,
    write_csv,
)

bootstrap()

from evaluation import metrics  # noqa: E402
from evaluation.corpus import corpus_folders, index_corpus, isolated_db, temp_dir  # noqa: E402

DEFAULT_CONFIGS = ["R1", "R2", "R3", "R4", "R5", "R6"]
LOAI = ("chung", "phu_thuoc_khoa")


def needed_models(config: dict[str, Any], embedder_kind: str) -> list[str]:
    """Mô hình Hugging Face cấu hình cần. Chế độ hashing chỉ thay embedding, reranker vẫn là mô hình
    thật -> vẫn phải kiểm tra (tránh tự tải ~2 GB)."""
    models = [config["embedding"]] if embedder_kind == "model" else []
    if config.get("use_rerank") and config.get("reranker"):
        models.append(config["reranker"])
    return models


def run_config(
    config: dict[str, Any], questions: list[dict[str, Any]], embedder_kind: str, cache: dict
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from src.rag.embedder import CrossEncoderReranker, HashingEmbedder, SentenceTransformerEmbedder
    from src.rag.retriever import Retriever, SearchOptions
    from src.rag.store import VectorStore
    from src.shared.config import get_settings
    from src.shared.db import get_assistant_engine

    key = "hashing" if embedder_kind == "hashing" else config["embedding"]
    if key not in cache:
        cache[key] = (
            HashingEmbedder() if embedder_kind == "hashing" else SentenceTransformerEmbedder(key)
        )
    embedder = cache[key]
    reranker = None
    if config.get("use_rerank") and config.get("reranker"):
        rkey = "rerank:" + config["reranker"]
        cache.setdefault(rkey, CrossEncoderReranker(config["reranker"]))
        reranker = cache[rkey]

    options = SearchOptions(
        use_vector=bool(config.get("use_vector", True)),
        use_keyword=bool(config.get("use_keyword", False)),
        use_version_filter=bool(config.get("use_version_filter", False)),
        use_rerank=reranker is not None,
    )
    top_k = int(config.get("top_k", 5))
    rows: list[dict[str, Any]] = []
    with isolated_db(get_assistant_engine()) as iso, temp_dir("tn1_chroma_") as chroma:
        store = VectorStore(chroma, embedder.name)
        info = index_corpus(
            iso.factory,
            store,
            embedder,
            corpus_folders(config),
            config.get("chien_luoc_chunk"),
            get_settings().chunk_max_tokens,
        )
        print(
            f"  Lập chỉ mục: {info['so_van_ban']} văn bản, {info['so_doan']} đoạn, {info['giay']} s"
        )
        retriever = Retriever(iso.factory, store, embedder, reranker, options)
        for i, q in enumerate(questions, start=1):
            started = time.perf_counter()
            hits = retriever.search(q["cau_hoi"], q.get("ma_khoa"), top_k, options)
            ms = (time.perf_counter() - started) * 1000
            found = [
                {
                    "van_ban": h.van_ban,
                    "phien_ban": h.phien_ban,
                    "dieu": h.dieu,
                    "noi_dung": h.noi_dung,
                }
                for h in hits
            ]
            rank = metrics.first_hit_rank(found, q.get("nguon_dung") or [])
            rows.append(
                {
                    "cau_hinh": config["ma"],
                    "id": q["id"],
                    "loai": q.get("loai"),
                    "ma_khoa": q.get("ma_khoa"),
                    "cau_hoi": q["cau_hoi"],
                    "hang_dung": rank,
                    "thoi_gian_ms": round(ms, 1),
                    "ket_qua": [f"{h.van_ban} {h.phien_ban} · {h.dieu or '—'}" for h in hits],
                }
            )
            if i % 10 == 0 or i == len(questions):
                progress(i, len(questions), q["id"])
    return rows, info


def summarize(
    config: dict[str, Any], rows: list[dict[str, Any]], info: dict[str, Any]
) -> list[dict]:
    out = []
    groups: list[tuple[str, list[dict[str, Any]]]] = [
        ("tat_ca", [r for r in rows if r["loai"] in LOAI])
    ]
    groups += [(loai, [r for r in rows if r["loai"] == loai]) for loai in LOAI]
    for name, items in groups:
        scores = metrics.retrieval_scores([r["hang_dung"] for r in items])
        out.append(
            {
                "cau_hinh": config["ma"],
                "mo_ta": config.get("ten", ""),
                "nhom": name,
                **scores,
                "so_doan": info["so_doan"],
                "thoi_gian_tb_ms": round(sum(r["thoi_gian_ms"] for r in items) / len(items), 1)
                if items
                else None,
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--configs", nargs="+", default=DEFAULT_CONFIGS, help="vd R1 R2 (tên tệp rag_<mã>.yaml)"
    )
    parser.add_argument("--limit", type=int, help="chỉ chạy N câu đầu")
    parser.add_argument("--du-lieu", help="ghi đè tệp câu hỏi (.jsonl)")
    parser.add_argument(
        "--embedder",
        choices=["model", "hashing"],
        default="model",
        help="hashing = không tải mô hình, chỉ để thử script",
    )
    parser.add_argument(
        "--cho-phep-tai",
        action="store_true",
        help="cho phép tải mô hình chưa có trên máy (bge-m3, reranker ~2 GB mỗi cái)",
    )
    args = parser.parse_args()

    configs = [
        load_config(c if c.startswith("rag_") or "/" in c else f"rag_{c}") for c in args.configs
    ]
    selected, skipped = [], []
    for c in configs:
        missing = [m for m in needed_models(c, args.embedder) if not model_cached(m)]
        if missing and not args.cho_phep_tai:
            skipped.append((c["ma"], missing))
        else:
            selected.append(c)
    for code, missing in skipped:
        print(
            f"Bỏ qua {code}: chưa có mô hình {', '.join(missing)} trên máy "
            "(thêm --cho-phep-tai để tải về)."
        )
    if not selected:
        print("Không còn cấu hình nào để chạy.")
        return 1

    run_dir = new_run_dir("tn1_truy_xuat")
    all_rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    cache: dict[str, Any] = {}
    started = time.perf_counter()
    for c in selected:
        questions = read_jsonl(args.du_lieu or dataset_path(c, "rag_questions.jsonl"), args.limit)
        print(f"\n== {c['ma']}: {c.get('ten', '')} ({len(questions)} câu)")
        rows, info = run_config(c, questions, args.embedder, cache)
        all_rows += rows
        summary += summarize(c, rows, info)

    write_csv(run_dir / "chi_tiet.csv", all_rows)
    write_csv(run_dir / "tong_hop.csv", summary)
    columns = [
        ("cau_hinh", "Cấu hình"),
        ("mo_ta", "Mô tả"),
        ("hit@1", "Hit@1"),
        ("hit@3", "Hit@3"),
        ("hit@5", "Hit@5"),
        ("mrr", "MRR"),
        ("n", "Số câu"),
        ("thoi_gian_tb_ms", "TB (ms)"),
    ]
    pct = {"hit@1", "hit@3", "hit@5"}
    md = ["# TN1 — Chất lượng truy xuất", ""]
    if args.embedder == "hashing":
        md += ["> CHẠY THỬ với HashingEmbedder — số liệu KHÔNG dùng cho khóa luận.", ""]
    md += [
        "## Tất cả câu có nguồn đúng",
        "",
        markdown_table([s for s in summary if s["nhom"] == "tat_ca"], columns, pct),
        "",
    ]
    for loai in LOAI:
        md += [
            f"## Nhóm `{loai}`",
            "",
            markdown_table([s for s in summary if s["nhom"] == loai], columns, pct),
            "",
        ]
    if skipped:
        md += [
            "Bỏ qua (chưa có mô hình): " + "; ".join(f"{c} ({', '.join(m)})" for c, m in skipped),
            "",
        ]
    (run_dir / "bang.md").write_text("\n".join(md), encoding="utf-8")
    save_configs(
        run_dir,
        selected,
        {
            "tn": "TN1",
            "embedder": args.embedder,
            "limit": args.limit,
            "bo_qua": dict(skipped),
            "giay": round(time.perf_counter() - started, 1),
        },
    )
    print("\n" + markdown_table([s for s in summary if s["nhom"] == "tat_ca"], columns, pct))
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
