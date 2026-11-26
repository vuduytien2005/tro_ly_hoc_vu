"""Bộ kho hỏi đáp mẫu: đọc/kiểm tra tệp JSON, nạp mục còn thiếu, xuất ra tệp, lập chỉ mục."""

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.assistant_api.knowledge_seed import (
    SeedEntry,
    export_entries,
    index_knowledge,
    insert_missing,
    load_entries,
)
from src.assistant_api.models import DoanVanBan, KhoHoiDap, NguoiDung, VanBan
from src.rag.embedder import HashingEmbedder
from src.rag.knowledge import KNOWLEDGE_KIND
from src.rag.store import VectorStore

SAMPLE = Path(__file__).resolve().parents[3] / "database" / "kho_hoi_dap_mau.json"


def write(tmp_path: Path, items: object) -> Path:
    p = tmp_path / "kho.json"
    p.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return p


def entry(cau_hoi: str = "Một tín chỉ tương đương bao nhiêu tiết học?") -> dict[str, str]:
    return {
        "cau_hoi": cau_hoi,
        "tra_loi": "Một tín chỉ bằng 15 tiết lý thuyết.",
        "phong_ban": "dao_tao",
    }


def test_load_entries_reads_valid_file(tmp_path: Path) -> None:
    [e] = load_entries(write(tmp_path, [entry()]))
    assert e == SeedEntry(**entry())


@pytest.mark.parametrize(
    "bad",
    [
        {"cau_hoi": "Ngắn", "tra_loi": "Câu trả lời đủ dài.", "phong_ban": "dao_tao"},
        {**entry(), "phong_ban": "phong_khong_co"},
        {**entry(), "tra_loi": ""},
        {"cau_hoi": "Thiếu trường trả lời và phòng ban"},
    ],
)
def test_load_entries_rejects_invalid_item(tmp_path: Path, bad: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="Mục 1"):
        load_entries(write(tmp_path, [bad]))


def test_load_entries_rejects_duplicate_questions(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="trùng"):
        load_entries(write(tmp_path, [entry(), entry()]))


def test_sample_file_is_valid_and_sizeable() -> None:
    entries = load_entries(SAMPLE)
    assert len(entries) >= 50
    assert {e.phong_ban for e in entries} <= {"dao_tao", "ctsv", "tai_chinh", "khac"}


def test_insert_missing_is_idempotent(db: Session, admin: NguoiDung) -> None:
    db.execute(delete(KhoHoiDap))
    items = [SeedEntry(**entry()), SeedEntry(**entry("Điểm B+ tương ứng bao nhiêu điểm hệ 10?"))]
    assert insert_missing(db, items, admin.id) == 2
    assert insert_missing(db, items, admin.id) == 0  # chạy lại: không trùng
    rows = db.scalars(select(KhoHoiDap)).all()
    assert len(rows) == 2 and {r.nguoi_tao_id for r in rows} == {admin.id}


def test_insert_matches_question_ignoring_spacing(db: Session, admin: NguoiDung) -> None:
    db.execute(delete(KhoHoiDap))
    insert_missing(db, [SeedEntry(**entry())], admin.id)
    spaced = SeedEntry(**entry("  Một tín chỉ  tương đương bao nhiêu tiết học? "))
    assert insert_missing(db, [spaced], admin.id) == 0


def test_export_round_trip(db: Session, admin: NguoiDung, tmp_path: Path) -> None:
    db.execute(delete(KhoHoiDap))
    insert_missing(db, [SeedEntry(**entry())], admin.id)
    out = tmp_path / "xuat.json"
    assert export_entries(db, out) == 1
    assert load_entries(out) == [SeedEntry(**entry())]


def test_index_knowledge_builds_one_chunk_per_entry(
    db: Session, admin: NguoiDung, tmp_path: Path
) -> None:
    db.execute(delete(KhoHoiDap))
    insert_missing(
        db,
        [SeedEntry(**entry()), SeedEntry(**entry("Điểm B+ tương ứng bao nhiêu điểm hệ 10?"))],
        admin.id,
    )
    embedder = HashingEmbedder()
    van_ban_id = index_knowledge(db, VectorStore(tmp_path / "chroma", embedder.name), embedder)
    doc = db.get_one(VanBan, van_ban_id)
    assert doc.loai == KNOWLEDGE_KIND and doc.trang_thai == "da_lap_chi_muc"
    count = db.scalar(select(func.count()).where(DoanVanBan.van_ban_id == van_ban_id))
    assert count == 2
