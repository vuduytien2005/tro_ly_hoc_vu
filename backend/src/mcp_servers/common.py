"""Phần dùng chung cho các MCP server (dao_tao, ctsv, tai_chinh, quy_che).

SDK: package `mcp` 2.x — lớp `MCPServer` (bản 1.x gọi là `FastMCP`), transport
streamable HTTP tại `/mcp`, chỉ lắng nghe 127.0.0.1.

Bảo mật:
- assistant_api -> MCP server: header `Authorization: Bearer <INTERNAL_API_TOKEN>`,
  kiểm bằng `BearerAuthMiddleware` (ASGI) bọc ngoài ứng dụng của SDK.
- MCP server -> qlsv_api: header `X-Internal-Token` (trong `QlsvClient`).
- SDK tự bật chống DNS rebinding khi host = 127.0.0.1 (chỉ nhận Host 127.0.0.1/localhost).

Quy ước công cụ:
- Tham số dữ liệu cá nhân đầu tiên là `ma_sv: MaSv`. Mô tả "[INJECTED]" nằm trong JSON schema
  của tham số (không nằm trong docstring), nên khi assistant_api xóa `ma_sv` khỏi schema thì
  LLM không còn thấy dấu vết nào của tham số này.
- Lỗi nghiệp vụ KHÔNG ném exception mà trả `{"thanh_cong": false, "ma_loi", "thong_bao"}`
  để LLM giải thích được cho sinh viên.
"""

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, ParamSpec
from urllib.parse import quote

import httpx
import uvicorn
from mcp.server.mcpserver import MCPServer
from pydantic import Field
from starlette.applications import Starlette
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.config import get_settings
from src.shared.security import INTERNAL_TOKEN_HEADER, is_valid_internal_token

logger = logging.getLogger("mcp_servers")

P = ParamSpec("P")

INJECTED_NOTE = "[INJECTED] Do hệ thống điền, không yêu cầu người dùng cung cấp."

MaSv = Annotated[str, Field(description=f"Mã sinh viên. {INJECTED_NOTE}")]
MaKhoa = Annotated[
    str,
    Field(description=f"Mã khóa của sinh viên (vd K22), để lọc phiên bản quy chế. {INJECTED_NOTE}"),
]
MaHocKy = Annotated[
    str | None,
    Field(
        description=(
            'Mã học kỳ, ví dụ "2025-2026-HK2". Bỏ trống để dùng học kỳ hiện tại. '
            "Chỉ điền khi sinh viên nói rõ học kỳ nào."
        )
    ),
]


# ---------------------------------------------------------------------------
# Gọi qlsv_api
# ---------------------------------------------------------------------------
class ToolFailure(Exception):
    """Lỗi nghiệp vụ của tool -> `@tool_errors` đổi thành dict lỗi có cấu trúc cho LLM."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class QlsvError(ToolFailure):
    """Lỗi từ qlsv_api (nghiệp vụ 4xx) hoặc lỗi kết nối."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(code, message)
        self.status = status


def path_segment(value: str) -> str:
    """Mã hóa một đoạn đường dẫn: chặn tham số do LLM sinh kiểu "../" hay "a/b"."""
    return quote(str(value).strip(), safe="")


