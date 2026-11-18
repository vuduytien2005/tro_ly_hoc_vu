"""MCP server `dao_tao` (:9101) — hồ sơ, bảng điểm, lịch học, lịch thi, tốt nghiệp, lớp học phần.

Tool ĐỌC: hồ sơ, bảng điểm, lịch, tiến độ tốt nghiệp, tìm lớp.
Tool GHI (register_course, cancel_course_registration): assistant_api KHÔNG gọi ngay mà tạo thẻ xác
nhận; chỉ gọi khi sinh viên bấm "Xác nhận" (bảng cong_cu: can_xac_nhan = 1).
Chạy: python -m src.mcp_servers.dao_tao
"""

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from src.mcp_servers.common import (
    MaHocKy,
    MaSv,
    day_label,
    path_segment,
    qlsv,
    run,
    tool_errors,
)
from src.shared.config import get_settings

MAX_SECTIONS = 10

mcp = MCPServer(
    name="dao_tao",
    title="Phòng Đào tạo",
    instructions=(
        "Tra cứu thông tin học tập của sinh viên đang đăng nhập: hồ sơ, bảng điểm, GPA, "
        "thời khóa biểu, lịch thi, tiến độ tốt nghiệp và các lớp học phần đang mở đăng ký; "
        "đăng ký / hủy đăng ký lớp học phần (cần sinh viên xác nhận)."
    ),
    version="0.6.0",
)


def _student_path(ma_sv: str, suffix: str = "") -> str:
    return f"/internal/students/{path_segment(ma_sv)}{suffix}"


@mcp.tool()
@tool_errors
async def get_student_profile(ma_sv: MaSv) -> dict[str, Any]:
    """Xem hồ sơ của sinh viên đang đăng nhập: họ tên, lớp, ngành, khóa, trạng thái học tập.

    Dùng khi sinh viên hỏi "em học lớp nào", "em thuộc khóa nào", "tình trạng học của em".
    """
    p = await qlsv.get(_student_path(ma_sv))
    return {
        "ho_ten": p["ho_ten"],
        "lop": p["lop"],
        "nganh": p["nganh"],
        "khoa": p["khoa"],
        "trang_thai": p["trang_thai"],
        "thong_bao": f"{p['ho_ten']}, lớp {p['lop']}, ngành {p['nganh']}, khóa {p['khoa']}.",
    }


@mcp.tool()
@tool_errors
async def get_transcript(ma_sv: MaSv, ma_hoc_ky: MaHocKy = None) -> dict[str, Any]:
    """Xem bảng điểm của sinh viên (toàn khóa hoặc một học kỳ), kèm GPA tích lũy và số tín chỉ
    tích lũy.

    Dùng khi sinh viên hỏi về điểm, môn bị F/rớt, GPA, điểm trung bình, số tín chỉ đã tích lũy.
    Ví dụ: "điểm của em thế nào", "GPA của em bao nhiêu", "học kỳ trước em được mấy điểm".
    GPA và tín chỉ luôn là TÍCH LŨY toàn khóa, kể cả khi lọc theo học kỳ.
    """
    t = await qlsv.get(_student_path(ma_sv, "/transcript"), ma_hoc_ky=ma_hoc_ky)
    rows = [
        {
            "ma_hp": r["ma_hp"],
            "ten_hp": r["ten_hp"],
            "tin_chi": r["tin_chi"],
            "hoc_ky": r["hoc_ky"],
            "diem_tong_ket": r["diem_tong_ket"],
            "diem_chu": r["diem_chu"],
            "lan_hoc": r["lan_hoc"],
        }
        for r in t["ket_qua"]
    ]
    failed = sorted({r["ma_hp"] for r in t["ket_qua"] if not r["dat"]})
    pham_vi = f"học kỳ {ma_hoc_ky}" if ma_hoc_ky else "toàn khóa"
    note = f"Bảng điểm {pham_vi}: {len(rows)} lượt học. "
    note += f"GPA tích lũy {t['gpa_tich_luy']:.2f}, đã tích lũy {t['tin_chi_tich_luy']} tín chỉ."
    if failed:
        note += f" Có điểm F ở: {', '.join(failed)}."
    if t["canh_bao_hoc_vu"]:
        note += " Sinh viên đang thuộc diện cảnh báo học vụ."
    return {
        "ket_qua": rows,
        "gpa_tich_luy": t["gpa_tich_luy"],
        "tin_chi_tich_luy": t["tin_chi_tich_luy"],
        "canh_bao_hoc_vu": t["canh_bao_hoc_vu"],
        "thong_bao": note,
    }


