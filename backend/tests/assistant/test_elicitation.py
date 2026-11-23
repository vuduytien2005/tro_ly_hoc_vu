"""MCP elicitation trong luồng thẻ xác nhận (bổ sung 23/11/2026).

Đơn bảo lưu: sau khi sinh viên bấm Xác nhận, server ctsv hỏi số điện thoại liên hệ qua biểu mẫu
(MCP 2026-07-28, InputRequiredResult). Kiểm:
- LLM không thấy / không điền được trường liên hệ; vòng Agent thường không bị hỏi;
- thẻ chuyển 'cho_bo_sung' kèm biểu mẫu, gửi biểu mẫu -> đơn có liên hệ;
- giá trị điền KHÔNG vào lịch sử hội thoại / nhật ký / kết quả công cụ trả về LLM;
- dữ liệu sai -> 422, thẻ vẫn chờ; hủy được thẻ đang chờ bổ sung.
"""

import json
from collections.abc import Callable
from typing import Any

import anyio
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.agent.elicitation import UnsupportedInputRequest, form_errors, form_request
from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.mcp_client.client import McpClient
from src.assistant_api.models import HanhDongChoXacNhan, LuotGoiCongCu, NguoiDung, TinNhan
from src.mcp_servers import ctsv
from tests.assistant.conftest import chat, login, parse_sse

PHONE = "0912345678"
ARGS = {"ma_sv": "SV22001", "ly_do": "Đi làm để lo học phí", "tu_hoc_ky": "2026-2027-HK2"}
CREATED = {
    "ma_don": "DT-2026-0042",
    "loai_don": "bao_luu",
    "noi_dung": {"ly_do": "Đi làm", "so_hoc_ky": 1, "tu_hoc_ky": "2026-2027-HK2"},
    "trang_thai": "moi_tao",
    "ghi_chu_xu_ly": None,
    "tao_boi": "tro_ly_ai",
    "created_at": "2026-11-23T09:00:00+07:00",
    "updated_at": "2026-11-23T09:00:00+07:00",
}


# ----- Tầng MCP: server ctsv + McpClient -------------------------------------------------------
def test_contact_field_is_not_in_llm_schema() -> None:
    async def schema() -> dict[str, Any]:
        tools = await McpClient({"ctsv": ctsv.mcp}).list_tools("ctsv")
        return next(t for t in tools if t.name == "submit_deferral_request").input_schema

    props = anyio.run(schema)["properties"]
    assert "lien_he" not in props and set(props) >= {"ma_sv", "ly_do", "tu_hoc_ky"}


def test_normal_call_is_never_asked(qlsv_mock: respx.MockRouter) -> None:
    """Vòng Agent thường / thực nghiệm (không khai báo năng lực elicitation) -> không hỏi."""
    post = qlsv_mock.post("/internal/students/SV22001/requests").respond(201, json=CREATED)
    client = McpClient({"ctsv": ctsv.mcp})
    result = anyio.run(client.call_tool, "ctsv", "submit_deferral_request", ARGS)
    assert result.input_required is None and result.data["ma_don"] == "DT-2026-0042"
    assert "lien_he" not in json.loads(post.calls.last.request.content)["noi_dung"]


def test_interactive_call_asks_then_resumes(qlsv_mock: respx.MockRouter) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/requests").respond(201, json=CREATED)
    client = McpClient({"ctsv": ctsv.mcp})

    async def run() -> tuple[Any, Any]:
        first = await client.call_tool("ctsv", "submit_deferral_request", ARGS, interactive=True)
        stored = form_request(first.input_required)
        second = await client.call_tool(
            "ctsv",
            "submit_deferral_request",
            ARGS,
            interactive=True,
            input_responses={
                stored["khoa"]: {"action": "accept", "content": {"so_dien_thoai": PHONE}}
            },
            request_state=stored["request_state"],
        )
        return stored, second

    stored, second = anyio.run(run)
    assert post.call_count == 1  # vòng đầu KHÔNG gọi qlsv_api (thân công cụ chưa chạy)
    assert stored["schema"]["required"] == ["so_dien_thoai"]
    assert "trợ lý AI không đọc được" in stored["thong_diep"]
    assert second.data["ma_don"] == "DT-2026-0042"
    assert PHONE not in json.dumps(second.data)  # kết quả trả về (đi vào prompt) không có SĐT
    sent = json.loads(post.calls.last.request.content)["noi_dung"]
    assert sent["lien_he"] == {"so_dien_thoai": PHONE}


