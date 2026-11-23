"""Hội thoại, tin nhắn (SSE) và đánh giá câu trả lời — chỉ dành cho sinh viên.

Mọi truy vấn đều lọc theo `nguoi_dung_id` của tài khoản đăng nhập: hội thoại của người khác trả 404
(không phải 403) để không lộ việc id đó có tồn tại.
"""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.agent.loop import DEFAULT_TITLE, AgentEvent, AgentRunner
from src.assistant_api.agent.prompts import tool_label
from src.assistant_api.agent.registry import HIDDEN_PARAMS, ToolRegistry
from src.assistant_api.deps import DbSession, Now, Student
from src.assistant_api.errors import not_found
from src.assistant_api.models import (
    DanhGiaCauTraLoi,
    HanhDongChoXacNhan,
    HoiThoai,
    LuotGoiCongCu,
    NguoiDung,
    TinNhan,
)
from src.assistant_api.schemas import (
    ConversationIn,
    ConversationOut,
    ConversationPatch,
    FeedbackIn,
    FeedbackOut,
    MessageIn,
    MessageOut,
    MessagesOut,
    PendingActionOut,
    TraceOut,
    TraceStepOut,
)
from src.shared.config import get_settings
from src.shared.time import to_db, wall_clock

router = APIRouter(prefix="/api", tags=["Hội thoại"])


def own_conversation(db: Session, user: NguoiDung, conversation_id: int) -> HoiThoai:
    conversation = db.scalar(
        select(HoiThoai).where(HoiThoai.id == conversation_id, HoiThoai.nguoi_dung_id == user.id)
    )
    if conversation is None:
        raise not_found("KHONG_TIM_THAY_HOI_THOAI", "Không tìm thấy cuộc trò chuyện.")
    return conversation


def sse(event: AgentEvent) -> str:
    return (
        f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False, default=str)}\n\n"
    )


@router.get(
    "/conversations", response_model=list[ConversationOut], summary="Danh sách, mới nhất trước"
)
def list_conversations(user: Student, db: DbSession) -> list[HoiThoai]:
    return list(
        db.scalars(
            select(HoiThoai)
            .where(HoiThoai.nguoi_dung_id == user.id)
            .order_by(HoiThoai.updated_at.desc(), HoiThoai.id.desc())
        )
    )


@router.post("/conversations", response_model=ConversationOut, status_code=201, summary="Tạo mới")
def create_conversation(
    user: Student, db: DbSession, body: ConversationIn | None = None
) -> HoiThoai:
    conversation = HoiThoai(
        nguoi_dung_id=user.id, tieu_de=(body.tieu_de if body and body.tieu_de else DEFAULT_TITLE)
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.patch(
    "/conversations/{conversation_id}", response_model=ConversationOut, summary="Đổi tiêu đề"
)
def rename_conversation(
    conversation_id: int, body: ConversationPatch, user: Student, db: DbSession
) -> HoiThoai:
    conversation = own_conversation(db, user, conversation_id)
    conversation.tieu_de = body.tieu_de
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204, summary="Xóa")
def delete_conversation(conversation_id: int, user: Student, db: DbSession) -> Response:
    db.delete(own_conversation(db, user, conversation_id))  # tin nhắn xóa theo ON DELETE CASCADE
    db.commit()
    return Response(status_code=204)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagesOut,
    summary="Tin nhắn user/assistant (ẩn tool), kèm trích dẫn và hành động chờ xác nhận",
)
def list_messages(conversation_id: int, user: Student, db: DbSession) -> MessagesOut:
    conversation = own_conversation(db, user, conversation_id)
    rows = db.scalars(
        select(TinNhan)
        .where(TinNhan.hoi_thoai_id == conversation.id, TinNhan.vai_tro.in_(("user", "assistant")))
        .order_by(TinNhan.id)
    ).all()
    ratings = dict(
        db.execute(
            select(DanhGiaCauTraLoi.tin_nhan_id, DanhGiaCauTraLoi.diem).where(
                DanhGiaCauTraLoi.nguoi_dung_id == user.id,
                DanhGiaCauTraLoi.tin_nhan_id.in_([r.id for r in rows] or [0]),
            )
        ).all()
    )
    pending = db.scalars(
        select(HanhDongChoXacNhan)
        .where(
            HanhDongChoXacNhan.hoi_thoai_id == conversation.id,
            HanhDongChoXacNhan.nguoi_dung_id == user.id,
            HanhDongChoXacNhan.trang_thai == "cho",
            HanhDongChoXacNhan.het_han_luc > to_db(wall_clock()),  # hạn tính theo giờ thật
        )
        .order_by(HanhDongChoXacNhan.id)
    ).all()
    return MessagesOut(
        tin_nhan=[
            MessageOut(
                id=r.id,
                vai_tro=r.vai_tro,  # type: ignore[arg-type]
                noi_dung=r.noi_dung,
                trich_dan=r.trich_dan,
                danh_gia=ratings.get(r.id),
                created_at=r.created_at,
            )
            for r in rows
            if r.noi_dung and r.noi_dung.strip()  # bỏ bước trung gian chỉ có tool_call
        ],
        hanh_dong_cho_xac_nhan=[PendingActionOut.model_validate(p) for p in pending],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Gửi tin nhắn -> SSE (token, tool_start, tool_end, citations, done, error)",
    response_class=StreamingResponse,
)
def send_message(
    conversation_id: int, body: MessageIn, request: Request, user: Student, db: DbSession, now: Now
) -> StreamingResponse:
    own_conversation(db, user, conversation_id)  # kiểm tra quyền TRƯỚC khi mở luồng (lỗi -> JSON)
    runner: AgentRunner = request.app.state.runner
    session_factory: Callable[[], Session] = request.app.state.session_factory
    user_id = user.id
    # Trả kết nối về pool ngay: luồng SSE có thể kéo dài hàng chục giây và dùng phiên riêng
    db.close()

    async def events() -> AsyncIterator[str]:
        # Phiên CSDL riêng, sống cùng luồng SSE (phiên của request đóng khi handler trả về)
        with session_factory() as session:
            owner = session.get(NguoiDung, user_id)
            conversation = session.get(HoiThoai, conversation_id)
            assert owner is not None and conversation is not None
            async for event in runner.run(session, owner, conversation, body.noi_dung, now):
                yield sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackOut,
    summary="Đánh giá câu trả lời (1 hữu ích / -1 chưa đúng); gửi lại thì ghi đè",
)
def feedback(message_id: int, body: FeedbackIn, user: Student, db: DbSession) -> FeedbackOut:
    message = db.scalar(
        select(TinNhan)
        .join(HoiThoai)
        .where(
            TinNhan.id == message_id,
            TinNhan.vai_tro == "assistant",
            HoiThoai.nguoi_dung_id == user.id,
        )
    )
    if message is None:
        raise not_found("KHONG_TIM_THAY_TIN_NHAN", "Không tìm thấy câu trả lời để đánh giá.")
    rating = db.scalar(
        select(DanhGiaCauTraLoi).where(
            DanhGiaCauTraLoi.tin_nhan_id == message.id, DanhGiaCauTraLoi.nguoi_dung_id == user.id
        )
    )
    if rating is None:
        rating = DanhGiaCauTraLoi(tin_nhan_id=message.id, nguoi_dung_id=user.id, diem=body.diem)
        db.add(rating)
    rating.diem = body.diem
    rating.gop_y = body.gop_y or None
    db.commit()
    return FeedbackOut(tin_nhan_id=message.id, diem=rating.diem, gop_y=rating.gop_y)


