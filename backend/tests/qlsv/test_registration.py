"""Đăng ký học phần: mỗi mã lỗi một test, dựa trên dữ liệu mẫu (rollback sau mỗi test)."""

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.models import DangKyHocPhan, HocKy, KetQuaHocTap, LopHocPhan, SinhVien
from src.qlsv_api.services import registration_service
from tests.qlsv.conftest import AFTER_REGISTRATION, DEMO_NOW


def register(db: Session, ma_sv: str, ma_lop: str):  # type: ignore[no-untyped-def]
    result = registration_service.register(db, ma_sv, ma_lop, DEMO_NOW)
    db.commit()  # chỉ commit tới SAVEPOINT (xem conftest)
    return result


def assert_error(db: Session, ma_sv: str, ma_lop: str, code: str) -> BusinessError:
    with pytest.raises(BusinessError) as e:
        registration_service.register(db, ma_sv, ma_lop, DEMO_NOW)
    db.rollback()
    assert e.value.code == code, e.value.message
    return e.value


# ---------- Thành công ----------
def test_register_success(db: Session) -> None:
    out = register(db, "SV22001", "IT004.02")
    assert (out.ma_hp, out.tin_chi, out.trang_thai) == ("IT004", 3, "da_dang_ky")
    assert out.lich == "Thứ 2, tiết 1-3, phòng B2.101"


# ---------- 9 mã lỗi, đúng thứ tự kiểm tra ----------
def test_1_sv_khong_dang_hoc(db: Session) -> None:
    db.execute(update(SinhVien).where(SinhVien.ma_sv == "SV22002").values(trang_thai="bao_luu"))
    assert_error(db, "SV22002", "IT004.02", "SV_KHONG_DANG_HOC")


def test_2_lop_khong_ton_tai(db: Session) -> None:
    assert_error(db, "SV22001", "XX999.01", "LOP_KHONG_TON_TAI")


def test_3_ngoai_thoi_gian_dang_ky_hoc_ky_khong_mo(db: Session) -> None:
    # SE105.01 thuộc HK1 2026-2027 (không mở đăng ký)
    assert_error(db, "SV22001", "SE105.01", "NGOAI_THOI_GIAN_DANG_KY")


def test_3_ngoai_thoi_gian_dang_ky_da_het_han(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        registration_service.register(db, "SV22001", "IT004.02", AFTER_REGISTRATION)
    assert e.value.code == "NGOAI_THOI_GIAN_DANG_KY"


def test_4_da_dang_ky_hoc_phan(db: Session) -> None:
    register(db, "SV22001", "IT004.02")
    assert_error(db, "SV22001", "IT004.03", "DA_DANG_KY_HOC_PHAN")  # lớp khác, cùng học phần
    assert_error(db, "SV22001", "IT004.02", "DA_DANG_KY_HOC_PHAN")  # chính lớp đó


def test_5_da_dat_hoc_phan(db: Session) -> None:
    assert_error(db, "SV22001", "SE104.01", "DA_DAT_HOC_PHAN")


def test_6_chua_dat_tien_quyet(db: Session) -> None:
    # SE201 yêu cầu IT003; SV23001 chưa học IT003
    err = assert_error(db, "SV23001", "SE201.01", "CHUA_DAT_TIEN_QUYET")
    assert "IT003" in err.message


def test_7_lop_da_day(db: Session) -> None:
    # SE202.01 sĩ số 2, đã có SV22002 và SV23001
    assert_error(db, "SV22001", "SE202.01", "LOP_DA_DAY")


def test_8_trung_lich(db: Session) -> None:
    register(db, "SV22001", "IT004.02")  # Thứ 2, tiết 1-3
    err = assert_error(db, "SV22001", "SE105.02", "TRUNG_LICH")  # Thứ 2, tiết 1-4
    assert "IT004.02" in err.message


def test_9_vuot_tin_chi_toi_da(db: Session) -> None:
    db.execute(update(HocKy).where(HocKy.ma_hoc_ky == "2026-2027-HK2").values(tin_chi_toi_da=3))
    register(db, "SV22001", "IT004.02")  # 3 tín chỉ = đúng giới hạn
    assert_error(db, "SV22001", "SE201.01", "VUOT_TIN_CHI_TOI_DA")  # +3 -> 6 > 3


def test_9_warning_student_uses_lower_limit(db: Session) -> None:
    """SV bị cảnh báo học vụ dùng tin_chi_toi_da_canh_bao."""
    db.execute(
        update(HocKy)
        .where(HocKy.ma_hoc_ky == "2026-2027-HK2")
        .values(tin_chi_toi_da=25, tin_chi_toi_da_canh_bao=2)
    )
    # SV22002 bình thường không bị cảnh báo; đổi 2 môn thành F -> có 2 học phần F chưa học lại
    sv_id = db.scalar(select(SinhVien.id).where(SinhVien.ma_sv == "SV22002"))
    db.execute(
        update(KetQuaHocTap)
        .where(KetQuaHocTap.sinh_vien_id == sv_id, KetQuaHocTap.hoc_phan_id.in_([2, 6]))
        .values(diem_chu="F", diem_he_4=0)
    )
    err = assert_error(db, "SV22002", "IT004.02", "VUOT_TIN_CHI_TOI_DA")
    assert "cảnh báo học vụ" in err.message


# ---------- Hủy và đăng ký lại ----------
def test_cancel_then_register_again_reuses_row(db: Session) -> None:
    register(db, "SV22001", "IT004.02")
    out = registration_service.cancel(db, "SV22001", "IT004.02", DEMO_NOW)
    db.commit()
    assert out.trang_thai == "da_huy"

    register(db, "SV22001", "IT004.02")  # đăng ký lại: kích hoạt bản ghi cũ, không vi phạm UNIQUE
    lop_id = db.scalar(select(LopHocPhan.id).where(LopHocPhan.ma_lop == "IT004.02"))
    rows = db.scalars(select(DangKyHocPhan).where(DangKyHocPhan.lop_hoc_phan_id == lop_id)).all()
    assert len(rows) == 1 and rows[0].trang_thai == "da_dang_ky" and rows[0].thoi_gian_huy is None


def test_cancel_not_registered(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        registration_service.cancel(db, "SV22001", "IT004.02", DEMO_NOW)
    assert e.value.code == "CHUA_DANG_KY_LOP"


def test_cancel_outside_registration_period(db: Session) -> None:
    register(db, "SV22001", "IT004.02")
    with pytest.raises(BusinessError) as e:
        registration_service.cancel(db, "SV22001", "IT004.02", AFTER_REGISTRATION)
    assert e.value.code == "NGOAI_THOI_GIAN_DANG_KY"


def test_cancelled_seat_is_freed(db: Session) -> None:
    """SE202.01 đầy; SV22002 hủy -> SV22001 đăng ký được."""
    registration_service.cancel(db, "SV22002", "SE202.01", DEMO_NOW)
    db.commit()
    assert register(db, "SV22001", "SE202.01").trang_thai == "da_dang_ky"
