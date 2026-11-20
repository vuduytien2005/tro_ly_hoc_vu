"""Harness chạy trợ lý THẬT (assistant_api + vòng lặp Agent + 4 MCP server + qlsv_api) trong cùng
tiến trình cho TN2/TN3/TN4.

Khác với lúc chạy demo:
- MCP server được gọi trong tiến trình (`McpClient` nhận đối tượng MCPServer, như
  backend/tests) thay vì qua HTTP; qlsv_api được gắn qua `httpx.ASGITransport`.
  Logic công cụ, tiêm ngữ cảnh, xác nhận
  hành động, nhật ký... là code thật, không giả lập.
- CSDL tlhv_assistant: 1 transaction cho cả lượt chạy, ROLLBACK ở cuối (hội thoại, nhật ký, văn bản
  thực nghiệm không ở lại). CSDL tlhv_qlsv: MỖI kịch bản 1 transaction riêng, ROLLBACK sau kịch bản
  -> kịch bản nào cũng bắt đầu từ dữ liệu mẫu (đăng ký lớp ở A006 không ảnh hưởng A007).
- quy_che dùng Chroma tạm chứa bộ văn bản thực nghiệm (evaluation/corpus_*).
- Gọi API qua TestClient + JWT thật (đăng nhập bằng token tạo từ create_access_token).

Đo: số bước (số lần gọi LLM), token vào/ra, chi phí ước tính (bảng giá LiteLLM hoặc ghi đè trong
cấu hình), thời gian phản hồi.
"""

import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from typing import Any

from evaluation.common import PACER, mean, quiet_logs

MINIMAL_PARAM_KEYS = ("type", "items", "enum", "anyOf", "default", "minimum", "maximum")

# Giá trị điền cho tham số BẮT BUỘC mà kịch bản không nêu (chỉ dùng khi --dry-run)
DRY_RUN_DEFAULTS: dict[str, Any] = {
    "tu_khoa": "IT004",
    "ma_lop": "IT004.02",
    "ma_hp": "IT004",
    "muc_dich": "làm hồ sơ",
    "ly_do": "lý do cá nhân",
    "tu_hoc_ky": "2026-2027-HK2",
    "ma_don": "DT-2026-0001",
}


# ----- LLM có đo đếm -----------------------------------------------------------------
class MeteredLLM:
    """Bọc LLM thật/giả: đếm số lần gọi (bước), token; `inner` đổi được giữa các kịch bản.

    Đo thời gian (NF-01), tính từ `start_timer()`, đã TRỪ thời gian giãn nhịp:
    - `first_feedback_s`: phản hồi đầu tiên sinh viên thấy — chữ đầu tiên, hoặc lúc LLM trả lời
      gọi công cụ (chip "Đang ..." hiện ngay sau đó), tùy cái nào đến trước;
    - `ttft_s`: chữ đầu tiên của câu trả lời (None nếu không có chữ nào khi đồng hồ còn chạy).
    """

    def __init__(
        self, inner: Any, clock: Callable[[], float] = time.perf_counter, pacer: Any = PACER
    ) -> None:
        self.inner = inner
        self.clock = clock
        self.pacer = pacer
        self.first_feedback_s: float | None = None
        self.ttft_s: float | None = None
        self._timing = False
        self._t0 = 0.0
        self._paced0 = 0.0
        self.reset()

    def reset(self) -> None:
        self.steps = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.texts: list[str] = []  # văn bản GỐC của LLM (trước hậu kiểm trích dẫn)
        self.paced = 0.0  # giây chờ do giãn nhịp (không tính vào độ trễ)

    def start_timer(self) -> None:
        self.first_feedback_s = self.ttft_s = None
        self._t0, self._paced0, self._timing = self.clock(), self.paced, True

    def stop_timer(self) -> None:
        self._timing = False

    def _elapsed(self) -> float:
        return self.clock() - self._t0 - (self.paced - self._paced0)

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[Any]:
        from src.assistant_api.agent.llm import LlmTurn

        self.steps += 1
        self.paced += await self.pacer.await_turn()
        async for item in self.inner.stream(messages, tools):
            if isinstance(item, LlmTurn):
                self.tokens_in += item.input_tokens or 0
                self.tokens_out += item.output_tokens or 0
                if item.text:
                    self.texts.append(item.text)
                if self._timing and item.tool_calls and self.first_feedback_s is None:
                    self.first_feedback_s = self._elapsed()
            elif self._timing and item and self.ttft_s is None:
                self.ttft_s = self._elapsed()
                if self.first_feedback_s is None:
                    self.first_feedback_s = self.ttft_s
            yield item


