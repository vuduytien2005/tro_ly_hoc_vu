"""Quản lý tài khoản (/api/admin/users, AD-09) — chỉ quản trị viên.

- Cấp tài khoản sinh viên chỉ bằng MÃ SINH VIÊN: họ tên, email, khóa đọc từ qlsv_api
  (src/assistant_api/qlsv_directory.py). Không có tự đăng ký: nếu người dùng tự khai `ma_sv`,
  họ có thể xưng là sinh viên khác và cơ chế tiêm ngữ cảnh (quy tắc bảo mật 1) mất tác dụng.
- Khóa tài khoản có hiệu lực ngay: mỗi request đều đọc lại `dang_hoat_dong` (deps.py).
- Không sửa hồ sơ sinh viên — đó là việc của hệ thống QLSV.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.assistant_api.auth.security import hash_password
from src.assistant_api.deps import Admin, DbSession, require_admin
from src.assistant_api.errors import ApiError, conflict, not_found
from src.assistant_api.models import NguoiDung
from src.assistant_api.qlsv_directory import QlsvDirectory, StudentIdentity
from src.assistant_api.schemas_admin import (
    AccountCreateIn,
    AccountOut,
    AccountPage,
    AccountPatch,
    PasswordResetIn,
    VaiTro,
)

router = APIRouter(
    prefix="/api/admin/users", tags=["Quản trị — tài khoản"], dependencies=[Depends(require_admin)]
)

BCRYPT_MAX_BYTES = 72  # bcrypt chỉ dùng 72 byte đầu -> chặn thay vì cắt im lặng
_LETTER = re.compile(r"[^\W\d_]")
_DIGIT = re.compile(r"\d")


def qlsv_directory(request: Request) -> QlsvDirectory:
    directory: QlsvDirectory = request.app.state.qlsv_directory
    return directory


def check_password(password: str) -> None:
    if (
        len(password) < 8
        or len(password.encode("utf-8")) > BCRYPT_MAX_BYTES
        or not _LETTER.search(password)
        or not _DIGIT.search(password)
    ):
        raise ApiError(
            "MAT_KHAU_YEU",
            "Mật khẩu phải dài 8–72 ký tự, có ít nhất một chữ cái và một chữ số.",
            422,
        )


def _get_account(db: DbSession, user_id: int) -> NguoiDung:
    user = db.get(NguoiDung, user_id)
    if user is None:
        raise not_found("TAI_KHOAN_KHONG_TON_TAI", "Không tìm thấy tài khoản.")
    return user


@router.get("", response_model=AccountPage, summary="Danh sách tài khoản")
def list_accounts(
    db: DbSession,
    tu_khoa: Annotated[str | None, Query(max_length=100)] = None,
    vai_tro: VaiTro | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AccountPage:
    conditions = []
    if tu_khoa and tu_khoa.strip():
        text = tu_khoa.strip()
        conditions.append(
            or_(
                NguoiDung.email.contains(text, autoescape=True),
                NguoiDung.ho_ten.contains(text, autoescape=True),
                NguoiDung.ma_sv.contains(text, autoescape=True),
            )
        )
    if vai_tro:
        conditions.append(NguoiDung.vai_tro == vai_tro)

    total = db.scalar(select(func.count(NguoiDung.id)).where(*conditions))
    rows = db.scalars(
        select(NguoiDung)
        .where(*conditions)
        .order_by(NguoiDung.vai_tro, NguoiDung.ma_sv, NguoiDung.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AccountPage(
        tong=total or 0,
        trang_so=page,
        so_moi_trang=page_size,
        nguoi_dung=[AccountOut.model_validate(u) for u in rows],
    )


@router.post(
    "",
    response_model=AccountOut,
    status_code=201,
    summary="Cấp tài khoản sinh viên từ mã sinh viên (thông tin lấy từ QLSV)",
)
async def create_student_account(
    body: AccountCreateIn,
    db: DbSession,
    directory: Annotated[QlsvDirectory, Depends(qlsv_directory)],
) -> NguoiDung:
    check_password(body.mat_khau)
    ensure_no_account(db, body.ma_sv)
    student = await directory.get_student(body.ma_sv)
    return add_student_account(db, student, body.mat_khau)


def ensure_no_account(db: Session, ma_sv: str) -> None:
    if db.scalar(select(NguoiDung.id).where(NguoiDung.ma_sv == ma_sv)) is not None:
        raise conflict("TAI_KHOAN_DA_TON_TAI", f"Sinh viên {ma_sv} đã có tài khoản.")


def ensure_email_free(db: Session, email: str, except_user_id: int | None = None) -> None:
    """Email đăng nhập là duy nhất trong tlhv_assistant (kể cả tài khoản quản trị)."""
    query = select(NguoiDung.id).where(func.lower(NguoiDung.email) == email.lower())
    if except_user_id is not None:
        query = query.where(NguoiDung.id != except_user_id)
    if db.scalar(query) is not None:
        raise conflict("EMAIL_DA_TON_TAI", f"Email {email} đã được dùng cho một tài khoản khác.")


def add_student_account(db: Session, student: StudentIdentity, password: str) -> NguoiDung:
    """Tạo tài khoản từ hồ sơ QLSV (mật khẩu đã qua check_password). Commit."""
    ensure_no_account(db, student.ma_sv)
    ensure_email_free(db, student.email)
    user = NguoiDung(
        email=student.email,
        mat_khau_hash=hash_password(password),
        ho_ten=student.ho_ten,
        vai_tro="sinh_vien",
        ma_sv=student.ma_sv,
        ma_khoa=student.ma_khoa,
        dang_hoat_dong=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # hai quản trị viên cấp cùng lúc -> chỉ mục UNIQUE chặn
        db.rollback()
        raise conflict(
            "TAI_KHOAN_DA_TON_TAI", f"Sinh viên {student.ma_sv} đã có tài khoản."
        ) from exc
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=AccountOut, summary="Khóa / mở khóa tài khoản")
def update_account(user_id: int, body: AccountPatch, db: DbSession, me: Admin) -> NguoiDung:
    user = _get_account(db, user_id)
    if user.id == me.id and not body.dang_hoat_dong:
        raise ApiError(
            "KHONG_THE_KHOA_CHINH_MINH", "Không thể tự khóa tài khoản đang đăng nhập.", 422
        )
    user.dang_hoat_dong = body.dang_hoat_dong
    db.commit()
    return user


@router.post(
    "/{user_id}/reset-password", status_code=204, summary="Đặt lại mật khẩu (mật khẩu tạm)"
)
def reset_password(user_id: int, body: PasswordResetIn, db: DbSession) -> Response:
    check_password(body.mat_khau)
    user = _get_account(db, user_id)
    user.mat_khau_hash = hash_password(body.mat_khau)
    db.commit()
    return Response(status_code=204)
