"""Bộ kho hỏi đáp mẫu (database/kho_hoi_dap_mau.json) — nạp / xuất / lập chỉ mục ngoài giao diện.

Dùng bởi scripts/seed_knowledge.py: giữ các mục kho trong Git để cài mới / tạo lại CSDL không mất.
Kiểm tra mục giống hệt API thêm mục (POST /api/admin/knowledge): độ dài, phòng ban, không có thông
tin cá nhân. Lập chỉ mục dùng đúng đường của quy_che (build_knowledge_chunks + index_chunks).
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.knowledge import personal_info_problem
from src.assistant_api.models import KhoHoiDap
from src.assistant_api.schemas_admin import CauHoiKho, PhongBan, TraLoiKho
from src.rag.embedder import Embedder
from src.rag.indexer import DocumentMeta, index_chunks
from src.rag.knowledge import (
    KNOWLEDGE_DOC,
    KNOWLEDGE_KIND,
    KNOWLEDGE_VERSION,
    build_knowledge_chunks,
)
from src.rag.store import VectorStore
from src.shared.time import now, to_db

KNOWLEDGE_META = DocumentMeta(
    ten=KNOWLEDGE_DOC,
    loai=KNOWLEDGE_KIND,
    phien_ban=KNOWLEDGE_VERSION,
    ten_tep="",
    duong_dan_tep="",
)


class SeedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cau_hoi: CauHoiKho
    tra_loi: TraLoiKho
    phong_ban: PhongBan


def _key(question: str) -> str:
    return " ".join(question.split()).casefold()


def load_entries(path: Path) -> list[SeedEntry]:
    """Đọc và kiểm tra tệp JSON (mảng mục). Lỗi -> ValueError nêu số thứ tự mục (từ 1)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Tệp kho hỏi đáp phải là một mảng JSON các mục.")
    entries: list[SeedEntry] = []
    seen: set[str] = set()
    for n, item in enumerate(data, start=1):
        try:
            entry = SeedEntry.model_validate(item)
        except ValidationError as exc:
            fields = ", ".join(str(e["loc"][0]) for e in exc.errors() if e["loc"]) or "dữ liệu"
            raise ValueError(f"Mục {n}: không hợp lệ ({fields}).") from exc
        for text in (entry.cau_hoi, entry.tra_loi):
            problem = personal_info_problem(text)
            if problem:
                raise ValueError(f"Mục {n}: có {problem} — kho trả cho mọi sinh viên.")
        key = _key(entry.cau_hoi)
        if key in seen:
            raise ValueError(f"Mục {n}: câu hỏi trùng với một mục phía trước.")
        seen.add(key)
        entries.append(entry)
    return entries


def insert_missing(db: Session, entries: list[SeedEntry], creator_id: int) -> int:
    """Thêm các mục chưa có (so theo câu hỏi, bỏ qua khác biệt khoảng trắng / hoa thường).
    Không commit. Trả số mục đã thêm."""
    existing = {_key(q) for q in db.scalars(select(KhoHoiDap.cau_hoi))}
    stamp = to_db(now())
    added = 0
    for e in entries:
        if _key(e.cau_hoi) in existing:
            continue
        db.add(
            KhoHoiDap(
                cau_hoi=e.cau_hoi,
                tra_loi=e.tra_loi,
                phong_ban=e.phong_ban,
                nguoi_tao_id=creator_id,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        existing.add(_key(e.cau_hoi))
        added += 1
    db.flush()
    return added


def export_entries(db: Session, path: Path) -> int:
    """Ghi toàn bộ mục kho (theo id) ra tệp JSON. Trả số mục."""
    rows = db.scalars(select(KhoHoiDap).order_by(KhoHoiDap.id)).all()
    items = [{"cau_hoi": r.cau_hoi, "tra_loi": r.tra_loi, "phong_ban": r.phong_ban} for r in rows]
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(items)


def index_knowledge(db: Session, store: VectorStore, embedder: Embedder) -> int:
    """Lập chỉ mục lại văn bản kho từ bảng kho_hoi_dap (tạo văn bản nếu chưa có). Không commit.
    Trả van_ban_id."""
    entries = list(db.scalars(select(KhoHoiDap)))
    if not entries:
        raise ValueError("Kho hỏi đáp chưa có mục nào.")
    chunks = build_knowledge_chunks(entries, embedder.count_tokens)
    return index_chunks(db, store, embedder, chunks, KNOWLEDGE_META)
