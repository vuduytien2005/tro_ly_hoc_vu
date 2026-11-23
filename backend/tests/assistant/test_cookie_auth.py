"""Cookie phiên HttpOnly + chống CSRF (bổ sung 23/11/2026, thay JWT trong localStorage)."""

from fastapi.testclient import TestClient

from src.assistant_api.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from src.assistant_api.auth.security import create_access_token
from src.assistant_api.models import NguoiDung
from tests.assistant.conftest import PASSWORD


def cookie_login(client: TestClient, email: str) -> str:
    """Đăng nhập như trình duyệt: KHÔNG dùng access_token trong body; trả giá trị CSRF đọc từ
    cookie (như JavaScript của web)."""
    r = client.post("/api/auth/login", json={"email": email, "mat_khau": PASSWORD})
    assert r.status_code == 200, r.text
    return client.cookies[CSRF_COOKIE]


def test_login_sets_httponly_session_and_readable_csrf(
    client: TestClient, student: NguoiDung
) -> None:
    r = client.post("/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD})
    cookies = {c.split("=", 1)[0]: c.lower() for c in r.headers.get_list("set-cookie")}
    session = cookies[SESSION_COOKIE]
    assert "httponly" in session and "samesite=strict" in session and "path=/api" in session
    csrf = cookies[CSRF_COOKIE]
    assert "httponly" not in csrf and "samesite=strict" in csrf


def test_cookie_authenticates_reads(client: TestClient, student: NguoiDung) -> None:
    cookie_login(client, student.email)
    r = client.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == student.email


def test_cookie_write_requires_matching_csrf_header(client: TestClient, student: NguoiDung) -> None:
    csrf = cookie_login(client, student.email)
    # Trang độc gửi form tới API: trình duyệt tự kèm cookie, nhưng không đọc được giá trị CSRF
    r = client.post("/api/conversations", json={})
    assert r.status_code == 403 and r.json()["code"] == "CSRF_KHONG_HOP_LE"
    r = client.post("/api/conversations", json={}, headers={CSRF_HEADER: "doan-bua"})
    assert r.status_code == 403
    r = client.post("/api/conversations", json={}, headers={CSRF_HEADER: csrf})
    assert r.status_code == 201, r.text


def test_forged_csrf_cookie_does_not_help(client: TestClient, student: NguoiDung) -> None:
    """Kẻ tấn công ghi đè cookie CSRF (vd từ subdomain) rồi gửi header trùng cookie giả: vẫn bị
    chặn vì header phải trùng claim `csrf` ký trong JWT."""
    cookie_login(client, student.email)
    client.cookies.set(CSRF_COOKIE, "gia-tri-gia")
    r = client.post("/api/conversations", json={}, headers={CSRF_HEADER: "gia-tri-gia"})
    assert r.status_code == 403


def test_old_token_without_csrf_claim_cannot_write_via_cookie(
    client: TestClient, student: NguoiDung
) -> None:
    token, _ = create_access_token(student.id, student.vai_tro)  # không có claim csrf
    client.cookies.set(SESSION_COOKIE, token, path="/api")
    assert client.get("/api/auth/me").status_code == 200
    r = client.post("/api/conversations", json={}, headers={CSRF_HEADER: ""})
    assert r.status_code == 403


def test_bearer_header_needs_no_csrf(client: TestClient, student: NguoiDung) -> None:
    """API / thực nghiệm: header Authorization không bị trình duyệt tự gửi -> không cần CSRF."""
    token = client.post(
        "/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD}
    ).json()["access_token"]
    client.cookies.clear()
    r = client.post("/api/conversations", json={}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_logout_clears_cookies(client: TestClient, student: NguoiDung) -> None:
    cookie_login(client, student.email)
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert SESSION_COOKIE not in client.cookies and CSRF_COOKIE not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
