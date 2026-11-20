"""MCP server dao_tao: danh sách tool, schema tiêm ngữ cảnh, kết quả từng tool (qlsv_api mock)."""

import pytest
import respx

from src.mcp_servers import dao_tao
from src.mcp_servers.common import INJECTED_NOTE
from tests.mcp.conftest import call_tool, list_tools

pytestmark = pytest.mark.anyio

READ_TOOLS = {
    "plan_next_semester",
    "get_student_profile",
    "get_transcript",
    "get_exam_schedule",
    "get_current_schedule",
    "get_graduation_progress",
    "search_course_sections",
}

TRANSCRIPT = {
    "ma_sv": "SV22001",
    "ma_hoc_ky": None,
    "ket_qua": [
        {
            "ma_hp": "IT001",
            "ten_hp": "Nhập môn lập trình",
            "tin_chi": 4,
            "hoc_ky": "2024-2025-HK1",
            "diem_qua_trinh": 8.0,
            "diem_thi": 7.5,
            "diem_tong_ket": 7.7,
            "diem_chu": "B",
            "diem_he_4": 3.0,
            "lan_hoc": 1,
            "dat": True,
        },
        {
            "ma_hp": "IT004",
            "ten_hp": "Cơ sở dữ liệu",
            "tin_chi": 4,
            "hoc_ky": "2025-2026-HK2",
            "diem_qua_trinh": 3.0,
            "diem_thi": 2.5,
            "diem_tong_ket": 2.7,
            "diem_chu": "F",
            "diem_he_4": 0.0,
            "lan_hoc": 1,
            "dat": False,
        },
    ],
    "gpa_tich_luy": 3.06,
    "tin_chi_tich_luy": 25,
    "canh_bao_hoc_vu": False,
}


WRITE_TOOLS = {"register_course", "cancel_course_registration", "register_courses_bundle"}


async def test_tools_exposed() -> None:
    assert set(await list_tools(dao_tao.mcp)) == READ_TOOLS | WRITE_TOOLS


async def test_ma_sv_is_injected_parameter_not_in_description() -> None:
    """ma_sv là tham số đầu tiên, bắt buộc; ghi chú [INJECTED] nằm ở schema của tham số,
    KHÔNG nằm trong mô tả tool -> assistant_api xóa thuộc tính là LLM mất hết dấu vết."""
    for name, tool in (await list_tools(dao_tao.mcp)).items():
        schema = tool.input_schema
        assert next(iter(schema["properties"])) == "ma_sv", name
        assert "ma_sv" in schema["required"], name
        assert INJECTED_NOTE in schema["properties"]["ma_sv"]["description"], name
        assert "ma_sv" not in (tool.description or ""), name
        assert "INJECTED" not in (tool.description or ""), name


async def test_get_transcript(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/internal/students/SV22001/transcript").respond(200, json=TRANSCRIPT)
    out = await call_tool(dao_tao.mcp, "get_transcript", {"ma_sv": "SV22001"})

    assert "ma_hoc_ky" not in route.calls.last.request.url.params
    assert out["gpa_tich_luy"] == 3.06
    assert out["tin_chi_tich_luy"] == 25
    assert [r["ma_hp"] for r in out["ket_qua"]] == ["IT001", "IT004"]
    assert set(out["ket_qua"][0]) == {
        "ma_hp",
        "ten_hp",
        "tin_chi",
        "hoc_ky",
        "diem_tong_ket",
        "diem_chu",
        "lan_hoc",
    }
    assert "GPA tích lũy 3.06" in out["thong_bao"]
    assert "Có điểm F ở: IT004" in out["thong_bao"]


async def test_get_transcript_passes_semester(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/internal/students/SV22001/transcript").respond(200, json=TRANSCRIPT)
    out = await call_tool(
        dao_tao.mcp, "get_transcript", {"ma_sv": "SV22001", "ma_hoc_ky": "2025-2026-HK2"}
    )
    assert route.calls.last.request.url.params["ma_hoc_ky"] == "2025-2026-HK2"
    assert out["thong_bao"].startswith("Bảng điểm học kỳ 2025-2026-HK2")


async def test_unknown_student_returns_structured_error(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV99999/transcript").respond(
        404, json={"detail": "Không tìm thấy sinh viên SV99999.", "code": "SV_KHONG_TON_TAI"}
    )
    out = await call_tool(dao_tao.mcp, "get_transcript", {"ma_sv": "SV99999"})
    assert out == {
        "thanh_cong": False,
        "ma_loi": "SV_KHONG_TON_TAI",
        "thong_bao": "Không tìm thấy sinh viên SV99999.",
    }


async def test_qlsv_down_returns_structured_error(qlsv_mock: respx.MockRouter) -> None:
    import httpx

    qlsv_mock.get("/internal/students/SV22001").mock(side_effect=httpx.ConnectError("x"))
    out = await call_tool(dao_tao.mcp, "get_student_profile", {"ma_sv": "SV22001"})
    assert out["ma_loi"] == "QLSV_KHONG_KET_NOI"


async def test_get_student_profile(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ho_ten": "Nguyễn Văn An",
            "email": "an@sv.edu.vn",
            "ngay_sinh": "2004-03-15",
            "gioi_tinh": "nam",
            "lop": "KTPM2022",
            "ma_nganh": "7480103",
            "nganh": "Kỹ thuật phần mềm",
            "khoa": "K2022",
            "trang_thai": "dang_hoc",
        },
    )
    out = await call_tool(dao_tao.mcp, "get_student_profile", {"ma_sv": "SV22001"})
    assert out["ho_ten"] == "Nguyễn Văn An"
    assert "email" not in out and "ngay_sinh" not in out  # chỉ trả thông tin cần cho câu trả lời
    assert "lớp KTPM2022" in out["thong_bao"]


async def test_get_current_schedule(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/schedule").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ma_hoc_ky": "2026-2027-HK1",
            "lop": [
                {
                    "ma_lop": "SE104.01",
                    "ma_hp": "SE104",
                    "ten_hp": "Nhập môn CNPM",
                    "tin_chi": 4,
                    "thu": 2,
                    "tiet_bat_dau": 1,
                    "tiet_ket_thuc": 3,
                    "lich": "Thứ 2, tiết 1-3, phòng B2.101",
                    "phong": "B2.101",
                    "giang_vien": "TS. Trần B",
                }
            ],
            "tong_tin_chi": 4,
        },
    )
    out = await call_tool(dao_tao.mcp, "get_current_schedule", {"ma_sv": "SV22001"})
    assert out["lop"][0]["thu"] == "Thứ 2"
    assert out["lop"][0]["tiet"] == "1-3"
    assert out["thong_bao"] == "Học kỳ 2026-2027-HK1: 1 lớp, tổng 4 tín chỉ."


