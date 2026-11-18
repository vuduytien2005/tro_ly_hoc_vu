from sqlalchemy.orm import Session

from src.qlsv_api.errors import not_found
from src.qlsv_api.models import LopHocPhan, SinhVien
from src.qlsv_api.repositories import students as student_repo


def get_student_or_404(db: Session, ma_sv: str) -> SinhVien:
    sv = student_repo.get_by_ma_sv(db, ma_sv)
    if sv is None:
        raise not_found("SV_KHONG_TON_TAI", f"Không tìm thấy sinh viên {ma_sv}.")
    return sv


def format_vnd(amount: int) -> str:
    """5000000 -> "5.000.000 đồng"."""
    return f"{amount:,}".replace(",", ".") + " đồng"


def day_label(thu: int) -> str:
    return "Chủ nhật" if thu == 8 else f"Thứ {thu}"


def schedule_label(lop: LopHocPhan) -> str:
    """vd: "Thứ 2, tiết 1-3, phòng B2.101"."""
    return f"{day_label(lop.thu)}, tiết {lop.tiet_bat_dau}-{lop.tiet_ket_thuc}, phòng {lop.phong}"
