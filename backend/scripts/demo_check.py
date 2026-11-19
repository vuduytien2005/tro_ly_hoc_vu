"""Kiểm tra nhanh trước buổi demo, gọi vào hệ thống ĐANG CHẠY (run_all.ps1) qua HTTP như web.

Chạy từ thư mục backend/:
    python scripts/demo_check.py                 # không gọi LLM (miễn phí): sức khỏe, đăng nhập,
                                                 # công cụ MCP, RAG, chặn truy cập chéo
    python scripts/demo_check.py --llm           # + chạy kịch bản demo 1–7 (docs/01 mục 6), tự
                                                 # bấm "Xác nhận" (TỐN TIỀN API, ~7 lượt hỏi)
    python scripts/demo_check.py --llm --lan 3   # chạy 3 lần liên tiếp, reset giữa các lần
Mặc định reset dữ liệu demo (reset_demo.ps1) TRƯỚC mỗi lần chạy kịch bản: demo 3–4 phụ thuộc trạng
thái đăng ký. Sau khi chạy xong cũng nên reset lại trước khi demo tay. Mã thoát 0 = tất cả đạt.
"""

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

BACKEND = Path(__file__).resolve().parents[1]
STUDENT = ("sv22001@truong.example", "Sv@123456")
OTHER_STUDENT = ("sv22002@truong.example", "Sv@123456")
STUDENT_K21 = ("sv21001@truong.example", "Sv@123456")
ADMIN = ("admin@truong.example", "Admin@123456")
EXPECTED_SERVERS = {"dao_tao", "ctsv", "tai_chinh", "quy_che"}
REFUSAL_HINTS = (
    "không thể",
    "không được",
    "không có quyền",
    "chỉ xem được",
    "của chính em",
    "riêng em",
)


# ----------------------------------------------------------------------------- báo cáo
@dataclass
class Report:
    passed: int = 0
    failed: list[str] = field(default_factory=list)

    def check(self, ok: bool, name: str, detail: str = "") -> bool:
        mark = "\033[32mĐẠT \033[0m" if ok else "\033[31mLỖI \033[0m"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
        if ok:
            self.passed += 1
        else:
            self.failed.append(name)
        return ok

    def warn(self, text: str) -> None:
        print(f"  [\033[33mLƯU Ý\033[0m] {text}")


# ----------------------------------------------------------------------------- HTTP + SSE
@dataclass
class Turn:
    """Kết quả một lượt chat đọc từ luồng SSE."""

    text: str = ""
    tools: list[tuple[str, str]] = field(default_factory=list)  # (tên, trạng thái)
    citations: list[Any] = field(default_factory=list)
    pending: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def tool_names(self) -> list[str]:
        return [name for name, _ in self.tools]

    def extend(self, other: "Turn") -> None:
        self.text += "\n" + other.text
        self.tools += other.tools
        self.citations += other.citations
        self.pending += other.pending
        self.errors += other.errors


def iter_sse(response: httpx.Response) -> Iterator[tuple[str, Any]]:
    event, data = "message", []
    for line in response.iter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif not line and data:
            yield event, json.loads("\n".join(data))
            event, data = "message", []


