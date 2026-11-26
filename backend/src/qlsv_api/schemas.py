"""Kiểu dữ liệu vào/ra của qlsv_api (Pydantic v2). Khóa tiếng Việt không dấu.

Số điểm/GPA trả dạng float (JSON number) thay vì Decimal (Pydantic sẽ biến Decimal
thành chuỗi). Thời gian luôn có múi giờ +07:00.
"""

from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

TrangThaiDon = Literal["moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat"]
LoaiDon = Literal["giay_xac_nhan_sv", "bao_luu", "phuc_khao", "hoi_dap"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Học kỳ ----------
class SemesterOut(Schema):
    ma_hoc_ky: str
    ten: str
    ngay_bat_dau: date
    ngay_ket_thuc: date
    dang_ky_tu: datetime | None = None
    dang_ky_den: datetime | None = None
    tin_chi_toi_da: int


class CurrentSemestersOut(Schema):
    hien_tai: SemesterOut
    dang_mo_dang_ky: SemesterOut | None


# ---------- Sinh viên ----------
class StudentProfileOut(Schema):
    ma_sv: str
    ho_ten: str
    email: str
    ngay_sinh: date
    gioi_tinh: str
    lop: str
    ma_nganh: str
    nganh: str
    khoa: str
    trang_thai: str


# ---------- Quản lý hồ sơ sinh viên (phòng đào tạo, AD-10) ----------
GioiTinh = Literal["nam", "nu", "khac"]
TrangThaiSv = Literal["dang_hoc", "bao_luu", "thoi_hoc", "tot_nghiep"]
MaSv = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{3,20}$", max_length=20
    ),
]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255
    ),
]
HoTen = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Lop = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
MaNganh = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
MaKhoa = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=10)
]


class StudentCreateIn(Schema):
    ma_sv: MaSv
    ho_ten: HoTen
    email: Email
    ngay_sinh: date
    gioi_tinh: GioiTinh
    ma_nganh: MaNganh
    ma_khoa: MaKhoa
    lop: Lop
    trang_thai: TrangThaiSv = "dang_hoc"


class StudentUpdateIn(Schema):
    """Chỉ gửi trường cần đổi. Không đổi được ma_sv (khóa định danh, tài khoản trợ lý gắn vào)."""

    ho_ten: HoTen | None = None
    email: Email | None = None
    ngay_sinh: date | None = None
    gioi_tinh: GioiTinh | None = None
    ma_nganh: MaNganh | None = None
    ma_khoa: MaKhoa | None = None
    lop: Lop | None = None
    trang_thai: TrangThaiSv | None = None


class StudentListOut(Schema):
    tong: int
    trang_so: int
    so_moi_trang: int
    sinh_vien: list[StudentProfileOut]


class AttentionReason(Schema):
    loai: Literal["canh_bao_hoc_vu", "no_hoc_phi", "chua_du_dk_tot_nghiep"]
    muc_do: Literal["khan", "chu_y"]
    chi_tiet: str


class AttentionStudentOut(Schema):
    ma_sv: str
    ho_ten: str
    lop: str
    khoa: str
    ly_do: list[AttentionReason]


class AttentionListOut(Schema):
    """Sinh viên đang học cần chú ý, nhiều lý do khẩn trước (bổ sung 26/11/2026)."""

    tong: int
    sinh_vien: list[AttentionStudentOut]


class ProgramOut(Schema):
    """Một cặp ngành – khóa có chương trình đào tạo (chỉ những cặp này mới gán được cho SV)."""

    ma_nganh: str
    ten_nganh: str
    ma_khoa: str


class TranscriptRow(Schema):
    ma_hp: str
    ten_hp: str
    tin_chi: int
    hoc_ky: str
    diem_qua_trinh: float
    diem_thi: float
    diem_tong_ket: float
    diem_chu: str
    diem_he_4: float
    lan_hoc: int
    dat: bool


class TranscriptOut(Schema):
    ma_sv: str
    ma_hoc_ky: str | None = Field(description="Học kỳ đang lọc; None = toàn khóa")
    ket_qua: list[TranscriptRow]
    gpa_tich_luy: float
    tin_chi_tich_luy: int
    canh_bao_hoc_vu: bool


class MissingCourse(Schema):
    ma_hp: str
    ten_hp: str
    tin_chi: int
    bat_buoc: bool
    hoc_ky_goi_y: int


class CertificateStatus(Schema):
    ngoai_ngu: bool
    gdtc: bool
    gdqp: bool


class GraduationProgressOut(Schema):
    ma_sv: str
    tong_tin_chi_yeu_cau: int
    tin_chi_tich_luy: int
    gpa: float
    gpa_toi_thieu: float
    hoc_phan_con_thieu: list[MissingCourse]
    chung_chi: CertificateStatus
    yeu_cau_ngoai_ngu: bool
    du_dieu_kien: bool
    ly_do_chua_du: list[str]


# ---------- Lớp học phần / thời khóa biểu / lịch thi ----------
class SectionOut(Schema):
    ma_lop: str
    ma_hp: str
    ten_hp: str
    tin_chi: int
    hoc_ky: str
    giang_vien: str
    thu: int
    tiet_bat_dau: int
    tiet_ket_thuc: int
    phong: str
    lich: str
    si_so_toi_da: int
    da_dang_ky: int
    con_trong: int


class ScheduleRow(Schema):
    ma_lop: str
    ma_hp: str
    ten_hp: str
    tin_chi: int
    thu: int
    tiet_bat_dau: int
    tiet_ket_thuc: int
    lich: str
    phong: str
    giang_vien: str


