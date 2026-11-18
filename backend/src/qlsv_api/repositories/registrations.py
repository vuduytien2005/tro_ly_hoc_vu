from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import DangKyHocPhan, LichThi, LopHocPhan


def list_active_in_semester(db: Session, sinh_vien_id: int, hoc_ky_id: int) -> list[DangKyHocPhan]:
    """Các lớp sinh viên đang đăng ký (chưa hủy) trong một học kỳ."""
    return list(
        db.scalars(
            select(DangKyHocPhan)
            .join(LopHocPhan, DangKyHocPhan.lop_hoc_phan_id == LopHocPhan.id)
            .options(
                joinedload(DangKyHocPhan.lop_hoc_phan).joinedload(LopHocPhan.hoc_phan),
            )
            .where(
                DangKyHocPhan.sinh_vien_id == sinh_vien_id,
                DangKyHocPhan.trang_thai == "da_dang_ky",
                LopHocPhan.hoc_ky_id == hoc_ky_id,
            )
            .order_by(LopHocPhan.thu, LopHocPhan.tiet_bat_dau)
        )
    )


def get(db: Session, sinh_vien_id: int, lop_hoc_phan_id: int) -> DangKyHocPhan | None:
    """Bản ghi đăng ký (kể cả đã hủy) — ràng buộc UNIQUE (sinh_vien_id, lop_hoc_phan_id)."""
    return db.scalar(
        select(DangKyHocPhan).where(
            DangKyHocPhan.sinh_vien_id == sinh_vien_id,
            DangKyHocPhan.lop_hoc_phan_id == lop_hoc_phan_id,
        )
    )


def list_exams_in_semester(db: Session, sinh_vien_id: int, hoc_ky_id: int) -> list[LichThi]:
    return list(
        db.scalars(
            select(LichThi)
            .join(LopHocPhan, LichThi.lop_hoc_phan_id == LopHocPhan.id)
            .join(DangKyHocPhan, DangKyHocPhan.lop_hoc_phan_id == LopHocPhan.id)
            .options(joinedload(LichThi.lop_hoc_phan).joinedload(LopHocPhan.hoc_phan))
            .where(
                DangKyHocPhan.sinh_vien_id == sinh_vien_id,
                DangKyHocPhan.trang_thai == "da_dang_ky",
                LopHocPhan.hoc_ky_id == hoc_ky_id,
            )
            .order_by(LichThi.ngay_thi, LichThi.gio_bat_dau)
        )
    )
