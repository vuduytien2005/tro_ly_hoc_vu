"""Lỗi của nhà cung cấp LLM -> LlmError với thông báo tiếng Việt (không lọt lỗi thô ra sinh viên).

Gặp thật khi chạy Gemini gói miễn phí: 503 "high demand", 404 model ngừng cấp cho người mới.
Các lỗi này kế thừa openai.APIError chứ không phải litellm.APIError.
"""

from typing import Any

import anyio
import litellm
import pytest

from src.assistant_api.agent.llm import OLLAMA_DEFAULT_NUM_CTX, LiteLlm, LlmError
from src.shared.config import get_settings

ARGS = {"model": "gemini/gemini-x", "llm_provider": "gemini"}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (litellm.ServiceUnavailableError("high demand", **ARGS), "quá tải"),
        (litellm.RateLimitError("quota", **ARGS), "quá tải"),
        (litellm.NotFoundError("no longer available", **ARGS), "LLM_MODEL"),
        (litellm.BadRequestError("bad", **ARGS), "Không gọi được"),
    ],
)
def test_provider_errors_become_friendly(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: str
) -> None:
    async def fail(**_: Any) -> Any:
        raise error

    monkeypatch.setattr(litellm, "acompletion", fail)

    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 0  # không phụ thuộc LLM_RATE_LIMIT_WAIT_SECONDS trong .env của máy

    async def run() -> None:
        async for _ in llm.stream([{"role": "user", "content": "hi"}], []):
            pass

    with pytest.raises(LlmError, match=expected):
        anyio.run(run)


def test_num_retries_is_sent() -> None:
    params = LiteLlm("gemini/gemini-x")._params("gemini/gemini-x", [], [])
    assert params["num_retries"] >= 0


# ----- Chờ rồi gọi lại khi vượt hạn mức (Gemini miễn phí: 5 lượt/phút) ----------------
GEMINI_429 = (
    'litellm.RateLimitError: {"error": {"code": 429, "details": [{"@type": '
    '"type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "31s"}]}}'
)


def test_retry_delay_parsed_from_gemini_error() -> None:
    from src.assistant_api.agent.llm import DEFAULT_RETRY_DELAY, retry_delay_seconds

    assert retry_delay_seconds(Exception(GEMINI_429)) == 32.0
    assert retry_delay_seconds(Exception("Please retry in 12.5s.")) == 13.5
    assert retry_delay_seconds(Exception("quota")) == DEFAULT_RETRY_DELAY


class _Chunk:
    def __init__(self, text: str) -> None:
        delta = type("D", (), {"content": text})()
        self.choices = [type("C", (), {"delta": delta})()]


def _flaky(fail_times: int) -> tuple[Any, list[int]]:
    calls = [0]

    async def acompletion(**_: Any) -> Any:
        calls[0] += 1
        if calls[0] <= fail_times:
            raise litellm.RateLimitError(GEMINI_429, **ARGS)

        async def gen() -> Any:
            yield _Chunk("xin chào")

        return gen()

    return acompletion, calls


def _run_stream(llm: LiteLlm) -> list[Any]:
    async def run() -> list[Any]:
        return [x async for x in llm._stream_once("gemini/gemini-x", [], [])]

    return anyio.run(run)


