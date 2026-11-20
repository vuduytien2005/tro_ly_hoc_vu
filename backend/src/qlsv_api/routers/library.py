from typing import Annotated

from fastapi import APIRouter, Query

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now, run_in_transaction
from src.qlsv_api.schemas import BookOut, BorrowOut
from src.qlsv_api.services import library_service

router = APIRouter(prefix="/internal", tags=["Thư viện"], dependencies=[InternalAuth])


@router.get(
    "/students/{ma_sv}/borrows",
    response_model=list[BorrowOut],
    summary="Sách sinh viên đang mượn (kèm có gia hạn được không)",
)
def list_borrows(ma_sv: str, db: DbSession, now: Now) -> list[BorrowOut]:
    return library_service.list_borrows(db, ma_sv, now)


@router.get("/books", response_model=list[BookOut], summary="Tìm sách theo tên hoặc tác giả")
def search_books(
    db: DbSession, tu_khoa: Annotated[str, Query(min_length=1, max_length=100)]
) -> list[BookOut]:
    return library_service.search_books(db, tu_khoa)


@router.post(
    "/students/{ma_sv}/borrows/{muon_id}/renew",
    response_model=BorrowOut,
    summary="Gia hạn một lượt mượn (404 nếu không thuộc sinh viên này)",
)
def renew(ma_sv: str, muon_id: int, db: DbSession, now: Now) -> BorrowOut:
    return run_in_transaction(db, lambda: library_service.renew(db, ma_sv, muon_id, now))
