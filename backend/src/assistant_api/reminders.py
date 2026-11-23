"""Nhắc việc chủ động: tính các hạn sắp tới từ kết quả công cụ MCP đọc (không gọi gì ở đây).

Đầu vào là đúng dict mà `get_tuition_status`, `get_exam_schedule`, `get_borrowed_books`,
`list_my_requests` trả về;
nguồn nào thiếu (None) hoặc sai dạng thì bỏ qua. Hàm thuần -> dễ kiểm thử, không chạm CSDL.
Thiết kế: docs/superpowers/specs/2026-11-23-nhac-viec-design.md.
"""

from collections.abc import Callable, Iterable
from datetime import date
from typing import Any, Literal, TypedDict

Level = Literal["khan", "sap_toi"]
Kind = Literal["hoc_phi", "lich_thi", "sach", "don"]

TUITION_WINDOW_DAYS = 30
TUITION_URGENT_DAYS = 7
EXAM_WINDOW_DAYS = 14
EXAM_URGENT_DAYS = 3
BOOK_WINDOW_DAYS = 7
BOOK_URGENT_DAYS = 2
# Đơn vừa được cán bộ xử lý xong (duyệt / từ chối / hoàn tất) trong N ngày gần đây
REQUEST_WINDOW_DAYS = 7
REQUEST_DONE = {
    "da_duyet": "đã được duyệt",
    "tu_choi": "bị từ chối",
    "hoan_tat": "đã hoàn tất",
}


class Reminder(TypedDict):
    loai: Kind
    muc_do: Level
    tieu_de: str
    chi_tiet: str
    han: str  # YYYY-MM-DD (đơn: ngày cập nhật trạng thái)
    con_ngay: int  # âm = đã quá hạn (đơn: âm số ngày kể từ lúc xử lý)
    cau_hoi: str  # câu hỏi soạn sẵn cho khung chat


def _vn(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đồng"


def _when(days: int) -> str:
    if days < 0:
        return f"đã quá hạn {-days} ngày"
    if days == 0:
        return "hôm nay"
    if days == 1:
        return "ngày mai"
    return f"còn {days} ngày"


def _tuition(data: dict[str, Any], today: date) -> Iterable[Reminder]:
    con_no = int(data.get("con_no") or 0)
    if con_no <= 0:
        return
    due = date.fromisoformat(str(data["han_nop"]))
    days = (due - today).days
    if days > TUITION_WINDOW_DAYS:
        return
    title = "Học phí đã quá hạn nộp" if days < 0 else "Sắp đến hạn nộp học phí"
    yield Reminder(
        loai="hoc_phi",
        muc_do="khan" if days <= TUITION_URGENT_DAYS else "sap_toi",
        tieu_de=title,
        chi_tiet=f"Còn nợ {_vnd(con_no)}, hạn nộp {_vn(due)} ({_when(days)}).",
        han=due.isoformat(),
        con_ngay=days,
        cau_hoi="Em còn nợ học phí bao nhiêu và hạn nộp khi nào?",
    )


def _exams(data: dict[str, Any], today: date) -> Iterable[Reminder]:
    for x in data["lich_thi"]:
        day = date.fromisoformat(str(x["ngay_thi"]))
        days = (day - today).days
        if not 0 <= days <= EXAM_WINDOW_DAYS:
            continue
        yield Reminder(
            loai="lich_thi",
            muc_do="khan" if days <= EXAM_URGENT_DAYS else "sap_toi",
            tieu_de=f"Thi {x['ten_hp']}",
            chi_tiet=f"{_vn(day)} lúc {x['gio']}, phòng {x['phong']} ({_when(days)}).",
            han=day.isoformat(),
            con_ngay=days,
            cau_hoi=f"Lịch thi môn {x['ten_hp']} của em thế nào?",
        )


def _books(data: dict[str, Any], today: date) -> Iterable[Reminder]:
    for b in data["sach"]:
        due = date.fromisoformat(str(b["han_tra"]))
        days = (due - today).days
        overdue = bool(b.get("qua_han")) or days < 0
        if not overdue and days > BOOK_WINDOW_DAYS:
            continue
        name = b["ten_sach"]
        ask = (
            f"Gia hạn sách “{name}” giúp em."
            if b.get("gia_han_duoc") and not overdue
            else f"Sách “{name}” của em không gia hạn được thì em phải làm gì?"
        )
        yield Reminder(
            loai="sach",
            muc_do="khan" if overdue or days <= BOOK_URGENT_DAYS else "sap_toi",
            tieu_de=f"Trả sách “{name}”" if overdue else f"Sách “{name}” sắp hết hạn",
            chi_tiet=f"Hạn trả {_vn(due)} ({_when(days)}).",
            han=due.isoformat(),
            con_ngay=days,
            cau_hoi=ask,
        )


def _ago(days: int) -> str:
    return "hôm nay" if days == 0 else ("hôm qua" if days == 1 else f"{days} ngày trước")


def _requests(data: dict[str, Any], today: date) -> Iterable[Reminder]:
    for d in data["don"]:
        status = REQUEST_DONE.get(str(d["ma_trang_thai"]))
        if status is None:
            continue  # mới tạo / đang xử lý: chưa có gì để báo
        changed = date.fromisoformat(str(d.get("ngay_cap_nhat") or d["ngay_tao"]))
        days = (today - changed).days
        if not 0 <= days <= REQUEST_WINDOW_DAYS:
            continue
        rejected = d["ma_trang_thai"] == "tu_choi"
        ma_don = d["ma_don"]
        yield Reminder(
            loai="don",
            # bị từ chối: sinh viên cần làm lại / bổ sung -> khẩn; còn lại chỉ để biết
            muc_do="khan" if rejected else "sap_toi",
            tieu_de=f"{d['loai_don']} {status}",
            chi_tiet=f"Mã đơn {ma_don}, cập nhật {_ago(days)} ({_vn(changed)}).",
            han=changed.isoformat(),
            con_ngay=-days,
            cau_hoi=(
                f"Vì sao đơn {ma_don} của em bị từ chối và em cần làm gì tiếp?"
                if rejected
                else f"Đơn {ma_don} của em xử lý thế nào rồi?"
            ),
        )


def _safe(
    fn: Callable[[dict[str, Any], date], Iterable[Reminder]],
    data: dict[str, Any] | None,
    today: date,
) -> list[Reminder]:
    if not data:
        return []
    try:
        return list(fn(data, today))
    except (KeyError, TypeError, ValueError):
        return []  # kết quả công cụ sai dạng: bỏ nguồn này, không làm hỏng cả danh sách


def build_reminders(
    tuition: dict[str, Any] | None,
    exams: dict[str, Any] | None,
    borrows: dict[str, Any] | None,
    today: date,
    requests: dict[str, Any] | None = None,
) -> list[Reminder]:
    """Danh sách nhắc việc, việc khẩn trước, cùng mức thì hạn gần trước."""
    items = (
        _safe(_tuition, tuition, today)
        + _safe(_exams, exams, today)
        + _safe(_books, borrows, today)
        + _safe(_requests, requests, today)
    )
    return sorted(items, key=lambda r: (r["muc_do"] != "khan", r["con_ngay"]))
