"""Cơ chế xác nhận hành động (quy tắc bảo mật 2) — FakeLLM + MCP server thật + qlsv_api mock.

Kịch bản bắt buộc (docs/07, giai đoạn 6): xác nhận -> đăng ký thành công; xác nhận lần 2 -> lỗi;
người khác xác nhận -> 403; hết hạn -> het_han; trùng lịch -> LLM nhận lỗi TRUNG_LICH.
"""

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.models import CongCu, HanhDongChoXacNhan, LuotGoiCongCu, NguoiDung
from src.shared.time import to_db, wall_clock
from tests.assistant.conftest import chat, login, parse_sse

SECTION = {
    "ma_lop": "IT004.02",
    "ma_hp": "IT004",
    "ten_hp": "Cơ sở dữ liệu",
    "tin_chi": 3,
    "hoc_ky": "2026-2027-HK1",
    "giang_vien": "TS. Trần Bình",
    "thu": 2,
    "tiet_bat_dau": 1,
    "tiet_ket_thuc": 3,
    "phong": "B2.101",
    "lich": "Thứ 2, tiết 1-3, phòng B2.101",
    "si_so_toi_da": 60,
    "da_dang_ky": 10,
    "con_trong": 50,
}
REGISTERED = {
    "thanh_cong": True,
    "ma_lop": "IT004.02",
    "ma_hp": "IT004",
    "ten_hp": "Cơ sở dữ liệu",
    "tin_chi": 3,
    "hoc_ky": "2026-2027-HK1",
    "lich": "Thứ 2, tiết 1-3, phòng B2.101",
    "trang_thai": "da_dang_ky",
}
CARD = "Đăng ký lớp IT004.02 – Cơ sở dữ liệu (3 tín chỉ), Thứ 2, tiết 1-3, phòng B2.101"


def start_register(
    client: TestClient,
    headers: dict[str, str],
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
    args: dict[str, Any] | None = None,
) -> tuple[int, list[tuple[str, Any]]]:
    qlsv_mock.get("/internal/course-sections").respond(200, json=[SECTION])
    script(
        FakeResponse(tool_calls=[("register_course", args or {"ma_lop": "IT004.02"})]),
        FakeResponse(text="Em kiểm tra thẻ rồi bấm Xác nhận nhé."),
    )
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    return cid, chat(client, headers, cid, "Đăng ký giúp em lớp IT004.02")


def confirm(client: TestClient, headers: dict[str, str], ma: str):
    return client.post(f"/api/actions/{ma}/confirm", headers=headers)


def action_row(db: Session, ma: str) -> HanhDongChoXacNhan:
    db.expire_all()
    row = db.scalar(select(HanhDongChoXacNhan).where(HanhDongChoXacNhan.ma == ma))
    assert row is not None
    return row


def tool_logs(db: Session, cid: int, tool: str) -> list[LuotGoiCongCu]:
    db.expire_all()
    return list(
        db.scalars(
            select(LuotGoiCongCu).where(
                LuotGoiCongCu.hoi_thoai_id == cid, LuotGoiCongCu.ten_cong_cu == tool
            )
        )
    )


# ----- tạo thẻ ------------------------------------------------------------------
def test_write_tool_creates_card_and_is_not_executed(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)

    assert not post.called  # chưa thực thi
    card = dict(events)["pending_action"]
    assert card["mo_ta"] == CARD  # dựng từ mẫu + dữ liệu lớp thật, không phải lời LLM
    assert card["het_han_luc"].endswith("+07:00")
    assert "tool_start" not in [e for e, _ in events]

    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "cho_xac_nhan"
    assert log.tham_so == {"ma_lop": "IT004.02", "ma_sv": "SV22001"}
    (lookup,) = tool_logs(db, cid, "search_course_sections")
    assert lookup.tham_so_llm is None and lookup.trang_thai == "thanh_cong"  # do hệ thống gọi

    action = action_row(db, card["ma"])
    assert action.trang_thai == "cho" and action.luot_goi_id == log.id
    body = client.get(f"/api/conversations/{cid}/messages", headers=headers).json()
    assert [a["ma"] for a in body["hanh_dong_cho_xac_nhan"]] == [card["ma"]]


