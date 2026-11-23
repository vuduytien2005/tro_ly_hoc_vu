from typing import Annotated

from fastapi import APIRouter, Query, status

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now, run_in_transaction
from src.qlsv_api.schemas import (
    LoaiDon,
    RequestCreateIn,
    RequestOut,
    RequestSummaryOut,
    RequestUpdateIn,
    StaffRequestListOut,
    TrangThaiDon,
)
from src.qlsv_api.services import request_service

router = APIRouter(prefix="/internal", tags=["Đơn từ"], dependencies=[InternalAuth])


@router.post(
    "/students/{ma_sv}/requests",
    response_model=RequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đơn (giấy xác nhận SV, bảo lưu, phúc khảo)",
)
def create_request(ma_sv: str, body: RequestCreateIn, db: DbSession, now: Now) -> RequestOut:
    return run_in_transaction(
        db,
        lambda: request_service.create_request(
            db, ma_sv, body.loai_don, body.noi_dung, body.tao_boi, now
        ),
    )


@router.get(
    "/students/{ma_sv}/requests",
    response_model=list[RequestSummaryOut],
    summary="Danh sách đơn của sinh viên",
)
def list_requests(
    ma_sv: str, db: DbSession, trang_thai: Annotated[TrangThaiDon | None, Query()] = None
) -> list[RequestSummaryOut]:
    return request_service.list_requests(db, ma_sv, trang_thai)


@router.get(
    "/students/{ma_sv}/requests/{ma_don}",
    response_model=RequestOut,
    summary="Chi tiết đơn (404 nếu không thuộc sinh viên này)",
)
def get_request(ma_sv: str, ma_don: str, db: DbSession) -> RequestOut:
    return request_service.get_request(db, ma_sv, ma_don)


@router.get(
    "/requests",
    response_model=StaffRequestListOut,
    summary="(Cán bộ) Mọi đơn, mới nhất trước, kèm người nộp",
)
def list_all_requests(
    db: DbSession,
    trang_thai: Annotated[TrangThaiDon | None, Query()] = None,
    loai_don: Annotated[LoaiDon | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StaffRequestListOut:
    return request_service.list_all_requests(db, trang_thai, loai_don, page, page_size)


@router.patch(
    "/requests/{ma_don}",
    response_model=RequestOut,
    summary="(Cán bộ) Cập nhật trạng thái đơn",
)
def update_request(ma_don: str, body: RequestUpdateIn, db: DbSession, now: Now) -> RequestOut:
    return run_in_transaction(
        db,
        lambda: request_service.update_status(db, ma_don, body.trang_thai, body.ghi_chu_xu_ly, now),
    )
