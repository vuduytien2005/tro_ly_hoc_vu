from collections.abc import Callable
from datetime import datetime
from typing import Annotated, TypeVar

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.shared.db import get_qlsv_session
from src.shared.security import INTERNAL_TOKEN_HEADER
from src.shared.time import now

T = TypeVar("T")

# Chỉ để Swagger (/docs) hiện nút "Authorize" nhập token; việc CHẶN do middleware ở main.py.
internal_token_scheme = APIKeyHeader(name=INTERNAL_TOKEN_HEADER, auto_error=False)
InternalAuth = Security(internal_token_scheme)


def get_now() -> datetime:
    """Thời điểm hiện tại (ưu tiên DEMO_NOW). Test có thể override dependency này."""
    return now()


DbSession = Annotated[Session, Depends(get_qlsv_session)]
Now = Annotated[datetime, Depends(get_now)]


def run_in_transaction(db: Session, action: Callable[[], T]) -> T:
    """Chạy thao tác ghi; thành công thì commit (nhả khóa UPDLOCK), lỗi thì rollback."""
    try:
        result = action()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
