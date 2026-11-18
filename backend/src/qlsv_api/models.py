"""Model ORM cho CSDL `tlhv_qlsv` (SQL Server) — ánh xạ CHÍNH XÁC database/01_qlsv_schema.sql.

Lưu ý: bảng do script SQL tạo; KHÔNG gọi `QlsvBase.metadata.create_all()`.
Cột DATETIME2 lưu giờ Việt Nam dạng naive -> dùng src.shared.time.to_db/from_db.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Time,
    Unicode,
    UnicodeText,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class QlsvBase(DeclarativeBase):
    pass


class Nganh(QlsvBase):
    __tablename__ = "nganh"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_nganh: Mapped[str] = mapped_column(Unicode(20), unique=True)
    ten_nganh: Mapped[str] = mapped_column(Unicode(255))


class KhoaHoc(QlsvBase):
    __tablename__ = "khoa_hoc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_khoa: Mapped[str] = mapped_column(Unicode(10), unique=True)
    nam_bat_dau: Mapped[int] = mapped_column(SmallInteger)


class ChuongTrinh(QlsvBase):
    __tablename__ = "chuong_trinh"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nganh_id: Mapped[int] = mapped_column(ForeignKey("nganh.id"))
    khoa_hoc_id: Mapped[int] = mapped_column(ForeignKey("khoa_hoc.id"))
    tong_tin_chi: Mapped[int] = mapped_column(SmallInteger)
    gpa_toi_thieu: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("2.00"))
    yeu_cau_ngoai_ngu: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    nganh: Mapped[Nganh] = relationship()
    khoa_hoc: Mapped[KhoaHoc] = relationship()


class SinhVien(QlsvBase):
    __tablename__ = "sinh_vien"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_sv: Mapped[str] = mapped_column(Unicode(20), unique=True)
    ho_ten: Mapped[str] = mapped_column(Unicode(100))
    email: Mapped[str] = mapped_column(Unicode(255), unique=True)
    ngay_sinh: Mapped[date] = mapped_column(Date)
    gioi_tinh: Mapped[str] = mapped_column(Enum("nam", "nu", "khac", name="gioi_tinh"))
    nganh_id: Mapped[int] = mapped_column(ForeignKey("nganh.id"))
    khoa_hoc_id: Mapped[int] = mapped_column(ForeignKey("khoa_hoc.id"))
    lop: Mapped[str] = mapped_column(Unicode(20))
    trang_thai: Mapped[str] = mapped_column(
        Enum("dang_hoc", "bao_luu", "thoi_hoc", "tot_nghiep", name="trang_thai_sv"),
        server_default=text("N'dang_hoc'"),
    )
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))

    nganh: Mapped[Nganh] = relationship()
    khoa_hoc: Mapped[KhoaHoc] = relationship()


class HocPhan(QlsvBase):
    __tablename__ = "hoc_phan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_hp: Mapped[str] = mapped_column(Unicode(20), unique=True)
    ten_hp: Mapped[str] = mapped_column(Unicode(255))
    so_tin_chi: Mapped[int] = mapped_column(TINYINT)
    mo_ta: Mapped[str | None] = mapped_column(UnicodeText)


class HocPhanTienQuyet(QlsvBase):
    """hoc_phan_id yêu cầu đã học đạt tien_quyet_id."""

    __tablename__ = "hoc_phan_tien_quyet"

    hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("hoc_phan.id"), primary_key=True)
    tien_quyet_id: Mapped[int] = mapped_column(ForeignKey("hoc_phan.id"), primary_key=True)


class ChuongTrinhHocPhan(QlsvBase):
    __tablename__ = "chuong_trinh_hoc_phan"

    chuong_trinh_id: Mapped[int] = mapped_column(ForeignKey("chuong_trinh.id"), primary_key=True)
    hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("hoc_phan.id"), primary_key=True)
    hoc_ky_goi_y: Mapped[int] = mapped_column(TINYINT)
    bat_buoc: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    hoc_phan: Mapped[HocPhan] = relationship()


class HocKy(QlsvBase):
    __tablename__ = "hoc_ky"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_hoc_ky: Mapped[str] = mapped_column(Unicode(20), unique=True)
    ten: Mapped[str] = mapped_column(Unicode(100))
    ngay_bat_dau: Mapped[date] = mapped_column(Date)
    ngay_ket_thuc: Mapped[date] = mapped_column(Date)
    dang_ky_tu: Mapped[datetime | None] = mapped_column(DATETIME2)  # NULL = không mở đăng ký
    dang_ky_den: Mapped[datetime | None] = mapped_column(DATETIME2)
    tin_chi_toi_da: Mapped[int] = mapped_column(TINYINT, server_default=text("25"))
    tin_chi_toi_da_canh_bao: Mapped[int] = mapped_column(TINYINT, server_default=text("14"))


class LopHocPhan(QlsvBase):
    __tablename__ = "lop_hoc_phan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_lop: Mapped[str] = mapped_column(Unicode(30), unique=True)
    hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("hoc_phan.id"))
    hoc_ky_id: Mapped[int] = mapped_column(ForeignKey("hoc_ky.id"))
    giang_vien: Mapped[str] = mapped_column(Unicode(100))
    si_so_toi_da: Mapped[int] = mapped_column(SmallInteger)
    thu: Mapped[int] = mapped_column(TINYINT)  # 2..7 = Thứ 2..Thứ 7, 8 = Chủ nhật
    tiet_bat_dau: Mapped[int] = mapped_column(TINYINT)
    tiet_ket_thuc: Mapped[int] = mapped_column(TINYINT)
    phong: Mapped[str] = mapped_column(Unicode(20))

    hoc_phan: Mapped[HocPhan] = relationship()
    hoc_ky: Mapped[HocKy] = relationship()


class DangKyHocPhan(QlsvBase):
    __tablename__ = "dang_ky_hoc_phan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sinh_vien_id: Mapped[int] = mapped_column(ForeignKey("sinh_vien.id"))
    lop_hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("lop_hoc_phan.id"))
    trang_thai: Mapped[str] = mapped_column(
        Enum("da_dang_ky", "da_huy", name="trang_thai_dk"),
        server_default=text("N'da_dang_ky'"),
    )
    thoi_gian_dang_ky: Mapped[datetime] = mapped_column(
        DATETIME2, server_default=text("SYSDATETIME()")
    )
    thoi_gian_huy: Mapped[datetime | None] = mapped_column(DATETIME2)

    lop_hoc_phan: Mapped[LopHocPhan] = relationship()


class KetQuaHocTap(QlsvBase):
    """Điểm tổng kết = 0.4 * quá trình + 0.6 * thi."""

    __tablename__ = "ket_qua_hoc_tap"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sinh_vien_id: Mapped[int] = mapped_column(ForeignKey("sinh_vien.id"))
    hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("hoc_phan.id"))
    hoc_ky_id: Mapped[int] = mapped_column(ForeignKey("hoc_ky.id"))
    diem_qua_trinh: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    diem_thi: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    diem_tong_ket: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    diem_chu: Mapped[str] = mapped_column(Unicode(2))  # A, B+, B, C+, C, D+, D, F
    diem_he_4: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    lan_hoc: Mapped[int] = mapped_column(TINYINT, server_default=text("1"))

    hoc_phan: Mapped[HocPhan] = relationship()
    hoc_ky: Mapped[HocKy] = relationship()


class LichThi(QlsvBase):
    __tablename__ = "lich_thi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lop_hoc_phan_id: Mapped[int] = mapped_column(ForeignKey("lop_hoc_phan.id"))
    ngay_thi: Mapped[date] = mapped_column(Date)
    gio_bat_dau: Mapped[time] = mapped_column(Time)
    phong: Mapped[str] = mapped_column(Unicode(20))
    hinh_thuc: Mapped[str] = mapped_column(
        Enum("tu_luan", "trac_nghiem", "van_dap", "do_an", name="hinh_thuc_thi")
    )

    lop_hoc_phan: Mapped[LopHocPhan] = relationship()


class HocPhi(QlsvBase):
    __tablename__ = "hoc_phi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sinh_vien_id: Mapped[int] = mapped_column(ForeignKey("sinh_vien.id"))
    hoc_ky_id: Mapped[int] = mapped_column(ForeignKey("hoc_ky.id"))
    so_tien_phai_nop: Mapped[Decimal] = mapped_column(Numeric(12, 0))
    so_tien_da_nop: Mapped[Decimal] = mapped_column(Numeric(12, 0), server_default=text("0"))
    han_nop: Mapped[date] = mapped_column(Date)
    trang_thai: Mapped[str] = mapped_column(
        Enum("chua_nop", "nop_mot_phan", "da_nop", name="trang_thai_hoc_phi"),
        server_default=text("N'chua_nop'"),
    )

    hoc_ky: Mapped[HocKy] = relationship()


class ChungChi(QlsvBase):
    __tablename__ = "chung_chi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sinh_vien_id: Mapped[int] = mapped_column(ForeignKey("sinh_vien.id"))
    loai: Mapped[str] = mapped_column(
        Enum("ngoai_ngu", "tin_hoc", "gdtc", "gdqp", name="loai_chung_chi")
    )
    ten: Mapped[str] = mapped_column(Unicode(255))
    ngay_cap: Mapped[date] = mapped_column(Date)
    trang_thai_duyet: Mapped[str] = mapped_column(
        Enum("cho_duyet", "da_duyet", "tu_choi", name="trang_thai_duyet"),
        server_default=text("N'cho_duyet'"),
    )


class DonTu(QlsvBase):
    """Đơn từ sinh viên gửi (qua cổng hoặc qua trợ lý AI). ma_don dạng DT-2026-0001."""

    __tablename__ = "don_tu"
    # Bảng có TRIGGER: SQL Server cấm "INSERT ... OUTPUT" (cách SQLAlchemy lấy id mới)
    # trên bảng có trigger -> tắt implicit_returning, SQLAlchemy dùng SCOPE_IDENTITY().
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_don: Mapped[str] = mapped_column(Unicode(30), unique=True)
    sinh_vien_id: Mapped[int] = mapped_column(ForeignKey("sinh_vien.id"))
    loai_don: Mapped[str] = mapped_column(
        Enum("giay_xac_nhan_sv", "bao_luu", "phuc_khao", name="loai_don")
    )
    noi_dung: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    trang_thai: Mapped[str] = mapped_column(
        Enum("moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat", name="trang_thai_don"),
        server_default=text("N'moi_tao'"),
    )
    ghi_chu_xu_ly: Mapped[str | None] = mapped_column(UnicodeText)
    tao_boi: Mapped[str] = mapped_column(
        Enum("sinh_vien", "tro_ly_ai", name="tao_boi"), server_default=text("N'sinh_vien'")
    )
    created_at: Mapped[datetime] = mapped_column(DATETIME2, server_default=text("SYSDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        server_default=text("SYSDATETIME()"),
        server_onupdate=FetchedValue(),  # trigger AFTER UPDATE trong script SQL
    )
