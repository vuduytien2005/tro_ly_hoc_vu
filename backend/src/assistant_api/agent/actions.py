"""Hành động chờ xác nhận (quy tắc bảo mật 2 trong CLAUDE.md).

- Tool `can_xac_nhan = 1` KHÔNG được thực thi khi LLM yêu cầu: hệ thống tạo `hanh_dong_cho_xac_nhan`
  (hết hạn sau ACTION_EXPIRE_MINUTES phút) và hiển thị thẻ xác nhận.
- `mo_ta` trên thẻ được DỰNG TỪ MẪU theo từng tool bằng dữ liệu thật (vd tra lớp học phần), không
  dùng câu chữ do LLM viết -> sinh viên thấy đúng điều sẽ xảy ra.
- Tham số được kiểm tra theo JSON schema của tool TRƯỚC khi tạo thẻ.
- Xác nhận/hủy: khóa hàng `WITH (UPDLOCK, ROWLOCK)`, kiểm tra chủ sở hữu, trạng thái, hạn; đổi
  trạng thái và COMMIT trước khi thực thi -> bấm 2 lần (kể cả đồng thời) chỉ thực thi 1 lần.
- Hạn tính theo GIỜ THẬT (`wall_clock`), không theo DEMO_NOW.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.agent.executor import Outcome
from src.assistant_api.errors import ApiError, forbidden, not_found
from src.assistant_api.models import HanhDongChoXacNhan, HoiThoai, LuotGoiCongCu, NguoiDung
from src.shared.config import get_settings
from src.shared.locking import lock_for_update
from src.shared.time import to_db, wall_clock

Lookup = Callable[[str, str, dict[str, Any]], Awaitable[Outcome]]
TEXT_LIMIT = 200
STATUS_LABELS = {"da_xac_nhan": "đã xác nhận", "da_huy": "đã hủy", "het_han": "đã hết hạn"}


class ActionRejected(Exception):
    """Không tạo được thẻ xác nhận (tham số sai, lớp không tồn tại...). Trả lỗi cho LLM."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _short(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= TEXT_LIMIT else text[: TEXT_LIMIT - 1] + "…"


# ----- kiểm tra tham số ----------------------------------------------------------
def validate_args(schema: dict[str, Any], args: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(args), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e.path) or 'tham số'}: {e.message}" for e in errors[:5]
        )
        raise ActionRejected("THAM_SO_KHONG_HOP_LE", f"Tham số không hợp lệ ({details}).")


# Lỗi hạ tầng: vẫn hiện thẻ, điều kiện được kiểm tra lại khi thực thi
_INFRA_ERRORS = {"DICH_VU_KHONG_KHA_DUNG", "LOI_HE_THONG"}


async def _precheck_registration(ma_sv: str, ma_lop: str, lookup: Lookup) -> None:
    """Kiểm tra trước (không ghi) các điều kiện đăng ký — trùng lịch, lớp đầy, tiên quyết... —
    để báo lỗi NGAY thay vì hiện thẻ rồi sinh viên bấm Xác nhận mới thất bại."""
    outcome = await lookup(
        "dao_tao", "register_course", {"ma_sv": ma_sv, "ma_lop": ma_lop, "chi_kiem_tra": True}
    )
    result = outcome.result if isinstance(outcome.result, dict) else {}
    code = str(result.get("ma_loi") or "")
    if outcome.status == "loi" and code and code not in _INFRA_ERRORS:
        raise ActionRejected(code, str(result.get("thong_bao") or "Không đăng ký được lớp này."))


# ----- mô tả thẻ xác nhận (template) ---------------------------------------------
async def _section(ma_sv: str, ma_lop: str, lookup: Lookup) -> dict[str, Any] | None:
    """Tra lớp qua search_course_sections. None = không tra được (dịch vụ lỗi)."""
    outcome = await lookup("dao_tao", "search_course_sections", {"ma_sv": ma_sv, "tu_khoa": ma_lop})
    if outcome.status != "thanh_cong" or not isinstance(outcome.result, dict):
        return None
    for section in outcome.result.get("lop") or []:
        if str(section.get("ma_lop", "")).upper() == ma_lop.upper():
            return section
    raise ActionRejected(
        "LOP_KHONG_TON_TAI",
        f"Không tìm thấy lớp {ma_lop} trong các lớp đang mở đăng ký. "
        "Hãy dùng search_course_sections để tìm đúng mã lớp.",
    )


