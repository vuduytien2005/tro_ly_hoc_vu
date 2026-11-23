"""Đơn từ: giấy xác nhận sinh viên, bảo lưu, phúc khảo.

- ma_don = DT-{năm}-{số thứ tự 4 chữ số}, sinh dưới khóa khoảng để không trùng.
- Bảo lưu: chỉ khi đang học và không nợ học phí học kỳ hiện tại (NO_HOC_PHI).
- Phúc khảo: chỉ học phần có điểm trong học kỳ ĐÃ KẾT THÚC GẦN NHẤT.
"""

from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.qlsv_api.errors import conflict, invalid, not_found
from src.qlsv_api.models import DonTu
from src.qlsv_api.repositories import requests as request_repo
from src.qlsv_api.repositories import results as result_repo
from src.qlsv_api.repositories import tuition as tuition_repo
from src.qlsv_api.schemas import (
    REQUEST_CONTENT_SCHEMAS,
    DeferralContent,
    RegradeContent,
    RequestOut,
    RequestSummaryOut,
    StaffRequestListOut,
    StaffRequestOut,
)
from src.qlsv_api.services import semester_service
from src.qlsv_api.services.common import format_vnd, get_student_or_404
from src.shared.time import from_db, to_db

FINAL_STATUSES = {"hoan_tat", "tu_choi"}
# Máy trạng thái của đơn (cán bộ xử lý). Trạng thái cuối không có bước kế tiếp.
NEXT_STATUSES: dict[str, set[str]] = {
    "moi_tao": {"dang_xu_ly", "da_duyet", "tu_choi"},
    "dang_xu_ly": {"da_duyet", "tu_choi"},
    "da_duyet": {"hoan_tat"},
}


def _to_out(don: DonTu) -> RequestOut:
    return RequestOut(
        ma_don=don.ma_don,
        loai_don=don.loai_don,
        noi_dung=don.noi_dung,
        trang_thai=don.trang_thai,
        ghi_chu_xu_ly=don.ghi_chu_xu_ly,
        tao_boi=don.tao_boi,
        created_at=from_db(don.created_at),  # type: ignore[arg-type]
        updated_at=from_db(don.updated_at),  # type: ignore[arg-type]
    )


def _validate_content(loai_don: str, noi_dung: dict[str, Any]) -> dict[str, Any]:
    schema = REQUEST_CONTENT_SCHEMAS[loai_don]
    try:
        # exclude_none: trường tùy chọn không có (vd lien_he) thì không lưu khóa rỗng
        return schema.model_validate(noi_dung).model_dump(exclude_none=True)
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) for e in exc.errors() if e["loc"])
        raise invalid(
            "DU_LIEU_KHONG_HOP_LE", f"Nội dung đơn không hợp lệ (kiểm tra: {fields})."
        ) from exc


def create_request(
    db: Session,
    ma_sv: str,
    loai_don: str,
    noi_dung: dict[str, Any],
    tao_boi: str,
    now: datetime,
) -> RequestOut:
    """Tạo đơn mới. Không commit."""
    sv = get_student_or_404(db, ma_sv)
    content = _validate_content(loai_don, noi_dung)

    if loai_don == "bao_luu":
        deferral = DeferralContent.model_validate(content)
        if sv.trang_thai != "dang_hoc":
            raise conflict(
                "SV_KHONG_DANG_HOC",
                f"Chỉ sinh viên đang học mới được bảo lưu (hiện tại: '{sv.trang_thai}').",
            )
        semester_service.get_by_ma_or_404(db, deferral.tu_hoc_ky)
        hk = semester_service.current_semester(db, now)
        fee = tuition_repo.get_for_semester(db, sv.id, hk.id)
        if fee is not None and fee.trang_thai != "da_nop":
            owed = format_vnd(int(fee.so_tien_phai_nop - fee.so_tien_da_nop))
            raise conflict(
                "NO_HOC_PHI",
                f"Em còn nợ học phí {hk.ten}: {owed}. "
                "Cần hoàn tất học phí trước khi nộp đơn bảo lưu.",
            )

    elif loai_don == "phuc_khao":
        regrade = RegradeContent.model_validate(content)
        hk = semester_service.latest_finished_semester(db, now)
        result = None
        if hk is not None:
            result = next(
                (
                    r
                    for r in result_repo.list_for_student(db, sv.id, hk.id)
                    if r.hoc_phan.ma_hp.upper() == regrade.ma_hp.upper()
                ),
                None,
            )
        if hk is None or result is None:
            ten_hk = hk.ten if hk else "gần nhất"
            raise conflict(
                "KHONG_CO_DIEM_HOC_KY_GAN_NHAT",
                f"Học phần {regrade.ma_hp} không có điểm trong {ten_hk}, nên không thể phúc khảo.",
            )
        content.update(
            ma_hp=result.hoc_phan.ma_hp,
            ten_hp=result.hoc_phan.ten_hp,
            ma_hoc_ky=hk.ma_hoc_ky,
            diem_thi=float(result.diem_thi),
        )

    seq = request_repo.next_sequence(db, now.year)
    don = DonTu(
        ma_don=f"DT-{now.year}-{seq:04d}",
        sinh_vien_id=sv.id,
        loai_don=loai_don,
        noi_dung=content,
        trang_thai="moi_tao",
        tao_boi=tao_boi,
        created_at=to_db(now),
        updated_at=to_db(now),
    )
    db.add(don)
    db.flush()
    return _to_out(don)


