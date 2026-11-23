"""Nhắc việc: hàm thuần build_reminders (không chạm CSDL) và API /api/my/reminders."""

from datetime import date
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.models import CongCu, LuotGoiCongCu, NguoiDung
from src.assistant_api.reminders import build_reminders
from tests.assistant.conftest import login

TODAY = date(2026, 11, 23)


def tuition(con_no: int, han_nop: str) -> dict[str, Any]:
    return {"hoc_ky": "2026-2027-HK1", "con_no": con_no, "han_nop": han_nop}


def exam(ngay: str, ten: str = "Cấu trúc dữ liệu") -> dict[str, Any]:
    return {
        "ma_lop": "IT003.01",
        "ten_hp": ten,
        "ngay_thi": ngay,
        "gio": "07:30",
        "phong": "B2.101",
    }


def book(han_tra: str, qua_han: bool = False, gia_han_duoc: bool = True) -> dict[str, Any]:
    return {
        "muon_id": 7,
        "ten_sach": "Nhập môn CSDL",
        "han_tra": han_tra,
        "qua_han": qua_han,
        "gia_han_duoc": gia_han_duoc,
    }


def test_nothing_to_remind() -> None:
    assert build_reminders(tuition(0, "2026-11-25"), {"lich_thi": []}, {"sach": []}, TODAY) == []


def test_tuition_due_soon_is_urgent() -> None:
    [r] = build_reminders(tuition(5_000_000, "2026-11-28"), None, None, TODAY)
    assert r["loai"] == "hoc_phi" and r["muc_do"] == "khan" and r["con_ngay"] == 5
    assert "5.000.000" in r["chi_tiet"] and "28/11/2026" in r["chi_tiet"]
    assert r["cau_hoi"]


def test_tuition_far_or_paid_is_skipped() -> None:
    assert build_reminders(tuition(5_000_000, "2027-02-01"), None, None, TODAY) == []
    assert build_reminders(tuition(0, "2026-11-24"), None, None, TODAY) == []


def test_tuition_within_month_is_upcoming_and_overdue_is_urgent() -> None:
    [r] = build_reminders(tuition(1_000, "2026-12-15"), None, None, TODAY)
    assert r["muc_do"] == "sap_toi"
    [r] = build_reminders(tuition(1_000, "2026-11-01"), None, None, TODAY)
    assert r["muc_do"] == "khan" and r["con_ngay"] == -22 and "quá hạn" in r["tieu_de"]


def test_exams_within_two_weeks() -> None:
    exams = {
        "lich_thi": [
            exam("2026-11-20", "Đã thi"),
            exam("2026-11-25", "Thi gần"),
            exam("2026-12-05", "Thi xa vừa"),
            exam("2026-12-20", "Thi quá xa"),
        ]
    }
    rs = build_reminders(None, exams, None, TODAY)
    assert [r["muc_do"] for r in rs] == ["khan", "sap_toi"]
    assert "Thi gần" in rs[0]["tieu_de"] and "B2.101" in rs[0]["chi_tiet"]


def test_books_overdue_and_due_soon() -> None:
    borrows = {
        "sach": [
            book("2026-11-20", qua_han=True),
            book("2026-11-28"),
            book("2026-12-30"),
        ]
    }
    rs = build_reminders(None, None, borrows, TODAY)
    assert [(r["muc_do"], r["con_ngay"]) for r in rs] == [("khan", -3), ("sap_toi", 5)]
    assert "Gia hạn" in rs[1]["cau_hoi"]


def test_book_that_cannot_be_renewed_asks_differently() -> None:
    [r] = build_reminders(None, None, {"sach": [book("2026-11-24", gia_han_duoc=False)]}, TODAY)
    assert "Gia hạn" not in r["cau_hoi"]


def test_sorted_urgent_first_then_by_deadline() -> None:
    rs = build_reminders(
        tuition(1_000, "2026-12-10"),
        {"lich_thi": [exam("2026-11-26")]},
        {"sach": [book("2026-11-24")]},
        TODAY,
    )
    assert [r["loai"] for r in rs] == ["sach", "lich_thi", "hoc_phi"]


@pytest.mark.parametrize("bad", [{"lich_thi": [{"ngay_thi": "khong-phai-ngay"}]}, {"x": 1}])
def test_malformed_source_is_ignored(bad: dict[str, Any]) -> None:
    assert build_reminders(None, bad, None, TODAY) == []


# ---------------------------------------------------------------- API ----
@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime

    from src.assistant_api.routers import my_requests
    from src.shared.time import VN_TZ

    monkeypatch.setattr(my_requests, "now", lambda: datetime(2026, 11, 23, 9, tzinfo=VN_TZ))


