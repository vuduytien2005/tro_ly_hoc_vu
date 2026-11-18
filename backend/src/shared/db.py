"""Kết nối hai CSDL SQL Server tách biệt: `tlhv_qlsv` (hệ thống của trường)
và `tlhv_assistant` (trợ lý AI).

Mỗi CSDL có engine, session factory và dependency FastAPI riêng, nên một service
chỉ chạm tới đúng CSDL của mình (qlsv_api -> tlhv_qlsv; assistant_api/rag -> tlhv_assistant).
Engine được tạo lười (lần đầu dùng) để import module không mở kết nối.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shared.config import get_settings


def _make_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,  # tự phát hiện kết nối đã bị đóng trước khi dùng
        pool_recycle=3600,
        fast_executemany=True,  # pyodbc: chèn nhiều dòng nhanh (dùng khi lập chỉ mục RAG)
    )


@lru_cache
def get_qlsv_engine() -> Engine:
    return _make_engine(get_settings().qlsv_db_url)


@lru_cache
def get_assistant_engine() -> Engine:
    return _make_engine(get_settings().assistant_db_url)


@lru_cache
def qlsv_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_qlsv_engine(), autoflush=False, expire_on_commit=False)


@lru_cache
def assistant_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_assistant_engine(), autoflush=False, expire_on_commit=False)


def get_qlsv_session() -> Iterator[Session]:
    """Dependency FastAPI: `db: Session = Depends(get_qlsv_session)`."""
    with qlsv_session_factory()() as session:
        yield session


def get_assistant_session() -> Iterator[Session]:
    """Dependency FastAPI: `db: Session = Depends(get_assistant_session)`."""
    with assistant_session_factory()() as session:
        yield session
