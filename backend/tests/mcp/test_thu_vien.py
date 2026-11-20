"""MCP server thu_vien: khai báo title/annotation, gọi qlsv_api (mock bằng respx)."""

import pytest
import respx

from src.mcp_servers import thu_vien
from src.mcp_servers.common import INJECTED_NOTE
from tests.mcp.conftest import call_tool, list_tools

pytestmark = pytest.mark.anyio

BORROW = {
    "muon_id": 1,
    "ma_sach": "TV001",
    "ten_sach": "Nhập môn công nghệ phần mềm",
    "tac_gia": "Nguyễn Văn Hòa",
    "ngay_muon": "2026-11-06",
    "han_tra": "2026-11-27",
    "so_lan_gia_han": 0,
    "qua_han": False,
    "gia_han_duoc": True,
    "ly_do_khong_gia_han": None,
}


async def test_tools_declared() -> None:
    tools = await list_tools(thu_vien.mcp)
    assert set(tools) == {"get_borrowed_books", "search_books", "renew_book"}
    assert tools["get_borrowed_books"].title == "Xem sách đang mượn"
    assert tools["search_books"].title == "Tìm sách thư viện"
    assert tools["renew_book"].title == "Gia hạn sách"
    assert tools["renew_book"].annotations.read_only_hint is False
    assert tools["get_borrowed_books"].annotations.read_only_hint is True
    for t in tools.values():
        assert INJECTED_NOTE in t.input_schema["properties"]["ma_sv"]["description"]


async def test_renew_book_maps_business_error(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.post("/internal/students/SV22001/borrows/2/renew").respond(
        409,
        json={"detail": "Sách đang có người đặt trước.", "code": "CO_NGUOI_DAT_TRUOC"},
    )
    out = await call_tool(thu_vien.mcp, "renew_book", {"ma_sv": "SV22001", "muon_id": 2})
    assert out["ma_loi"] == "CO_NGUOI_DAT_TRUOC"


async def test_renew_book_success(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.post("/internal/students/SV22001/borrows/1/renew").respond(
        200, json={**BORROW, "han_tra": "2026-12-11", "so_lan_gia_han": 1}
    )
    out = await call_tool(thu_vien.mcp, "renew_book", {"ma_sv": "SV22001", "muon_id": 1})
    assert out["thanh_cong"] is True and out["han_tra_moi"] == "2026-12-11"
    assert "11/12/2026" in out["thong_bao"]


async def test_get_borrowed_books_message(qlsv_mock: respx.MockRouter) -> None:
    second = {
        **BORROW,
        "muon_id": 2,
        "ma_sach": "TV002",
        "ten_sach": "Kiểm thử phần mềm thực hành",
        "gia_han_duoc": False,
        "ly_do_khong_gia_han": "Sách đang có người đặt trước nên không gia hạn được.",
    }
    qlsv_mock.get("/internal/students/SV22001/borrows").respond(200, json=[BORROW, second])
    out = await call_tool(thu_vien.mcp, "get_borrowed_books", {"ma_sv": "SV22001"})
    assert len(out["sach"]) == 2
    assert "Nhập môn công nghệ phần mềm" in out["thong_bao"]
    assert "Kiểm thử phần mềm thực hành" in out["thong_bao"]


async def test_search_books(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/internal/books").respond(200, json=[])
    out = await call_tool(thu_vien.mcp, "search_books", {"ma_sv": "SV22001", "tu_khoa": "abc"})
    assert out["sach"] == [] and out["thong_bao"]
    assert route.calls.last.request.url.params["tu_khoa"] == "abc"
