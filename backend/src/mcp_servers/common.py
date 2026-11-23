"""Phần dùng chung cho các MCP server (dao_tao, ctsv, tai_chinh, quy_che).

SDK: package `mcp` 2.x — lớp `MCPServer` (bản 1.x gọi là `FastMCP`), transport
streamable HTTP tại `/mcp`, chỉ lắng nghe 127.0.0.1.

Bảo mật:
- assistant_api -> MCP server (`/mcp`): OAuth 2.1 — token JWT ngắn hạn do assistant_api ký
  (Ed25519), gắn `aud` = URL server này, `scope` = công cụ, `sub` = mã sinh viên; kiểm bằng
  `McpAuthMiddleware` (ASGI) + `check_token_for_tool` trong `tool_errors`. `MCP_AUTH_MODE=token`
  quay về cách cũ (Bearer INTERNAL_API_TOKEN dùng chung).
- assistant_api -> `/internal/*` của quy_che (quản trị RAG): Bearer INTERNAL_API_TOKEN.
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
from urllib.parse import quote, urlsplit

import httpx
import uvicorn
from mcp.server.auth.middleware.auth_context import auth_context_var, get_access_token
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.mcpserver import MCPServer
from pydantic import Field
from starlette.applications import Starlette
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.config import get_settings
from src.shared.oauth import JwtVerifier, normalize_resource, tool_scope
from src.shared.security import INTERNAL_TOKEN_HEADER, is_valid_internal_token

logger = logging.getLogger("mcp_servers")

P = ParamSpec("P")

INJECTED_NOTE = "[INJECTED] Do hệ thống điền, không yêu cầu người dùng cung cấp."

MaSv = Annotated[str, Field(description=f"Mã sinh viên. {INJECTED_NOTE}")]
MaKhoa = Annotated[
    str,
    Field(description=f"Mã khóa của sinh viên (vd K22), để lọc phiên bản quy chế. {INJECTED_NOTE}"),
]
ChiKiemTra = Annotated[
    bool,
    Field(
        description="Chỉ kiểm tra điều kiện, không thực hiện. [SYSTEM] Do hệ thống tự đặt khi "
        "chuẩn bị thẻ xác nhận; bị ẩn khỏi schema gửi cho LLM."
    ),
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


def check_token_for_tool(tool: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Phòng thủ nhiều lớp (OAuth): token của lần gọi phải cho phép ĐÚNG công cụ này, và nếu công
    cụ có `ma_sv` thì phải trùng `sub` (sinh viên đang đăng nhập) — assistant_api có lỗi tiêm ngữ
    cảnh cũng không đọc được dữ liệu sinh viên khác. Không có token (gọi trong tiến trình: test,
    thực nghiệm; hoặc chế độ token cũ) thì bỏ qua."""
    access = get_access_token()
    if access is None:
        return None
    if tool_scope(tool) not in access.scopes:
        logger.warning("Từ chối %s: token chỉ cho phép %s", tool, access.scopes)
        return to_tool_error("KHONG_DU_QUYEN", "Token không cho phép gọi công cụ này.")
    ma_sv = kwargs.get("ma_sv")
    if ma_sv is not None and str(ma_sv).strip().upper() != (access.subject or "").upper():
        logger.warning("Từ chối %s: ma_sv không khớp sub của token", tool)
        return to_tool_error("KHONG_DU_QUYEN", "Không được truy cập dữ liệu của sinh viên khác.")
    return None