def cost_usd(model: str, tokens_in: int, tokens_out: int, config: dict[str, Any]) -> float | None:
    price_in = config.get("gia_vao_usd_trieu_token")
    price_out = config.get("gia_ra_usd_trieu_token")
    if price_in is not None and price_out is not None:
        return (tokens_in * float(price_in) + tokens_out * float(price_out)) / 1_000_000
    try:
        import litellm

        a, b = litellm.cost_per_token(
            model=model, prompt_tokens=tokens_in, completion_tokens=tokens_out
        )
        return float(a) + float(b)
    except Exception:
        return None


def oracle_llm(steps: list[tuple[str, dict[str, Any]]], final_text: str) -> Any:
    """LLM giả cho --dry-run: gọi lần lượt các công cụ trong `steps` (mỗi bước 1 công cụ), sau đó
    luôn trả `final_text` (đủ cho cả lượt sau thẻ xác nhận và lượt sau khi bấm Xác nhận)."""
    from src.assistant_api.agent.llm import FakeLLM, FakeResponse

    responses = [FakeResponse(tool_calls=[(name, args)]) for name, args in steps]
    responses += [FakeResponse(text=final_text) for _ in range(6)]
    return FakeLLM(responses)


def minimal_spec(spec: Any) -> Any:
    """Mô tả công cụ "tối giản" (TN3): bỏ docstring hướng dẫn, chỉ giữ tên + kiểu tham số."""
    schema = json.loads(json.dumps(spec.input_schema))
    for prop in (schema.get("properties") or {}).values():
        for key in list(prop):
            if key not in MINIMAL_PARAM_KEYS:
                prop.pop(key)
    return replace(spec, description=spec.name.replace("_", " "), input_schema=schema)


def ma_khoa_of(ma_sv: str) -> str:
    """Quy ước dữ liệu mẫu: SV22xxx thuộc K22."""
    return f"K{ma_sv[2:4]}"


# ----- Kết quả một kịch bản -----------------------------------------------------------
@dataclass
class TurnResult:
    hoi_thoai_id: int
    answer: str  # nối mọi tin assistant của hội thoại
    last_answer: str
    citations: list[dict[str, Any]]
    calls: list[dict[str, Any]]  # nhật ký luot_goi_cong_cu theo thứ tự
    events: list[str]
    pending: list[dict[str, Any]]
    confirmed: int
    steps: int
    tokens_in: int
    tokens_out: int
    seconds: float
    raw_answer: str = ""  # câu trả lời cuối do LLM sinh, CHƯA qua hậu kiểm trích dẫn
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    first_feedback_s: float | None = None  # NF-01, xem MeteredLLM
    ttft_s: float | None = None

    @property
    def llm_calls(self) -> list[dict[str, Any]]:
        """Lượt gọi do LLM yêu cầu (bỏ lượt hệ thống tự gọi, vd tra lớp để dựng thẻ xác nhận)."""
        return [c for c in self.calls if c.get("tham_so_llm") is not None]


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