@mcp.tool()
@tool_errors
async def get_exam_schedule(ma_sv: MaSv, ma_hoc_ky: MaHocKy = None) -> dict[str, Any]:
    """Xem lịch thi các lớp học phần sinh viên đã đăng ký (mặc định học kỳ hiện tại).

    Dùng khi sinh viên hỏi "khi nào em thi", "lịch thi môn X", "thi ở phòng nào".
    """
    e = await qlsv.get(_student_path(ma_sv, "/exam-schedule"), ma_hoc_ky=ma_hoc_ky)
    rows = [
        {
            "ma_lop": x["ma_lop"],
            "ten_hp": x["ten_hp"],
            "ngay_thi": x["ngay_thi"],
            "gio": x["gio_bat_dau"][:5],
            "phong": x["phong"],
            "hinh_thuc": x["hinh_thuc"],
        }
        for x in e["lich_thi"]
    ]
    note = (
        f"Có {len(rows)} lịch thi trong học kỳ {e['ma_hoc_ky']}."
        if rows
        else f"Chưa có lịch thi nào trong học kỳ {e['ma_hoc_ky']}."
    )
    return {"hoc_ky": e["ma_hoc_ky"], "lich_thi": rows, "thong_bao": note}


@mcp.tool()
@tool_errors
async def get_current_schedule(ma_sv: MaSv, ma_hoc_ky: MaHocKy = None) -> dict[str, Any]:
    """Xem thời khóa biểu: các lớp học phần sinh viên đã đăng ký (mặc định học kỳ hiện tại).

    Dùng khi sinh viên hỏi "thời khóa biểu của em", "thứ mấy em học môn X", "em đã đăng ký
    những môn gì học kỳ sau" (khi đó truyền mã học kỳ sau, ví dụ "2026-2027-HK2").
    """
    s = await qlsv.get(_student_path(ma_sv, "/schedule"), ma_hoc_ky=ma_hoc_ky)
    rows = [
        {
            "ma_lop": x["ma_lop"],
            "ten_hp": x["ten_hp"],
            "tin_chi": x["tin_chi"],
            "thu": day_label(x["thu"]),
            "tiet": f"{x['tiet_bat_dau']}-{x['tiet_ket_thuc']}",
            "phong": x["phong"],
            "giang_vien": x["giang_vien"],
        }
        for x in s["lop"]
    ]
    note = (
        f"Học kỳ {s['ma_hoc_ky']}: {len(rows)} lớp, tổng {s['tong_tin_chi']} tín chỉ."
        if rows
        else f"Sinh viên chưa đăng ký lớp nào trong học kỳ {s['ma_hoc_ky']}."
    )
    return {
        "hoc_ky": s["ma_hoc_ky"],
        "lop": rows,
        "tong_tin_chi": s["tong_tin_chi"],
        "thong_bao": note,
    }


@mcp.tool()
@tool_errors
async def get_graduation_progress(ma_sv: MaSv) -> dict[str, Any]:
    """Đối chiếu tiến độ học tập với điều kiện tốt nghiệp: tín chỉ tích lũy, GPA, học phần còn
    thiếu, chứng chỉ (ngoại ngữ, giáo dục thể chất, giáo dục quốc phòng).

    Dùng khi sinh viên hỏi "em còn thiếu gì để tốt nghiệp", "em đủ điều kiện ra trường chưa".
    Nên kết hợp search_regulations để giải thích điều kiện tốt nghiệp theo quy chế.
    """
    g = await qlsv.get(_student_path(ma_sv, "/graduation-progress"))
    missing = [
        {
            "ma_hp": m["ma_hp"],
            "ten_hp": m["ten_hp"],
            "tin_chi": m["tin_chi"],
            "bat_buoc": m["bat_buoc"],
        }
        for m in g["hoc_phan_con_thieu"]
    ]
    if g["du_dieu_kien"]:
        note = "Sinh viên đã đủ điều kiện tốt nghiệp."
    else:
        note = "Chưa đủ điều kiện tốt nghiệp. " + " ".join(g["ly_do_chua_du"])
    return {
        "tong_tin_chi_yeu_cau": g["tong_tin_chi_yeu_cau"],
        "tin_chi_tich_luy": g["tin_chi_tich_luy"],
        "gpa": g["gpa"],
        "gpa_toi_thieu": g["gpa_toi_thieu"],
        "hoc_phan_con_thieu": missing,
        "chung_chi": g["chung_chi"],
        "du_dieu_kien": g["du_dieu_kien"],
        "thong_bao": note,
    }


