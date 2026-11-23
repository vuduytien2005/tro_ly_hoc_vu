"""McpClient cấp token OAuth cho từng lần gọi; chạy đầu-cuối qua HTTP thật (uvicorn)."""

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import anyio
import pytest
import uvicorn

from src.assistant_api.mcp_client.client import McpClient
from src.mcp_servers import dao_tao
from src.mcp_servers.common import build_app
from src.shared.config import get_settings
from src.shared.oauth import SCOPE_LIST, JwtVerifier, get_key_store, tool_scope

URL = "http://127.0.0.1:9101/mcp"


def claims_of(token: str, resource: str = URL) -> Any:
    async def load() -> dict[str, Any]:
        return get_key_store().jwks()

    return anyio.run(JwtVerifier(resource, loader=load).verify_token, token)


def test_call_token_bound_to_server_tool_and_student() -> None:
    token = McpClient({"dao_tao": URL})._bearer(URL, "get_transcript", {"ma_sv": "SV22001"})
    access = claims_of(token)
    assert access is not None
    assert (access.subject, access.scopes) == ("SV22001", [tool_scope("get_transcript")])
    assert claims_of(token, "http://127.0.0.1:9102/mcp") is None  # không dùng được ở ctsv


def test_list_token_has_no_student() -> None:
    access = claims_of(McpClient({})._bearer(URL, None, None))
    assert access is not None
    assert (access.subject, access.scopes) == ("assistant_api", [SCOPE_LIST])


def test_each_call_gets_a_fresh_token() -> None:
    client = McpClient({})
    assert client._bearer(URL, "x", None) != client._bearer(URL, "x", None)  # jti khác nhau


def test_legacy_and_explicit_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    assert McpClient({}, token="co-dinh")._bearer(URL, "x", None) == "co-dinh"
    monkeypatch.setattr(get_settings(), "mcp_auth_mode", "token")
    assert McpClient({})._bearer(URL, "x", None) == get_settings().internal_api_token


# ----- Đầu-cuối: McpClient -> HTTP -> McpAuthMiddleware (JWKS từ tệp công khai) -> công cụ ------
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live_dao_tao() -> Iterator[str]:
    get_key_store().ensure()  # như assistant_api lúc khởi động: có khóa + tệp JWKS công khai
    port = _free_port()
    # assistant_api không chạy trong test -> JwtVerifier mặc định rơi về tệp JWKS công khai
    server = uvicorn.Server(
        uvicorn.Config(
            build_app(dao_tao.mcp, port), host="127.0.0.1", port=port, log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn không khởi động được"
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_end_to_end_over_http(live_dao_tao: str) -> None:
    client = McpClient({"dao_tao": live_dao_tao})
    names = {t.name for t in anyio.run(client.list_tools, "dao_tao")}
    assert "get_transcript" in names

    # Giả lập assistant_api có lỗi: token cấp cho SV22001 (sinh viên đang đăng nhập) nhưng tham
    # số lại mang ma_sv của SV21001 -> MCP server phải chặn trước khi đọc dữ liệu
    original = client._bearer
    client._bearer = lambda target, tool, args, scope=None: original(  # type: ignore[method-assign]
        target, tool, {"ma_sv": "SV22001"}, scope
    )
    result = anyio.run(client.call_tool, "dao_tao", "get_student_profile", {"ma_sv": "SV21001"})
    assert result.data["ma_loi"] == "KHONG_DU_QUYEN"
