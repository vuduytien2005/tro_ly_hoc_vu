"""Kiểu dữ liệu vào/ra của qlsv_api (Pydantic v2). Khóa tiếng Việt không dấu.

Số điểm/GPA trả dạng float (JSON number) thay vì Decimal (Pydantic sẽ biến Decimal
thành chuỗi). Thời gian luôn có múi giờ +07:00.
"""

from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

TrangThaiDon = Literal["moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat"]
LoaiDon = Literal["giay_xac_nhan_sv", "bao_luu", "phuc_khao"]


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


class DeferralContent(Schema):
    """bao_luu"""

    ly_do: NonEmptyStr
    so_hoc_ky: int = Field(default=1, ge=1, le=2)
    tu_hoc_ky: NonEmptyStr


class RegradeContent(Schema):
    """phuc_khao"""

    ma_hp: NonEmptyStr
    ly_do: NonEmptyStr


REQUEST_CONTENT_SCHEMAS: dict[str, type[Schema]] = {
    "giay_xac_nhan_sv": CertificateContent,
    "bao_luu": DeferralContent,
    "phuc_khao": RegradeContent,
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
    created_at: datetime


class RequestUpdateIn(Schema):
    trang_thai: TrangThaiDon
    ghi_chu_xu_ly: str | None = None
