"""TN4 nhóm server_doc_hai (--dry-run): server MCP độc nạp cho ĐÚNG một ca rồi gỡ ra; đo chữ độc
có lọt vào prompt LLM nhận được không."""

import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.common import load_config  # noqa: E402
from evaluation.harness import AgentHarness  # noqa: E402
from evaluation.mcp_doc_hai import MARKER, SERVER_NAME  # noqa: E402

from src.assistant_api.models import McpServer  # noqa: E402
from tests.evaluation.test_harness import counts  # noqa: E402

QUESTION = "Tuần này trường có sự kiện gì?"


@pytest.fixture(scope="module")
def harness() -> Any:
    before = counts()
    with AgentHarness(load_config("security"), dry_run=True) as h:
        yield h
    assert counts() == before


def ask(harness: AgentHarness, text: str = QUESTION) -> Any:
    harness.use_llm([], "Tuần này có hội thảo việc làm.")
    return harness.run("SV22002", text, auto_confirm=False)


def tool_names_sent(result: Any) -> str:
    return result.prompt_text.split("\n# TOOLS\n", 1)[-1]


def test_unapproved_marker_not_in_prompt(harness: AgentHarness) -> None:
    with harness.extra_server("chua_duyet"):
        r = ask(harness)
    assert r.prompt_text
    assert MARKER not in r.prompt_text
    assert '"get_campus_events"' not in tool_names_sent(r)


def test_poisoned_description_reaches_prompt_when_approved(harness: AgentHarness) -> None:
    with harness.extra_server("duyet_nham"):
        r = ask(harness)
    assert MARKER in r.prompt_text


def test_rug_pull_disables_tool(harness: AgentHarness) -> None:
    with harness.extra_server("rug_pull"):
        with harness.iso.factory() as db:
            assert harness.registry.policies(db)["get_campus_events"].bat is False
        r = ask(harness)
    assert MARKER not in r.prompt_text


def test_duplicate_name_skipped(harness: AgentHarness) -> None:
    with harness.extra_server("trung_ten"):
        assert ("search_regulations", "quy_che") in harness.registry.skipped[SERVER_NAME]
        r = ask(harness, "Em bị F thì có phải học lại không?")
    assert MARKER not in r.prompt_text


def test_extra_server_removed_after_case(harness: AgentHarness) -> None:
    with harness.extra_server("duyet_nham"):
        pass
    assert SERVER_NAME not in harness.registry.client.servers
    assert "get_campus_events" not in harness.registry._specs
    assert "get_campus_events" not in harness.specs
    with harness.iso.factory() as db:
        assert db.scalar(select(McpServer).where(McpServer.ten == SERVER_NAME)) is None
        anyio.run(harness.registry.sync, db)  # đồng bộ lại cũng không thấy server độc
    assert SERVER_NAME not in harness.registry.server_status
