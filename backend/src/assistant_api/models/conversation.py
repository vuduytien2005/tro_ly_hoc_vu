from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    SmallInteger,
    Unicode,
    UnicodeText,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.assistant_api.models.base import AssistantBase


class HoiThoai(AssistantBase):
    __tablename__ = "hoi_thoai"
    # Bảng có TRIGGER: SQL Server cấm "INSERT ... OUTPUT" (cách SQLAlchemy lấy id mới)
    # trên bảng có trigger -> tắt implicit_returning, SQLAlchemy dùng SCOPE_IDENTITY().
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nguoi_dung_id: Mapped[int] = mapped_column(ForeignKey("nguoi_dung.id"))
    tieu_de: Mapped[str] = mapped_column(
        Unicode(255), server_default=text("N'Cuộc trò chuyện mới'")
    )
    kenh: Mapped[str] = mapped_column(
        Enum("web", "zalo", name="kenh"), server_default=text("N'web'")
    )
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        server_default=text("SYSDATETIME()"),
        server_onupdate=FetchedValue(),  # trigger AFTER UPDATE trong script SQL
    )

    tin_nhan: Mapped[list["TinNhan"]] = relationship(
        back_populates="hoi_thoai",
        order_by="TinNhan.created_at",
        passive_deletes=True,  # CSDL tự ON DELETE CASCADE
    )


class TinNhan(AssistantBase):
    """vai_tro 'tool' lưu kết quả công cụ để dựng lại ngữ cảnh cho LLM."""

    __tablename__ = "tin_nhan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hoi_thoai_id: Mapped[int] = mapped_column(ForeignKey("hoi_thoai.id", ondelete="CASCADE"))
    vai_tro: Mapped[str] = mapped_column(Enum("user", "assistant", "tool", name="vai_tro_tn"))
    noi_dung: Mapped[str] = mapped_column(UnicodeText)
    tool_call_id: Mapped[str | None] = mapped_column(Unicode(100))
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    trich_dan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    so_token_vao: Mapped[int | None] = mapped_column(Integer)
    so_token_ra: Mapped[int | None] = mapped_column(Integer)
    thoi_gian_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(precision=3), server_default=text("SYSDATETIME()")
    )

    hoi_thoai: Mapped[HoiThoai] = relationship(back_populates="tin_nhan")


class DanhGiaCauTraLoi(AssistantBase):
    __tablename__ = "danh_gia_cau_tra_loi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tin_nhan_id: Mapped[int] = mapped_column(ForeignKey("tin_nhan.id", ondelete="CASCADE"))
    nguoi_dung_id: Mapped[int] = mapped_column(ForeignKey("nguoi_dung.id"))
    # 1 = hữu ích, -1 = chưa đúng (TINYINT của SQL Server không có số âm)
    diem: Mapped[int] = mapped_column(SmallInteger)
    gop_y: Mapped[str | None] = mapped_column(UnicodeText)
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))
