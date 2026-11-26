"""Sinh viên cần chú ý (phòng đào tạo): cảnh báo học vụ, nợ học phí, đủ tín chỉ nhưng chưa đủ điều
kiện tốt nghiệp. Chỉ xét sinh viên đang học. Dùng lại đúng các quy tắc đã có (academic_service)."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.models import HocPhi, SinhVien
from src.qlsv_api.schemas import (
    AttentionListOut,
    AttentionReason,
    AttentionStudentOut,
    GraduationProgressOut,
)
from src.qlsv_api.services import academic_service
from src.qlsv_api.services.academic_service import AcademicSummary


def _vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đ"


def _gpa(value: object) -> str:
    return f"{float(str(value)):.2f}".replace(".", ",")


def build_reasons(
    summary: AcademicSummary,
    debts: list[tuple[int, date]],
    progress: GraduationProgressOut | None,
    today: date,
) -> list[AttentionReason]:
    """Hàm thuần: lý do cần chú ý của MỘT sinh viên, khẩn trước."""
    reasons: list[AttentionReason] = []
    if summary.canh_bao_hoc_vu:
        failed = len(summary.failed_course_ids)
        detail = f"GPA tích lũy {_gpa(summary.gpa)}"
        if failed:
            detail += f", {failed} học phần F chưa học lại"
        reasons.append(
            AttentionReason(loai="canh_bao_hoc_vu", muc_do="khan", chi_tiet=detail + ".")
        )
    owed = [(amount, due) for amount, due in debts if amount > 0]
    if owed:
        total = sum(amount for amount, _ in owed)
        earliest = min(due for _, due in owed)
        overdue = earliest < today
        detail = f"Nợ {_vnd(total)}"
        if len(owed) > 1:
            detail += f" ({len(owed)} học kỳ)"
        detail += (
            f", quá hạn từ {earliest:%d/%m/%Y}." if overdue else f", hạn nộp {earliest:%d/%m/%Y}."
        )
        reasons.append(
            AttentionReason(
                loai="no_hoc_phi", muc_do="khan" if overdue else "chu_y", chi_tiet=detail
            )
        )
    if (
        progress is not None
        and not progress.du_dieu_kien
        and progress.tin_chi_tich_luy >= progress.tong_tin_chi_yeu_cau
    ):
        reasons.append(
            AttentionReason(
                loai="chua_du_dk_tot_nghiep",
                muc_do="chu_y",
                chi_tiet="Đủ tín chỉ nhưng chưa đủ điều kiện tốt nghiệp: "
                + " ".join(progress.ly_do_chua_du),
            )
        )
    return sorted(reasons, key=lambda r: r.muc_do != "khan")


def list_attention(db: Session, now: datetime) -> AttentionListOut:
    today = now.date()
    students = db.scalars(
        select(SinhVien).where(SinhVien.trang_thai == "dang_hoc").order_by(SinhVien.ma_sv)
    ).all()
    out: list[AttentionStudentOut] = []
    for sv in students:
        debts = [
            (int(max(f.so_tien_phai_nop - f.so_tien_da_nop, 0)), f.han_nop)
            for f in db.scalars(select(HocPhi).where(HocPhi.sinh_vien_id == sv.id))
        ]
        try:
            progress = academic_service.get_graduation_progress(db, sv.ma_sv)
        except BusinessError:  # chưa có chương trình đào tạo cho ngành – khóa
            progress = None
        reasons = build_reasons(academic_service.summary_for(db, sv), debts, progress, today)
        if reasons:
            out.append(
                AttentionStudentOut(
                    ma_sv=sv.ma_sv,
                    ho_ten=sv.ho_ten,
                    lop=sv.lop,
                    khoa=sv.khoa_hoc.ma_khoa,
                    ly_do=reasons,
                )
            )
    out.sort(key=lambda s: -sum(r.muc_do == "khan" for r in s.ly_do))  # ổn định: giữ thứ tự ma_sv
    return AttentionListOut(tong=len(out), sinh_vien=out)
