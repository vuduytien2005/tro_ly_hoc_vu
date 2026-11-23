"""assistant_api là authorization server cho các MCP server (OAuth 2.1, bổ sung 23/11/2026).

- /.well-known/jwks.json: khóa CÔNG KHAI Ed25519 để MCP server kiểm chữ ký token.
- /.well-known/oauth-authorization-server (RFC 8414): mô tả issuer, jwks_uri, scope.
Không có /oauth/token qua HTTP: client duy nhất (McpClient) chạy trong chính assistant_api.
"""

from typing import Any

from fastapi import APIRouter

from src.shared.config import get_settings
from src.shared.oauth import SCOPE_LIST, get_key_store

router = APIRouter(tags=["OAuth cho MCP"])


@router.get("/.well-known/jwks.json", summary="Khóa công khai ký token MCP (JWKS)")
def jwks() -> dict[str, Any]:
    return get_key_store().jwks()


@router.get(
    "/.well-known/oauth-authorization-server",
    summary="Siêu dữ liệu authorization server (RFC 8414)",
)
def authorization_server_metadata() -> dict[str, Any]:
    issuer = get_settings().oauth_issuer_url
    return {
        "issuer": issuer,
        "jwks_uri": f"{issuer}/.well-known/jwks.json",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["none"],
        "response_types_supported": [],
        "scopes_supported": [SCOPE_LIST, "mcp:tool:<tên công cụ>"],
        "authorization_details": (
            "Client duy nhất chạy trong assistant_api: token cấp bằng lời gọi hàm, gắn aud = URL "
            "MCP server (RFC 8707), sub = mã sinh viên, sống 60 giây."
        ),
    }
