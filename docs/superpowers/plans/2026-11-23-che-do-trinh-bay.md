# Chế độ trình bày — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bảng "Bên trong Agent" cạnh khung chat, đọc từ nhật ký `luot_goi_cong_cu`, kèm câu hỏi soạn sẵn, Nhật ký tự cập nhật và nút phóng chữ, phục vụ demo trước hội đồng.

**Architecture:** Backend thêm `GET /api/conversations/{id}/trace`, chỉ bật khi `CHE_DO_TRINH_BAY=true`; `/health` báo cờ này. Web thêm `TracePanel` dùng TanStack Query (`['trace', id]`), được `invalidate` khi luồng SSE báo `tool_end` / `pending_action` / `done` và khi xác nhận hoặc hủy thẻ. Không sửa vòng lặp Agent.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, pydantic-settings, pytest; React 18 + TypeScript + TailwindCSS + TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-11-23-che-do-trinh-bay-design.md`

## Global Constraints
- Không sửa `backend/src/assistant_api/agent/loop.py`.
- Lỗi API theo dạng `{"detail": "<tiếng Việt>", "code": "<MA_LOI>"}`. Mã khi tắt chế độ: `KHONG_BAT_CHE_DO_TRINH_BAY` (HTTP 404).
- Trace của hội thoại người khác → 404 `KHONG_TIM_THAY_HOI_THOAI` (dùng `own_conversation`).
- Trace **không** trả `ket_qua`.
- Cấu hình chỉ đọc qua `src/shared/config.py`: `che_do_trinh_bay: bool = False`.
- Khóa `localStorage`: `tlhv_trinh_bay` (`"1"`/`"0"`), `tlhv_co_chu` (`"100"|"115"|"130"`).
- Nhật ký tự cập nhật: `refetchInterval` 3000 ms.
- Chuỗi hiển thị tiếng Việt, code tiếng Anh. `ruff`, `pytest -q`, `npm run build`, `npx vitest run` đều sạch.

## Review Focus
1. LLM tự gửi `ma_sv` khác (bị ghi đè) → trace phải hiện cả giá trị LLM gửi lẫn giá trị hệ thống điền. Test: `test_trace_shows_override`.
2. Lượt hệ thống tự gọi (`tham_so_llm` NULL, vd `chi_kiem_tra`) → `tham_so_he_thong_dien` không được liệt kê mọi tham số như "hệ thống điền". Test: `test_trace_system_call_has_null_llm_args`.
3. Thẻ chờ xác nhận được bấm → đọc lại trace thì cùng `id` đổi trạng thái `cho_xac_nhan` → `thanh_cong`, không sinh dòng trùng trong panel. Test: `test_trace_after_confirm_updates_status`.
4. Trace lỗi (mạng, 404 do tắt cờ giữa chừng) → panel hiện một dòng lỗi nhỏ, chat vẫn hoạt động. Test vitest `traceLines` không áp dụng; kiểm tra thủ công ở Task 3 bước cuối.
5. Hội thoại mới chưa có id (trang `/chat` trống) → panel hiện "Chưa có bước nào", không gọi API. Đặt `enabled: conversationId != null` (Task 2).

---

### Task 1: Backend — cờ cấu hình, API trace, `/health`

**Files:**
- Modify: `backend/src/shared/config.py`, `backend/src/assistant_api/routers/conversations.py`, `backend/src/assistant_api/schemas.py` (hoặc file schema chứa `MessagesOut`), `backend/src/assistant_api/main.py` (`/health`), `.env.example`, `README.md`, `docs/04-api.md`
- Test: `backend/tests/assistant/test_trace.py` (mới)

**Interfaces:**
- Produces:
  - `Settings.che_do_trinh_bay: bool = False`.
  - `GET /api/conversations/{conversation_id}/trace` → `TraceOut { luot_goi: list[TraceStepOut] }`.
  - `TraceStepOut`: `id: int`, `thoi_diem: datetime`, `ten_cong_cu: str`, `nhan: str`, `mcp_server: str`, `tham_so_llm: dict | None`, `tham_so_he_thong_dien: dict`, `trang_thai: str`, `ly_do: str | None`, `thoi_gian_ms: int | None`.
  - Hàm thuần `system_filled(tham_so: dict, tham_so_llm: dict | None) -> dict` trong `conversations.py`. Trả các khóa của `tham_so` mà không có trong `tham_so_llm` hoặc khác giá trị (`!=`). Khi `tham_so_llm is None`, chỉ trả các khóa thuộc `HIDDEN_PARAMS` của registry.
  - `nhan` = `tool_label(name, registry.title(name))`, bỏ tiền tố `"Đang "` / `"Đang dùng: "` rồi viết hoa chữ đầu. Có thể dùng `paused_label` trong `prompts.py` nếu nó cho ra đúng chuỗi.
  - `/health` thêm khóa `"che_do_trinh_bay": bool`.

- [ ] **Step 1: Viết test** `test_trace.py`. Dùng fixture `client`, `student`, `other_student`, `script` của `tests/assistant/conftest.py`. Bật cờ bằng `monkeypatch.setattr(get_settings(), "che_do_trinh_bay", True)`.
  - `test_trace_disabled_404`: cờ tắt → `GET .../trace` 404, `code == "KHONG_BAT_CHE_DO_TRINH_BAY"`.
  - `test_trace_lists_calls_with_injected_ma_sv`: `script(FakeResponse(tool_calls=[("get_transcript", {})]), FakeResponse(text="Đây."))`, chat → một bước, `ten_cong_cu == "get_transcript"`, `tham_so_he_thong_dien == {"ma_sv": <ma_sv của student>}`, `"ket_qua" not in step`, `trang_thai == "thanh_cong"`.
  - `test_trace_shows_override`: LLM gửi `{"ma_sv": "SV99999"}` → `tham_so_llm["ma_sv"] == "SV99999"`, `tham_so_he_thong_dien["ma_sv"]` là mã của student.
  - `test_trace_system_call_has_null_llm_args`: unit test `system_filled({"ma_sv": "SV1", "ma_lop": "X", "chi_kiem_tra": True}, None) == {"ma_sv": "SV1", "chi_kiem_tra": True}`.
  - `test_trace_after_confirm_updates_status`: LLM gọi `register_course {"ma_lop": "IT004.02"}`. Trace có bước `cho_xac_nhan`. `POST /api/actions/{ma}/confirm`, rồi trace lại: bước cùng `id` có `trang_thai` khác `cho_xac_nhan`, số bước `register_course` có `tham_so_llm` khác null không tăng. Theo mẫu các test xác nhận có sẵn ở `test_actions.py`, kể cả `qlsv_mock` nếu cần.
  - `test_trace_other_student_404`: cờ bật, SV khác gọi → 404 `KHONG_TIM_THAY_HOI_THOAI`.
  - `test_health_reports_presentation_flag`: `/health` có `che_do_trinh_bay` là bool.
- [ ] **Step 2: Chạy** `pytest -q tests/assistant/test_trace.py` (từ `backend/`). Expected: FAIL.
- [ ] **Step 3: Cài đặt** theo Interfaces. Endpoint kiểm cờ trước khi kiểm quyền sở hữu, dùng dependency `Student` như các route khác, sắp theo `LuotGoiCongCu.id`. `thoi_diem` lấy `created_at`. Registry lấy từ `request.app.state.registry`.
- [ ] **Step 4: Chạy** `pytest -q` và `ruff check src tests scripts ../evaluation`. Expected: PASS, sạch.
- [ ] **Step 5: Tài liệu:**
  - `.env.example`: `CHE_DO_TRINH_BAY=false`, kèm chú thích "true chỉ khi demo";
  - `README.md`: mục biến môi trường;
  - `docs/04-api.md`: API trace + trường `/health`.
- [ ] **Step 6: Commit** `git commit -m "Trợ lý: API trace lượt gọi công cụ cho chế độ trình bày (mặc định tắt)"`

### Task 2: Web — chế độ trình bày trên trang chat

**Files:**
- Create: `web/src/lib/presentation.ts`, `web/src/lib/presentation.test.ts`, `web/src/lib/demoPrompts.ts`, `web/src/components/chat/TracePanel.tsx`
- Modify: `web/src/lib/types.ts`, `web/src/lib/health.ts` (`HealthResponse.che_do_trinh_bay?: boolean`), `web/src/pages/ChatPage.tsx`, `web/src/components/chat/Composer.tsx` (cho phép điền chữ từ ngoài), `web/src/index.css` (hiệu ứng nổi bật, nếu cần)

**Interfaces:**
- Consumes: API trace và `/health.che_do_trinh_bay` (Task 1).
- Produces:
  - `types.ts`: `TraceStep`, `TraceResponse { luot_goi: TraceStep[] }` khớp `TraceStepOut`.
  - `presentation.ts`:
    - `usePresentationMode(): [boolean, (on: boolean) => void]` (khóa `tlhv_trinh_bay`);
    - `useFontScale(): [FontScale, (s: FontScale) => void]` với `type FontScale = 100 | 115 | 130`. Hook đặt `document.documentElement.style.fontSize = \`${s}%\`` (khóa `tlhv_co_chu`);
    - `traceLines(step: TraceStep): { llm: string | null; system: { key: string; value: string; overridden?: string }[] }`. `llm` là `"ma_lop=IT004.02, thu=2"` hoặc `null` khi hệ thống tự gọi. `overridden` là giá trị LLM gửi khi khác giá trị hệ thống điền.
  - `demoPrompts.ts`: `DEMO_PROMPTS: { label: string; text: string }[]`, nguyên văn câu trong `docs/kich-ban-demo.md`:
    - `Em bị F môn Cơ sở dữ liệu thì có phải học lại không?`
    - `Đăng ký giúp em lớp học lại Cơ sở dữ liệu vào thứ 2`
    - `Đăng ký thêm SE105.02`
    - `Cho em xem điểm của SV22002`
    - `Gia hạn giúp em cuốn sách sắp hết hạn`
    - `Em còn thiếu gì để tốt nghiệp?`
    - `Lập kế hoạch học kỳ tới rồi đăng ký cả gói giúp em.`
    
    Đầu file chú thích "giữ khớp backend/scripts/demo_check.py".
  - `TracePanel({ conversationId }: { conversationId: number | null })`.

