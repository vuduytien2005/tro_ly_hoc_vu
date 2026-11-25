"""Kho hỏi đáp cán bộ trong RAG (nâng cấp 10): dựng đoạn từ kho_hoi_dap, lập chỉ mục không cần tệp,
tìm kiếm trả `loai` = hoi_dap để web không hiện nút mở tệp gốc."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from src.rag.embedder import HashingEmbedder
from src.rag.indexer import DocumentMeta, index_chunks
from src.rag.knowledge import KNOWLEDGE_DOC, build_knowledge_chunks
from src.rag.retriever import Retriever
from src.rag.store import VectorStore


@dataclass
class Entry:
    id: int
    cau_hoi: str
    tra_loi: str
    phong_ban: str
    updated_at: datetime


ENTRIES = [
    Entry(7, "Ký túc xá đóng cửa lúc mấy giờ?", "Ký túc xá đóng cửa lúc 23 giờ.", "ctsv",
          datetime(2026, 11, 25, 9, 0)),
    Entry(3, "Lệ phí cấp lại thẻ sinh viên là bao nhiêu?", "Lệ phí cấp lại thẻ là 50.000 đồng.",
          "tai_chinh", datetime(2026, 11, 24, 8, 0)),
]  # fmt: skip


def test_build_knowledge_chunks() -> None:
    chunks = build_knowledge_chunks(ENTRIES, lambda text: len(text.split()))
    assert [c.thu_tu for c in chunks] == [1, 2]  # theo id tăng dần: 3 rồi 7
    first = chunks[0]
    assert first.chuong == "Phòng Kế hoạch – Tài chính"
    assert first.dieu == "Hỏi đáp: Lệ phí cấp lại thẻ sinh viên là bao nhiêu?"
    assert "Câu hỏi: Lệ phí cấp lại thẻ sinh viên là bao nhiêu?" in first.noi_dung
    assert "Trả lời: Lệ phí cấp lại thẻ là 50.000 đồng." in first.noi_dung
    assert "24/11/2026" in first.noi_dung and first.trang is None
    assert first.so_token == len(first.noi_dung.split())


def test_indexed_knowledge_is_searchable_with_kind(
    db: Session, store: VectorStore, embedder: HashingEmbedder, retriever: Retriever
) -> None:
    meta = DocumentMeta(
        ten=KNOWLEDGE_DOC, loai="hoi_dap", phien_ban="kho", ten_tep="", duong_dan_tep=""
    )
    chunks = build_knowledge_chunks(ENTRIES, embedder.count_tokens)
    van_ban_id = index_chunks(db, store, embedder, chunks, meta)
    db.commit()

    found = retriever.search("ký túc xá đóng cửa mấy giờ", "K22", 3)
    assert found and found[0].van_ban_id == van_ban_id
    assert found[0].loai == "hoi_dap" and found[0].van_ban == KNOWLEDGE_DOC
    assert "23 giờ" in found[0].noi_dung
