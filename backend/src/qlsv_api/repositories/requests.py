from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.qlsv_api.models import DonTu
from src.qlsv_api.repositories.locking import lock_range_for_update


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
