"""assistant_api — Backend trợ lý học vụ (đăng nhập, hội thoại, vòng lặp Agent).
Chạy (từ thư mục backend/):  python -m src.assistant_api.main   -> http://127.0.0.1:8000/docs
- Lỗi luôn có dạng {"detail": "<tiếng Việt>", "code": "<MA_LOI>"}.
- Khởi động: đồng bộ danh mục công cụ với các MCP server (server chưa chạy -> thử lại sau 30 giây).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.assistant_api.agent.actions import expire_stale_actions
from src.assistant_api.agent.llm import LLM, LiteLlm, llm_key_present
from src.assistant_api.agent.loop import AgentRunner
from src.assistant_api.agent.registry import ToolRegistry
from src.assistant_api.errors import ApiError
from src.assistant_api.mcp_client.client import McpClient
from src.assistant_api.qlsv_directory import QlsvDirectory
from src.assistant_api.rag_admin import RagAdminClient
from src.assistant_api.routers import (
    actions,
    admin,
    admin_knowledge,
    admin_requests,
    admin_students,
    admin_users,
    auth,
    conversations,
    documents,
    my_requests,
    oauth,
)
from src.shared.config import get_settings
from src.shared.db import assistant_session_factory
from src.shared.oauth import get_key_store

logger = logging.getLogger("assistant_api")


async def sweep_expired_actions(session_factory: Callable[[], Session], interval: float) -> None:
    """Việc nền: định kỳ chuyển thẻ xác nhận quá hạn sang `het_han` (chạy trong luồng riêng vì
    pyodbc đồng bộ). Lỗi CSDL chỉ ghi log, lần sau thử lại."""

    def run_once() -> int:
        with session_factory() as db:
            return expire_stale_actions(db)

    while True:
        try:
            count = await asyncio.to_thread(run_once)
            if count:
                logger.info("Đã chuyển %d thẻ xác nhận quá hạn sang het_han.", count)
        except Exception:
            logger.exception("Dọn thẻ xác nhận quá hạn thất bại.")
        await asyncio.sleep(interval)


def error_response(status: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def default_verifier(llm: LLM | None) -> LLM | None:
    """Giám khảo kiểm chứng: chạy thật (không truyền LLM giả) và ANSWER_VERIFY bật -> LiteLlm với
    VERIFIER_MODEL (trống = LLM_MODEL). Test truyền FakeLLM thì mặc định KHÔNG có giám khảo."""
    settings = get_settings()
    if llm is not None or not settings.answer_verify:
        return None
    return LiteLlm(settings.verifier_model or None)


def create_app(
    registry: ToolRegistry | None = None,
    llm: LLM | None = None,
    session_factory: Callable[[], Session] | None = None,
    rag_admin: RagAdminClient | None = None,
    qlsv_directory: QlsvDirectory | None = None,
    verifier_llm: LLM | None = None,
) -> FastAPI:
    """Test truyền registry (MCP server chạy trong tiến trình), FakeLLM, session_factory riêng
    và rag_admin (gọi app quy_che trong tiến trình)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.session_factory = session_factory or assistant_session_factory()
        app.state.registry = registry or ToolRegistry(McpClient({}))
        app.state.runner = AgentRunner(
            app.state.registry, llm or LiteLlm(), verifier_llm or default_verifier(llm)
        )
        app.state.rag_admin = rag_admin or RagAdminClient()
        app.state.qlsv_directory = qlsv_directory or QlsvDirectory()
        if get_settings().mcp_auth_mode == "oauth":
            # Tạo/nạp khóa ký TRƯỚC khi đồng bộ công cụ: kèm tệp JWKS công khai cho MCP server
            logger.info("Khóa ký OAuth cho MCP: kid=%s", get_key_store().ensure())
        if registry is None:
            with app.state.session_factory() as db:
                await app.state.registry.sync(db)
            logger.info("Trạng thái MCP server: %s", app.state.registry.server_status)
        if not get_settings().llm_model and llm is None:
            logger.warning("Chưa đặt LLM_MODEL trong .env -> trợ lý sẽ báo lỗi khi trò chuyện.")
        sweeper = None
        interval = get_settings().action_sweep_seconds
        # Test truyền session_factory riêng (transaction + savepoint, một kết nối) -> không chạy
        # việc nền ở luồng khác; test gọi expire_stale_actions trực tiếp.
        if session_factory is None and interval > 0:
            sweeper = asyncio.create_task(
                sweep_expired_actions(app.state.session_factory, interval)
            )
        try:
            yield
        finally:
            if sweeper is not None:
                sweeper.cancel()

    app = FastAPI(
        title="Trợ lý học vụ — assistant_api",
        description="Bấm **Authorize**, dán `access_token` nhận từ `/api/auth/login`.",
        version="0.8.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
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
        return error_response(500, "Lỗi hệ thống, vui lòng thử lại sau.", "LOI_HE_THONG")

    app.include_router(auth.router)
    app.include_router(conversations.router)
    app.include_router(actions.router)
    app.include_router(my_requests.router)
    app.include_router(documents.router)
    app.include_router(oauth.router)
    app.include_router(admin.router)
    app.include_router(admin_users.router)
    app.include_router(admin_students.router)
    app.include_router(admin_requests.router)
    app.include_router(admin_knowledge.router)

    @app.get("/health", tags=["Hệ thống"], summary="Trạng thái service và các MCP server")
    async def health(request: Request) -> dict[str, object]:
        """Web đọc mỗi 30 giây để hiện banner "chức năng đang gián đoạn" (không cần đăng nhập,
        không chứa dữ liệu nhạy cảm)."""
        registry: ToolRegistry = request.app.state.registry
        await registry.probe()
        with request.app.state.session_factory() as db:
            await registry.ensure_fresh(db)  # server vừa chết / sống lại -> đồng bộ danh mục tool
        status = registry.server_status
        model = get_settings().llm_model
        return {
            "trang_thai": "ok",
            "mcp_server": status,
            "gian_doan": sorted(s for s, v in status.items() if v not in ("ok", "tắt")),
            "llm_da_cau_hinh": bool(model),
            "llm_co_khoa": llm_key_present(model) if model else False,
            "che_do_trinh_bay": get_settings().che_do_trinh_bay,
        }

    return app


app = create_app()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=get_settings().assistant_api_port)


if __name__ == "__main__":
    main()
