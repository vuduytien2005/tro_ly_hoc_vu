"""Thư viện: sách đang mượn, tìm sách, gia hạn (5 điều kiện theo đúng thứ tự)."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from src.qlsv_api.main import app
from src.qlsv_api.routers.deps import get_now
from src.shared.time import VN_TZ


def renew(client: TestClient, ma_sv: str, muon_id: int):  # type: ignore[no-untyped-def]
    return client.post(f"/internal/students/{ma_sv}/borrows/{muon_id}/renew")


def test_list_borrows_only_active(client: TestClient) -> None:
    r = client.get("/internal/students/SV22001/borrows")
    assert r.status_code == 200
    rows = {b["muon_id"]: b for b in r.json()}
    assert sorted(rows) == [1, 2]  # lượt 5 đã trả -> không hiện
    assert rows[1]["gia_han_duoc"] is True and rows[1]["ly_do_khong_gia_han"] is None
    assert rows[2]["gia_han_duoc"] is False
    assert "đặt trước" in rows[2]["ly_do_khong_gia_han"]
    assert rows[1]["qua_han"] is False


def test_renew_ok(client: TestClient) -> None:
    r = renew(client, "SV22001", 1)
    assert r.status_code == 200, r.text
    assert r.json()["han_tra"] == "2026-12-11" and r.json()["so_lan_gia_han"] == 1
    r = renew(client, "SV22001", 1)
    assert r.json()["han_tra"] == "2026-12-25" and r.json()["so_lan_gia_han"] == 2
    r = renew(client, "SV22001", 1)
    assert (r.status_code, r.json()["code"]) == (409, "HET_LUOT_GIA_HAN")


@pytest.mark.parametrize(
    ("ma_sv", "muon_id", "status", "code"),
    [
        ("SV22002", 1, 404, "KHONG_TIM_THAY_LUOT_MUON"),  # lượt của người khác
        ("SV22001", 99, 404, "KHONG_TIM_THAY_LUOT_MUON"),
        ("SV22001", 5, 409, "DA_TRA_SACH"),
        ("SV22002", 3, 409, "SACH_QUA_HAN"),
        ("SV21001", 4, 409, "HET_LUOT_GIA_HAN"),
        ("SV22001", 2, 409, "CO_NGUOI_DAT_TRUOC"),
    ],
)
def test_renew_errors(client: TestClient, ma_sv: str, muon_id: int, status: int, code: str) -> None:
    r = renew(client, ma_sv, muon_id)
    assert (r.status_code, r.json()["code"]) == (status, code)
    assert r.json()["detail"]


def test_renew_on_due_date_is_allowed(client: TestClient) -> None:
    app.dependency_overrides[get_now] = lambda: datetime(2026, 11, 27, 9, 0, tzinfo=VN_TZ)
    r = renew(client, "SV22001", 1)
    assert r.status_code == 200, r.text
    assert date.fromisoformat(r.json()["han_tra"]) == date(2026, 12, 11)


def test_search_books(client: TestClient) -> None:
    r = client.get("/internal/books", params={"tu_khoa": "phần mềm"})
    assert r.status_code == 200 and len(r.json()) >= 1
    book = r.json()[0]
    assert {"ma_sach", "ten_sach", "tac_gia", "nam_xb", "tong_so_ban", "so_ban_con"} <= set(book)
    assert client.get("/internal/books", params={"tu_khoa": "zzz"}).json() == []
