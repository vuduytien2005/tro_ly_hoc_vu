"""Schema vào/ra của API quản trị (/api/admin/*). Thời gian trả về ISO 8601, múi giờ +07:00."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from src.shared.time import from_db

LoaiVanBan = Literal["quy_che", "so_tay", "quy_dinh", "huong_dan", "thong_bao"]
ChienLuocChunk = Literal["theo_dieu", "co_dinh", "ngu_nghia"]
MucRuiRo = Literal["doc", "ghi", "nhay_cam"]
TrangThaiDuyet = Literal["da_duyet", "moi", "thay_doi"]
TrangThaiLuotGoi = Literal["thanh_cong", "loi", "bi_tu_choi", "cho_xac_nhan", "da_huy"]


def _aware(value: datetime | None) -> datetime | None:
    return from_db(value)


# ----- Tài liệu ---------------------------------------------------------------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ten: str
    loai: str
    phien_ban: str
    ap_dung_tu_khoa: int | None
    ap_dung_den_khoa: int | None
    ngay_hieu_luc: date | None
    ten_tep: str
    trang_thai: str
    chien_luoc_chunk: str
    so_doan: int
    loi: str | None
    created_at: datetime
    updated_at: datetime

    _tz = field_validator("created_at", "updated_at", mode="after")(_aware)


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thu_tu: int
    chuong: str | None
    dieu: str | None
    khoan: str | None
    trang: int | None
    so_token: int | None
    noi_dung: str


class ChunkPage(BaseModel):
    tong: int
    trang_so: int
    so_moi_trang: int
    doan: list[ChunkOut]


class RagSearchIn(BaseModel):
    cau_hoi: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    ma_khoa: str | None = Field(default=None, max_length=10)
    top_k: int = Field(default=5, ge=1, le=20)
    use_vector: bool = True
    use_keyword: bool = True
    use_version_filter: bool = True
    use_rerank: bool = False


# ----- MCP & quyền ------------------------------------------------------------
class ToolOut(BaseModel):
    id: int
    ten: str
    mo_ta: str
    muc_rui_ro: str
    can_xac_nhan: bool
    bat: bool
    co_tren_server: bool  # server hiện có cung cấp tool này không (theo lần đồng bộ gần nhất)
    title: str | None = None  # tên hiển thị server khai báo
    mo_ta_day_du: str | None = None  # mô tả ĐẦY ĐỦ server gửi cho LLM (để quản trị viên duyệt)
    tham_so: dict[str, Any] | None = None  # input schema LLM thấy (đã ẩn ma_sv/ma_khoa)
    # readOnlyHint server TỰ khai báo: chỉ là gợi ý, quản trị viên tự quyết mức rủi ro
    chi_doc_theo_server: bool | None = None
    duyet: TrangThaiDuyet = "da_duyet"


class SkippedTool(BaseModel):
    ten: str
    trung_voi: str  # server đang giữ tên công cụ này


class McpServerOut(BaseModel):
    id: int
    ten: str
    mo_ta: str
    dia_chi: str
    bat: bool
    trang_thai: str  # "ok" | "tắt" | thông báo lỗi kết nối | "chưa đồng bộ"
    cong_cu: list[ToolOut]
    cong_cu_bi_bo_qua: list[SkippedTool] = []  # trùng tên với công cụ của server khác


McpName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
McpAddress = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class McpCheckIn(BaseModel):
    dia_chi: McpAddress


class ToolPreview(BaseModel):
    ten: str
    title: str | None
    mo_ta: str
    tham_so: dict[str, Any]
    chi_doc_theo_server: bool | None
    trung_ten_voi: str | None  # server đã đăng ký có công cụ cùng tên (công cụ này sẽ bị bỏ)


class McpCheckOut(BaseModel):
    cong_cu: list[ToolPreview]


class McpServerCreate(BaseModel):
    ten: McpName
    mo_ta: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] = ""
    dia_chi: McpAddress


class McpServerPatch(BaseModel):
    mo_ta: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    dia_chi: McpAddress | None = None
    bat: bool | None = None


class ToolPatch(BaseModel):
    bat: bool | None = None
    can_xac_nhan: bool | None = None
    muc_rui_ro: MucRuiRo | None = None


# ----- Nhật ký ----------------------------------------------------------------
class AuditUser(BaseModel):
    id: int
    ho_ten: str
    email: str


class AuditLogOut(BaseModel):
    id: int
    created_at: datetime
    nguoi_dung: AuditUser
    hoi_thoai_id: int | None
    mcp_server: str
    ten_cong_cu: str
    trang_thai: str
    ly_do: str | None
    thoi_gian_ms: int | None
    tham_so: dict[str, Any]
    tham_so_llm: dict[str, Any] | None
    # tham_so_llm khác tham_so: assistant_api đã điền/ghi đè ma_sv, ma_khoa (quy tắc bảo mật 1)
    da_tiem_ngu_canh: bool

    _tz = field_validator("created_at", mode="after")(_aware)


class AuditLogDetail(AuditLogOut):
    ket_qua: dict[str, Any] | list[Any] | None


class AuditLogPage(BaseModel):
    tong: int
    trang_so: int
    so_moi_trang: int
    luot_goi: list[AuditLogOut]


# ----- Thống kê ---------------------------------------------------------------
class ToolUsage(BaseModel):
    ten_cong_cu: str
    so_lan: int
    so_loi: int  # loi + bi_tu_choi


class DailyCount(BaseModel):
    ngay: date
    so_cau_hoi: int


class DislikedAnswer(BaseModel):
    tin_nhan_id: int
    hoi_thoai_id: int
    nguoi_dung: str
    cau_hoi: str | None
    cau_tra_loi: str
    gop_y: str | None
    created_at: datetime

    _tz = field_validator("created_at", mode="after")(_aware)


class StatsOut(BaseModel):
    tu: date
    den: date
    so_hoi_thoai: int
    so_cau_hoi: int
    so_danh_gia: int
    so_huu_ich: int
    ti_le_huu_ich: float | None  # None khi chưa có đánh giá
    thoi_gian_phan_hoi_tb_ms: int | None
    so_luot_goi_cong_cu: int
    top_cong_cu: list[ToolUsage]
    theo_ngay: list[DailyCount]
    cau_bi_che: list[DislikedAnswer]


# ----- Tài khoản (AD-09) ---------------------------------------------------------
VaiTro = Literal["sinh_vien", "admin"]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    ho_ten: str
    vai_tro: str
    ma_sv: str | None
    ma_khoa: str | None
    dang_hoat_dong: bool
    created_at: datetime

    _tz = field_validator("created_at", mode="after")(_aware)


class AccountPage(BaseModel):
    tong: int
    trang_so: int
    so_moi_trang: int
    nguoi_dung: list[AccountOut]


class AccountCreateIn(BaseModel):
    ma_sv: Annotated[
        str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=20)
    ]
    mat_khau: str = Field(max_length=200)  # quy tắc độ mạnh kiểm tra ở router (lỗi MAT_KHAU_YEU)


class AccountPatch(BaseModel):
    dang_hoat_dong: bool


class PasswordResetIn(BaseModel):
    mat_khau: str = Field(max_length=200)


# ----- Hồ sơ sinh viên trên QLSV (AD-10) — qlsv_api kiểm tra chi tiết, ở đây chỉ chặn thô ---------
GioiTinh = Literal["nam", "nu", "khac"]
TrangThaiSv = Literal["dang_hoc", "bao_luu", "thoi_hoc", "tot_nghiep"]


class LinkedAccount(BaseModel):
    id: int
    dang_hoat_dong: bool


class StudentAdminOut(BaseModel):
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
    tai_khoan: LinkedAccount | None = None


class StudentAdminPage(BaseModel):
    tong: int
    trang_so: int
    so_moi_trang: int
    sinh_vien: list[StudentAdminOut]


class ProgramOut(BaseModel):
    ma_nganh: str
    ten_nganh: str
    ma_khoa: str


class StudentFields(BaseModel):
    ho_ten: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    ngay_sinh: date | None = None
    gioi_tinh: GioiTinh | None = None
    ma_nganh: str | None = Field(default=None, max_length=20)
    ma_khoa: str | None = Field(default=None, max_length=10)
    lop: str | None = Field(default=None, max_length=20)
    trang_thai: TrangThaiSv | None = None


class StudentCreateAdminIn(StudentFields):
    ma_sv: str = Field(max_length=20)
    ho_ten: str = Field(max_length=100)
    email: str = Field(max_length=255)
    ngay_sinh: date
    gioi_tinh: GioiTinh
    ma_nganh: str = Field(max_length=20)
    ma_khoa: str = Field(max_length=10)
    lop: str = Field(max_length=20)
    trang_thai: TrangThaiSv = "dang_hoc"
    # Cấp tài khoản trợ lý ngay sau khi thêm hồ sơ
    cap_tai_khoan: bool = False
    mat_khau: str | None = Field(default=None, max_length=200)


class StudentCreateAdminOut(BaseModel):
    sinh_vien: StudentAdminOut
    tai_khoan: AccountOut | None
    canh_bao: str | None = None  # hồ sơ đã thêm nhưng chưa cấp được tài khoản


# ----- Kho hỏi đáp cán bộ (nâng cấp 10) -----------------------------------------
PhongBan = Literal["dao_tao", "ctsv", "tai_chinh", "khac"]
CauHoiKho = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]
TraLoiKho = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=4000)]


class KnowledgeIn(BaseModel):
    cau_hoi: CauHoiKho
    tra_loi: TraLoiKho
    phong_ban: PhongBan = "khac"
    ma_don: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=30)] = None
    tin_nhan_id: int | None = None


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cau_hoi: str
    tra_loi: str
    phong_ban: str
    ma_don: str | None
    tin_nhan_id: int | None
    created_at: datetime
    updated_at: datetime

    _tz = field_validator("created_at", "updated_at", mode="after")(_aware)


class KnowledgeDocOut(BaseModel):
    """Trạng thái lập chỉ mục của văn bản kho ("Hỏi đáp cán bộ")."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trang_thai: str
    so_doan: int
    loi: str | None
    updated_at: datetime

    _tz = field_validator("updated_at", mode="after")(_aware)


class KnowledgeList(BaseModel):
    van_ban: KnowledgeDocOut | None
    muc: list[KnowledgeOut]