# ----- Harness -----------------------------------------------------------------------
class AgentHarness:
    def __init__(self, config: dict[str, Any], dry_run: bool, embedder_kind: str = "model") -> None:
        self.config = config
        self.dry_run = dry_run
        self.embedder_kind = "hashing" if dry_run else embedder_kind
        self.model = config.get("llm_model") or ""
        self.llm = MeteredLLM(None)
        # cho_giua_luot_goi_giay (cấu hình): khoảng cách tối thiểu giữa hai lần gọi LLM thật
        PACER.min_interval = 0.0 if dry_run else float(config.get("cho_giua_luot_goi_giay") or 0)
        self._stack = ExitStack()

    # -- dựng môi trường --
    def __enter__(self) -> "AgentHarness":
        import anyio
        import httpx
        from fastapi.testclient import TestClient
        from src.assistant_api.agent.registry import ToolRegistry
        from src.assistant_api.deps import get_db
        from src.assistant_api.main import create_app
        from src.assistant_api.mcp_client.client import McpClient
        from src.mcp_servers import common, ctsv, dao_tao, quy_che, tai_chinh
        from src.qlsv_api.main import app as qlsv_app
        from src.rag import retriever as rag
        from src.rag.embedder import HashingEmbedder, SentenceTransformerEmbedder
        from src.rag.retriever import Retriever, SearchOptions
        from src.rag.store import VectorStore
        from src.shared.config import get_settings
        from src.shared.db import get_assistant_engine

        from evaluation.corpus import corpus_folders, index_corpus, isolated_db, temp_dir

        stack = self._stack
        self.iso = stack.enter_context(isolated_db(get_assistant_engine()))
        chroma = stack.enter_context(temp_dir("tn_agent_chroma_"))

        embedder = (
            HashingEmbedder()
            if self.embedder_kind == "hashing"
            else SentenceTransformerEmbedder(
                self.config.get("embedding") or get_settings().embedding_model
            )
        )
        store = VectorStore(chroma, embedder.name)
        self.corpus_info = index_corpus(
            self.iso.factory,
            store,
            embedder,
            corpus_folders(self.config),
            max_tokens=get_settings().chunk_max_tokens,
        )
        retriever = Retriever(self.iso.factory, store, embedder, None, SearchOptions())
        original_get = rag.get_retriever
        rag.get_retriever = lambda: retriever
        stack.callback(setattr, rag, "get_retriever", original_get)

        # qlsv_api trong tiến trình; phiên CSDL do từng kịch bản cung cấp (_qlsv_session)
        common.qlsv.transport = httpx.ASGITransport(app=qlsv_app)
        stack.callback(setattr, common.qlsv, "transport", None)
        from src.shared.db import get_qlsv_session

        self._qlsv_session: Any = None

        def qlsv_session() -> Iterator[Any]:
            assert self._qlsv_session is not None, "chỉ gọi qlsv trong một kịch bản"
            yield self._qlsv_session

        qlsv_app.dependency_overrides[get_qlsv_session] = qlsv_session
        stack.callback(qlsv_app.dependency_overrides.pop, get_qlsv_session, None)

        mcp_client = McpClient(
            {
                "dao_tao": dao_tao.mcp,
                "ctsv": ctsv.mcp,
                "tai_chinh": tai_chinh.mcp,
                "quy_che": quy_che.mcp,
            }
        )
        self.registry = ToolRegistry(mcp_client)
        with self.iso.factory() as db:
            anyio.run(self.registry.sync, db)
            missing = [s for s, v in self.registry.server_status.items() if v not in ("ok", "tắt")]
            if missing:
                raise RuntimeError(f"MCP server lỗi: {self.registry.server_status}")
            if self.config.get("mo_ta_cong_cu") == "toi_gian":
                self.registry._specs = {n: minimal_spec(s) for n, s in self.registry._specs.items()}
            policies = self.registry.policies(db)
        self.write_tools = {
            n for n, p in policies.items() if p.can_xac_nhan or p.muc_rui_ro in ("ghi", "nhay_cam")
        }
        self.specs = dict(self.registry._specs)

        app = create_app(registry=self.registry, llm=self.llm, session_factory=self.iso.factory)

        def override_db() -> Iterator[Any]:
            # như backend/tests/assistant/conftest.py: kết thúc bằng commit (SQL Server không có
            # RELEASE SAVEPOINT) — mọi thứ vẫn nằm trong transaction ngoài cùng, rollback ở cuối
            with self.iso.factory() as session:
                yield session
                if session.in_transaction():
                    session.commit()

        app.dependency_overrides[get_db] = override_db
        self.client = stack.enter_context(TestClient(app))
        quiet_logs()
        self._tokens: dict[str, dict[str, str]] = {}
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stack.close()

    # -- tài khoản --
    def headers(self, ma_sv: str) -> dict[str, str]:
        from sqlalchemy import select
        from src.assistant_api.auth.security import create_access_token
        from src.assistant_api.models import NguoiDung

        if ma_sv not in self._tokens:
            with self.iso.factory() as db:
                user = db.scalar(select(NguoiDung).where(NguoiDung.ma_sv == ma_sv))
                if user is None:
                    user = NguoiDung(
                        ho_ten=f"Sinh viên {ma_sv}",
                        email=f"eval.{ma_sv.lower()}@tlhv.test",
                        mat_khau_hash="x",
                    )
                    db.add(user)
                user.vai_tro = "sinh_vien"
                user.ma_sv = ma_sv
                user.ma_khoa = ma_khoa_of(ma_sv)
                user.dang_hoat_dong = True
                db.commit()
                token, _ = create_access_token(user.id, "sinh_vien")
            self._tokens[ma_sv] = {"Authorization": f"Bearer {token}"}
        return self._tokens[ma_sv]

    # -- bật/tắt công cụ (trong transaction, khôi phục sau kịch bản) --
    @contextmanager
    def tools_disabled(self, names: list[str]) -> Iterator[None]:
        from sqlalchemy import select
        from src.assistant_api.models import CongCu

        if not names:
            yield
            return
        with self.iso.factory() as db:
            rows = list(db.scalars(select(CongCu).where(CongCu.ten.in_(names))))
            before = {r.ten: r.bat for r in rows}
            for r in rows:
                r.bat = False
            db.commit()
        try:
            yield
        finally:
            with self.iso.factory() as db:
                for r in db.scalars(select(CongCu).where(CongCu.ten.in_(names))):
                    r.bat = before[r.ten]
                db.commit()

    # -- LLM cho từng kịch bản --
    def use_llm(self, dry_steps: list[tuple[str, dict[str, Any]]], dry_text: str) -> None:
        from src.assistant_api.agent.llm import LiteLlm

        if self.dry_run:
            self.llm.inner = oracle_llm(dry_steps, dry_text)
        elif not isinstance(self.llm.inner, LiteLlm):
            self.llm.inner = LiteLlm(self.model)
        self.llm.reset()

    def fill_required(self, tool: str, args: dict[str, Any], question: str) -> dict[str, Any]:
        """Dry-run: điền tham số bắt buộc còn thiếu để công cụ chạy được."""
        spec = self.specs.get(tool)
        out = {k: v for k, v in args.items()}
        for name in (spec.input_schema.get("required") or []) if spec else []:
            if name in ("ma_sv", "ma_khoa") or name in out:
                continue
            out[name] = question if name == "cau_hoi" else DRY_RUN_DEFAULTS.get(name, "x")
        return out

    # -- chạy một lượt hỏi --
    def run(self, ma_sv: str, text: str, auto_confirm: bool) -> TurnResult:
        from sqlalchemy import select
        from src.assistant_api.models import LuotGoiCongCu, TinNhan
        from src.shared.db import get_qlsv_engine

        from evaluation.corpus import isolated_db

        headers = self.headers(ma_sv)
        events: list[str] = []
        pending: list[dict[str, Any]] = []
        confirmed = 0
        error = None
        started = time.perf_counter()
        with isolated_db(get_qlsv_engine()) as qlsv, qlsv.factory() as qlsv_db:
            self._qlsv_session = qlsv_db
            try:
                cid = self.client.post("/api/conversations", json={}, headers=headers).json()["id"]
                self.llm.start_timer()  # chỉ đo lượt gửi tin đầu tiên (không tính lượt xác nhận)
                r = self.client.post(
                    f"/api/conversations/{cid}/messages",
                    json={"noi_dung": text},
                    headers=headers,
                )
                self.llm.stop_timer()
                batch = parse_sse(r.text) if r.status_code == 200 else []
                if r.status_code != 200:
                    error = f"HTTP {r.status_code}: {r.text[:200]}"
                rounds = 0
                while batch and rounds < 3:
                    rounds += 1
                    events += [e for e, _ in batch]
                    error = error or next((d.get("detail") for e, d in batch if e == "error"), None)
                    cards = [d for e, d in batch if e == "pending_action"]
                    pending += cards
                    batch = []
                    if auto_confirm and cards:
                        card = cards[0]
                        rc = self.client.post(f"/api/actions/{card['ma']}/confirm", headers=headers)
                        if rc.status_code == 200:
                            confirmed += 1
                            batch = parse_sse(rc.text)
                        else:
                            error = error or f"Xác nhận lỗi HTTP {rc.status_code}: {rc.text[:200]}"
            finally:
                self._qlsv_session = None
        seconds = time.perf_counter() - started - self.llm.paced

        with self.iso.factory() as db:
            logs = db.scalars(
                select(LuotGoiCongCu)
                .where(LuotGoiCongCu.hoi_thoai_id == cid)
                .order_by(LuotGoiCongCu.id)
            ).all()
            calls = [
                {
                    "ten_cong_cu": g.ten_cong_cu,
                    "tham_so": g.tham_so,
                    "tham_so_llm": g.tham_so_llm,
                    "ket_qua": g.ket_qua,
                    "trang_thai": g.trang_thai,
                    "ly_do": g.ly_do,
                    "thoi_gian_ms": g.thoi_gian_ms,
                }
                for g in logs
            ]
            replies = db.scalars(
                select(TinNhan)
                .where(TinNhan.hoi_thoai_id == cid, TinNhan.vai_tro == "assistant")
                .order_by(TinNhan.id)
            ).all()
            texts = [m.noi_dung for m in replies if m.noi_dung]
            cited = next((m.trich_dan for m in reversed(replies) if m.trich_dan), None) or []
        return TurnResult(
            hoi_thoai_id=cid,
            answer="\n".join(texts),
            last_answer=texts[-1] if texts else "",
            citations=cited,
            calls=calls,
            events=events,
            pending=pending,
            confirmed=confirmed,
            steps=self.llm.steps,
            tokens_in=self.llm.tokens_in,
            tokens_out=self.llm.tokens_out,
            seconds=seconds,
            raw_answer=self.llm.texts[-1] if self.llm.texts else "",
            error=error,
            first_feedback_s=self.llm.first_feedback_s,
            ttft_s=self.llm.ttft_s,
        )

    def cost(self, tokens_in: int, tokens_out: int) -> float | None:
        if self.dry_run:
            return 0.0
        return cost_usd(self.model, tokens_in, tokens_out, self.config)


def usage_summary(results: list[TurnResult], harness: AgentHarness) -> dict[str, Any]:
    tin = sum(r.tokens_in for r in results)
    tout = sum(r.tokens_out for r in results)
    return {
        "token_vao": tin,
        "token_ra": tout,
        "chi_phi_usd": harness.cost(tin, tout),
        "buoc_tb": mean(r.steps for r in results),
    }
