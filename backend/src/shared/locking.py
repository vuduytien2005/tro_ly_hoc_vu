"""Khóa hàng khi đọc để ghi (pessimistic locking) trên SQL Server.

LƯU Ý QUAN TRỌNG: với SQL Server, SQLAlchemy BỎ QUA `select(...).with_for_update()`
một cách im lặng (câu SQL sinh ra không có khóa nào). Vì vậy phải dùng table hint:
    WITH (UPDLOCK, ROWLOCK)
- UPDLOCK: giữ khóa "update" đến hết transaction; transaction khác muốn khóa cùng hàng
  phải chờ -> hai yêu cầu đăng ký cùng lớp được xử lý tuần tự.
- ROWLOCK: chỉ khóa hàng, không khóa cả trang/bảng.
- HOLDLOCK (khi cần): khóa cả KHOẢNG khóa chỉ mục, chặn transaction khác chèn giá trị
  mới vào khoảng đó (dùng khi sinh số thứ tự mã đơn).
- READPAST (việc nền): BỎ QUA hàng đang bị transaction khác khóa thay vì chờ -> việc dọn thẻ hết
  hạn không tranh chấp với người đang bấm Xác nhận.
"""

from typing import Any, TypeVar

from sqlalchemy import Select

S = TypeVar("S", bound=Select[Any])

UPDATE_LOCK = "WITH (UPDLOCK, ROWLOCK)"
RANGE_UPDATE_LOCK = "WITH (UPDLOCK, HOLDLOCK)"
SKIP_LOCKED_UPDATE_LOCK = "WITH (UPDLOCK, ROWLOCK, READPAST)"


def lock_for_update(stmt: S, entity: Any) -> S:
    """Thêm `WITH (UPDLOCK, ROWLOCK)` cho bảng của `entity` trong câu SELECT."""
    return stmt.with_hint(entity, UPDATE_LOCK, "mssql")


def lock_skip_locked(stmt: S, entity: Any) -> S:
    """Thêm `WITH (UPDLOCK, ROWLOCK, READPAST)`: khóa hàng đọc được, bỏ qua hàng đang bị khóa."""
    return stmt.with_hint(entity, SKIP_LOCKED_UPDATE_LOCK, "mssql")


def lock_range_for_update(stmt: S, entity: Any) -> S:
    """Thêm `WITH (UPDLOCK, HOLDLOCK)`: khóa cả khoảng giá trị đã đọc."""
    return stmt.with_hint(entity, RANGE_UPDATE_LOCK, "mssql")
