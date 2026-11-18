from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import ChungChi, ChuongTrinh, ChuongTrinhHocPhan, SinhVien
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
