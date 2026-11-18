"""MCP server `ctsv` (:9102) — Công tác sinh viên: đơn từ.

Giai đoạn 3: chỉ các tool ĐỌC (list_my_requests, get_request_status).
Tool ghi (request_student_certificate, submit_deferral_request, submit_regrade_request)
ở Giai đoạn 6.
Chạy: python -m src.mcp_servers.ctsv
"""

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from src.mcp_servers.common import MaSv, path_segment, qlsv, run, tool_errors
from src.shared.config import get_settings

mcp = MCPServer(
    name="ctsv",
    title="Phòng Công tác sinh viên",
    instructions=(
        "Tra cứu các đơn sinh viên đã gửi (giấy xác nhận sinh viên, bảo lưu, phúc khảo) "
        "và trạng thái xử lý."
    ),
    version="0.3.0",
)

LOAI_DON = {
    "giay_xac_nhan_sv": "Giấy xác nhận sinh viên",
    "bao_luu": "Đơn bảo lưu",
    "phuc_khao": "Đơn phúc khảo",
}
TRANG_THAI_DON = {
    "moi_tao": "mới tạo",
    "dang_xu_ly": "đang xử lý",
    "da_duyet": "đã duyệt",
    "tu_choi": "bị từ chối",
    "hoan_tat": "hoàn tất",
}


@mcp.tool()
@tool_errors
async def list_my_requests(
    ma_sv: MaSv,
    trang_thai: Annotated[
        Literal["moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat"] | None,
        Field(description="Lọc theo trạng thái đơn. Bỏ trống để xem tất cả."),
    ] = None,
) -> dict[str, Any]:
    """Xem danh sách các đơn sinh viên đã gửi (mới nhất trước) và trạng thái từng đơn.

    Dùng khi sinh viên hỏi "em đã gửi những đơn gì", "đơn của em xử lý đến đâu rồi" mà không
    nêu mã đơn cụ thể.
    """
    rows = await qlsv.get(
        f"/internal/students/{path_segment(ma_sv)}/requests", trang_thai=trang_thai
    )
    don = [
        {
            "ma_don": d["ma_don"],
            "loai_don": LOAI_DON.get(d["loai_don"], d["loai_don"]),
            "trang_thai": TRANG_THAI_DON.get(d["trang_thai"], d["trang_thai"]),
            "ngay_tao": d["created_at"][:10],
        }
        for d in rows
    ]
    note = f"Sinh viên có {len(don)} đơn." if don else "Sinh viên chưa có đơn nào phù hợp."
    return {"don": don, "thong_bao": note}


@mcp.tool()
@tool_errors
async def get_request_status(
    ma_sv: MaSv,
    ma_don: Annotated[str, Field(description='Mã đơn, ví dụ "DT-2026-0001".')],
) -> dict[str, Any]:
    """Xem chi tiết và trạng thái xử lý của MỘT đơn theo mã đơn.

    Dùng khi sinh viên hỏi về một đơn cụ thể, ví dụ "đơn DT-2026-0001 của em sao rồi".
    Chỉ xem được đơn của chính sinh viên đang đăng nhập.
    """
    d = await qlsv.get(f"/internal/students/{path_segment(ma_sv)}/requests/{path_segment(ma_don)}")
    loai = LOAI_DON.get(d["loai_don"], d["loai_don"])
    trang_thai = TRANG_THAI_DON.get(d["trang_thai"], d["trang_thai"])
    note = f"{loai} {d['ma_don']} đang ở trạng thái {trang_thai}."
    if d.get("ghi_chu_xu_ly"):
        note += f" Ghi chú: {d['ghi_chu_xu_ly']}"
    return {
        "ma_don": d["ma_don"],
        "loai_don": loai,
        "noi_dung": d["noi_dung"],
        "trang_thai": trang_thai,
        "ghi_chu_xu_ly": d.get("ghi_chu_xu_ly"),
        "ngay_tao": d["created_at"][:10],
        "cap_nhat_luc": d["updated_at"],
        "thong_bao": note,
    }


def main() -> None:
    run(mcp, get_settings().mcp_ctsv_port)


if __name__ == "__main__":
    main()
