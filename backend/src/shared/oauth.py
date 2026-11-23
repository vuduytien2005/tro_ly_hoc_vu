"""OAuth 2.1 cho MCP: token truy cập JWT ngắn hạn, ký Ed25519 (bổ sung 23/11/2026).

Vai trò (MCP Authorization):
- assistant_api = authorization server + client duy nhất: `issue_mcp_token()` cấp token cho MỘT lần
  gọi (cùng tiến trình nên không cần endpoint /oauth/token; tương đương grant client_credentials
  kèm resource indicator RFC 8707).
- MCP server = resource server: `JwtVerifier` kiểm chữ ký bằng khóa CÔNG KHAI tải từ JWKS của
  assistant_api, kiểm `iss`, `aud` (đúng server này), `exp`.

Claim: iss, aud (URL MCP server), sub (ma_sv hoặc "assistant_api"), scope ("mcp:tool:<tên>" |
"mcp:tools.list"), client_id, iat, exp, jti.
Thiết kế: docs/superpowers/specs/2026-11-23-oauth-mcp-design.md.
"""

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from jwt.algorithms import OKPAlgorithm
from mcp.server.auth.provider import AccessToken

from src.shared.config import get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "EdDSA"
CLIENT_ID = "assistant_api"
SERVICE_SUBJECT = "assistant_api"  # token không thay mặt sinh viên nào (liệt kê công cụ...)
SCOPE_LIST = "mcp:tools.list"
LEEWAY_SECONDS = 10  # chênh đồng hồ giữa các tiến trình (cùng máy -> rất nhỏ)
JWKS_REFRESH_MIN_SECONDS = 30.0


def tool_scope(tool: str) -> str:
    return f"mcp:tool:{tool}"


# ----- Định danh tài nguyên (RFC 8707) -------------------------------------------------------
LOOPBACK = ("127.0.0.1", "localhost")


def normalize_resource(url: str) -> str:
    """Dạng chuẩn để so `aud`: chữ thường scheme/host, bỏ "/" cuối, bỏ query/fragment."""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def resource_aliases(url: str) -> set[str]:
    """127.0.0.1 và localhost là một máy: quản trị viên khai URL kiểu nào cũng khớp."""
    canon = normalize_resource(url)
    parts = urlsplit(canon)
    host, _, port = parts.netloc.partition(":")
    if host not in LOOPBACK:
        return {canon}
    return {
        urlunsplit((parts.scheme, f"{h}:{port}" if port else h, parts.path, "", ""))
        for h in LOOPBACK
    }


# ----- Khóa ký (chỉ assistant_api) ------------------------------------------------------------
def public_jwks_path(key_path: Path) -> Path:
    return key_path.with_name(key_path.stem + ".jwks.json")


def _kid_of(public_key: Ed25519PublicKey) -> str:
    """Mã khóa = 16 ký tự đầu SHA-256 của khóa công khai (đổi khóa -> đổi kid)."""
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def _jwks_of(public_key: Ed25519PublicKey) -> dict[str, Any]:
    jwk = json.loads(OKPAlgorithm.to_jwk(public_key))
    jwk.update(kid=_kid_of(public_key), alg=ALGORITHM, use="sig")
    return {"keys": [jwk]}


