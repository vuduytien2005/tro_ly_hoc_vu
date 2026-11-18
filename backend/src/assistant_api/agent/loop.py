"""Vòng lặp Agent (docs/02 mục 3): LLM <-> công cụ MCP, phát sự kiện SSE, ghi nhật ký.

Một lượt (một tin nhắn của sinh viên):
1. Lưu tin user; dựng messages = system + lịch sử gần nhất + tin user.
2. Lặp tối đa AGENT_MAX_STEPS bước: gọi LLM (stream token ra SSE). Không có tool_call -> lưu câu trả
   lời (đã hậu kiểm trích dẫn), phát `done`. Có tool_call -> với từng lời gọi: kiểm tra chính sách,
   tiêm ngữ cảnh, gọi MCP, GHI NHẬT KÝ (mọi trường hợp), nối kết quả vào messages.
3. Quá số bước -> trả lời cố định, đề nghị chia nhỏ câu hỏi.

Lịch sử gửi cho LLM chỉ gồm văn bản + tool_calls + kết quả tool (không có khối "thinking" của các
lượt trước — API Claude cho phép bỏ toàn bộ khối thinking cũ; trong CÙNG một lượt thì khối thinking
được gửi lại nguyên vẹn qua `LlmTurn.assistant_message`).
"""

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.agent.llm import LLM, LlmError, LlmTurn, ToolCall
from src.assistant_api.agent.prompts import system_prompt, tool_label
from src.assistant_api.agent.registry import (
    ContextInjectionError,
    ToolPolicy,
    ToolRegistry,
    inject_context,
)
from src.assistant_api.mcp_client.client import McpUnavailableError
from src.assistant_api.models import HoiThoai, LuotGoiCongCu, NguoiDung, TinNhan
from src.shared.config import get_settings

logger = logging.getLogger(__name__)

TOO_COMPLEX = "Yêu cầu quá phức tạp, em thử chia nhỏ câu hỏi nhé."
REFUSED = "Xin lỗi, mình không thể hỗ trợ yêu cầu này."
EMPTY = "Xin lỗi, mình chưa có câu trả lời phù hợp. Em thử hỏi lại theo cách khác nhé."
NEEDS_CONFIRMATION_LATER = (
    "Thao tác này cần sinh viên xác nhận trên giao diện; chức năng xác nhận chưa được bật "
    "trong phiên bản hiện tại. Hãy báo sinh viên thực hiện trực tiếp trên cổng thông tin."
)
CITATION_RE = re.compile(r"\[(\d{1,3})\]")
DEFAULT_TITLE = "Cuộc trò chuyện mới"
TITLE_MAX = 80


@dataclass(frozen=True)
class AgentEvent:
    event: str  # token | tool_start | tool_end | citations | pending_action | done | error
    data: Any


def make_title(content: str) -> str:
    text = " ".join(content.split())
    return text if len(text) <= TITLE_MAX else text[: TITLE_MAX - 1].rstrip() + "…"


def failure(code: str, message: str) -> dict[str, Any]:
    """Cùng dạng lỗi mà MCP server trả về (mcp_servers/common.py)."""
    return {"thanh_cong": False, "ma_loi": code, "thong_bao": message}


# ----- lịch sử hội thoại ---------------------------------------------------------
def to_llm_message(row: TinNhan) -> dict[str, Any]:
    if row.vai_tro == "tool":
        return {"role": "tool", "tool_call_id": row.tool_call_id, "content": row.noi_dung}
    message: dict[str, Any] = {"role": row.vai_tro, "content": row.noi_dung or None}
    if row.vai_tro == "assistant" and row.tool_calls:
        message["tool_calls"] = row.tool_calls
    return message


