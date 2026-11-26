"""Cơ chế xác nhận hành động (quy tắc bảo mật 2) — FakeLLM + MCP server thật + qlsv_api mock.

Kịch bản bắt buộc (docs/07, giai đoạn 6): xác nhận -> đăng ký thành công; xác nhận lần 2 -> lỗi;
người khác xác nhận -> 403; hết hạn -> het_han; trùng lịch -> LLM nhận lỗi TRUNG_LICH.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.assistant_api.agent.actions import expire_stale_actions
from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.main import sweep_expired_actions
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
CHECKED = {**REGISTERED, "trang_thai": "hop_le"}
CARD = "Đăng ký lớp IT004.02 – Cơ sở dữ liệu (3 tín chỉ), Thứ 2, tiết 1-3, phòng B2.101"


def start_register(
    client: TestClient,
    headers: dict[str, str],
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
    args: dict[str, Any] | None = None,
) -> tuple[int, list[tuple[str, Any]]]:
    qlsv_mock.get("/internal/course-sections").respond(200, json=[SECTION])
    if "check" not in qlsv_mock.routes:
        qlsv_mock.post("/internal/students/SV22001/registrations/check", name="check").respond(
            200, json=CHECKED
        )
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


def tool_logs(db: Session, cid: int, tool: str, system: bool = False) -> list[LuotGoiCongCu]:
    """Dòng nhật ký của một tool; mặc định chỉ lượt do LLM gọi, system=True: lượt hệ thống tự
    gọi (tra lớp, kiểm tra trước khi tạo thẻ — tham_so_llm rỗng)."""
    db.expire_all()
    origin = (
        LuotGoiCongCu.tham_so_llm.is_(None) if system else LuotGoiCongCu.tham_so_llm.is_not(None)
    )
    return list(
        db.scalars(
            select(LuotGoiCongCu).where(
                LuotGoiCongCu.hoi_thoai_id == cid, LuotGoiCongCu.ten_cong_cu == tool, origin
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
    (lookup,) = tool_logs(db, cid, "search_course_sections", system=True)
    assert lookup.trang_thai == "thanh_cong"  # do hệ thống gọi
    (check,) = tool_logs(db, cid, "register_course", system=True)  # kiểm tra trước, không ghi
    assert check.tham_so["chi_kiem_tra"] is True and check.trang_thai == "thanh_cong"

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
    assert tool_logs(db, cid, "search_course_sections", system=True) == []  # dừng trước tra cứu


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


def test_schedule_conflict_detected_before_card(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    """Demo 4: trùng lịch được báo NGAY (kiểm tra trước, không ghi), không hiện thẻ xác nhận."""
    conflict = {
        "detail": "Lớp SE105.02 trùng lịch với IT004.02 (Thứ 2, tiết 1-3).",
        "code": "TRUNG_LICH",
    }
    qlsv_mock.post("/internal/students/SV22001/registrations/check", name="check").respond(
        409, json=conflict
    )
    post = qlsv_mock.post("/internal/students/SV22001/registrations").respond(201, json=REGISTERED)
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    assert "pending_action" not in dict(events) and not post.called
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "loi" and log.ket_qua["ma_loi"] == "TRUNG_LICH"
    # Chỉ xét hội thoại này: CSDL dev có thể có thẻ thật do người dùng tạo khi chạy web
    assert (
        db.scalars(select(HanhDongChoXacNhan).where(HanhDongChoXacNhan.hoi_thoai_id == cid)).all()
        == []
    )


def test_schedule_conflict_reaches_llm(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    # kiểm tra trước thì hợp lệ, nhưng đến lúc xác nhận đã trùng (vd vừa đăng ký lớp khác)
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


# ----- Mô tả thẻ theo title MCP (server mới) ----------------------------------------------
async def _no_lookup(server: str, tool: str, args: dict[str, Any]) -> Any:
    raise AssertionError("không được tra cứu cho công cụ chung")


def test_describe_uses_title_and_hides_injected() -> None:
    import anyio

    from src.assistant_api.agent.actions import describe

    args = {"muon_id": 1, "ma_sv": "SV22001", "ma_khoa": "K22", "chi_kiem_tra": True}
    mo_ta = anyio.run(describe, "renew_book", args, _no_lookup, "Gia hạn sách")
    assert mo_ta == "Gia hạn sách (muon_id: 1)"


def test_describe_without_title_unchanged() -> None:
    import anyio

    from src.assistant_api.agent.actions import describe

    assert (
        anyio.run(describe, "x_tool", {"a": 1}, _no_lookup) == "Thực hiện thao tác x_tool (a = 1)"
    )


def test_labels_use_title() -> None:
    from src.assistant_api.agent.prompts import paused_label, tool_label

    assert tool_label("renew_book", "Gia hạn sách") == "Đang dùng: Gia hạn sách"
    assert tool_label("renew_book") == "Đang dùng công cụ renew_book"
    assert tool_label("register_course", "Bất kỳ") == "Đang đăng ký học phần"  # nhãn cũ giữ nguyên
    assert "gia hạn sách" in paused_label("renew_book", "Gia hạn sách").lower()


# ----- Thẻ cả gói (register_courses_bundle) -----------------------------------------------
SECTIONS = {
    "IT004.02": {
        "ma_lop": "IT004.02",
        "ten_hp": "Cơ sở dữ liệu",
        "tin_chi": 3,
        "lich": "Thứ 2, tiết 1-3, phòng B2.101",
    },
    "SE201.01": {
        "ma_lop": "SE201.01",
        "ten_hp": "Trí tuệ nhân tạo ứng dụng",
        "tin_chi": 3,
        "lich": "Thứ 3, tiết 7-9, phòng A1.305",
    },
}


def bundle_lookup(check_error: str | None = None) -> Any:
    from src.assistant_api.agent.executor import Outcome

    async def lookup(server: str, tool: str, args: dict[str, Any]) -> Outcome:
        if tool == "register_courses_bundle":
            assert args["chi_kiem_tra"] is True
            if check_error:
                return Outcome(
                    {"thanh_cong": False, "ma_loi": check_error, "thong_bao": "Lớp X: trùng lịch"},
                    "loi",
                )
            return Outcome({"thanh_cong": True, "tong_tin_chi": 6}, "thanh_cong")
        assert tool == "search_course_sections"
        return Outcome({"lop": [SECTIONS[args["tu_khoa"]]]}, "thanh_cong")

    return lookup


def test_describe_bundle_lists_each_class() -> None:
    import anyio

    from src.assistant_api.agent.actions import describe

    args = {"ma_sv": "SV22001", "ma_lop": ["IT004.02", "SE201.01"]}
    lines = anyio.run(describe, "register_courses_bundle", args, bundle_lookup()).splitlines()
    assert lines[0] == "Đăng ký 2 lớp (6 tín chỉ) học kỳ tới:"
    assert lines[1].startswith("• IT004.02 – Cơ sở dữ liệu (3 tín chỉ)")
    assert lines[2].startswith("• SE201.01 – Trí tuệ nhân tạo ứng dụng (3 tín chỉ)")


def test_describe_bundle_precheck_rejects() -> None:
    import anyio

    from src.assistant_api.agent.actions import ActionRejected, describe

    args = {"ma_sv": "SV22001", "ma_lop": ["IT004.02", "SE105.02"]}
    with pytest.raises(ActionRejected) as exc:
        anyio.run(describe, "register_courses_bundle", args, bundle_lookup("TRUNG_LICH"))
    assert exc.value.code == "TRUNG_LICH"


def test_bundle_labels() -> None:
    from src.assistant_api.agent.prompts import tool_label

    assert tool_label("plan_next_semester") == "Đang lập kế hoạch học kỳ tới"
    assert tool_label("register_courses_bundle") == "Đang đăng ký cả gói học phần"


# ----- việc nền dọn thẻ quá hạn -----------------------------------------------


def _set_expiry(db: Session, ma: str, seconds: int, status: str | None = None) -> None:
    values: dict[str, Any] = {"het_han_luc": to_db(wall_clock() + timedelta(seconds=seconds))}
    if status:
        values["trang_thai"] = status
    db.execute(update(HanhDongChoXacNhan).where(HanhDongChoXacNhan.ma == ma).values(**values))
    db.commit()


@pytest.mark.parametrize("status", ["cho", "cho_bo_sung"])
def test_sweeper_expires_stale_cards(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
    status: str,
) -> None:
    """Thẻ không ai bấm: việc nền chuyển het_han, nhật ký da_huy (trước đây kẹt ở 'cho')."""
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    ma = dict(events)["pending_action"]["ma"]
    _set_expiry(db, ma, -1, status)

    assert expire_stale_actions(db) >= 1
    row = action_row(db, ma)
    assert row.trang_thai == "het_han" and row.xu_ly_luc is not None
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "da_huy" and log.ly_do == "Hết hạn xác nhận"
    assert confirm(client, headers, ma).json()["code"] == "HANH_DONG_DA_XU_LY"
    assert expire_stale_actions(db) == 0  # lần quét sau không đụng lại


def test_sweeper_leaves_live_cards(
    client: TestClient,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
    qlsv_mock: respx.MockRouter,
) -> None:
    headers = login(client, student.email)
    cid, events = start_register(client, headers, script, qlsv_mock)
    ma = dict(events)["pending_action"]["ma"]
    expire_stale_actions(db)
    assert action_row(db, ma).trang_thai == "cho"
    (log,) = tool_logs(db, cid, "register_course")
    assert log.trang_thai == "cho_xac_nhan"


def test_sweep_loop_survives_db_errors(caplog: pytest.LogCaptureFixture) -> None:
    calls = 0

    def broken_factory() -> Session:
        nonlocal calls
        calls += 1
        raise RuntimeError("mất kết nối")

    async def run() -> None:
        task = asyncio.create_task(sweep_expired_actions(broken_factory, 0.01))
        # Chờ theo điều kiện, không theo thời gian cố định: máy chậm (in traceback lâu) vẫn đúng
        for _ in range(500):
            if calls >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()

    asyncio.run(run())
    assert calls >= 2  # lỗi không làm dừng việc nền
    assert any(r.getMessage().startswith("Dọn thẻ xác nhận quá hạn") for r in caplog.records)


def test_describe_ask_staff() -> None:
    import anyio

    from src.assistant_api.agent.actions import describe
    from src.assistant_api.agent.prompts import tool_label

    args = {"ma_sv": "SV22001", "cau_hoi": "Học bổng xét theo học kỳ nào?", "phong_ban": "ctsv"}
    mo_ta = anyio.run(describe, "ask_staff", args, _no_lookup)
    assert mo_ta == 'Gửi câu hỏi tới Phòng Công tác sinh viên: "Học bổng xét theo học kỳ nào?"'
    no_dept = anyio.run(
        describe, "ask_staff", {"ma_sv": "x", "cau_hoi": "Câu hỏi khác ạ"}, _no_lookup
    )
    assert no_dept.startswith("Gửi câu hỏi tới cán bộ phụ trách:")
    assert tool_label("ask_staff") == "Đang gửi câu hỏi cho cán bộ"