def test_waits_then_retries_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    acompletion, calls = _flaky(fail_times=1)
    slept: list[float] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    monkeypatch.setattr(litellm, "acompletion", acompletion)
    monkeypatch.setattr("src.assistant_api.agent.llm.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(litellm, "stream_chunk_builder", lambda *a, **k: None)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 90
    with pytest.raises(LlmError, match="không trả về nội dung"):  # stream giả không có kết thúc
        _run_stream(llm)
    assert calls[0] == 2 and slept == [32.0]


def test_no_wait_when_disabled_or_budget_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    acompletion, calls = _flaky(fail_times=5)
    monkeypatch.setattr(litellm, "acompletion", acompletion)

    async def fake_sleep(s: float) -> None:
        pass

    monkeypatch.setattr("src.assistant_api.agent.llm.asyncio.sleep", fake_sleep)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 0
    with pytest.raises(LlmError, match="quá tải"):
        _run_stream(llm)
    assert calls[0] == 1
    llm.rate_limit_wait = 70  # đủ chờ 2 lần 32 giây, lần 3 vượt ngân sách -> báo lỗi
    calls[0] = 0
    with pytest.raises(LlmError, match="quá tải"):
        _run_stream(llm)
    assert calls[0] == 3


def test_daily_quota_has_its_own_message(monkeypatch: pytest.MonkeyPatch) -> None:
    async def daily(**_: Any) -> Any:
        raise litellm.RateLimitError('PerDay quota exceeded "retryDelay": "11836s"', **ARGS)

    monkeypatch.setattr(litellm, "acompletion", daily)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 90
    with pytest.raises(LlmError, match="hạn mức"):
        _run_stream(llm)


# ----- Ollama (mô hình cục bộ, bổ sung 23/11/2026) -------------------------------------------
@pytest.mark.parametrize("model", ["ollama_chat/qwen3:8b", "ollama/llama3.1:8b"])
def test_ollama_gets_wide_context_window(model: str) -> None:
    # Ollama mặc định chỉ 2–4 nghìn token và LẶNG LẼ cắt prompt -> danh sách công cụ bị mất
    params = LiteLlm(model)._params(model, [], [])
    assert params["num_ctx"] == OLLAMA_DEFAULT_NUM_CTX


def test_num_ctx_override_and_cloud_models_untouched() -> None:
    assert (
        LiteLlm("ollama_chat/qwen3:8b", num_ctx=8192)._params("ollama_chat/qwen3:8b", [], [])[
            "num_ctx"
        ]
        == 8192
    )
    assert "num_ctx" not in LiteLlm("gemini/gemini-x")._params("gemini/gemini-x", [], [])


def test_timeout_override() -> None:
    assert LiteLlm("ollama_chat/qwen3:8b", timeout=600)._params("x", [], [])["timeout"] == 600
    assert LiteLlm("gemini/gemini-x", timeout=None).timeout == get_settings().llm_timeout_seconds


# ----- Dự phòng khi hết hạn mức / quá tải (bổ sung 26/11/2026) -------------------------------
def _by_model(fail: dict[str, Exception]) -> tuple[Any, list[str]]:
    """acompletion giả: model trong `fail` -> ném lỗi; model khác -> trả "từ <model>"."""
    seen: list[str] = []

    async def acompletion(**kw: Any) -> Any:
        seen.append(kw["model"])
        if kw["model"] in fail:
            raise fail[kw["model"]]

        async def gen() -> Any:
            yield _Chunk(f"từ {kw['model']}")

        return gen()

    return acompletion, seen


def _texts(llm: LiteLlm) -> list[str]:
    async def run() -> list[str]:
        return [x async for x in llm.stream([], []) if isinstance(x, str)]

    return anyio.run(run)


@pytest.mark.parametrize(
    "error",
    [
        litellm.RateLimitError('PerDay quota "retryDelay": "11836s"', **ARGS),  # hết hạn mức ngày
        litellm.ServiceUnavailableError("high demand", **ARGS),  # quá tải
    ],
)
def test_switches_to_fallback_when_quota_or_overload(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    acompletion, seen = _by_model({"gemini/gemini-x": error})
    monkeypatch.setattr(litellm, "acompletion", acompletion)
    monkeypatch.setattr(litellm, "stream_chunk_builder", lambda *a, **k: None)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 0
    llm.fallback_model = "ollama/qwen2.5:7b"
    with pytest.raises(LlmError, match="không trả về nội dung"):  # stream giả không có kết thúc
        _texts(llm)
    assert seen == ["gemini/gemini-x", "ollama/qwen2.5:7b"]


def test_fallback_is_announced_and_turn_names_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.assistant_api.agent.llm import FallbackNotice, LlmTurn

    acompletion, _ = _by_model({"gemini/gemini-x": litellm.RateLimitError("quota", **ARGS)})
    monkeypatch.setattr(litellm, "acompletion", acompletion)
    final = type("F", (), {})()
    final.choices = [
        type(
            "C",
            (),
            {
                "message": type("M", (), {"content": "ok", "tool_calls": None})(),
                "finish_reason": "stop",
            },
        )()
    ]
    monkeypatch.setattr(litellm, "stream_chunk_builder", lambda *a, **k: final)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 0
    llm.fallback_model = "ollama/qwen2.5:7b"

    async def run() -> list[Any]:
        return [x async for x in llm.stream([], [])]

    items = anyio.run(run)
    # Báo trước (giao diện hiện "đang dùng mô hình dự phòng"), rồi mới tới chữ của dự phòng
    assert items[0] == FallbackNotice("ollama/qwen2.5:7b")
    assert items[1] == "từ ollama/qwen2.5:7b"
    assert isinstance(items[-1], LlmTurn) and items[-1].model == "ollama/qwen2.5:7b"


def test_no_fallback_for_other_errors_or_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    acompletion, seen = _by_model({"gemini/gemini-x": litellm.BadRequestError("bad", **ARGS)})
    monkeypatch.setattr(litellm, "acompletion", acompletion)
    llm = LiteLlm("gemini/gemini-x")
    llm.fallback_model = "ollama/qwen2.5:7b"
    with pytest.raises(LlmError, match="Không gọi được"):
        _texts(llm)  # lỗi cấu hình / yêu cầu sai: dự phòng không giúp được, báo đúng lỗi
    assert seen == ["gemini/gemini-x"]

    acompletion, seen = _by_model({"gemini/gemini-x": litellm.RateLimitError("quota", **ARGS)})
    monkeypatch.setattr(litellm, "acompletion", acompletion)
    llm = LiteLlm("gemini/gemini-x")
    llm.rate_limit_wait = 0
    llm.fallback_model = ""
    with pytest.raises(LlmError, match="quá tải"):
        _texts(llm)
    assert seen == ["gemini/gemini-x"]
