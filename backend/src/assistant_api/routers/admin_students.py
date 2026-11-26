"""Hồ sơ sinh viên trên hệ thống QLSV (/api/admin/students, AD-10) — chỉ quản trị viên.

Trang này MÔ PHỎNG phần mềm của phòng đào tạo để demo (trường thật nhập hồ sơ trên hệ thống
riêng). Mọi thao tác đi qua API của qlsv_api — QLSV vẫn là nguồn sự thật, kiểm tra mọi ràng buộc.

Đồng bộ với tài khoản trợ lý: nguoi_dung giữ bản sao họ tên, email, ma_khoa của sinh viên. Khi
sửa hồ sơ, bản sao được cập nhật theo — nếu không, trợ lý sẽ lọc quy chế theo khóa cũ và sinh viên
đăng nhập bằng email cũ.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from src.assistant_api.deps import DbSession, require_admin
from src.assistant_api.errors import ApiError
from src.assistant_api.models import NguoiDung
from src.assistant_api.qlsv_directory import QlsvDirectory, StudentIdentity
from src.assistant_api.routers.admin_users import (
    add_student_account,
    check_password,
    ensure_email_free,
    ensure_no_account,
    qlsv_directory,
)
from src.assistant_api.schemas_admin import (
    AccountOut,
    LinkedAccount,
    ProgramOut,
    StudentAdminOut,
    StudentAdminPage,
    StudentCreateAdminIn,
    StudentCreateAdminOut,
    StudentFields,
    TrangThaiSv,
)

router = APIRouter(
    prefix="/api/admin/students",
    tags=["Quản trị — hồ sơ sinh viên (QLSV)"],
    dependencies=[Depends(require_admin)],
)

Directory = Annotated[QlsvDirectory, Depends(qlsv_directory)]


def _account_of(db: DbSession, ma_sv: str) -> NguoiDung | None:
    return db.scalar(select(NguoiDung).where(NguoiDung.ma_sv == ma_sv))


def _with_account(profile: dict[str, Any], account: NguoiDung | None) -> StudentAdminOut:
    linked = (
        LinkedAccount(id=account.id, dang_hoat_dong=bool(account.dang_hoat_dong))
        if account
        else None
    )
    return StudentAdminOut.model_validate({**profile, "tai_khoan": linked})


@router.get("", response_model=StudentAdminPage, summary="Danh sách sinh viên (từ QLSV)")
async def list_students(
    db: DbSession,
    directory: Directory,
    q: Annotated[str | None, Query(max_length=100)] = None,
    trang_thai: TrangThaiSv | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentAdminPage:
    data = await directory.list_students(
        {"q": q, "trang_thai": trang_thai, "page": page, "page_size": page_size}
    )
    ma_svs = [s["ma_sv"] for s in data["sinh_vien"]]
    accounts = (
        {u.ma_sv: u for u in db.scalars(select(NguoiDung).where(NguoiDung.ma_sv.in_(ma_svs)))}
        if ma_svs
        else {}
    )
    return StudentAdminPage(
        tong=data["tong"],
        trang_so=data["trang_so"],
        so_moi_trang=data["so_moi_trang"],
        sinh_vien=[_with_account(s, accounts.get(s["ma_sv"])) for s in data["sinh_vien"]],
    )


@router.get(
    "/attention",
    summary="Sinh viên cần chú ý (từ QLSV): cảnh báo học vụ, nợ học phí, chưa đủ ĐK tốt nghiệp",
)
async def list_attention(directory: Directory) -> dict[str, Any]:
    """Chỉ đọc, chỉ quản trị viên (router có require_admin). Không qua LLM / MCP."""
    return await directory.list_attention()


@router.get("/programs", response_model=list[ProgramOut], summary="Các cặp ngành – khóa")
async def list_programs(directory: Directory) -> list[dict[str, Any]]:
    return await directory.list_programs()


@router.post(
    "",
    response_model=StudentCreateAdminOut,
    status_code=201,
    summary="Thêm sinh viên vào QLSV (tùy chọn: cấp tài khoản trợ lý luôn)",
)
async def create_student(
    body: StudentCreateAdminIn, db: DbSession, directory: Directory
) -> StudentCreateAdminOut:
    password = body.mat_khau or ""
    if body.cap_tai_khoan:
        # Kiểm tra phía trợ lý TRƯỚC khi ghi vào QLSV -> tránh thêm hồ sơ rồi mới báo lỗi
        check_password(password)
        ensure_no_account(db, body.ma_sv.strip().upper())
        ensure_email_free(db, body.email.strip())

    profile = await directory.create_student(
        body.model_dump(exclude={"cap_tai_khoan", "mat_khau"}, mode="json")
    )
    account: NguoiDung | None = None
    warning: str | None = None
    if body.cap_tai_khoan:
        try:
            account = add_student_account(db, StudentIdentity.from_profile(profile), password)
        except ApiError as exc:  # hiếm: bị chiếm chỗ giữa hai bước
            warning = f"Đã thêm hồ sơ nhưng chưa cấp được tài khoản: {exc.message}"
    return StudentCreateAdminOut(
        sinh_vien=_with_account(profile, account),
        tai_khoan=AccountOut.model_validate(account) if account else None,
        canh_bao=warning,
    )


@router.patch(
    "/{ma_sv}",
    response_model=StudentAdminOut,
    summary="Sửa hồ sơ / đổi trạng thái trên QLSV (đồng bộ tài khoản trợ lý)",
)
async def update_student(
    ma_sv: str, body: StudentFields, db: DbSession, directory: Directory
) -> StudentAdminOut:
    changes = body.model_dump(exclude_none=True, mode="json")
    if not changes:
        raise ApiError("DU_LIEU_KHONG_HOP_LE", "Không có thông tin nào cần sửa.", 422)
    account = _account_of(db, ma_sv.strip().upper())
    if account is not None and "email" in changes:
        ensure_email_free(db, changes["email"].strip(), except_user_id=account.id)

    profile = await directory.update_student(ma_sv, changes)

    if account is not None:
        student = StudentIdentity.from_profile(profile)
        account.ho_ten = student.ho_ten
        account.email = student.email
        account.ma_khoa = student.ma_khoa
        db.commit()
    return _with_account(profile, account)
