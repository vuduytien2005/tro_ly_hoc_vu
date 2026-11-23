"""OAuth cho MCP: cấp token (assistant_api) và kiểm token (MCP server)."""

import time
from pathlib import Path
from typing import Any

import anyio
import jwt
import pytest

from src.shared.oauth import (
    SCOPE_LIST,
    JwtVerifier,
    KeyStore,
    default_jwks_loader,
    issue_mcp_token,
    normalize_resource,
    resource_aliases,
    tool_scope,
)

DAO_TAO = "http://127.0.0.1:9101/mcp"
THU_VIEN = "http://127.0.0.1:9105/mcp"


@pytest.fixture
def keys(tmp_path: Path) -> KeyStore:
    return KeyStore(tmp_path / "k" / "key.pem")


def verifier(keys: KeyStore, resource: str = DAO_TAO) -> JwtVerifier:
    async def load() -> dict[str, Any]:
        return keys.jwks()

    return JwtVerifier(resource, loader=load)


def verify(v: JwtVerifier, token: str) -> Any:
    return anyio.run(v.verify_token, token)


def test_key_is_created_once_and_reloaded(keys: KeyStore) -> None:
    kid = keys.kid
    assert keys.path.is_file()
    assert KeyStore(keys.path).kid == kid  # đọc lại cùng khóa
    jwk = keys.jwks()["keys"][0]
    assert (jwk["kty"], jwk["crv"], jwk["alg"], jwk["kid"]) == ("OKP", "Ed25519", "EdDSA", kid)
    assert "d" not in jwk  # JWKS chỉ có khóa CÔNG KHAI


def test_valid_token_carries_subject_and_scope(keys: KeyStore) -> None:
    token = issue_mcp_token(DAO_TAO, tool="get_transcript", subject="SV22001", key_store=keys)
    access = verify(verifier(keys), token)
    assert access is not None
    assert access.subject == "SV22001"
    assert access.scopes == [tool_scope("get_transcript")]
    assert access.resource == normalize_resource(DAO_TAO)
    assert access.expires_at and access.expires_at - time.time() <= 61


def test_list_token_has_list_scope(keys: KeyStore) -> None:
    access = verify(verifier(keys), issue_mcp_token(DAO_TAO, key_store=keys))
    assert access is not None and access.scopes == [SCOPE_LIST]
    assert access.subject == "assistant_api"


def test_token_for_another_server_is_rejected(keys: KeyStore) -> None:
    """Cốt lõi: token cấp cho thu_vien (có thể là server độc) không dùng lại được ở dao_tao."""
    stolen = issue_mcp_token(THU_VIEN, tool="get_borrowed_books", subject="SV22001", key_store=keys)
    assert verify(verifier(keys, DAO_TAO), stolen) is None
    assert verify(verifier(keys, THU_VIEN), stolen) is not None


def test_localhost_alias_accepted(keys: KeyStore) -> None:
    token = issue_mcp_token("http://localhost:9101/mcp/", key_store=keys)
    assert verify(verifier(keys, DAO_TAO), token) is not None
    assert resource_aliases(DAO_TAO) == {DAO_TAO, "http://localhost:9101/mcp"}
    assert resource_aliases("https://mcp.example.com/mcp") == {"https://mcp.example.com/mcp"}


def test_expired_token_rejected(keys: KeyStore, monkeypatch: pytest.MonkeyPatch) -> None:
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() - 3600)
    old = issue_mcp_token(DAO_TAO, key_store=keys)
    monkeypatch.setattr(time, "time", real)
    assert verify(verifier(keys), old) is None


def test_token_signed_by_other_key_rejected(keys: KeyStore, tmp_path: Path) -> None:
    forged = issue_mcp_token(DAO_TAO, key_store=KeyStore(tmp_path / "attacker.pem"))
    assert verify(verifier(keys), forged) is None


@pytest.mark.parametrize("alg", ["none", "HS256"])
def test_algorithm_confusion_rejected(keys: KeyStore, alg: str) -> None:
    claims = {
        "iss": "http://127.0.0.1:8000",
        "aud": DAO_TAO,
        "sub": "SV22001",
        "scope": SCOPE_LIST,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    secret = "khoa-cong-khai-dung-lam-bi-mat-hmac-0123456789" if alg == "HS256" else None
    token = jwt.encode(claims, secret, algorithm=alg, headers={"kid": keys.kid})
    assert verify(verifier(keys), token) is None


def test_wrong_issuer_and_garbage_rejected(keys: KeyStore) -> None:
    v = verifier(keys)
    v.issuer = "http://127.0.0.1:9999"
    assert verify(v, issue_mcp_token(DAO_TAO, key_store=keys)) is None
    assert verify(verifier(keys), "khong-phai-jwt") is None


def test_jwks_unavailable_means_reject_not_crash(keys: KeyStore) -> None:
    async def down() -> dict[str, Any]:
        raise OSError("assistant_api chưa chạy")

    v = JwtVerifier(DAO_TAO, loader=down)
    assert verify(v, issue_mcp_token(DAO_TAO, key_store=keys)) is None


def test_public_jwks_file_fallback(keys: KeyStore) -> None:
    """assistant_api đang khởi động (chưa mở cổng) -> MCP server đọc tệp JWKS công khai."""
    token = issue_mcp_token(DAO_TAO, key_store=keys)  # tạo khóa -> ghi kèm tệp .jwks.json
    assert keys.jwks_path.is_file()
    assert "PRIVATE" not in keys.jwks_path.read_text(encoding="utf-8")
    loader = default_jwks_loader("http://127.0.0.1:1", public_file=keys.jwks_path)  # cổng đóng
    assert verify(JwtVerifier(DAO_TAO, loader=loader), token) is not None