def sanitize_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bảo đảm lịch sử hợp lệ với API LLM khi có lượt bị gián đoạn (mất kết nối, lỗi LLM):
    - bắt đầu bằng tin user;
    - tool_call nào thiếu kết quả -> bỏ cả lời gọi lẫn kết quả lẻ;
    - tin user không được trả lời (hai tin user liền nhau) -> bỏ tin cũ;
    - tin assistant rỗng (không chữ, không tool_call) -> bỏ."""
    while messages and messages[0]["role"] != "user":
        messages = messages[1:]
    result: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            ids = [c["id"] for c in msg["tool_calls"]]
            results = []
            j = i + 1
            while j < len(messages) and messages[j]["role"] == "tool":
                results.append(messages[j])
                j += 1
            if sorted(r["tool_call_id"] for r in results) == sorted(ids):
                result.append(msg)
                result.extend(results)
            elif msg.get("content"):
                result.append({"role": "assistant", "content": msg["content"]})
            i = j
            continue
        if msg["role"] == "tool":
            i += 1  # kết quả lẻ, không có lời gọi tương ứng
            continue
        if msg["role"] == "assistant" and not msg.get("content"):
            i += 1
            continue
        if msg["role"] == "user" and result and result[-1]["role"] == "user":
            result.pop()
        result.append(msg)
        i += 1
    return result


def load_history(
    db: Session, conversation_id: int, before_id: int, limit: int
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(TinNhan)
        .where(TinNhan.hoi_thoai_id == conversation_id, TinNhan.id < before_id)
        .order_by(TinNhan.id.desc())
        .limit(limit)
    ).all()
    return sanitize_history([to_llm_message(r) for r in reversed(rows)])


# ----- trích dẫn -----------------------------------------------------------------
def collect_sources(result: Any) -> dict[int, dict[str, Any]]:
    """Kết quả search_regulations -> {so: thông tin đoạn} (không gồm nội dung)."""
    if not isinstance(result, dict):
        return {}
    sources = {}
    for d in result.get("doan") or []:
        if isinstance(d, dict) and isinstance(d.get("so"), int):
            sources[d["so"]] = {
                "so": d["so"],
                "doan_id": d.get("doan_id"),
                "van_ban_id": d.get("van_ban_id"),
                "van_ban": d.get("van_ban"),
                "phien_ban": d.get("phien_ban"),
                "dieu": d.get("dieu"),
                "khoan": d.get("khoan"),
                "trang": d.get("trang"),
            }
    return sources


def check_citations(
    text: str, sources: dict[int, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Hậu kiểm chống ảo giác: giữ [n] có thật trong kết quả tra cứu của lượt này, xóa [n] bịa."""
    used: list[int] = []

    def replace(match: re.Match[str]) -> str:
        n = int(match.group(1))
        if n in sources:
            if n not in used:
                used.append(n)
            return match.group(0)
        return ""

    cleaned = CITATION_RE.sub(replace, text) if sources or CITATION_RE.search(text) else text
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned, [sources[n] for n in used]


