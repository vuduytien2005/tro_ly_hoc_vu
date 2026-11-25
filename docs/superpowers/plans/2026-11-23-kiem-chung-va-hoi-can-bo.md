# Kiểm chứng câu trả lời + Hỏi cán bộ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sau mỗi câu trả lời có tra cứu quy chế, một lượt LLM giám khảo chấm từng ý có/không có căn cứ (hiện trên giao diện, lưu CSDL); thêm công cụ MCP `ask_staff` để chuyển câu hỏi cho cán bộ trả lời qua trang "Đơn từ".

**Architecture:** `agent/verifier.py` (hàm thuần + 1 hàm async dùng giao diện `LLM` sẵn có) được `AgentRunner._finish` gọi; kết quả vào cột `tin_nhan.kiem_chung` và hai sự kiện SSE mới. Câu hỏi cán bộ là loại đơn `hoi_dap` trong `don_tu` (qlsv_api) với máy trạng thái riêng, tạo qua công cụ `ctsv.ask_staff` (cần xác nhận).

**Tech Stack:** FastAPI, SQLAlchemy 2, SQL Server, MCP SDK 2.x, LiteLLM, React + TS + vitest.

**Spec:** `docs/superpowers/specs/2026-11-23-kiem-chung-va-hoi-can-bo-design.md`

## Global Constraints
- Code tiếng Anh; chuỗi hiển thị tiếng Việt có dấu; bảng/cột tiếng Việt không dấu snake_case.
- Lỗi API dạng `{"detail": "...", "code": "MA_LOI"}`.
- Literal tiếng Việt trong SQL có tiền tố `N'...'`; JSON = `NVARCHAR(MAX)` + `CHECK (ISJSON(...)=1)`; model `JSON(none_as_null=True)`.
- Script nâng cấp `database/09_nang_cap_kiem_chung_hoi_dap.sql` chạy lại nhiều lần vẫn an toàn (kiểu 07/08), có cả phần `USE tlhv_qlsv` và `USE tlhv_assistant`; đồng thời sửa script tạo mới (01, 02, 04).
- `ma_sv` của `ask_staff` là tham số `[INJECTED]` (alias `MaSv` ở `mcp_servers/common.py`).
- KHÔNG sửa docstring/schema các công cụ MCP đã có (đổi → mã băm `ban_duyet` đổi → công cụ tự tắt).
- KHÔNG đụng các file phiên khác đang sửa: `assistant_api/auth/*`, `deps.py`, `routers/auth.py`, `web/src/lib/api.ts`, `web/src/lib/auth.tsx`. `shared/config.py`, `.env.example`, `docs/04`, `docs/10` đang bị sửa dở → chỉ THÊM khối mới bằng Edit, không ghi đè cả file.
- Không tự commit (CLAUDE.md: người dùng tự commit) — cuối mỗi task chỉ chạy test; gợi ý message ở cuối.
- Lệnh test chạy từ `backend/`: `.venv/Scripts/python -m pytest -q <path>`; web: `cd web; npx vitest run; npx tsc -b --noEmit`.

## Review Focus
1. Giám khảo trả JSON bọc trong ```json … ``` hoặc kèm chữ thừa → vẫn phải đọc được (test `test_parse_fenced_json`).
2. Giám khảo "trích" câu không có trong câu trả lời / số đoạn bịa → bị loại (test `test_drops_claims_not_in_answer`).
3. Giám khảo lỗi/hết giờ/hết phản hồi → câu trả lời vẫn lưu, không có sự kiện `verification`, vẫn `done` (test `test_verifier_failure_keeps_answer`).
4. Đơn `hoi_dap` chuyển `hoan_tat` với ghi chú toàn khoảng trắng → 422 `CAN_NOI_DUNG_TRA_LOI` (test `test_answer_requires_text`).
5. Ý không căn cứ chứa `[n]` hoặc ký tự markdown khi gạch chân trên web → không phá liên kết trích dẫn (test `markUnverified keeps citations`).

---

### Task 1: qlsv_api — loại đơn `hoi_dap` và máy trạng thái riêng

**Files:**
- Modify: `database/01_qlsv_schema.sql` (CHECK `chk_don_loai` thêm `N'hoi_dap'`)
- Create: `database/09_nang_cap_kiem_chung_hoi_dap.sql` (phần `USE tlhv_qlsv`: drop/add `chk_don_loai` nếu definition chưa có `hoi_dap`)
- Modify: `backend/src/qlsv_api/schemas.py` (`LoaiDon` + `QuestionContent` + `REQUEST_CONTENT_SCHEMAS`)
- Modify: `backend/src/qlsv_api/services/request_service.py` (`next_statuses`, `update_status`)
- Test: `backend/tests/qlsv/test_requests.py`