def test_request_status_hides_contact_from_llm(qlsv_mock: respx.MockRouter) -> None:
    detail = {**CREATED, "noi_dung": {**CREATED["noi_dung"], "lien_he": {"so_dien_thoai": PHONE}}}
    qlsv_mock.get("/internal/students/SV22001/requests/DT-2026-0042").respond(200, json=detail)
    client = McpClient({"ctsv": ctsv.mcp})
    out = anyio.run(
        client.call_tool,
        "ctsv",
        "get_request_status",
        {"ma_sv": "SV22001", "ma_don": "DT-2026-0042"},
    )
    assert PHONE not in json.dumps(out.data, ensure_ascii=False)
    assert out.data["noi_dung"]["lien_he"] == ctsv.HIDDEN_CONTACT


# ----- Hàm thuần --------------------------------------------------------------------------------
SCHEMA = {
    "type": "object",
    "properties": {
        "so_dien_thoai": {"type": "string", "title": "Số điện thoại", "pattern": r"^0\d{9}$"},
        "email_ca_nhan": {"type": "string", "title": "Email"},
    },
    "required": ["so_dien_thoai"],
}


def test_form_errors_use_server_labels() -> None:
    assert form_errors(SCHEMA, {"so_dien_thoai": PHONE}) == []
    assert form_errors(SCHEMA, {}) == ["Số điện thoại: bắt buộc"]
    assert form_errors(SCHEMA, {"so_dien_thoai": "123"}) == ["Số điện thoại: không hợp lệ"]
    assert form_errors(SCHEMA, {"so_dien_thoai": PHONE, "la": 1}) == [
        "Có trường không thuộc biểu mẫu"
    ]


@pytest.mark.parametrize(
    "requests",
    [
        {},
        {"a": {"method": "sampling/createMessage", "params": {}}},
        {"a": {"method": "elicitation/create", "params": {"mode": "url", "url": "http://x"}}},
        {
            "a": {"method": "elicitation/create", "params": {"requestedSchema": SCHEMA}},
            "b": {"method": "elicitation/create", "params": {"requestedSchema": SCHEMA}},
        },
    ],
)
def test_unsupported_input_requests(requests: dict[str, Any]) -> None:
    with pytest.raises(UnsupportedInputRequest):
        form_request({"input_requests": requests, "request_state": "s"})


def test_too_many_rounds() -> None:
    ok = {"a": {"method": "elicitation/create", "params": {"requestedSchema": SCHEMA}}}
    assert form_request({"input_requests": ok}, rounds=2)["vong"] == 3
    with pytest.raises(UnsupportedInputRequest):
        form_request({"input_requests": ok}, rounds=3)


