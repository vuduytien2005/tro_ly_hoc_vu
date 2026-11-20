"""Quản lý hồ sơ sinh viên — vai trò "phòng đào tạo" của hệ thống QLSV giả lập (AD-10).

Thêm, sửa hồ sơ, đổi trạng thái học tập. Không xóa (sinh viên đã có điểm, đơn, đăng ký -> ràng
buộc khóa ngoại; trường thật cũng không xóa mà chuyển trạng thái thoi_hoc / tot_nghiep).
Không đổi được ma_sv: đó là khóa định danh mà tài khoản trợ lý và mọi công cụ MCP gắn vào.
"""

from datetime import date

from sqlalchemy.orm import Session

from src.qlsv_api.errors import conflict, invalid
from src.qlsv_api.models import KhoaHoc, Nganh, SinhVien
from src.qlsv_api.repositories import students as student_repo
from src.qlsv_api.schemas import (
    ProgramOut,
    StudentCreateIn,
    StudentListOut,
    StudentProfileOut,
    StudentUpdateIn,
)
from src.qlsv_api.services.academic_service import get_profile
from src.qlsv_api.services.common import get_student_or_404


def list_students(
    db: Session, q: str | None, trang_thai: str | None, page: int, page_size: int
) -> StudentListOut:
    text = q.strip() if q else None
    rows = student_repo.list_page(db, text, trang_thai, (page - 1) * page_size, page_size)
    return StudentListOut(
        tong=student_repo.count(db, text, trang_thai),
        trang_so=page,
        so_moi_trang=page_size,
        sinh_vien=[_profile(sv) for sv in rows],
    )


def list_programs(db: Session) -> list[ProgramOut]:
    return [
        ProgramOut(
            ma_nganh=p.nganh.ma_nganh, ten_nganh=p.nganh.ten_nganh, ma_khoa=p.khoa_hoc.ma_khoa
        )
        for p in student_repo.list_programs(db)
    ]


def create_student(db: Session, body: StudentCreateIn, today: date) -> StudentProfileOut:
    if student_repo.get_by_ma_sv(db, body.ma_sv) is not None:
        raise conflict("SV_DA_TON_TAI", f"Mã sinh viên {body.ma_sv} đã tồn tại.")
    _check_email_free(db, body.email, owner=None)
    _check_birth_date(body.ngay_sinh, today)
    nganh, khoa = _resolve_program(db, body.ma_nganh, body.ma_khoa)
    sv = SinhVien(
        ma_sv=body.ma_sv,
        ho_ten=body.ho_ten,
        email=body.email,
        ngay_sinh=body.ngay_sinh,
        gioi_tinh=body.gioi_tinh,
        nganh_id=nganh.id,
        khoa_hoc_id=khoa.id,
        lop=body.lop,
        trang_thai=body.trang_thai,
    )
    db.add(sv)
    db.flush()  # lỗi UNIQUE (hai cán bộ thêm cùng lúc) nổ ra ở đây -> router rollback
    return get_profile(db, sv.ma_sv)


def update_student(
    db: Session, ma_sv: str, body: StudentUpdateIn, today: date
) -> StudentProfileOut:
    get_student_or_404(db, ma_sv)
    sv = student_repo.lock_by_ma_sv(db, ma_sv)  # khóa hàng: không sửa chồng lên nhau
    assert sv is not None
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in changes:
        _check_email_free(db, changes["email"], owner=sv.ma_sv)
    if "ngay_sinh" in changes:
        _check_birth_date(changes["ngay_sinh"], today)
    if "ma_nganh" in changes or "ma_khoa" in changes:
        current = student_repo.get_by_ma_sv(db, ma_sv)
        assert current is not None
        nganh, khoa = _resolve_program(
            db,
            changes.pop("ma_nganh", current.nganh.ma_nganh),
            changes.pop("ma_khoa", current.khoa_hoc.ma_khoa),
        )
        sv.nganh_id, sv.khoa_hoc_id = nganh.id, khoa.id
    for field in ("ho_ten", "email", "ngay_sinh", "gioi_tinh", "lop", "trang_thai"):
        if field in changes:
            setattr(sv, field, changes[field])
    db.flush()
    db.expire(sv)  # nạp lại quan hệ ngành / khóa mới
    return get_profile(db, ma_sv)


def _profile(sv: SinhVien) -> StudentProfileOut:
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


def _check_email_free(db: Session, email: str, owner: str | None) -> None:
    current_owner = student_repo.email_owner(db, email)
    if current_owner is not None and current_owner != owner:
        raise conflict("EMAIL_DA_TON_TAI", f"Email {email} đã thuộc sinh viên {current_owner}.")


def _check_birth_date(ngay_sinh: date, today: date) -> None:
    if not date(today.year - 100, 1, 1) <= ngay_sinh <= date(today.year - 14, 12, 31):
        raise invalid("NGAY_SINH_KHONG_HOP_LE", "Ngày sinh không hợp lệ.")


def _resolve_program(db: Session, ma_nganh: str, ma_khoa: str) -> tuple[Nganh, KhoaHoc]:
    nganh = student_repo.get_nganh(db, ma_nganh)
    if nganh is None:
        raise invalid("NGANH_KHONG_TON_TAI", f"Không có ngành {ma_nganh}.")
    khoa = student_repo.get_khoa_hoc(db, ma_khoa)
    if khoa is None:
        raise invalid("KHOA_HOC_KHONG_TON_TAI", f"Không có khóa {ma_khoa}.")
    if student_repo.get_program(db, nganh.id, khoa.id) is None:
        raise invalid(
            "CHUONG_TRINH_KHONG_TON_TAI",
            f"Ngành {nganh.ten_nganh} chưa có chương trình đào tạo cho khóa {ma_khoa}.",
        )
    return nganh, khoa
