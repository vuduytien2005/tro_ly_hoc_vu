"""Đo thời gian đến phản hồi đầu tiên / chữ đầu tiên (NF-01) trong MeteredLLM, bằng đồng hồ giả."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.harness import MeteredLLM  # noqa: E402

from src.assistant_api.agent.llm import LlmTurn, ToolCall  # noqa: E402

TOOL = [ToolCall(id="1", name="get_transcript", arguments="{}")]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Pacer:
    """Pacer giả: chờ `waits[i]` giây ở lần gọi thứ i (tăng đồng hồ đúng chừng ấy)."""

    def __init__(self, clock: Clock, waits: list[float] | None = None) -> None:
        self.clock, self.waits, self.calls = clock, waits or [], 0

    async def await_turn(self) -> float:
        wait = self.waits[self.calls] if self.calls < len(self.waits) else 0.0
        self.calls += 1
        self.clock.now += wait
        return wait


class ScriptLLM:
    """Mỗi lần stream chạy một kịch bản: list (thời điểm tăng thêm, mục yield)."""

    def __init__(self, clock: Clock, turns: list[list[tuple[float, Any]]]) -> None:
        self.clock, self.turns = clock, list(turns)

    async def stream(self, messages: Any, tools: Any) -> AsyncIterator[Any]:
        for dt, item in self.turns.pop(0):
            self.clock.now += dt
            yield item


def make(turns: list[list[tuple[float, Any]]], waits: list[float] | None = None) -> MeteredLLM:
    clock = Clock()
    return MeteredLLM(ScriptLLM(clock, turns), clock=clock, pacer=Pacer(clock, waits))


def drain(llm: MeteredLLM, times: int = 1) -> None:
    async def run() -> None:
        for _ in range(times):
            async for _item in llm.stream([], []):
                pass

    anyio.run(run)


def test_text_only() -> None:
    llm = make([[(2.0, "Xin"), (0.5, LlmTurn(text="Xin chào"))]])
    llm.start_timer()
    drain(llm)
    assert (llm.ttft_s, llm.first_feedback_s) == (2.0, 2.0)


def test_tool_call_then_text() -> None:
    llm = make([[(1.5, LlmTurn(tool_calls=TOOL))], [(2.5, "Kết"), (0.1, LlmTurn(text="Kết quả"))]])
    llm.start_timer()
    drain(llm, 2)
    assert (llm.first_feedback_s, llm.ttft_s) == (1.5, 4.0)


def test_text_before_tool_call_counts() -> None:
    llm = make([[(1.0, "Để mình tra"), (0.2, LlmTurn(text="Để mình tra", tool_calls=TOOL))]])
    llm.start_timer()
    drain(llm)
    assert (llm.ttft_s, llm.first_feedback_s) == (1.0, 1.0)


def test_paced_wait_subtracted() -> None:
    llm = make(
        [[(1.0, LlmTurn(tool_calls=TOOL))], [(0.5, "Kết"), (0.1, LlmTurn(text="Kết"))]],
        waits=[0.0, 3.0],
    )
    llm.start_timer()
    drain(llm, 2)
    assert llm.first_feedback_s == 1.0
    assert llm.ttft_s == 1.5


def test_stop_timer_ignores_later_text() -> None:
    llm = make([[(1.0, LlmTurn(tool_calls=TOOL))], [(1.0, "Xong"), (0.1, LlmTurn(text="Xong"))]])
    llm.start_timer()
    drain(llm)
    llm.stop_timer()
    drain(llm)
    assert llm.ttft_s is None
    assert llm.first_feedback_s == 1.0


def test_no_text_is_none() -> None:
    llm = make([[(1.0, LlmTurn(text=""))]])
    llm.start_timer()
    drain(llm)
    assert llm.ttft_s is None and llm.first_feedback_s is None


def test_start_timer_resets() -> None:
    llm = make([[(1.0, "A"), (0.1, LlmTurn(text="A"))], [(2.0, LlmTurn(tool_calls=TOOL))]])
    llm.start_timer()
    drain(llm)
    llm.start_timer()
    assert llm.ttft_s is None and llm.first_feedback_s is None
    drain(llm)
    assert llm.first_feedback_s == 2.0 and llm.ttft_s is None