class ScheduleOut(Schema):
    ma_sv: str
    ma_hoc_ky: str
    lop: list[ScheduleRow]
    tong_tin_chi: int


class ExamRow(Schema):
    ma_lop: str
    ma_hp: str
    ten_hp: str
    ngay_thi: date
    gio_bat_dau: time
    phong: str
    hinh_thuc: str


class ExamScheduleOut(Schema):
    ma_sv: str
    ma_hoc_ky: str
    lich_thi: list[ExamRow]


class TuitionOut(Schema):
    ma_sv: str
    ma_hoc_ky: str
    phai_nop: int
    da_nop: int
    con_no: int
    han_nop: date
    trang_thai: str


# ---------- Đăng ký học phần ----------
class RegistrationIn(Schema):
    ma_lop: NonEmptyStr


class RegistrationOut(Schema):
    thanh_cong: bool = True
    ma_lop: str
    ma_hp: str
    ten_hp: str
    tin_chi: int
    hoc_ky: str
    lich: str
    trang_thai: str


# ---------- Đơn từ ----------
class CertificateContent(Schema):
    """giay_xac_nhan_sv"""

    muc_dich: NonEmptyStr
    so_ban: int = Field(default=1, ge=1, le=5)


class DeferralContact(Schema):
    """Liên hệ trong thời gian bảo lưu — sinh viên điền qua biểu mẫu MCP elicitation."""

    so_dien_thoai: Annotated[str, StringConstraints(pattern=r"^0\d{9}$")]
    email_ca_nhan: Email | None = None


class DeferralContent(Schema):
    """bao_luu"""

    ly_do: NonEmptyStr
    so_hoc_ky: int = Field(default=1, ge=1, le=2)
    tu_hoc_ky: NonEmptyStr
    lien_he: DeferralContact | None = None


class RegradeContent(Schema):
    """phuc_khao"""

    ma_hp: NonEmptyStr
    ly_do: NonEmptyStr


class QuestionContent(Schema):
    """hoi_dap — câu hỏi sinh viên gửi cán bộ (qua công cụ ask_staff); câu trả lời của cán bộ
    nằm ở ghi_chu_xu_ly."""

    cau_hoi: NonEmptyStr = Field(max_length=1000)
    phong_ban: Literal["dao_tao", "ctsv", "tai_chinh", "khac"] = "khac"


REQUEST_CONTENT_SCHEMAS: dict[str, type[Schema]] = {
    "giay_xac_nhan_sv": CertificateContent,
    "bao_luu": DeferralContent,
    "phuc_khao": RegradeContent,
    "hoi_dap": QuestionContent,
}


class RequestCreateIn(Schema):
    loai_don: LoaiDon
    noi_dung: dict[str, Any]
    tao_boi: Literal["sinh_vien", "tro_ly_ai"] = "sinh_vien"


class RequestOut(Schema):
    ma_don: str
    loai_don: str
    noi_dung: dict[str, Any]
    trang_thai: str
    ghi_chu_xu_ly: str | None
    tao_boi: str
    created_at: datetime
    updated_at: datetime


class RequestSummaryOut(Schema):
    ma_don: str
    loai_don: str
    trang_thai: str
    tao_boi: str
    created_at: datetime
    updated_at: datetime


class StaffRequestOut(RequestOut):
    """Đơn kèm người nộp — cho trang duyệt đơn của cán bộ."""

    ma_sv: str
    ho_ten: str


class StaffRequestListOut(Schema):
    tong: int
    trang_so: int
    so_moi_trang: int
    don: list[StaffRequestOut]


class RequestUpdateIn(Schema):
    trang_thai: TrangThaiDon
    ghi_chu_xu_ly: str | None = None


# ----- Thư viện ------------------------------------------------------------------
class BorrowOut(Schema):
    muon_id: int
    ma_sach: str
    ten_sach: str
    tac_gia: str
    ngay_muon: date
    han_tra: date
    so_lan_gia_han: int
    qua_han: bool
    gia_han_duoc: bool
    ly_do_khong_gia_han: str | None


class BookOut(Schema):
    ma_sach: str
    ten_sach: str
    tac_gia: str
    nam_xb: int
    tong_so_ban: int
    so_ban_con: int


# ----- Kế hoạch học kỳ tới ----------------------------------------------------
class PlannedSection(Schema):
    ma_lop: str
    ma_hp: str
    ten_hp: str
    tin_chi: int
    lich: str
    bat_buoc: bool
    ly_do_chon: str


class ExcludedSection(Schema):
    ma_lop: str
    ma_loi: str  # LOP_DA_DAY | TRUNG_LICH | VUOT_TIN_CHI_TOI_DA
    ly_do: str


class ExcludedCourse(Schema):
    ma_hp: str
    ten_hp: str
    # DANG_HOC | CHUA_DAT_TIEN_QUYET | KHONG_CO_LOP_MO | KHONG_CON_LOP_PHU_HOP
    ma_loi: str
    ly_do: str
    lop: list[ExcludedSection] = []


class SemesterPlanOut(Schema):
    hoc_ky: str
    ten_hoc_ky: str
    tin_chi_toi_da: int
    tin_chi_da_dang_ky: int
    de_xuat: list[PlannedSection]
    tong_tin_chi_de_xuat: int
    bi_loai: list[ExcludedCourse]


# ----- Đăng ký cả gói ---------------------------------------------------------
class BundleIn(Schema):
    ma_lop: Annotated[list[NonEmptyStr], Field(min_length=1, max_length=8)]


class BundleOut(Schema):
    thanh_cong: bool = True
    trang_thai: str  # da_dang_ky | hop_le (chỉ kiểm tra)
    lop: list[RegistrationOut]
    tong_tin_chi: int
