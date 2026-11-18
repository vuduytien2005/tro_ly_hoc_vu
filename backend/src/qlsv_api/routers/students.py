from fastapi import APIRouter, Query

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now
from src.qlsv_api.schemas import (
    ExamScheduleOut,
    GraduationProgressOut,
    ScheduleOut,
    StudentProfileOut,
    TranscriptOut,
    TuitionOut,
)
from src.qlsv_api.services import academic_service, schedule_service

router = APIRouter(prefix="/internal/students", tags=["Sinh viên"], dependencies=[InternalAuth])

HocKyQuery = Query(default=None, description="Mã học kỳ, vd 2026-2027-HK1")


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
