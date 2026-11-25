"""Kho hỏi đáp cán bộ (nâng cấp 10): dựng các mục `kho_hoi_dap` thành đoạn của MỘT văn bản loại
`hoi_dap` (không có tệp). Tìm kiếm, trích dẫn, bọc <tai_lieu>, kiểm chứng dùng lại y nguyên."""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from src.rag.chunker import Chunk
from src.shared.departments import PHONG_BAN

KNOWLEDGE_DOC = "Hỏi đáp cán bộ"
KNOWLEDGE_KIND = "hoi_dap"
KNOWLEDGE_VERSION = "kho"
QUESTION_LABEL_MAX = 200


class KnowledgeEntry(Protocol):
    id: int
    cau_hoi: str
    tra_loi: str
    phong_ban: str
    updated_at: datetime


def department_name(code: str) -> str:
    name = PHONG_BAN.get(code, PHONG_BAN["khac"])
    return name if code != "khac" else "Cán bộ phụ trách"


def build_knowledge_chunks(
    entries: Sequence[KnowledgeEntry], count_tokens: Callable[[str], int]
) -> list[Chunk]:
    """Mỗi mục một đoạn, thứ tự theo id (ổn định giữa các lần lập chỉ mục lại)."""
    chunks = []
    for thu_tu, e in enumerate(sorted(entries, key=lambda x: x.id), start=1):
        phong = department_name(e.phong_ban)
        question = " ".join(e.cau_hoi.split())
        text = (
            f"[{KNOWLEDGE_DOC} — {phong}, cập nhật {e.updated_at:%d/%m/%Y}]\n"
            f"Câu hỏi: {question}\n"
            f"Trả lời: {e.tra_loi.strip()}"
        )
        label = question if len(question) <= QUESTION_LABEL_MAX else question[:199] + "…"
        chunks.append(
            Chunk(
                thu_tu=thu_tu,
                noi_dung=text,
                trang=None,
                so_token=count_tokens(text),
                chuong=phong,
                dieu=f"Hỏi đáp: {label}",
            )
        )
    return chunks
