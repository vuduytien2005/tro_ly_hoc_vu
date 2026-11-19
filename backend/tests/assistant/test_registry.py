"""ToolRegistry: ẩn ma_sv/ma_khoa khỏi schema, tiêm ngữ cảnh, đồng bộ bảng cong_cu, lọc tool tắt."""

import anyio
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.assistant_api.agent.registry import (
    ContextInjectionError,
    ToolRegistry,
    inject_context,
    strip_injected,
)
from src.assistant_api.mcp_client.client import ToolSpec
from src.assistant_api.models import CongCu, McpServer, NguoiDung

SCHEMA = {
    "type": "object",
    "properties": {
        "ma_sv": {"type": "string", "description": "[INJECTED]"},
        "ma_khoa": {"type": "string"},
        "cau_hoi": {"type": "string"},
    },
    "required": ["ma_sv", "ma_khoa", "cau_hoi"],
}


def test_strip_injected_removes_properties_and_required() -> None:
    clean = strip_injected(SCHEMA)
    assert set(clean["properties"]) == {"cau_hoi"}
    assert clean["required"] == ["cau_hoi"]
    assert "ma_sv" in SCHEMA["properties"]  # không sửa schema gốc


def test_system_params_hidden_and_dropped(student: NguoiDung) -> None:
    schema = {
        "type": "object",
        "properties": {"ma_sv": {}, "ma_lop": {}, "chi_kiem_tra": {"type": "boolean"}},
        "required": ["ma_sv", "ma_lop"],
    }
    assert set(strip_injected(schema)["properties"]) == {"ma_lop"}  # LLM không thấy
    spec = ToolSpec("dao_tao", "register_course", "", schema)
    args = inject_context(spec, {"ma_lop": "IT004.02", "chi_kiem_tra": True}, student)
    assert args == {"ma_lop": "IT004.02", "ma_sv": "SV22001"}  # LLM gửi kèm -> bị bỏ


def test_strip_injected_drops_empty_required() -> None:
    clean = strip_injected({"type": "object", "properties": {"ma_sv": {}}, "required": ["ma_sv"]})
    assert clean["properties"] == {} and "required" not in clean


def test_inject_overrides_llm_values(student: NguoiDung) -> None:
    spec = ToolSpec("quy_che", "search_regulations", "", SCHEMA)
    args = inject_context(spec, {"ma_sv": "SV22002", "ma_khoa": "K99", "cau_hoi": "x"}, student)
    assert args == {"ma_sv": "SV22001", "ma_khoa": "K22", "cau_hoi": "x"}


def test_inject_only_declared_params(student: NguoiDung) -> None:
    spec = ToolSpec("x", "t", "", {"type": "object", "properties": {"q": {}}})
    # LLM bịa ma_sv cho tool không khai báo -> bị bỏ, không được thêm
    assert inject_context(spec, {"q": 1, "ma_sv": "SV22002"}, student) == {"q": 1}


def test_inject_requires_account_values(admin: NguoiDung) -> None:
    spec = ToolSpec("dao_tao", "get_transcript", "", SCHEMA)
    with pytest.raises(ContextInjectionError):
        inject_context(spec, {"cau_hoi": "x"}, admin)


def test_tools_for_llm_never_expose_injected_params(registry: ToolRegistry, db: Session) -> None:
    anyio.run(registry.sync, db)
    tools = registry.tools_for_llm(registry.policies(db))
    names = {t["function"]["name"] for t in tools}
    assert {"search_regulations", "get_transcript", "get_tuition_status"} <= names
    for tool in tools:
        params = tool["function"]["parameters"]
        assert "ma_sv" not in params["properties"] and "ma_khoa" not in params["properties"]
        assert not {"ma_sv", "ma_khoa"} & set(params.get("required", []))


def test_disabled_tool_and_disabled_server_hidden(registry: ToolRegistry, db: Session) -> None:
    anyio.run(registry.sync, db)
    db.scalar(select(CongCu).where(CongCu.ten == "get_transcript")).bat = False
    db.scalar(select(McpServer).where(McpServer.ten == "tai_chinh")).bat = False
    db.commit()
    policies = registry.policies(db)
    names = {t["function"]["name"] for t in registry.tools_for_llm(policies)}
    assert "get_transcript" not in names
    assert "get_tuition_status" not in names  # server tắt -> mọi tool của nó bị ẩn
    assert "get_exam_schedule" in names


def test_sync_adds_unknown_tool_disabled_and_requiring_confirmation(
    registry: ToolRegistry, db: Session
) -> None:
    db.execute(delete(CongCu).where(CongCu.ten == "get_article"))
    db.commit()
    anyio.run(registry.sync, db)
    row = db.scalar(select(CongCu).where(CongCu.ten == "get_article"))
    assert row is not None
    assert (row.bat, row.can_xac_nhan, row.muc_rui_ro) == (False, True, "ghi")
    names = {t["function"]["name"] for t in registry.tools_for_llm(registry.policies(db))}
    assert "get_article" not in names


def test_unreachable_server_reported(registry: ToolRegistry, db: Session) -> None:
    registry.client.set_target("ctsv", "http://127.0.0.1:9/mcp")  # không có server
    anyio.run(registry.sync, db)
    assert registry.server_status["ctsv"] != "ok"
    assert registry.server_status["dao_tao"] == "ok"
    names = {t["function"]["name"] for t in registry.tools_for_llm(registry.policies(db))}
    assert "list_my_requests" not in names and "get_transcript" in names