# ----- Đầu-cuối qua assistant_api ---------------------------------------------------------------
@pytest.fixture
def deferral_card(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> tuple[dict[str, str], int, dict[str, Any], respx.Route]:
    post = qlsv_mock.post("/internal/students/SV22001/requests").respond(201, json=CREATED)
    llm_args = {k: v for k, v in ARGS.items() if k != "ma_sv"}
    script(
        FakeResponse(tool_calls=[("submit_deferral_request", llm_args)]),
        FakeResponse(text="Em kiểm tra rồi bấm Xác nhận nhé."),
    )
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    card = dict(chat(client, headers, cid, "Em muốn bảo lưu từ HK2"))["pending_action"]
    return headers, cid, card, post


def _row(db: Session, ma: str) -> HanhDongChoXacNhan:
    db.expire_all()
    row = db.scalar(select(HanhDongChoXacNhan).where(HanhDongChoXacNhan.ma == ma))
    assert row is not None
    return row


def test_confirm_then_form_then_done(
    client: TestClient,
    db: Session,
    script: Callable[..., FakeLLM],
    deferral_card: tuple[dict[str, str], int, dict[str, Any], respx.Route],
) -> None:
    headers, cid, card, post = deferral_card
    assert card["bo_sung"] is None

    # 1) Xác nhận -> server cần bổ sung -> thẻ quay lại kèm biểu mẫu, CHƯA gọi qlsv_api
    r = client.post(f"/api/actions/{card['ma']}/confirm", headers=headers)
    events = dict(parse_sse(r.text))
    again = events["pending_action"]
    assert again["ma"] == card["ma"]
    assert again["bo_sung"]["schema"]["required"] == ["so_dien_thoai"]
    assert not post.called
    row = _row(db, card["ma"])
    assert row.trang_thai == "cho_bo_sung" and row.yeu_cau_bo_sung["vong"] == 1
    assert row.luot_goi.trang_thai == "cho_xac_nhan" and "bổ sung" in row.luot_goi.ly_do
    listed = client.get(f"/api/conversations/{cid}/messages", headers=headers).json()
    (pending,) = listed["hanh_dong_cho_xac_nhan"]
    assert pending["bo_sung"]["thong_diep"] and "request_state" not in pending["bo_sung"]

    # 2) Xác nhận lần nữa không được (phải gửi biểu mẫu)
    assert client.post(f"/api/actions/{card['ma']}/confirm", headers=headers).status_code == 409

    # 3) Dữ liệu sai -> 422, thẻ vẫn chờ
    bad = client.post(
        f"/api/actions/{card['ma']}/input",
        json={"du_lieu": {"so_dien_thoai": "abc"}},
        headers=headers,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "DU_LIEU_BO_SUNG_KHONG_HOP_LE"
    assert _row(db, card["ma"]).trang_thai == "cho_bo_sung"

    # 4) Gửi đúng -> đơn được tạo kèm liên hệ, LLM báo kết quả
    script(FakeResponse(text="Đã nộp đơn bảo lưu DT-2026-0042."))
    ok = client.post(
        f"/api/actions/{card['ma']}/input",
        json={"du_lieu": {"so_dien_thoai": PHONE, "email_ca_nhan": ""}},
        headers=headers,
    )
    assert ok.status_code == 200
    assert "DT-2026-0042" in "".join(d["text"] for e, d in parse_sse(ok.text) if e == "token")
    sent = json.loads(post.calls.last.request.content)["noi_dung"]
    assert sent["lien_he"] == {"so_dien_thoai": PHONE}  # ô trống tùy chọn không gửi

    # 5) SĐT không nằm ở lịch sử hội thoại (đi vào prompt LLM) và nhật ký
    db.expire_all()
    history = db.scalars(select(TinNhan).where(TinNhan.hoi_thoai_id == cid)).all()
    assert all(PHONE not in (m.noi_dung or "") for m in history)
    log = db.get(LuotGoiCongCu, _row(db, card["ma"]).luot_goi_id)
    assert log is not None and log.trang_thai == "thanh_cong"
    assert "so_dien_thoai" in (log.ly_do or "")
    assert PHONE not in json.dumps([log.tham_so, log.ket_qua, log.ly_do], ensure_ascii=False)
    assert _row(db, card["ma"]).trang_thai == "da_xac_nhan"


def test_cancel_while_waiting_for_input(
    client: TestClient,
    db: Session,
    deferral_card: tuple[dict[str, str], int, dict[str, Any], respx.Route],
) -> None:
    headers, _cid, card, post = deferral_card
    client.post(f"/api/actions/{card['ma']}/confirm", headers=headers)
    r = client.post(f"/api/actions/{card['ma']}/cancel", headers=headers)
    assert r.status_code == 200 and r.json()["trang_thai"] == "da_huy"
    assert not post.called
    assert (
        client.post(
            f"/api/actions/{card['ma']}/input",
            json={"du_lieu": {"so_dien_thoai": PHONE}},
            headers=headers,
        ).status_code
        == 409
    )


def test_input_on_normal_card_is_rejected(
    client: TestClient,
    deferral_card: tuple[dict[str, str], int, dict[str, Any], respx.Route],
) -> None:
    """Thẻ chưa xác nhận (chưa có biểu mẫu) -> không được gửi biểu mẫu để vượt bước Xác nhận."""
    headers, _cid, card, post = deferral_card
    r = client.post(
        f"/api/actions/{card['ma']}/input",
        json={"du_lieu": {"so_dien_thoai": PHONE}},
        headers=headers,
    )
    assert r.status_code == 409 and not post.called
