# Bộ dữ liệu thực nghiệm TN3 (Agent) và TN4 (An toàn) — thiết kế

Ngày: 20/11/2026. Liên quan: `docs/09-danh-gia.md`.

## Mục đích
Đủ cỡ mẫu cho Chương 4 khóa luận: TN3 60–100 kịch bản, TN4 30–50 ca. Bộ hiện có (12 + 11) chỉ mang tính minh họa.
TN1/TN2 **hoãn** đến khi có PDF quy chế thật trong `data/van_ban/` (hiện chỉ có 3 văn bản giả lập, 23 Điều).

## Đã chốt với người dùng
1. Làm TN3/TN4 trước, TN1/TN2 sau khi có văn bản thật.
2. **Giữ nguyên dữ liệu QLSV mẫu** (`database/03_qlsv_seed.sql`) — không thêm sinh viên/lớp; đa dạng bằng tổ hợp sinh viên × công cụ × lỗi nghiệp vụ × cách hỏi. Demo 1–7 và `demo_check.py` không bị ảnh hưởng.
3. TN4 giữ 5 nhóm của `docs/09` và **thêm 3 nhóm**: `ghi_thay_nguoi_khac`, `lo_cau_hinh`, `dong_vai`.
4. Cách làm: **viết tay từng dòng jsonl, kiểm bằng máy**.

## Phương án đã cân nhắc
| Phương án | Đánh đổi | Kết quả |
|---|---|---|
| 1. Viết tay + kiểm bằng máy | Mỗi câu có chủ đích; đáp án được đối chiếu dữ liệu thật; tốn công viết | **Chọn** |
| 2. Script sinh theo mẫu | Nhanh nhưng câu na ná, bộ dữ liệu "nhân bản" | Loại |
| 3. Viết tay, không kiểm | Nhanh nhất, người dùng phải dò ~120 đáp án | Loại |

## Phạm vi
**Có:** viết lại `evaluation/datasets/agent_scenarios.jsonl` (~72 dòng) và `security_cases.jsonl` (~49 dòng); thêm 3–4 Điều độc hại vào `evaluation/corpus_an_toan/huong_dan_doc_hai.txt`; cập nhật `docs/09` (cỡ mẫu, bảng nhóm TN4, trường `can_kiem_tra`).
**Không:** sửa code (`harness.py`, `run_*.py`, `metrics.py`), sửa seed QLSV, chạy thật bằng LLM (người dùng tự chạy khi muốn, tốn hạn mức).
**Phản mục tiêu:** câu chỉ khác vài chữ; đáp án không khớp dữ liệu thật; kịch bản phụ thuộc thứ tự chạy (mỗi kịch bản QLSV đã rollback riêng nên phải tự đủ).

## Định dạng
Giữ nguyên định dạng mà script đang đọc (xem dòng mẫu hiện có). Giữ nguyên 23 dòng cũ và ID (A001–A012, S001–S011) để so sánh được với lượt chạy 19/11; dòng mới đánh số tiếp.
Thêm trường **`can_kiem_tra`** (chuỗi, chỉ có ở dòng cần người dùng đối chiếu, ghi rõ văn bản + Điều cần xem). Script hiện tại bỏ qua trường lạ.
Các nhóm/loại phân biệt bằng trường **`loai`** ở TN3 (mới, script bỏ qua; dùng để chia bảng khi viết khóa luận) và `nhom` ở TN4 (đã có).

## Phân bổ (đề xuất của Claude, người dùng có thể chỉnh)
**TN3 (~72):** `chi_rag` 10 · `du_lieu_ca_nhan` 22 (đủ 5 SV, đủ 9 tool đọc) · `ket_hop` 10 · `thu_tuc_ghi` 12 (5 tool ghi, có ca `tu_dong_xac_nhan: false`) · `nhieu_buoc` 8 (tìm lớp → đăng ký, tra đơn → xem trạng thái) · `loi_nghiep_vu` 10 (TRUNG_LICH, LOP_DA_DAY, DA_DAT_HOC_PHAN, chưa đạt tiên quyết, nợ học phí khi bảo lưu…).
Cách hỏi đa dạng: tên môn thay mã, viết tắt, không dấu, hỏi vòng vo.

**TN4 (~49):** `truy_cap_cheo` 8 · `gia_mao` 7 · `bo_qua_xac_nhan` 7 · `prompt_injection_gian_tiep` 8 · `cong_cu_tat` 6 · `ghi_thay_nguoi_khac` 5 · `lo_cau_hinh` 4 · `dong_vai` 4. Mỗi ca có `hanh_vi_gia_lap` để `--dry-run` chứng minh tầng hệ thống chặn.
`lo_cau_hinh`: `khong_chua` gồm đoạn đặc trưng của system prompt và giá trị `INTERNAL_API_TOKEN` (đọc từ `.env` lúc kiểm, **không ghi token vào jsonl** — dùng đoạn system prompt và tên biến).

## Kiểm bằng máy (script tạm, ở scratchpad, không commit)
1. Mỗi kịch bản TN3 `du_lieu_ca_nhan`/`loi_nghiep_vu`/`thu_tuc_ghi`: gọi `qlsv_api` thật (in-process, transaction rollback) đúng thao tác mong đợi → so `ket_qua_mong_doi` (chuỗi phải xuất hiện trong kết quả JSON; mã lỗi phải trùng).
2. Mọi dòng parse được, ID không trùng, tên công cụ ∈ 16 công cụ, `nhom`/`loai` hợp lệ.
3. `python evaluation/run_agent.py --dry-run` và `run_security.py --dry-run` chạy hết, không lỗi; TN4 dry-run: 0 ca `bi_lot`.
4. `pytest` backend vẫn xanh.

## Người dùng tự kiểm
Chỉ các dòng có `can_kiem_tra`: kịch bản tra quy chế (đáp án lấy từ văn bản giả lập) và các Điều độc hại mới. Cuối việc, Claude liệt kê danh sách ID này.
