# Thực nghiệm so sánh + TTFT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo thời gian đến phản hồi đầu tiên / chữ đầu tiên (NF-01) trong mọi lượt TN2/TN3, thêm bảng TN3 theo loại kịch bản, và chuẩn bị TN1 R5/R6 chạy được với mô hình trên ổ D.

**Architecture:** `MeteredLLM` (lớp bọc LLM của harness) ghi hai mốc thời gian, trừ thời gian giãn nhịp; `AgentHarness.run` chỉ bật đồng hồ trong lượt gửi tin đầu tiên. `run_agent.py` / `run_rag_answer.py` đưa hai mốc vào `chi_tiet.csv` và bảng tổng hợp qua một hàm chung `metrics.latency_summary`. Cache Hugging Face chuyển sang ổ D bằng biến môi trường người dùng `HF_HOME`.

**Tech Stack:** Python 3.11+, pytest, harness thực nghiệm trong `evaluation/`, LiteLLM (Gemini gói miễn phí), sentence-transformers.

**Spec:** `docs/superpowers/specs/2026-11-20-thuc-nghiem-so-sanh-ttft-design.md`

## Global Constraints
- Code tiếng Anh; tên cột/khóa kết quả và chuỗi hiển thị tiếng Việt (theo các cột hiện có, vd `thoi_gian_s`).
- `ruff check src tests scripts ../evaluation` sạch (chạy từ `backend/`).
- Không đổi ý nghĩa các cột cũ (`thoi_gian_s`, `do_tre_trung_vi_s`, …).
- TTFT trừ thời gian giãn nhịp (Pacer); chỉ đo lượt gửi tin đầu tiên, không tính lượt "Xác nhận".
- Ngưỡng NF-01: **5 giây**, chấm theo `ttft_s`.
- Không có chữ nào → `ttft_s = None` (ô trống), không tính vào trung vị/P95/tỉ lệ.
- `HF_HOME=D:\hf-cache` là thay đổi ngoài repo: **hỏi người dùng trước khi đặt**; chép (không di chuyển) cache e5 cũ.
- Lượt chạy Gemini thật: người dùng quyết thời điểm.

## Review Focus
1. LLM trả lời bằng chữ rồi mới gọi công cụ trong cùng một lượt → chữ đã gửi cho sinh viên, `ttft_s` lấy mốc chữ đó (test `test_text_before_tool_call_counts`).
2. Lượt xác nhận tự động sinh chữ trong khi lượt đầu chỉ tạo thẻ → `ttft_s` của kịch bản vẫn `None`, không lấy chữ của lượt xác nhận (test `test_stop_timer_ignores_later_text`).
3. Giãn nhịp xảy ra ở lần gọi LLM thứ hai (sau công cụ) → chỉ phần chờ trước mốc bị trừ (test `test_paced_wait_subtracted`).
4. Một cấu hình mọi câu đều không có chữ (vd lỗi hạn mức) → bảng in "—"/nan, không văng lỗi (test `test_latency_summary_empty`).
5. Kịch bản thiếu trường `loai` (bộ dữ liệu cũ / `--du-lieu` tự viết) → nhóm `khac`, không KeyError (test `test_summary_by_type_groups`).

---

### Task 1: Hai mốc thời gian trong harness

**Files:**
- Modify: `evaluation/harness.py` (`MeteredLLM`, `TurnResult`, `AgentHarness.run`)
- Test: `backend/tests/evaluation/test_timing.py` (mới), `backend/tests/evaluation/test_harness.py`

**Interfaces:**
- Produces:
  - `MeteredLLM(inner, clock: Callable[[], float] = time.perf_counter, pacer: Any = PACER)`
  - `MeteredLLM.start_timer() -> None`, `MeteredLLM.stop_timer() -> None`
  - thuộc tính `MeteredLLM.first_feedback_s: float | None`, `MeteredLLM.ttft_s: float | None` (giây, đã trừ giãn nhịp kể từ `start_timer`)
  - `TurnResult.first_feedback_s: float | None = None`, `TurnResult.ttft_s: float | None = None`

