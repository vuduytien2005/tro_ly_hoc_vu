from fastapi import APIRouter, status

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now, run_in_transaction
from src.qlsv_api.schemas import (
    BundleIn,
    BundleOut,
    RegistrationIn,
    RegistrationOut,
    SemesterPlanOut,
)
from src.qlsv_api.services import planning_service, registration_service

router = APIRouter(
    prefix="/internal/students", tags=["Đăng ký học phần"], dependencies=[InternalAuth]
)


@router.post(
    "/{ma_sv}/registrations",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký lớp học phần",
    description=(
        "Kiểm tra theo thứ tự: SV_KHONG_DANG_HOC, LOP_KHONG_TON_TAI, NGOAI_THOI_GIAN_DANG_KY, "
        "DA_DANG_KY_HOC_PHAN, DA_DAT_HOC_PHAN, CHUA_DAT_TIEN_QUYET, LOP_DA_DAY, TRUNG_LICH, "
        "VUOT_TIN_CHI_TOI_DA (409)."
    ),
)
def register(ma_sv: str, body: RegistrationIn, db: DbSession, now: Now) -> RegistrationOut:
    return run_in_transaction(
        db, lambda: registration_service.register(db, ma_sv, body.ma_lop, now)
    )


@router.post(
    "/{ma_sv}/registrations/check",
    response_model=RegistrationOut,
    summary="Kiểm tra có đăng ký được lớp không (không ghi)",
    description="Cùng các bước kiểm tra như đăng ký; hợp lệ trả trang_thai 'hop_le', không ghi gì.",
)
def check(ma_sv: str, body: RegistrationIn, db: DbSession, now: Now) -> RegistrationOut:
    try:
        return registration_service.register(db, ma_sv, body.ma_lop, now, dry_run=True)
    finally:
        db.rollback()  # nhả khóa UPDLOCK, không ghi gì


@router.delete(
    "/{ma_sv}/registrations/{ma_lop}",
    response_model=RegistrationOut,
    summary="Hủy đăng ký (chỉ trong thời gian đăng ký)",
)
def cancel(ma_sv: str, ma_lop: str, db: DbSession, now: Now) -> RegistrationOut:
    return run_in_transaction(db, lambda: registration_service.cancel(db, ma_sv, ma_lop, now))


@router.get(
    "/{ma_sv}/semester-plan",
    response_model=SemesterPlanOut,
    summary="Lập kế hoạch đăng ký học kỳ đang mở (chỉ đọc)",
    description=(
        "Gói lớp đề xuất kèm lý do chọn, và các học phần bị loại kèm lý do (DANG_HOC, "
        "CHUA_DAT_TIEN_QUYET, KHONG_CO_LOP_MO, KHONG_CON_LOP_PHU_HOP). Không có học kỳ mở đăng "
        "ký -> 409 KHONG_CO_HOC_KY_MO_DANG_KY."
    ),
)
def semester_plan(ma_sv: str, db: DbSession, now: Now) -> SemesterPlanOut:
    return planning_service.plan_next_semester(db, ma_sv, now)


@router.post(
    "/{ma_sv}/registrations/bundle",
    response_model=BundleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký cả gói lớp học phần (nguyên khối)",
    description=(
        "Cùng 9 bước kiểm tra như đăng ký một lớp, cho từng lớp, trong một giao dịch: một lớp lỗi "
        "thì không lớp nào được ghi (409 với mã lỗi của lớp đó, detail nêu mã lớp). Mã lớp trùng "
        "-> 422 DANH_SACH_LOP_KHONG_HOP_LE."
    ),
)
def register_bundle(ma_sv: str, body: BundleIn, db: DbSession, now: Now) -> BundleOut:
    return run_in_transaction(
        db, lambda: registration_service.register_bundle(db, ma_sv, body.ma_lop, now)
    )


@router.post(
    "/{ma_sv}/registrations/bundle/check",
    response_model=BundleOut,
    summary="Kiểm tra có đăng ký được cả gói không (không ghi)",
)
def check_bundle(ma_sv: str, body: BundleIn, db: DbSession, now: Now) -> BundleOut:
    try:
        return registration_service.register_bundle(db, ma_sv, body.ma_lop, now, dry_run=True)
    finally:
        db.rollback()  # bỏ các bản ghi tạm + nhả khóa
