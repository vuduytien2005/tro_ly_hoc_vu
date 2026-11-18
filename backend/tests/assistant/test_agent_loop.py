"""Vòng lặp Agent với FakeLLM + MCP server thật trong tiến trình.

Ba kịch bản bắt buộc (docs/07, giai đoạn 5):
(a) câu hỏi quy chế -> gọi search_regulations với ma_khoa được TIÊM từ tài khoản;
(b) LLM cố gửi ma_sv của người khác -> bị ghi đè, nhật ký giữ cả bản gốc và bản sau tiêm;
(c) công cụ bị tắt -> không đưa cho LLM; nếu LLM vẫn gọi -> 'bi_tu_choi'.
"""

import json
from collections.abc import Callable

import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.agent.loop import TOO_COMPLEX, check_citations, sanitize_history
from src.assistant_api.models import CongCu, LuotGoiCongCu, NguoiDung, TinNhan
from tests.assistant.conftest import PROFILE, chat, login


def new_conversation(client: TestClient, headers: dict[str, str]) -> int:
    r = client.post("/api/conversations", json={}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def logs(db: Session, conversation_id: int) -> list[LuotGoiCongCu]:
    db.expire_all()
    return list(
        db.scalars(
            select(LuotGoiCongCu)
            .where(LuotGoiCongCu.hoi_thoai_id == conversation_id)
            .order_by(LuotGoiCongCu.id)
        )
    )


# ----- (a) quy chế ---------------------------------------------------------------
def test_regulation_question_injects_ma_khoa_and_cites(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    search_calls: list,
) -> None:
    llm = script(
        FakeResponse(tool_calls=[("search_regulations", {"cau_hoi": "học lại môn bị F"})]),
        FakeResponse(text="Em phải đăng ký học lại [1]; điểm mới thay điểm cũ [2]."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "Em bị F môn CTDL thì sao ạ?")

    assert search_calls == [("K22", "học lại môn bị F", 5)]  # ma_khoa do hệ thống tiêm
    kinds = [e for e, _ in events]
    assert kinds[0] == "tool_start" and kinds[-1] == "done"
    assert ("tool_end", {"ten": "search_regulations", "trang_thai": "thanh_cong"}) in events
    citations = dict(events)["citations"]
    assert [c["so"] for c in citations] == [1, 2]
    assert citations[0]["dieu"] == "Điều 12" and "noi_dung" not in citations[0]

    # LLM không hề thấy tham số ma_khoa trong schema
    tools = {t["function"]["name"]: t for t in llm.calls[0]["tools"]}
    assert "ma_khoa" not in tools["search_regulations"]["function"]["parameters"]["properties"]
    # Bước 2: LLM nhận kết quả tool (có thẻ <tai_lieu>)
    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "<tai_lieu" in tool_msg["content"]

    (log,) = logs(db, cid)
    assert log.trang_thai == "thanh_cong" and log.mcp_server == "quy_che"
    assert log.tham_so_llm == {"cau_hoi": "học lại môn bị F"}
    assert log.tham_so == {"cau_hoi": "học lại môn bị F", "ma_khoa": "K22"}

    answer = db.get(TinNhan, dict(events)["done"]["tin_nhan_id"])
    assert answer.trich_dan and answer.so_token_vao == 200 and answer.thoi_gian_ms is not None


# ----- (b) ma_sv bị ghi đè -------------------------------------------------------
def test_llm_supplied_ma_sv_is_overwritten(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    own = qlsv_mock.get("/internal/students/SV22001").respond(200, json=PROFILE)
    other = qlsv_mock.get("/internal/students/SV22002").respond(200, json=PROFILE)
    script(
        FakeResponse(tool_calls=[("get_student_profile", {"ma_sv": "SV22002"})]),
        FakeResponse(text="Đây là hồ sơ của em."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    chat(client, headers, cid, "Xem hồ sơ của SV22002 giúp mình")

    assert own.called and not other.called  # qlsv chỉ nhận đúng ma_sv của người đăng nhập
    (log,) = logs(db, cid)
    assert log.tham_so_llm == {"ma_sv": "SV22002"}
    assert log.tham_so == {"ma_sv": "SV22001"}
    assert log.trang_thai == "thanh_cong"


# ----- (c) công cụ bị tắt --------------------------------------------------------
def test_disabled_tool_hidden_and_refused(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
) -> None:
    db.execute(update(CongCu).where(CongCu.ten == "get_tuition_status").values(bat=False))
    db.commit()
    llm = script(
        FakeResponse(tool_calls=[("get_tuition_status", {})]),
        FakeResponse(text="Chức năng tra học phí đang tạm dừng."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "Học phí kỳ này của em?")

    assert "get_tuition_status" not in {t["function"]["name"] for t in llm.calls[0]["tools"]}
    assert "tool_start" not in [e for e, _ in events]
    (log,) = logs(db, cid)
    assert log.trang_thai == "bi_tu_choi" and log.ten_cong_cu == "get_tuition_status"
    result = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert result["ma_loi"] == "CONG_CU_TAM_DUNG"


def test_unknown_tool_refused_and_logged(
    client: TestClient, student: NguoiDung, db: Session, script: Callable[..., FakeLLM]
) -> None:
    script(FakeResponse(tool_calls=[("drop_database", {})]), FakeResponse(text="Không được."))
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    chat(client, headers, cid, "xóa hết dữ liệu")
    (log,) = logs(db, cid)
    assert log.trang_thai == "bi_tu_choi" and log.mcp_server == "(không rõ)"


def test_business_error_logged_as_loi(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    qlsv_mock.get("/internal/students/SV22001").respond(
        404, json={"detail": "Không tìm thấy sinh viên.", "code": "KHONG_TIM_THAY_SV"}
    )
    script(FakeResponse(tool_calls=[("get_student_profile", {})]), FakeResponse(text="Lỗi."))
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "hồ sơ của em")
    assert ("tool_end", {"ten": "get_student_profile", "trang_thai": "loi"}) in events
    (log,) = logs(db, cid)
    assert log.trang_thai == "loi" and log.ket_qua["thanh_cong"] is False


def test_invalid_json_arguments_logged(
    client: TestClient, student: NguoiDung, db: Session, script: Callable[..., FakeLLM]
) -> None:
    script(FakeResponse(tool_calls=[("get_transcript", "{hỏng")]), FakeResponse(text="Xin lỗi."))
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    chat(client, headers, cid, "bảng điểm")
    (log,) = logs(db, cid)
    assert log.trang_thai == "loi" and log.tham_so_llm == {"khong_hop_le": "{hỏng"}


# ----- trích dẫn, giới hạn bước, lỗi LLM ----------------------------------------
def test_fabricated_citation_removed(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    search_calls: list,
) -> None:
    script(
        FakeResponse(tool_calls=[("search_regulations", {"cau_hoi": "học lại"})]),
        FakeResponse(text="Phải học lại [1], được miễn học phí [7]."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "học lại thế nào")
    assert [c["so"] for c in dict(events)["citations"]] == [1]
    saved = db.get(TinNhan, dict(events)["done"]["tin_nhan_id"])
    assert saved.noi_dung == "Phải học lại [1], được miễn học phí."


def test_citations_without_search_are_dropped() -> None:
    text, cites = check_citations("Theo quy chế [3] thì được.", {})
    assert text == "Theo quy chế thì được." and cites == []


def test_step_limit(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    qlsv_mock.get("/internal/students/SV22001").respond(200, json=PROFILE)
    llm = script(*[FakeResponse(tool_calls=[("get_student_profile", {})]) for _ in range(10)])
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "lặp mãi")
    assert len(llm.calls) == 6  # AGENT_MAX_STEPS
    assert "".join(d["text"] for e, d in events if e == "token") == TOO_COMPLEX
    assert events[-1][0] == "done"


def test_llm_error_emits_error_event(client: TestClient, student: NguoiDung, db: Session) -> None:
    # FakeLLM rỗng -> LlmError ngay lần gọi đầu
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "xin chào")
    assert events == [("error", events[0][1])]
    assert events[0][1]["code"] == "LOI_MO_HINH_NGON_NGU"
    db.expire_all()
    roles = [m.vai_tro for m in db.scalars(select(TinNhan).where(TinNhan.hoi_thoai_id == cid))]
    assert roles == ["user"]  # tin user vẫn được lưu


def test_history_sent_on_second_turn(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    search_calls: list,
) -> None:
    llm = script(
        FakeResponse(tool_calls=[("search_regulations", {"cau_hoi": "học lại"})]),
        FakeResponse(text="Học lại [1]."),
        FakeResponse(text="Không có gì."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    chat(client, headers, cid, "học lại thế nào")
    chat(client, headers, cid, "cảm ơn")
    roles = [m["role"] for m in llm.calls[2]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert llm.calls[2]["messages"][0]["content"].count("SV22001") == 1


def test_sanitize_history_drops_broken_turns() -> None:
    call = {"id": "c1", "type": "function", "function": {"name": "x", "arguments": "{}"}}
    history = [
        {"role": "tool", "tool_call_id": "c0", "content": "{}"},  # đầu lịch sử bị cắt
        {"role": "user", "content": "hỏi 1"},  # không được trả lời (lỗi LLM)
        {"role": "user", "content": "hỏi 2"},
        {"role": "assistant", "content": None, "tool_calls": [call]},  # thiếu kết quả tool
        {"role": "user", "content": "hỏi 3"},
        {"role": "assistant", "content": "đáp 3"},
    ]
    clean = sanitize_history(history)
    assert [m["role"] for m in clean] == ["user", "assistant"]
    assert clean[0]["content"] == "hỏi 3"