# ----------------------------------------------------------------------------- chế độ trình bày
def system_filled(tham_so: dict[str, Any], tham_so_llm: dict[str, Any] | None) -> dict[str, Any]:
    """Tham số do HỆ THỐNG đặt: có trong `tham_so` (thực thi) mà LLM không gửi hoặc gửi khác
    (tiêm ngữ cảnh ghi đè). Lượt hệ thống tự gọi (`tham_so_llm` None): chỉ các tham số ẩn."""
    if tham_so_llm is None:
        return {k: v for k, v in tham_so.items() if k in HIDDEN_PARAMS}
    return {k: v for k, v in tham_so.items() if k not in tham_so_llm or tham_so_llm[k] != v}


def step_label(registry: ToolRegistry, name: str) -> str:
    """Nhãn bước: 'Đang đăng ký học phần' -> 'Đăng ký học phần'; title server -> title."""
    label = tool_label(name, registry.title(name))
    label = label.removeprefix("Đang dùng: ").removeprefix("Đang ").rstrip(".… ")
    return label[:1].upper() + label[1:]


@router.get(
    "/conversations/{conversation_id}/trace",
    response_model=TraceOut,
    summary="Chế độ trình bày: các lượt gọi công cụ của hội thoại (đọc từ nhật ký)",
)
def conversation_trace(
    conversation_id: int, request: Request, user: Student, db: DbSession
) -> TraceOut:
    """Chỉ bật khi CHE_DO_TRINH_BAY=true; chỉ chủ hội thoại xem được; không trả kết quả công cụ."""
    if not get_settings().che_do_trinh_bay:
        raise not_found("KHONG_BAT_CHE_DO_TRINH_BAY", "Chế độ trình bày đang tắt.")
    own_conversation(db, user, conversation_id)
    registry: ToolRegistry = request.app.state.registry
    rows = db.scalars(
        select(LuotGoiCongCu)
        .where(LuotGoiCongCu.hoi_thoai_id == conversation_id)
        .order_by(LuotGoiCongCu.id)
    ).all()
    return TraceOut(
        luot_goi=[
            TraceStepOut(
                id=g.id,
                thoi_diem=g.created_at,
                ten_cong_cu=g.ten_cong_cu,
                nhan=step_label(registry, g.ten_cong_cu),
                mcp_server=g.mcp_server,
                tham_so_llm=g.tham_so_llm,
                tham_so_he_thong_dien=system_filled(g.tham_so or {}, g.tham_so_llm),
                trang_thai=g.trang_thai,
                ly_do=g.ly_do,
                thoi_gian_ms=g.thoi_gian_ms,
            )
            for g in rows
        ]
    )