class KeyStore:
    """Khóa Ed25519 lưu dạng PEM; chưa có thì tự sinh. Thư mục data/keys/ không commit."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._key: Ed25519PrivateKey | None = None

    @property
    def private_key(self) -> Ed25519PrivateKey:
        with self._lock:
            if self._key is None:
                self._key = self._load_or_create()
                self._publish_jwks_file(self._key)
            return self._key

    def ensure(self) -> str:
        """Nạp (hoặc tạo) khóa ngay, kèm ghi tệp JWKS công khai; trả kid."""
        return self.kid

    @property
    def jwks_path(self) -> Path:
        return public_jwks_path(self.path)

    def _publish_jwks_file(self, key: Ed25519PrivateKey) -> None:
        """Ghi JWKS (chỉ khóa CÔNG KHAI) cạnh khóa ký: MCP server đọc khi chưa gọi được HTTP
        (lúc assistant_api đang khởi động thì chính nó gọi MCP server mà chưa mở cổng)."""
        try:
            self.jwks_path.write_text(json.dumps(_jwks_of(key.public_key())), encoding="utf-8")
        except OSError as exc:
            logger.warning("Không ghi được %s: %s", self.jwks_path, exc)

    def _load_or_create(self) -> Ed25519PrivateKey:
        if not self.path.is_file():
            key = Ed25519PrivateKey.generate()
            pem = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # O_EXCL: hai tiến trình cùng tạo thì chỉ một bên ghi, bên kia đọc lại tệp đó
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as f:
                    f.write(pem)
                logger.info("Đã tạo khóa ký OAuth cho MCP: %s", self.path)
                return key
        loaded = serialization.load_pem_private_key(self.path.read_bytes(), password=None)
        if not isinstance(loaded, Ed25519PrivateKey):
            raise ValueError(f"{self.path} không phải khóa Ed25519.")
        return loaded

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    @property
    def kid(self) -> str:
        """Mã khóa = 16 ký tự đầu SHA-256 của khóa công khai (đổi khóa -> đổi kid)."""
        raw = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return hashlib.sha256(raw).hexdigest()[:16]

    def jwks(self) -> dict[str, Any]:
        return _jwks_of(self.public_key)


@lru_cache
def get_key_store() -> KeyStore:
    return KeyStore(get_settings().oauth_key_path)


def issue_mcp_token(
    resource: str,
    *,
    tool: str | None = None,
    subject: str | None = None,
    key_store: KeyStore | None = None,
) -> str:
    """Token cho MỘT lần gọi tới `resource`: gọi công cụ `tool`, hoặc liệt kê (tool=None)."""
    settings = get_settings()
    store = key_store or get_key_store()
    now = int(time.time())
    claims = {
        "iss": settings.oauth_issuer_url,
        "aud": normalize_resource(resource),
        "sub": subject or SERVICE_SUBJECT,
        "client_id": CLIENT_ID,
        "scope": tool_scope(tool) if tool else SCOPE_LIST,
        "iat": now,
        "exp": now + settings.oauth_token_ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, store.private_key, algorithm=ALGORITHM, headers={"kid": store.kid})


# ----- Kiểm token (MCP server) ----------------------------------------------------------------
JwksLoader = Callable[[], Awaitable[dict[str, Any]]]


def default_jwks_loader(issuer: str, public_file: Path | None = None) -> JwksLoader:
    """JWKS qua HTTP từ authorization server (chuẩn); không gọi được thì đọc tệp JWKS công khai
    assistant_api ghi cạnh khóa ký (cùng máy, chỉ chứa khóa công khai)."""
    path = public_file or public_jwks_path(get_settings().oauth_key_path)

    async def load() -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{issuer}/.well-known/jwks.json")
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
        except (httpx.HTTPError, ValueError):
            if not path.is_file():
                raise
            from_file: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return from_file

    return load


class JwtVerifier:
    """TokenVerifier (giao thức của SDK `mcp`) cho MCP server có URL `resource_url`."""

    def __init__(
        self, resource_url: str, loader: JwksLoader | None = None, issuer: str | None = None
    ) -> None:
        self.resource_url = normalize_resource(resource_url)
        self.audiences = resource_aliases(resource_url)
        self.issuer = (issuer or get_settings().oauth_issuer_url).rstrip("/")
        self._loader = loader or default_jwks_loader(self.issuer)
        self._keys: dict[str, Ed25519PublicKey] = {}
        self._loaded_at: float | None = None

    async def _refresh(self) -> None:
        if (
            self._loaded_at is not None
            and time.monotonic() - self._loaded_at < JWKS_REFRESH_MIN_SECONDS
        ):
            return  # không tải dồn dập khi bị gửi token có kid lạ
        try:
            jwks = await self._loader()
        except Exception as exc:  # assistant_api chưa chạy...
            logger.warning("Không tải được JWKS từ %s: %s", self.issuer, exc)
            return
        keys: dict[str, Ed25519PublicKey] = {}
        for jwk in jwks.get("keys", []):
            if jwk.get("kty") == "OKP" and jwk.get("crv") == "Ed25519" and jwk.get("kid"):
                key = OKPAlgorithm.from_jwk(json.dumps(jwk))
                if isinstance(key, Ed25519PublicKey):
                    keys[str(jwk["kid"])] = key
        self._keys, self._loaded_at = keys, time.monotonic()

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError:
            return None
        if not isinstance(kid, str):
            return None
        if kid not in self._keys:
            await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            return None
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],  # cố định thuật toán: chặn "alg=none" / đổi thuật toán
                audience=list(self.audiences),
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "aud", "iss", "sub", "scope"]},
            )
        except jwt.PyJWTError:
            return None
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or ""),
            scopes=str(claims["scope"]).split(),
            expires_at=int(claims["exp"]),
            resource=self.resource_url,
            subject=str(claims["sub"]),
            claims={"iss": claims["iss"], "jti": claims.get("jti")},
        )
