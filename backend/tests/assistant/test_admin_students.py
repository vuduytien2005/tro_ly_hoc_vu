"""Hồ sơ sinh viên qua trang quản trị (/api/admin/students, AD-10).

qlsv_api THẬT chạy trong tiến trình (httpx.ASGITransport, có middleware X-Internal-Token), dùng
CSDL tlhv_qlsv bọc transaction rồi rollback — như tlhv_assistant ở conftest.py.
"""

from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.assistant_api.agent.llm import FakeLLM
from src.assistant_api.agent.registry import ToolRegistry
from src.assistant_api.deps import get_db
from src.assistant_api.main import create_app
from src.assistant_api.models import NguoiDung
from src.assistant_api.qlsv_directory import QlsvDirectory
from src.qlsv_api.main import app as qlsv_app
from src.shared.db import get_qlsv_engine, get_qlsv_session
from tests.assistant.conftest import PASSWORD, login

NEW: dict[str, Any] = {
    "ma_sv": "SV22099",
    "ho_ten": "Đỗ Minh Khoa",
    "email": "sv22099@truong.example",
    "ngay_sinh": "2004-03-15",
    "gioi_tinh": "nam",
    "ma_nganh": "CNPM",
    "ma_khoa": "K22",
    "lop": "KTPM2022",
}
TEMP_PASSWORD = "TamThoi123"


@pytest.fixture
def qlsv_session() -> Iterator[Session]:
    try:
        connection = get_qlsv_engine().connect()
    except DBAPIError as exc:
        pytest.fail(f"Không kết nối được CSDL tlhv_qlsv: {exc.orig}")
    outer = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    qlsv_app.dependency_overrides[get_qlsv_session] = lambda: session
    try:
        yield session
    finally:
        qlsv_app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def app_client(
    session_factory: Callable[[], Session],
    registry: ToolRegistry,
    fake_llm: FakeLLM,
    db: Session,
    qlsv_session: Session,
) -> Iterator[TestClient]:
    directory = QlsvDirectory(
        base_url="http://qlsv.test", transport=httpx.ASGITransport(app=qlsv_app)
    )
    app = create_app(
        registry=registry, llm=fake_llm, session_factory=session_factory, qlsv_directory=directory
    )

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session
            if session.in_transaction():
                session.commit()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c


def test_student_role_forbidden(app_client: TestClient, student: NguoiDung) -> None:
    r = app_client.get("/api/admin/students", headers=login(app_client, student.email))
    assert r.status_code == 403


def test_list_shows_linked_accounts(
    app_client: TestClient, admin: NguoiDung, student: NguoiDung
) -> None:
    r = app_client.get("/api/admin/students", headers=login(app_client, admin.email))
    assert r.status_code == 200, r.text
    rows = {s["ma_sv"]: s for s in r.json()["sinh_vien"]}
    assert r.json()["tong"] >= 5  # 5 SV của 03_qlsv_seed.sql (+ 9 SV nếu đã chạy 11)
    assert rows["SV22001"]["tai_khoan"] == {"id": student.id, "dang_hoat_dong": True}

    programs = app_client.get(
        "/api/admin/students/programs", headers=login(app_client, admin.email)
    ).json()
    assert {p["ma_khoa"] for p in programs} >= {"K21", "K22", "K23"}


