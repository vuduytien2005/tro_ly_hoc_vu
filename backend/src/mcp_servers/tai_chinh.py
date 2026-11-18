"""MCP server `tai_chinh` (:9103) — học phí.

Chạy: python -m src.mcp_servers.tai_chinh
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from src.mcp_servers.common import MaHocKy, MaSv, format_vnd, path_segment, qlsv, run, tool_errors
from src.shared.config import get_settings

mcp = MCPServer(
    name="tai_chinh",
    title="Phòng Tài chính",
    instructions="Tra cứu học phí của sinh viên đang đăng nhập.",
    version="0.3.0",
)

TRANG_THAI = {"da_nop": "đã nộp đủ", "nop_mot_phan": "mới nộp một phần", "chua_nop": "chưa nộp"}


@mcp.tool()
@tool_errors
async def get_tuition_status(ma_sv: MaSv, ma_hoc_ky: MaHocKy = None) -> dict[str, Any]:
    """Xem tình trạng học phí của sinh viên (mặc định học kỳ hiện tại): số phải nộp, đã nộp,
    còn nợ, hạn nộp.

    Dùng khi sinh viên hỏi "em còn nợ học phí không", "học phí kỳ này bao nhiêu", "hạn nộp
    học phí khi nào".
    """
    f = await qlsv.get(f"/internal/students/{path_segment(ma_sv)}/tuition", ma_hoc_ky=ma_hoc_ky)
    note = (
        f"Học kỳ {f['ma_hoc_ky']}: phải nộp {format_vnd(f['phai_nop'])}, "
        f"đã nộp {format_vnd(f['da_nop'])} ({TRANG_THAI.get(f['trang_thai'], f['trang_thai'])})."
    )
    if f["con_no"] > 0:
        note += f" Còn nợ {format_vnd(f['con_no'])}, hạn nộp {f['han_nop']}."
    return {
        "hoc_ky": f["ma_hoc_ky"],
        "phai_nop": f["phai_nop"],
        "da_nop": f["da_nop"],
        "con_no": f["con_no"],
        "han_nop": f["han_nop"],
        "trang_thai": f["trang_thai"],
        "thong_bao": note,
    }


def main() -> None:
    run(mcp, get_settings().mcp_tai_chinh_port)


if __name__ == "__main__":
    main()
