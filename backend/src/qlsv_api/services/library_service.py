"""Thư viện: sách đang mượn, tìm sách, gia hạn.

Gia hạn kiểm theo đúng thứ tự (mỗi lỗi một mã): lượt mượn thuộc sinh viên
(KHONG_TIM_THAY_LUOT_MUON) -> chưa trả (DA_TRA_SACH) -> chưa quá hạn (SACH_QUA_HAN; trả đúng
ngày hạn vẫn chưa quá hạn) -> chưa gia hạn đủ MAX_RENEWALS lần (HET_LUOT_GIA_HAN) -> không có
người đặt trước (CO_NGUOI_DAT_TRUOC). Đạt: han_tra += RENEW_DAYS ngày.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError, conflict, not_found
from src.qlsv_api.models import MuonSach
from src.qlsv_api.repositories import library as library_repo
from src.qlsv_api.schemas import BookOut, BorrowOut
from src.qlsv_api.services.common import get_student_or_404

RENEW_DAYS = 14
MAX_RENEWALS = 2


def _renew_blocker(muon: MuonSach, today: date) -> BusinessError | None:
    """Lý do KHÔNG gia hạn được (sau bước kiểm chủ sở hữu), hoặc None nếu được."""
    if muon.trang_thai == "da_tra":
        return conflict("DA_TRA_SACH", "Sách này đã được trả, không cần gia hạn.")
    if muon.han_tra < today:
        return conflict(
            "SACH_QUA_HAN",
            f"Sách đã quá hạn trả ({muon.han_tra:%d/%m/%Y}) nên không gia hạn được; "
            "em mang sách đến thư viện để trả nhé.",
        )
    if muon.so_lan_gia_han >= MAX_RENEWALS:
        return conflict(
            "HET_LUOT_GIA_HAN",
            f"Sách này đã gia hạn đủ {MAX_RENEWALS} lần, không gia hạn thêm được.",
        )
    if muon.sach.so_luot_dat_truoc > 0:
        return conflict(
            "CO_NGUOI_DAT_TRUOC", "Sách đang có người đặt trước nên không gia hạn được."
        )
    return None


def _to_out(muon: MuonSach, today: date) -> BorrowOut:
    blocker = _renew_blocker(muon, today)
    return BorrowOut(
        muon_id=muon.id,
        ma_sach=muon.ma_sach,
        ten_sach=muon.sach.ten_sach,
        tac_gia=muon.sach.tac_gia,
        ngay_muon=muon.ngay_muon,
        han_tra=muon.han_tra,
        so_lan_gia_han=muon.so_lan_gia_han,
        qua_han=muon.han_tra < today,
        gia_han_duoc=blocker is None,
        ly_do_khong_gia_han=blocker.message if blocker else None,
    )


def list_borrows(db: Session, ma_sv: str, now: datetime) -> list[BorrowOut]:
    sv = get_student_or_404(db, ma_sv)
    return [_to_out(m, now.date()) for m in library_repo.active_borrows(db, sv.id)]


def search_books(db: Session, tu_khoa: str) -> list[BookOut]:
    return [
        BookOut(
            ma_sach=s.ma_sach,
            ten_sach=s.ten_sach,
            tac_gia=s.tac_gia,
            nam_xb=s.nam_xb,
            tong_so_ban=s.tong_so_ban,
            so_ban_con=s.so_ban_con,
        )
        for s in library_repo.search_books(db, tu_khoa)
    ]


def renew(db: Session, ma_sv: str, muon_id: int, now: datetime) -> BorrowOut:
    """Gia hạn một lượt mượn của chính sinh viên. Không commit."""
    sv = get_student_or_404(db, ma_sv)
    muon = library_repo.get_borrow_for_update(db, sv.id, muon_id)
    if muon is None:
        raise not_found("KHONG_TIM_THAY_LUOT_MUON", "Không tìm thấy lượt mượn sách này của em.")
    today = now.date()
    blocker = _renew_blocker(muon, today)
    if blocker is not None:
        raise blocker
    muon.han_tra = muon.han_tra + timedelta(days=RENEW_DAYS)
    muon.so_lan_gia_han += 1
    db.flush()
    return _to_out(muon, today)
