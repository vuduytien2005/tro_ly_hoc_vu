"""Thời gian theo giờ Việt Nam.

- Trong code luôn dùng datetime CÓ múi giờ (aware).
- Cột DATETIME2 của SQL Server không lưu múi giờ -> quy ước lưu giờ Việt Nam, chuyển đổi qua
  `to_db()` / `from_db()`.
- `DEMO_NOW` trong .env cố định "hiện tại" để demo ổn định (vd. luôn đang trong
  thời gian đăng ký học phần).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.shared.config import get_settings

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now() -> datetime:
    """Thời điểm hiện tại theo giờ Việt Nam; ưu tiên DEMO_NOW nếu có."""
    demo = get_settings().demo_now
    if demo is not None:
        return demo.astimezone(VN_TZ) if demo.tzinfo else demo.replace(tzinfo=VN_TZ)
    return datetime.now(VN_TZ)


def to_db(dt: datetime) -> datetime:
    """datetime aware -> datetime naive theo giờ Việt Nam để ghi vào cột DATETIME2."""
    if dt.tzinfo is None:
        raise ValueError("Cần datetime có múi giờ (aware)")
    return dt.astimezone(VN_TZ).replace(tzinfo=None)


def from_db(dt: datetime | None) -> datetime | None:
    """datetime naive đọc từ CSDL (giờ Việt Nam) -> datetime aware."""
    if dt is None:
        return None
    return dt.replace(tzinfo=VN_TZ) if dt.tzinfo is None else dt.astimezone(VN_TZ)


def wall_clock() -> datetime:
    """Giờ THẬT (bỏ qua DEMO_NOW), giờ Việt Nam. Dùng cho mọi hạn bảo mật đo thời gian trôi qua:
    hạn token, hạn xác nhận hành động. DEMO_NOW cố định nên không dùng được cho các hạn này."""
    return datetime.now(VN_TZ)
