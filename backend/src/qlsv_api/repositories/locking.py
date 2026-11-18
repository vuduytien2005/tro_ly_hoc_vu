"""Khóa hàng khi đọc để ghi (pessimistic locking) trên SQL Server.

LƯU Ý QUAN TRỌNG: với SQL Server, SQLAlchemy BỎ QUA `select(...).with_for_update()`
một cách im lặng (câu SQL sinh ra không có khóa nào). Vì vậy phải dùng table hint:
    WITH (UPDLOCK, ROWLOCK)
- UPDLOCK: giữ khóa "update" đến hết transaction; transaction khác muốn khóa cùng hàng
  phải chờ -> hai yêu cầu đăng ký cùng lớp được xử lý tuần tự.
- ROWLOCK: chỉ khóa hàng, không khóa cả trang/bảng.
- HOLDLOCK (khi cần): khóa cả KHOẢNG khóa chỉ mục, chặn transaction khác chèn giá trị
  mới vào khoảng đó (dùng khi sinh số thứ tự mã đơn).
"""

from typing import Any, TypeVar

from sqlalchemy import Select

S = TypeVar("S", bound=Select[Any])

UPDATE_LOCK = "WITH (UPDLOCK, ROWLOCK)"
RANGE_UPDATE_LOCK = "WITH (UPDLOCK, HOLDLOCK)"


def lock_for_update(stmt: S, entity: Any) -> S:
    """Thêm `WITH (UPDLOCK, ROWLOCK)` cho bảng của `entity` trong câu SELECT."""
    return stmt.with_hint(entity, UPDATE_LOCK, "mssql")


def lock_range_for_update(stmt: S, entity: Any) -> S:
    """Thêm `WITH (UPDLOCK, HOLDLOCK)`: khóa cả khoảng giá trị đã đọc."""
    return stmt.with_hint(entity, RANGE_UPDATE_LOCK, "mssql")
