"""Quản lý tài khoản (/api/admin/users, AD-09). qlsv_api giả lập bằng respx (fixture qlsv_mock)."""

import httpx
import respx
from fastapi.testclient import TestClient

from src.assistant_api.models import NguoiDung
from src.shared.config import get_settings
from src.shared.security import INTERNAL_TOKEN_HEADER
from tests.assistant.conftest import PASSWORD, login

NEW_SV = "SV99001"
NEW_EMAIL = "sv99001@tlhv.test"
NEW_PASSWORD = "TamThoi123"
PROFILE = {
    "ma_sv": NEW_SV,
    "ho_ten": "Trần Thị Thử",
    "email": NEW_EMAIL,
    "ngay_sinh": "2004-05-06",
    "gioi_tinh": "Nữ",
    "lop": "KTPM2022",
    "ma_nganh": "7480103",
    "nganh": "Kỹ thuật phần mềm",
    "khoa": "K22",
    "trang_thai": "dang_hoc",
}


def _mock_profile(
    qlsv_mock: respx.MockRouter, profile: dict[str, str] | None = None
) -> respx.Route:
    return qlsv_mock.get(f"/internal/students/{NEW_SV}").respond(200, json=profile or PROFILE)


def test_student_cannot_manage_accounts(client: TestClient, student: NguoiDung) -> None:
    headers = login(client, student.email)
    r = client.get("/api/admin/users", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "KHONG_DU_QUYEN"
    r = client.post(
        "/api/admin/users", json={"ma_sv": NEW_SV, "mat_khau": NEW_PASSWORD}, headers=headers
    )
    assert r.status_code == 403


def test_create_student_account_from_qlsv(
    client: TestClient, admin: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    route = _mock_profile(qlsv_mock)
    headers = login(client, admin.email)

    r = client.post(
        "/api/admin/users", json={"ma_sv": " sv99001 ", "mat_khau": NEW_PASSWORD}, headers=headers
    )

    assert r.status_code == 201, r.text
    body = r.json()
    # Họ tên, email, khóa lấy từ QLSV, không do quản trị viên nhập
    assert body["ma_sv"] == NEW_SV
    assert body["ho_ten"] == "Trần Thị Thử"
    assert body["email"] == NEW_EMAIL
    assert body["ma_khoa"] == "K22"
    assert body["vai_tro"] == "sinh_vien"
    assert body["dang_hoat_dong"] is True
    assert body["created_at"].endswith("+07:00")
    assert (
        route.calls.last.request.headers[INTERNAL_TOKEN_HEADER] == get_settings().internal_api_token
    )

    # Sinh viên đăng nhập được ngay bằng mật khẩu tạm
    me = client.get("/api/auth/me", headers=login(client, NEW_EMAIL, NEW_PASSWORD)).json()
    assert me["ma_sv"] == NEW_SV


def test_create_rejects_existing_student_without_calling_qlsv(
    client: TestClient, admin: NguoiDung, student: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    route = qlsv_mock.get("/internal/students/SV22001").respond(200, json=PROFILE)
    r = client.post(
        "/api/admin/users",
        json={"ma_sv": "SV22001", "mat_khau": NEW_PASSWORD},
        headers=login(client, admin.email),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "TAI_KHOAN_DA_TON_TAI"
    assert not route.called


def test_create_rejects_email_already_used(
    client: TestClient, admin: NguoiDung, student: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    _mock_profile(qlsv_mock, {**PROFILE, "email": student.email.upper()})
    r = client.post(
        "/api/admin/users",
        json={"ma_sv": NEW_SV, "mat_khau": NEW_PASSWORD},
        headers=login(client, admin.email),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "EMAIL_DA_TON_TAI"


def test_create_unknown_student(
    client: TestClient, admin: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    qlsv_mock.get(f"/internal/students/{NEW_SV}").respond(
        404, json={"detail": "Không tìm thấy", "code": "SV_KHONG_TON_TAI"}
    )
    r = client.post(
        "/api/admin/users",
        json={"ma_sv": NEW_SV, "mat_khau": NEW_PASSWORD},
        headers=login(client, admin.email),
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SV_KHONG_TON_TAI"


def test_create_when_qlsv_down(
    client: TestClient, admin: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    qlsv_mock.get(f"/internal/students/{NEW_SV}").mock(side_effect=httpx.ConnectError("down"))
    r = client.post(
        "/api/admin/users",
        json={"ma_sv": NEW_SV, "mat_khau": NEW_PASSWORD},
        headers=login(client, admin.email),
    )
    assert r.status_code == 503
    assert r.json()["code"] == "QLSV_KHONG_KET_NOI"


def test_weak_password_rejected(
    client: TestClient, admin: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    route = _mock_profile(qlsv_mock)
    headers = login(client, admin.email)
    for weak in ("Ab1", "chikhongcoso", "12345678", "a1" + "ệ" * 30):  # cuối: > 72 byte
        r = client.post(
            "/api/admin/users", json={"ma_sv": NEW_SV, "mat_khau": weak}, headers=headers
        )
        assert r.status_code == 422, weak
        assert r.json()["code"] == "MAT_KHAU_YEU"
    assert not route.called


def test_list_and_filter_accounts(
    client: TestClient, admin: NguoiDung, student: NguoiDung, other_student: NguoiDung
) -> None:
    headers = login(client, admin.email)

    r = client.get("/api/admin/users", params={"tu_khoa": "sv22001"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [u["ma_sv"] for u in body["nguoi_dung"]] == ["SV22001"]
    assert body["tong"] == 1
    assert "mat_khau_hash" not in body["nguoi_dung"][0]

    admins = client.get("/api/admin/users", params={"vai_tro": "admin"}, headers=headers).json()
    assert admins["nguoi_dung"] and all(u["vai_tro"] == "admin" for u in admins["nguoi_dung"])

    page = client.get("/api/admin/users", params={"page_size": 1}, headers=headers).json()
    assert len(page["nguoi_dung"]) == 1 and page["tong"] >= 3


def test_lock_takes_effect_immediately(
    client: TestClient, admin: NguoiDung, student: NguoiDung
) -> None:
    admin_headers = login(client, admin.email)
    student_headers = login(client, student.email)

    r = client.patch(
        f"/api/admin/users/{student.id}", json={"dang_hoat_dong": False}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["dang_hoat_dong"] is False

    # Token cũ bị từ chối ngay, đăng nhập lại cũng không được
    r = client.get("/api/auth/me", headers=student_headers)
    assert r.status_code == 403
    assert r.json()["code"] == "TAI_KHOAN_BI_KHOA"
    r = client.post("/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD})
    assert r.status_code == 403

    client.patch(
        f"/api/admin/users/{student.id}", json={"dang_hoat_dong": True}, headers=admin_headers
    )
    assert client.get("/api/auth/me", headers=student_headers).status_code == 200


def test_admin_cannot_lock_self(client: TestClient, admin: NguoiDung) -> None:
    r = client.patch(
        f"/api/admin/users/{admin.id}",
        json={"dang_hoat_dong": False},
        headers=login(client, admin.email),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "KHONG_THE_KHOA_CHINH_MINH"


def test_reset_password(client: TestClient, admin: NguoiDung, student: NguoiDung) -> None:
    headers = login(client, admin.email)
    r = client.post(
        f"/api/admin/users/{student.id}/reset-password",
        json={"mat_khau": NEW_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 204

    old = client.post("/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD})
    assert old.status_code == 401
    login(client, student.email, NEW_PASSWORD)

    r = client.post(
        f"/api/admin/users/{student.id}/reset-password", json={"mat_khau": "yeu"}, headers=headers
    )
    assert r.json()["code"] == "MAT_KHAU_YEU"


def test_unknown_account(client: TestClient, admin: NguoiDung) -> None:
    headers = login(client, admin.email)
    r = client.patch("/api/admin/users/999999999", json={"dang_hoat_dong": False}, headers=headers)
    assert r.status_code == 404
    assert r.json()["code"] == "TAI_KHOAN_KHONG_TON_TAI"
    r = client.post(
        "/api/admin/users/999999999/reset-password",
        json={"mat_khau": NEW_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 404