**Interfaces:**
- Produces: `loai_don="hoi_dap"`, `noi_dung={"cau_hoi": str, "phong_ban": "dao_tao"|"ctsv"|"tai_chinh"|"khac"}`; `QUESTION_NEXT_STATUSES = {"moi_tao": {"dang_xu_ly","hoan_tat","tu_choi"}, "dang_xu_ly": {"hoan_tat","tu_choi"}}`; `next_statuses(loai_don: str, current: str) -> set[str]`.

- [ ] **Step 1: Write failing tests** (dùng fixture/kiểu sẵn có trong file):
  - `test_create_question_request`: tạo `hoi_dap` với `{"cau_hoi": "Học bổng KKHT xét theo điểm học kỳ nào ạ?", "phong_ban": "ctsv"}` → 201/OK, `trang_thai == "moi_tao"`, không kiểm tra nợ học phí.
  - `test_question_can_be_answered_directly`: `moi_tao → hoan_tat` với ghi chú "Xét theo điểm HK gần nhất." → OK, `ghi_chu_xu_ly` lưu đúng.
  - `test_answer_requires_text`: `→ hoan_tat` với ghi chú `"   "` → 422 code `CAN_NOI_DUNG_TRA_LOI`.
  - `test_question_cannot_be_approved`: `moi_tao → da_duyet` → 409 `CHUYEN_TRANG_THAI_KHONG_HOP_LE`.
  - `test_question_content_validated`: `cau_hoi` rỗng → 422 `DU_LIEU_KHONG_HOP_LE`.
- [ ] **Step 2:** Run `pytest -q tests/qlsv/test_requests.py` → các test mới FAIL.
- [ ] **Step 3:** Implement. `QuestionContent(Schema)`: `cau_hoi: NonEmptyStr` (max 1000), `phong_ban: Literal[...] = "khac"`. `update_status` dùng `next_statuses(don.loai_don, don.trang_thai)`; với `hoi_dap` + `hoan_tat` thiếu ghi chú → `invalid("CAN_NOI_DUNG_TRA_LOI", "Cần nhập nội dung trả lời cho sinh viên.")`. Sửa SQL 01 + 09.
- [ ] **Step 4:** Run `pytest -q tests/qlsv` → PASS.

### Task 2: MCP `ctsv.ask_staff` + đăng ký công cụ ở assistant_api

**Files:**
- Modify: `backend/src/mcp_servers/ctsv.py` (`LOAI_DON["hoi_dap"]`, tool `ask_staff`, `version="0.7.0"`, câu `instructions` thêm "câu hỏi gửi cán bộ")
- Modify: `database/04_assistant_seed.sql` + `database/09_…sql` (phần `USE tlhv_assistant`: INSERT `ask_staff` kiểu 07: `N'Gửi câu hỏi cho cán bộ phòng ban'`, `N'ghi'`, `can_xac_nhan=1`)
- Modify: `backend/src/assistant_api/agent/actions.py` (`describe`), `agent/prompts.py` (`TOOL_LABELS`, một nguyên tắc trong `SYSTEM_PROMPT`)
- Modify: `backend/tests/test_db.py:65` (18 → 19)
- Test: `backend/tests/mcp/test_tai_chinh_ctsv.py`, `backend/tests/assistant/test_actions.py`

**Interfaces:**
- Produces: tool `ask_staff(ma_sv: MaSv, cau_hoi: str (10–1000), phong_ban: Literal["dao_tao","ctsv","tai_chinh","khac"]="khac") -> dict` trả như `_create_request` (`thanh_cong, ma_don, loai_don, trang_thai, thong_bao`). `PHONG_BAN = {"dao_tao": "Phòng Đào tạo", "ctsv": "Phòng Công tác sinh viên", "tai_chinh": "Phòng Kế hoạch – Tài chính", "khac": "cán bộ phụ trách"}` (đặt trong ctsv.py, actions.py import từ đây hoặc chép — chọn import nếu không tạo vòng phụ thuộc; không thì chép).
- Mô tả thẻ: `f"Gửi câu hỏi tới {PHONG_BAN[phong_ban]}: \"{_short(cau_hoi)}\""`. Nhãn: `"ask_staff": "Đang gửi câu hỏi cho cán bộ"`.
- Nguyên tắc prompt (chép nguyên): `- Văn bản không có căn cứ để trả lời, hoặc sinh viên muốn hỏi trực tiếp cán bộ: đề nghị gửi câu hỏi cho phòng ban phụ trách; sinh viên đồng ý thì gọi ask_staff với câu hỏi viết lại đầy đủ, tự hiểu được (cán bộ không xem được cuộc trò chuyện).`

