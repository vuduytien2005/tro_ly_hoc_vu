"""Thử truy xuất RAG từ dòng lệnh (giống tool search_regulations, kèm điểm để gỡ lỗi).

Chạy từ thư mục backend/:
    python scripts/try_search.py "học lại môn bị F" --khoa K22
    python scripts/try_search.py "điều kiện tốt nghiệp" --khoa K21 --top-k 3 --no-keyword
    python scripts/try_search.py "bảo lưu" --khoa K22 --no-filter     # bỏ lọc phiên bản
"""

import argparse
import sys
import time

from src.rag.embedder import get_reranker
from src.rag.retriever import InvalidCohortError, SearchOptions, get_retriever


def main() -> int:
    parser = argparse.ArgumentParser(description="Thử truy xuất quy chế")
    parser.add_argument("cau_hoi")
    parser.add_argument("--khoa", default="K22")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-vector", action="store_true")
    parser.add_argument("--no-keyword", action="store_true")
    parser.add_argument("--no-filter", action="store_true", help="bỏ lọc phiên bản theo khóa")
    parser.add_argument(
        "--rerank", action="store_true", help="bật rerank (tải mô hình ~2GB lần đầu)"
    )
    parser.add_argument("--full", action="store_true", help="in toàn bộ nội dung đoạn")
    args = parser.parse_args()

    retriever = get_retriever()
    if args.rerank and retriever._reranker is None:  # noqa: SLF001 - script gỡ lỗi
        retriever._reranker = get_reranker()  # noqa: SLF001
    options = SearchOptions(
        use_vector=not args.no_vector,
        use_keyword=not args.no_keyword,
        use_version_filter=not args.no_filter,
        use_rerank=args.rerank,
    )
    started = time.perf_counter()
    try:
        results = retriever.search(args.cau_hoi, args.khoa, args.top_k, options)
    except (InvalidCohortError, ValueError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started

    print(f'Câu hỏi: "{args.cau_hoi}" | khóa {args.khoa} | {options}\n')
    if not results:
        print("Không tìm thấy đoạn nào.")
    for r in results:
        ranks = f"vector #{r.vector_rank or '-'} | BM25 #{r.keyword_rank or '-'}"
        if r.rerank_score is not None:
            ranks += f" | rerank {r.rerank_score:.3f}"
        print(
            f"[{r.so}] {r.van_ban} ({r.phien_ban}) – {r.dieu or '(không có Điều)'}"
            f"{f' – khoản {r.khoan}' if r.khoan else ''} – trang {r.trang}"
        )
        print(f"     điểm {r.score:.4f} ({ranks})")
        body = r.noi_dung.split("\n", 1)[-1].replace("\n", " ")
        print(f"     {body if args.full else body[:220] + ('…' if len(body) > 220 else '')}\n")
    print(f"Thời gian truy xuất: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
