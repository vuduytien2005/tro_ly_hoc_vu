"""MCP server `ctsv` (:9102) — Công tác sinh viên: đơn từ.

Tool ĐỌC: list_my_requests, get_request_status.
Tool GHI (request_student_certificate, submit_deferral_request, submit_regrade_request,
ask_staff — câu hỏi gửi cán bộ, loại đơn hoi_dap): chỉ được
assistant_api gọi sau khi sinh viên bấm "Xác nhận"; đơn ghi nhận tao_boi = "tro_ly_ai".
Chạy: python -m src.mcp_servers.ctsv
"""

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.resolve import Elicit, Resolve
from pydantic import BaseModel, Field

from src.mcp_servers.common import MaSv, path_segment, qlsv, run, tool_errors
from src.shared.config import get_settings

mcp = MCPServer(
    name="ctsv",
    title="Phòng Công tác sinh viên",
    instructions=(
        "Nộp và tra cứu các đơn của sinh viên (giấy xác nhận sinh viên, bảo lưu, phúc khảo) "
        "cùng trạng thái xử lý; gửi câu hỏi cho cán bộ phòng ban. Nộp đơn, gửi câu hỏi cần "
        "sinh viên xác nhận."
    ),
    version="0.7.0",
)

LOAI_DON = {
    "giay_xac_nhan_sv": "Giấy xác nhận sinh viên",
    "bao_luu": "Đơn bảo lưu",
    "phuc_khao": "Đơn phúc khảo",
    "hoi_dap": "Câu hỏi gửi cán bộ",
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
            "ma_loai_don": d["loai_don"],
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
        label = "Trả lời của cán bộ" if d["loai_don"] == "hoi_dap" else "Ghi chú"
        note += f" {label}: {d['ghi_chu_xu_ly']}"
    return {
        "ma_don": d["ma_don"],
        "loai_don": loai,
        "ma_loai_don": d["loai_don"],
        "noi_dung": _hide_contact(d["noi_dung"]),
        "trang_thai": trang_thai,
        "ma_trang_thai": d["trang_thai"],
        "tao_boi": TAO_BOI.get(d.get("tao_boi", ""), d.get("tao_boi")),
        "ghi_chu_xu_ly": d.get("ghi_chu_xu_ly"),
        "ngay_tao": d["created_at"][:10],
        "cap_nhat_luc": d["updated_at"],
        "thong_bao": note,
    }


class LienHeBaoLuu(BaseModel):
    """Biểu mẫu MCP elicitation: liên hệ trong thời gian bảo lưu. Sinh viên điền thẳng trên thẻ
    xác nhận -> dữ liệu cá nhân này KHÔNG đi qua LLM."""

    so_dien_thoai: str = Field(
        title="Số điện thoại liên hệ",
        description="10 chữ số, bắt đầu bằng 0 (vd 0912345678).",
        pattern=r"^0\d{9}$",
    )
    email_ca_nhan: str | None = Field(
        default=None,
        title="Email cá nhân (không bắt buộc)",
        description="Email ngoài email trường, để phòng CTSV liên lạc khi em nghỉ học.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


ASK_CONTACT = (
    "Phòng Công tác sinh viên cần thông tin liên hệ của em trong thời gian bảo lưu. "
    "Thông tin này gửi thẳng tới hệ thống của trường, trợ lý AI không đọc được."
)
HIDDEN_CONTACT = "Đã cung cấp qua biểu mẫu (ẩn với trợ lý AI)."


def ask_contact(ctx: Context) -> Elicit[LienHeBaoLuu] | None:
    """Resolver: chỉ hỏi khi client khai báo năng lực elicitation (luồng thẻ xác nhận có giao
    diện). Client khác (vòng Agent thường, thực nghiệm) -> không hỏi, đơn không có liên hệ."""
    caps = ctx.client_capabilities
    if caps is None or caps.elicitation is None:
        return None
    return Elicit(ASK_CONTACT, LienHeBaoLuu)


def _hide_contact(noi_dung: dict[str, Any]) -> dict[str, Any]:
    """Kết quả công cụ đi vào prompt LLM -> không trả SĐT/email đã điền qua biểu mẫu."""
    return {**noi_dung, "lien_he": HIDDEN_CONTACT} if noi_dung.get("lien_he") else noi_dung


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
    # Do resolver điền (MCP elicitation) -> KHÔNG có trong input schema, LLM không thấy / không
    # điền được; mã băm duyệt của công cụ không đổi.
    lien_he: Annotated[LienHeBaoLuu | None, Resolve(ask_contact)] = None,
) -> dict[str, Any]:
    """Nộp đơn xin bảo lưu kết quả học tập (tạm dừng học).

    Đây là thao tác NHẠY CẢM: chỉ dùng khi sinh viên nói rõ muốn bảo lưu và đã cho biết lý do,
    học kỳ bắt đầu. Nên tra cứu quy chế về bảo lưu trước để nhắc sinh viên điều kiện.
    Lỗi thường gặp: NO_HOC_PHI (còn nợ học phí), SV_KHONG_DANG_HOC. Cần sinh viên xác nhận.
    """
    noi_dung: dict[str, Any] = {"ly_do": ly_do, "so_hoc_ky": so_hoc_ky, "tu_hoc_ky": tu_hoc_ky}
    if lien_he is not None:
        noi_dung["lien_he"] = lien_he.model_dump(exclude_none=True)
    return await _create_request(ma_sv, "bao_luu", noi_dung)


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


@mcp.tool()
@tool_errors
async def ask_staff(
    ma_sv: MaSv,
    cau_hoi: Annotated[
        str,
        Field(
            min_length=10,
            max_length=1000,
            description="Câu hỏi gửi cán bộ, viết lại đầy đủ để người đọc hiểu được ngay.",
        ),
    ],
    phong_ban: Annotated[
        Literal["dao_tao", "ctsv", "tai_chinh", "khac"],
        Field(
            description=(
                "Phòng ban phụ trách: dao_tao (học tập, đăng ký, tốt nghiệp), ctsv (học bổng, "
                "rèn luyện, giấy tờ), tai_chinh (học phí), khac (chưa rõ)."
            )
        ),
    ] = "khac",
) -> dict[str, Any]:
    """Gửi câu hỏi của sinh viên cho cán bộ phòng ban trả lời sau (xem ở "Thủ tục của em").

    Dùng khi văn bản quy chế không có căn cứ để trả lời, hoặc sinh viên muốn hỏi trực tiếp cán bộ,
    và sinh viên đã đồng ý gửi. Cán bộ KHÔNG xem được cuộc trò chuyện: viết lại câu hỏi đầy đủ,
    tự hiểu được. Thao tác này cần sinh viên xác nhận.
    """
    return await _create_request(ma_sv, "hoi_dap", {"cau_hoi": cau_hoi, "phong_ban": phong_ban})


def main() -> None:
    run(mcp, get_settings().mcp_ctsv_port)


if __name__ == "__main__":
    main()
