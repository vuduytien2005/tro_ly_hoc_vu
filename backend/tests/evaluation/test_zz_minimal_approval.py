"""Cấu hình tối giản (TN3): duyệt phải băm bản mô tả GỐC của server, nếu không lần đồng bộ sau
thấy mã băm khác -> tự tắt nhầm công cụ vừa duyệt.

Tệp riêng (tên zz_ để chạy sau cùng): harness giữ giao dịch dài trên CSDL, mở harness thứ hai
khi harness của module khác còn mở sẽ bị khóa chờ vô hạn."""

import sys
from pathlib import Path

import anyio

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.common import load_config  # noqa: E402
from evaluation.harness import AgentHarness  # noqa: E402

from tests.evaluation.test_harness import counts  # noqa: E402


def test_minimal_config_approval_survives_resync() -> None:
    before = counts()
    with AgentHarness(load_config("agent_gemini_toi_gian"), dry_run=True) as h:
        with h.iso.factory() as db:
            anyio.run(h.registry.sync, db)
            assert h.registry.policies(db)["renew_book"].bat is True
        with h.extra_server("duyet_nham"), h.iso.factory() as db:
            assert h.registry.policies(db)["get_campus_events"].bat is True
    assert counts() == before
