from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import DonTu
from src.shared.locking import lock_for_update, lock_range_for_update


def list_for_student(db: Session, sinh_vien_id: int, trang_thai: str | None) -> list[DonTu]:
    stmt = (
        select(DonTu)
        .where(DonTu.sinh_vien_id == sinh_vien_id)
        .order_by(DonTu.created_at.desc(), DonTu.id.desc())
    )
    if trang_thai:
        stmt = stmt.where(DonTu.trang_thai == trang_thai)
    return list(db.scalars(stmt))


def get_by_ma_don(db: Session, ma_don: str) -> DonTu | None:
    return db.scalar(select(DonTu).where(DonTu.ma_don == ma_don))


def get_by_ma_don_for_update(db: Session, ma_don: str) -> DonTu | None:
    """Đọc kèm khóa hàng: hai cán bộ cùng xử lý một đơn thì người sau thấy trạng thái mới."""
    return db.scalar(lock_for_update(select(DonTu).where(DonTu.ma_don == ma_don), DonTu))


def _filters(trang_thai: str | None, loai_don: str | None) -> list[Any]:
    conds: list[Any] = []
    if trang_thai:
        conds.append(DonTu.trang_thai == trang_thai)
    if loai_don:
        conds.append(DonTu.loai_don == loai_don)
    return conds


def count_all(db: Session, trang_thai: str | None, loai_don: str | None) -> int:
    stmt = select(func.count(DonTu.id)).where(*_filters(trang_thai, loai_don))
    return db.scalar(stmt) or 0


def list_all_page(
    db: Session, trang_thai: str | None, loai_don: str | None, offset: int, limit: int
) -> list[DonTu]:
    return list(
        db.scalars(
            select(DonTu)
            .options(joinedload(DonTu.sinh_vien))
            .where(*_filters(trang_thai, loai_don))
            .order_by(DonTu.created_at.desc(), DonTu.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )


def next_sequence(db: Session, year: int) -> int:
    """Số thứ tự kế tiếp cho mã đơn DT-{year}-NNNN.

    Khóa khoảng (UPDLOCK, HOLDLOCK) trên chỉ mục uq_don_ma: hai yêu cầu tạo đơn song song
    không thể cùng đọc ra một số thứ tự. Ràng buộc UNIQUE của ma_don là chốt chặn cuối.
    """
    prefix = f"DT-{year}-"
    stmt = lock_range_for_update(
        select(func.max(DonTu.ma_don))
        .select_from(DonTu)
        .where(DonTu.ma_don.startswith(prefix, autoescape=True)),
        DonTu,
    )
    last = db.scalar(stmt)
    return int(last.removeprefix(prefix)) + 1 if last else 1
