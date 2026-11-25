"""CRUD hội thoại, danh sách tin nhắn (ẩn tool), quyền sở hữu, đánh giá."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.models import NguoiDung
from tests.assistant.conftest import chat, login


def test_crud_and_auto_title(
    client: TestClient, student: NguoiDung, script: Callable[..., FakeLLM]
) -> None:
    headers = login(client, student.email)
    existing_ids = [c["id"] for c in client.get("/api/conversations", headers=headers).json()]
    created = client.post("/api/conversations", json={}, headers=headers).json()
    assert created["tieu_de"] == "Cuộc trò chuyện mới"
    assert created["created_at"].endswith("+07:00")

    script(FakeResponse(text="Chào em!"))
    chat(client, headers, created["id"], "  Xin chào   trợ lý  ")
    # Tài khoản SV22001 có thể đã có hội thoại thật trên CSDL dev -> chỉ xét các hội thoại mới
    before = set(existing_ids)
    listed = client.get("/api/conversations", headers=headers).json()
    assert [c["id"] for c in listed if c["id"] not in before] == [created["id"]]
    assert listed[0]["id"] == created["id"]  # mới nhất lên đầu
    assert listed[0]["tieu_de"] == "Xin chào trợ lý"  # tiêu đề tự đặt từ câu hỏi đầu

    r = client.patch(
        f"/api/conversations/{created['id']}", json={"tieu_de": "Hỏi thăm"}, headers=headers
    )
    assert r.json()["tieu_de"] == "Hỏi thăm"
    assert client.delete(f"/api/conversations/{created['id']}", headers=headers).status_code == 204
    remaining = client.get("/api/conversations", headers=headers).json()
    assert {c["id"] for c in remaining} == before


def test_messages_hide_tool_steps_and_include_citations(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    search_calls: list,
) -> None:
    script(
        FakeResponse(tool_calls=[("search_regulations", {"cau_hoi": "học lại"})]),
        FakeResponse(text="Học lại [2]."),
    )
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    chat(client, headers, cid, "học lại thế nào")
    body = client.get(f"/api/conversations/{cid}/messages", headers=headers).json()
    assert [(m["vai_tro"], m["noi_dung"]) for m in body["tin_nhan"]] == [
        ("user", "học lại thế nào"),
        ("assistant", "Học lại [2]."),
    ]
    assert body["tin_nhan"][1]["trich_dan"][0]["dieu"] == "Điều 13"
    assert body["hanh_dong_cho_xac_nhan"] == []


def test_other_students_conversation_is_404(
    client: TestClient, student: NguoiDung, other_student: NguoiDung
) -> None:
    owner = login(client, student.email)
    intruder = login(client, other_student.email)
    cid = client.post("/api/conversations", json={}, headers=owner).json()["id"]
    for method, path, body in [
        ("GET", f"/api/conversations/{cid}/messages", None),
        ("POST", f"/api/conversations/{cid}/messages", {"noi_dung": "đọc trộm"}),
        ("PATCH", f"/api/conversations/{cid}", {"tieu_de": "x"}),
        ("DELETE", f"/api/conversations/{cid}", None),
    ]:
        r = client.request(method, path, json=body, headers=intruder)
        assert r.status_code == 404, (method, path)
        assert r.json()["code"] == "KHONG_TIM_THAY_HOI_THOAI"
    assert client.get("/api/conversations", headers=intruder).json() == []


def test_empty_message_rejected(client: TestClient, student: NguoiDung) -> None:
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", json={"noi_dung": "   "}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "DU_LIEU_KHONG_HOP_LE"


def test_feedback_upsert_and_ownership(
    client: TestClient,
    student: NguoiDung,
    other_student: NguoiDung,
    script: Callable[..., FakeLLM],
) -> None:
    script(FakeResponse(text="Trả lời."))
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    events = chat(client, headers, cid, "hỏi")
    mid = dict(events)["done"]["tin_nhan_id"]

    url = f"/api/messages/{mid}/feedback"
    assert client.post(url, json={"diem": 1}, headers=headers).json()["diem"] == 1
    r = client.post(url, json={"diem": -1, "gop_y": "Sai điều khoản"}, headers=headers)
    assert r.json() == {"tin_nhan_id": mid, "diem": -1, "gop_y": "Sai điều khoản"}
    msgs = client.get(f"/api/conversations/{cid}/messages", headers=headers).json()["tin_nhan"]
    assert msgs[1]["danh_gia"] == -1

    assert client.post(url, json={"diem": 5}, headers=headers).status_code == 422
    other = login(client, other_student.email)
    assert client.post(url, json={"diem": 1}, headers=other).status_code == 404
    user_msg_id = msgs[0]["id"]  # không đánh giá tin của chính user
    assert (
        client.post(
            f"/api/messages/{user_msg_id}/feedback", json={"diem": 1}, headers=headers
        ).status_code
        == 404
    )


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["trang_thai"] == "ok"
    assert body["mcp_server"]["quy_che"] == "ok"
