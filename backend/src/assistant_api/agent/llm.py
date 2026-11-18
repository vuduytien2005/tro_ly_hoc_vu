"""Gọi LLM qua LiteLLM (đổi nhà cung cấp chỉ bằng LLM_MODEL) + FakeLLM cho test.

Giao diện chung: `stream(messages, tools)` là async generator, phát ra các chuỗi `str` (từng đoạn
câu trả lời, để đẩy ra SSE) và cuối cùng đúng một `LlmTurn` (tool_calls, token đã dùng...).

Lưu ý với Claude Opus 5.5 (mặc định của dự án):
- Không gửi temperature/top_p (API trả 400) -> chỉ gửi khi LLM_TEMPERATURE được đặt.
- tool_choice chỉ dùng "auto" (dạng ép gọi tool bị từ chối).
- Mô hình luôn "thinking"; khối thinking phải gửi lại NGUYÊN VẸN khi tiếp tục lượt có tool_call ->
  `LlmTurn.assistant_message` giữ nguyên `thinking_blocks` do LiteLLM ghép từ stream.
- Bộ lọc an toàn có thể từ chối (finish_reason "refusal") -> thử lại với LLM_FALLBACK_MODEL nếu có.
"""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import litellm

from src.shared.config import get_settings

logger = logging.getLogger(__name__)

litellm.drop_params = True  # bỏ tham số mà nhà cung cấp không hỗ trợ thay vì báo lỗi


class LlmError(Exception):
    """Lỗi gọi LLM (chưa cấu hình, sai khóa API, quá hạn mức...)."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON do LLM sinh, có thể hỏng -> loop tự kiểm tra


@dataclass
class LlmTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    # Tin nhắn assistant để nối vào messages ở bước sau (kèm thinking_blocks nếu có)
    assistant_message: dict[str, Any] = field(default_factory=dict)

    @property
    def refused(self) -> bool:
        return self.finish_reason == "refusal"


class LLM(Protocol):
    def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str | LlmTurn]: ...


def build_assistant_message(
    text: str, tool_calls: Sequence[ToolCall], thinking_blocks: list[Any] | None = None
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if tool_calls:
        message["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in tool_calls
        ]
    if thinking_blocks:
        message["thinking_blocks"] = thinking_blocks
    return message


def _uses_sampling_params(model: str) -> bool:
    """Claude thế hệ 5 trở đi từ chối temperature/top_p."""
    name = model.split("/")[-1]
    return not (
        name.startswith("claude-") and any(f"-{v}" in name for v in ("5", "fable", "mythos"))
    )


class LiteLlm:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.fallback_model = settings.llm_fallback_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.timeout = settings.llm_timeout_seconds

    def _params(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "timeout": self.timeout,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        if self.temperature is not None and _uses_sampling_params(model):
            params["temperature"] = self.temperature
        return params

    async def _stream_once(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str | LlmTurn]:
        try:
            response = await litellm.acompletion(**self._params(model, messages, tools))
            chunks: list[Any] = []
            async for chunk in response:
                chunks.append(chunk)
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except litellm.AuthenticationError as exc:
            raise LlmError("Khóa API của mô hình ngôn ngữ không hợp lệ (kiểm tra .env).") from exc
        except litellm.RateLimitError as exc:
            raise LlmError("Mô hình ngôn ngữ đang quá tải, vui lòng thử lại sau ít phút.") from exc
        except litellm.Timeout as exc:
            raise LlmError("Mô hình ngôn ngữ phản hồi quá lâu, vui lòng thử lại.") from exc
        except litellm.APIError as exc:
            logger.exception("LLM lỗi")
            raise LlmError("Không gọi được mô hình ngôn ngữ, vui lòng thử lại sau.") from exc

        final = litellm.stream_chunk_builder(chunks, messages=messages)
        if final is None or not final.choices:
            raise LlmError("Mô hình ngôn ngữ không trả về nội dung.")
        choice = final.choices[0]
        message = choice.message
        calls = [
            ToolCall(c.id, c.function.name or "", c.function.arguments or "{}")
            for c in (message.tool_calls or [])
        ]
        usage = getattr(final, "usage", None)
        text = message.content or ""
        yield LlmTurn(
            text=text,
            tool_calls=calls,
            finish_reason=choice.finish_reason,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            assistant_message=build_assistant_message(
                text, calls, getattr(message, "thinking_blocks", None)
            ),
        )

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str | LlmTurn]:
        if not self.model:
            raise LlmError("Chưa cấu hình mô hình ngôn ngữ (LLM_MODEL trong .env).")
        turn: LlmTurn | None = None
        async for item in self._stream_once(self.model, messages, tools):
            if isinstance(item, LlmTurn):
                turn = item
            else:
                yield item
        assert turn is not None
        if turn.refused and self.fallback_model and not turn.text:
            logger.warning("%s từ chối trả lời, thử lại với %s", self.model, self.fallback_model)
            async for item in self._stream_once(self.fallback_model, messages, tools):
                yield item
            return
        yield turn


# ----- LLM giả lập cho test -----------------------------------------------------
@dataclass
class FakeResponse:
    text: str = ""
    tool_calls: list[tuple[str, dict[str, Any] | str]] = field(default_factory=list)


class FakeLLM:
    """Trả lần lượt các phản hồi định sẵn; ghi lại messages/tools mỗi lần gọi để test kiểm tra."""

    def __init__(self, responses: Sequence[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str | LlmTurn]:
        self.calls.append({"messages": json.loads(json.dumps(messages)), "tools": tools})
        if not self._responses:
            raise LlmError("FakeLLM hết phản hồi định sẵn.")
        response = self._responses.pop(0)
        for i in range(0, len(response.text), 8):
            yield response.text[i : i + 8]
        n = len(self.calls)
        calls = [
            ToolCall(
                f"call_{n}_{i}",
                name,
                args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
            )
            for i, (name, args) in enumerate(response.tool_calls)
        ]
        yield LlmTurn(
            text=response.text,
            tool_calls=calls,
            finish_reason="tool_calls" if calls else "stop",
            input_tokens=100,
            output_tokens=20,
            assistant_message=build_assistant_message(response.text, calls),
        )
