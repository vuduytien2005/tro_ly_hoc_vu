"""Kho hỏi đáp cán bộ + lỗ hổng tri thức (nâng cấp 10).

Kho trả cho MỌI sinh viên qua RAG -> câu hỏi/trả lời không được chứa thông tin cá nhân. Kiểm tra ở
đây là lớp chặn cuối (giao diện đã cảnh báo trước khi gửi): mã SV, email, số điện thoại.
Thiết kế: docs/superpowers/specs/2026-11-25-kho-hoi-dap-va-lo-hong-tri-thuc-design.md.
"""

import re
from datetime import datetime
from typing import Any

from sqlalchemy import UnicodeText, cast, func, select
from sqlalchemy.orm import Session

from src.assistant_api.models import DanhGiaCauTraLoi, KhoHoiDap, TinNhan
from src.shared.time import from_db, to_db

PERSONAL_PATTERNS = [
    (re.compile(r"\bSV\d{5}\b", re.IGNORECASE), "mã sinh viên"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "địa chỉ email"),
    # 0xxx / +84xxx, 9–11 chữ số, cho phép cách bằng khoảng trắng, dấu chấm, gạch ngang
    (re.compile(r"(?<![\d.,])(?:\+84|0)(?:[\s.-]?\d){8,10}(?![\d])"), "số điện thoại"),
]


def personal_info_problem(text: str) -> str | None:
    """Tên loại thông tin cá nhân đầu tiên tìm thấy (vd "mã sinh viên"), không có -> None."""
    for pattern, label in PERSONAL_PATTERNS:
        if pattern.search(text):
            return label
    return None


# ----- Lỗ hổng tri thức -------------------------------------------------------------
# Bốn nguồn: ý giám khảo gắn khong_co_can_cu; câu trả lời sau tra cứu mà không khẳng định được gì
# (giám khảo: 0 ý — thường là "văn bản không đề cập"); câu hỏi gửi cán bộ (đơn hoi_dap ở qlsv);
# đánh giá -1.
# Hai nguồn từ chat KHÔNG trả mã SV / họ tên / id người dùng (quản trị chỉ cần biết hỏi gì).
GAP_SOURCES = ("khong_can_cu", "khong_tim_thay", "hoi_can_bo", "danh_gia_xau")
MAX_PER_SOURCE = 200
EXCERPT_MAX = 300


def _excerpt(text: str | None) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= EXCERPT_MAX else flat[: EXCERPT_MAX - 1].rstrip() + "…"


def _item(nguon: str, thoi_gian: datetime, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "nguon": nguon,
        "thoi_gian": thoi_gian,
        "cau_hoi": None,
        "noi_dung": "",
        "ly_do": None,
        "tra_loi_can_bo": None,
        "tin_nhan_id": None,
        "ma_don": None,
        "phong_ban": None,
        "trang_thai": None,
        "da_vao_kho": False,
    }
    base.update(fields)
    return base


def _previous_questions(db: Session, messages: list[TinNhan]) -> dict[int, str]:
    """{id tin nhắn trợ lý: câu hỏi của sinh viên ngay trước nó trong cùng hội thoại}."""
    conv_ids = {m.hoi_thoai_id for m in messages}
    if not conv_ids:
        return {}
    rows = db.execute(
        select(TinNhan.id, TinNhan.hoi_thoai_id, TinNhan.noi_dung)
        .where(TinNhan.hoi_thoai_id.in_(conv_ids), TinNhan.vai_tro == "user")
        .order_by(TinNhan.id)
    ).all()
    by_conv: dict[int, list[tuple[int, str]]] = {}
    for msg_id, conv_id, text in rows:
        by_conv.setdefault(conv_id, []).append((msg_id, text))
    out = {}
    for m in messages:
        before = [text for msg_id, text in by_conv.get(m.hoi_thoai_id, []) if msg_id < m.id]
        if before:
            out[m.id] = _excerpt(before[-1])
    return out


