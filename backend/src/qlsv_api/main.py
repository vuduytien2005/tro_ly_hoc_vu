"""qlsv_api — Hệ thống quản lý sinh viên GIẢ LẬP (đóng vai hệ thống thật của trường).

Chạy (từ thư mục backend/):  python -m src.qlsv_api.main   -> http://127.0.0.1:8001/docs
- Chỉ lắng nghe 127.0.0.1 (không lộ ra mạng ngoài).
- Mọi route /internal/* bắt buộc header X-Internal-Token = INTERNAL_API_TOKEN.
- Lỗi luôn có dạng {"detail": "<tiếng Việt>", "code": "<MA_LOI>"}.
"""

import logging
from collections.abc import Awaitable, Callable

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.routers import catalog, registrations, requests, students
from src.shared.config import get_settings
from src.shared.security import INTERNAL_TOKEN_HEADER, is_valid_internal_token

logger = logging.getLogger("qlsv_api")

PROTECTED_PREFIX = "/internal"


def error_response(status: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def create_app() -> FastAPI:
    app = FastAPI(
        title="QLSV giả lập (nội bộ)",
        description=(
            "Hệ thống quản lý sinh viên giả lập cho đề tài trợ lý học vụ. "
            "Bấm **Authorize** và nhập `INTERNAL_API_TOKEN` (trong .env) để gọi thử."
        ),
        version="0.2.0",
    )

    @app.middleware("http")
    async def require_internal_token(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(PROTECTED_PREFIX):
            token = request.headers.get(INTERNAL_TOKEN_HEADER)
            if not token:
                return error_response(
                    401, "Thiếu token xác thực nội bộ (X-Internal-Token).", "THIEU_TOKEN_NOI_BO"
                )
            if not is_valid_internal_token(token):
                return error_response(
                    401, "Token xác thực nội bộ không hợp lệ.", "TOKEN_NOI_BO_KHONG_HOP_LE"
                )
        return await call_next(request)

    @app.exception_handler(BusinessError)
    async def business_error_handler(_: Request, exc: BusinessError) -> JSONResponse:
        return error_response(exc.status, exc.message, exc.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors())
        return error_response(
            422, f"Dữ liệu gửi lên không hợp lệ (kiểm tra: {fields}).", "DU_LIEU_KHONG_HOP_LE"
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "Không tìm thấy đường dẫn yêu cầu.", "KHONG_TIM_THAY")
        if exc.status_code == 405:
            return error_response(405, "Phương thức không được hỗ trợ.", "PHUONG_THUC_KHONG_HO_TRO")
        return error_response(exc.status_code, str(exc.detail), "LOI_HTTP")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Lỗi không xử lý được", exc_info=exc)
        return error_response(500, "Lỗi hệ thống QLSV, vui lòng thử lại sau.", "LOI_HE_THONG")

    for router in (students.router, registrations.router, requests.router, catalog.router):
        app.include_router(router)

    @app.get("/health", tags=["Hệ thống"], summary="Kiểm tra service đang chạy")
    def health() -> dict[str, str]:
        return {"trang_thai": "ok"}

    return app


app = create_app()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=get_settings().qlsv_api_port)


if __name__ == "__main__":
    main()
