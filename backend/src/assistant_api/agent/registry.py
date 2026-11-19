"""Danh mục công cụ: đồng bộ với MCP server, lọc theo chính sách, ẩn tham số + tiêm ngữ cảnh.

Quy tắc bảo mật (CLAUDE.md):
1. `ma_sv`, `ma_khoa` bị XÓA khỏi JSON schema gửi cho LLM; khi gọi, assistant_api ghi đè bằng
   giá trị của tài khoản đang đăng nhập (LLM gửi kèm cũng bị bỏ). Nhật ký lưu cả bản gốc lẫn
   bản sau tiêm.
6. Công cụ bị tắt (`cong_cu.bat = 0`) hoặc thuộc server bị tắt không được đưa cho LLM.

Đồng bộ (docs/02 mục 7): tool có trên server nhưng chưa có trong bảng `cong_cu` được thêm với
`muc_rui_ro='ghi'`, `can_xac_nhan=1`, `bat=0` — an toàn mặc định, quản trị viên phải bật.
Chính sách (bat, can_xac_nhan) đọc lại từ CSDL mỗi lượt -> quản trị viên đổi là có hiệu lực ngay.
"""

import copy
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.mcp_client.client import McpClient, McpUnavailableError, ToolSpec
from src.assistant_api.models import CongCu, McpServer, NguoiDung

logger = logging.getLogger(__name__)

INJECTED_PARAMS = ("ma_sv", "ma_khoa")
RESYNC_SECONDS = 30.0
PROBE_SECONDS = 15.0


@dataclass(frozen=True)
class ToolPolicy:
    server: str
    name: str
    muc_rui_ro: str
    can_xac_nhan: bool
    bat: bool  # tool bật VÀ server bật
    spec: ToolSpec | None  # None = server hiện không cung cấp tool này

    @property
    def available(self) -> bool:
        return self.bat and self.spec is not None


class ContextInjectionError(Exception):
    """Tool cần ma_sv/ma_khoa nhưng tài khoản không có (vd admin)."""


def strip_injected(schema: dict[str, Any]) -> dict[str, Any]:
    """Bản sao schema đã xóa ma_sv/ma_khoa khỏi properties và required."""
    clean = copy.deepcopy(schema)
    props = clean.get("properties") or {}
    for key in INJECTED_PARAMS:
        props.pop(key, None)
    if "required" in clean:
        clean["required"] = [r for r in clean["required"] if r not in INJECTED_PARAMS]
        if not clean["required"]:
            clean.pop("required")
    clean.setdefault("type", "object")
    clean.setdefault("properties", props)
    return clean


def inject_context(spec: ToolSpec, llm_args: dict[str, Any], user: NguoiDung) -> dict[str, Any]:
    """Bỏ mọi ma_sv/ma_khoa LLM gửi; điền giá trị của tài khoản (chỉ tham số tool có khai báo)."""
    args = {k: v for k, v in llm_args.items() if k not in INJECTED_PARAMS}
    declared = (spec.input_schema.get("properties") or {}).keys()
    values = {"ma_sv": user.ma_sv, "ma_khoa": user.ma_khoa}
    for key in INJECTED_PARAMS:
        if key in declared:
            if not values[key]:
                raise ContextInjectionError(
                    f"Tài khoản không có {key} nên không dùng được công cụ {spec.name}."
                )
            args[key] = values[key]
    return args


def first_line(text: str, limit: int = 500) -> str:
    line = (text or "").strip().split("\n", 1)[0].strip()
    return line[:limit] or "(chưa có mô tả)"


