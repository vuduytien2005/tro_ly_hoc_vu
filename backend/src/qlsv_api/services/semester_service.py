"""Xác định học kỳ hiện tại / đang mở đăng ký / đã kết thúc gần nhất theo `now`."""

from datetime import datetime

from sqlalchemy.orm import Session

from src.qlsv_api.errors import not_found
from src.qlsv_api.models import HocKy
from src.qlsv_api.repositories import semesters as semester_repo
from src.qlsv_api.schemas import CurrentSemestersOut, SemesterOut
from src.shared.time import from_db


def current_semester(db: Session, now: datetime) -> HocKy:
    """Học kỳ chứa ngày hôm nay; nếu đang giữa 2 học kỳ thì lấy học kỳ bắt đầu gần nhất."""
    today = now.date()
    semesters = semester_repo.list_all(db)  # sắp theo ngay_bat_dau tăng dần
    if not semesters:
        raise not_found("HOC_KY_KHONG_TON_TAI", "Hệ thống chưa có dữ liệu học kỳ.")
    for hk in semesters:
        if hk.ngay_bat_dau <= today <= hk.ngay_ket_thuc:
            return hk
    started = [hk for hk in semesters if hk.ngay_bat_dau <= today]
    return started[-1] if started else semesters[0]


def is_registration_open(hk: HocKy, now: datetime) -> bool:
    start, end = from_db(hk.dang_ky_tu), from_db(hk.dang_ky_den)
    return start is not None and end is not None and start <= now <= end


def open_registration_semester(db: Session, now: datetime) -> HocKy | None:
    for hk in semester_repo.list_all(db):
        if is_registration_open(hk, now):
            return hk
    return None


def latest_finished_semester(db: Session, now: datetime) -> HocKy | None:
    """Học kỳ đã kết thúc gần nhất (dùng cho quy tắc phúc khảo)."""
    finished = [hk for hk in semester_repo.list_all(db) if hk.ngay_ket_thuc < now.date()]
    return max(finished, key=lambda hk: hk.ngay_ket_thuc) if finished else None


def get_by_ma_or_404(db: Session, ma_hoc_ky: str) -> HocKy:
    hk = semester_repo.get_by_ma(db, ma_hoc_ky)
    if hk is None:
        raise not_found("HOC_KY_KHONG_TON_TAI", f"Không tìm thấy học kỳ {ma_hoc_ky}.")
    return hk


def to_schema(hk: HocKy) -> SemesterOut:
    return SemesterOut(
        ma_hoc_ky=hk.ma_hoc_ky,
        ten=hk.ten,
        ngay_bat_dau=hk.ngay_bat_dau,
        ngay_ket_thuc=hk.ngay_ket_thuc,
        dang_ky_tu=from_db(hk.dang_ky_tu),
        dang_ky_den=from_db(hk.dang_ky_den),
        tin_chi_toi_da=hk.tin_chi_toi_da,
    )


def get_current_semesters(db: Session, now: datetime) -> CurrentSemestersOut:
    open_hk = open_registration_semester(db, now)
    return CurrentSemestersOut(
        hien_tai=to_schema(current_semester(db, now)),
        dang_mo_dang_ky=to_schema(open_hk) if open_hk else None,
    )