def test_reminders_api_uses_logged_in_student_and_logs(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    qlsv_mock: respx.MockRouter,
    fixed_today: None,
) -> None:
    qlsv_mock.get("/internal/students/SV22001/tuition").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ma_hoc_ky": "2026-2027-HK1",
            "phai_nop": 9_000_000,
            "da_nop": 4_000_000,
            "con_no": 5_000_000,
            "han_nop": "2026-11-28",
            "trang_thai": "nop_mot_phan",
        },
    )
    qlsv_mock.get("/internal/students/SV22001/exam-schedule").respond(
        500, json={"detail": "lỗi", "code": "LOI"}
    )
    r = client.get("/api/my/reminders", headers=login(client, student.email))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ngay"] == "2026-11-23"
    assert [x["loai"] for x in body["nhac_viec"]] == ["hoc_phi"]
    assert "get_exam_schedule" in body["nguon_loi"]
    db.expire_all()
    log = db.scalar(
        select(LuotGoiCongCu)
        .where(LuotGoiCongCu.ten_cong_cu == "get_tuition_status")
        .order_by(LuotGoiCongCu.id.desc())
    )
    assert log.hoi_thoai_id is None and log.tham_so == {"ma_sv": "SV22001"}
    assert "Nhắc việc" in (log.ly_do or "")


def test_reminders_skip_disabled_tool_without_calling(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    qlsv_mock: respx.MockRouter,
    fixed_today: None,
) -> None:
    db.execute(update(CongCu).where(CongCu.ten == "get_tuition_status").values(bat=False))
    db.commit()
    tuition_route = qlsv_mock.get("/internal/students/SV22001/tuition").respond(200, json={})
    qlsv_mock.get("/internal/students/SV22001/exam-schedule").respond(
        200, json={"ma_sv": "SV22001", "ma_hoc_ky": "2026-2027-HK1", "lich_thi": []}
    )
    qlsv_mock.get("/internal/students/SV22001/requests").respond(200, json=[])
    r = client.get("/api/my/reminders", headers=login(client, student.email))
    assert r.status_code == 200
    assert r.json()["nhac_viec"] == [] and r.json()["nguon_loi"] == []
    assert not tuition_route.called  # quy tắc 6: công cụ tắt thì không gọi


def test_reminders_require_student(client: TestClient) -> None:
    assert client.get("/api/my/reminders").status_code == 401


# ----- Đơn vừa được xử lý (bổ sung 23/11/2026) -------------------------------------------------
def req(ma_trang_thai: str, ngay_cap_nhat: str, ma_don: str = "DT-2026-0007") -> dict[str, Any]:
    return {
        "ma_don": ma_don,
        "loai_don": "Đơn bảo lưu",
        "ma_trang_thai": ma_trang_thai,
        "ngay_tao": "2026-11-01",
        "ngay_cap_nhat": ngay_cap_nhat,
    }


def test_recently_processed_requests_are_reminded() -> None:
    data = {
        "don": [
            req("da_duyet", "2026-11-22", "DT-1"),
            req("tu_choi", "2026-11-20", "DT-2"),
            req("hoan_tat", "2026-11-23", "DT-3"),
            req("dang_xu_ly", "2026-11-23", "DT-4"),  # chưa xử lý xong: không báo
            req("moi_tao", "2026-11-23", "DT-5"),
            req("da_duyet", "2026-11-10", "DT-6"),  # quá 7 ngày: không báo nữa
        ]
    }
    items = build_reminders(None, None, None, TODAY, data)
    assert [(r["loai"], r["muc_do"], r["con_ngay"]) for r in items] == [
        ("don", "khan", -3),  # bị từ chối -> khẩn (cần làm lại)
        ("don", "sap_toi", -1),
        ("don", "sap_toi", 0),
    ]
    rejected = items[0]
    assert rejected["tieu_de"] == "Đơn bảo lưu bị từ chối"
    assert "DT-2" in rejected["chi_tiet"] and "3 ngày trước" in rejected["chi_tiet"]
    assert "bị từ chối" in rejected["cau_hoi"]
    assert items[2]["chi_tiet"].startswith("Mã đơn DT-3, cập nhật hôm nay")


def test_request_without_update_date_uses_creation_date() -> None:
    old_api = {"don": [{**req("da_duyet", ""), "ngay_cap_nhat": None, "ngay_tao": "2026-11-21"}]}
    assert [r["han"] for r in build_reminders(None, None, None, TODAY, old_api)] == ["2026-11-21"]


def test_reminders_api_includes_processed_request(
    client: TestClient,
    student: NguoiDung,
    qlsv_mock: respx.MockRouter,
    fixed_today: None,
) -> None:
    qlsv_mock.get("/internal/students/SV22001/tuition").respond(
        200, json={"ma_sv": "SV22001", "con_no": 0, "han_nop": "2026-11-28"}
    )
    qlsv_mock.get("/internal/students/SV22001/exam-schedule").respond(
        200, json={"ma_sv": "SV22001", "ma_hoc_ky": "2026-2027-HK1", "lich_thi": []}
    )
    route = qlsv_mock.get("/internal/students/SV22001/requests").respond(
        200,
        json=[
            {
                "ma_don": "DT-2026-0009",
                "loai_don": "phuc_khao",
                "trang_thai": "da_duyet",
                "tao_boi": "tro_ly_ai",
                "created_at": "2026-11-15T08:00:00+07:00",
                "updated_at": "2026-11-22T14:30:00+07:00",
            }
        ],
    )
    r = client.get("/api/my/reminders", headers=login(client, student.email))
    assert r.status_code == 200, r.text
    assert route.called
    [item] = [x for x in r.json()["nhac_viec"] if x["loai"] == "don"]
    assert item["tieu_de"] == "Đơn phúc khảo đã được duyệt"
    assert item["han"] == "2026-11-22"
