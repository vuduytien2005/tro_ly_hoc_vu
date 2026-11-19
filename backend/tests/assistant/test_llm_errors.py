"""Lỗi của nhà cung cấp LLM -> LlmError với thông báo tiếng Việt (không lọt lỗi thô ra sinh viên).

Gặp thật khi chạy Gemini gói miễn phí: 503 "high demand", 404 model ngừng cấp cho người mới.
Các lỗi này kế thừa openai.APIError chứ không phải litellm.APIError.
"""

from typing import Any

import anyio
import litellm
import pytest

from src.assistant_api.agent.llm import LiteLlm, LlmError

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