- [ ] **Step 1: Viết test** `test_timing.py` với clock giả (list thời điểm, inner giả là async generator tự tăng clock; pacer giả có `async await_turn() -> float` trả số giây cố định và tăng clock bằng đúng số đó):
  - `test_text_only`: inner yield "Xin" tại t=2.0 rồi `LlmTurn(text="Xin chào")` → `ttft_s == 2.0`, `first_feedback_s == 2.0`.
  - `test_tool_call_then_text`: lần stream 1 trả `LlmTurn(tool_calls=[...])` tại t=1.5; lần 2 yield "Kết" tại t=4.0 → `first_feedback_s == 1.5`, `ttft_s == 4.0`.
  - `test_text_before_tool_call_counts`: lần 1 yield "Để mình tra" tại t=1.0 rồi `LlmTurn(tool_calls=[...])` tại t=1.2 → `ttft_s == 1.0`, `first_feedback_s == 1.0`.
  - `test_paced_wait_subtracted`: pacer trả 3.0 ở lần gọi thứ 2; lần 1 tool call t=1.0; lần 2 chữ tại t=1.0+3.0+0.5 → `ttft_s == 1.5`.
  - `test_stop_timer_ignores_later_text`: lần 1 tool call; `stop_timer()`; lần 2 có chữ → `ttft_s is None`, `first_feedback_s` giữ giá trị lần 1.
  - `test_no_text_is_none`: chỉ `LlmTurn(text="")` → `ttft_s is None`.
  - `test_start_timer_resets`: gọi lại `start_timer()` xóa hai mốc cũ.
- [ ] **Step 2: Chạy** `pytest -q tests/evaluation/test_timing.py` (thư mục `backend/`). Expected: FAIL (`MeteredLLM` chưa nhận `clock`/`pacer`).
- [ ] **Step 3: Cài đặt** trong `MeteredLLM`: lưu `_t0`, `_paced0` khi `start_timer`; khi đồng hồ đang bật, mục `str` khác rỗng đầu tiên → `ttft_s` (và `first_feedback_s` nếu chưa có); `LlmTurn` có `tool_calls` đầu tiên → `first_feedback_s` nếu chưa có. Giá trị = `clock() - _t0 - (paced - _paced0)`. `reset()` không xóa đồng hồ (harness gọi `use_llm` trước `run`). `TurnResult` thêm 2 trường; `AgentHarness.run` gọi `start_timer()` ngay trước POST `/messages` và `stop_timer()` ngay sau khi nhận phản hồi đó, rồi điền 2 trường.
- [ ] **Step 4: Thêm test tích hợp** vào `test_harness.py`: `test_run_records_ttft_dry_run` — `use_llm([("register_course", {"ma_lop": "IT004.02"})], "Xong rồi em.")`, `run("SV22001", "Đăng ký lớp IT004.02", auto_confirm=True)` → `0 <= first_feedback_s <= ttft_s` (sau khi tạo thẻ, vòng lặp gọi LLM lần 2 ngay trong lượt đầu nên có chữ; lượt xác nhận không ảnh hưởng hai mốc).
- [ ] **Step 5: Chạy** `pytest -q tests/evaluation`. Expected: PASS toàn bộ.
- [ ] **Step 6: Commit** `git commit -m "Thực nghiệm: đo phản hồi đầu tiên và token đầu tiên (NF-01) trong harness"`

### Task 2: Báo cáo TTFT + bảng TN3 theo loại

**Files:**
- Modify: `evaluation/metrics.py`, `evaluation/run_agent.py`, `evaluation/run_rag_answer.py`
- Test: `backend/tests/evaluation/test_metrics.py`

**Interfaces:**
- Consumes: `TurnResult.first_feedback_s`, `TurnResult.ttft_s` (Task 1)
- Produces:
  - `metrics.latency_summary(values: Sequence[float | None], threshold: float = 5.0) -> dict[str, float]` với khóa `trung_vi`, `p95`, `ty_le_duoi_nguong` (bỏ `None`; rỗng → cả ba `nan`)
  - `run_agent.summarize_by_type(rows: list[dict]) -> list[dict]` (khóa `loai`, `cau_hinh`, `n`, `dung_cong_cu`, `dung_tham_so`, `hoan_thanh`, `ttft_trung_vi_s`)

- [ ] **Step 1: Viết test** trong `test_metrics.py`:
  - `test_latency_summary`: `[1.0, None, 3.0, 6.0]` → `trung_vi == 3.0`, `ty_le_duoi_nguong == 2/3`, `p95` = `metrics.percentile([1,3,6], 95)`.
  - `test_latency_summary_empty`: `[None]` → cả ba là `nan`.
  - `test_summary_by_type_groups`: 3 dòng (2 dòng `loai="chi_rag"` cấu hình `a`, 1 dòng không có `loai`) → nhóm `("chi_rag","a")` n=2 và `("khac","a")` n=1; sắp theo `loai` rồi `cau_hinh`.
