from datetime import datetime

from sqlalchemy import (
    Boolean,
    Enum,
    Integer,
    Unicode,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from src.assistant_api.models.base import AssistantBase


class NguoiDung(AssistantBase):
    __tablename__ = "nguoi_dung"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Unicode(255), unique=True)
    mat_khau_hash: Mapped[str] = mapped_column(Unicode(255))
    ho_ten: Mapped[str] = mapped_column(Unicode(100))
    vai_tro: Mapped[str] = mapped_column(Enum("sinh_vien", "admin", name="vai_tro_nd"))
    # Liên kết sang tlhv_qlsv.sinh_vien.ma_sv (chỉ với sinh viên).
    # Duy nhất khi khác NULL: chỉ mục có lọc uq_nd_ma_sv trong script SQL.
    ma_sv: Mapped[str | None] = mapped_column(Unicode(20))
    # K22... dùng để lọc phiên bản quy chế
    ma_khoa: Mapped[str | None] = mapped_column(Unicode(10))
    dang_hoat_dong: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))
