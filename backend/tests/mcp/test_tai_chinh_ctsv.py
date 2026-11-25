"""MCP server tai_chinh và ctsv (phần đọc), qlsv_api mock bằng respx."""

import pytest
import respx

from src.mcp_servers import ctsv, tai_chinh
from src.mcp_servers.common import INJECTED_NOTE
from tests.mcp.conftest import call_tool, list_tools

pytestmark = pytest.mark.anyio


# --- tai_chinh ------------------------------------------------------------
async def test_tai_chinh_tools() -> None:
    tools = await list_tools(tai_chinh.mcp)
    assert set(tools) == {"get_tuition_status"}
    props = tools["get_tuition_status"].input_schema["properties"]
    assert INJECTED_NOTE in props["ma_sv"]["description"]


async def test_tuition_with_debt(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22002/tuition").respond(
        200,
        json={
            "ma_sv": "SV22002",
            "ma_hoc_ky": "2026-2027-HK1",
            "phai_nop": 12500000,
            "da_nop": 5000000,
            "con_no": 7500000,
            "han_nop": "2026-12-15",
            "trang_thai": "nop_mot_phan",
        },
    )
    out = await call_tool(tai_chinh.mcp, "get_tuition_status", {"ma_sv": "SV22002"})
    assert out["con_no"] == 7500000
    assert out["thong_bao"] == (
        "Học kỳ 2026-2027-HK1: phải nộp 12.500.000 đồng, đã nộp 5.000.000 đồng "
        "(mới nộp một phần). Còn nợ 7.500.000 đồng, hạn nộp 2026-12-15."
    )


async def test_tuition_paid(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/tuition").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ma_hoc_ky": "2026-2027-HK1",
            "phai_nop": 10000000,
            "da_nop": 10000000,
            "con_no": 0,
            "han_nop": "2026-12-15",
            "trang_thai": "da_nop",
        },
    )
    out = await call_tool(tai_chinh.mcp, "get_tuition_status", {"ma_sv": "SV22001"})
    assert "Còn nợ" not in out["thong_bao"]
    assert "(đã nộp đủ)" in out["thong_bao"]


async def test_tuition_not_found(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/tuition").respond(
        404, json={"detail": "Chưa có thông tin học phí.", "code": "HOC_PHI_KHONG_TON_TAI"}
    )
    out = await call_tool(
        tai_chinh.mcp, "get_tuition_status", {"ma_sv": "SV22001", "ma_hoc_ky": "2020-2021-HK1"}
    )
    assert out["ma_loi"] == "HOC_PHI_KHONG_TON_TAI"


# --- ctsv -----------------------------------------------------------------
REQUEST = {
    "ma_don": "DT-2026-0001",
    "loai_don": "giay_xac_nhan_sv",
    "noi_dung": {"muc_dich": "Bổ sung hồ sơ vay vốn", "so_ban": 2},
    "trang_thai": "dang_xu_ly",
    "ghi_chu_xu_ly": "Nhận tại phòng A1.01",
    "tao_boi": "sinh_vien",
    "created_at": "2026-11-10T08:00:00+07:00",
    "updated_at": "2026-11-11T09:00:00+07:00",
}


async def test_ctsv_tools() -> None:
    tools = await list_tools(ctsv.mcp)
    assert set(tools) == {
        "list_my_requests",
        "get_request_status",
        "request_student_certificate",
        "submit_deferral_request",
        "submit_regrade_request",
        "ask_staff",
    }
    for tool in tools.values():
        assert next(iter(tool.input_schema["properties"])) == "ma_sv"


async def test_list_my_requests(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/internal/students/SV22001/requests").respond(
        200,
        json=[
            {
                k: REQUEST[k]
                for k in ("ma_don", "loai_don", "trang_thai", "tao_boi", "created_at", "updated_at")
            }
        ],
    )
    out = await call_tool(
        ctsv.mcp, "list_my_requests", {"ma_sv": "SV22001", "trang_thai": "dang_xu_ly"}
    )
    assert route.calls.last.request.url.params["trang_thai"] == "dang_xu_ly"
    assert out["don"] == [
        {
            "ma_don": "DT-2026-0001",
            "loai_don": "Giấy xác nhận sinh viên",
            "ma_loai_don": "giay_xac_nhan_sv",
            "trang_thai": "đang xử lý",
            "ma_trang_thai": "dang_xu_ly",
            "tao_boi": "Sinh viên",
            "ngay_tao": "2026-11-10",
            "ngay_cap_nhat": REQUEST["updated_at"][:10],
        }
    ]


async def test_list_my_requests_rejects_invalid_status() -> None:
    """Trạng thái ngoài enum bị SDK chặn trước khi tới qlsv_api."""
    from mcp import Client

    async with Client(ctsv.mcp) as client:
        result = await client.call_tool(
            "list_my_requests", {"ma_sv": "SV22001", "trang_thai": "bay_ba"}
        )
    assert result.is_error


async def test_get_request_status(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/requests/DT-2026-0001").respond(200, json=REQUEST)
    out = await call_tool(
        ctsv.mcp, "get_request_status", {"ma_sv": "SV22001", "ma_don": "DT-2026-0001"}
    )
    assert out["trang_thai"] == "đang xử lý" and out["ma_loai_don"] == "giay_xac_nhan_sv"
    assert out["thong_bao"] == (
        "Giấy xác nhận sinh viên DT-2026-0001 đang ở trạng thái đang xử lý. "
        "Ghi chú: Nhận tại phòng A1.01"
    )


async def test_get_request_status_encodes_ma_don(qlsv_mock: respx.MockRouter) -> None:
    """ma_don do LLM sinh ra có '/' không được thoát ra ngoài đường dẫn của sinh viên."""
    route = qlsv_mock.get(url__regex=r".*").respond(
        404, json={"detail": "Không tìm thấy đơn.", "code": "DON_KHONG_TON_TAI"}
    )
    out = await call_tool(
        ctsv.mcp, "get_request_status", {"ma_sv": "SV22001", "ma_don": "../../SV22002/requests/X"}
    )
    raw_path = route.calls.last.request.url.raw_path.decode()
    assert raw_path.startswith("/internal/students/SV22001/requests/..%2F..%2FSV22002")
    assert out["ma_loi"] == "DON_KHONG_TON_TAI"


async def test_other_students_request_is_not_found(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/requests/DT-2026-0002").respond(
        404, json={"detail": "Không tìm thấy đơn DT-2026-0002 của em.", "code": "DON_KHONG_TON_TAI"}
    )
    out = await call_tool(
        ctsv.mcp, "get_request_status", {"ma_sv": "SV22001", "ma_don": "DT-2026-0002"}
    )
    assert out["ma_loi"] == "DON_KHONG_TON_TAI"


async def test_answered_question_status_says_staff_answer(qlsv_mock: respx.MockRouter) -> None:
    question = {
        **REQUEST,
        "loai_don": "hoi_dap",
        "noi_dung": {"cau_hoi": "Học bổng xét theo học kỳ nào ạ?", "phong_ban": "ctsv"},
        "trang_thai": "hoan_tat",
        "ghi_chu_xu_ly": "Theo học kỳ liền trước.",
    }
    qlsv_mock.get("/internal/students/SV22001/requests/DT-2026-0001").respond(200, json=question)
    out = await call_tool(
        ctsv.mcp, "get_request_status", {"ma_sv": "SV22001", "ma_don": "DT-2026-0001"}
    )
    assert out["loai_don"] == "Câu hỏi gửi cán bộ" and out["ma_loai_don"] == "hoi_dap"
    assert out["thong_bao"].endswith("Trả lời của cán bộ: Theo học kỳ liền trước.")
