"""Chống đăng ký trùng khi 2 yêu cầu đến CÙNG LÚC — kiểm tra khóa thật trên SQL Server.

Hai kết nối độc lập (như 2 sinh viên bấm cùng lúc):
- A đăng ký IT004.02 nhưng CHƯA commit -> đang giữ UPDLOCK trên hàng lớp IT004.02.
- B (SET LOCK_TIMEOUT 1000) đăng ký cùng lớp -> phải CHỜ khóa; sau 1 giây SQL Server báo
  lỗi 1222 "Lock request time out period exceeded". Nếu không có khóa, B sẽ đọc sĩ số cũ
  và chen vào -> test thất bại.
Cuối cùng rollback cả hai, không để lại dữ liệu.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.qlsv_api.services import registration_service
from src.shared.db import get_qlsv_engine
from tests.qlsv.conftest import DEMO_NOW

LOCK_TIMEOUT_ERROR = "1222"


def test_second_registration_waits_for_class_lock() -> None:
    engine = get_qlsv_engine()
    with engine.connect() as conn_a, engine.connect() as conn_b:
        tx_a, tx_b = conn_a.begin(), conn_b.begin()
        db_a, db_b = Session(bind=conn_a), Session(bind=conn_b)
        try:
            registration_service.register(db_a, "SV22001", "IT004.02", DEMO_NOW)  # giữ khóa

            db_b.execute(text("SET LOCK_TIMEOUT 1000"))
            with pytest.raises(DBAPIError) as e:
                registration_service.register(db_b, "SV22002", "IT004.02", DEMO_NOW)
            assert LOCK_TIMEOUT_ERROR in str(e.value.orig)
        finally:
            db_a.close()
            db_b.close()
            tx_a.rollback()
            tx_b.rollback()


def test_different_classes_do_not_block_each_other() -> None:
    """Đối chứng: khóa chỉ ở MỨC HÀNG — hai SV đăng ký hai lớp khác nhau không chờ nhau."""
    engine = get_qlsv_engine()
    with engine.connect() as conn_a, engine.connect() as conn_b:
        tx_a, tx_b = conn_a.begin(), conn_b.begin()
        db_a, db_b = Session(bind=conn_a), Session(bind=conn_b)
        try:
            registration_service.register(db_a, "SV22001", "IT004.02", DEMO_NOW)  # giữ khóa
            db_b.execute(text("SET LOCK_TIMEOUT 1000"))
            # Lớp khác (IT004.03), sinh viên khác: không chờ khóa, đăng ký thành công ngay.
            # (Nhờ READ_COMMITTED_SNAPSHOT, câu đếm sĩ số không bị chặn bởi hàng A vừa chèn.)
            out = registration_service.register(db_b, "SV22002", "IT004.03", DEMO_NOW)
            assert out.trang_thai == "da_dang_ky"
        finally:
            db_a.close()
            db_b.close()
            tx_a.rollback()
            tx_b.rollback()
