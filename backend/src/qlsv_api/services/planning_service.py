"""Lập kế hoạch đăng ký cho học kỳ đang mở đăng ký (chỉ đọc, thuần, lặp lại được).

Thuật toán (docs/superpowers/specs/2026-11-20-ke-hoach-hoc-ky-design.md, mục 4.1):
1. Ứng viên = học phần trong chương trình chưa đạt.
2. Học phần đã đăng ký ở học kỳ đích: bỏ khỏi ứng viên, nhưng lớp của nó vẫn chiếm lịch + tín chỉ.
3. Loại theo học phần: đang học ở học kỳ hiện tại (DANG_HOC), thiếu tiên quyết
   (CHUA_DAT_TIEN_QUYET), không có lớp mở (KHONG_CO_LOP_MO).
4. Ưu tiên: học lại (từng bị F) -> bắt buộc -> học kỳ gợi ý nhỏ hơn -> mã học phần.
5. Tham lam: mỗi học phần chọn lớp đầu tiên (theo mã lớp) còn chỗ, không trùng lịch, không vượt
   tín chỉ tối đa (thấp hơn khi bị cảnh báo học vụ — cùng quy tắc với đăng ký). Không chọn được
   lớp nào -> KHONG_CON_LOP_PHU_HOP kèm lý do từng lớp.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.qlsv_api.errors import conflict, not_found
from src.qlsv_api.models import ChuongTrinhHocPhan, HocPhan, LopHocPhan
from src.qlsv_api.repositories import registrations as registration_repo
from src.qlsv_api.repositories import results as result_repo
from src.qlsv_api.repositories import sections as section_repo
from src.qlsv_api.repositories import students as student_repo
from src.qlsv_api.schemas import (
    ExcludedCourse,
    ExcludedSection,
    PlannedSection,
    SemesterPlanOut,
)
from src.qlsv_api.services import academic_service, semester_service
from src.qlsv_api.services.common import get_student_or_404, schedule_label
from src.qlsv_api.services.registration_service import overlaps


def _reason(course: ChuongTrinhHocPhan, retake: bool) -> str:
    if retake:
        return "Học lại (đã bị điểm F)"
    if course.bat_buoc:
        return f"Bắt buộc, học kỳ gợi ý {course.hoc_ky_goi_y}"
    return "Tự chọn"


def _excluded(
    hp: HocPhan, code: str, reason: str, lops: list[ExcludedSection] | None = None
) -> ExcludedCourse:
    return ExcludedCourse(
        ma_hp=hp.ma_hp, ten_hp=hp.ten_hp, ma_loi=code, ly_do=reason, lop=lops or []
    )


def plan_next_semester(db: Session, ma_sv: str, now: datetime) -> SemesterPlanOut:
    sv = get_student_or_404(db, ma_sv)
    target = semester_service.open_registration_semester(db, now)
    if target is None:
        raise conflict(
            "KHONG_CO_HOC_KY_MO_DANG_KY", "Hiện không có học kỳ nào đang mở đăng ký học phần."
        )
    program = student_repo.get_program(db, sv.nganh_id, sv.khoa_hoc_id)
    if program is None:
        raise not_found(
            "CHUONG_TRINH_KHONG_TON_TAI", "Chưa có chương trình đào tạo cho sinh viên này."
        )
    results = result_repo.list_for_student(db, sv.id)
    summary = academic_service.summarize(results)
    limit = target.tin_chi_toi_da_canh_bao if summary.canh_bao_hoc_vu else target.tin_chi_toi_da

    # Lớp đã đăng ký ở học kỳ đích: chiếm lịch + tín chỉ
    taken: list[LopHocPhan] = [
        r.lop_hoc_phan for r in registration_repo.list_active_in_semester(db, sv.id, target.id)
    ]
    registered_courses = {lop.hoc_phan_id for lop in taken}
    registered_credits = sum(lop.hoc_phan.so_tin_chi for lop in taken)

    # Đang học ở học kỳ hiện tại (khác học kỳ đích) mà chưa có điểm
    current = semester_service.current_semester(db, now)
    in_progress: dict[int, str] = {}
    if current.id != target.id:
        graded = {r.hoc_phan_id for r in results if r.hoc_ky_id == current.id}
        for r in registration_repo.list_active_in_semester(db, sv.id, current.id):
            if r.lop_hoc_phan.hoc_phan_id not in graded:
                in_progress[r.lop_hoc_phan.hoc_phan_id] = r.lop_hoc_phan.ma_lop

    candidates = [
        c
        for c in student_repo.list_program_courses(db, program.id)
        if c.hoc_phan_id not in summary.passed_course_ids
        and c.hoc_phan_id not in registered_courses
    ]
    candidates.sort(
        key=lambda c: (
            c.hoc_phan_id not in summary.failed_course_ids,
            not c.bat_buoc,
            c.hoc_ky_goi_y,
            c.hoc_phan.ma_hp,
        )
    )

    sections = section_repo.list_in_semester(db, target.id, [c.hoc_phan_id for c in candidates])
    seats = section_repo.count_registered(db, [lop.id for lop in sections])
    by_course: dict[int, list[LopHocPhan]] = {}
    for lop in sections:
        by_course.setdefault(lop.hoc_phan_id, []).append(lop)

    chosen: list[PlannedSection] = []
    excluded: list[ExcludedCourse] = []
    occupied = list(taken)
    credits = registered_credits

    for course in candidates:
        hp = course.hoc_phan

        if course.hoc_phan_id in in_progress:
            excluded.append(
                _excluded(
                    hp,
                    "DANG_HOC",
                    f"Em đang học lớp {in_progress[course.hoc_phan_id]} ở học kỳ này, chờ kết quả.",
                )
            )
            continue
        missing = [
            p
            for p in section_repo.list_prerequisites(db, course.hoc_phan_id)
            if p.id not in summary.passed_course_ids
        ]
        if missing:
            names = ", ".join(f"{p.ma_hp} - {p.ten_hp}" for p in missing)
            excluded.append(
                _excluded(hp, "CHUA_DAT_TIEN_QUYET", f"Chưa đạt học phần tiên quyết: {names}.")
            )
            continue
        options = by_course.get(course.hoc_phan_id, [])
        if not options:
            excluded.append(
                _excluded(hp, "KHONG_CO_LOP_MO", f"Học kỳ {target.ten} không mở lớp học phần này.")
            )
            continue

        rejected: list[ExcludedSection] = []
        for lop in options:
            if seats.get(lop.id, 0) >= lop.si_so_toi_da:
                rejected.append(
                    ExcludedSection(
                        ma_lop=lop.ma_lop,
                        ma_loi="LOP_DA_DAY",
                        ly_do=f"Lớp đã đủ {lop.si_so_toi_da} sinh viên.",
                    )
                )
                continue
            clash = next((o for o in occupied if overlaps(lop, o)), None)
            if clash is not None:
                rejected.append(
                    ExcludedSection(
                        ma_lop=lop.ma_lop,
                        ma_loi="TRUNG_LICH",
                        ly_do=f"Trùng lịch với lớp {clash.ma_lop} ({schedule_label(clash)}).",
                    )
                )
                continue
            if credits + hp.so_tin_chi > limit:
                rejected.append(
                    ExcludedSection(
                        ma_lop=lop.ma_lop,
                        ma_loi="VUOT_TIN_CHI_TOI_DA",
                        ly_do=f"Thêm lớp này thì tổng {credits + hp.so_tin_chi} tín chỉ, "
                        f"vượt mức tối đa {limit}.",
                    )
                )
                continue
            occupied.append(lop)
            credits += hp.so_tin_chi
            chosen.append(
                PlannedSection(
                    ma_lop=lop.ma_lop,
                    ma_hp=hp.ma_hp,
                    ten_hp=hp.ten_hp,
                    tin_chi=hp.so_tin_chi,
                    lich=schedule_label(lop),
                    bat_buoc=course.bat_buoc,
                    ly_do_chon=_reason(course, course.hoc_phan_id in summary.failed_course_ids),
                )
            )
            break
        else:
            excluded.append(
                _excluded(
                    hp,
                    "KHONG_CON_LOP_PHU_HOP",
                    "Không còn lớp nào phù hợp (xem lý do từng lớp).",
                    rejected,
                )
            )

    return SemesterPlanOut(
        hoc_ky=target.ma_hoc_ky,
        ten_hoc_ky=target.ten,
        tin_chi_toi_da=limit,
        tin_chi_da_dang_ky=registered_credits,
        de_xuat=chosen,
        tong_tin_chi_de_xuat=credits - registered_credits,
        bi_loai=excluded,
    )
