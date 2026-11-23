"""Cấu hình MCP, danh mục công cụ, nhật ký gọi công cụ, hành động chờ xác nhận."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Unicode,
    UnicodeText,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.assistant_api.models.base import AssistantBase


class McpServer(AssistantBase):
    __tablename__ = "mcp_server"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ten: Mapped[str] = mapped_column(Unicode(50), unique=True)  # dao_tao, ctsv, ...
    mo_ta: Mapped[str] = mapped_column(Unicode(255))
    dia_chi: Mapped[str] = mapped_column(Unicode(255))  # vd: http://127.0.0.1:9101/mcp
    bat: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    cong_cu: Mapped[list["CongCu"]] = relationship(back_populates="mcp_server")


class CongCu(AssistantBase):
    """Danh mục công cụ + chính sách quyền (rủi ro, cần xác nhận, bật/tắt)."""

    __tablename__ = "cong_cu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcp_server_id: Mapped[int] = mapped_column(ForeignKey("mcp_server.id"))
    ten: Mapped[str] = mapped_column(Unicode(100))
    mo_ta: Mapped[str] = mapped_column(Unicode(500))
    muc_rui_ro: Mapped[str] = mapped_column(Enum("doc", "ghi", "nhay_cam", name="muc_rui_ro"))
    can_xac_nhan: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))
    bat: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    # SHA-256 (mô tả + title + input schema) lúc quản trị viên bật; NULL = chưa duyệt.
    # Mô tả trên server khác bản đã duyệt -> tự tắt (chống "rug pull"), xem registry.sync.
    ban_duyet: Mapped[str | None] = mapped_column(Unicode(64))

    mcp_server: Mapped[McpServer] = relationship(back_populates="cong_cu")


TRANG_THAI_LUOT_GOI = ("thanh_cong", "loi", "bi_tu_choi", "cho_xac_nhan", "da_huy")


class LuotGoiCongCu(AssistantBase):
    """Nhật ký MỌI lần Agent gọi công cụ (quản trị + thực nghiệm Chương 4)."""

    __tablename__ = "luot_goi_cong_cu"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hoi_thoai_id: Mapped[int | None] = mapped_column(
        ForeignKey("hoi_thoai.id", ondelete="SET NULL")
    )
    nguoi_dung_id: Mapped[int] = mapped_column(ForeignKey("nguoi_dung.id"))
    mcp_server: Mapped[str] = mapped_column(Unicode(50))
    ten_cong_cu: Mapped[str] = mapped_column(Unicode(100))
    # SAU khi tiêm ngữ cảnh
    tham_so: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    # Tham số gốc do LLM sinh (để phân tích)
    tham_so_llm: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    # CHECK ISJSON chỉ nhận object/array -> kết quả dạng scalar phải bọc, vd {"gia_tri": ...}
    ket_qua: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON(none_as_null=True))
    trang_thai: Mapped[str] = mapped_column(Enum(*TRANG_THAI_LUOT_GOI, name="trang_thai_lg"))
    ly_do: Mapped[str | None] = mapped_column(Unicode(500))
    thoi_gian_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(precision=3), server_default=text("SYSDATETIME()")
    )


class HanhDongChoXacNhan(AssistantBase):
    """Hành động ghi/nhạy cảm đang chờ sinh viên bấm "Xác nhận"."""

    __tablename__ = "hanh_dong_cho_xac_nhan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma: Mapped[str] = mapped_column(CHAR(36), unique=True)  # UUID gửi cho frontend
    hoi_thoai_id: Mapped[int] = mapped_column(ForeignKey("hoi_thoai.id", ondelete="CASCADE"))
    nguoi_dung_id: Mapped[int] = mapped_column(ForeignKey("nguoi_dung.id"))
    luot_goi_id: Mapped[int] = mapped_column(ForeignKey("luot_goi_cong_cu.id"))
    mcp_server: Mapped[str] = mapped_column(Unicode(50))
    ten_cong_cu: Mapped[str] = mapped_column(Unicode(100))
    tham_so: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    mo_ta: Mapped[str] = mapped_column(UnicodeText)
    trang_thai: Mapped[str] = mapped_column(
        Enum("cho", "cho_bo_sung", "da_xac_nhan", "da_huy", "het_han", name="trang_thai_hd"),
        server_default=text("N'cho'"),
    )
    # MCP elicitation: yêu cầu bổ sung của server {khoa, thong_diep, schema, request_state, vong}
    yeu_cau_bo_sung: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    het_han_luc: Mapped[datetime] = mapped_column(DATETIME2)
    xu_ly_luc: Mapped[datetime | None] = mapped_column(DATETIME2)
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))

    luot_goi: Mapped[LuotGoiCongCu] = relationship()
