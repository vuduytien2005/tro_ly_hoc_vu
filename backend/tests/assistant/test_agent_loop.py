"""Vòng lặp Agent với FakeLLM + MCP server thật trong tiến trình.

Ba kịch bản bắt buộc (docs/07, giai đoạn 5):
(a) câu hỏi quy chế -> gọi search_regulations với ma_khoa được TIÊM từ tài khoản;
(b) LLM cố gửi ma_sv của người khác -> bị ghi đè, nhật ký giữ cả bản gốc và bản sau tiêm;
(c) công cụ bị tắt -> không đưa cho LLM; nếu LLM vẫn gọi -> 'bi_tu_choi'.
"""

import json
from collections.abc import Callable

import anyio
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.agent.loop import TOO_COMPLEX, check_citations, sanitize_history
from src.assistant_api.agent.registry import ToolRegistry
from src.assistant_api.models import CongCu, LuotGoiCongCu, McpServer, NguoiDung, TinNhan
from tests.assistant.conftest import PROFILE, THU_VIEN_URL, chat, login


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
    assert citations[0]["trich_doan"] == "Sinh viên bị điểm F phải đăng ký học lại."

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


def test_excerpt_strips_tags_and_truncates() -> None:
    from src.assistant_api.agent.loop import excerpt

    assert excerpt('<tai_lieu so="3">\n  Điều 5.\n Nội   dung\n</tai_lieu>') == "Điều 5. Nội dung"
    long = excerpt("x " * 400)
    assert long is not None and len(long) == 300 and long.endswith("…")
    assert excerpt(None) is None


# ----- (d) server mới (thư viện): thẻ / nhãn lấy từ title MCP, không sửa code trợ lý ----------
def enable_library(db: Session, registry: ToolRegistry) -> None:
    db.add(McpServer(ten="thu_vien", mo_ta="Thư viện", dia_chi=THU_VIEN_URL, bat=True))
    db.commit()
    anyio.run(registry.sync, db)
    db.execute(update(CongCu).where(CongCu.ten == "renew_book").values(bat=True))
    db.execute(
        update(CongCu)
        .where(CongCu.ten == "get_borrowed_books")
        .values(bat=True, muc_rui_ro="doc", can_xac_nhan=False)
    )
    db.commit()


