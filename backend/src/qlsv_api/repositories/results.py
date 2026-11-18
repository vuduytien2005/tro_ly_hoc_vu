from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.qlsv_api.models import HocKy, HocPhan, KetQuaHocTap


def list_for_student(
    db: Session, sinh_vien_id: int, hoc_ky_id: int | None = None
) -> list[KetQuaHocTap]:
    """Mọi lần học của sinh viên (tuỳ chọn lọc theo học kỳ), sắp theo thời gian."""
    stmt = (
        select(KetQuaHocTap)
        .join(HocKy, KetQuaHocTap.hoc_ky_id == HocKy.id)
        .join(HocPhan, KetQuaHocTap.hoc_phan_id == HocPhan.id)
        .options(joinedload(KetQuaHocTap.hoc_phan), joinedload(KetQuaHocTap.hoc_ky))
        .where(KetQuaHocTap.sinh_vien_id == sinh_vien_id)
        .order_by(HocKy.ngay_bat_dau, HocPhan.ma_hp, KetQuaHocTap.lan_hoc)
    )
    if hoc_ky_id is not None:
        stmt = stmt.where(KetQuaHocTap.hoc_ky_id == hoc_ky_id)
    return list(db.scalars(stmt))
