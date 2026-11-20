"""Kiểm tra kết nối 2 CSDL và model ORM khớp với schema thật trong SQL Server.

Yêu cầu: SQL Server đang chạy, đã chạy 4 script trong database/, có file .env.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session

from src.assistant_api.models import (
    AssistantBase,
    CongCu,
    HoiThoai,
    LuotGoiCongCu,
    McpServer,
    NguoiDung,
    TinNhan,
)
from src.qlsv_api.models import QlsvBase, SinhVien
from src.shared.db import (
    assistant_session_factory,
    get_assistant_engine,
    get_qlsv_engine,
    qlsv_session_factory,
)


def _connect_or_fail(engine: Engine, name: str) -> None:
    try:
        with engine.connect():
            pass
    except (OperationalError, InterfaceError) as exc:
        pytest.fail(
            f"Không kết nối được CSDL '{name}'. Kiểm tra SQL Server và file .env: {exc.orig}"
        )


@pytest.fixture(scope="module")
def qlsv_db() -> Iterator[Session]:
    _connect_or_fail(get_qlsv_engine(), "qlsv")
    with qlsv_session_factory()() as session:
        yield session


@pytest.fixture(scope="module")
def assistant_db() -> Iterator[Session]:
    _connect_or_fail(get_assistant_engine(), "assistant")
    with assistant_session_factory()() as session:
        yield session


def test_read_five_students(qlsv_db: Session) -> None:
    students = qlsv_db.scalars(select(SinhVien).order_by(SinhVien.id)).all()
    assert len(students) == 5
    assert students[0].ma_sv == "SV22001"
    assert students[0].ho_ten == "Nguyễn Văn An"  # utf8mb4 đọc đúng tiếng Việt
    assert students[0].khoa_hoc.ma_khoa == "K22"


def test_read_seed_tools(assistant_db: Session) -> None:
    # 16 công cụ ban đầu + plan_next_semester, register_courses_bundle (ý tưởng 3, nâng cấp 07)
    assert assistant_db.scalar(select(func.count()).select_from(CongCu)) == 18
    assert assistant_db.scalar(select(func.count()).select_from(McpServer)) == 4

    register = assistant_db.scalar(select(CongCu).where(CongCu.ten == "register_course"))
    assert register is not None
    assert register.can_xac_nhan is True
    assert register.muc_rui_ro == "ghi"
    assert register.mcp_server.ten == "dao_tao"


def _assert_models_match_db(base: type[DeclarativeBase], engine: Engine) -> None:
    """Mọi bảng/cột của ORM phải tồn tại trong CSDL và ngược lại."""
    insp = inspect(engine)
    db_tables = set(insp.get_table_names())
    orm_tables = set(base.metadata.tables)
    assert orm_tables == db_tables, f"Lệch bảng: ORM={orm_tables ^ db_tables}"

    for name, table in base.metadata.tables.items():
        db_cols = {c["name"] for c in insp.get_columns(name)}
        orm_cols = set(table.columns.keys())
        assert orm_cols == db_cols, f"Bảng {name} lệch cột: {orm_cols ^ db_cols}"


def test_qlsv_models_match_schema(qlsv_db: Session) -> None:
    _assert_models_match_db(QlsvBase, get_qlsv_engine())


def test_assistant_models_match_schema(assistant_db: Session) -> None:
    _assert_models_match_db(AssistantBase, get_assistant_engine())


@pytest.mark.parametrize(
    ("base", "session_name"),
    [(QlsvBase, "qlsv_db"), (AssistantBase, "assistant_db")],
)
def test_every_model_can_be_queried(
    base: type[DeclarativeBase], session_name: str, request: pytest.FixtureRequest
) -> None:
    """Đọc thử vài dòng mỗi bảng: phát hiện sai kiểu (ENUM, JSON, DECIMAL, TIME...)."""
    session: Session = request.getfixturevalue(session_name)
    for mapper in base.registry.mappers:
        session.scalars(select(mapper.class_).limit(5)).all()


def test_write_round_trip_rolls_back() -> None:
    """Ghi thử rồi ROLLBACK: bảng có trigger (lấy id qua SCOPE_IDENTITY), JSON NULL
    (CHECK ISJSON), JSON có tiếng Việt, trigger cập nhật updated_at."""
    _connect_or_fail(get_assistant_engine(), "assistant")
    with assistant_session_factory()() as db:
        try:
            user = db.scalar(select(NguoiDung).where(NguoiDung.ma_sv == "SV22001"))
            assert user is not None, "Chạy scripts/seed_users.py trước"

            conv = HoiThoai(nguoi_dung_id=user.id, tieu_de="Hỏi về học phí")
            db.add(conv)
            db.flush()
            assert conv.id is not None  # bảng có trigger vẫn lấy được id

            db.add(TinNhan(hoi_thoai_id=conv.id, vai_tro="user", noi_dung="Em nợ bao nhiêu?"))
            log = LuotGoiCongCu(
                hoi_thoai_id=conv.id,
                nguoi_dung_id=user.id,
                mcp_server="tai_chinh",
                ten_cong_cu="get_tuition_status",
                tham_so={"ma_sv": "SV22001"},
                tham_so_llm=None,  # phải lưu NULL thật, không phải chuỗi 'null'
                ket_qua={"trang_thai": "đã nộp"},
                trang_thai="thanh_cong",
            )
            db.add(log)
            db.flush()

            db.expire_all()
            saved = db.get(LuotGoiCongCu, log.id)
            assert saved is not None
            assert saved.tham_so_llm is None
            assert saved.ket_qua == {"trang_thai": "đã nộp"}

            conv = db.get(HoiThoai, conv.id)
            assert conv is not None and conv.tieu_de == "Hỏi về học phí"
            conv.tieu_de = "Đổi tiêu đề"
            db.flush()  # trigger trg_hoi_thoai_updated_at chạy được với UPDATE của ORM
        finally:
            db.rollback()
