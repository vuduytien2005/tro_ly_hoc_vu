"""assistant_api công bố JWKS + siêu dữ liệu authorization server (OAuth cho MCP)."""

from fastapi.testclient import TestClient

from src.shared.config import get_settings
from src.shared.oauth import get_key_store


def test_jwks_public_only(client: TestClient) -> None:
    body = client.get("/.well-known/jwks.json").json()
    [key] = body["keys"]
    assert key["kid"] == get_key_store().kid and key["alg"] == "EdDSA"
    assert "d" not in key  # phần bí mật của khóa Ed25519 không bao giờ lộ


def test_authorization_server_metadata(client: TestClient) -> None:
    meta = client.get("/.well-known/oauth-authorization-server").json()
    issuer = get_settings().oauth_issuer_url
    assert meta["issuer"] == issuer
    assert meta["jwks_uri"] == f"{issuer}/.well-known/jwks.json"
