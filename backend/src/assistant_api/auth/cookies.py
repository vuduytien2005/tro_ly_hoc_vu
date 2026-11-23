"""Cookie phiên đăng nhập của web (bổ sung 23/11/2026, thay cho JWT trong localStorage).

- `SESSION_COOKIE`: JWT, HttpOnly (JavaScript KHÔNG đọc được -> XSS không lấy được token),
  SameSite=Strict, Path=/api, Secure theo AUTH_COOKIE_SECURE.
- `CSRF_COOKIE`: giá trị chống CSRF, JavaScript đọc được để gửi lại trong header `CSRF_HEADER`.
  Giá trị này cũng nằm trong claim `csrf` của JWT (ký) -> so sánh header với claim
  ("signed double-submit"): trang web khác không đọc được cookie của ta nên không gửi đúng header.
Header `Authorization: Bearer` vẫn được chấp nhận cho thực nghiệm / công cụ dòng lệnh.
"""

from datetime import datetime

from fastapi import Response

from src.shared.config import get_settings

SESSION_COOKIE = "tlhv_phien"
CSRF_COOKIE = "tlhv_csrf"
CSRF_HEADER = "X-CSRF-Token"


def set_session_cookies(response: Response, token: str, csrf: str, expires: datetime) -> None:
    secure = get_settings().auth_cookie_secure
    max_age = max(0, int((expires - datetime.now(expires.tzinfo)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/api",
        httponly=True,
        samesite="strict",
        secure=secure,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        path="/",
        httponly=False,
        samesite="strict",
        secure=secure,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")
