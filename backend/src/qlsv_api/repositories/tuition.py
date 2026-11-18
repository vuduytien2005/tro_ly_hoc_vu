from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import HocPhi


def get_for_semester(db: Session, sinh_vien_id: int, hoc_ky_id: int) -> HocPhi | None:
    return db.scalar(
        select(HocPhi)
        .options(joinedload(HocPhi.hoc_ky))
        .where(HocPhi.sinh_vien_id == sinh_vien_id, HocPhi.hoc_ky_id == hoc_ky_id)
    )
