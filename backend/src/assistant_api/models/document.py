"""Văn bản quy chế cho RAG. Vector nằm trong ChromaDB (id = doan_van_ban.vector_id)."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    SmallInteger,
    Unicode,
    UnicodeText,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.assistant_api.models.base import AssistantBase


class VanBan(AssistantBase):
    """ap_dung_tu_khoa..ap_dung_den_khoa: số năm 2 chữ số (21..99 = từ K21 trở đi).
    NULL = áp dụng cho mọi khóa."""

    __tablename__ = "van_ban"
    # Bảng có TRIGGER -> tắt implicit_returning (xem HoiThoai)
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ten: Mapped[str] = mapped_column(Unicode(255))
    loai: Mapped[str] = mapped_column(
        Enum("quy_che", "so_tay", "quy_dinh", "huong_dan", "thong_bao", name="loai_van_ban")
    )
    phien_ban: Mapped[str] = mapped_column(Unicode(50))
    ap_dung_tu_khoa: Mapped[int | None] = mapped_column(TINYINT)
    ap_dung_den_khoa: Mapped[int | None] = mapped_column(TINYINT)
    ngay_hieu_luc: Mapped[date | None] = mapped_column(Date)
    ten_tep: Mapped[str] = mapped_column(Unicode(255))
    duong_dan_tep: Mapped[str] = mapped_column(Unicode(500))
    trang_thai: Mapped[str] = mapped_column(
        Enum("dang_xu_ly", "da_lap_chi_muc", "loi", name="trang_thai_vb"),
        server_default=text("N'dang_xu_ly'"),
    )
    chien_luoc_chunk: Mapped[str] = mapped_column(
        Enum("theo_dieu", "co_dinh", "ngu_nghia", name="chien_luoc_chunk"),
        server_default=text("N'theo_dieu'"),
    )
    so_doan: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    loi: Mapped[str | None] = mapped_column(UnicodeText)
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        server_default=text("SYSDATETIME()"),
        server_onupdate=FetchedValue(),  # trigger AFTER UPDATE trong script SQL
    )

    doan: Mapped[list["DoanVanBan"]] = relationship(
        back_populates="van_ban", order_by="DoanVanBan.thu_tu", passive_deletes=True
    )


class DoanVanBan(AssistantBase):
    """Một đoạn (chunk). Tìm theo từ khóa dùng BM25 trong Python (src/rag), không dùng
    Full-Text Search của SQL Server."""

    __tablename__ = "doan_van_ban"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    van_ban_id: Mapped[int] = mapped_column(ForeignKey("van_ban.id", ondelete="CASCADE"))
    thu_tu: Mapped[int] = mapped_column(Integer)
    chuong: Mapped[str | None] = mapped_column(Unicode(255))
    dieu: Mapped[str | None] = mapped_column(Unicode(255))  # vd: "Điều 12. Đăng ký học phần"
    khoan: Mapped[str | None] = mapped_column(Unicode(50))
    trang: Mapped[int | None] = mapped_column(SmallInteger)
    noi_dung: Mapped[str] = mapped_column(UnicodeText)
    so_token: Mapped[int | None] = mapped_column(Integer)
    vector_id: Mapped[str] = mapped_column(Unicode(64), unique=True)  # vb{van_ban_id}_d{thu_tu}

    van_ban: Mapped[VanBan] = relationship(back_populates="doan")