async def test_get_exam_schedule_empty(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/exam-schedule").respond(
        200, json={"ma_sv": "SV22001", "ma_hoc_ky": "2026-2027-HK1", "lich_thi": []}
    )
    out = await call_tool(dao_tao.mcp, "get_exam_schedule", {"ma_sv": "SV22001"})
    assert out["lich_thi"] == []
    assert "Chưa có lịch thi" in out["thong_bao"]


async def test_get_exam_schedule(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/exam-schedule").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ma_hoc_ky": "2026-2027-HK1",
            "lich_thi": [
                {
                    "ma_lop": "SE104.01",
                    "ma_hp": "SE104",
                    "ten_hp": "Nhập môn CNPM",
                    "ngay_thi": "2027-01-10",
                    "gio_bat_dau": "07:30:00",
                    "phong": "A1.201",
                    "hinh_thuc": "tu_luan",
                }
            ],
        },
    )
    out = await call_tool(dao_tao.mcp, "get_exam_schedule", {"ma_sv": "SV22001"})
    assert out["lich_thi"][0]["gio"] == "07:30"


async def test_get_graduation_progress(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/graduation-progress").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "tong_tin_chi_yeu_cau": 40,
            "tin_chi_tich_luy": 25,
            "gpa": 3.06,
            "gpa_toi_thieu": 2.0,
            "hoc_phan_con_thieu": [
                {
                    "ma_hp": "SE202",
                    "ten_hp": "Khóa luận",
                    "tin_chi": 5,
                    "bat_buoc": True,
                    "hoc_ky_goi_y": 8,
                },
            ],
            "chung_chi": {"ngoai_ngu": False, "gdtc": True, "gdqp": True},
            "yeu_cau_ngoai_ngu": True,
            "du_dieu_kien": False,
            "ly_do_chua_du": ["Còn thiếu 15 tín chỉ.", "Chưa có chứng chỉ ngoại ngữ."],
        },
    )
    out = await call_tool(dao_tao.mcp, "get_graduation_progress", {"ma_sv": "SV22001"})
    assert out["du_dieu_kien"] is False
    assert out["hoc_phan_con_thieu"][0]["ma_hp"] == "SE202"
    assert "hoc_ky_goi_y" not in out["hoc_phan_con_thieu"][0]
    assert out["thong_bao"] == (
        "Chưa đủ điều kiện tốt nghiệp. Còn thiếu 15 tín chỉ. Chưa có chứng chỉ ngoại ngữ."
    )


async def test_search_course_sections(qlsv_mock: respx.MockRouter) -> None:
    section = {
        "ma_lop": "IT004.01",
        "ma_hp": "IT004",
        "ten_hp": "Cơ sở dữ liệu",
        "tin_chi": 4,
        "hoc_ky": "2026-2027-HK2",
        "giang_vien": "ThS. Lê C",
        "thu": 3,
        "tiet_bat_dau": 1,
        "tiet_ket_thuc": 3,
        "phong": "B1.102",
        "lich": "Thứ 3, tiết 1-3, phòng B1.102",
        "si_so_toi_da": 60,
        "da_dang_ky": 58,
        "con_trong": 2,
    }
    route = qlsv_mock.get("/internal/course-sections").respond(200, json=[section] * 15)
    out = await call_tool(
        dao_tao.mcp, "search_course_sections", {"ma_sv": "SV22001", "tu_khoa": "IT004"}
    )
    params = route.calls.last.request.url.params
    assert params["q"] == "IT004"
    assert params["limit"] == "10"
    assert "ma_sv" not in params  # ma_sv không bị gửi đi khi không cần
    assert len(out["lop"]) == dao_tao.MAX_SECTIONS
    assert out["lop"][0]["con_trong"] == 2