# ----- vòng lặp ------------------------------------------------------------------
class AgentRunner:
    def __init__(self, registry: ToolRegistry, llm: LLM) -> None:
        self.registry = registry
        self.llm = llm
        settings = get_settings()
        self.max_steps = settings.agent_max_steps
        self.history_limit = settings.agent_history_messages

    async def run(
        self,
        db: Session,
        user: NguoiDung,
        conversation: HoiThoai,
        content: str,
        now: datetime,
    ) -> AsyncIterator[AgentEvent]:
        started = time.perf_counter()
        user_msg = TinNhan(hoi_thoai_id=conversation.id, vai_tro="user", noi_dung=content)
        db.add(user_msg)
        if conversation.tieu_de in (None, "", DEFAULT_TITLE):
            conversation.tieu_de = make_title(content)
        else:
            # "Chạm" hội thoại để trigger cập nhật updated_at -> danh sách sắp mới nhất trước
            db.execute(
                update(HoiThoai)
                .where(HoiThoai.id == conversation.id)
                .values(tieu_de=HoiThoai.tieu_de)
            )
        db.commit()

        try:
            await self.registry.ensure_fresh(db)
            policies = self.registry.policies(db)
            tools = self.registry.tools_for_llm(policies)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt(user, now)},
                *load_history(db, conversation.id, user_msg.id, self.history_limit),
                {"role": "user", "content": content},
            ]
            sources: dict[int, dict[str, Any]] = {}
            tokens_in = tokens_out = 0

            for _step in range(self.max_steps):
                turn: LlmTurn | None = None
                async for item in self.llm.stream(messages, tools):
                    if isinstance(item, LlmTurn):
                        turn = item
                    else:
                        yield AgentEvent("token", {"text": item})
                assert turn is not None
                tokens_in += turn.input_tokens or 0
                tokens_out += turn.output_tokens or 0

                if not turn.tool_calls:
                    text = turn.text.strip()
                    if not text:
                        text = REFUSED if turn.refused else EMPTY
                        yield AgentEvent("token", {"text": text})
                    async for event in self._finish(
                        db, conversation, text, sources, tokens_in, tokens_out, started
                    ):
                        yield event
                    return

                db.add(
                    TinNhan(
                        hoi_thoai_id=conversation.id,
                        vai_tro="assistant",
                        noi_dung=turn.text,
                        tool_calls=turn.assistant_message.get("tool_calls"),
                    )
                )
                db.commit()
                messages.append(turn.assistant_message)

                for call in turn.tool_calls:
                    policy = policies.get(call.name)
                    if policy is not None and policy.available and not policy.can_xac_nhan:
                        yield AgentEvent(
                            "tool_start", {"ten": call.name, "nhan": tool_label(call.name)}
                        )
                    result, status = await self._execute(db, user, conversation, call, policy)
                    if call.name == "search_regulations" and status == "thanh_cong":
                        sources = collect_sources(result)
                    if policy is not None and policy.available and not policy.can_xac_nhan:
                        yield AgentEvent("tool_end", {"ten": call.name, "trang_thai": status})
                    result_text = json.dumps(result, ensure_ascii=False)
                    db.add(
                        TinNhan(
                            hoi_thoai_id=conversation.id,
                            vai_tro="tool",
                            noi_dung=result_text,
                            tool_call_id=call.id,
                        )
                    )
                    db.commit()
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": result_text}
                    )

            yield AgentEvent("token", {"text": TOO_COMPLEX})
            async for event in self._finish(
                db, conversation, TOO_COMPLEX, {}, tokens_in, tokens_out, started
            ):
                yield event
        except LlmError as exc:
            db.rollback()
            yield AgentEvent("error", {"detail": str(exc), "code": "LOI_MO_HINH_NGON_NGU"})
        except Exception:
            db.rollback()
            logger.exception("Lỗi vòng lặp Agent")
            yield AgentEvent(
                "error", {"detail": "Lỗi hệ thống, vui lòng thử lại sau.", "code": "LOI_HE_THONG"}
            )

    async def _finish(
        self,
        db: Session,
        conversation: HoiThoai,
        text: str,
        sources: dict[int, dict[str, Any]],
        tokens_in: int,
        tokens_out: int,
        started: float,
    ) -> AsyncIterator[AgentEvent]:
        text, citations = check_citations(text, sources)
        message = TinNhan(
            hoi_thoai_id=conversation.id,
            vai_tro="assistant",
            noi_dung=text,
            trich_dan=citations or None,
            so_token_vao=tokens_in or None,
            so_token_ra=tokens_out or None,
            thoi_gian_ms=int((time.perf_counter() - started) * 1000),
        )
        db.add(message)
        db.commit()
        if citations:
            yield AgentEvent("citations", citations)
        yield AgentEvent("done", {"tin_nhan_id": message.id})

    async def _execute(
        self,
        db: Session,
        user: NguoiDung,
        conversation: HoiThoai,
        call: ToolCall,
        policy: ToolPolicy | None,
    ) -> tuple[dict[str, Any] | list[Any], str]:
        """Thực thi MỘT lời gọi tool, LUÔN ghi 1 dòng nhật ký. Trả (kết quả, trạng thái)."""
        started = time.perf_counter()
        log = LuotGoiCongCu(
            hoi_thoai_id=conversation.id,
            nguoi_dung_id=user.id,
            mcp_server=policy.server if policy else "(không rõ)",
            ten_cong_cu=call.name[:100],
            tham_so={},
        )

        def finish(result: dict[str, Any] | list[Any], status: str, reason: str | None = None):
            log.ket_qua = result
            log.trang_thai = status
            log.ly_do = reason[:500] if reason else None
            log.thoi_gian_ms = int((time.perf_counter() - started) * 1000)
            db.add(log)
            db.commit()
            return result, status

        try:
            llm_args = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            llm_args = None
        log.tham_so_llm = (
            llm_args if isinstance(llm_args, dict) else {"khong_hop_le": call.arguments}
        )

        if policy is None or not policy.available:
            reason = (
                "Công cụ không tồn tại"
                if policy is None
                else "Công cụ đang tắt hoặc không khả dụng"
            )
            return finish(
                failure("CONG_CU_TAM_DUNG", "Chức năng này hiện đang tạm dừng."),
                "bi_tu_choi",
                reason,
            )
        if not isinstance(llm_args, dict):
            return finish(
                failure(
                    "THAM_SO_KHONG_HOP_LE", "Tham số gọi công cụ không phải JSON object hợp lệ."
                ),
                "loi",
                "LLM sinh tham số không hợp lệ",
            )
        assert policy.spec is not None
        try:
            args = inject_context(policy.spec, llm_args, user)
        except ContextInjectionError as exc:
            return finish(failure("KHONG_DU_QUYEN", str(exc)), "bi_tu_choi", str(exc))
        log.tham_so = args

        if policy.can_xac_nhan:
            # Giai đoạn 6 sẽ thay bằng: tạo hanh_dong_cho_xac_nhan + trạng thái 'cho_xac_nhan'
            return finish(
                failure("CHUA_HO_TRO_XAC_NHAN", NEEDS_CONFIRMATION_LATER),
                "bi_tu_choi",
                "Công cụ cần xác nhận - chưa hỗ trợ ở giai đoạn này",
            )

        try:
            outcome = await self.registry.client.call_tool(policy.server, call.name, args)
        except McpUnavailableError as exc:
            return finish(
                failure(
                    "DICH_VU_KHONG_KHA_DUNG",
                    "Hệ thống liên quan đang tạm gián đoạn, vui lòng thử lại sau.",
                ),
                "loi",
                str(exc),
            )
        except Exception as exc:
            logger.exception("Gọi tool %s lỗi", call.name)
            return finish(failure("LOI_HE_THONG", "Lỗi khi gọi công cụ."), "loi", repr(exc))

        if not outcome.ok:
            return finish(
                failure("LOI_CONG_CU", "Công cụ báo lỗi khi xử lý yêu cầu."), "loi", outcome.error
            )
        data = outcome.data
        if isinstance(data, dict) and data.get("thanh_cong") is False:
            return finish(data, "loi", str(data.get("thong_bao") or data.get("ma_loi")))
        return finish(data, "thanh_cong")
