"""Duyệt đơn (/api/admin/requests) — quản trị viên đóng vai cán bộ phòng CTSV / đào tạo.

Thao tác của cán bộ, không phải hành động của Agent -> gọi thẳng qlsv_api qua QlsvDirectory
(ngoại lệ đã ghi ở docs/02), không qua MCP/LLM. Máy trạng thái của đơn nằm ở qlsv_api (nguồn sự
thật); lỗi nghiệp vụ 4xx (chuyển sai bước, thiếu lý do từ chối) được chuyển nguyên văn.
Thiết kế: docs/superpowers/specs/2026-11-23-duyet-don-design.md.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.assistant_api.deps import require_admin
from src.assistant_api.qlsv_directory import QlsvDirectory
from src.assistant_api.routers.admin_users import qlsv_directory

router = APIRouter(
    prefix="/api/admin/requests",
    tags=["Quản trị — duyệt đơn"],
    dependencies=[Depends(require_admin)],
)

Directory = Annotated[QlsvDirectory, Depends(qlsv_directory)]
TrangThaiDon = Literal["moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat"]
LoaiDon = Literal["giay_xac_nhan_sv", "bao_luu", "phuc_khao", "hoi_dap"]


class ReviewIn(BaseModel):
    trang_thai: Literal["dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat", "moi_tao"]
    ghi_chu_xu_ly: Annotated[str | None, Field(max_length=2000)] = None


@router.get("", summary="Danh sách đơn của mọi sinh viên (mới nhất trước)")
async def list_requests(
    directory: Directory,
    trang_thai: TrangThaiDon | None = None,
    loai_don: LoaiDon | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    return await directory.list_requests(
        {"trang_thai": trang_thai, "loai_don": loai_don, "page": page, "page_size": page_size}
    )


@router.patch("/{ma_don}", summary="Chuyển trạng thái đơn, kèm ghi chú xử lý cho sinh viên")
async def review_request(ma_don: str, body: ReviewIn, directory: Directory) -> dict[str, Any]:
    return await directory.update_request(ma_don, body.model_dump())