# ----- Kế hoạch học kỳ tới + đăng ký cả gói ------------------------------------------------
PLAN = {
    "hoc_ky": "2026-2027-HK2",
    "ten_hoc_ky": "Học kỳ 2 năm học 2026-2027",
    "tin_chi_toi_da": 25,
    "tin_chi_da_dang_ky": 0,
    "de_xuat": [
        {
            "ma_lop": "IT004.02",
            "ma_hp": "IT004",
            "ten_hp": "Cơ sở dữ liệu",
            "tin_chi": 3,
            "lich": "Thứ 2, tiết 1-3, phòng B2.101",
            "bat_buoc": True,
            "ly_do_chon": "Học lại (đã bị điểm F)",
        },
        {
            "ma_lop": "SE201.01",
            "ma_hp": "SE201",
            "ten_hp": "Trí tuệ nhân tạo ứng dụng",
            "tin_chi": 3,
            "lich": "Thứ 3, tiết 7-9, phòng A1.305",
            "bat_buoc": False,
            "ly_do_chon": "Tự chọn",
        },
    ],
    "tong_tin_chi_de_xuat": 6,
    "bi_loai": [
        {
            "ma_hp": "SE202",
            "ten_hp": "Điện toán đám mây",
            "ma_loi": "KHONG_CON_LOP_PHU_HOP",
            "ly_do": "Không còn lớp nào phù hợp (xem lý do từng lớp).",
            "lop": [{"ma_lop": "SE202.01", "ma_loi": "LOP_DA_DAY", "ly_do": "Lớp đã đủ 2."}],
        }
    ],
}


async def test_plan_tool_message(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/internal/students/SV22001/semester-plan").respond(200, json=PLAN)
    out = await call_tool(dao_tao.mcp, "plan_next_semester", {"ma_sv": "SV22001"})
    assert [s["ma_lop"] for s in out["de_xuat"]] == ["IT004.02", "SE201.01"]
    assert "IT004.02" in out["thong_bao"] and "6 tín chỉ" in out["thong_bao"]
    assert "SE202" in out["thong_bao"] and "LOP_DA_DAY" not in out["thong_bao"]


async def test_plan_tool_empty_message(qlsv_mock: respx.MockRouter) -> None:
    empty = {**PLAN, "de_xuat": [], "tong_tin_chi_de_xuat": 0}
    qlsv_mock.get("/internal/students/SV21001/semester-plan").respond(200, json=empty)
    out = await call_tool(dao_tao.mcp, "plan_next_semester", {"ma_sv": "SV21001"})
    assert out["thong_bao"].startswith("Không có lớp nào phù hợp")


async def test_bundle_tool_check_and_error(qlsv_mock: respx.MockRouter) -> None:
    base = "/internal/students/SV22001/registrations/bundle"
    ok = {
        "trang_thai": "hop_le",
        "tong_tin_chi": 3,
        "lop": [
            {
                "ma_lop": "IT004.02",
                "ma_hp": "IT004",
                "ten_hp": "Cơ sở dữ liệu",
                "tin_chi": 3,
                "hoc_ky": "2026-2027-HK2",
                "lich": "Thứ 2, tiết 1-3, phòng B2.101",
                "trang_thai": "hop_le",
            }
        ],
    }
    check = qlsv_mock.post(f"{base}/check").respond(200, json=ok)
    out = await call_tool(
        dao_tao.mcp,
        "register_courses_bundle",
        {"ma_sv": "SV22001", "ma_lop": ["IT004.02"], "chi_kiem_tra": True},
    )
    assert check.called and out["thanh_cong"] is True
    qlsv_mock.post(base).respond(
        409, json={"detail": "Lớp SE105.02: trùng lịch", "code": "TRUNG_LICH"}
    )
    out = await call_tool(
        dao_tao.mcp,
        "register_courses_bundle",
        {"ma_sv": "SV22001", "ma_lop": ["IT004.02", "SE105.02"]},
    )
    assert out["ma_loi"] == "TRUNG_LICH"


async def test_bundle_tool_schema() -> None:
    tools = await list_tools(dao_tao.mcp)
    props = tools["register_courses_bundle"].input_schema["properties"]
    assert props["ma_lop"]["type"] == "array"
    assert (props["ma_lop"]["minItems"], props["ma_lop"]["maxItems"]) == (1, 8)
    assert INJECTED_NOTE in props["ma_sv"]["description"]
    assert "ma_sv" in tools["plan_next_semester"].input_schema["properties"]
