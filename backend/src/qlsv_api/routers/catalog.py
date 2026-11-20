from fastapi import APIRouter, Query

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now
from src.qlsv_api.schemas import CurrentSemestersOut, ProgramOut, SectionOut
from src.qlsv_api.services import schedule_service, semester_service, student_admin_service

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


@router.get(
    "/programs",
    response_model=list[ProgramOut],
    summary="Các cặp ngành – khóa có chương trình đào tạo (để gán cho sinh viên)",
)
def list_programs(db: DbSession) -> list[ProgramOut]:
    return student_admin_service.list_programs(db)
