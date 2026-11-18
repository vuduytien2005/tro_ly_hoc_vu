"""Fixture cho test qlsv_api: chạy trên CSDL THẬT nhưng mỗi test bọc trong 1 transaction
rồi ROLLBACK -> dữ liệu mẫu không bao giờ bị thay đổi.

Kỹ thuật: mở 1 kết nối + BEGIN, gắn Session vào kết nối đó với
join_transaction_mode="create_savepoint". Khi code nghiệp vụ gọi session.commit(), SQLAlchemy
chỉ "commit" tới SAVEPOINT (SQL Server: SAVE TRANSACTION), transaction ngoài vẫn mở và
bị rollback ở cuối test.
"""

from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.qlsv_api.main import app
from src.qlsv_api.routers.deps import get_now
from src.shared.config import get_settings
from src.shared.db import get_qlsv_engine, get_qlsv_session
from src.shared.security import INTERNAL_TOKEN_HEADER
from src.shared.time import VN_TZ

# Thời điểm demo: đang học HK1 2026-2027, đang mở đăng ký HK2 2026-2027 (15/11 → 20/12)
DEMO_NOW = datetime(2026, 11, 20, 9, 0, tzinfo=VN_TZ)
AFTER_REGISTRATION = datetime(2026, 12, 25, 9, 0, tzinfo=VN_TZ)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = get_qlsv_engine()
    try:
        connection = engine.connect()
    except DBAPIError as exc:
        pytest.fail(f"Không kết nối được CSDL tlhv_qlsv. Kiểm tra SQL Server và .env: {exc.orig}")
    outer = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """TestClient dùng CHUNG session đang bọc transaction ở trên, thời gian = DEMO_NOW."""

    def _session() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_qlsv_session] = _session
    app.dependency_overrides[get_now] = lambda: DEMO_NOW
    with TestClient(app, headers={INTERNAL_TOKEN_HEADER: get_settings().internal_api_token}) as c:
        yield c
    app.dependency_overrides.clear()
