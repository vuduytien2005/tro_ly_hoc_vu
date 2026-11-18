"""QlsvClient + chuẩn trả lỗi + xác thực Bearer của MCP server."""

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from src.mcp_servers import dao_tao
from src.mcp_servers.common import QlsvError, build_app, path_segment, qlsv, tool_errors
from src.shared.config import get_settings
from src.shared.security import INTERNAL_TOKEN_HEADER

pytestmark = pytest.mark.anyio

ACCEPT = {"Accept": "application/json, text/event-stream"}
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}


# --- QlsvClient -----------------------------------------------------------
async def test_sends_internal_token(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/internal/students/SV22001").respond(200, json={"ok": True})
    assert await qlsv.get("/internal/students/SV22001") == {"ok": True}
    sent = route.calls.last.request
    assert sent.headers[INTERNAL_TOKEN_HEADER] == get_settings().internal_api_token


async def test_drops_empty_query_params(qlsv_mock: respx.MockRouter) -> None:
    route = qlsv_mock.get("/x").respond(200, json={})
    await qlsv.get("/x", ma_hoc_ky=None, q="IT004", trang_thai="")
    assert dict(route.calls.last.request.url.params) == {"q": "IT004"}


async def test_business_error_keeps_code_and_detail(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/x").respond(409, json={"detail": "Lớp đã đầy.", "code": "LOP_DA_DAY"})
    with pytest.raises(QlsvError) as exc:
        await qlsv.get("/x")
    assert (exc.value.code, exc.value.message, exc.value.status) == (
        "LOP_DA_DAY",
        "Lớp đã đầy.",
        409,
    )


async def test_non_json_error(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/x").respond(502, text="Bad gateway")
    with pytest.raises(QlsvError) as exc:
        await qlsv.get("/x")
    assert exc.value.code == "QLSV_LOI_502"


async def test_connection_error(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/x").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(QlsvError) as exc:
        await qlsv.get("/x")
    assert exc.value.code == "QLSV_KHONG_KET_NOI"


async def test_timeout(qlsv_mock: respx.MockRouter) -> None:
    qlsv_mock.get("/x").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(QlsvError) as exc:
        await qlsv.get("/x")
    assert exc.value.code == "QLSV_QUA_THOI_GIAN"


def test_path_segment_blocks_traversal() -> None:
    assert path_segment("../admin") == "..%2Fadmin"
    assert path_segment(" SV22001 ") == "SV22001"


# --- tool_errors ----------------------------------------------------------
async def test_tool_errors_wraps_qlsv_error() -> None:
    @tool_errors
    async def boom() -> dict:
        raise QlsvError("SV_KHONG_TON_TAI", "Không tìm thấy sinh viên.", 404)

    assert await boom() == {
        "thanh_cong": False,
        "ma_loi": "SV_KHONG_TON_TAI",
        "thong_bao": "Không tìm thấy sinh viên.",
    }


async def test_tool_errors_hides_unexpected_exception() -> None:
    @tool_errors
    async def boom() -> dict:
        raise KeyError("secret internal detail")

    result = await boom()
    assert result["ma_loi"] == "LOI_HE_THONG"
    assert "secret" not in result["thong_bao"]


# --- Xác thực Bearer trên transport HTTP ----------------------------------
@pytest.fixture
def http_client():
    with TestClient(build_app(dao_tao.mcp), base_url="http://127.0.0.1:9101") as client:
        yield client


def test_missing_token_rejected(http_client: TestClient) -> None:
    r = http_client.post("/mcp", json=INIT, headers=ACCEPT)
    assert r.status_code == 401
    assert r.json()["code"] == "THIEU_TOKEN"


def test_wrong_token_rejected(http_client: TestClient) -> None:
    r = http_client.post("/mcp", json=INIT, headers={**ACCEPT, "Authorization": "Bearer sai-token"})
    assert r.status_code == 401
    assert r.json()["code"] == "TOKEN_KHONG_HOP_LE"


def test_x_internal_token_header_not_accepted(http_client: TestClient) -> None:
    """MCP server chỉ nhận Bearer; header của qlsv_api không thay thế được."""
    headers = {**ACCEPT, INTERNAL_TOKEN_HEADER: get_settings().internal_api_token}
    assert http_client.post("/mcp", json=INIT, headers=headers).status_code == 401


def test_valid_token_initialize_and_list_tools(http_client: TestClient) -> None:
    headers = {**ACCEPT, "Authorization": f"Bearer {get_settings().internal_api_token}"}
    r = http_client.post("/mcp", json=INIT, headers=headers)
    assert r.status_code == 200
    assert r.json()["result"]["serverInfo"]["name"] == "dao_tao"

    r = http_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers=headers,
    )
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert "get_transcript" in names


def test_foreign_host_rejected() -> None:
    """Chống DNS rebinding: Host khác 127.0.0.1/localhost bị chặn dù token đúng."""
    with TestClient(build_app(dao_tao.mcp), base_url="http://evil.example") as client:
        headers = {**ACCEPT, "Authorization": f"Bearer {get_settings().internal_api_token}"}
        assert client.post("/mcp", json=INIT, headers=headers).status_code == 421
