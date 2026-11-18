from sqlalchemy import select
from sqlalchemy.orm import Session

from src.qlsv_api.models import HocKy


def list_all(db: Session) -> list[HocKy]:
    return list(db.scalars(select(HocKy).order_by(HocKy.ngay_bat_dau)))


def get_by_ma(db: Session, ma_hoc_ky: str) -> HocKy | None:
    return db.scalar(select(HocKy).where(HocKy.ma_hoc_ky == ma_hoc_ky))
