"""Chế độ trình bày: API trace lượt gọi công cụ của một hội thoại (đọc từ luot_goi_cong_cu)."""

from collections.abc import Callable

import pytest
import respx
from fastapi.testclient import TestClient

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.models import NguoiDung
from src.assistant_api.routers.conversations import system_filled
from src.shared.config import get_settings
from tests.assistant.conftest import login
from tests.assistant.test_actions import REGISTERED, confirm, start_register


@pytest.fixture
def presentation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "che_do_trinh_bay", True)


def trace(client: TestClient, headers: dict[str, str], cid: int) -> list[dict]:
    r = client.get(f"/api/conversations/{cid}/trace", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["luot_goi"]


def llm_steps(steps: list[dict], name: str) -> list[dict]:
    return [s for s in steps if s["ten_cong_cu"] == name and s["tham_so_llm"] is not None]


def test_trace_disabled_404(
    client: TestClient, student: NguoiDung, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "che_do_trinh_bay", False)
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    r = client.get(f"/api/conversations/{cid}/trace", headers=headers)
    assert r.status_code == 404
    assert r.json()["code"] == "KHONG_BAT_CHE_DO_TRINH_BAY"


def test_trace_lists_calls_with_injected_ma_sv(
    presentation: None,
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    headers = login(client, student.email)
    cid, _ = start_register(client, headers, script, qlsv_mock)
    steps = trace(client, headers, cid)
    (step,) = llm_steps(steps, "register_course")
    assert step["tham_so_llm"] == {"ma_lop": "IT004.02"}
    assert step["tham_so_he_thong_dien"] == {"ma_sv": student.ma_sv}
    assert step["trang_thai"] == "cho_xac_nhan"
    assert step["nhan"] and step["mcp_server"] == "dao_tao"
    assert all("ket_qua" not in s for s in steps)
    assert [s["id"] for s in steps] == sorted(s["id"] for s in steps)


def test_trace_shows_override(
    presentation: None,
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    headers = login(client, student.email)
    cid, _ = start_register(
        client, headers, script, qlsv_mock, {"ma_lop": "IT004.02", "ma_sv": "SV99999"}
    )
    (step,) = llm_steps(trace(client, headers, cid), "register_course")
    assert step["tham_so_llm"]["ma_sv"] == "SV99999"
    assert step["tham_so_he_thong_dien"]["ma_sv"] == student.ma_sv


def test_trace_system_call_has_null_llm_args() -> None:
    assert system_filled({"ma_sv": "SV1", "ma_lop": "X", "chi_kiem_tra": True}, None) == {
        "ma_sv": "SV1",
        "chi_kiem_tra": True,
    }
    assert system_filled({"ma_lop": ["A", "B"]}, {"ma_lop": ["A", "B"]}) == {}


def test_trace_after_confirm_updates_status(
    presentation: None,
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    (before,) = llm_steps(trace(client, headers, cid), "register_course")
    script(FakeResponse(text="Xong."))
    assert confirm(client, headers, dict(events)["pending_action"]["ma"]).status_code == 200
    (after,) = llm_steps(trace(client, headers, cid), "register_course")
    assert after["id"] == before["id"]
    assert after["trang_thai"] == "thanh_cong"


def test_trace_other_student_404(
    presentation: None, client: TestClient, student: NguoiDung, other_student: NguoiDung
) -> None:
    owner = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=owner).json()["id"]
    r = client.get(f"/api/conversations/{cid}/trace", headers=login(client, other_student.email))
    assert r.status_code == 404 and r.json()["code"] == "KHONG_TIM_THAY_HOI_THOAI"


def test_health_reports_presentation_flag(presentation: None, client: TestClient) -> None:
    assert client.get("/health").json()["che_do_trinh_bay"] is True
