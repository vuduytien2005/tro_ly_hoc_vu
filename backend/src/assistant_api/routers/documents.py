"""Mở văn bản gốc từ trích dẫn (/api/documents/{id}/file) — bổ sung 23/11/2026.

Câu trả lời trích "[1] Quy chế đào tạo, Điều 12, trang 8": sinh viên bấm để mở đúng văn bản đó.
Chỉ phục vụ văn bản ĐÃ LẬP CHỈ MỤC (chính là văn bản trợ lý được phép trích dẫn), chỉ tệp nằm
trong UPLOAD_DIR (chặn đọc tệp ngoài thư mục nếu bản ghi CSDL bị sửa sai). Mọi tài khoản đăng
nhập đều xem được: quy chế là tài liệu công khai trong trường.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.assistant_api.deps import CurrentUser, DbSession
from src.assistant_api.errors import ApiError
from src.assistant_api.models import VanBan
from src.assistant_api.routers import admin as admin_router

router = APIRouter(prefix="/api/documents", tags=["Văn bản quy chế"])

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}
INDEXED = "da_lap_chi_muc"


def _not_found() -> ApiError:
    return ApiError("VAN_BAN_KHONG_TON_TAI", "Không tìm thấy văn bản gốc.", 404)


@router.get("/{van_ban_id}/file", summary="Tệp gốc của văn bản đã lập chỉ mục (xem trực tiếp)")
def get_document_file(van_ban_id: int, _user: CurrentUser, db: DbSession) -> FileResponse:
    van_ban = db.get(VanBan, van_ban_id)
    if van_ban is None or van_ban.trang_thai != INDEXED:
        raise _not_found()
    root = Path(admin_router.upload_dir()).resolve()
    path = Path(van_ban.duong_dan_tep).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise _not_found()
    ext = path.suffix.lower()
    if ext not in MEDIA_TYPES:
        raise _not_found()
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[ext],
        filename=van_ban.ten_tep,
        content_disposition_type="inline",
    )