def test_unknown_class_creates_no_card(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    llm = script()
    headers = login(client, student.email)
    qlsv_mock.get("/internal/course-sections").respond(200, json=[])
    llm._responses.extend(
        [
            FakeResponse(tool_calls=[("register_course", {"ma_lop": "XX999.01"})]),
            FakeResponse(text="Không có lớp này."),
        ]
    )
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    events = chat(client, headers, cid, "Đăng ký XX999.01")
    assert "pending_action" not in dict(events)
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "loi" and log.ket_qua["ma_loi"] == "LOP_KHONG_TON_TAI"
    assert json.loads(llm.calls[1]["messages"][-1]["content"])["ma_loi"] == "LOP_KHONG_TON_TAI"


def test_invalid_arguments_create_no_card(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock, args={"ma_lop": 5})
    assert "pending_action" not in dict(events)
    (log,) = tool_logs(db, cid, "register_course")
    assert log.ket_qua["ma_loi"] == "THAM_SO_KHONG_HOP_LE"
    assert tool_logs(db, cid, "search_course_sections") == []  # dừng trước khi tra cứu


# ----- xác nhận -----------------------------------------------------------------
def test_confirm_registers_and_llm_reports(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    llm = script(FakeResponse(text="Đã đăng ký xong lớp IT004.02 cho em."))
    ma = dict(events)["pending_action"]["ma"]

    r = confirm(client, headers, ma)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    result = parse_sse(r.text)
    assert ("tool_end", {"ten": "register_course", "trang_thai": "thanh_cong"}) in result
    assert result[-1][0] == "done"

    assert post.call_count == 1
    assert json.loads(post.calls.last.request.content) == {"ma_lop": "IT004.02"}
    (log,) = tool_logs(db, cid, "register_course")  # CÙNG dòng nhật ký, đã cập nhật
    assert log.trang_thai == "thanh_cong" and log.ket_qua["ten_hp"] == "Cơ sở dữ liệu"
    action = action_row(db, ma)
    assert action.trang_thai == "da_xac_nhan" and action.xu_ly_luc is not None

    # LLM thấy: user "Xác nhận: ..." -> tool_call tổng hợp (không lộ ma_sv) -> kết quả thật
    messages = llm.calls[-1]["messages"]
    assert messages[-3] == {"role": "user", "content": "Xác nhận: " + CARD}
    call = messages[-2]["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"ma_lop": "IT004.02"}
    tool_result = json.loads(messages[-1]["content"])
    assert tool_result["thanh_cong"] is True and "ghi_chu_he_thong" in tool_result

    texts = [
        m["noi_dung"]
        for m in client.get(f"/api/conversations/{cid}/messages", headers=headers).json()[
            "tin_nhan"
        ]
    ]
    assert texts[-2:] == ["Xác nhận: " + CARD, "Đã đăng ký xong lớp IT004.02 cho em."]


def test_confirm_twice_is_rejected(
    client: TestClient,
    student: NguoiDung,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    _, events = start_register(client, headers, script, qlsv_mock)
    script(FakeResponse(text="Xong."))
    ma = dict(events)["pending_action"]["ma"]
    assert confirm(client, headers, ma).status_code == 200
    again = confirm(client, headers, ma)
    assert again.status_code == 409 and again.json()["code"] == "HANH_DONG_DA_XU_LY"
    assert post.call_count == 1  # không đăng ký 2 lần


def test_other_student_cannot_confirm(
    client: TestClient,
    student: NguoiDung,
    other_student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    _, events = start_register(client, headers, script, qlsv_mock)
    ma = dict(events)["pending_action"]["ma"]

    intruder = login(client, other_student.email)
    for action in ("confirm", "cancel"):
        r = client.post(f"/api/actions/{ma}/{action}", headers=intruder)
        assert r.status_code == 403 and r.json()["code"] == "KHONG_DU_QUYEN"
    assert not post.called and action_row(db, ma).trang_thai == "cho"  # chủ thẻ vẫn xác nhận được


def test_expired_action(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    ma = dict(events)["pending_action"]["ma"]
    db.execute(
        update(HanhDongChoXacNhan)
        .where(HanhDongChoXacNhan.ma == ma)
        .values(het_han_luc=to_db(wall_clock() - timedelta(seconds=1)))
    )
    db.commit()

    r = confirm(client, headers, ma)
    assert r.status_code == 409 and r.json()["code"] == "HANH_DONG_HET_HAN"
    assert not post.called
    assert action_row(db, ma).trang_thai == "het_han"
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "da_huy" and log.ly_do == "Hết hạn xác nhận"
    body = client.get(f"/api/conversations/{cid}/messages", headers=headers).json()
    assert body["hanh_dong_cho_xac_nhan"] == []
    assert confirm(client, headers, ma).json()["code"] == "HANH_DONG_DA_XU_LY"


def test_schedule_conflict_reaches_llm(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    qlsv_mock.post("/internal/students/SV22001/registrations").respond(
        409,
        json={
            "detail": "Lớp SE105.02 trùng lịch với IT004.02 (Thứ 2, tiết 1-3).",
            "code": "TRUNG_LICH",
        },
    )
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    llm = script(FakeResponse(text="Lớp này trùng lịch với IT004.02 của em."))
    r = confirm(client, headers, dict(events)["pending_action"]["ma"])
    assert ("tool_end", {"ten": "register_course", "trang_thai": "loi"}) in parse_sse(r.text)
    tool_result = json.loads(llm.calls[-1]["messages"][-1]["content"])
    assert tool_result["ma_loi"] == "TRUNG_LICH"
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "loi" and log.ket_qua["ma_loi"] == "TRUNG_LICH"


def test_tool_disabled_after_card_is_refused(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    db.execute(update(CongCu).where(CongCu.ten == "register_course").values(bat=False))
    db.commit()
    script(FakeResponse(text="Chức năng tạm dừng."))
    r = confirm(client, headers, dict(events)["pending_action"]["ma"])
    assert r.status_code == 200 and not post.called
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "bi_tu_choi"


# ----- hủy ----------------------------------------------------------------------
def test_cancel(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    ma = dict(events)["pending_action"]["ma"]

    r = client.post(f"/api/actions/{ma}/cancel", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["trang_thai"] == "da_huy" and body["tin_nhan"]["noi_dung"].startswith("Đã hủy")
    assert not post.called
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "da_huy"
    assert confirm(client, headers, ma).json()["code"] == "HANH_DONG_DA_XU_LY"


def test_unknown_action_404(client: TestClient, student: NguoiDung) -> None:
    r = confirm(client, login(client, student.email), "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["code"] == "KHONG_TIM_THAY_HANH_DONG"


# ----- đơn từ (kịch bản demo 6) --------------------------------------------------
def test_certificate_request_flow(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    post = qlsv_mock.post("/internal/students/SV22001/requests").respond(
        201,
        json={
            "ma_don": "DT-2026-0009",
            "loai_don": "giay_xac_nhan_sv",
            "noi_dung": {"muc_dich": "làm hồ sơ vay vốn", "so_ban": 1},
            "trang_thai": "moi_tao",
            "ghi_chu_xu_ly": None,
            "tao_boi": "tro_ly_ai",
            "created_at": "2026-11-20T09:00:00+07:00",
            "updated_at": "2026-11-20T09:00:00+07:00",
        },
    )
    script(
        FakeResponse(
            tool_calls=[("request_student_certificate", {"muc_dich": "làm hồ sơ vay vốn"})]
        ),
        FakeResponse(text="Em bấm Xác nhận nhé."),
        FakeResponse(text="Đã tạo đơn DT-2026-0009."),
    )
    headers = login(client, student.email)
    cid = client.post("/api/conversations", json={}, headers=headers).json()["id"]
    card = dict(chat(client, headers, cid, "Em xin giấy xác nhận sinh viên để vay vốn"))[
        "pending_action"
    ]
    assert card["mo_ta"] == (
        "Tạo yêu cầu cấp giấy xác nhận sinh viên – mục đích: làm hồ sơ vay vốn, 1 bản"
    )
    assert not post.called
    confirm(client, headers, card["ma"])
    assert json.loads(post.calls.last.request.content)["tao_boi"] == "tro_ly_ai"
    (log,) = tool_logs(db, cid, "request_student_certificate")
    assert log.trang_thai == "thanh_cong" and log.ket_qua["ma_don"] == "DT-2026-0009"
