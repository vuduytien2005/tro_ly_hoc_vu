"""Xác nhận / hủy hành động chờ xác nhận (quy tắc bảo mật 2).

Kiểm tra quyền + trạng thái + hạn được làm TRƯỚC khi mở luồng SSE, dưới khóa hàng
`WITH (UPDLOCK, ROWLOCK)`; lỗi trả JSON {"detail","code"}:
- 404 KHONG_TIM_THAY_HANH_DONG, 403 KHONG_DU_QUYEN (không phải chủ sở hữu),
- 409 HANH_DONG_DA_XU_LY (đã xác nhận/hủy/hết hạn), 409 HANH_DONG_HET_HAN (vừa quá hạn).
Trạng thái đổi sang 'da_xac_nhan' và COMMIT trước khi thực thi -> bấm hai lần chỉ chạy một lần.
"""

from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.assistant_api.agent.actions import close_action, lock_pending
from src.assistant_api.agent.loop import CANCEL_PREFIX, AgentRunner, save_user_message
from src.assistant_api.deps import DbSession, Now, Student
from src.assistant_api.models import HoiThoai, NguoiDung, TinNhan
from src.assistant_api.routers.conversations import sse
from src.assistant_api.schemas import ActionCancelOut, MessageOut

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
    session_factory: Callable[[], Session] = request.app.state.session_factory

    async def events() -> AsyncIterator[str]:
        with session_factory() as session:
            owner = session.get(NguoiDung, user_id)
            assert owner is not None
            async for event in runner.confirm(session, owner, action_id, now):
                yield sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{ma}/cancel", response_model=ActionCancelOut, summary="Hủy, không thực thi")
def cancel(ma: str, user: Student, db: DbSession) -> ActionCancelOut:
    action = lock_pending(db, user, ma)
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
