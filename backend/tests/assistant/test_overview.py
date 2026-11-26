"""Trang "Học tập của em": API /api/my/overview gọi thẳng các tool đọc (không qua LLM)."""

import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.models import CongCu, LuotGoiCongCu, NguoiDung
from tests.assistant.conftest import login

PROFILE = {
    "ma_sv": "SV22001",
    "ho_ten": "Nguyễn Văn An",
    "email": "sv22001@truong.example",
    "ngay_sinh": "2004-01-01",
    "gioi_tinh": "nam",
    "lop": "22CNPM1",
    "ma_nganh": "CNPM",
    "nganh": "Công nghệ phần mềm",
    "khoa": "K22",
    "trang_thai": "dang_hoc",
}
TRANSCRIPT = {
    "ma_sv": "SV22001",
    "ma_hoc_ky": None,
    "ket_qua": [
        {
            "ma_hp": "IT004",
            "ten_hp": "Cơ sở dữ liệu",
            "tin_chi": 3,
            "hoc_ky": "2025-2026-HK1",
            "diem_qua_trinh": 3.0,
            "diem_thi": 3.0,
            "diem_tong_ket": 3.0,
            "diem_chu": "F",
            "diem_he_4": 0.0,
            "lan_hoc": 1,
            "dat": False,
        }
    ],
    "gpa_tich_luy": 2.5,
    "tin_chi_tich_luy": 20,
    "canh_bao_hoc_vu": False,
}
TUITION = {
    "ma_sv": "SV22001",
    "ma_hoc_ky": "2026-2027-HK1",
    "phai_nop": 9_000_000,
    "da_nop": 4_000_000,
    "con_no": 5_000_000,
    "han_nop": "2026-11-28",
    "trang_thai": "nop_mot_phan",
}


def test_overview_collects_sections_for_logged_in_student(
    client: TestClient, student: NguoiDung, db: Session, qlsv_mock: respx.MockRouter
) -> None:
    qlsv_mock.get("/internal/students/SV22001").respond(200, json=PROFILE)
    qlsv_mock.get("/internal/students/SV22001/transcript").respond(200, json=TRANSCRIPT)
    qlsv_mock.get("/internal/students/SV22001/tuition").respond(200, json=TUITION)
    qlsv_mock.get("/internal/students/SV22001/schedule").respond(
        500, json={"detail": "lỗi", "code": "LOI"}
    )
    r = client.get("/api/my/overview", headers=login(client, student.email))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ho_so"]["lop"] == "22CNPM1"
    assert body["bang_diem"]["gpa_tich_luy"] == 2.5
    assert body["bang_diem"]["ket_qua"][0]["diem_chu"] == "F"
    assert body["hoc_phi"]["con_no"] == 5_000_000
    assert body["thoi_khoa_bieu"] is None
    assert "get_current_schedule" in body["nguon_loi"]
    db.expire_all()
    log = db.scalar(
        select(LuotGoiCongCu)
        .where(LuotGoiCongCu.ten_cong_cu == "get_transcript")
        .order_by(LuotGoiCongCu.id.desc())
    )
    # Quy tắc 1 + 3: ma_sv lấy từ tài khoản đăng nhập, lần gọi có nhật ký
    assert log.hoi_thoai_id is None and log.tham_so == {"ma_sv": "SV22001"}
    assert "Học tập của em" in (log.ly_do or "")


def test_overview_ignores_student_supplied_ma_sv(
    client: TestClient, student: NguoiDung, qlsv_mock: respx.MockRouter
) -> None:
    other = qlsv_mock.get("/internal/students/SV22002/transcript").respond(200, json=TRANSCRIPT)
    qlsv_mock.get("/internal/students/SV22001/transcript").respond(200, json=TRANSCRIPT)
    r = client.get("/api/my/overview?ma_sv=SV22002", headers=login(client, student.email))
    assert r.status_code == 200
    assert not other.called


def test_overview_skips_disabled_tool_without_calling(
    client: TestClient, student: NguoiDung, db: Session, qlsv_mock: respx.MockRouter
) -> None:
    db.execute(update(CongCu).where(CongCu.ten == "get_tuition_status").values(bat=False))
    db.commit()
    tuition_route = qlsv_mock.get("/internal/students/SV22001/tuition").respond(200, json=TUITION)
    r = client.get("/api/my/overview", headers=login(client, student.email))
    assert r.status_code == 200
    body = r.json()
    assert body["hoc_phi"] is None and "get_tuition_status" not in body["nguon_loi"]
    assert "get_tuition_status" in body["tam_dung"]
    assert not tuition_route.called  # quy tắc 6


def test_overview_requires_student(client: TestClient) -> None:
    assert client.get("/api/my/overview").status_code == 401