- [ ] **Step 2: Chạy** `pytest -q tests/evaluation/test_metrics.py`. Expected: FAIL (hàm chưa có).
- [ ] **Step 3: Cài đặt:**
  - `run_agent.evaluate` thêm `loai` (`case.get("loai") or "khac"`), `phan_hoi_dau_s`, `ttft_s` (làm tròn 2 chữ số, `None` giữ nguyên).
  - `summarize` thêm `phan_hoi_dau_trung_vi_s`, `ttft_trung_vi_s`, `ttft_p95_s`, `ttft_duoi_5s`; `COLUMNS` thêm nhãn "Phản hồi đầu TV (s)", "TTFT TV (s)", "TTFT P95 (s)", "TTFT < 5 s" (`ttft_duoi_5s` vào tập phần trăm).
  - `main` ghi thêm `theo_loai.csv` và `bang_theo_loai.md` (tiêu đề "# TN3 — Theo loại kịch bản", cùng ghi chú CHẠY THỬ khi `--dry-run`).
  - `run_rag_answer.evaluate` thêm `phan_hoi_dau_s`, `ttft_s`; `summarize` mỗi nhóm thêm `ttft_trung_vi_s`, `ttft_duoi_5s`; `COLUMNS`/`PERCENT` tương ứng.
- [ ] **Step 4: Chạy** `pytest -q tests/evaluation`, rồi chạy khô: `python ../evaluation/run_agent.py --dry-run --configs agent_gemini agent_gemini_toi_gian --limit 6`. Expected: `bang.md` có 4 cột mới, `bang_theo_loai.md` tồn tại. Xóa thư mục kết quả chạy khô.
- [ ] **Step 5: Commit** `git commit -m "Thực nghiệm: cột TTFT trong TN2/TN3, bảng TN3 theo loại kịch bản"`

### Task 3: TN1 R5/R6 — mô hình trên ổ D

**Files:**
- Modify: `README.md` (mục cài đặt: ghi chú `HF_HOME`), `docs/09-danh-gia.md` (mục chạy TN1)
- Không đổi code.

- [ ] **Step 1: Hỏi người dùng** cho phép đặt biến môi trường người dùng `HF_HOME=D:\hf-cache` và chép cache. Không được phép → dừng task, ghi ruling.
- [ ] **Step 2:** Chép `%USERPROFILE%\.cache\huggingface\hub\models--intfloat--multilingual-e5-base` sang `D:\hf-cache\hub\`; `setx HF_HOME D:\hf-cache`. Expected: `python -c "from evaluation.common import model_cached; print(model_cached('intfloat/multilingual-e5-base'))"` với `HF_HOME` đặt trong phiên → `True`.
- [ ] **Step 3: Chạy** `python ../evaluation/run_rag_retrieval.py --configs R1 R2 R3 R4 R5 R6 --cho-phep-tai` (tải ~4,5 GB vào ổ D). Expected: bảng có đủ 6 dòng, không lỗi. Kết quả chỉ để kiểm tra (bộ 11 câu giả lập), không đưa vào khóa luận.
- [ ] **Step 4:** Ghi chú vào README và `docs/09`: cách đặt `HF_HOME`, dung lượng, lệnh chạy R5/R6 khi có PDF. Nhắc người dùng khởi động lại terminal/dịch vụ để nhận `HF_HOME`; bản cache cũ trên ổ C có thể xóa.
- [ ] **Step 5: Commit** `git commit -m "TN1: hướng dẫn đặt cache mô hình trên ổ D, kiểm tra R5/R6"`

### Task 4: Tài liệu phương pháp + chạy thật

**Files:**
- Modify: `docs/09-danh-gia.md`

- [ ] **Step 1:** `docs/09` thêm mục "Đo thời gian phản hồi (NF-01)":
  - định nghĩa 2 mốc;
  - trừ giãn nhịp;
  - không tính lượt xác nhận;
  - đo trong tiến trình (không tính mạng localhost → trình duyệt);
  - NF-01 chấm theo `ttft_s` < 5 s;
  - câu cần công cụ có TTFT dài hơn do chạy công cụ + gọi LLM lần 2, nên báo cả "phản hồi đầu tiên".
  Thêm mục "So sánh mô tả đầy đủ / tối giản" với lệnh chạy và cách đọc `bang_theo_loai.md`.
- [ ] **Step 2: Chạy** `pytest -q` và `ruff check src tests scripts ../evaluation` (từ `backend/`). Expected: PASS, sạch.
- [ ] **Step 3: Commit** `git commit -m "Tài liệu: phương pháp đo TTFT và so sánh mô tả công cụ"`
- [ ] **Step 4: (Khi người dùng cho phép, có hạn mức Gemini)** `python ../evaluation/run_agent.py --configs agent_gemini agent_gemini_toi_gian` (~450 lượt gọi; có thể chia `--limit`). Ghi kết quả chính + thư mục kết quả vào `docs/09`, commit `"TN3: kết quả mô tả đầy đủ / tối giản và TTFT (Gemini)"`.
