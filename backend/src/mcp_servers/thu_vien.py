"""MCP server `thu_vien` (:9105) — Thư viện: sách đang mượn, tìm sách, gia hạn.

Server bổ sung (20/11/2026) để minh họa: quản trị viên THÊM server này trên trang "MCP & quyền"
lúc hệ thống đang chạy, duyệt mô tả rồi bật công cụ; trợ lý dùng được ngay, không sửa code.
Vì vậy server KHÔNG có trong dữ liệu mẫu `04_assistant_seed.sql`.

Mỗi công cụ khai báo `title` (tên hiển thị) và annotation `readOnlyHint` theo chuẩn MCP: trợ lý
dùng `title` cho thẻ xác nhận / nhãn "Đang…"; `readOnlyHint` chỉ là GỢI Ý cho quản trị viên
(server tự khai báo, không được tin tuyệt đối).

Chạy: python -m src.mcp_servers.thu_vien
"""

from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from src.mcp_servers.common import MaSv, path_segment, qlsv, run, tool_errors
from src.shared.config import get_settings

mcp = MCPServer(
    name="thu_vien",
    title="Thư viện",
    instructions="Tra cứu sách đang mượn, tìm sách và gia hạn sách cho sinh viên đang đăng nhập.",
    version="0.1.0",
)

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False)


def _vn_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def _borrow(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "muon_id": b["muon_id"],
        "ma_sach": b["ma_sach"],
        "ten_sach": b["ten_sach"],
        "tac_gia": b["tac_gia"],
        "han_tra": b["han_tra"],
        "so_lan_gia_han": b["so_lan_gia_han"],
        "qua_han": b["qua_han"],
        "gia_han_duoc": b["gia_han_duoc"],
        "ly_do_khong_gia_han": b["ly_do_khong_gia_han"],
    }


@mcp.tool(title="Xem sách đang mượn", annotations=READ_ONLY)
@tool_errors
async def get_borrowed_books(ma_sv: MaSv) -> dict[str, Any]:
    """Xem danh sách sách sinh viên đang mượn ở thư viện: hạn trả, số lần đã gia hạn, có gia hạn
    được không (và vì sao).

    Dùng khi sinh viên hỏi "em đang mượn sách gì", "sách khi nào hết hạn", hoặc TRƯỚC khi gia
    hạn để lấy `muon_id`.
    """
    rows = await qlsv.get(f"/internal/students/{path_segment(ma_sv)}/borrows")
    if not rows:
        return {"sach": [], "thong_bao": "Em hiện không mượn cuốn sách nào."}
    parts = []
    for b in rows:
        state = "quá hạn" if b["qua_han"] else f"hạn trả {_vn_date(b['han_tra'])}"
        extra = "" if b["gia_han_duoc"] else f" — {b['ly_do_khong_gia_han']}"
        parts.append(f"{b['ten_sach']} ({state}){extra}")
    return {
        "sach": [_borrow(b) for b in rows],
        "thong_bao": f"Em đang mượn {len(rows)} cuốn: " + "; ".join(parts) + ".",
    }


@mcp.tool(title="Tìm sách thư viện", annotations=READ_ONLY)
@tool_errors
async def search_books(
    ma_sv: MaSv,
    tu_khoa: Annotated[
        str, Field(min_length=1, max_length=100, description="Tên sách hoặc tên tác giả cần tìm.")
    ],
) -> dict[str, Any]:
    """Tìm sách trong thư viện theo tên hoặc tác giả, cho biết còn bao nhiêu bản để mượn.

    Dùng khi sinh viên hỏi "thư viện có sách … không", "còn sách … để mượn không".
    """
    rows = await qlsv.get("/internal/books", tu_khoa=tu_khoa)
    if not rows:
        return {"sach": [], "thong_bao": f"Không tìm thấy sách nào khớp với '{tu_khoa}'."}
    return {
        "sach": rows,
        "thong_bao": f"Tìm thấy {len(rows)} cuốn: "
        + "; ".join(f"{s['ten_sach']} - {s['tac_gia']} (còn {s['so_ban_con']} bản)" for s in rows)
        + ".",
    }


@mcp.tool(title="Gia hạn sách", annotations=WRITE)
@tool_errors
async def renew_book(
    ma_sv: MaSv,
    muon_id: Annotated[
        int, Field(ge=1, description="Mã lượt mượn (muon_id) lấy từ get_borrowed_books.")
    ],
) -> dict[str, Any]:
    """Gia hạn thêm 14 ngày cho một cuốn sách sinh viên đang mượn.

    Không gia hạn được khi sách đã quá hạn, đã gia hạn đủ 2 lần hoặc đang có người đặt trước.
    Nếu chưa biết `muon_id`, gọi get_borrowed_books trước.
    """
    b = await qlsv.request(
        "POST", f"/internal/students/{path_segment(ma_sv)}/borrows/{muon_id}/renew"
    )
    return {
        "thanh_cong": True,
        "muon_id": b["muon_id"],
        "ten_sach": b["ten_sach"],
        "han_tra_moi": b["han_tra"],
        "so_lan_gia_han": b["so_lan_gia_han"],
        "thong_bao": (
            f"Đã gia hạn sách '{b['ten_sach']}' đến ngày {_vn_date(b['han_tra'])} "
            f"(đã gia hạn {b['so_lan_gia_han']} lần)."
        ),
    }


def main() -> None:
    run(mcp, get_settings().mcp_thu_vien_port)


if __name__ == "__main__":
    main()