def test_renew_book_creates_card_with_title(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    registry: ToolRegistry,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    enable_library(db, registry)
    qlsv_mock.get("/internal/students/SV22001/borrows").respond(200, json=[])
    script(
        FakeResponse(tool_calls=[("get_borrowed_books", {})]),
        FakeResponse(tool_calls=[("renew_book", {"muon_id": 1, "ma_sv": "SV99999"})]),
        FakeResponse(text="Em bấm Xác nhận để gia hạn nhé."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "Gia hạn giúp em cuốn sách sắp hết hạn")

    starts = [d for e, d in events if e == "tool_start"]
    assert starts[0]["nhan"] == "Đang dùng: Xem sách đang mượn"
    (card,) = [d for e, d in events if e == "pending_action"]
    assert card["mo_ta"] == "Gia hạn sách (muon_id: 1)"
    assert "SV" not in card["mo_ta"]
    renew = [g for g in logs(db, cid) if g.ten_cong_cu == "renew_book"]
    assert renew[0].trang_thai == "cho_xac_nhan"
    assert renew[0].tham_so["ma_sv"] == student.ma_sv


# ----- (e) kế hoạch học kỳ tới -> một thẻ cho cả gói --------------------------------------
def test_plan_then_bundle_one_card(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    from tests.mcp.test_dao_tao import PLAN

    qlsv_mock.get("/internal/students/SV22001/semester-plan").respond(200, json=PLAN)
    base = "/internal/students/SV22001/registrations/bundle"
    qlsv_mock.post(f"{base}/check").respond(
        200, json={"trang_thai": "hop_le", "tong_tin_chi": 6, "lop": []}
    )
    real = qlsv_mock.post(base).respond(201, json={})
    sections = [
        {**s, "ma_hp": s["ma_hp"], "giang_vien": "GV", "con_trong": 10} for s in PLAN["de_xuat"]
    ]
    qlsv_mock.get("/internal/course-sections").respond(200, json=sections)
    script(
        FakeResponse(tool_calls=[("plan_next_semester", {})]),
        FakeResponse(
            tool_calls=[("register_courses_bundle", {"ma_lop": ["IT004.02", "SE201.01"]})]
        ),
        FakeResponse(text="Em bấm Xác nhận trên thẻ để đăng ký cả gói nhé."),
    )
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    events = chat(client, headers, cid, "Lập kế hoạch học kỳ tới rồi đăng ký cả gói giúp em")

    cards = [d for e, d in events if e == "pending_action"]
    assert len(cards) == 1 and cards[0]["ten_cong_cu"] == "register_courses_bundle"
    assert "IT004.02" in cards[0]["mo_ta"] and "SE201.01" in cards[0]["mo_ta"]
    assert cards[0]["mo_ta"].startswith("Đăng ký 2 lớp (6 tín chỉ) học kỳ tới:")
    pending = [g for g in logs(db, cid) if g.ten_cong_cu == "register_courses_bundle"]
    assert pending[-1].trang_thai == "cho_xac_nhan"
    assert pending[-1].tham_so["ma_sv"] == student.ma_sv
    assert real.called is False  # chưa xác nhận -> chưa đăng ký thật


# ----- Kiểm chứng câu trả lời bằng LLM giám khảo (bổ sung 23/11/2026) ---------------------------
VERIFIED_ANSWER = "Em phải đăng ký học lại [1]. Học lại tối đa 2 lần [2]."


def verdict_json() -> str:
    return json.dumps(
        {
            "y": [
                {"cau": "Em phải đăng ký học lại [1].", "ket_luan": "co_can_cu", "doan": [1]},
                {"cau": "Học lại tối đa 2 lần [2].", "ket_luan": "khong_co_can_cu", "doan": [2]},
            ]
        },
        ensure_ascii=False,
    )


def regulation_turn(script: Callable[..., FakeLLM]) -> FakeLLM:
    return script(
        FakeResponse(tool_calls=[("search_regulations", {"cau_hoi": "học lại"})]),
        FakeResponse(text=VERIFIED_ANSWER),
    )


def test_answer_is_verified_and_saved(
    verified_client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    verifier_llm: FakeLLM,
    search_calls: list,
) -> None:
    regulation_turn(script)
    verifier_llm._responses.append(FakeResponse(text=verdict_json()))
    headers = login(verified_client, student.email)
    cid = new_conversation(verified_client, headers)
    events = chat(verified_client, headers, cid, "Em bị F thì sao?")

    kinds = [e for e, _ in events]
    assert kinds[-4:] == ["citations", "verifying", "verification", "done"]
    result = dict(events)["verification"]
    assert (result["tong"], result["co_can_cu"]) == (2, 1)
    # Giám khảo nhận toàn văn đoạn (không phải trích đoạn 300 ký tự), bọc lại trong <tai_lieu>
    system = verifier_llm.calls[0]["messages"][0]["content"]
    assert '<tai_lieu so="1">\nSinh viên bị điểm F phải đăng ký học lại.\n</tai_lieu>' in system

    db.expire_all()
    answer = db.get(TinNhan, dict(events)["done"]["tin_nhan_id"])
    assert answer.kiem_chung is not None and answer.kiem_chung["tong"] == 2
    assert answer.so_token_vao == 200 + 100 and answer.so_token_ra == 40 + 20

    r = verified_client.get(f"/api/conversations/{cid}/messages", headers=headers)
    last = r.json()["tin_nhan"][-1]
    assert last["kiem_chung"]["co_can_cu"] == 1


def test_no_verification_without_search(
    verified_client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    verifier_llm: FakeLLM,
) -> None:
    script(FakeResponse(text="Chào em, mình có thể giúp gì?"))
    headers = login(verified_client, student.email)
    cid = new_conversation(verified_client, headers)
    events = chat(verified_client, headers, cid, "Chào bạn")
    assert "verifying" not in [e for e, _ in events]
    assert verifier_llm.calls == []


def test_verifier_failure_keeps_answer(
    verified_client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    verifier_llm: FakeLLM,
    search_calls: list,
) -> None:
    regulation_turn(script)  # verifier_llm không có phản hồi -> LlmError bên trong giám khảo
    headers = login(verified_client, student.email)
    cid = new_conversation(verified_client, headers)
    events = chat(verified_client, headers, cid, "Em bị F thì sao?")
    kinds = [e for e, _ in events]
    assert "verification" not in kinds and "error" not in kinds and kinds[-1] == "done"
    db.expire_all()
    answer = db.get(TinNhan, dict(events)["done"]["tin_nhan_id"])
    assert answer.noi_dung == VERIFIED_ANSWER and answer.kiem_chung is None


def test_client_without_verifier_is_unchanged(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    search_calls: list,
) -> None:
    regulation_turn(script)
    headers = login(client, student.email)
    cid = new_conversation(client, headers)
    kinds = [e for e, _ in chat(client, headers, cid, "Em bị F thì sao?")]
    assert "verifying" not in kinds and kinds[-1] == "done"


def test_collect_sources_keeps_document_kind() -> None:
    """Trích dẫn từ kho hỏi đáp cán bộ mang loai=hoi_dap -> web hiện nhãn, ẩn nút mở tệp gốc."""
    from src.assistant_api.agent.loop import collect_sources

    result = {
        "doan": [
            {"so": 1, "van_ban": "Hỏi đáp cán bộ", "loai": "hoi_dap", "noi_dung": "23 giờ"},
            {"so": 2, "van_ban": "Quy chế", "noi_dung": "Điều 4"},  # server cũ chưa trả loai
        ]
    }
    sources = collect_sources(result)
    assert sources[1]["loai"] == "hoi_dap" and sources[2]["loai"] == "quy_che"


def test_answer_without_claims_is_saved_as_zero_verification(
    verified_client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    verifier_llm: FakeLLM,
    search_calls: list,
) -> None:
    regulation_turn(script)
    verifier_llm._responses.append(FakeResponse(text='{"y": []}'))
    headers = login(verified_client, student.email)
    cid = new_conversation(verified_client, headers)
    events = chat(verified_client, headers, cid, "KTX đóng cửa mấy giờ?")
    assert dict(events)["verification"]["tong"] == 0
    db.expire_all()
    answer = db.get(TinNhan, dict(events)["done"]["tin_nhan_id"])
    assert answer.kiem_chung is not None and answer.kiem_chung["tong"] == 0