class QlsvClient:
    """Client HTTP tới qlsv_api, luôn kèm header X-Internal-Token."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url
        self._token = token
        self._timeout = timeout
        # Thực nghiệm (evaluation/) gắn qlsv_api chạy trong tiến trình: httpx.ASGITransport(app)
        self.transport: httpx.AsyncBaseTransport | None = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        settings = get_settings()
        headers = {INTERNAL_TOKEN_HEADER: self._token or settings.internal_api_token}
        clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        async with httpx.AsyncClient(
            base_url=self._base_url or settings.qlsv_api_url,
            headers=headers,
            timeout=self._timeout,
            transport=self.transport,
        ) as client:
            try:
                response = await client.request(method, path, params=clean_params, json=json_body)
            except httpx.TimeoutException as exc:
                raise QlsvError(
                    "QLSV_QUA_THOI_GIAN",
                    "Hệ thống quản lý sinh viên phản hồi quá chậm, em thử lại sau ít phút nhé.",
                    504,
                ) from exc
            except httpx.HTTPError as exc:
                raise QlsvError(
                    "QLSV_KHONG_KET_NOI",
                    "Không kết nối được hệ thống quản lý sinh viên, em thử lại sau nhé.",
                    503,
                ) from exc

        if response.is_success:
            return response.json()
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {}
        raise QlsvError(
            code=str(body.get("code") or f"QLSV_LOI_{response.status_code}"),
            message=str(body.get("detail") or "Hệ thống quản lý sinh viên báo lỗi."),
            status=response.status_code,
        )

    async def get(self, path: str, **params: Any) -> Any:
        return await self.request("GET", path, params=params)


qlsv = QlsvClient()


# ---------------------------------------------------------------------------
# Chuẩn trả lỗi cho LLM
# ---------------------------------------------------------------------------
def to_tool_error(code: str, message: str) -> dict[str, Any]:
    return {"thanh_cong": False, "ma_loi": code, "thong_bao": message}


def tool_errors(
    fn: Callable[P, Awaitable[dict[str, Any]]],
) -> Callable[P, Awaitable[dict[str, Any]]]:
    """Bọc tool: lỗi qlsv_api -> dict lỗi có cấu trúc; lỗi bất ngờ -> ghi log + thông báo chung.

    functools.wraps giữ nguyên chữ ký hàm, nên MCPServer vẫn sinh đúng JSON schema.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except ToolFailure as exc:
            return to_tool_error(exc.code, exc.message)
        except Exception:
            logger.exception("Tool %s lỗi không mong đợi", fn.__name__)
            return to_tool_error(
                "LOI_HE_THONG", "Có lỗi hệ thống khi xử lý yêu cầu, em thử lại sau nhé."
            )

    return wrapper


def format_vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đồng"


def day_label(thu: int) -> str:
    return "Chủ nhật" if thu == 8 else f"Thứ {thu}"


# ---------------------------------------------------------------------------
# Xác thực Bearer + chạy server
# ---------------------------------------------------------------------------
class BearerAuthMiddleware:
    """ASGI middleware: mọi request HTTP phải có `Authorization: Bearer <INTERNAL_API_TOKEN>`.

    Viết dạng ASGI thuần (không dùng BaseHTTPMiddleware) để không ảnh hưởng luồng streaming
    của transport MCP.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            await _reject(
                send, "Thiếu token xác thực nội bộ (Authorization: Bearer).", "THIEU_TOKEN"
            )
            return
        if not is_valid_internal_token(token.strip()):
            await _reject(send, "Token xác thực nội bộ không hợp lệ.", "TOKEN_KHONG_HOP_LE")
            return
        await self.app(scope, receive, send)


async def _reject(send: Send, detail: str, code: str) -> None:
    body = json.dumps({"detail": detail, "code": code}, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"www-authenticate", b"Bearer"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


HOST = "127.0.0.1"


def build_app(mcp: MCPServer) -> Starlette:
    """Ứng dụng ASGI của MCP server (endpoint /mcp) đã bọc xác thực Bearer.

    - stateless_http: mỗi lệnh gọi tool độc lập, không giữ phiên -> đơn giản cho assistant_api.
    - json_response: trả JSON thay vì SSE (tool trả kết quả một lần, không cần streaming).
    """
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host=HOST,  # SDK tự bật chống DNS rebinding cho 127.0.0.1
    )
    app.add_middleware(BearerAuthMiddleware)
    return app


def run(mcp: MCPServer, port: int) -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("MCP server %s: http://%s:%d/mcp", mcp.name, HOST, port)
    uvicorn.run(build_app(mcp), host=HOST, port=port)
