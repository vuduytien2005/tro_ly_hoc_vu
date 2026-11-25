"""Duyệt đơn qua trang quản trị (/api/admin/requests) — qlsv_api thật chạy trong tiến trình."""

from fastapi.testclient import TestClient

from src.assistant_api.models import NguoiDung
from tests.assistant.conftest import login
from tests.assistant.test_admin_students import app_client, qlsv_session  # noqa: F401  (fixture)


def _new_request(
    c: TestClient,
    student: NguoiDung,
    loai_don: str = "giay_xac_nhan_sv",
    noi_dung: dict[str, str] | None = None,
) -> str:
    # Tạo đơn như sinh viên nộp: đi thẳng qlsv_api trong tiến trình (không phải phần đang kiểm thử)
    from fastapi.testclient import TestClient as Raw

    from src.qlsv_api.main import app as qlsv_app
    from src.shared.config import get_settings
    from src.shared.security import INTERNAL_TOKEN_HEADER

    raw = Raw(qlsv_app, headers={INTERNAL_TOKEN_HEADER: get_settings().internal_api_token})
    r = raw.post(
        f"/internal/students/{student.ma_sv}/requests",
        json={"loai_don": loai_don, "noi_dung": noi_dung or {"muc_dich": "Làm thẻ xe"}},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["ma_don"])


def test_student_cannot_review(app_client: TestClient, student: NguoiDung) -> None:  # noqa: F811
    headers = login(app_client, student.email)
    assert app_client.get("/api/admin/requests", headers=headers).status_code == 403
    r = app_client.patch(
        "/api/admin/requests/DT-2026-0001", json={"trang_thai": "da_duyet"}, headers=headers
    )
    assert r.status_code == 403


def test_admin_lists_and_reviews(
    app_client: TestClient,  # noqa: F811
    admin: NguoiDung,
    student: NguoiDung,
) -> None:
    ma_don = _new_request(app_client, student)
    headers = login(app_client, admin.email)
    page = app_client.get("/api/admin/requests?trang_thai=moi_tao", headers=headers)
    assert page.status_code == 200, page.text
    assert [d["ma_don"] for d in page.json()["don"]] == [ma_don]
    assert page.json()["don"][0]["ma_sv"] == student.ma_sv

    r = app_client.patch(
        f"/api/admin/requests/{ma_don}",
        json={"trang_thai": "tu_choi", "ghi_chu_xu_ly": ""},
        headers=headers,
    )
    assert (r.status_code, r.json()["code"]) == (422, "CAN_LY_DO_TU_CHOI")

    r = app_client.patch(
        f"/api/admin/requests/{ma_don}",
        json={"trang_thai": "da_duyet", "ghi_chu_xu_ly": "Nhận tại phòng CTSV"},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["trang_thai"] == "da_duyet"
    assert r.json()["ghi_chu_xu_ly"] == "Nhận tại phòng CTSV"

    r = app_client.patch(
        f"/api/admin/requests/{ma_don}", json={"trang_thai": "moi_tao"}, headers=headers
    )
    assert (r.status_code, r.json()["code"]) == (409, "CHUYEN_TRANG_THAI_KHONG_HOP_LE")


def test_bad_filter_is_422(app_client: TestClient, admin: NguoiDung) -> None:  # noqa: F811
    r = app_client.get("/api/admin/requests?loai_don=xyz", headers=login(app_client, admin.email))
    assert r.status_code == 422


def test_admin_filters_and_answers_question(
    app_client: TestClient,  # noqa: F811
    admin: NguoiDung,
    student: NguoiDung,
) -> None:
    ma_don = _new_request(
        app_client, student, "hoi_dap", {"cau_hoi": "Học bổng xét theo học kỳ nào ạ?"}
    )
    headers = login(app_client, admin.email)
    page = app_client.get("/api/admin/requests?loai_don=hoi_dap", headers=headers)
    assert page.status_code == 200, page.text
    assert [d["ma_don"] for d in page.json()["don"]] == [ma_don]

    r = app_client.patch(
        f"/api/admin/requests/{ma_don}", json={"trang_thai": "hoan_tat"}, headers=headers
    )
    assert (r.status_code, r.json()["code"]) == (422, "CAN_NOI_DUNG_TRA_LOI")
    r = app_client.patch(
        f"/api/admin/requests/{ma_don}",
        json={"trang_thai": "hoan_tat", "ghi_chu_xu_ly": "Theo học kỳ liền trước."},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["trang_thai"] == "hoan_tat"
