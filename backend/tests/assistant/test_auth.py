"""Đăng nhập JWT, /me, phân quyền sinh viên/admin."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.assistant_api.auth.security import ALGORITHM, decode_access_token
from src.assistant_api.models import NguoiDung
from src.shared.config import get_settings
from tests.assistant.conftest import PASSWORD, login


def test_login_ok_returns_token_and_user(client: TestClient, student: NguoiDung) -> None:
    r = client.post("/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["nguoi_dung"]["ma_sv"] == "SV22001"
    assert "mat_khau_hash" not in body["nguoi_dung"]
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(student.id) and payload["vai_tro"] == "sinh_vien"
    assert body["het_han_luc"].endswith("+07:00")


def test_login_email_is_case_insensitive(client: TestClient, student: NguoiDung) -> None:
    r = client.post("/api/auth/login", json={"email": student.email.upper(), "mat_khau": PASSWORD})
    assert r.status_code == 200


def test_wrong_password_and_unknown_email_same_error(
    client: TestClient, student: NguoiDung
) -> None:
    wrong = client.post("/api/auth/login", json={"email": student.email, "mat_khau": "sai"})
    unknown = client.post("/api/auth/login", json={"email": "khong@co.vn", "mat_khau": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["code"] == "SAI_THONG_TIN_DANG_NHAP"


def test_locked_account_cannot_login_or_use_token(
    client: TestClient, student: NguoiDung, db: Session
) -> None:
    headers = login(client, student.email)
    student.dang_hoat_dong = False
    db.commit()
    assert (
        client.post("/api/auth/login", json={"email": student.email, "mat_khau": PASSWORD}).json()[
            "code"
        ]
        == "TAI_KHOAN_BI_KHOA"
    )
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "TAI_KHOAN_BI_KHOA"


def test_me(client: TestClient, student: NguoiDung) -> None:
    r = client.get("/api/auth/me", headers=login(client, student.email))
    assert r.status_code == 200
    assert r.json()["email"] == student.email


def test_me_without_or_with_bad_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").json()["code"] == "CHUA_DANG_NHAP"
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401 and r.json()["code"] == "TOKEN_KHONG_HOP_LE"


def test_token_signed_with_other_secret_rejected(client: TestClient, student: NguoiDung) -> None:
    forged = jwt.encode(
        {"sub": str(student.id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        "khoa-gia-mao-du-dai-32-ky-tu-xxxxxxxx",
        algorithm=ALGORITHM,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.json()["code"] == "TOKEN_KHONG_HOP_LE"


def test_expired_token(client: TestClient, student: NguoiDung) -> None:
    expired = jwt.encode(
        {"sub": str(student.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm=ALGORITHM,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["code"] == "PHIEN_HET_HAN"


def test_admin_cannot_use_student_endpoints(client: TestClient, admin: NguoiDung) -> None:
    r = client.get("/api/conversations", headers=login(client, admin.email))
    assert r.status_code == 403 and r.json()["code"] == "KHONG_DU_QUYEN"
