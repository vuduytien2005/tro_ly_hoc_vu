"""Fixture cho test MCP server: mock qlsv_api bằng respx, gọi tool qua giao thức MCP thật
(`mcp.Client(server)` kết nối trong tiến trình, không mở cổng)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer

from src.shared.config import get_settings


@pytest.fixture
def qlsv_mock() -> Iterator[respx.MockRouter]:
    """Chặn mọi request tới qlsv_api; route nào chưa khai báo sẽ làm test lỗi."""
    with respx.mock(base_url=get_settings().qlsv_api_url, assert_all_called=False) as router:
        yield router


async def call_tool(server: MCPServer, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Gọi tool qua MCP client và giải JSON kết quả (tool trả dict -> 1 TextContent JSON)."""
    async with Client(server) as client:
        result = await client.call_tool(name, args)
    assert not result.is_error, result
    return json.loads(result.content[0].text)


async def list_tools(server: MCPServer) -> dict[str, Any]:
    async with Client(server) as client:
        return {t.name: t for t in (await client.list_tools()).tools}