def unsupported_claim_gaps(db: Session, since: datetime) -> list[dict[str, Any]]:
    messages = list(
        db.scalars(
            select(TinNhan)
            .where(
                TinNhan.vai_tro == "assistant",
                TinNhan.created_at >= to_db(since),
                cast(TinNhan.kiem_chung, UnicodeText).like("%khong_co_can_cu%"),
            )
            .order_by(TinNhan.id.desc())
            .limit(MAX_PER_SOURCE)
        )
    )
    questions = _previous_questions(db, messages)
    items = []
    for m in messages:
        for claim in (m.kiem_chung or {}).get("y", []):
            if isinstance(claim, dict) and claim.get("ket_luan") == "khong_co_can_cu":
                items.append(
                    _item(
                        "khong_can_cu",
                        from_db(m.created_at),  # type: ignore[arg-type]
                        cau_hoi=questions.get(m.id),
                        noi_dung=_excerpt(str(claim.get("cau", ""))),
                        ly_do=_excerpt(str(claim.get("ly_do", ""))) or None,
                        tin_nhan_id=m.id,
                    )
                )
    return items


def not_found_gaps(db: Session, since: datetime) -> list[dict[str, Any]]:
    """Trợ lý đã tra cứu quy chế nhưng câu trả lời không có ý nào để kiểm chứng (tong = 0)."""
    messages = list(
        db.scalars(
            select(TinNhan)
            .where(
                TinNhan.vai_tro == "assistant",
                TinNhan.created_at >= to_db(since),
                func.json_value(TinNhan.kiem_chung, "$.tong") == "0",
            )
            .order_by(TinNhan.id.desc())
            .limit(MAX_PER_SOURCE)
        )
    )
    questions = _previous_questions(db, messages)
    return [
        _item(
            "khong_tim_thay",
            from_db(m.created_at),  # type: ignore[arg-type]
            cau_hoi=questions.get(m.id),
            noi_dung=_excerpt(m.noi_dung),
            tin_nhan_id=m.id,
        )
        for m in messages
    ]


def bad_rating_gaps(db: Session, since: datetime) -> list[dict[str, Any]]:
    rows = db.execute(
        select(DanhGiaCauTraLoi, TinNhan)
        .join(TinNhan, TinNhan.id == DanhGiaCauTraLoi.tin_nhan_id)
        .where(DanhGiaCauTraLoi.diem == -1, DanhGiaCauTraLoi.created_at >= to_db(since))
        .order_by(DanhGiaCauTraLoi.id.desc())
        .limit(MAX_PER_SOURCE)
    ).all()
    questions = _previous_questions(db, [m for _, m in rows])
    return [
        _item(
            "danh_gia_xau",
            from_db(rating.created_at),  # type: ignore[arg-type]
            cau_hoi=questions.get(m.id),
            noi_dung=_excerpt(m.noi_dung),
            ly_do=_excerpt(rating.gop_y) or None,
            tin_nhan_id=m.id,
        )
        for rating, m in rows
    ]


def staff_question_gaps(requests: list[dict[str, Any]], since: datetime) -> list[dict[str, Any]]:
    items = []
    for don in requests:
        try:
            created = datetime.fromisoformat(str(don["created_at"]))
        except (KeyError, ValueError):
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=since.tzinfo)
        if created < since:
            continue
        content = don.get("noi_dung") or {}
        question = _excerpt(str(content.get("cau_hoi", "")))
        items.append(
            _item(
                "hoi_can_bo",
                created,
                cau_hoi=question,
                noi_dung=question,
                tra_loi_can_bo=don.get("ghi_chu_xu_ly"),
                ma_don=don.get("ma_don"),
                phong_ban=content.get("phong_ban"),
                trang_thai=don.get("trang_thai"),
            )
        )
    return items


def mark_in_knowledge_base(db: Session, items: list[dict[str, Any]]) -> None:
    linked = db.execute(select(KhoHoiDap.tin_nhan_id, KhoHoiDap.ma_don)).all()
    messages = {t for t, _ in linked if t is not None}
    requests = {d for _, d in linked if d}
    for item in items:
        item["da_vao_kho"] = item["tin_nhan_id"] in messages or item["ma_don"] in requests
