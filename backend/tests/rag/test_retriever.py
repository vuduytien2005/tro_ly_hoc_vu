"""indexer + retriever trên CSDL thật (rollback) và Chroma tạm.

Kiểm tra lọc phiên bản, RRF, cờ thực nghiệm.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.assistant_api.models import DoanVanBan, VanBan
from src.rag.embedder import HashingEmbedder
from src.rag.indexer import DocumentMeta, delete_document, index_document, mark_failed
from src.rag.retriever import InvalidCohortError, Retriever, SearchOptions, parse_ma_khoa, rrf_fuse
from src.rag.store import VectorStore
from tests.rag.conftest import DOC_NAME, SAMPLE, make_version

MAX_CREDITS_Q = "khối lượng đăng ký tối đa bao nhiêu tín chỉ mỗi học kỳ"


def _versions(results: list) -> set[str]:
    return {r.phien_ban for r in results}


# --- tiện ích -------------------------------------------------------------
@pytest.mark.parametrize(("value", "expected"), [("K22", 22), ("k21", 21), (" 23 ", 23)])
def test_parse_ma_khoa(value: str, expected: int) -> None:
    assert parse_ma_khoa(value) == expected


@pytest.mark.parametrize("value", ["", "K2", "KHOA22", "K222", "22A"])
def test_parse_ma_khoa_invalid(value: str) -> None:
    with pytest.raises(InvalidCohortError):
        parse_ma_khoa(value)


def test_rrf_fuse() -> None:
    fused = rrf_fuse([[1, 2, 3], [3, 1]], rrf_k=60)
    assert [doc_id for doc_id, _ in fused] == [1, 3, 2]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


# --- indexer --------------------------------------------------------------
def test_index_document_writes_db_and_chroma(
    two_versions: dict[str, int], db: Session, store: VectorStore
) -> None:
    vb = db.get(VanBan, two_versions["2023"])
    assert vb is not None
    assert vb.trang_thai == "da_lap_chi_muc"
    assert vb.so_doan == 8  # mở đầu + 7 Điều
    chunks = db.scalars(select(DoanVanBan).where(DoanVanBan.van_ban_id == vb.id)).all()
    assert len(chunks) == 8
    assert chunks[0].vector_id == f"vb{vb.id}_d1"
    assert store.count() == 16  # 2 phiên bản x 8 đoạn


def test_reindex_is_idempotent(
    two_versions: dict[str, int],
    db: Session,
    store: VectorStore,
    embedder: HashingEmbedder,
    tmp_path: Path,
) -> None:
    meta = DocumentMeta(
        ten=DOC_NAME,
        loai="quy_che",
        phien_ban="2023",
        ten_tep="quy_che_2023.txt",
        duong_dan_tep="x",
        ap_dung_tu_khoa=22,
    )
    result = index_document(db, store, embedder, tmp_path / "quy_che_2023.txt", meta, max_tokens=90)
    db.commit()
    assert result.van_ban_id == two_versions["2023"]  # cùng văn bản, không tạo mới
    assert db.scalar(select(func.count(VanBan.id))) == 2
    count = db.scalar(
        select(func.count(DoanVanBan.id)).where(DoanVanBan.van_ban_id == result.van_ban_id)
    )
    assert count == result.so_doan > 8  # max_tokens nhỏ hơn -> nhiều đoạn hơn, đoạn cũ đã xóa
    assert store.count() == 8 + result.so_doan


def test_delete_document(two_versions: dict[str, int], db: Session, store: VectorStore) -> None:
    assert delete_document(db, store, two_versions["2021"])
    db.commit()
    assert db.get(VanBan, two_versions["2021"]) is None
    assert store.count() == 8
    assert not delete_document(db, store, 999_999)


def test_mark_failed(db: Session) -> None:
    meta = DocumentMeta(
        ten="Hỏng", loai="quy_che", phien_ban="1", ten_tep="x.pdf", duong_dan_tep="x.pdf"
    )
    mark_failed(db, meta, "PDF không có lớp chữ")
    db.commit()
    vb = db.scalar(select(VanBan).where(VanBan.ten == "Hỏng"))
    assert vb is not None and vb.trang_thai == "loi" and vb.loi == "PDF không có lớp chữ"


# --- lọc phiên bản ----------------------------------------------------------
@pytest.mark.parametrize(
    ("ma_khoa", "version", "credits"),
    [("K20", "2021", "24"), ("K21", "2021", "24"), ("K22", "2023", "25"), ("K25", "2023", "25")],
)
def test_version_filter(
    two_versions: dict[str, int], retriever: Retriever, ma_khoa: str, version: str, credits: str
) -> None:
    results = retriever.search(MAX_CREDITS_Q, ma_khoa, top_k=8)
    assert results
    assert _versions(results) == {version}
    top = next(r for r in results if r.dieu == "Điều 3. Đăng ký học phần")
    assert f"tối đa là {credits} tín chỉ" in top.noi_dung


@pytest.mark.parametrize(
    "options",
    [SearchOptions(use_keyword=False), SearchOptions(use_vector=False)],
    ids=["chi_vector", "chi_bm25"],
)
def test_version_filter_applies_to_each_branch(
    two_versions: dict[str, int], retriever: Retriever, options: SearchOptions
) -> None:
    assert _versions(retriever.search(MAX_CREDITS_Q, "K21", 8, options)) == {"2021"}
    assert _versions(retriever.search(MAX_CREDITS_Q, "K22", 8, options)) == {"2023"}


def test_without_version_filter_mixes_versions(
    two_versions: dict[str, int], retriever: Retriever
) -> None:
    results = retriever.search(MAX_CREDITS_Q, None, 8, SearchOptions(use_version_filter=False))
    assert _versions(results) == {"2021", "2023"}


# --- ngày hiệu lực (bổ sung 23/11/2026) --------------------------------------
@pytest.fixture
def future_version(
    two_versions: dict[str, int],
    tmp_path: Path,
    db: Session,
    store: VectorStore,
    embedder: HashingEmbedder,
) -> int:
    """Bản 2099 áp dụng từ K22 nhưng CHƯA có hiệu lực (ngày hiệu lực 01/08/2099)."""
    path = make_version(tmp_path, "2099", 30, "3. Điểm học lại theo quy định mới.")
    meta = DocumentMeta(
        ten=DOC_NAME,
        loai="quy_che",
        phien_ban="2099",
        ten_tep=path.name,
        duong_dan_tep=str(path),
        ap_dung_tu_khoa=22,
        ngay_hieu_luc=date(2099, 8, 1),
    )
    van_ban_id = index_document(db, store, embedder, path, meta).van_ban_id
    db.commit()
    return van_ban_id


@pytest.mark.parametrize(
    "options",
    [SearchOptions(), SearchOptions(use_keyword=False), SearchOptions(use_vector=False)],
    ids=["lai", "chi_vector", "chi_bm25"],
)
def test_not_yet_effective_document_is_hidden(
    future_version: int, retriever: Retriever, options: SearchOptions
) -> None:
    assert _versions(retriever.search(MAX_CREDITS_Q, "K22", 8, options)) == {"2023"}


def test_document_becomes_visible_on_effective_date(
    future_version: int, retriever: Retriever, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.rag import retriever as retriever_module

    monkeypatch.setattr(retriever_module, "_today", lambda: date(2099, 8, 1))
    assert "2099" in _versions(retriever.search(MAX_CREDITS_Q, "K22", 8))


def test_without_version_filter_also_ignores_effective_date(
    future_version: int, retriever: Retriever
) -> None:
    results = retriever.search(MAX_CREDITS_Q, None, 12, SearchOptions(use_version_filter=False))
    assert "2099" in _versions(results)


def test_invalid_cohort(two_versions: dict[str, int], retriever: Retriever) -> None:
    with pytest.raises(InvalidCohortError):
        retriever.search("học lại", "khoa22")


# --- kết quả ----------------------------------------------------------------
def test_retake_question_finds_retake_article(
    two_versions: dict[str, int], retriever: Retriever
) -> None:
    results = retriever.search("học lại môn bị F", "K22", top_k=3)
    assert results[0].dieu == "Điều 4. Học lại và học cải thiện điểm"
    assert results[0].phien_ban == "2023"
    assert results[0].trang == 2
    assert [r.so for r in results] == [1, 2, 3]
    assert results[0].vector_rank is not None and results[0].keyword_rank is not None


def test_top_k_and_empty_query(two_versions: dict[str, int], retriever: Retriever) -> None:
    assert len(retriever.search("tín chỉ", "K22", top_k=2)) == 2
    assert retriever.search("   ", "K22") == []


def test_requires_one_branch(retriever: Retriever) -> None:
    with pytest.raises(ValueError):
        retriever.search("x", "K22", options=SearchOptions(use_vector=False, use_keyword=False))


def test_ignores_documents_not_indexed(
    two_versions: dict[str, int], db: Session, retriever: Retriever
) -> None:
    vb = db.get(VanBan, two_versions["2023"])
    assert vb is not None
    vb.trang_thai = "loi"
    db.commit()
    assert retriever.search(MAX_CREDITS_Q, "K22", 8) == []


def test_keyword_index_refreshes_after_new_document(
    db: Session, store: VectorStore, embedder: HashingEmbedder, retriever: Retriever
) -> None:
    assert retriever.search("học lại", "K22", options=SearchOptions(use_vector=False)) == []
    meta = DocumentMeta(
        ten=DOC_NAME, loai="quy_che", phien_ban="2023", ten_tep=SAMPLE.name, duong_dan_tep="x"
    )
    index_document(db, store, embedder, SAMPLE, meta)
    db.commit()
    assert retriever.search("học lại", "K22", options=SearchOptions(use_vector=False))


class FakeReranker:
    """Đẩy đoạn chứa 'tốt nghiệp' lên đầu."""

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [1.0 if "tốt nghiệp" in p else 0.0 for p in passages]


def test_rerank_reorders(
    two_versions: dict[str, int],
    session_factory: Callable[[], Session],
    store: VectorStore,
    embedder: HashingEmbedder,
) -> None:
    retriever = Retriever(session_factory, store, embedder, reranker=FakeReranker())
    results = retriever.search("học lại môn bị F", "K22", 3, SearchOptions(use_rerank=True))
    assert results[0].dieu == "Điều 7. Điều kiện tốt nghiệp"
    assert results[0].rerank_score == 1.0
