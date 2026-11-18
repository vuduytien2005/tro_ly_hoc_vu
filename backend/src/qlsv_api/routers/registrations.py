from fastapi import APIRouter, status

from src.qlsv_api.routers.deps import DbSession, InternalAuth, Now, run_in_transaction
from src.qlsv_api.schemas import RegistrationIn, RegistrationOut
from src.qlsv_api.services import registration_service

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


@router.delete(
    "/{ma_sv}/registrations/{ma_lop}",
    response_model=RegistrationOut,
    summary="Hủy đăng ký (chỉ trong thời gian đăng ký)",
)
def cancel(ma_sv: str, ma_lop: str, db: DbSession, now: Now) -> RegistrationOut:
    return run_in_transaction(db, lambda: registration_service.cancel(db, ma_sv, ma_lop, now))
