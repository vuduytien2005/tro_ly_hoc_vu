"""Gọi một tool MCP và ghi nhật ký — dùng chung cho vòng lặp Agent, bước xác nhận hành động,
và API gọi trực tiếp (/api/my/requests).

Quy tắc 3 (CLAUDE.md): MỌI lần gọi công cụ đều có một dòng `luot_goi_cong_cu`.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.assistant_api.mcp_client.client import McpClient, McpUnavailableError
from src.assistant_api.models import LuotGoiCongCu

logger = logging.getLogger(__name__)

Result = dict[str, Any] | list[Any]


def failure(code: str, message: str) -> dict[str, Any]:
    """Cùng dạng lỗi mà MCP server trả về (mcp_servers/common.py)."""
    return {"thanh_cong": False, "ma_loi": code, "thong_bao": message}


@dataclass
class Outcome:
    result: Result
    status: str  # thanh_cong | loi | bi_tu_choi | cho_xac_nhan | da_huy
    reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


async def invoke(client: McpClient, server: str, name: str, args: dict[str, Any]) -> Outcome:
    """Gọi MCP; kết quả `thanh_cong: false` (lỗi nghiệp vụ) -> trạng thái 'loi'."""
    try:
        outcome = await client.call_tool(server, name, args)
    except McpUnavailableError as exc:
        return Outcome(
            failure(
                "DICH_VU_KHONG_KHA_DUNG",
                "Hệ thống liên quan đang tạm gián đoạn, vui lòng thử lại sau.",
            ),
            "loi",
            str(exc),
        )
    except Exception as exc:
        logger.exception("Gọi tool %s lỗi", name)
        return Outcome(failure("LOI_HE_THONG", "Lỗi khi gọi công cụ."), "loi", repr(exc))
    if not outcome.ok:
        return Outcome(
            failure("LOI_CONG_CU", "Công cụ báo lỗi khi xử lý yêu cầu."), "loi", outcome.error
        )
    data = outcome.data
    if isinstance(data, dict) and data.get("thanh_cong") is False:
        return Outcome(data, "loi", str(data.get("thong_bao") or data.get("ma_loi")))
    return Outcome(data, "thanh_cong")


def parse_arguments(raw: str | None) -> dict[str, Any] | None:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


class ToolLog:
    """Một dòng nhật ký: tạo ngay, ghi khi có kết quả (`save`)."""

    def __init__(
        self,
        db: Session,
        *,
        user_id: int,
        conversation_id: int | None,
        server: str,
        tool: str,
        llm_args: dict[str, Any] | None,
    ) -> None:
        self.db = db
        self.started = time.perf_counter()
        self.row = LuotGoiCongCu(
            hoi_thoai_id=conversation_id,
            nguoi_dung_id=user_id,
            mcp_server=server[:50],
            ten_cong_cu=tool[:100],
            tham_so={},
            tham_so_llm=llm_args,
        )

    def set_args(self, args: dict[str, Any]) -> None:
        self.row.tham_so = args

    def save(self, outcome: Outcome, *, commit: bool = True) -> LuotGoiCongCu:
        update_log(self.row, outcome, self.started)
        self.db.add(self.row)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.row


def update_log(row: LuotGoiCongCu, outcome: Outcome, started: float) -> None:
    row.ket_qua = outcome.result
    row.trang_thai = outcome.status
    row.ly_do = outcome.reason[:500] if outcome.reason else None
    row.thoi_gian_ms = int((time.perf_counter() - started) * 1000)
