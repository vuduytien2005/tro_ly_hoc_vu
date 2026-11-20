"""Đăng ký / hủy đăng ký lớp học phần.

Chống đăng ký trùng khi nhiều yêu cầu đến cùng lúc (race condition):
  Trong CÙNG một transaction, khóa hàng `sinh_vien` rồi đến hàng `lop_hoc_phan`
  bằng WITH (UPDLOCK, ROWLOCK), sau đó mới đếm sĩ số, kiểm tra và ghi.
  - Khóa lớp: hai sinh viên cùng giành chỗ cuối -> người sau chờ người trước xong
    rồi mới đếm, nên thấy lớp đã đầy.
  - Khóa sinh viên: một sinh viên gửi 2 yêu cầu song song (2 lớp khác nhau) không thể
    cùng vượt qua kiểm tra trùng lịch / tín chỉ tối đa.
  - Luôn khóa theo thứ tự sinh_vien -> lop_hoc_phan để tránh deadlock.
Khóa được nhả khi tầng router commit/rollback.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError, conflict, invalid, not_found
from src.qlsv_api.models import DangKyHocPhan, LopHocPhan, SinhVien
from src.qlsv_api.repositories import registrations as registration_repo
from src.qlsv_api.repositories import results as result_repo
from src.qlsv_api.repositories import sections as section_repo
from src.qlsv_api.repositories import students as student_repo
from src.qlsv_api.schemas import BundleOut, RegistrationOut
from src.qlsv_api.services import academic_service, semester_service
from src.qlsv_api.services.common import schedule_label
from src.shared.time import to_db


def _lock_student(db: Session, ma_sv: str) -> SinhVien:
    sv = student_repo.lock_by_ma_sv(db, ma_sv)
    if sv is None:
        raise not_found("SV_KHONG_TON_TAI", f"Không tìm thấy sinh viên {ma_sv}.")
    return sv


def _lock_section(db: Session, ma_lop: str) -> LopHocPhan:
    lop = section_repo.lock_by_ma_lop(db, ma_lop)
    if lop is None:
        raise conflict("LOP_KHONG_TON_TAI", f"Không tồn tại lớp học phần {ma_lop}.")
    return lop


def _ensure_registration_open(lop: LopHocPhan, now: datetime) -> None:
    if not semester_service.is_registration_open(lop.hoc_ky, now):
        raise conflict(
            "NGOAI_THOI_GIAN_DANG_KY",
            f"Học kỳ {lop.hoc_ky.ten} hiện không trong thời gian đăng ký học phần.",
        )


def overlaps(a: LopHocPhan, b: LopHocPhan) -> bool:
    """Hai lớp trùng lịch: cùng thứ và khoảng tiết giao nhau."""
    return (
        a.thu == b.thu and a.tiet_bat_dau <= b.tiet_ket_thuc and b.tiet_bat_dau <= a.tiet_ket_thuc
    )


_overlaps = overlaps


def _to_out(lop: LopHocPhan, trang_thai: str) -> RegistrationOut:
    return RegistrationOut(
        ma_lop=lop.ma_lop,
        ma_hp=lop.hoc_phan.ma_hp,
        ten_hp=lop.hoc_phan.ten_hp,
        tin_chi=lop.hoc_phan.so_tin_chi,
        hoc_ky=lop.hoc_ky.ma_hoc_ky,
        lich=schedule_label(lop),
        trang_thai=trang_thai,
    )


def register(
    db: Session, ma_sv: str, ma_lop: str, now: datetime, dry_run: bool = False
) -> RegistrationOut:
    """Kiểm tra lần lượt 9 điều kiện (đúng thứ tự trong docs/03) rồi ghi đăng ký.

    `dry_run=True`: chỉ kiểm tra, không ghi (trả trang_thai "hop_le") — dùng để báo lỗi
    (trùng lịch, lớp đầy...) TRƯỚC khi hiện thẻ xác nhận.
    Không commit — tầng gọi (router) commit để nhả khóa.
    """
    # 1. Sinh viên đang học
    sv = _lock_student(db, ma_sv)
    if sv.trang_thai != "dang_hoc":
        raise conflict(
            "SV_KHONG_DANG_HOC",
            f"Sinh viên đang ở trạng thái '{sv.trang_thai}', không được đăng ký học phần.",
        )

    # 2. Lớp tồn tại
    lop = _lock_section(db, ma_lop)

    # 3. Học kỳ của lớp đang mở đăng ký
    _ensure_registration_open(lop, now)

    current = registration_repo.list_active_in_semester(db, sv.id, lop.hoc_ky_id)

    # 4. Chưa đăng ký lớp khác (hoặc chính lớp này) của cùng học phần trong học kỳ
    same_course = [r for r in current if r.lop_hoc_phan.hoc_phan_id == lop.hoc_phan_id]
    if same_course:
        raise conflict(
            "DA_DANG_KY_HOC_PHAN",
            f"Em đã đăng ký lớp {same_course[0].lop_hoc_phan.ma_lop} của học phần "
            f"{lop.hoc_phan.ten_hp} trong học kỳ này.",
        )

    # 5. Chưa đạt học phần (bản giả lập không cho học cải thiện)
    summary = academic_service.summarize(result_repo.list_for_student(db, sv.id))
    if lop.hoc_phan_id in summary.passed_course_ids:
        raise conflict(
            "DA_DAT_HOC_PHAN", f"Em đã đạt học phần {lop.hoc_phan.ten_hp}, không cần đăng ký lại."
        )

    # 6. Đạt đủ học phần tiên quyết
    missing_prereq = [
        hp
        for hp in section_repo.list_prerequisites(db, lop.hoc_phan_id)
        if hp.id not in summary.passed_course_ids
    ]
    if missing_prereq:
        names = ", ".join(f"{hp.ma_hp} - {hp.ten_hp}" for hp in missing_prereq)
        raise conflict("CHUA_DAT_TIEN_QUYET", f"Em chưa đạt học phần tiên quyết: {names}.")

    # 7. Lớp còn chỗ (đếm khi ĐANG GIỮ KHÓA lớp)
    registered = section_repo.count_registered(db, [lop.id])[lop.id]
    if registered >= lop.si_so_toi_da:
        raise conflict(
            "LOP_DA_DAY", f"Lớp {lop.ma_lop} đã đủ {lop.si_so_toi_da} sinh viên, không còn chỗ."
        )

    # 8. Không trùng lịch với lớp đã đăng ký cùng học kỳ
    for r in current:
        if _overlaps(lop, r.lop_hoc_phan):
            raise conflict(
                "TRUNG_LICH",
                f"Lớp {lop.ma_lop} ({schedule_label(lop)}) trùng lịch với lớp đã đăng ký "
                f"{r.lop_hoc_phan.ma_lop} ({schedule_label(r.lop_hoc_phan)}).",
            )

    # 9. Tổng tín chỉ sau đăng ký không vượt giới hạn
    limit = (
        lop.hoc_ky.tin_chi_toi_da_canh_bao if summary.canh_bao_hoc_vu else lop.hoc_ky.tin_chi_toi_da
    )
    total = sum(r.lop_hoc_phan.hoc_phan.so_tin_chi for r in current) + lop.hoc_phan.so_tin_chi
    if total > limit:
        note = " (đang bị cảnh báo học vụ)" if summary.canh_bao_hoc_vu else ""
        raise conflict(
            "VUOT_TIN_CHI_TOI_DA",
            f"Tổng tín chỉ sau khi đăng ký là {total}, vượt mức tối đa {limit} tín chỉ{note}.",
        )

    if dry_run:
        return _to_out(lop, "hop_le")

    # Ghi: có bản ghi đã hủy (UNIQUE sinh_vien_id + lop_hoc_phan_id) thì kích hoạt lại
    record = registration_repo.get(db, sv.id, lop.id)
    if record is None:
        db.add(
            DangKyHocPhan(
                sinh_vien_id=sv.id,
                lop_hoc_phan_id=lop.id,
                trang_thai="da_dang_ky",
                thoi_gian_dang_ky=to_db(now),
            )
        )
    else:
        record.trang_thai = "da_dang_ky"
        record.thoi_gian_dang_ky = to_db(now)
        record.thoi_gian_huy = None
    db.flush()
    return _to_out(lop, "da_dang_ky")


def cancel(db: Session, ma_sv: str, ma_lop: str, now: datetime) -> RegistrationOut:
    """Hủy đăng ký — chỉ trong thời gian đăng ký của học kỳ. Không commit."""
    sv = _lock_student(db, ma_sv)
    lop = _lock_section(db, ma_lop)
    _ensure_registration_open(lop, now)

    record = registration_repo.get(db, sv.id, lop.id)
    if record is None or record.trang_thai != "da_dang_ky":
        raise conflict("CHUA_DANG_KY_LOP", f"Em chưa đăng ký lớp {lop.ma_lop} nên không thể hủy.")
    record.trang_thai = "da_huy"
    record.thoi_gian_huy = to_db(now)
    db.flush()
    return _to_out(lop, "da_huy")


MAX_BUNDLE = 8


def register_bundle(
    db: Session, ma_sv: str, ma_lops: list[str], now: datetime, dry_run: bool = False
) -> BundleOut:
    """Đăng ký nhiều lớp NGUYÊN KHỐI: chạy `register` lần lượt (theo mã lớp — thứ tự khóa cố
    định, tránh deadlock) trong cùng giao dịch; lớp sau thấy lớp trước (trùng lịch / vượt tín chỉ
    TRONG gói cũng bị bắt). Một lớp lỗi -> ném lỗi của lớp đó, tầng gọi rollback cả gói.

    `dry_run=True`: vẫn ghi tạm (flush) để bắt lỗi trong gói; router `bundle/check` rollback.
    Không commit.
    """
    codes = [m.strip().upper() for m in ma_lops]
    if not codes or len(codes) > MAX_BUNDLE or len(set(codes)) != len(codes):
        raise invalid(
            "DANH_SACH_LOP_KHONG_HOP_LE",
            f"Danh sách lớp phải có 1–{MAX_BUNDLE} mã lớp, không trùng nhau.",
        )
    done: list[RegistrationOut] = []
    for ma_lop in sorted(codes):
        try:
            out = register(db, ma_sv, ma_lop, now)
        except BusinessError as exc:
            raise BusinessError(exc.code, f"Lớp {ma_lop}: {exc.message}", exc.status) from exc
        done.append(out.model_copy(update={"trang_thai": "hop_le"}) if dry_run else out)
    return BundleOut(
        trang_thai="hop_le" if dry_run else "da_dang_ky",
        lop=done,
        tong_tin_chi=sum(r.tin_chi for r in done),
    )
