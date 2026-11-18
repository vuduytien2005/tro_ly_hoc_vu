"""Thời khóa biểu, lịch thi, học phí, tra cứu lớp học phần."""

from datetime import datetime

from sqlalchemy.orm import Session

from src.qlsv_api.errors import not_found
from src.qlsv_api.models import HocKy
from src.qlsv_api.repositories import registrations as registration_repo
from src.qlsv_api.repositories import sections as section_repo
from src.qlsv_api.repositories import tuition as tuition_repo
from src.qlsv_api.schemas import (
    ExamRow,
    ExamScheduleOut,
    ScheduleOut,
    ScheduleRow,
    SectionOut,
    TuitionOut,
)
from src.qlsv_api.services import semester_service
from src.qlsv_api.services.common import get_student_or_404, schedule_label

MAX_SECTIONS = 50


def _semester_or_current(db: Session, ma_hoc_ky: str | None, now: datetime) -> HocKy:
    if ma_hoc_ky:
        return semester_service.get_by_ma_or_404(db, ma_hoc_ky)
    return semester_service.current_semester(db, now)


def get_schedule(db: Session, ma_sv: str, ma_hoc_ky: str | None, now: datetime) -> ScheduleOut:
    sv = get_student_or_404(db, ma_sv)
    hk = _semester_or_current(db, ma_hoc_ky, now)
    rows = [
        ScheduleRow(
            ma_lop=r.lop_hoc_phan.ma_lop,
            ma_hp=r.lop_hoc_phan.hoc_phan.ma_hp,
            ten_hp=r.lop_hoc_phan.hoc_phan.ten_hp,
            tin_chi=r.lop_hoc_phan.hoc_phan.so_tin_chi,
            thu=r.lop_hoc_phan.thu,
            tiet_bat_dau=r.lop_hoc_phan.tiet_bat_dau,
            tiet_ket_thuc=r.lop_hoc_phan.tiet_ket_thuc,
            lich=schedule_label(r.lop_hoc_phan),
            phong=r.lop_hoc_phan.phong,
            giang_vien=r.lop_hoc_phan.giang_vien,
        )
        for r in registration_repo.list_active_in_semester(db, sv.id, hk.id)
    ]
    return ScheduleOut(
        ma_sv=sv.ma_sv,
        ma_hoc_ky=hk.ma_hoc_ky,
        lop=rows,
        tong_tin_chi=sum(r.tin_chi for r in rows),
    )


def get_exam_schedule(
    db: Session, ma_sv: str, ma_hoc_ky: str | None, now: datetime
) -> ExamScheduleOut:
    sv = get_student_or_404(db, ma_sv)
    hk = _semester_or_current(db, ma_hoc_ky, now)
    exams = registration_repo.list_exams_in_semester(db, sv.id, hk.id)
    return ExamScheduleOut(
        ma_sv=sv.ma_sv,
        ma_hoc_ky=hk.ma_hoc_ky,
        lich_thi=[
            ExamRow(
                ma_lop=e.lop_hoc_phan.ma_lop,
                ma_hp=e.lop_hoc_phan.hoc_phan.ma_hp,
                ten_hp=e.lop_hoc_phan.hoc_phan.ten_hp,
                ngay_thi=e.ngay_thi,
                gio_bat_dau=e.gio_bat_dau,
                phong=e.phong,
                hinh_thuc=e.hinh_thuc,
            )
            for e in exams
        ],
    )


def get_tuition(db: Session, ma_sv: str, ma_hoc_ky: str | None, now: datetime) -> TuitionOut:
    sv = get_student_or_404(db, ma_sv)
    hk = _semester_or_current(db, ma_hoc_ky, now)
    fee = tuition_repo.get_for_semester(db, sv.id, hk.id)
    if fee is None:
        raise not_found(
            "HOC_PHI_KHONG_TON_TAI", f"Chưa có thông tin học phí học kỳ {hk.ten} của em."
        )
    return TuitionOut(
        ma_sv=sv.ma_sv,
        ma_hoc_ky=hk.ma_hoc_ky,
        phai_nop=int(fee.so_tien_phai_nop),
        da_nop=int(fee.so_tien_da_nop),
        con_no=int(max(fee.so_tien_phai_nop - fee.so_tien_da_nop, 0)),
        han_nop=fee.han_nop,
        trang_thai=fee.trang_thai,
    )


def search_sections(
    db: Session,
    keyword: str | None,
    ma_hoc_ky: str | None,
    now: datetime,
    limit: int = MAX_SECTIONS,
) -> list[SectionOut]:
    """Lớp học phần (mặc định: học kỳ đang mở đăng ký), kèm số chỗ còn trống."""
    if ma_hoc_ky:
        hk: HocKy | None = semester_service.get_by_ma_or_404(db, ma_hoc_ky)
    else:
        hk = semester_service.open_registration_semester(db, now)
    if hk is None:
        return []
    sections = section_repo.search(db, hk.id, keyword, min(limit, MAX_SECTIONS))
    counts = section_repo.count_registered(db, (s.id for s in sections))
    return [
        SectionOut(
            ma_lop=s.ma_lop,
            ma_hp=s.hoc_phan.ma_hp,
            ten_hp=s.hoc_phan.ten_hp,
            tin_chi=s.hoc_phan.so_tin_chi,
            hoc_ky=s.hoc_ky.ma_hoc_ky,
            giang_vien=s.giang_vien,
            thu=s.thu,
            tiet_bat_dau=s.tiet_bat_dau,
            tiet_ket_thuc=s.tiet_ket_thuc,
            phong=s.phong,
            lich=schedule_label(s),
            si_so_toi_da=s.si_so_toi_da,
            da_dang_ky=counts[s.id],
            con_trong=max(s.si_so_toi_da - counts[s.id], 0),
        )
        for s in sections
    ]
