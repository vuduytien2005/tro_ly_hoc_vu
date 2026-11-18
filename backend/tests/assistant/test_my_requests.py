"""/api/my/requests: gọi tool trực tiếp, vẫn tiêm ma_sv, kiểm tra tool bật, ghi nhật ký."""

import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.models import CongCu, LuotGoiCongCu, NguoiDung
from tests.assistant.conftest import login

SUMMARY = {
    "ma_don": "DT-2026-0001",
    "loai_don": "giay_xac_nhan_sv",
    "trang_thai": "moi_tao",
    "created_at": "2026-11-19T10:00:00+07:00",
}


def test_list_requests_uses_logged_in_student(
    client: TestClient, student: NguoiDung, db: Session, qlsv_mock: respx.MockRouter
) -> None:
    route = qlsv_mock.get("/internal/students/SV22001/requests").respond(200, json=[SUMMARY])
    r = client.get("/api/my/requests", headers=login(client, student.email))
    assert r.status_code == 200
    assert r.json()["don"][0]["ma_don"] == "DT-2026-0001"
    assert route.called
    db.expire_all()
    log = db.scalar(
        select(LuotGoiCongCu)
        .where(LuotGoiCongCu.ten_cong_cu == "list_my_requests")
        .order_by(LuotGoiCongCu.id.desc())
    )
    assert log.hoi_thoai_id is None and log.tham_so == {"ma_sv": "SV22001"}
    assert log.trang_thai == "thanh_cong"


def test_filter_validated(client: TestClient, student: NguoiDung) -> None:
    r = client.get("/api/my/requests?trang_thai=xoa_het", headers=login(client, student.email))
    assert r.status_code == 422


def test_request_detail_not_found(
    client: TestClient, student: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    qlsv_mock.get("/internal/students/SV22001/requests/DT-2026-9999").respond(
        404, json={"detail": "Không tìm thấy đơn.", "code": "DON_KHONG_TON_TAI"}
    )
    r = client.get("/api/my/requests/DT-2026-9999", headers=login(client, student.email))
    assert r.status_code == 404 and r.json()["code"] == "DON_KHONG_TON_TAI"


def test_disabled_tool_returns_503(client: TestClient, student: NguoiDung, db: Session) -> None:
    db.execute(update(CongCu).where(CongCu.ten == "list_my_requests").values(bat=False))
    db.commit()
    r = client.get("/api/my/requests", headers=login(client, student.email))
    assert r.status_code == 503 and r.json()["code"] == "CHUC_NANG_TAM_DUNG"
