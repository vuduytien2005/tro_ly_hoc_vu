"""Fixture cho test RAG.

- CSDL tlhv_assistant THẬT, mỗi test bọc trong 1 transaction rồi ROLLBACK (như tests/qlsv).
  Đầu mỗi test xóa mọi văn bản đang có (cũng bị rollback) -> test không phụ thuộc PDF thật đã nạp.
- ChromaDB trong thư mục tạm của pytest -> không đụng data/chroma.
- HashingEmbedder: không cần tải mô hình, chạy nhanh, kết quả tất định.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, delete
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.assistant_api.models import VanBan
from src.rag.embedder import HashingEmbedder
from src.rag.indexer import DocumentMeta, index_document
from src.rag.retriever import Retriever
from src.rag.store import VectorStore
from src.shared.db import get_assistant_engine

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "quy_che_mau.txt"
DOC_NAME = "Quy chế đào tạo (giả lập)"


@pytest.fixture
def connection() -> Iterator[Connection]:
    try:
        conn = get_assistant_engine().connect()
    except DBAPIError as exc:
        pytest.fail(f"Không kết nối được CSDL tlhv_assistant: {exc.orig}")
    outer = conn.begin()
    try:
        yield conn
    finally:
        outer.rollback()
        conn.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    def factory() -> Session:
        return Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )

    return factory


@pytest.fixture
def db(session_factory: Callable[[], Session]) -> Iterator[Session]:
    session = session_factory()
    session.execute(delete(VanBan))  # cô lập khỏi văn bản thật (bị rollback cuối test)
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def embedder() -> HashingEmbedder:
    return HashingEmbedder()


@pytest.fixture
def store(tmp_path: Path, embedder: HashingEmbedder) -> VectorStore:
    return VectorStore(tmp_path / "chroma", embedder.name)


@pytest.fixture
def retriever(
    session_factory: Callable[[], Session], store: VectorStore, embedder: HashingEmbedder
) -> Retriever:
    return Retriever(session_factory, store, embedder)


def make_version(tmp_path: Path, phien_ban: str, max_credits: int, retake_rule: str) -> Path:
    """Tạo một phiên bản giả của văn bản mẫu với nội dung khác biệt dễ kiểm tra."""
    text = SAMPLE.read_text(encoding="utf-8")
    text = text.replace("tối đa là 25 tín chỉ", f"tối đa là {max_credits} tín chỉ")
    text = text.replace("3. Điểm học lại được lấy theo lần học có điểm cao nhất.", retake_rule)
    path = tmp_path / f"quy_che_{phien_ban}.txt"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def two_versions(
    tmp_path: Path, db: Session, store: VectorStore, embedder: HashingEmbedder
) -> dict[str, int]:
    """Bản 2021 áp dụng đến K21, bản 2023 áp dụng từ K22. Trả {phiên bản: van_ban_id}."""
    specs = [
        ("2021", None, 21, 24, "3. Điểm học lại thay thế điểm lần học trước."),
        ("2023", 22, None, 25, "3. Điểm học lại được lấy theo lần học có điểm cao nhất."),
    ]
    ids: dict[str, int] = {}
    for phien_ban, tu, den, credits, rule in specs:
        path = make_version(tmp_path, phien_ban, credits, rule)
        meta = DocumentMeta(
            ten=DOC_NAME,
            loai="quy_che",
            phien_ban=phien_ban,
            ten_tep=path.name,
            duong_dan_tep=str(path),
            ap_dung_tu_khoa=tu,
            ap_dung_den_khoa=den,
        )
        ids[phien_ban] = index_document(db, store, embedder, path, meta).van_ban_id
    db.commit()
    return ids