- [ ] **Step 1: Failing tests:** `test_ask_staff_creates_question` (respx mock `POST /internal/students/SV22001/requests` kiểm tra body `{"loai_don": "hoi_dap", "noi_dung": {"cau_hoi": ..., "phong_ban": "ctsv"}, "tao_boi": "tro_ly_ai"}`, kết quả `loai_don == "Câu hỏi gửi cán bộ"`); `test_ask_staff_hides_ma_sv` (input schema không có `ma_sv`); `test_describe_ask_staff` trong test_actions → chuỗi bắt đầu `"Gửi câu hỏi tới Phòng Công tác sinh viên:"`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement (docstring tool: khi nào dùng, viết lại câu hỏi tự đứng được, cần sinh viên xác nhận).
- [ ] **Step 4:** Run `pytest -q tests/mcp tests/assistant/test_actions.py tests/assistant/test_registry.py tests/test_db.py` → PASS (test_db cần chạy lại 04 trên máy dev; nếu CSDL dev chưa nâng cấp, ghi chú cho người dùng chạy 09).

### Task 3: Nhắc việc — câu hỏi đã được trả lời

**Files:** Modify `backend/src/assistant_api/reminders.py` (`_requests`); Test `backend/tests/assistant/test_reminders.py`.

- [ ] **Step 1:** `test_answered_question_is_reminded`: `{"ma_don": "DT-9", "loai_don": "Câu hỏi gửi cán bộ", "ma_loai_don": "hoi_dap", "ma_trang_thai": "hoan_tat", "ngay_cap_nhat": "2026-11-22", ...}` → `tieu_de == "Câu hỏi của em đã được cán bộ trả lời"`, `muc_do == "sap_toi"`, `cau_hoi == "Cán bộ trả lời câu hỏi DT-9 của em thế nào?"`.
- [ ] **Step 2:** FAIL. **Step 3:** `list_my_requests` (ctsv.py) trả thêm khóa `ma_loai_don` (KHÔNG đổi docstring/schema đầu vào — chỉ đổi dữ liệu trả về); `_requests` nhánh riêng khi `d.get("ma_loai_don") == "hoi_dap"`. **Step 4:** `pytest -q tests/assistant/test_reminders.py tests/mcp` → PASS.

### Task 4: Web — `hoi_dap` ở "Đơn từ" và "Thủ tục của em"

**Files:** Modify `web/src/lib/admin.ts`, `web/src/lib/adminTypes.ts` (nhãn loại `hoi_dap: 'Câu hỏi cán bộ'`), `web/src/pages/admin/RequestsPage.tsx`, `web/src/pages/ProceduresPage.tsx`; Test `web/src/lib/review.test.ts`.

**Interfaces:** `nextStatuses(current: string, loai?: string): string[]`; `reviewNoteProblem(target: string, note: string, loai?: string): string | null`.

- [ ] **Step 1:** Tests: `nextStatuses('moi_tao', 'hoi_dap')` → `['dang_xu_ly', 'hoan_tat', 'tu_choi']`; `nextStatuses('da_duyet','hoi_dap')` → `[]`; `reviewNoteProblem('hoan_tat', ' ', 'hoi_dap')` khác null; `reviewNoteProblem('hoan_tat', ' ')` (đơn thường) null; test cũ giữ nguyên.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; RequestsPage: với `hoi_dap` nút `hoan_tat` ghi "Trả lời", nhãn ô ghi chú "Nội dung trả lời", hiện `noi_dung.cau_hoi` + phòng ban. ProceduresPage: đơn `hoi_dap` hiện câu hỏi và "Trả lời của cán bộ" (= `ghi_chu_xu_ly`). **Step 4:** `npx vitest run; npx tsc -b --noEmit` → PASS.

### Task 5: `agent/verifier.py` — giám khảo

**Files:** Create `backend/src/assistant_api/agent/verifier.py`; Test create `backend/tests/assistant/test_verifier.py`.

