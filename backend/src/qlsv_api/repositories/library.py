from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import MuonSach, Sach
from src.shared.locking import lock_for_update

SEARCH_LIMIT = 10


def active_borrows(db: Session, sinh_vien_id: int) -> list[MuonSach]:
    return list(
        db.scalars(
            select(MuonSach)
            .options(joinedload(MuonSach.sach))
            .where(MuonSach.sinh_vien_id == sinh_vien_id, MuonSach.trang_thai == "dang_muon")
            .order_by(MuonSach.han_tra, MuonSach.id)
        )
    )


def get_borrow_for_update(db: Session, sinh_vien_id: int, muon_id: int) -> MuonSach | None:
    """Lượt mượn CỦA sinh viên này (khóa hàng); của người khác -> None như không tồn tại."""
    return db.scalar(
        lock_for_update(
            select(MuonSach).where(MuonSach.id == muon_id, MuonSach.sinh_vien_id == sinh_vien_id),
            MuonSach,
        )
    )


def search_books(db: Session, tu_khoa: str) -> list[Sach]:
    pattern = f"%{tu_khoa.strip().lower()}%"
    return list(
        db.scalars(
            select(Sach)
            .where(
                or_(func.lower(Sach.ten_sach).like(pattern), func.lower(Sach.tac_gia).like(pattern))
            )
            .order_by(Sach.ma_sach)
            .limit(SEARCH_LIMIT)
        )
    )
