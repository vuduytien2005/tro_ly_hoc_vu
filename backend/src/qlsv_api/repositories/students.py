from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import (
    ChungChi,
    ChuongTrinh,
    ChuongTrinhHocPhan,
    KhoaHoc,
    Nganh,
    SinhVien,
)
from src.shared.locking import lock_for_update


def get_by_ma_sv(db: Session, ma_sv: str) -> SinhVien | None:
    return db.scalar(
        select(SinhVien)
        .options(joinedload(SinhVien.nganh), joinedload(SinhVien.khoa_hoc))
        .where(SinhVien.ma_sv == ma_sv)
    )


def lock_by_ma_sv(db: Session, ma_sv: str) -> SinhVien | None:
    """Đọc và KHÓA hàng sinh viên đến hết transaction (chống 1 SV gửi 2 yêu cầu song song)."""
    return db.scalar(lock_for_update(select(SinhVien).where(SinhVien.ma_sv == ma_sv), SinhVien))


def get_program(db: Session, nganh_id: int, khoa_hoc_id: int) -> ChuongTrinh | None:
    return db.scalar(
        select(ChuongTrinh).where(
            ChuongTrinh.nganh_id == nganh_id, ChuongTrinh.khoa_hoc_id == khoa_hoc_id
        )
    )


def list_program_courses(db: Session, chuong_trinh_id: int) -> list[ChuongTrinhHocPhan]:
    return list(
        db.scalars(
            select(ChuongTrinhHocPhan)
            .options(joinedload(ChuongTrinhHocPhan.hoc_phan))
            .where(ChuongTrinhHocPhan.chuong_trinh_id == chuong_trinh_id)
            .order_by(ChuongTrinhHocPhan.hoc_ky_goi_y, ChuongTrinhHocPhan.hoc_phan_id)
        )
    )


def list_certificates(db: Session, sinh_vien_id: int) -> list[ChungChi]:
    return list(db.scalars(select(ChungChi).where(ChungChi.sinh_vien_id == sinh_vien_id)))


# ----- Quản lý hồ sơ (AD-10) -----
def _search(q: str | None, trang_thai: str | None) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if q:
        conditions.append(
            or_(
                SinhVien.ma_sv.contains(q, autoescape=True),
                SinhVien.ho_ten.contains(q, autoescape=True),
                SinhVien.email.contains(q, autoescape=True),
                SinhVien.lop.contains(q, autoescape=True),
            )
        )
    if trang_thai:
        conditions.append(SinhVien.trang_thai == trang_thai)
    return conditions


def count(db: Session, q: str | None, trang_thai: str | None) -> int:
    return db.scalar(select(func.count(SinhVien.id)).where(*_search(q, trang_thai))) or 0


def list_page(
    db: Session, q: str | None, trang_thai: str | None, offset: int, limit: int
) -> list[SinhVien]:
    return list(
        db.scalars(
            select(SinhVien)
            .options(joinedload(SinhVien.nganh), joinedload(SinhVien.khoa_hoc))
            .where(*_search(q, trang_thai))
            .order_by(SinhVien.ma_sv)
            .offset(offset)
            .limit(limit)
        )
    )


def email_owner(db: Session, email: str) -> str | None:
    """ma_sv đang dùng email này (so không phân biệt hoa thường), hoặc None."""
    return db.scalar(select(SinhVien.ma_sv).where(func.lower(SinhVien.email) == email.lower()))


def get_nganh(db: Session, ma_nganh: str) -> Nganh | None:
    return db.scalar(select(Nganh).where(Nganh.ma_nganh == ma_nganh))


def get_khoa_hoc(db: Session, ma_khoa: str) -> KhoaHoc | None:
    return db.scalar(select(KhoaHoc).where(KhoaHoc.ma_khoa == ma_khoa))


def list_programs(db: Session) -> list[ChuongTrinh]:
    return list(
        db.scalars(
            select(ChuongTrinh)
            .options(joinedload(ChuongTrinh.nganh), joinedload(ChuongTrinh.khoa_hoc))
            .join(Nganh, Nganh.id == ChuongTrinh.nganh_id)
            .join(KhoaHoc, KhoaHoc.id == ChuongTrinh.khoa_hoc_id)
            .order_by(Nganh.ma_nganh, KhoaHoc.ma_khoa)
        )
    )