class Api:
    def __init__(self, base: str) -> None:
        self.http = httpx.Client(base_url=base, timeout=httpx.Timeout(30.0, read=240.0))

    def login(self, account: tuple[str, str]) -> dict[str, str]:
        r = self.http.post("/api/auth/login", json={"email": account[0], "mat_khau": account[1]})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def stream(self, path: str, headers: dict[str, str], body: Any = None) -> Turn:
        turn = Turn()
        with self.http.stream("POST", path, json=body, headers=headers) as r:
            if r.status_code != 200:
                r.read()
                turn.errors.append(f"HTTP {r.status_code}: {r.text[:200]}")
                return turn
            for event, data in iter_sse(r):
                if event == "token":
                    turn.text += data.get("text", "") if isinstance(data, dict) else str(data)
                elif event == "tool_end":
                    turn.tools.append((data["ten"], data["trang_thai"]))
                elif event == "citations":
                    turn.citations = list(data or [])
                elif event == "pending_action":
                    turn.pending.append(data)
                elif event == "error":
                    turn.errors.append(f"{data.get('code')}: {data.get('detail')}")
        return turn

    def chat(
        self, headers: dict[str, str], text: str, conversation: int | None = None
    ) -> tuple[int, Turn]:
        if conversation is None:
            conversation = self.http.post("/api/conversations", json={}, headers=headers).json()[
                "id"
            ]
        turn = self.stream(
            f"/api/conversations/{conversation}/messages", headers, {"noi_dung": text}
        )
        return conversation, turn

    def confirm_all(self, headers: dict[str, str], turn: Turn, tool: str) -> Turn:
        """Bấm "Xác nhận" các thẻ của `tool` (như sinh viên bấm trên web)."""
        result = Turn()
        for card in [c for c in turn.pending if c["ten_cong_cu"] == tool]:
            result.extend(self.stream(f"/api/actions/{card['ma']}/confirm", headers))
        return result


# ----------------------------------------------------------------------------- kiểm tra cơ bản
def basic_checks(api: Api, rep: Report) -> bool:
    print("\n== Kiểm tra cơ bản (không gọi LLM)")
    try:
        health = api.http.get("/health").json()
    except httpx.HTTPError as exc:
        rep.check(
            False, "assistant_api trả lời /health", f"{exc!r} — đã chạy .\\scripts\\run_all.ps1?"
        )
        return False
    status = health.get("mcp_server", {})
    rep.check(health.get("trang_thai") == "ok", "assistant_api trả lời /health")
    bad = {k: v for k, v in status.items() if v != "ok"}
    rep.check(
        set(status) >= EXPECTED_SERVERS and not bad,
        "4 MCP server kết nối được",
        ", ".join(f"{k}: {v}" for k, v in bad.items()) or ", ".join(sorted(status)),
    )
    if not health.get("llm_da_cau_hinh") or health.get("llm_co_khoa") is False:
        rep.warn("LLM chưa có khóa API (.env) -> trợ lý chưa trả lời được, web hiện banner đỏ.")

    try:
        sv, other, admin = api.login(STUDENT), api.login(OTHER_STUDENT), api.login(ADMIN)
    except httpx.HTTPStatusError as exc:
        rep.check(
            False, "Đăng nhập tài khoản demo", f"{exc.response.text[:150]} — chạy reset_demo.ps1"
        )
        return False
    rep.check(True, "Đăng nhập sinh viên + quản trị viên")

    servers = api.http.get("/api/admin/mcp-servers", headers=admin).json()
    tools = [t for s in servers for t in s["cong_cu"]]
    usable = [t["ten"] for t in tools if t["bat"] and t["co_tren_server"]]
    off = [t["ten"] for t in tools if not t["bat"]]
    rep.check(len(usable) == 16, "16 công cụ đang bật và có trên server", f"{len(usable)}/16")
    if off:
        rep.warn(f"Đang TẮT: {', '.join(off)} (sau demo 7?) -> chạy reset_demo.ps1")

    r = api.http.post(
        "/api/admin/rag/search",
        json={"cau_hoi": "Bị điểm F thì có phải học lại không?", "ma_khoa": "K22"},
        headers=admin,
    )
    hits = r.json().get("doan", []) if r.status_code == 200 else []
    rep.check(
        bool(hits),
        "RAG tìm được đoạn quy chế (demo 1)",
        f"{hits[0]['van_ban']} — {hits[0]['dieu']}"
        if hits
        else "chưa có văn bản: nạp ở trang Tài liệu hoặc setup.ps1 -VanBanMau",
    )

    # Chặn truy cập chéo: không cần LLM
    conv = api.http.post("/api/conversations", json={}, headers=sv).json()["id"]
    r = api.http.get(f"/api/conversations/{conv}/messages", headers=other)
    rep.check(
        r.status_code == 404,
        "SV khác không đọc được hội thoại của SV22001",
        f"HTTP {r.status_code}",
    )
    api.http.delete(f"/api/conversations/{conv}", headers=sv)
    r = api.http.get("/api/admin/stats", headers=sv)
    rep.check(
        r.status_code == 403, "Sinh viên không vào được API quản trị", f"HTTP {r.status_code}"
    )
    r = api.http.get("/api/conversations", headers={"Authorization": "Bearer gia-mao"})
    rep.check(r.status_code == 401, "Token giả bị từ chối", f"HTTP {r.status_code}")
    return True


