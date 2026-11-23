"""Dependency dùng chung: phiên CSDL, thời gian, người dùng hiện tại, phân quyền."""

import hmac
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.assistant_api.auth.cookies import CSRF_HEADER, SESSION_COOKIE
from src.assistant_api.auth.security import decode_access_token
from src.assistant_api.errors import forbidden, unauthorized
from src.assistant_api.models import NguoiDung
from src.shared.db import assistant_session_factory
from src.shared.time import now as current_time


def get_db() -> Iterator[Session]:
    with assistant_session_factory()() as session:
        yield session


def get_now() -> datetime:
    return current_time()


DbSession = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]

_bearer = HTTPBearer(auto_error=False, description="JWT nhận từ /api/auth/login")


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> NguoiDung:
    """Xác thực bằng header `Authorization: Bearer` (API, thực nghiệm) hoặc cookie HttpOnly
    `SESSION_COOKIE` (web). Cookie trình duyệt TỰ gửi -> yêu cầu thay đổi dữ liệu phải kèm
    `X-CSRF-Token` trùng claim `csrf` trong JWT (chống CSRF); header Bearer thì không cần."""
    from_cookie = False
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif request.cookies.get(SESSION_COOKIE):
        token, from_cookie = request.cookies[SESSION_COOKIE], True
    else:
        raise unauthorized("CHUA_DANG_NHAP", "Bạn cần đăng nhập để tiếp tục.")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized(
            "PHIEN_HET_HAN", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại."
        ) from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise unauthorized("TOKEN_KHONG_HOP_LE", "Token đăng nhập không hợp lệ.") from exc
    if from_cookie and request.method not in SAFE_METHODS:
        expected = payload.get("csrf")
        sent = request.headers.get(CSRF_HEADER, "")
        if not isinstance(expected, str) or not hmac.compare_digest(expected, sent):
            raise forbidden(
                "CSRF_KHONG_HOP_LE", "Yêu cầu không hợp lệ, vui lòng tải lại trang rồi thử lại."
            )
    user = db.get(NguoiDung, user_id)
    if user is None:
        raise unauthorized("TOKEN_KHONG_HOP_LE", "Token đăng nhập không hợp lệ.")
    if not user.dang_hoat_dong:
        raise forbidden("TAI_KHOAN_BI_KHOA", "Tài khoản đã bị khóa, liên hệ quản trị viên.")
    return user


CurrentUser = Annotated[NguoiDung, Depends(get_current_user)]


def require_student(user: CurrentUser) -> NguoiDung:
    if user.vai_tro != "sinh_vien" or not user.ma_sv:
        raise forbidden("KHONG_DU_QUYEN", "Chức năng này chỉ dành cho sinh viên.")
    return user


def require_admin(user: CurrentUser) -> NguoiDung:
    if user.vai_tro != "admin":
        raise forbidden("KHONG_DU_QUYEN", "Chức năng này chỉ dành cho quản trị viên.")
    return user


Student = Annotated[NguoiDung, Depends(require_student)]
Admin = Annotated[NguoiDung, Depends(require_admin)]
