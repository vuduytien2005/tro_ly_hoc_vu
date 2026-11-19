"""Tool GHI của dao_tao và ctsv (qlsv_api mock): request gửi đúng, lỗi nghiệp vụ trả có cấu trúc."""

import json

import pytest
import respx

from src.mcp_servers import ctsv, dao_tao
from tests.mcp.conftest import call_tool, list_tools

pytestmark = pytest.mark.anyio

REGISTRATION = {
    "thanh_cong": True,
    "ma_lop": "IT004.02",
    "ma_hp": "IT004",
    "ten_hp": "Cơ sở dữ liệu",
    "tin_chi": 3,
    "hoc_ky": "2026-2027-HK1",
    "lich": "Thứ 2, tiết 1-3, phòng B2.101",
    "trang_thai": "da_dang_ky",
}


def request_out(loai_don: str, noi_dung: dict) -> dict:
    return {
        "ma_don": "DT-2026-0007",
        "loai_don": loai_don,
        "noi_dung": noi_dung,
        "trang_thai": "moi_tao",
        "ghi_chu_xu_ly": None,
        "tao_boi": "tro_ly_ai",
        "created_at": "2026-11-20T09:00:00+07:00",
        "updated_at": "2026-11-20T09:00:00+07:00",
    }


async def test_register_course(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.post("/internal/students/SV22001/registrations").respond(
        201, json=REGISTRATION
    )
    out = await call_tool(
        dao_tao.mcp, "register_course", {"ma_sv": "SV22001", "ma_lop": "IT004.02"}
    )
    assert json.loads(route.calls.last.request.content) == {"ma_lop": "IT004.02"}
    assert out["thanh_cong"] is True and out["ten_hp"] == "Cơ sở dữ liệu"
    assert "IT004.02" in out["thong_bao"]


async def test_register_course_check_only(qlsv_mock: respx.MockRouter) -> None:
    check = qlsv_mock.post("/internal/students/SV22001/registrations/check").respond(
        200, json={**REGISTRATION, "trang_thai": "hop_le"}
    )
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(
        201, json=REGISTRATION
    )
    out = await call_tool(
        dao_tao.mcp,
        "register_course",
        {"ma_sv": "SV22001", "ma_lop": "IT004.02", "chi_kiem_tra": True},
    )
    assert check.called and not post.called
    assert out["thanh_cong"] is True and "chưa đăng ký" in out["thong_bao"]


async def test_register_course_conflict_is_structured(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.post("/internal/students/SV22001/registrations").respond(
        409, json={"detail": "Trùng lịch với lớp IT004.02.", "code": "TRUNG_LICH"}
    )
    out = await call_tool(
        dao_tao.mcp, "register_course", {"ma_sv": "SV22001", "ma_lop": "SE105.02"}
    )
    assert out == {
        "thanh_cong": False,
        "ma_loi": "TRUNG_LICH",
        "thong_bao": "Trùng lịch với lớp IT004.02.",
    }


async def test_cancel_registration_encodes_path(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.delete("/internal/students/SV22001/registrations/IT004.02").respond(
        200, json={**REGISTRATION, "trang_thai": "da_huy"}
    )
    out = await call_tool(
        dao_tao.mcp, "cancel_course_registration", {"ma_sv": "SV22001", "ma_lop": "IT004.02"}
    )
    assert route.called and out["thanh_cong"] is True


async def test_cancel_rejects_path_traversal(qlsv_mock: respx.MockRouter) -> None:
    out = await call_tool(
        dao_tao.mcp, "cancel_course_registration", {"ma_sv": "SV22001", "ma_lop": "../SV22002"}
    )
    assert out["thanh_cong"] is False  # path_segment chặn, không gọi qlsv


async def test_certificate_request_sent_by_ai(qlsv_mock: respx.MockRouter) -> None:
    noi_dung = {"muc_dich": "vay vốn", "so_ban": 2}
    route = qlsv_mock.post("/internal/students/SV21001/requests").respond(
        201, json=request_out("giay_xac_nhan_sv", noi_dung)
    )
    out = await call_tool(
        ctsv.mcp,
        "request_student_certificate",
        {"ma_sv": "SV21001", "muc_dich": "vay vốn", "so_ban": 2},
    )
    assert json.loads(route.calls.last.request.content) == {
        "loai_don": "giay_xac_nhan_sv",
        "noi_dung": noi_dung,
        "tao_boi": "tro_ly_ai",
    }
    assert out["ma_don"] == "DT-2026-0007" and out["loai_don"] == "Giấy xác nhận sinh viên"


async def test_deferral_and_regrade_payloads(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.post("/internal/students/SV22001/requests").respond(
        201, json=request_out("bao_luu", {})
    )
    await call_tool(
        ctsv.mcp,
        "submit_deferral_request",
        {"ma_sv": "SV22001", "ly_do": "Ốm dài ngày", "tu_hoc_ky": "2026-2027-HK1"},
    )
    assert json.loads(route.calls.last.request.content)["noi_dung"] == {
        "ly_do": "Ốm dài ngày",
        "so_hoc_ky": 1,
        "tu_hoc_ky": "2026-2027-HK1",
    }
    await call_tool(
        ctsv.mcp, "submit_regrade_request", {"ma_sv": "SV22001", "ma_hp": "IT004", "ly_do": "Sai"}
    )
    body = json.loads(route.calls.last.request.content)
    assert body["loai_don"] == "phuc_khao" and body["noi_dung"] == {
        "ma_hp": "IT004",
        "ly_do": "Sai",
    }


async def test_deferral_debt_error(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.post("/internal/students/SV22001/requests").respond(
        409, json={"detail": "Em còn nợ học phí.", "code": "NO_HOC_PHI"}
    )
    out = await call_tool(
        ctsv.mcp,
        "submit_deferral_request",
        {"ma_sv": "SV22001", "ly_do": "x y", "tu_hoc_ky": "2026-2027-HK1"},
    )
    assert out["ma_loi"] == "NO_HOC_PHI"


async def test_write_tools_have_injected_ma_sv_first() -> None:
    for server, names in [
        (dao_tao.mcp, ["register_course", "cancel_course_registration"]),
        (
            ctsv.mcp,
            ["request_student_certificate", "submit_deferral_request", "submit_regrade_request"],
        ),
    ]:
        tools = await list_tools(server)
        for name in names:
            schema = tools[name].input_schema
            assert next(iter(schema["properties"])) == "ma_sv"
            assert "ma_sv" not in (tools[name].description or "")
