from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import DangKyHocPhan, HocPhan, HocPhanTienQuyet, LopHocPhan
from src.shared.locking import lock_for_update


def get_by_ma_lop(db: Session, ma_lop: str) -> LopHocPhan | None:
    return db.scalar(
        select(LopHocPhan)
        .options(joinedload(LopHocPhan.hoc_phan), joinedload(LopHocPhan.hoc_ky))
        .where(LopHocPhan.ma_lop == ma_lop)
    )


def lock_by_ma_lop(db: Session, ma_lop: str) -> LopHocPhan | None:
    """Đọc và KHÓA hàng lớp học phần đến hết transaction.

    Hai sinh viên cùng giành chỗ cuối: transaction thứ hai phải chờ transaction đầu
    commit/rollback rồi mới đếm sĩ số -> không bao giờ vượt si_so_toi_da.
    """
    lop = db.scalar(
        lock_for_update(select(LopHocPhan).where(LopHocPhan.ma_lop == ma_lop), LopHocPhan)
    )
    if lop is not None:
        # nạp quan hệ sau khi đã khóa (câu khóa chỉ chạm bảng lop_hoc_phan)
        _ = lop.hoc_phan, lop.hoc_ky
    return lop


def search(db: Session, hoc_ky_id: int, keyword: str | None, limit: int) -> list[LopHocPhan]:
    stmt = (
        select(LopHocPhan)
        .join(HocPhan, LopHocPhan.hoc_phan_id == HocPhan.id)
        .options(joinedload(LopHocPhan.hoc_phan), joinedload(LopHocPhan.hoc_ky))
        .where(LopHocPhan.hoc_ky_id == hoc_ky_id)
        .order_by(LopHocPhan.ma_lop)
        .limit(limit)  # SQLAlchemy tự sinh TOP / OFFSET FETCH cho SQL Server
    )
    if keyword and keyword.strip():
        kw = keyword.strip()
        stmt = stmt.where(
            or_(
                LopHocPhan.ma_lop.contains(kw, autoescape=True),
                HocPhan.ma_hp.contains(kw, autoescape=True),
                HocPhan.ten_hp.contains(kw, autoescape=True),
                LopHocPhan.giang_vien.contains(kw, autoescape=True),
            )
        )
    return list(db.scalars(stmt))


def count_registered(db: Session, lop_ids: Iterable[int]) -> dict[int, int]:
    """Số sinh viên đang đăng ký (trang_thai = 'da_dang_ky') theo từng lớp."""
    ids = list(lop_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(DangKyHocPhan.lop_hoc_phan_id, func.count())
        .where(DangKyHocPhan.lop_hoc_phan_id.in_(ids), DangKyHocPhan.trang_thai == "da_dang_ky")
        .group_by(DangKyHocPhan.lop_hoc_phan_id)
    ).all()
    counts = {lop_id: 0 for lop_id in ids}
    counts.update({lop_id: n for lop_id, n in rows})
    return counts


def list_prerequisites(db: Session, hoc_phan_id: int) -> list[HocPhan]:
    return list(
        db.scalars(
            select(HocPhan)
            .join(HocPhanTienQuyet, HocPhanTienQuyet.tien_quyet_id == HocPhan.id)
            .where(HocPhanTienQuyet.hoc_phan_id == hoc_phan_id)
            .order_by(HocPhan.ma_hp)
        )
    )


def list_in_semester(db: Session, hoc_ky_id: int, hoc_phan_ids: Iterable[int]) -> list[LopHocPhan]:
    """Các lớp của những học phần cho trước trong một học kỳ, sắp theo mã lớp."""
    ids = list(hoc_phan_ids)
    if not ids:
        return []
    return list(
        db.scalars(
            select(LopHocPhan)
            .options(joinedload(LopHocPhan.hoc_phan), joinedload(LopHocPhan.hoc_ky))
            .where(LopHocPhan.hoc_ky_id == hoc_ky_id, LopHocPhan.hoc_phan_id.in_(ids))
            .order_by(LopHocPhan.ma_lop)
        )
    )