def list_requests(db: Session, ma_sv: str, trang_thai: str | None) -> list[RequestSummaryOut]:
    sv = get_student_or_404(db, ma_sv)
    return [
        RequestSummaryOut(
            ma_don=d.ma_don,
            loai_don=d.loai_don,
            trang_thai=d.trang_thai,
            tao_boi=d.tao_boi,
            created_at=from_db(d.created_at),  # type: ignore[arg-type]
            updated_at=from_db(d.updated_at),  # type: ignore[arg-type]
        )
        for d in request_repo.list_for_student(db, sv.id, trang_thai)
    ]


def get_request(db: Session, ma_sv: str, ma_don: str) -> RequestOut:
    """Chi tiết đơn; đơn của sinh viên khác cũng trả 404 (không tiết lộ là có tồn tại)."""
    sv = get_student_or_404(db, ma_sv)
    don = request_repo.get_by_ma_don(db, ma_don)
    if don is None or don.sinh_vien_id != sv.id:
        raise not_found("DON_KHONG_TON_TAI", f"Không tìm thấy đơn {ma_don} của em.")
    return _to_out(don)


def update_status(
    db: Session, ma_don: str, trang_thai: str, ghi_chu_xu_ly: str | None, now: datetime
) -> RequestOut:
    """(Cán bộ) chuyển trạng thái đơn theo NEXT_STATUSES. Không commit."""
    don = request_repo.get_by_ma_don_for_update(db, ma_don)
    if don is None:
        raise not_found("DON_KHONG_TON_TAI", f"Không tìm thấy đơn {ma_don}.")
    if don.trang_thai in FINAL_STATUSES:
        raise conflict(
            "DON_DA_KET_THUC", f"Đơn {ma_don} đã ở trạng thái '{don.trang_thai}', không thể sửa."
        )
    if trang_thai not in NEXT_STATUSES.get(don.trang_thai, set()):
        raise conflict(
            "CHUYEN_TRANG_THAI_KHONG_HOP_LE",
            f"Không thể chuyển đơn {ma_don} từ '{don.trang_thai}' sang '{trang_thai}'.",
        )
    note = ghi_chu_xu_ly.strip() if ghi_chu_xu_ly else None
    if trang_thai == "tu_choi" and not note:
        raise invalid("CAN_LY_DO_TU_CHOI", "Từ chối đơn cần ghi rõ lý do cho sinh viên.")
    don.trang_thai = trang_thai
    if note:
        don.ghi_chu_xu_ly = note
    don.updated_at = to_db(now)
    # Luôn đưa updated_at vào câu UPDATE (kể cả khi giá trị trùng cũ, vd DEMO_NOW cố định),
    # để trigger trg_don_tu_updated_at thấy UPDATE(updated_at) và không ghi đè bằng giờ máy.
    flag_modified(don, "updated_at")
    db.flush()
    return _to_out(don)


def list_all_requests(
    db: Session, trang_thai: str | None, loai_don: str | None, page: int, page_size: int
) -> StaffRequestListOut:
    """(Cán bộ) mọi đơn, mới nhất trước, kèm mã SV và họ tên người nộp."""
    rows = request_repo.list_all_page(db, trang_thai, loai_don, (page - 1) * page_size, page_size)
    return StaffRequestListOut(
        tong=request_repo.count_all(db, trang_thai, loai_don),
        trang_so=page,
        so_moi_trang=page_size,
        don=[
            StaffRequestOut(
                **_to_out(d).model_dump(), ma_sv=d.sinh_vien.ma_sv, ho_ten=d.sinh_vien.ho_ten
            )
            for d in rows
        ],
    )