class ToolRegistry:
    def __init__(self, client: McpClient) -> None:
        self.client = client
        self._specs: dict[str, ToolSpec] = {}  # tên tool -> spec
        self.server_status: dict[str, str] = {}  # server -> "ok" | thông báo lỗi
        self._last_sync = 0.0
        self._last_probe = 0.0

    # ----- đồng bộ ------------------------------------------------------------
    async def sync(self, db: Session) -> None:
        servers = db.scalars(select(McpServer).order_by(McpServer.id)).all()
        specs: dict[str, ToolSpec] = {}
        for server in servers:
            if not server.bat:
                self.server_status[server.ten] = "tắt"
                continue
            if server.ten not in self.client.servers:
                self.client.set_target(server.ten, server.dia_chi)
            try:
                tools = await self.client.list_tools(server.ten)
            except McpUnavailableError as exc:
                self.server_status[server.ten] = str(exc)
                logger.warning("Đồng bộ %s thất bại: %s", server.ten, exc)
                continue
            self.server_status[server.ten] = "ok"
            known = {c.ten for c in server.cong_cu}
            for spec in tools:
                if spec.name in specs:
                    logger.error(
                        "Trùng tên tool '%s' giữa các server, bỏ bản ở %s", spec.name, server.ten
                    )
                    continue
                specs[spec.name] = spec
                if spec.name not in known:
                    db.add(
                        CongCu(
                            mcp_server_id=server.id,
                            ten=spec.name,
                            mo_ta=first_line(spec.description),
                            muc_rui_ro="ghi",
                            can_xac_nhan=True,
                            bat=False,
                        )
                    )
                    logger.warning("Tool mới '%s' (%s): thêm với bat=0", spec.name, server.ten)
        db.commit()
        self._specs = specs
        self._last_sync = time.monotonic()

    async def ensure_fresh(self, db: Session) -> None:
        """Server lỗi lúc khởi động -> thử đồng bộ lại (tối đa 30 giây/lần)."""
        failing = any(s not in ("ok", "tắt") for s in self.server_status.values())
        stale = time.monotonic() - self._last_sync > RESYNC_SECONDS
        if (not self._last_sync or failing) and stale:
            await self.sync(db)

    async def probe(self, max_age: float = PROBE_SECONDS) -> dict[str, str]:
        """Dò nhanh các MCP server đang bật (dùng cho /health, tối đa 1 lần / max_age giây).
        Server vừa chết -> đánh dấu lỗi, lần ensure_fresh sau sẽ đồng bộ lại (gỡ tool của nó);
        server sống lại -> ensure_fresh cũng đồng bộ lại để có tool trở lại."""
        if time.monotonic() - self._last_probe < max_age:
            return self.server_status
        self._last_probe = time.monotonic()
        for name, status in list(self.server_status.items()):
            if status == "tắt" or name not in self.client.servers:
                continue
            try:
                await self.client.list_tools(name)
            except McpUnavailableError as exc:
                if status == "ok":
                    logger.warning("MCP server %s mất kết nối: %s", name, exc)
                self.server_status[name] = str(exc)
                self._last_sync = 0.0  # cho phép ensure_fresh đồng bộ lại ngay
            else:
                if status != "ok":
                    self._last_sync = 0.0
                    self.server_status[name] = "khoi_phuc"
        return self.server_status

    def available_tool_names(self) -> set[str]:
        """Tên các tool server đang cung cấp (theo lần đồng bộ gần nhất)."""
        return set(self._specs)

    # ----- chính sách ---------------------------------------------------------
    def policies(self, db: Session) -> dict[str, ToolPolicy]:
        rows = db.execute(select(CongCu, McpServer).join(McpServer)).all()
        return {
            tool.ten: ToolPolicy(
                server=server.ten,
                name=tool.ten,
                muc_rui_ro=tool.muc_rui_ro,
                can_xac_nhan=bool(tool.can_xac_nhan),
                bat=bool(tool.bat and server.bat),
                spec=self._specs.get(tool.ten),
            )
            for tool, server in rows
        }

    @staticmethod
    def tools_for_llm(policies: dict[str, ToolPolicy]) -> list[dict[str, Any]]:
        """Định dạng tool kiểu OpenAI (LiteLLM tự chuyển sang Anthropic), sắp theo tên để
        danh sách tool ổn định giữa các lượt (giữ prompt cache)."""
        tools = []
        for name in sorted(policies):
            policy = policies[name]
            if not policy.available or policy.spec is None:
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": policy.spec.description.strip(),
                        "parameters": strip_injected(policy.spec.input_schema),
                    },
                }
            )
        return tools