- [ ] **Step 1: Viết test** `presentation.test.ts`:
  - `traceLines` với `tham_so_llm={ma_lop:"IT004.02"}`, `tham_so_he_thong_dien={ma_sv:"SV22001"}` → `llm === "ma_lop=IT004.02"`, `system` là `[{key:"ma_sv", value:"SV22001"}]`;
  - LLM gửi `ma_sv:"SV22002"` → `system[0].overridden === "SV22002"`;
  - `tham_so_llm=null` → `llm === null`;
  - giá trị mảng `["IT004.02","SE201.01"]` hiển thị `"IT004.02, SE201.01"`.
- [ ] **Step 2: Chạy** `npx vitest run src/lib/presentation.test.ts` (từ `web/`). Expected: FAIL.
- [ ] **Step 3: Cài đặt** `presentation.ts`, `demoPrompts.ts`, `TracePanel`, rồi gắn vào `ChatPage`:
  - Chỉ hiện công tắc "Chế độ trình bày" và nút A−/A+ khi `/health.che_do_trinh_bay` true. Dùng chung query `/health` mà `StatusBanner` đang dùng, cùng `queryKey`.
  - Bật thì bố cục chat chia hai cột: panel ở bên phải, rộng `w-[360px]`; dưới breakpoint `lg` thì panel xếp xuống dưới.
  - Gọi `queryClient.invalidateQueries({ queryKey: ['trace', conversationId] })` ở các nhánh `tool_end`, `pending_action`, `done` của trình xử lý SSE, và sau khi xác nhận hoặc hủy thẻ.
  - Thẻ trong panel gồm:
    - số thứ tự;
    - `nhan`, kèm `ten_cong_cu` chữ nhỏ;
    - huy hiệu trạng thái, dùng cùng màu với `AuditPage`;
    - dòng "LLM gửi: …";
    - dòng nền vàng "🔒 Hệ thống điền: ma_sv=SV22001". Khi bị ghi đè thì ghi "LLM gửi SV22002 → hệ thống ghi đè SV22001";
    - `ly_do` màu đỏ nếu `bi_tu_choi`;
    - `null` thì ghi "Hệ thống tự gọi (kiểm tra trước khi tạo thẻ)".
  - Thẻ mới (id chưa thấy) có class nổi bật khoảng 1 giây.
  - Chân panel ghi: "Bảng này đọc trực tiếp từ nhật ký hệ thống (luot_goi_cong_cu)."
  - Trace lỗi thì hiện "Không tải được nhật ký" chữ nhỏ.
  - Hàng nút `DEMO_PROMPTS` đặt phía trên `Composer`, chỉ hiện khi bật chế độ. Bấm nút thì điền chữ vào ô nhập, không gửi.
