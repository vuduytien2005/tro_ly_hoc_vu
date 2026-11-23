"""Đăng nhập (JWT) và thông tin tài khoản hiện tại.

Đăng nhập đặt cookie HttpOnly cho web (auth/cookies.py) và vẫn trả `access_token` trong body cho
API / thực nghiệm (web KHÔNG lưu giá trị này).
"""

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from src.assistant_api.auth.cookies import clear_session_cookies, set_session_cookies
from src.assistant_api.auth.security import (
    create_access_token,
    new_csrf_token,
    verify_password,
)
from src.assistant_api.deps import CurrentUser, DbSession
from src.assistant_api.errors import forbidden, unauthorized
from src.assistant_api.models import NguoiDung
from src.assistant_api.schemas import LoginIn, LoginOut, UserOut
from src.shared.time import from_db

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])


@router.post("/login", response_model=LoginOut, summary="Đăng nhập bằng email + mật khẩu")
def login(body: LoginIn, db: DbSession, response: Response) -> LoginOut:
    user = db.scalar(select(NguoiDung).where(func.lower(NguoiDung.email) == body.email.lower()))
    # Luôn chạy bcrypt (kể cả email không tồn tại) và trả CÙNG một thông báo -> không dò được email
    if not verify_password(body.mat_khau, user.mat_khau_hash if user else None) or user is None:
        raise unauthorized("SAI_THONG_TIN_DANG_NHAP", "Email hoặc mật khẩu không đúng.")
    if not user.dang_hoat_dong:
        raise forbidden("TAI_KHOAN_BI_KHOA", "Tài khoản đã bị khóa, liên hệ quản trị viên.")
    csrf = new_csrf_token()
    token, expires = create_access_token(user.id, user.vai_tro, csrf)
    set_session_cookies(response, token, csrf, expires)
    return LoginOut(
        access_token=token, het_han_luc=from_db(expires), nguoi_dung=UserOut.model_validate(user)
    )


@router.post("/logout", status_code=204, summary="Đăng xuất: xóa cookie phiên")
def logout(response: Response) -> Response:
    # Không cần đăng nhập / CSRF: chỉ xóa cookie của chính trình duyệt gửi request
    clear_session_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut, summary="Thông tin tài khoản đang đăng nhập")
def me(user: CurrentUser) -> NguoiDung:
    return user