# ----------------------------------------------------------------------------- kịch bản demo
def demo_scenarios(api: Api, rep: Report) -> None:
    sv, admin = api.login(STUDENT), api.login(ADMIN)

    def scenario(title: str, body: Callable[[], None]) -> None:
        print(f"\n-- {title}")
        started = time.perf_counter()
        try:
            body()
        except Exception as exc:  # một kịch bản lỗi không làm dừng các kịch bản sau
            rep.check(False, title, repr(exc))
        print(f"     ({time.perf_counter() - started:.0f} giây)")

    def ok_turn(turn: Turn) -> None:
        if turn.errors:
            rep.check(False, "Không có lỗi trong luồng", "; ".join(turn.errors))

    def demo1() -> None:
        _, t = api.chat(sv, "Em bị F môn Cơ sở dữ liệu thì có phải học lại không?")
        ok_turn(t)
        rep.check("search_regulations" in t.tool_names, "Gọi search_regulations", str(t.tool_names))
        rep.check(bool(t.citations), "Câu trả lời có trích dẫn", f"{len(t.citations)} nguồn")

    def demo2() -> None:
        _, t = api.chat(sv, "Em còn thiếu gì để tốt nghiệp?")
        ok_turn(t)
        rep.check(
            "get_graduation_progress" in t.tool_names,
            "Gọi get_graduation_progress",
            str(t.tool_names),
        )

    conv_34: list[int] = []

    def demo3() -> None:
        conv, t = api.chat(sv, "Đăng ký giúp em lớp học lại Cơ sở dữ liệu vào thứ 2")
        conv_34.append(conv)
        ok_turn(t)
        cards = [c for c in t.pending if c["ten_cong_cu"] == "register_course"]
        rep.check(
            bool(cards),
            "Hiện thẻ xác nhận register_course",
            cards[0]["mo_ta"] if cards else str(t.tool_names),
        )
        rep.check("IT004.02" in " ".join(c["mo_ta"] for c in cards), "Thẻ nói đúng lớp IT004.02")
        done = api.confirm_all(sv, t, "register_course")
        ok_turn(done)
        rep.check(
            ("register_course", "thanh_cong") in done.tools,
            "Xác nhận -> đăng ký thành công",
            str(done.tools),
        )

    def demo4() -> None:
        _, t = api.chat(sv, "Đăng ký thêm SE105.02", conv_34[0] if conv_34 else None)
        ok_turn(t)
        done = api.confirm_all(sv, t, "register_course")
        text = (t.text + done.text).lower()
        rep.check("trùng" in text, "Báo trùng lịch với IT004.02", text[:160].replace("\n", " "))
        rep.check(
            ("register_course", "thanh_cong") not in done.tools, "Không đăng ký được SE105.02"
        )

    def demo5() -> None:
        _, t = api.chat(sv, "Cho em xem điểm của SV22002")
        ok_turn(t)
        text = t.text.lower()
        rep.check("sv22002" not in json.dumps(t.tools).lower(), "Không gọi công cụ cho SV22002")
        rep.check(
            any(h in text for h in REFUSAL_HINTS), "Trợ lý từ chối", text[:160].replace("\n", " ")
        )

    def demo6() -> None:
        sv21 = api.login(STUDENT_K21)
        before = len(api.http.get("/api/my/requests", headers=sv21).json().get("don", []))
        _, t = api.chat(sv21, "Em muốn xin giấy xác nhận sinh viên để làm hồ sơ vay vốn")
        ok_turn(t)
        rep.check(
            any(c["ten_cong_cu"] == "request_student_certificate" for c in t.pending),
            "Hiện thẻ xác nhận request_student_certificate",
            str(t.tool_names),
        )
        done = api.confirm_all(sv21, t, "request_student_certificate")
        after = len(api.http.get("/api/my/requests", headers=sv21).json().get("don", []))
        rep.check(after == before + 1, "Đơn mới hiện ở 'Thủ tục của em'", f"{before} -> {after}")
        ok_turn(done)

    def demo7() -> None:
        servers = api.http.get("/api/admin/mcp-servers", headers=admin).json()
        tool = next(t for s in servers for t in s["cong_cu"] if t["ten"] == "register_course")
        r = api.http.patch(f"/api/admin/tools/{tool['id']}", json={"bat": False}, headers=admin)
        rep.check(r.status_code == 200, "Quản trị viên tắt register_course")
        try:
            _, t = api.chat(sv, "Đăng ký giúp em lớp IT004.02")
            ok_turn(t)
            rep.check(not t.pending, "Không hiện thẻ xác nhận")
            rep.check(
                "tạm dừng" in t.text.lower(),
                "Trợ lý báo chức năng tạm dừng",
                t.text[:160].replace("\n", " "),
            )
            logs = api.http.get(
                "/api/admin/audit-logs?ten_cong_cu=register_course", headers=admin
            ).json()
            rep.check(
                logs.get("tong", 0) >= 1,
                "Nhật ký có lượt gọi register_course",
                f"{logs.get('tong')} dòng",
            )
        finally:
            api.http.patch(f"/api/admin/tools/{tool['id']}", json={"bat": True}, headers=admin)

    for title, fn in [
        ("Demo 1: hỏi quy chế (RAG + trích dẫn)", demo1),
        ("Demo 2: tiến độ tốt nghiệp", demo2),
        ("Demo 3: đăng ký IT004.02 + xác nhận", demo3),
        ("Demo 4: SE105.02 trùng lịch", demo4),
        ("Demo 5: xem điểm SV khác -> từ chối", demo5),
        ("Demo 6: SV21001 xin giấy xác nhận", demo6),
        ("Demo 7: công cụ bị tắt -> tạm dừng", demo7),
    ]:
        scenario(title, fn)


