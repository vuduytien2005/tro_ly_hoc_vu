"""Dependency dùng chung: phiên CSDL, thời gian, người dùng hiện tại, phân quyền."""

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

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


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> NguoiDung:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("CHUA_DANG_NHAP", "Bạn cần đăng nhập để tiếp tục.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized(
            "PHIEN_HET_HAN", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại."
        ) from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise unauthorized("TOKEN_KHONG_HOP_LE", "Token đăng nhập không hợp lệ.") from exc
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