def tool_errors(
    fn: Callable[P, Awaitable[dict[str, Any]]],
) -> Callable[P, Awaitable[dict[str, Any]]]:
    """Bọc tool: lỗi qlsv_api -> dict lỗi có cấu trúc; lỗi bất ngờ -> ghi log + thông báo chung.

    functools.wraps giữ nguyên chữ ký hàm, nên MCPServer vẫn sinh đúng JSON schema.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        denied = check_token_for_tool(fn.__name__, kwargs)
        if denied is not None:
            return denied
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
PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"


def _bearer(scope: Scope) -> str | None:
    for key, value in scope["headers"]:
        if key.decode("latin-1").lower() == "authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            return token.strip() if scheme.lower() == "bearer" and token.strip() else None
    return None


class McpAuthMiddleware:
    """ASGI middleware xác thực MCP server.

    - `PROTECTED_RESOURCE_PATH` (RFC 9728): công khai — cho client biết authorization server nào
      cấp token cho tài nguyên này.
    - `/internal/*` (quản trị RAG của quy_che): Bearer INTERNAL_API_TOKEN.
    - Còn lại (`/mcp`): chế độ `oauth` -> token JWT hợp lệ cho ĐÚNG server này, đặt `AccessToken`
      vào context của SDK (`get_access_token()`); chế độ `token` -> Bearer INTERNAL_API_TOKEN.

    Viết dạng ASGI thuần (không dùng BaseHTTPMiddleware) để không ảnh hưởng luồng streaming.
    """

    def __init__(self, app: ASGIApp, resource_url: str, verifier: JwtVerifier | None) -> None:
        self.app = app
        self.resource_url = normalize_resource(resource_url)
        self.verifier = verifier
        self.metadata_url = metadata_url_for(self.resource_url)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if path == PROTECTED_RESOURCE_PATH or path.startswith(PROTECTED_RESOURCE_PATH + "/"):
            await _send_json(send, 200, self._metadata())
            return
        token = _bearer(scope)
        if path.startswith("/internal") or self.verifier is None:
            if token is None:
                await _reject(
                    send, "Thiếu token xác thực nội bộ (Authorization: Bearer).", "THIEU_TOKEN"
                )
            elif not is_valid_internal_token(token):
                await _reject(send, "Token xác thực nội bộ không hợp lệ.", "TOKEN_KHONG_HOP_LE")
            else:
                await self.app(scope, receive, send)
            return
        if token is None:
            await _reject(
                send,
                "Thiếu token truy cập (Authorization: Bearer).",
                "THIEU_TOKEN",
                self.metadata_url,
            )
            return
        access = await self.verifier.verify_token(token)
        if access is None:
            await _reject(
                send,
                "Token truy cập không hợp lệ, hết hạn hoặc không cấp cho server này.",
                "TOKEN_KHONG_HOP_LE",
                self.metadata_url,
            )
            return
        reset = auth_context_var.set(AuthenticatedUser(access))
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(reset)

    def _metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource_url,
            "authorization_servers": [get_settings().oauth_issuer_url],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["mcp:tools.list", "mcp:tool:<tên công cụ>"],
        }


def metadata_url_for(resource_url: str) -> str:
    """RFC 9728 mục 3.1: chèn /.well-known/oauth-protected-resource trước đường dẫn tài nguyên."""
    parts = urlsplit(resource_url)
    return f"{parts.scheme}://{parts.netloc}{PROTECTED_RESOURCE_PATH}{parts.path}"


async def _send_json(
    send: Send,
    status: int,
    payload: dict[str, Any],
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
                *(extra_headers or []),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _reject(send: Send, detail: str, code: str, metadata_url: str | None = None) -> None:
    challenge = "Bearer"
    if metadata_url:  # RFC 6750 + RFC 9728: chỉ cho client nơi tìm authorization server
        challenge += f' error="invalid_token", resource_metadata="{metadata_url}"'
    await _send_json(
        send, 401, {"detail": detail, "code": code}, [(b"www-authenticate", challenge.encode())]
    )


HOST = "127.0.0.1"


def resource_url_for(port: int) -> str:
    return f"http://{HOST}:{port}/mcp"


def _default_port(mcp: MCPServer) -> int:
    port = getattr(get_settings(), f"mcp_{mcp.name}_port", None)
    if not isinstance(port, int):
        raise ValueError(f"Không biết cổng của MCP server '{mcp.name}', truyền port vào build_app.")
    return port


def build_app(
    mcp: MCPServer, port: int | None = None, verifier: JwtVerifier | None = None
) -> Starlette:
    """Ứng dụng ASGI của MCP server (endpoint /mcp) đã bọc xác thực.

    - stateless_http: mỗi lệnh gọi tool độc lập, không giữ phiên -> đơn giản cho assistant_api.
    - json_response: trả JSON thay vì SSE (tool trả kết quả một lần, không cần streaming).
    - `verifier`: None -> tự tạo theo `MCP_AUTH_MODE` (oauth: JwtVerifier cho URL server này).
    """
    resource_url = resource_url_for(port if port is not None else _default_port(mcp))
    if verifier is None and get_settings().mcp_auth_mode == "oauth":
        verifier = JwtVerifier(resource_url)
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host=HOST,  # SDK tự bật chống DNS rebinding cho 127.0.0.1
    )
    app.add_middleware(McpAuthMiddleware, resource_url=resource_url, verifier=verifier)
    return app


def run(mcp: MCPServer, port: int) -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("MCP server %s: http://%s:%d/mcp", mcp.name, HOST, port)
    logger.info("Xác thực /mcp: %s", get_settings().mcp_auth_mode)
    uvicorn.run(build_app(mcp, port), host=HOST, port=port)
