"""Client gọi các MCP server (streamable HTTP).

Xác thực (MCP_AUTH_MODE): `oauth` (mặc định) — mỗi lần gọi một token JWT riêng, sống 60 giây,
gắn `aud` = URL server, `scope` = công cụ (hoặc liệt kê), `sub` = `ma_sv` đã tiêm từ tài khoản đăng
nhập (src/shared/oauth.py). Server độc có giữ token cũng không dùng lại được ở server khác.
`token` — Bearer INTERNAL_API_TOKEN dùng chung (cách cũ).

Mỗi lần gọi mở một kết nối mới (server chạy chế độ stateless, cùng máy -> chi phí rất nhỏ). Nhờ vậy
server khởi động lại thì lần gọi sau tự kết nối lại, không giữ phiên "chết".
Chỉ THỬ LẠI khi lỗi xảy ra lúc kết nối (ConnectError: yêu cầu chưa tới server). Lỗi sau khi yêu cầu
đã gửi đi thì không thử lại — tránh một tool ghi (đăng ký học phần...) bị thực hiện 2 lần.

`target` của một server: URL (chạy thật) hoặc đối tượng MCPServer (test, kết nối trong tiến trình).
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer

from src.shared.config import get_settings
from src.shared.oauth import issue_mcp_token

logger = logging.getLogger(__name__)

McpTarget = str | MCPServer
CONNECT_RETRIES = 1
PREVIEW_SERVER = "_xem_truoc"  # tên tạm khi kết nối thử server chưa đăng ký
TIMEOUT_SECONDS = 120.0  # lần đầu quy_che nạp mô hình embedding có thể mất vài chục giây


class McpUnavailableError(Exception):
    """Không kết nối được MCP server (sau khi đã thử lại)."""


@dataclass(frozen=True)
class ToolSpec:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None  # tên hiển thị server tự khai báo (chuẩn MCP)
    # Annotation readOnlyHint do server TỰ khai báo: chỉ là gợi ý cho quản trị viên, không tin
    read_only_hint: bool | None = None


@dataclass(frozen=True)
class ToolCallResult:
    ok: bool  # False = lỗi giao thức/thực thi (is_error), KHÔNG phải lỗi nghiệp vụ
    data: dict[str, Any] | list[Any]
    error: str | None = None


def _is_connect_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx2.ConnectError, ConnectionRefusedError)):
        return True
    inner = getattr(exc, "exceptions", None) or []
    return any(_is_connect_error(e) for e in inner) or (
        exc.__cause__ is not None and _is_connect_error(exc.__cause__)
    )


def parse_tool_content(result: Any) -> dict[str, Any] | list[Any]:
    """Kết quả tool (TextContent JSON) -> dict/list; văn bản thường bọc {"gia_tri": ...}."""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, (dict, list)) and structured:
        return structured
    texts = [getattr(c, "text", "") for c in (result.content or []) if getattr(c, "text", None)]
    text = "\n".join(texts)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"gia_tri": text}
    return parsed if isinstance(parsed, (dict, list)) else {"gia_tri": parsed}


class McpClient:
    def __init__(self, targets: Mapping[str, McpTarget], token: str | None = None) -> None:
        self._targets = dict(targets)
        self._token = token

    @property
    def servers(self) -> list[str]:
        return list(self._targets)

    def set_target(self, server: str, target: McpTarget) -> None:
        self._targets[server] = target

    async def preview(self, target: McpTarget) -> list[ToolSpec]:
        """Kết nối thử một server CHƯA đăng ký (cùng token), liệt kê tool; không đổi danh sách."""
        probe = McpClient({PREVIEW_SERVER: target}, token=self._token)
        return await probe.list_tools(PREVIEW_SERVER)

    def _bearer(self, target: str, tool: str | None, args: dict[str, Any] | None) -> str:
        if self._token:  # token cố định truyền vào (test / công cụ dòng lệnh)
            return self._token
        settings = get_settings()
        if settings.mcp_auth_mode != "oauth":
            return settings.internal_api_token
        ma_sv = (args or {}).get("ma_sv")
        return issue_mcp_token(target, tool=tool, subject=str(ma_sv) if ma_sv else None)

    def _client(
        self, server: str, tool: str | None = None, args: dict[str, Any] | None = None
    ) -> Client:
        target = self._targets.get(server)
        if target is None:
            raise McpUnavailableError(f"Chưa cấu hình MCP server '{server}'.")
        if isinstance(target, MCPServer):
            return Client(target)
        token = self._bearer(target, tool, args)
        http = httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT_SECONDS
        )
        return Client(streamable_http_client(target, http_client=http))

    async def list_tools(self, server: str) -> list[ToolSpec]:
        for attempt in range(CONNECT_RETRIES + 1):
            try:
                async with self._client(server) as client:
                    tools = (await client.list_tools()).tools
                return [
                    ToolSpec(
                        server,
                        t.name,
                        t.description or "",
                        dict(t.input_schema),
                        title=t.title or None,
                        read_only_hint=t.annotations.read_only_hint if t.annotations else None,
                    )
                    for t in tools
                ]
            except Exception as exc:
                if _is_connect_error(exc) and attempt < CONNECT_RETRIES:
                    continue
                raise McpUnavailableError(f"Không kết nối được MCP server '{server}'.") from exc
        raise AssertionError("unreachable")

    async def call_tool(self, server: str, name: str, args: dict[str, Any]) -> ToolCallResult:
        for attempt in range(CONNECT_RETRIES + 1):
            try:
                async with self._client(server, name, args) as client:
                    result = await client.call_tool(name, args)
            except Exception as exc:
                if _is_connect_error(exc):
                    if attempt < CONNECT_RETRIES:
                        logger.warning("Kết nối %s lỗi, thử lại...", server)
                        continue
                    raise McpUnavailableError(f"Không kết nối được MCP server '{server}'.") from exc
                raise
            if result.is_error:
                texts = [getattr(c, "text", "") for c in result.content or []]
                message = " ".join(t for t in texts if t) or "Công cụ báo lỗi."
                return ToolCallResult(False, {"loi": message}, message)
            return ToolCallResult(True, parse_tool_content(result))
        raise AssertionError("unreachable")
