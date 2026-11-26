"""Trang "Thủ tục của em": gọi thẳng tool MCP (không qua LLM).

Vẫn áp dụng đủ quy tắc bảo mật: tool phải đang bật (quy tắc 6), ma_sv lấy từ tài khoản đăng nhập
(quy tắc 1), mỗi lần gọi ghi nhật ký (quy tắc 3, hoi_thoai_id = NULL).
"""

from typing import Any, Literal

from fastapi import APIRouter, Request

from src.assistant_api.agent.executor import Outcome, ToolLog, failure, invoke
from src.assistant_api.agent.registry import (
    ContextInjectionError,
    ToolRegistry,
    inject_context,
)
from src.assistant_api.deps import DbSession, Student
from src.assistant_api.errors import ApiError
from src.assistant_api.models import NguoiDung
from src.assistant_api.reminders import build_reminders
from src.shared.time import now

router = APIRouter(prefix="/api/my", tags=["Thủ tục của em"])

DIRECT_REASON = "Gọi trực tiếp từ trang Thủ tục của em"
NOT_FOUND_CODES = {"DON_KHONG_TON_TAI", "SV_KHONG_TON_TAI"}


async def call_direct(
    request: Request,
    db: DbSession,
    user: NguoiDung,
    tool: str,
    args: dict[str, Any],
    reason: str = DIRECT_REASON,
) -> dict[str, Any]:
    registry: ToolRegistry = request.app.state.registry
    await registry.ensure_fresh(db)
    policy = registry.policies(db).get(tool)
    log = ToolLog(
        db,
        user_id=user.id,
        conversation_id=None,
        server=policy.server if policy else "(không rõ)",
        tool=tool,
        llm_args=None,
    )
    if policy is None or not policy.available or policy.spec is None:
        # Quy tắc 3: lần bị từ chối cũng phải có dòng nhật ký
        message = "Chức năng này hiện đang tạm dừng."
        log.set_args(args)
        log.save(Outcome(failure("CONG_CU_TAM_DUNG", message), "bi_tu_choi", DIRECT_REASON))
        raise ApiError("CHUC_NANG_TAM_DUNG", message, 503)
    try:
        full_args = inject_context(policy.spec, args, user)
    except ContextInjectionError as exc:
        log.set_args(args)
        log.save(Outcome(failure("KHONG_DU_QUYEN", str(exc)), "bi_tu_choi", str(exc)))
        raise ApiError("KHONG_DU_QUYEN", str(exc), 403) from exc
    log.set_args(full_args)
    outcome = await invoke(registry.client, policy.server, tool, full_args)
    outcome.reason = outcome.reason or reason
    log.save(outcome)
    result = outcome.result
    if outcome.status != "thanh_cong" or not isinstance(result, dict):
        data = result if isinstance(result, dict) else {}
        code = str(data.get("ma_loi") or "LOI_CONG_CU")
        message = str(data.get("thong_bao") or "Không lấy được dữ liệu, vui lòng thử lại sau.")
        status = 404 if code in NOT_FOUND_CODES else 502
        if code == "DICH_VU_KHONG_KHA_DUNG":
            status = 503
        raise ApiError(code, message, status)
    return result


@router.get("/requests", summary="Danh sách đơn của em (gọi tool list_my_requests)")
async def list_requests(
    request: Request,
    user: Student,
    db: DbSession,
    trang_thai: Literal["moi_tao", "dang_xu_ly", "da_duyet", "tu_choi", "hoan_tat"] | None = None,
) -> dict[str, Any]:
    args = {"trang_thai": trang_thai} if trang_thai else {}
    return await call_direct(request, db, user, "list_my_requests", args)


@router.get("/requests/{ma_don}", summary="Chi tiết một đơn (gọi tool get_request_status)")
async def get_request(
    request: Request, ma_don: str, user: Student, db: DbSession
) -> dict[str, Any]:
    return await call_direct(request, db, user, "get_request_status", {"ma_don": ma_don})


REMINDER_REASON = "Nhắc việc tự động (trang sinh viên)"
REMINDER_TOOLS = (
    "get_tuition_status",
    "get_exam_schedule",
    "get_borrowed_books",
    "list_my_requests",
)


async def call_read_tools(
    request: Request, db: DbSession, user: NguoiDung, tools: tuple[str, ...], reason: str
) -> tuple[dict[str, dict[str, Any] | None], list[str], list[str]]:
    """Gọi lần lượt các tool đọc (không tham số ngoài ma_sv được tiêm).

    Trả về (kết quả theo tên tool, tool gọi lỗi, tool đang tắt). Tool tắt / lỗi -> None,
    các tool còn lại vẫn có kết quả (trang không hỏng cả vì một nguồn).
    """
    registry: ToolRegistry = request.app.state.registry
    await registry.ensure_fresh(db)
    policies = registry.policies(db)
    results: dict[str, dict[str, Any] | None] = {}
    failed: list[str] = []
    paused: list[str] = []
    for tool in tools:
        policy = policies.get(tool)
        if policy is None or not policy.available or policy.spec is None:
            # Quy tắc 6: tool tắt / server chưa cài -> không gọi (không phải lỗi)
            results[tool] = None
            paused.append(tool)
            continue
        try:
            results[tool] = await call_direct(request, db, user, tool, {}, reason)
        except ApiError:
            results[tool] = None  # lần gọi lỗi đã được ghi nhật ký trong call_direct
            failed.append(tool)
    return results, failed, paused


@router.get(
    "/reminders",
    summary="Nhắc việc: học phí, lịch thi, sách sắp đến hạn, đơn vừa xử lý (gọi các tool đọc)",
)
async def list_reminders(request: Request, user: Student, db: DbSession) -> dict[str, Any]:
    results, failed, _ = await call_read_tools(request, db, user, REMINDER_TOOLS, REMINDER_REASON)
    today = now().date()
    return {
        "ngay": today.isoformat(),
        "nhac_viec": build_reminders(
            results["get_tuition_status"],
            results["get_exam_schedule"],
            results["get_borrowed_books"],
            today,
            results["list_my_requests"],
        ),
        "nguon_loi": failed,
    }


OVERVIEW_REASON = "Tổng quan học tập (trang Học tập của em, gợi ý câu hỏi ở chat)"
# Khóa trong kết quả -> tool đọc tương ứng
OVERVIEW_SECTIONS = {
    "ho_so": "get_student_profile",
    "bang_diem": "get_transcript",
    "tot_nghiep": "get_graduation_progress",
    "thoi_khoa_bieu": "get_current_schedule",
    "lich_thi": "get_exam_schedule",
    "hoc_phi": "get_tuition_status",
}


@router.get(
    "/overview",
    summary="Học tập của em: hồ sơ, bảng điểm, tiến độ tốt nghiệp, TKB, lịch thi, học phí",
)
async def get_overview(request: Request, user: Student, db: DbSession) -> dict[str, Any]:
    results, failed, paused = await call_read_tools(
        request, db, user, tuple(OVERVIEW_SECTIONS.values()), OVERVIEW_REASON
    )
    body: dict[str, Any] = {key: results[tool] for key, tool in OVERVIEW_SECTIONS.items()}
    body["nguon_loi"] = failed
    body["tam_dung"] = paused
    return body
