"""Hồ sơ, bảng điểm, GPA tích lũy, cảnh báo học vụ, tiến độ tốt nghiệp.

Quy tắc (docs/03-co-so-du-lieu.md):
- Học phần đạt: điểm chữ khác F.
- Học phần học nhiều lần: lấy lần có điểm hệ 4 CAO NHẤT.
- GPA tích lũy = Σ(điểm hệ 4 × tín chỉ) / Σ tín chỉ, chỉ tính học phần đạt, làm tròn 2 chữ số.
- Tín chỉ tích lũy = tổng tín chỉ các học phần đạt (mỗi học phần tính 1 lần).
- Cảnh báo học vụ: GPA tích lũy < 1.20 hoặc có ≥ 2 học phần F chưa học lại đạt.
  (Sinh viên chưa có điểm nào thì không bị cảnh báo.)
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src.qlsv_api.errors import not_found
from src.qlsv_api.models import KetQuaHocTap, SinhVien
from src.qlsv_api.repositories import results as result_repo
from src.qlsv_api.repositories import students as student_repo
from src.qlsv_api.schemas import (
    CertificateStatus,
    GraduationProgressOut,
    MissingCourse,
    StudentProfileOut,
    TranscriptOut,
    TranscriptRow,
)
from src.qlsv_api.services import semester_service
from src.qlsv_api.services.common import get_student_or_404

FAIL_GRADE = "F"
WARNING_GPA = Decimal("1.20")
WARNING_FAILED_COURSES = 2


@dataclass
class AcademicSummary:
    gpa: Decimal
    tin_chi_tich_luy: int
    passed_course_ids: set[int] = field(default_factory=set)
    failed_course_ids: set[int] = field(default_factory=set)  # F và chưa học lại đạt
    has_results: bool = False

    @property
    def canh_bao_hoc_vu(self) -> bool:
        if not self.has_results:
            return False
        return self.gpa < WARNING_GPA or len(self.failed_course_ids) >= WARNING_FAILED_COURSES


def is_passed(result: KetQuaHocTap) -> bool:
    return result.diem_chu != FAIL_GRADE


def summarize(results: Sequence[KetQuaHocTap]) -> AcademicSummary:
    """Tính GPA/tín chỉ tích lũy từ MỌI lần học của sinh viên (hàm thuần, dễ test)."""
    best: dict[int, KetQuaHocTap] = {}
    for r in results:
        current = best.get(r.hoc_phan_id)
        if current is None or r.diem_he_4 > current.diem_he_4:
            best[r.hoc_phan_id] = r

    passed = {hp_id: r for hp_id, r in best.items() if is_passed(r)}
    credits = sum(r.hoc_phan.so_tin_chi for r in passed.values())
    points = sum((r.diem_he_4 * r.hoc_phan.so_tin_chi for r in passed.values()), Decimal(0))
    gpa = (points / credits).quantize(Decimal("0.01"), ROUND_HALF_UP) if credits else Decimal("0")
    return AcademicSummary(
        gpa=gpa,
        tin_chi_tich_luy=credits,
        passed_course_ids=set(passed),
        failed_course_ids=set(best) - set(passed),
        has_results=bool(best),
    )


def summary_for(db: Session, sv: SinhVien) -> AcademicSummary:
    return summarize(result_repo.list_for_student(db, sv.id))


def get_profile(db: Session, ma_sv: str) -> StudentProfileOut:
    sv = get_student_or_404(db, ma_sv)
    return StudentProfileOut(
        ma_sv=sv.ma_sv,
        ho_ten=sv.ho_ten,
        email=sv.email,
        ngay_sinh=sv.ngay_sinh,
        gioi_tinh=sv.gioi_tinh,
        lop=sv.lop,
        ma_nganh=sv.nganh.ma_nganh,
        nganh=sv.nganh.ten_nganh,
        khoa=sv.khoa_hoc.ma_khoa,
        trang_thai=sv.trang_thai,
    )


def get_transcript(db: Session, ma_sv: str, ma_hoc_ky: str | None) -> TranscriptOut:
    """Bảng điểm (mọi lần học, có thể lọc theo học kỳ); GPA/tín chỉ luôn là TÍCH LŨY toàn khóa."""
    sv = get_student_or_404(db, ma_sv)
    all_results = result_repo.list_for_student(db, sv.id)
    shown = all_results
    if ma_hoc_ky:
        hk = semester_service.get_by_ma_or_404(db, ma_hoc_ky)
        shown = [r for r in all_results if r.hoc_ky_id == hk.id]
    summary = summarize(all_results)
    return TranscriptOut(
        ma_sv=sv.ma_sv,
        ma_hoc_ky=ma_hoc_ky,
        ket_qua=[
            TranscriptRow(
                ma_hp=r.hoc_phan.ma_hp,
                ten_hp=r.hoc_phan.ten_hp,
                tin_chi=r.hoc_phan.so_tin_chi,
                hoc_ky=r.hoc_ky.ma_hoc_ky,
                diem_qua_trinh=float(r.diem_qua_trinh),
                diem_thi=float(r.diem_thi),
                diem_tong_ket=float(r.diem_tong_ket),
                diem_chu=r.diem_chu,
                diem_he_4=float(r.diem_he_4),
                lan_hoc=r.lan_hoc,
                dat=is_passed(r),
            )
            for r in shown
        ],
        gpa_tich_luy=float(summary.gpa),
        tin_chi_tich_luy=summary.tin_chi_tich_luy,
        canh_bao_hoc_vu=summary.canh_bao_hoc_vu,
    )


def get_graduation_progress(db: Session, ma_sv: str) -> GraduationProgressOut:
    sv = get_student_or_404(db, ma_sv)
    program = student_repo.get_program(db, sv.nganh_id, sv.khoa_hoc_id)
    if program is None:
        raise not_found(
            "CHUONG_TRINH_KHONG_TON_TAI",
            f"Chưa có chương trình đào tạo cho ngành {sv.nganh.ma_nganh} "
            f"khóa {sv.khoa_hoc.ma_khoa}.",
        )
    summary = summary_for(db, sv)
    courses = student_repo.list_program_courses(db, program.id)
    # Mọi học phần trong chương trình chưa đạt (kể cả tự chọn) đều được liệt kê
    missing = [
        MissingCourse(
            ma_hp=c.hoc_phan.ma_hp,
            ten_hp=c.hoc_phan.ten_hp,
            tin_chi=c.hoc_phan.so_tin_chi,
            bat_buoc=c.bat_buoc,
            hoc_ky_goi_y=c.hoc_ky_goi_y,
        )
        for c in courses
        if c.hoc_phan_id not in summary.passed_course_ids
    ]
    approved = {
        cc.loai
        for cc in student_repo.list_certificates(db, sv.id)
        if cc.trang_thai_duyet == "da_duyet"
    }
    certs = CertificateStatus(
        ngoai_ngu="ngoai_ngu" in approved, gdtc="gdtc" in approved, gdqp="gdqp" in approved
    )

    reasons: list[str] = []
    if summary.tin_chi_tich_luy < program.tong_tin_chi:
        reasons.append(
            f"Chưa đủ tín chỉ: {summary.tin_chi_tich_luy}/{program.tong_tin_chi} tín chỉ."
        )
    if summary.gpa < program.gpa_toi_thieu:
        reasons.append(
            f"GPA tích lũy {summary.gpa} thấp hơn mức tối thiểu {program.gpa_toi_thieu}."
        )
    required_missing = [m.ma_hp for m in missing if m.bat_buoc]
    if required_missing:
        reasons.append(f"Còn học phần bắt buộc chưa đạt: {', '.join(required_missing)}.")
    if program.yeu_cau_ngoai_ngu and not certs.ngoai_ngu:
        reasons.append("Chưa có chứng chỉ ngoại ngữ được duyệt.")
    if not certs.gdtc:
        reasons.append("Chưa có chứng chỉ Giáo dục thể chất.")
    if not certs.gdqp:
        reasons.append("Chưa có chứng chỉ Giáo dục quốc phòng - an ninh.")

    return GraduationProgressOut(
        ma_sv=sv.ma_sv,
        tong_tin_chi_yeu_cau=program.tong_tin_chi,
        tin_chi_tich_luy=summary.tin_chi_tich_luy,
        gpa=float(summary.gpa),
        gpa_toi_thieu=float(program.gpa_toi_thieu),
        hoc_phan_con_thieu=missing,
        chung_chi=certs,
        yeu_cau_ngoai_ngu=program.yeu_cau_ngoai_ngu,
        du_dieu_kien=not reasons,
        ly_do_chua_du=reasons,
    )