async def describe(
    tool: str, args: dict[str, Any], lookup: Lookup, title: str | None = None
) -> str:
    if tool in ("register_course", "cancel_course_registration"):
        ma_lop = str(args["ma_lop"]).strip()
        verb = "Đăng ký" if tool == "register_course" else "Hủy đăng ký"
        section = await _section(str(args["ma_sv"]), ma_lop, lookup)
        if tool == "register_course":
            await _precheck_registration(str(args["ma_sv"]), ma_lop, lookup)
        if section is None:
            return f"{verb} lớp {ma_lop}"
        return (
            f"{verb} lớp {section['ma_lop']} – {section['ten_hp']} "
            f"({section['tin_chi']} tín chỉ), {section['lich']}"
        )
    if tool == "request_student_certificate":
        return (
            "Tạo yêu cầu cấp giấy xác nhận sinh viên – mục đích: "
            f"{_short(args['muc_dich'])}, {args.get('so_ban', 1)} bản"
        )
    if tool == "submit_deferral_request":
        return (
            f"Nộp đơn bảo lưu kết quả học tập {args.get('so_hoc_ky', 1)} học kỳ, "
            f"từ học kỳ {_short(args['tu_hoc_ky'])} – lý do: {_short(args['ly_do'])}"
        )
    if tool == "submit_regrade_request":
        return (
            f"Nộp đơn phúc khảo điểm thi học phần {_short(args['ma_hp'])} – "
            f"lý do: {_short(args['ly_do'])}"
        )
    # Tool mới do quản trị viên bật: title server khai báo (nếu có) + tham số, trừ tham số
    # do hệ thống điền (ma_sv, ma_khoa, chi_kiem_tra)
    hidden = ("ma_sv", "ma_khoa", "chi_kiem_tra")
    if title:
        shown = ", ".join(f"{k}: {_short(v)}" for k, v in args.items() if k not in hidden)
        return title + (f" ({shown})" if shown else "")
    shown = ", ".join(f"{k} = {_short(v)}" for k, v in args.items() if k not in hidden)
    return f"Thực hiện thao tác {tool}" + (f" ({shown})" if shown else "")


# ----- tạo / khóa / hủy ----------------------------------------------------------
def create_pending(
    db: Session,
    *,
    log: LuotGoiCongCu,
    user: NguoiDung,
    conversation: HoiThoai,
    server: str,
    tool: str,
    args: dict[str, Any],
    mo_ta: str,
) -> HanhDongChoXacNhan:
    expires = wall_clock() + timedelta(minutes=get_settings().action_expire_minutes)
    action = HanhDongChoXacNhan(
        ma=str(uuid.uuid4()),
        hoi_thoai_id=conversation.id,
        nguoi_dung_id=user.id,
        luot_goi_id=log.id,
        mcp_server=server,
        ten_cong_cu=tool,
        tham_so=args,
        mo_ta=mo_ta,
        trang_thai="cho",
        het_han_luc=to_db(expires),
    )
    db.add(action)
    return action


def lock_pending(db: Session, user: NguoiDung, ma: str) -> HanhDongChoXacNhan:
    """Khóa hàng và kiểm tra: tồn tại, đúng chủ, còn 'cho', còn hạn. Lỗi -> ApiError (JSON)."""
    action = db.scalar(
        lock_for_update(
            select(HanhDongChoXacNhan).where(HanhDongChoXacNhan.ma == ma), HanhDongChoXacNhan
        )
    )
    if action is None:
        raise not_found("KHONG_TIM_THAY_HANH_DONG", "Không tìm thấy thao tác cần xác nhận.")
    if action.nguoi_dung_id != user.id:
        raise forbidden("KHONG_DU_QUYEN", "Bạn không có quyền xử lý thao tác này.")
    if action.trang_thai != "cho":
        label = STATUS_LABELS.get(action.trang_thai, action.trang_thai)
        raise ApiError("HANH_DONG_DA_XU_LY", f"Thao tác này {label} trước đó.", 409)
    now = to_db(wall_clock())
    if action.het_han_luc <= now:
        action.trang_thai = "het_han"
        action.xu_ly_luc = now
        log = action.luot_goi
        log.trang_thai = "da_huy"
        log.ly_do = "Hết hạn xác nhận"
        db.commit()
        raise ApiError(
            "HANH_DONG_HET_HAN",
            "Thao tác đã hết hạn xác nhận, em hãy yêu cầu lại trợ lý nhé.",
            409,
        )
    return action


def close_action(db: Session, action: HanhDongChoXacNhan, status: str) -> None:
    """Đổi trạng thái (da_xac_nhan / da_huy); người gọi commit."""
    action.trang_thai = status
    action.xu_ly_luc = to_db(wall_clock())
