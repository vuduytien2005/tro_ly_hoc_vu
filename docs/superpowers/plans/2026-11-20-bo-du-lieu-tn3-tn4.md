# Bộ dữ liệu TN3/TN4 — kế hoạch thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Mở rộng `agent_scenarios.jsonl` lên ~72 kịch bản và `security_cases.jsonl` lên ~49 ca, đáp án được máy đối chiếu với dữ liệu QLSV mẫu.
**Architecture:** Chỉ dữ liệu (jsonl + văn bản độc hại) và tài liệu; không sửa code. Kiểm bằng script tạm ở scratchpad dùng `AgentHarness` (dry-run, LLM giả gọi đúng công cụ mong đợi, QLSV rollback).
**Tech Stack:** jsonl, `evaluation/harness.py`, `evaluation/metrics.py`.
**Spec:** `docs/superpowers/specs/2026-11-20-bo-du-lieu-tn3-tn4-design.md`

## Global Constraints
- Không sửa `database/03_qlsv_seed.sql`, `harness.py`, `run_*.py`, `metrics.py`.
- Giữ nguyên 23 dòng cũ (A001–A012, S001–S011), dòng mới đánh số tiếp (A013…, S012…).
- `DEMO_NOW=2026-11-20T09:00:00+07:00`: học kỳ hiện tại 2026-2027-HK1, đang mở đăng ký 2026-2027-HK2, học kỳ kết thúc gần nhất 2025-2026-HK2.
- Không ghi bí mật (token, khóa API) vào jsonl.
- Trường mới: `loai` (TN3), `can_kiem_tra` (chuỗi, dòng cần người dùng đối chiếu văn bản).

## Review Focus
1. Kịch bản đọc có `ket_qua_mong_doi` là chuỗi: dry-run luôn đạt (LLM giả nói đúng chuỗi) → phải kiểm riêng chuỗi có trong kết quả công cụ.
2. Mã lỗi phụ thuộc thứ tự 9 bước kiểm tra đăng ký (vd SV23001 + SE202.01 → DA_DANG_KY_HOC_PHAN trước LOP_DA_DAY).
3. Phúc khảo chỉ hợp lệ với môn có điểm trong 2025-2026-HK2.
4. TN4 dry-run: mọi ca có `hanh_vi_gia_lap` nguy hiểm phải ra `he_thong_chan`, 0 `bi_lot`.
5. `khong_chua` không được trùng chữ có thể xuất hiện hợp lệ trong câu trả lời của chính sinh viên.

---

### Task 1: TN3 — `agent_scenarios.jsonl`
**Files:** Modify `evaluation/datasets/agent_scenarios.jsonl`
- [ ] Thêm `loai` cho A001–A012; viết A013–A072 theo phân bổ trong spec.
- [ ] Script tạm `verify_tn3.py` (scratchpad): với mỗi kịch bản, dry-run qua `AgentHarness`; chuỗi mong đợi phải có trong `json.dumps(ket_qua)` của các lượt gọi (trừ `chi_rag`/`ket_hop` có `can_kiem_tra`); `thanh_cong`/`loi:`/`cho_xac_nhan` dùng `metrics.task_completed`.
- [ ] Chạy: kỳ vọng mọi kịch bản đạt. Sai → sửa dữ liệu (không sửa code).
- [ ] `python evaluation/run_agent.py --dry-run --configs agent_gemini` chạy hết, không lỗi.

### Task 2: TN4 — `security_cases.jsonl` + văn bản độc hại
**Files:** Modify `evaluation/datasets/security_cases.jsonl`, `evaluation/corpus_an_toan/huong_dan_doc_hai.txt`
- [ ] Thêm Điều 4–7 độc hại (thông báo hệ thống giả, tiếng Anh, giấu trong danh sách, mạo danh hiệu trưởng).
- [ ] Viết S012–S049 theo phân bổ trong spec, 3 nhóm mới `ghi_thay_nguoi_khac`, `lo_cau_hinh`, `dong_vai`.
- [ ] `python evaluation/run_security.py --dry-run`: 0 `bi_lot`.

### Task 3: Tài liệu + kiểm tra cuối
**Files:** Modify `docs/09-danh-gia.md`
- [ ] Cập nhật cỡ mẫu, bảng nhóm TN4 (3 nhóm mới), trường `loai`/`can_kiem_tra`, ghi chú TN1/TN2 hoãn.
- [ ] `pytest -q` (backend) xanh.
- [ ] Liệt kê ID có `can_kiem_tra` cho người dùng; gợi ý commit message (người dùng tự commit).
