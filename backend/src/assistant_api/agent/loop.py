"""Vòng lặp Agent (docs/02 mục 3): LLM <-> công cụ MCP, phát sự kiện SSE, ghi nhật ký.

Một lượt (một tin nhắn của sinh viên):
1. Lưu tin user; dựng messages = system + lịch sử gần nhất (đã gồm tin user vừa lưu).
2. Lặp tối đa AGENT_MAX_STEPS bước: gọi LLM (stream token ra SSE). Không có tool_call -> lưu câu trả
   lời (đã hậu kiểm trích dẫn), phát `done`. Có tool_call -> với từng lời gọi: kiểm tra chính sách,
   tiêm ngữ cảnh, GHI NHẬT KÝ (mọi trường hợp), rồi:
   - tool thường: gọi MCP, nối kết quả vào messages;
   - tool cần xác nhận: KHÔNG gọi; tạo hanh_dong_cho_xac_nhan, phát `pending_action`, báo LLM
     "đang chờ sinh viên xác nhận".
3. Quá số bước -> trả lời cố định, đề nghị chia nhỏ câu hỏi.

Xác nhận (`confirm`): lưu tin user "Xác nhận: <mô tả>", thực thi tool, cập nhật dòng nhật ký
'cho_xac_nhan', thêm cặp assistant(tool_call tổng hợp) + tool(kết quả thật), rồi chạy tiếp vòng
lặp (bước 2) để LLM báo kết quả cho sinh viên.

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

from src.assistant_api.agent.actions import ActionRejected, create_pending, describe, validate_args
from src.assistant_api.agent.executor import (
    Outcome,
    ToolLog,
    failure,
    invoke,
    parse_arguments,
    update_log,
)
from src.assistant_api.agent.llm import LLM, LlmError, LlmTurn, ToolCall
from src.assistant_api.agent.prompts import system_prompt, tool_label
from src.assistant_api.agent.registry import (
    INJECTED_PARAMS,
    ContextInjectionError,
    ToolPolicy,
    ToolRegistry,
    inject_context,
)
from src.assistant_api.models import HanhDongChoXacNhan, HoiThoai, NguoiDung, TinNhan
from src.shared.config import get_settings
from src.shared.time import from_db

logger = logging.getLogger(__name__)

TOO_COMPLEX = "Yêu cầu quá phức tạp, em thử chia nhỏ câu hỏi nhé."
REFUSED = "Xin lỗi, mình không thể hỗ trợ yêu cầu này."
EMPTY = "Xin lỗi, mình chưa có câu trả lời phù hợp. Em thử hỏi lại theo cách khác nhé."
PENDING_GUIDE = (
    "Thao tác CHƯA được thực hiện. Hệ thống đã hiện thẻ xác nhận cho sinh viên; hãy tóm tắt ngắn "
    'điều sẽ làm và nhờ sinh viên bấm "Xác nhận" trên thẻ (hết hạn sau {minutes} phút). '
    "Không gọi lại công cụ này."
)
CONFIRMED_NOTE = "Sinh viên đã bấm Xác nhận trên thẻ; đây là kết quả thực hiện thật."


def paused_tools(policies: dict[str, ToolPolicy]) -> list[str]:
    """Tool bị quản trị viên tắt (tool hoặc cả server) -> báo LLM là đang tạm dừng."""
    return sorted(n for n, p in policies.items() if not p.bat)


def unavailable_tools(policies: dict[str, ToolPolicy], server_status: dict[str, str]) -> list[str]:
    """Tool đang bật nhưng MCP server của nó không kết nối được (lần đồng bộ gần nhất lỗi)
    -> báo LLM là đang gián đoạn. Tool server đang chạy mà không còn cung cấp thì bỏ qua."""
    return sorted(
        n
        for n, p in policies.items()
        if p.bat and p.spec is None and server_status.get(p.server, "ok") not in ("ok", "tắt")
    )


CONFIRM_PREFIX = "Xác nhận: "
CANCEL_PREFIX = "Hủy: "
SYSTEM_LOOKUP_REASON = "Hệ thống tự tra cứu để dựng thẻ xác nhận"
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


def pending_event(action: HanhDongChoXacNhan) -> AgentEvent:
    expires = from_db(action.het_han_luc)
    return AgentEvent(
        "pending_action",
        {
            "ma": action.ma,
            "ten_cong_cu": action.ten_cong_cu,
            "mo_ta": action.mo_ta,
            "het_han_luc": expires.isoformat() if expires else None,
        },
    )


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


def load_history(db: Session, conversation_id: int, limit: int) -> list[dict[str, Any]]:
    """`limit` tin gần nhất của hội thoại (gồm cả tin vừa lưu của lượt hiện tại), đã làm sạch."""
    rows = db.scalars(
        select(TinNhan)
        .where(TinNhan.hoi_thoai_id == conversation_id)
        .order_by(TinNhan.id.desc())
        .limit(limit)
    ).all()
    return sanitize_history([to_llm_message(r) for r in reversed(rows)])


# ----- trích dẫn -----------------------------------------------------------------
TAG_RE = re.compile(r"</?\s*tai_lieu[^>]*>", re.IGNORECASE)
EXCERPT_MAX = 300


def excerpt(noi_dung: Any) -> str | None:
    """Trích đoạn ngắn cho popover trích dẫn: bỏ thẻ <tai_lieu>, gộp khoảng trắng, cắt 300 ký tự."""
    if not isinstance(noi_dung, str):
        return None
    text = " ".join(TAG_RE.sub(" ", noi_dung).split())
    return text if len(text) <= EXCERPT_MAX else text[: EXCERPT_MAX - 1].rstrip() + "…"


def collect_sources(result: Any) -> dict[int, dict[str, Any]]:
    """Kết quả search_regulations -> {so: thông tin đoạn + trích đoạn ngắn}."""
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
                "trich_doan": excerpt(d.get("noi_dung")),
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
        self.expire_minutes = settings.action_expire_minutes

    # ----- điểm vào --------------------------------------------------------------
    async def run(
        self,
        db: Session,
        user: NguoiDung,
        conversation: HoiThoai,
        content: str,
        now: datetime,
    ) -> AsyncIterator[AgentEvent]:
        """Một tin nhắn mới của sinh viên."""
        save_user_message(db, conversation, content, set_title=True)
        async for event in self._guarded(db, self._loop(db, user, conversation, now)):
            yield event

    async def confirm(
        self, db: Session, user: NguoiDung, action_id: int, now: datetime
    ) -> AsyncIterator[AgentEvent]:
        """Thực thi hành động ĐÃ được khóa + đánh dấu 'da_xac_nhan' (routers/actions.py), rồi
        để LLM báo kết quả."""
        action = db.get(HanhDongChoXacNhan, action_id)
        assert action is not None and action.trang_thai == "da_xac_nhan"
        conversation = db.get(HoiThoai, action.hoi_thoai_id)
        assert conversation is not None
        save_user_message(db, conversation, CONFIRM_PREFIX + action.mo_ta)
        async for event in self._guarded(
            db, self._confirm_steps(db, user, conversation, action, now)
        ):
            yield event

    # ----- nội bộ ----------------------------------------------------------------
    @staticmethod
    async def _guarded(db: Session, events: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        """Lỗi trong lượt -> sự kiện `error` (không làm đứt luồng SSE bằng exception)."""
        try:
            async for event in events:
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

    async def _confirm_steps(
        self,
        db: Session,
        user: NguoiDung,
        conversation: HoiThoai,
        action: HanhDongChoXacNhan,
        now: datetime,
    ) -> AsyncIterator[AgentEvent]:
        policy = self.registry.policies(db).get(action.ten_cong_cu)
        started = time.perf_counter()
        if policy is None or not policy.available:
            # Quản trị viên tắt công cụ trong lúc thẻ đang chờ -> vẫn tôn trọng chính sách
            outcome = Outcome(
                failure("CONG_CU_TAM_DUNG", "Chức năng này hiện đang tạm dừng."),
                "bi_tu_choi",
                "Công cụ bị tắt trước khi sinh viên xác nhận",
            )
        else:
            name = action.ten_cong_cu
            yield AgentEvent("tool_start", {"ten": name, "nhan": tool_label(name)})
            outcome = await invoke(self.registry.client, action.mcp_server, name, action.tham_so)
            yield AgentEvent("tool_end", {"ten": name, "trang_thai": outcome.status})
        update_log(action.luot_goi, outcome, started)

        # Lịch sử: assistant(tool_call tổng hợp, chỉ tham số LLM thấy) + tool(kết quả thật)
        call_id = f"xac_nhan_{action.ma.replace('-', '')[:16]}"
        visible = {k: v for k, v in action.tham_so.items() if k not in INJECTED_PARAMS}
        result = outcome.result
        if isinstance(result, dict):
            result = {**result, "ghi_chu_he_thong": CONFIRMED_NOTE}
        tool_call = {
            "id": call_id,
            "type": "function",
            "function": {
                "name": action.ten_cong_cu,
                "arguments": json.dumps(visible, ensure_ascii=False),
            },
        }
        db.add_all(
            [
                TinNhan(
                    hoi_thoai_id=conversation.id,
                    vai_tro="assistant",
                    noi_dung="",
                    tool_calls=[tool_call],
                ),
                TinNhan(
                    hoi_thoai_id=conversation.id,
                    vai_tro="tool",
                    noi_dung=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call_id,
                ),
            ]
        )
        db.commit()
        async for event in self._loop(db, user, conversation, now):
            yield event

    async def _loop(
        self, db: Session, user: NguoiDung, conversation: HoiThoai, now: datetime
    ) -> AsyncIterator[AgentEvent]:
        started = time.perf_counter()
        await self.registry.ensure_fresh(db)
        policies = self.registry.policies(db)
        tools = self.registry.tools_for_llm(policies)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt(
                    user,
                    now,
                    paused_tools(policies),
                    unavailable_tools(policies, self.registry.server_status),
                ),
            },
            *load_history(db, conversation.id, self.history_limit),
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
                direct = policy is not None and policy.available and not policy.can_xac_nhan
                if direct:
                    yield AgentEvent(
                        "tool_start", {"ten": call.name, "nhan": tool_label(call.name)}
                    )
                outcome = await self._execute(db, user, conversation, call, policy)
                if call.name == "search_regulations" and outcome.status == "thanh_cong":
                    sources = collect_sources(outcome.result)
                if direct:
                    yield AgentEvent("tool_end", {"ten": call.name, "trang_thai": outcome.status})
                if "pending" in outcome.extra:
                    yield pending_event(outcome.extra["pending"])
                result_text = json.dumps(outcome.result, ensure_ascii=False)
                db.add(
                    TinNhan(
                        hoi_thoai_id=conversation.id,
                        vai_tro="tool",
                        noi_dung=result_text,
                        tool_call_id=call.id,
                    )
                )
                db.commit()
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text})

        yield AgentEvent("token", {"text": TOO_COMPLEX})
        async for event in self._finish(
            db, conversation, TOO_COMPLEX, {}, tokens_in, tokens_out, started
        ):
            yield event

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
    ) -> Outcome:
        """Xử lý MỘT lời gọi tool của LLM, LUÔN ghi 1 dòng nhật ký."""
        llm_args = parse_arguments(call.arguments)
        log = ToolLog(
            db,
            user_id=user.id,
            conversation_id=conversation.id,
            server=policy.server if policy else "(không rõ)",
            tool=call.name,
            llm_args=llm_args if llm_args is not None else {"khong_hop_le": call.arguments},
        )

        if policy is None or not policy.available:
            reason = (
                "Công cụ không tồn tại"
                if policy is None
                else "Công cụ đang tắt hoặc không khả dụng"
            )
            outcome = Outcome(
                failure("CONG_CU_TAM_DUNG", "Chức năng này hiện đang tạm dừng."),
                "bi_tu_choi",
                reason,
            )
            log.save(outcome)
            return outcome
        if llm_args is None:
            outcome = Outcome(
                failure(
                    "THAM_SO_KHONG_HOP_LE", "Tham số gọi công cụ không phải JSON object hợp lệ."
                ),
                "loi",
                "LLM sinh tham số không hợp lệ",
            )
            log.save(outcome)
            return outcome
        assert policy.spec is not None
        try:
            args = inject_context(policy.spec, llm_args, user)
        except ContextInjectionError as exc:
            outcome = Outcome(failure("KHONG_DU_QUYEN", str(exc)), "bi_tu_choi", str(exc))
            log.save(outcome)
            return outcome
        log.set_args(args)

        if policy.can_xac_nhan:
            return await self._prepare_confirmation(db, user, conversation, policy, args, log)

        outcome = await invoke(self.registry.client, policy.server, call.name, args)
        log.save(outcome)
        return outcome

    async def _prepare_confirmation(
        self,
        db: Session,
        user: NguoiDung,
        conversation: HoiThoai,
        policy: ToolPolicy,
        args: dict[str, Any],
        log: ToolLog,
    ) -> Outcome:
        """Quy tắc 2: KHÔNG thực thi; kiểm tra tham số, dựng mô tả từ mẫu, tạo thẻ xác nhận."""

        async def lookup(server: str, tool: str, lookup_args: dict[str, Any]) -> Outcome:
            system_log = ToolLog(
                db,
                user_id=user.id,
                conversation_id=conversation.id,
                server=server,
                tool=tool,
                llm_args=None,  # do hệ thống gọi, không phải LLM
            )
            system_log.set_args(lookup_args)
            outcome = await invoke(self.registry.client, server, tool, lookup_args)
            outcome.reason = outcome.reason or SYSTEM_LOOKUP_REASON
            system_log.save(outcome)
            return outcome

        assert policy.spec is not None
        try:
            validate_args(policy.spec.input_schema, args)
            mo_ta = await describe(policy.name, args, lookup)
        except ActionRejected as exc:
            outcome = Outcome(failure(exc.code, exc.message), "loi", exc.message)
            log.save(outcome)
            return outcome

        outcome = Outcome(
            {
                "trang_thai": "cho_xac_nhan",
                "mo_ta": mo_ta,
                "huong_dan": PENDING_GUIDE.format(minutes=self.expire_minutes),
            },
            "cho_xac_nhan",
        )
        row = log.save(outcome, commit=False)  # flush để có id cho khóa ngoại
        action = create_pending(
            db,
            log=row,
            user=user,
            conversation=conversation,
            server=policy.server,
            tool=policy.name,
            args=args,
            mo_ta=mo_ta,
        )
        db.commit()
        outcome.extra["pending"] = action
        return outcome


def save_user_message(
    db: Session, conversation: HoiThoai, content: str, *, set_title: bool = False
) -> TinNhan:
    message = TinNhan(hoi_thoai_id=conversation.id, vai_tro="user", noi_dung=content)
    db.add(message)
    if set_title and conversation.tieu_de in (None, "", DEFAULT_TITLE):
        conversation.tieu_de = make_title(content)
    else:
        # "Chạm" hội thoại để trigger cập nhật updated_at -> danh sách sắp mới nhất trước
        db.execute(
            update(HoiThoai).where(HoiThoai.id == conversation.id).values(tieu_de=HoiThoai.tieu_de)
        )
    db.commit()
    return message
