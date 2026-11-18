from fastapi import APIRouter, Query

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now
from src.qlsv_api.schemas import CurrentSemestersOut, SectionOut
from src.qlsv_api.services import schedule_service, semester_service

router = APIRouter(prefix="/internal", tags=["Danh mục"], dependencies=[InternalAuth])


@router.get(
    "/course-sections",
    response_model=list[SectionOut],
    summary="Tra cứu lớp học phần (mặc định học kỳ đang mở đăng ký), kèm số chỗ trống",
)
def search_course_sections(
    db: DbSession,
    now: Now,
    q: str | None = Query(default=None, description="Mã lớp, mã/tên học phần, giảng viên"),
    ma_hoc_ky: str | None = Query(default=None),
    limit: int = Query(default=schedule_service.MAX_SECTIONS, ge=1, le=50),
) -> list[SectionOut]:
    return schedule_service.search_sections(db, q, ma_hoc_ky, now, limit)


@router.get(
    "/semesters/current",
    response_model=CurrentSemestersOut,
    summary="Học kỳ hiện tại và học kỳ đang mở đăng ký",
)
def get_current_semesters(db: DbSession, now: Now) -> CurrentSemestersOut:
    return semester_service.get_current_semesters(db, now)