def test_create_student_with_account(app_client: TestClient, admin: NguoiDung) -> None:
    r = app_client.post(
        "/api/admin/students",
        json={**NEW, "cap_tai_khoan": True, "mat_khau": TEMP_PASSWORD},
        headers=login(app_client, admin.email),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sinh_vien"]["khoa"] == "K22"
    assert body["tai_khoan"]["ma_sv"] == "SV22099"
    assert body["sinh_vien"]["tai_khoan"]["id"] == body["tai_khoan"]["id"]
    assert body["canh_bao"] is None

    # Sinh viên mới đăng nhập được, ma_khoa lấy từ QLSV
    me = app_client.get(
        "/api/auth/me", headers=login(app_client, NEW["email"], TEMP_PASSWORD)
    ).json()
    assert (me["ma_sv"], me["ma_khoa"]) == ("SV22099", "K22")


def test_create_student_only_then_grant_account(app_client: TestClient, admin: NguoiDung) -> None:
    headers = login(app_client, admin.email)
    r = app_client.post("/api/admin/students", json=NEW, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["tai_khoan"] is None

    # Cấp sau bằng API tài khoản (AD-09): giờ mã SV đã có trong QLSV
    r = app_client.post(
        "/api/admin/users", json={"ma_sv": "SV22099", "mat_khau": TEMP_PASSWORD}, headers=headers
    )
    assert r.status_code == 201, r.text


def test_create_checks_password_before_writing_qlsv(
    app_client: TestClient, admin: NguoiDung
) -> None:
    headers = login(app_client, admin.email)
    r = app_client.post(
        "/api/admin/students",
        json={**NEW, "cap_tai_khoan": True, "mat_khau": "yeu"},
        headers=headers,
    )
    assert r.json()["code"] == "MAT_KHAU_YEU"
    # Hồ sơ KHÔNG được thêm (kiểm tra trước khi ghi QLSV)
    found = app_client.get("/api/admin/students", params={"q": "SV22099"}, headers=headers)
    assert found.json()["tong"] == 0


def test_create_passes_qlsv_errors_through(app_client: TestClient, admin: NguoiDung) -> None:
    headers = login(app_client, admin.email)
    r = app_client.post("/api/admin/students", json={**NEW, "ma_sv": "SV22001"}, headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "SV_DA_TON_TAI"
    r = app_client.post("/api/admin/students", json={**NEW, "ma_khoa": "K30"}, headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == "KHOA_HOC_KHONG_TON_TAI"


def test_update_syncs_linked_account(
    app_client: TestClient, admin: NguoiDung, student: NguoiDung
) -> None:
    headers = login(app_client, admin.email)
    r = app_client.patch(
        "/api/admin/students/SV22001",
        json={"ho_ten": "Nguyễn Văn An Mới", "ma_khoa": "K23", "email": "an.moi@truong.example"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["khoa"] == "K23"

    # Tài khoản trợ lý đồng bộ: đăng nhập bằng email mới, ma_khoa mới (lọc quy chế K23)
    me = app_client.get(
        "/api/auth/me", headers=login(app_client, "an.moi@truong.example", PASSWORD)
    ).json()
    assert (me["ho_ten"], me["ma_khoa"]) == ("Nguyễn Văn An Mới", "K23")


def test_update_status(app_client: TestClient, admin: NguoiDung) -> None:
    r = app_client.patch(
        "/api/admin/students/SV22002",
        json={"trang_thai": "bao_luu"},
        headers=login(app_client, admin.email),
    )
    assert r.status_code == 200
    assert r.json()["trang_thai"] == "bao_luu"


def test_update_rejects_email_of_other_account(
    app_client: TestClient, admin: NguoiDung, student: NguoiDung
) -> None:
    headers = login(app_client, admin.email)
    # Email của tài khoản quản trị (không có trong QLSV) -> chặn ở phía trợ lý, QLSV không bị sửa
    r = app_client.patch(
        "/api/admin/students/SV22001", json={"email": admin.email}, headers=headers
    )
    assert r.status_code == 409
    assert r.json()["code"] == "EMAIL_DA_TON_TAI"
    found = app_client.get("/api/admin/students", params={"q": "SV22001"}, headers=headers)
    assert found.json()["sinh_vien"][0]["email"] != admin.email

    r = app_client.patch("/api/admin/students/SV22001", json={}, headers=headers)
    assert r.status_code == 422
    r = app_client.patch("/api/admin/students/SV99999", json={"lop": "X"}, headers=headers)
    assert r.status_code == 404


def test_attention_list_for_admin_only(
    app_client: TestClient, admin: NguoiDung, student: NguoiDung
) -> None:
    r = app_client.get("/api/admin/students/attention", headers=login(app_client, student.email))
    assert r.status_code == 403
    r = app_client.get("/api/admin/students/attention", headers=login(app_client, admin.email))
    assert r.status_code == 200, r.text
    rows = {s["ma_sv"]: s for s in r.json()["sinh_vien"]}
    # 03_qlsv_seed.sql: SV22002 nợ học phí HK1 2026-2027, hạn 15/10/2026
    assert any(x["loai"] == "no_hoc_phi" for x in rows["SV22002"]["ly_do"])
