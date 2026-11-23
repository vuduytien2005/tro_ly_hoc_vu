"""QlsvClient + chuẩn trả lỗi + xác thực (OAuth 2.1 / token nội bộ) của MCP server."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from src.mcp_servers import dao_tao
from src.mcp_servers.common import QlsvError, build_app, path_segment, qlsv, tool_errors
from src.shared.config import get_settings
from src.shared.oauth import JwtVerifier, KeyStore, issue_mcp_token
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


# --- Xác thực trên transport HTTP (OAuth 2.1, bổ sung 23/11/2026) -----------------------------
DAO_TAO_URL = "http://127.0.0.1:9101/mcp"


@pytest.fixture
def keys(tmp_path: Path) -> KeyStore:
    return KeyStore(tmp_path / "oauth.pem")


@pytest.fixture
def http_client(keys: KeyStore) -> Iterator[TestClient]:
    async def load() -> dict[str, Any]:
        return keys.jwks()

    app = build_app(dao_tao.mcp, 9101, verifier=JwtVerifier(DAO_TAO_URL, loader=load))
    with TestClient(app, base_url="http://127.0.0.1:9101") as client:
        yield client


def bearer(token: str) -> dict[str, str]:
    return {**ACCEPT, "Authorization": f"Bearer {token}"}


def call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }


def tool_result(r: Any) -> dict[str, Any]:
    result = r.json()["result"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_missing_token_rejected_with_resource_metadata(http_client: TestClient) -> None:
    r = http_client.post("/mcp", json=INIT, headers=ACCEPT)
    assert r.status_code == 401
    assert r.json()["code"] == "THIEU_TOKEN"
    challenge = r.headers["www-authenticate"]
    assert 'resource_metadata="http://127.0.0.1:9101/.well-known/oauth-protected-resource/mcp"' in (
        challenge
    )


def test_protected_resource_metadata_is_public(http_client: TestClient) -> None:
    meta = http_client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert meta["resource"] == DAO_TAO_URL
    assert meta["authorization_servers"] == [get_settings().oauth_issuer_url]


def test_shared_internal_token_no_longer_opens_mcp(http_client: TestClient) -> None:
    """Token nội bộ dùng chung (cách cũ) không còn mở được /mcp ở chế độ OAuth."""
    r = http_client.post("/mcp", json=INIT, headers=bearer(get_settings().internal_api_token))
    assert r.status_code == 401
    assert r.json()["code"] == "TOKEN_KHONG_HOP_LE"


def test_x_internal_token_header_not_accepted(http_client: TestClient) -> None:
    headers = {**ACCEPT, INTERNAL_TOKEN_HEADER: get_settings().internal_api_token}
    assert http_client.post("/mcp", json=INIT, headers=headers).status_code == 401


def test_valid_token_initialize_and_list_tools(http_client: TestClient, keys: KeyStore) -> None:
    headers = bearer(issue_mcp_token(DAO_TAO_URL, key_store=keys))
    r = http_client.post("/mcp", json=INIT, headers=headers)
    assert r.status_code == 200
    assert r.json()["result"]["serverInfo"]["name"] == "dao_tao"
    r = http_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers=headers,
    )
    assert r.status_code == 200
    assert "get_transcript" in {t["name"] for t in r.json()["result"]["tools"]}


def test_token_for_other_server_rejected(http_client: TestClient, keys: KeyStore) -> None:
    """Server độc (vd thu_vien giả) nhận token của nó rồi đem dùng lại ở dao_tao: bị chặn."""
    token = issue_mcp_token("http://127.0.0.1:9105/mcp", key_store=keys)
    assert http_client.post("/mcp", json=INIT, headers=bearer(token)).status_code == 401


def test_tool_call_for_another_student_rejected(http_client: TestClient, keys: KeyStore) -> None:
    """Phòng thủ nhiều lớp: token của SV22001 không đọc được hồ sơ SV21001 (kể cả khi
    assistant_api tiêm sai ma_sv). Bị chặn TRƯỚC khi gọi qlsv_api."""
    token = issue_mcp_token(
        DAO_TAO_URL, tool="get_student_profile", subject="SV22001", key_store=keys
    )
    r = http_client.post(
        "/mcp", json=call("get_student_profile", {"ma_sv": "SV21001"}), headers=bearer(token)
    )
    assert r.status_code == 200
    assert tool_result(r)["ma_loi"] == "KHONG_DU_QUYEN"


def test_tool_call_outside_scope_rejected(http_client: TestClient, keys: KeyStore) -> None:
    token = issue_mcp_token(
        DAO_TAO_URL, tool="get_exam_schedule", subject="SV22001", key_store=keys
    )
    r = http_client.post(
        "/mcp", json=call("get_student_profile", {"ma_sv": "SV22001"}), headers=bearer(token)
    )
    assert tool_result(r)["ma_loi"] == "KHONG_DU_QUYEN"


def test_tool_call_allowed_for_own_data(
    http_client: TestClient, keys: KeyStore, qlsv_mock: respx.MockRouter
) -> None:
    qlsv_mock.get("/internal/students/SV22001").respond(
        200,
        json={
            "ma_sv": "SV22001",
            "ho_ten": "Nguyễn Văn An",
            "email": "an@example.com",
            "lop": "KTPM2022",
            "nganh": "Kỹ thuật phần mềm",
            "khoa": "K22",
            "trang_thai": "dang_hoc",
            "canh_bao_hoc_vu": 0,
        },
    )
    token = issue_mcp_token(
        DAO_TAO_URL, tool="get_student_profile", subject="SV22001", key_store=keys
    )
    r = http_client.post(
        "/mcp", json=call("get_student_profile", {"ma_sv": "SV22001"}), headers=bearer(token)
    )
    assert "ma_loi" not in tool_result(r)


def test_legacy_token_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP_AUTH_MODE=token: quay về Bearer INTERNAL_API_TOKEN (để so sánh / khẩn cấp)."""
    monkeypatch.setattr(get_settings(), "mcp_auth_mode", "token")
    with TestClient(build_app(dao_tao.mcp, 9101), base_url="http://127.0.0.1:9101") as c:
        ok = c.post("/mcp", json=INIT, headers=bearer(get_settings().internal_api_token))
        assert ok.status_code == 200
        assert c.post("/mcp", json=INIT, headers=bearer("sai")).status_code == 401


def test_foreign_host_rejected(keys: KeyStore) -> None:
    """Chống DNS rebinding: Host khác 127.0.0.1/localhost bị chặn dù token đúng."""

    async def load() -> dict[str, Any]:
        return keys.jwks()

    app = build_app(dao_tao.mcp, 9101, verifier=JwtVerifier(DAO_TAO_URL, loader=load))
    with TestClient(app, base_url="http://evil.example") as client:
        headers = bearer(issue_mcp_token(DAO_TAO_URL, key_store=keys))
        assert client.post("/mcp", json=INIT, headers=headers).status_code == 421