@mcp.tool()
@tool_errors
async def search_course_sections(
    ma_sv: MaSv,
    tu_khoa: Annotated[
        str,
        Field(description='Mã lớp, mã học phần, tên học phần hoặc tên giảng viên, vd "IT004".'),
    ],
    ma_hoc_ky: MaHocKy = None,
) -> dict[str, Any]:
    """Tìm các lớp học phần đang mở đăng ký (mặc định học kỳ đang mở đăng ký), kèm lịch học và
    số chỗ còn trống. Trả tối đa 10 lớp.

    Dùng khi sinh viên muốn đăng ký / học lại một môn nhưng chưa biết mã lớp, hoặc hỏi
    "môn X có những lớp nào", "lớp nào còn chỗ". Sau đó dùng mã lớp tìm được để đăng ký.
    """
    del ma_sv  # không cần cho tra cứu, giữ để thống nhất quy ước tiêm ngữ cảnh / ghi nhật ký
    rows = await qlsv.get(
        "/internal/course-sections", q=tu_khoa, ma_hoc_ky=ma_hoc_ky, limit=MAX_SECTIONS
    )
    sections = [
        {
            "ma_lop": s["ma_lop"],
            "ma_hp": s["ma_hp"],
            "ten_hp": s["ten_hp"],
            "tin_chi": s["tin_chi"],
            "giang_vien": s["giang_vien"],
            "lich": s["lich"],
            "con_trong": s["con_trong"],
        }
        for s in rows[:MAX_SECTIONS]
    ]
    note = (
        f"Tìm thấy {len(sections)} lớp phù hợp với '{tu_khoa}'."
        if sections
        else f"Không có lớp nào đang mở phù hợp với '{tu_khoa}'."
    )
    return {"lop": sections, "thong_bao": note}


MaLop = Annotated[
    str,
    Field(
        min_length=2,
        max_length=30,
        description='Mã lớp học phần, ví dụ "IT004.02" (lấy từ kết quả search_course_sections).',
    ),
]


@mcp.tool()
@tool_errors
async def register_course(ma_sv: MaSv, ma_lop: MaLop) -> dict[str, Any]:
    """Đăng ký một lớp học phần cho sinh viên trong học kỳ đang mở đăng ký.

    Dùng khi sinh viên muốn đăng ký / học lại / học thêm một môn và đã xác định được mã lớp.
    Nếu chưa biết mã lớp, gọi search_course_sections trước để tìm lớp phù hợp (đúng thứ, còn chỗ).
    Thao tác này cần sinh viên xác nhận trên giao diện.
    Lỗi thường gặp: TRUNG_LICH (trùng lịch lớp đã đăng ký), LOP_DA_DAY, VUOT_TIN_CHI_TOI_DA,
    CHUA_DAT_TIEN_QUYET, DA_DANG_KY_HOC_PHAN, NGOAI_THOI_GIAN_DANG_KY.
    """
    r = await qlsv.request(
        "POST", _student_path(ma_sv, "/registrations"), json_body={"ma_lop": ma_lop}
    )
    return {
        "thanh_cong": True,
        "ma_lop": r["ma_lop"],
        "ten_hp": r["ten_hp"],
        "tin_chi": r["tin_chi"],
        "lich": r["lich"],
        "thong_bao": f"Đã đăng ký lớp {r['ma_lop']} – {r['ten_hp']} ({r['lich']}).",
    }


@mcp.tool()
@tool_errors
async def cancel_course_registration(ma_sv: MaSv, ma_lop: MaLop) -> dict[str, Any]:
    """Hủy đăng ký một lớp học phần sinh viên đã đăng ký (chỉ trong thời gian đăng ký).

    Dùng khi sinh viên muốn rút / bỏ / hủy một lớp đã đăng ký. Nếu chưa rõ mã lớp, gọi
    get_current_schedule để xem các lớp đã đăng ký. Thao tác này cần sinh viên xác nhận.
    """
    r = await qlsv.request("DELETE", _student_path(ma_sv, f"/registrations/{path_segment(ma_lop)}"))
    return {
        "thanh_cong": True,
        "ma_lop": r["ma_lop"],
        "ten_hp": r["ten_hp"],
        "thong_bao": f"Đã hủy đăng ký lớp {r['ma_lop']} – {r['ten_hp']}.",
    }


def main() -> None:
    run(mcp, get_settings().mcp_dao_tao_port)


if __name__ == "__main__":
    main()