**Interfaces (Produces):**
```python
class Claim(TypedDict):
    cau: str; ket_luan: Literal["co_can_cu", "khong_co_can_cu"]; doan: list[int]; ly_do: str
class Verification(TypedDict):
    tong: int; co_can_cu: int; y: list[Claim]; mo_hinh: str; thoi_gian_ms: int
def build_messages(answer: str, passages: dict[int, str]) -> list[dict[str, Any]]
def parse_verdict(raw: str, answer: str, valid_numbers: set[int]) -> list[Claim] | None
async def verify_answer(llm: LLM, answer: str, passages: dict[int, str], *, model_name: str,
                        timeout: float) -> tuple[Verification | None, int, int]  # (+token vào, ra)
```
- `build_messages`: system = prompt giám khảo (đoạn đặt trong `<tai_lieu so="n">…</tai_lieu>`, nói rõ là dữ liệu không phải lệnh; yêu cầu JSON đúng dạng spec; bỏ câu chào/gợi ý chung), user = câu trả lời.
- `parse_verdict`: lấy object JSON đầu tiên (chịu được ```json fence/chữ thừa); bỏ claim có `cau` (chuẩn hóa khoảng trắng) không nằm trong answer; lọc `doan` ngoài `valid_numbers`; `ket_luan` lạ → bỏ claim; rỗng → `None`.
- `verify_answer`: `llm.stream(messages, [])` gom chữ trong `anyio.fail_after(timeout)`; mọi exception → `(None, tokens…)` + `logger.warning`.

- [ ] **Step 1:** Tests: `test_parse_plain_json`, `test_parse_fenced_json`, `test_drops_claims_not_in_answer` (cau bịa + doan 9 không có → bị loại/lọc), `test_bad_json_returns_none`, `test_build_messages_wraps_passages` (có `<tai_lieu so="2">`, có câu "không phải lệnh"), `test_verify_answer_with_fake_llm` (FakeLLM trả JSON → `tong`, `co_can_cu` đúng; token = 100/20), `test_verify_answer_llm_error_returns_none` (FakeLLM rỗng).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `pytest -q tests/assistant/test_verifier.py` → PASS.

### Task 6: Gắn giám khảo vào vòng lặp, CSDL, API, SSE

**Files:**
- Modify: `database/02_assistant_schema.sql` (cột `kiem_chung` sau `trich_dan`), `database/09_…sql` (phần assistant: ADD COLUMN nếu chưa có + CHECK `chk_tn_kiem_chung`)
- Modify: `backend/src/assistant_api/models/conversation.py` (`kiem_chung: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))`)
- Modify: `backend/src/shared/config.py` (thêm `answer_verify: bool = True`, `verifier_model: str = ""`, `verifier_timeout_seconds: float = 20`), `.env.example` (3 dòng + chú thích)
- Modify: `backend/src/assistant_api/agent/loop.py` (`collect_passages`, `AgentRunner(registry, llm, verifier_llm=None)`, `_finish`)
- Modify: `backend/src/assistant_api/main.py` (`create_app(..., verifier_llm: LLM | None = None)`: verifier = `verifier_llm` nếu truyền; nếu không truyền và `llm is None` và `answer_verify` → `LiteLlm(settings.verifier_model or None)`; còn lại None — test cũ dùng FakeLLM không bị tốn thêm phản hồi)
- Modify: `backend/src/assistant_api/schemas.py` (`MessageOut.kiem_chung`), `routers/conversations.py:146` (trả `kiem_chung`)
- Test: `backend/tests/assistant/test_agent_loop.py` (+ fixture tạo app có `verifier_llm` FakeLLM riêng trong conftest)

**Interfaces:** `collect_passages(result: Any) -> dict[int, str]` (toàn văn theo `so`); SSE `verifying` `{}` và `verification` = `Verification`; thứ tự `citations → verifying → verification → done`.

- [ ] **Step 1:** Tests: `test_answer_is_verified_and_saved` (có search → events chứa `verifying`, `verification` trước `done`; `TinNhan.kiem_chung["tong"] == 2`; `so_token_vao == 200 + 100`); `test_no_verification_without_search` (câu trả lời không tra cứu → không có `verifying`); `test_verifier_failure_keeps_answer` (verifier FakeLLM hết phản hồi → không có `verification`, có `done`, tin nhắn lưu, `kiem_chung is None`); `test_messages_api_returns_kiem_chung`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; giám khảo chạy SAU khi lưu tin nhắn (commit) và sau `citations`; cập nhật `kiem_chung` + token rồi commit. Bỏ qua khi text ∈ {TOO_COMPLEX, REFUSED, EMPTY}. **Step 4:** `pytest -q tests/assistant` → PASS (toàn bộ, để chắc test cũ không đổi).

### Task 7: Web — hiển thị kiểm chứng + nút "Hỏi cán bộ"

**Files:** Create `web/src/lib/verification.ts` + `web/src/lib/verification.test.ts`; Modify `web/src/lib/types.ts` (`Verification`, `Message.kiem_chung`, 2 sự kiện SSE), `web/src/components/chat/Answer.tsx`, `web/src/pages/ChatPage.tsx`.

**Interfaces:** `markUnverified(text: string, v: Verification | null | undefined): string` — biến mỗi ý `khong_co_can_cu` thành `[<đoạn>](#unverified-<i>)` chỉ trên phần chữ KHÔNG chứa `[n]` (cắt bỏ trích dẫn khỏi `cau` trước khi tìm; không tìm thấy → bỏ qua); áp dụng TRƯỚC `linkCitations`. `verificationSummary(v): { label: string; ok: boolean }` → `"Đã kiểm chứng 4/5 ý với văn bản"`.

- [ ] **Step 1:** Tests vitest: `markUnverified` gạch đúng một ý; `keeps citations` (ý có `[2]` ở cuối → `[2]` vẫn còn nguyên ngoài liên kết); ý không có trong text → text không đổi; `verificationSummary` ok khi đủ.
- [ ] **Step 2:** FAIL. **Step 3:** Implement: `Answer.tsx` render `#unverified-i` thành `<span>` gạch chân chấm vàng, `title` = `ly_do`; dưới câu trả lời: "Đang kiểm chứng với văn bản…" khi đã nhận `verifying` chưa nhận kết quả; nhãn tóm tắt; nếu có ý không căn cứ → nút "Hỏi cán bộ" điền ô chat `"Mình muốn gửi câu hỏi này cho cán bộ phòng ban phụ trách."` (dùng cách điền sẵn mà chuông nhắc việc đang dùng — `ChatPrefillState`). **Step 4:** `npx vitest run; npx tsc -b --noEmit` → PASS.

### Task 8: Thực nghiệm + tài liệu

**Files:** Create `evaluation/run_verifier.py`, `evaluation/datasets/verifier_cases.jsonl` (25–35 ca); Modify `docs/09-danh-gia.md`, `docs/chuong-4-thuc-nghiem.md`, `docs/03-co-so-du-lieu.md`, `docs/04-api.md`, `docs/05-mcp-servers.md`, `docs/08-giao-dien.md`, `docs/10-ra-soat-bao-mat.md`, `CLAUDE.md` (ctsv có `ask_staff`), `README.md` (chạy script 09).

- Dòng jsonl: `{"id": "V01", "cau_hoi": ..., "doan": {"1": "...", "2": "..."}, "tra_loi_dung": ..., "tra_loi_sai": ..., "y_sai": "<câu bị cài sai, nguyên văn trong tra_loi_sai>"}` — đoạn lấy từ corpus thật (`evaluation/corpus_demo`).
- `run_verifier.py`: với mỗi ca gọi `verify_answer` trên cả hai câu trả lời; đo **recall** (ý sai bị gắn `khong_co_can_cu`), **báo nhầm** (tỷ lệ câu đúng có ít nhất 1 ý bị gắn không căn cứ), độ trễ trung bình, token thêm; ghi `evaluation/results/verifier_<model>_<ngày>.json` + in bảng; `--dry-run` chạy 2 ca với FakeLLM.
- [ ] **Step 1:** `python -m evaluation.run_verifier --dry-run` chạy không lỗi. **Step 2:** Cập nhật docs (mục mới "TN5 — Kiểm chứng câu trả lời" ở docs/09 và chương 4: mục đích, cách đo, bảng kết quả để trống chờ chạy thật). **Step 3:** `ruff check src ../evaluation` sạch.

---
**Gợi ý message commit (người dùng tự commit):**
1. `QLSV + MCP ctsv: câu hỏi gửi cán bộ (hoi_dap, ask_staff) + nhắc việc khi được trả lời`
2. `Trợ lý: kiểm chứng câu trả lời quy chế bằng LLM giám khảo (tin_nhan.kiem_chung, SSE verification)`
3. `Web: gạch chân ý chưa có căn cứ, nút Hỏi cán bộ, trả lời câu hỏi ở trang Đơn từ`
4. `Thực nghiệm TN5: kiểm chứng câu trả lời + tài liệu`
