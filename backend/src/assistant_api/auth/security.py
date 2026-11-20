"""Mật khẩu (bcrypt) và JWT (HS256).

JWT chứa: sub = id người dùng (chuỗi), vai_tro, iat, exp. Thông tin khác (ma_sv, ma_khoa) luôn
đọc lại từ CSDL khi xử lý request -> khóa tài khoản / đổi khóa có hiệu lực ngay.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from src.shared.config import get_settings

ALGORITHM = "HS256"
# Băm sẵn một mật khẩu giả để so khi email không tồn tại -> thời gian phản hồi như nhau,
# không dò được email nào có tài khoản.
_DUMMY_HASH = bcrypt.hashpw(b"khong-phai-mat-khau-that", bcrypt.gensalt(rounds=12))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    candidate = password.encode("utf-8")
    if not password_hash:
        bcrypt.checkpw(candidate, _DUMMY_HASH)
        return False
    try:
        return bcrypt.checkpw(candidate, password_hash.encode("utf-8"))
    except ValueError:  # hash hỏng
        return False


def create_access_token(user_id: int, vai_tro: str) -> tuple[str, datetime]:
    # Dùng đồng hồ THẬT (không dùng DEMO_NOW): PyJWT kiểm tra exp/iat theo giờ hệ thống
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "vai_tro": vai_tro, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires


def decode_access_token(token: str) -> dict[str, Any]:
    """Ném jwt.InvalidTokenError (gồm ExpiredSignatureError) nếu token không hợp lệ."""
    return jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )
