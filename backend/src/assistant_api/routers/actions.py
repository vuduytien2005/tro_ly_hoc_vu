"""Xác nhận / hủy hành động chờ xác nhận (quy tắc bảo mật 2).

Kiểm tra quyền + trạng thái + hạn được làm TRƯỚC khi mở luồng SSE, dưới khóa hàng
`WITH (UPDLOCK, ROWLOCK)`; lỗi trả JSON {"detail","code"}:
- 404 KHONG_TIM_THAY_HANH_DONG, 403 KHONG_DU_QUYEN (không phải chủ sở hữu),
- 409 HANH_DONG_DA_XU_LY (đã xác nhận/hủy/hết hạn), 409 HANH_DONG_HET_HAN (vừa quá hạn).
Trạng thái đổi sang 'da_xac_nhan' và COMMIT trước khi thực thi -> bấm hai lần chỉ chạy một lần.

MCP elicitation (23/11/2026): sau Xác nhận, server có thể cần thêm thông tin -> thẻ 'cho_bo_sung'
kèm biểu mẫu. `POST /{ma}/input {du_lieu}` kiểm dữ liệu theo schema của server (422
DU_LIEU_BO_SUNG_KHONG_HOP_LE), rồi cũng khóa + đổi 'da_xac_nhan' + COMMIT trước khi gọi lại công cụ.
Hủy nhận cả thẻ 'cho' và 'cho_bo_sung'.
"""

from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.assistant_api.agent.actions import close_action, lock_pending
from src.assistant_api.agent.elicitation import form_errors
from src.assistant_api.agent.loop import CANCEL_PREFIX, AgentEvent, AgentRunner, save_user_message
from src.assistant_api.deps import DbSession, Now, Student
from src.assistant_api.errors import ApiError
from src.assistant_api.models import HoiThoai, NguoiDung, TinNhan
from src.assistant_api.routers.conversations import sse
from src.assistant_api.schemas import ActionCancelOut, ActionInputIn, MessageOut

router = APIRouter(prefix="/api/actions", tags=["Hành động chờ xác nhận"])

CANCELLED_REPLY = "Đã hủy, mình chưa thực hiện thao tác: {mo_ta}. Em cần gì thêm cứ nhắn mình nhé."


@router.post(
    "/{ma}/confirm",
    summary="Xác nhận -> thực thi công cụ -> SSE câu trả lời tiếp theo",
    response_class=StreamingResponse,
)
def confirm(ma: str, request: Request, user: Student, db: DbSession, now: Now) -> StreamingResponse:
    action = lock_pending(db, user, ma)
    close_action(db, action, "da_xac_nhan")
    db.commit()  # nhả khóa; từ đây mọi lần bấm sau đều nhận 409
    action_id, user_id = action.id, user.id
    db.close()
    runner: AgentRunner = request.app.state.runner
    return _stream(
        request, user_id, lambda session, owner: runner.confirm(session, owner, action_id, now)
    )


@router.post(
    "/{ma}/input",
    summary="Gửi biểu mẫu bổ sung (MCP elicitation) -> gọi lại công cụ -> SSE",
    response_class=StreamingResponse,
)
def submit_input(
    ma: str, body: ActionInputIn, request: Request, user: Student, db: DbSession, now: Now
) -> StreamingResponse:
    action = lock_pending(db, user, ma, allowed=("cho_bo_sung",))
    stored = action.yeu_cau_bo_sung or {}
    # Bỏ trường để trống (không bắt buộc) trước khi kiểm: biểu mẫu web gửi "" cho ô bỏ trống
    answers = {k: v for k, v in body.du_lieu.items() if v not in (None, "")}
    errors = form_errors(stored.get("schema") or {}, answers)
    if errors:
        db.rollback()  # nhả khóa, thẻ vẫn chờ bổ sung
        raise ApiError(
            "DU_LIEU_BO_SUNG_KHONG_HOP_LE",
            "Thông tin chưa hợp lệ: " + "; ".join(errors) + ".",
            422,
        )
    close_action(db, action, "da_xac_nhan")
    db.commit()  # gửi hai lần cùng lúc -> lần sau nhận 409
    action_id, user_id = action.id, user.id
    db.close()
    runner: AgentRunner = request.app.state.runner
    return _stream(
        request,
        user_id,
        lambda session, owner: runner.resume(session, owner, action_id, now, answers),
    )


def _stream(
    request: Request,
    user_id: int,
    run: Callable[[Session, NguoiDung], AsyncIterator[AgentEvent]],
) -> StreamingResponse:
    session_factory: Callable[[], Session] = request.app.state.session_factory

    async def events() -> AsyncIterator[str]:
        with session_factory() as session:
            owner = session.get(NguoiDung, user_id)
            assert owner is not None
            async for event in run(session, owner):
                yield sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{ma}/cancel", response_model=ActionCancelOut, summary="Hủy, không thực thi")
def cancel(ma: str, user: Student, db: DbSession) -> ActionCancelOut:
    action = lock_pending(db, user, ma, allowed=("cho", "cho_bo_sung"))
    close_action(db, action, "da_huy")
    log = action.luot_goi
    log.trang_thai = "da_huy"
    log.ly_do = "Sinh viên bấm Hủy"
    conversation = db.get(HoiThoai, action.hoi_thoai_id)
    assert conversation is not None
    save_user_message(db, conversation, CANCEL_PREFIX + action.mo_ta)  # commit cả các thay đổi trên
    reply = TinNhan(
        hoi_thoai_id=conversation.id,
        vai_tro="assistant",
        noi_dung=CANCELLED_REPLY.format(mo_ta=action.mo_ta),
    )
    db.add(reply)
    db.commit()
    return ActionCancelOut(
        ma=action.ma,
        trang_thai=action.trang_thai,
        tin_nhan=MessageOut(
            id=reply.id,
            vai_tro="assistant",
            noi_dung=reply.noi_dung,
            created_at=reply.created_at,
        ),
    )
