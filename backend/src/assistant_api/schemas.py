"""Schema vào/ra của assistant_api (Pydantic v2). Thời gian trả về ISO 8601, múi giờ +07:00."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from src.shared.time import from_db

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _aware(value: datetime | None) -> datetime | None:
    return from_db(value)


class LoginIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    mat_khau: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    ho_ten: str
    vai_tro: str
    ma_sv: str | None
    ma_khoa: str | None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    het_han_luc: datetime
    nguoi_dung: UserOut


class ConversationIn(BaseModel):
    tieu_de: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


class ConversationPatch(BaseModel):
    tieu_de: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tieu_de: str
    kenh: str
    created_at: datetime
    updated_at: datetime

    _tz = field_validator("created_at", "updated_at", mode="after")(_aware)


class MessageIn(BaseModel):
    noi_dung: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vai_tro: Literal["user", "assistant"]
    noi_dung: str
    trich_dan: list[dict[str, Any]] | None = None
    danh_gia: int | None = None  # điểm người dùng đã đánh giá tin này (1 / -1)
    created_at: datetime

    _tz = field_validator("created_at", mode="after")(_aware)


class PendingActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ma: str
    ten_cong_cu: str
    mo_ta: str
    het_han_luc: datetime

    _tz = field_validator("het_han_luc", mode="after")(_aware)


class MessagesOut(BaseModel):
    tin_nhan: list[MessageOut]
    hanh_dong_cho_xac_nhan: list[PendingActionOut] = Field(default_factory=list)


class TraceStepOut(BaseModel):
    """Một lượt gọi công cụ cho bảng "Bên trong Agent" (KHÔNG có kết quả công cụ)."""

    id: int
    thoi_diem: datetime
    ten_cong_cu: str
    nhan: str
    mcp_server: str
    tham_so_llm: dict[str, Any] | None  # None = hệ thống tự gọi
    tham_so_he_thong_dien: dict[str, Any]
    trang_thai: str
    ly_do: str | None
    thoi_gian_ms: int | None

    _tz = field_validator("thoi_diem", mode="after")(_aware)


class TraceOut(BaseModel):
    luot_goi: list[TraceStepOut]


class FeedbackIn(BaseModel):
    diem: Literal[1, -1]
    gop_y: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class FeedbackOut(BaseModel):
    tin_nhan_id: int
    diem: int
    gop_y: str | None


class ActionCancelOut(BaseModel):
    ma: str
    trang_thai: str
    tin_nhan: MessageOut
