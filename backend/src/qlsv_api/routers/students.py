from typing import Annotated

from fastapi import APIRouter, Query, status

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now, run_in_transaction
from src.qlsv_api.schemas import (
    ExamScheduleOut,
    GraduationProgressOut,
    ScheduleOut,
    StudentCreateIn,
    StudentListOut,
    StudentProfileOut,
    StudentUpdateIn,
    TrangThaiSv,
    TranscriptOut,
    TuitionOut,
)
from src.qlsv_api.services import academic_service, schedule_service, student_admin_service

router = APIRouter(prefix="/internal/students", tags=["Sinh viên"], dependencies=[InternalAuth])

HocKyQuery = Query(default=None, description="Mã học kỳ, vd 2026-2027-HK1")


# ----- Quản lý hồ sơ (phòng đào tạo, AD-10) — khai báo TRƯỚC "/{ma_sv}" -----
@router.get("", response_model=StudentListOut, summary="(Phòng đào tạo) Danh sách sinh viên")
def list_students(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100, description="Mã SV, họ tên, email, lớp")] = None,
    trang_thai: TrangThaiSv | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentListOut:
    return student_admin_service.list_students(db, q, trang_thai, page, page_size)


@router.post(
    "",
    response_model=StudentProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="(Phòng đào tạo) Thêm sinh viên",
)
def create_student(body: StudentCreateIn, db: DbSession, now: Now) -> StudentProfileOut:
    return run_in_transaction(
        db, lambda: student_admin_service.create_student(db, body, now.date())
    )


@router.patch(
    "/{ma_sv}",
    response_model=StudentProfileOut,
    summary="(Phòng đào tạo) Sửa hồ sơ / đổi trạng thái (không đổi được mã SV)",
)
def update_student(ma_sv: str, body: StudentUpdateIn, db: DbSession, now: Now) -> StudentProfileOut:
    return run_in_transaction(
        db, lambda: student_admin_service.update_student(db, ma_sv, body, now.date())
    )


@router.get("/{ma_sv}", response_model=StudentProfileOut, summary="Hồ sơ sinh viên")
def get_profile(ma_sv: str, db: DbSession) -> StudentProfileOut:
    return academic_service.get_profile(db, ma_sv)


@router.get(
    "/{ma_sv}/transcript",
    response_model=TranscriptOut,
    summary="Bảng điểm + GPA và tín chỉ tích lũy",
)
def get_transcript(ma_sv: str, db: DbSession, ma_hoc_ky: str | None = HocKyQuery) -> TranscriptOut:
    return academic_service.get_transcript(db, ma_sv, ma_hoc_ky)


@router.get(
    "/{ma_sv}/graduation-progress",
    response_model=GraduationProgressOut,
    summary="Tiến độ so với điều kiện tốt nghiệp",
)
def get_graduation_progress(ma_sv: str, db: DbSession) -> GraduationProgressOut:
    return academic_service.get_graduation_progress(db, ma_sv)


@router.get(
    "/{ma_sv}/schedule",
    response_model=ScheduleOut,
    summary="Thời khóa biểu (mặc định học kỳ hiện tại)",
)
def get_schedule(
    ma_sv: str, db: DbSession, now: Now, ma_hoc_ky: str | None = HocKyQuery
) -> ScheduleOut:
    return schedule_service.get_schedule(db, ma_sv, ma_hoc_ky, now)


@router.get(
    "/{ma_sv}/exam-schedule",
    response_model=ExamScheduleOut,
    summary="Lịch thi (mặc định học kỳ hiện tại)",
)
def get_exam_schedule(
    ma_sv: str, db: DbSession, now: Now, ma_hoc_ky: str | None = HocKyQuery
) -> ExamScheduleOut:
    return schedule_service.get_exam_schedule(db, ma_sv, ma_hoc_ky, now)


@router.get(
    "/{ma_sv}/tuition", response_model=TuitionOut, summary="Học phí (mặc định học kỳ hiện tại)"
)
def get_tuition(
    ma_sv: str, db: DbSession, now: Now, ma_hoc_ky: str | None = HocKyQuery
) -> TuitionOut:
    return schedule_service.get_tuition(db, ma_sv, ma_hoc_ky, now)