- [ ] **Step 4: Chạy** `npx vitest run` và `npm run build`. Expected: PASS, build không lỗi kiểu.
- [ ] **Step 5: Commit** `git commit -m "Web: chế độ trình bày — bảng Bên trong Agent, câu hỏi soạn sẵn, phóng chữ"`

### Task 3: Web — Nhật ký tự cập nhật, phóng chữ trang quản trị; tài liệu demo

**Files:**
- Modify: `web/src/pages/admin/AuditPage.tsx`, `web/src/components/AdminLayout.tsx`, `docs/08-giao-dien.md`, `docs/kich-ban-demo.md`, `docs/10-ra-soat-bao-mat.md`

**Interfaces:**
- Consumes: `useFontScale` (Task 2).

- [ ] **Step 1: Cài đặt:**
  - `AuditPage` thêm công tắc "Tự cập nhật". Khi bật, query danh sách dùng `refetchInterval: 3000`; dòng có `id` mới so với lần trước có class nổi bật khoảng 1 giây. Mặc định tắt.
  - `AdminLayout` thêm nút A−/A+ dùng `useFontScale`. Nút này luôn hiện, vì đây là trang quản trị.
- [ ] **Step 2: Tài liệu:**
  - `docs/08`: mục "Chế độ trình bày".
  - `docs/kich-ban-demo.md`:
    - mục 2: cửa sổ A bật chế độ trình bày, câu hỏi bấm từ hàng nút, Notepad giữ làm dự phòng;
    - bước 2: lời thoại chỉ vào dòng "🔒 Hệ thống điền" trước khi bấm Xác nhận;
    - bước 4: nếu panel có dòng "ghi đè" thì chỉ vào đó;
    - bước 6: bật "Tự cập nhật", bỏ F5;
    - checklist: `.env` đặt `CHE_DO_TRINH_BAY=true`, sau buổi bảo vệ đặt lại `false`;
    - sự cố: panel không tải được thì tắt công tắc và làm tiếp như cũ.
  - `docs/10`: một dòng về chế độ trình bày (mặc định tắt; chỉ chủ hội thoại; không trả kết quả công cụ).
- [ ] **Step 3: Kiểm tra:**
  - `npm run build`, `npx vitest run`, rồi `pytest -q` (backend).
  - Thủ công: `CHE_DO_TRINH_BAY=true`, chạy `run_all.ps1` + `npm run dev`, làm bước 2 demo. Panel hiện bước `register_course` "chờ xác nhận" kèm "🔒 Hệ thống điền: ma_sv=SV22001" trước khi bấm Xác nhận, sau khi bấm thì chuyển "thành công".
  - Đặt lại cờ `false`: công tắc biến mất, `demo_check.py` (không `--llm`) đạt.
- [ ] **Step 4: Commit** `git commit -m "Web: Nhật ký tự cập nhật, phóng chữ trang quản trị; kịch bản demo dùng chế độ trình bày"`
