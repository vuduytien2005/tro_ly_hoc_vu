"""MCP server mất kết nối (Giai đoạn 10): /health báo gián đoạn, system prompt báo chức năng gián
đoạn để trợ lý trả lời thân thiện; server sống lại thì tự đồng bộ lại."""

import time
from collections.abc import Callable
from typing import Any

import anyio
from fastapi.testclient import TestClient

from src.assistant_api.agent.llm import FakeLLM, FakeResponse, llm_key_present
from src.assistant_api.agent.loop import paused_tools, unavailable_tools
from src.assistant_api.agent.registry import ToolPolicy, ToolRegistry
from src.assistant_api.mcp_client.client import McpUnavailableError, ToolSpec
from src.assistant_api.models import NguoiDung
from tests.assistant.conftest import login

SPEC = ToolSpec("tai_chinh", "get_tuition_status", "", {"type": "object", "properties": {}})


def policy(server: str, name: str, bat: bool, spec: ToolSpec | None) -> ToolPolicy:
    return ToolPolicy(server, name, "doc", False, bat, spec)


def test_paused_and_unavailable_are_separate() -> None:
    policies = {
        "register_course": policy("dao_tao", "register_course", False, None),  # admin tắt
        "get_tuition_status": policy("tai_chinh", "get_tuition_status", True, None),  # server chết
        "get_transcript": policy("dao_tao", "get_transcript", True, SPEC),  # bình thường
        "old_tool": policy("dao_tao", "old_tool", True, None),  # server sống, không còn tool này
    }
    status = {"dao_tao": "ok", "tai_chinh": "Không kết nối được MCP server 'tai_chinh'."}
    assert paused_tools(policies) == ["register_course"]
    assert unavailable_tools(policies, status) == ["get_tuition_status"]


class FlakyClient:
    """Client giả: server trong `down` ném McpUnavailableError."""

    def __init__(self) -> None:
        self.servers: dict[str, Any] = {"dao_tao": object(), "tai_chinh": object()}
        self.down: set[str] = set()

    async def list_tools(self, server: str) -> list[ToolSpec]:
        if server in self.down:
            raise McpUnavailableError(f"Không kết nối được MCP server '{server}'.")
        return []


def test_probe_marks_down_then_recovered() -> None:
    client = FlakyClient()
    registry = ToolRegistry(client)  # type: ignore[arg-type]
    registry.server_status = {"dao_tao": "ok", "tai_chinh": "ok"}
    registry._last_sync = time.monotonic()

    client.down.add("tai_chinh")
    status = anyio.run(registry.probe, 0.0)
    assert status["dao_tao"] == "ok" and status["tai_chinh"].startswith("Không kết nối")
    assert registry._last_sync == 0.0  # lần ensure_fresh sau sẽ đồng bộ lại

    client.down.clear()
    registry._last_sync = time.monotonic()
    assert anyio.run(registry.probe, 0.0)["tai_chinh"] == "khoi_phuc"
    assert registry._last_sync == 0.0


def test_probe_is_rate_limited() -> None:
    client = FlakyClient()
    registry = ToolRegistry(client)  # type: ignore[arg-type]
    registry.server_status = {"tai_chinh": "ok"}
    anyio.run(registry.probe, 60.0)
    client.down.add("tai_chinh")
    assert anyio.run(registry.probe, 60.0)["tai_chinh"] == "ok"  # chưa đến lượt dò lại


def test_llm_key_present(monkeypatch: Any) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert llm_key_present("anthropic/claude-opus-5-5") is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_key_present("anthropic/claude-opus-5-5") is True
    assert llm_key_present("ollama/qwen3") is True
    assert llm_key_present("lapla/mo-hinh") is None


def test_health_reports_interrupted_servers(client: TestClient, registry: ToolRegistry) -> None:
    body = client.get("/health").json()
    assert body["gian_doan"] == [] and "llm_co_khoa" in body
    registry.server_status["tai_chinh"] = "Không kết nối được MCP server 'tai_chinh'."
    registry._last_probe = time.monotonic()  # không dò lại trong test (server thật vẫn chạy)
    registry._last_sync = time.monotonic()
    assert client.get("/health").json()["gian_doan"] == ["tai_chinh"]


def test_system_prompt_mentions_interrupted_function(
    client: TestClient,
    registry: ToolRegistry,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
) -> None:
    # Giả lập: lần đồng bộ gần nhất không kết nối được tai_chinh -> tool của nó không còn spec
    registry.server_status["tai_chinh"] = "Không kết nối được MCP server 'tai_chinh'."
    registry._specs.pop("get_tuition_status")
    registry._last_sync = time.monotonic()  # chưa đến lúc đồng bộ lại

    llm = script(FakeResponse(text="Hệ thống học phí đang gián đoạn, em thử lại sau nhé."))
    headers = login(client, student.email)
    conv = client.post("/api/conversations", json={}, headers=headers).json()
    r = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"noi_dung": "Em còn nợ học phí không?"},
        headers=headers,
    )
    assert r.status_code == 200
    first = llm.calls[0]
    assert "get_tuition_status" not in {t["function"]["name"] for t in first["tools"]}
    system = first["messages"][0]["content"]
    assert "GIÁN ĐOẠN" in system and "học phí" in system
    assert "TẠM DỪNG" not in system  # không nhầm với chức năng do quản trị viên tắt