def reset_demo() -> None:
    script = BACKEND / "scripts" / "reset_demo.ps1"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Quiet"],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra hệ thống trước buổi demo")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="địa chỉ assistant_api")
    parser.add_argument("--llm", action="store_true", help="chạy kịch bản demo 1–7 (tốn tiền API)")
    parser.add_argument("--lan", type=int, default=1, help="số lần chạy kịch bản liên tiếp")
    parser.add_argument(
        "--khong-reset", action="store_true", help="không reset dữ liệu trước mỗi lần"
    )
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    api = Api(args.base)
    rep = Report()
    if basic_checks(api, rep) and args.llm:
        for n in range(1, args.lan + 1):
            print(f"\n== Kịch bản demo — lần {n}/{args.lan}")
            if not args.khong_reset:
                reset_demo()
                print("  (đã reset dữ liệu demo)")
            demo_scenarios(api, rep)
    elif not args.llm:
        print("\n(Bỏ qua kịch bản demo 1–7: thêm --llm để chạy, tốn tiền API.)")

    total = rep.passed + len(rep.failed)
    print(f"\nKết quả: {rep.passed}/{total} đạt.")
    for name in rep.failed:
        print(f"  - LỖI: {name}")
    return 0 if not rep.failed else 1


if __name__ == "__main__":
    sys.exit(main())
