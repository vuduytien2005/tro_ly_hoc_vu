"""MCP server `ctsv` (:9102) — Công tác sinh viên: đơn từ.

Tool ĐỌC: list_my_requests, get_request_status.
Tool GHI (request_student_certificate, submit_deferral_request, submit_regrade_request): chỉ được
assistant_api gọi sau khi sinh viên bấm "Xác nhận"; đơn ghi nhận tao_boi = "tro_ly_ai".
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
        "Nộp và tra cứu các đơn của sinh viên (giấy xác nhận sinh viên, bảo lưu, phúc khảo) "
        "cùng trạng thái xử lý. Nộp đơn cần sinh viên xác nhận."
    ),
    version="0.6.0",
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
TAO_BOI = {"sinh_vien": "Sinh viên", "tro_ly_ai": "Trợ lý AI"}


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
            "ma_trang_thai": d["trang_thai"],
            "tao_boi": TAO_BOI.get(d.get("tao_boi", ""), d.get("tao_boi")),
            "ngay_tao": d["created_at"][:10],
            "ngay_cap_nhat": (d.get("updated_at") or d["created_at"])[:10],
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
        "ma_trang_thai": d["trang_thai"],
        "tao_boi": TAO_BOI.get(d.get("tao_boi", ""), d.get("tao_boi")),
        "ghi_chu_xu_ly": d.get("ghi_chu_xu_ly"),
        "ngay_tao": d["created_at"][:10],
        "cap_nhat_luc": d["updated_at"],
        "thong_bao": note,
    }


async def _create_request(ma_sv: str, loai_don: str, noi_dung: dict[str, Any]) -> dict[str, Any]:
    d = await qlsv.request(
        "POST",
        f"/internal/students/{path_segment(ma_sv)}/requests",
        json_body={"loai_don": loai_don, "noi_dung": noi_dung, "tao_boi": "tro_ly_ai"},
    )
    loai = LOAI_DON.get(d["loai_don"], d["loai_don"])
    return {
        "thanh_cong": True,
        "ma_don": d["ma_don"],
        "loai_don": loai,
        "trang_thai": TRANG_THAI_DON.get(d["trang_thai"], d["trang_thai"]),
        "thong_bao": (
            f"Đã tạo {loai.lower()} mã {d['ma_don']}. "
            'Sinh viên theo dõi tiến độ ở mục "Thủ tục của em".'
        ),
    }


@mcp.tool()
@tool_errors
async def request_student_certificate(
    ma_sv: MaSv,
    muc_dich: Annotated[
        str,
        Field(
            min_length=2,
            max_length=200,
            description='Mục đích xin giấy, vd "làm hồ sơ vay vốn ngân hàng chính sách".',
        ),
    ],
    so_ban: Annotated[int, Field(ge=1, le=5, description="Số bản cần cấp (1–5).")] = 1,
) -> dict[str, Any]:
    """Tạo yêu cầu cấp giấy xác nhận sinh viên (đang học tại trường).

    Dùng khi sinh viên cần giấy xác nhận để vay vốn, xin học bổng, tạm hoãn nghĩa vụ quân sự,
    làm hồ sơ... Hỏi lại mục đích nếu sinh viên chưa nói. Thao tác này cần sinh viên xác nhận.
    """
    return await _create_request(
        ma_sv, "giay_xac_nhan_sv", {"muc_dich": muc_dich, "so_ban": so_ban}
    )


@mcp.tool()
@tool_errors
async def submit_deferral_request(
    ma_sv: MaSv,
    ly_do: Annotated[str, Field(min_length=2, max_length=500, description="Lý do xin bảo lưu.")],
    tu_hoc_ky: Annotated[
        str,
        Field(description='Học kỳ bắt đầu bảo lưu, mã dạng "2025-2026-HK2".'),
    ],
    so_hoc_ky: Annotated[int, Field(ge=1, le=2, description="Số học kỳ xin bảo lưu (1–2).")] = 1,
) -> dict[str, Any]:
    """Nộp đơn xin bảo lưu kết quả học tập (tạm dừng học).

    Đây là thao tác NHẠY CẢM: chỉ dùng khi sinh viên nói rõ muốn bảo lưu và đã cho biết lý do,
    học kỳ bắt đầu. Nên tra cứu quy chế về bảo lưu trước để nhắc sinh viên điều kiện.
    Lỗi thường gặp: NO_HOC_PHI (còn nợ học phí), SV_KHONG_DANG_HOC. Cần sinh viên xác nhận.
    """
    return await _create_request(
        ma_sv, "bao_luu", {"ly_do": ly_do, "so_hoc_ky": so_hoc_ky, "tu_hoc_ky": tu_hoc_ky}
    )


@mcp.tool()
@tool_errors
async def submit_regrade_request(
    ma_sv: MaSv,
    ma_hp: Annotated[
        str,
        Field(min_length=2, max_length=20, description='Mã học phần cần phúc khảo, vd "IT004".'),
    ],
    ly_do: Annotated[str, Field(min_length=2, max_length=500, description="Lý do xin phúc khảo.")],
) -> dict[str, Any]:
    """Nộp đơn phúc khảo điểm thi một học phần của học kỳ vừa kết thúc.

    Dùng khi sinh viên thấy điểm thi chưa đúng và muốn chấm lại. Nếu chưa rõ mã học phần,
    gọi get_transcript trước. Lỗi thường gặp: KHONG_CO_DIEM_HOC_KY_GAN_NHAT.
    Thao tác này cần sinh viên xác nhận.
    """
    return await _create_request(ma_sv, "phuc_khao", {"ma_hp": ma_hp, "ly_do": ly_do})


def main() -> None:
    run(mcp, get_settings().mcp_ctsv_port)


if __name__ == "__main__":
    main()
