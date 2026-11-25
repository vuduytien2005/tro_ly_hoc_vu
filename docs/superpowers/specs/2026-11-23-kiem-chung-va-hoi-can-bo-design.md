# Thiết kế: Kiểm chứng câu trả lời quy chế + Chuyển câu hỏi cho cán bộ

Ngày: 23/11/2026. Người dùng chọn phương án 1A + 2A.

## Mục đích
Trả lời hai câu hỏi khó nhất khi bảo vệ:
1. *"LLM bịa quy chế thì sao?"* — hiện chỉ có hậu kiểm số trích dẫn `[n]` (`check_citations`), không
   kiểm tra **nội dung** ý có đúng với đoạn được trích hay không.
2. *"AI không trả lời được thì sinh viên làm gì?"* — hiện chỉ gợi ý "liên hệ Phòng Đào tạo" bằng lời.

Hai chức năng nối nhau: kiểm chứng thấy câu trả lời yếu → gợi ý chuyển câu hỏi cho cán bộ.

## Mục tiêu / không làm / không được xảy ra
- Có: sau mỗi câu trả lời CÓ tra cứu quy chế, một lượt LLM "giám khảo" chấm từng ý *có căn cứ* /
  *không có căn cứ*; giao diện gạch chân ý không có căn cứ + nhãn "Đã kiểm chứng x/y ý"; lưu kết quả.
- Có: công cụ MCP `ask_staff` (server `ctsv`) tạo "câu hỏi gửi cán bộ" (cần xác nhận), cán bộ trả
  lời ở trang "Đơn từ", sinh viên được báo qua chuông nhắc việc.
- Có: thực nghiệm nhỏ cho Chương 4 — tỷ lệ phát hiện ý bịa cài sẵn.
- Không: giấu/sửa câu trả lời (chữ đã stream ra trước khi kiểm chứng xong — giữ TTFT đã đo).
- Không: vai trò "cán bộ" riêng (quản trị viên đóng vai, như trang "Đơn từ").
- Không được: kiểm chứng làm hỏng lượt trả lời — giám khảo lỗi/hết giờ/JSON hỏng thì bỏ qua im lặng
  (ghi log), câu trả lời vẫn lưu và hiện bình thường.
- Không được: nội dung tài liệu điều khiển giám khảo (prompt injection) — đoạn tài liệu đưa vào giám
  khảo vẫn bọc `<tai_lieu>` và prompt nói rõ là dữ liệu.

## Phương án (đã chọn A cho cả hai)
**Kiểm chứng:** A) LLM giám khảo sau khi trả lời (CHỌN) — chính xác với tiếng Việt, bật/tắt bằng
`.env` để so sánh; tốn 1 lượt LLM, +1–2 s sau khi trả lời xong. B) So độ tương đồng embedding — rẻ
nhưng không bắt được ý bịa số liệu (câu sai số vẫn "giống" đoạn gốc). C) Kiểm chứng rồi mới hiện —
mất TTFT.
**Hỏi cán bộ:** A) Công cụ MCP `ask_staff` lưu vào `don_tu` loại `hoi_dap` (CHỌN) — đi qua MCP, có
xác nhận + nhật ký, dùng lại trang "Đơn từ", "Thủ tục của em", chuông nhắc việc. B) Nút giao diện +
bảng riêng ở `tlhv_assistant` — bỏ qua MCP, làm lại trang cán bộ.

## Thiết kế — 1. Kiểm chứng câu trả lời
**Khi nào chạy:** trong `AgentRunner._finish`, chỉ khi lượt này có kết quả `search_regulations`
thành công (có đoạn) và `ANSWER_VERIFY=true` (mặc định bật). Không chạy cho câu trả lời cố định
(`TOO_COMPLEX`, `REFUSED`, `EMPTY`).

**Module mới `agent/verifier.py`** (hàm thuần + 1 hàm async gọi LLM):
- Đầu vào: câu trả lời (đã qua `check_citations`) + **toàn văn** các đoạn của lượt
  (`collect_sources` hiện chỉ giữ trích đoạn 300 ký tự → giữ thêm `noi_dung` đầy đủ trong bộ nhớ,
  KHÔNG lưu vào `trich_dan`).
- Gọi `llm.stream(messages, tools=[])` (dùng lại giao diện `LLM`, FakeLLM test được), gom chữ.
  Mô hình: `VERIFIER_MODEL` nếu đặt, không thì dùng mô hình chính.
- Prompt yêu cầu JSON: `{"y": [{"cau": "<trích NGUYÊN VĂN câu/ý trong câu trả lời>",
  "ket_luan": "co_can_cu" | "khong_co_can_cu", "doan": [<số đoạn>], "ly_do": "<ngắn>"}]}`.
  Câu chào hỏi/gợi ý chung (không phải khẳng định về quy chế) không cần đưa vào.
- Hậu xử lý: bỏ ý có `cau` không xuất hiện trong câu trả lời (sau chuẩn hóa khoảng trắng) — tránh
  giám khảo tự bịa; bỏ số đoạn không có thật. Kết quả:
  `{"tong": n, "co_can_cu": k, "y": [...], "mo_hinh": "...", "thoi_gian_ms": ...}`.
- Lỗi/timeout (`VERIFIER_TIMEOUT_SECONDS`, mặc định 20) / JSON hỏng / không còn ý nào → `None`.

**Lưu:** cột mới `tin_nhan.kiem_chung NVARCHAR(MAX) NULL CHECK (ISJSON(...)=1)` (script nâng cấp
`09_nang_cap_kiem_chung_hoi_dap.sql` phần `tlhv_assistant` + sửa `02_assistant_schema.sql`);
token giám khảo cộng vào `so_token_vao/ra` của tin nhắn (để thống kê chi phí trung thực).

**SSE:** thứ tự mới ở cuối lượt: `citations` → `verifying` (data `{}`) → `verification`
(data = kết quả, chỉ khi có) → `done`. API lịch sử tin nhắn trả thêm `kiem_chung`.

**Giao diện:** trong khi chờ: dòng nhỏ "Đang kiểm chứng với văn bản…". Xong: nhãn dưới câu trả lời
"✓ Đã kiểm chứng 4/5 ý với văn bản" (xanh khi đủ, vàng khi thiếu); ý không có căn cứ được gạch chân
chấm vàng, rê chuột thấy lý do. Có ý không có căn cứ → thêm nút **"Hỏi cán bộ"** (điền sẵn ô chat
"Mình muốn gửi câu hỏi này cho cán bộ phòng ban phụ trách").

**Nhật ký:** giám khảo không phải công cụ MCP → không ghi `luot_goi_cong_cu`; kết quả nằm trong
`tin_nhan.kiem_chung`. Trang "Nhật ký"/bảng "Bên trong Agent" hiện thêm bước "Kiểm chứng" (nếu
bảng TracePanel dựng từ dữ liệu sẵn có thì thêm, không thì để sau).

## Thiết kế — 2. Chuyển câu hỏi cho cán bộ
**qlsv_api:** `don_tu.loai_don` thêm `hoi_dap` (script 09 phần `tlhv_qlsv` sửa CHECK + sửa
`01_qlsv_schema.sql`; `LoaiDon` trong schemas). Máy trạng thái riêng cho `hoi_dap`:
`moi_tao → dang_xu_ly | hoan_tat | tu_choi`; `dang_xu_ly → hoan_tat | tu_choi`. `hoan_tat` = "đã
trả lời", **bắt buộc** `ghi_chu_xu_ly` (nội dung trả lời) → 422 `CAN_NOI_DUNG_TRA_LOI`; `tu_choi` =
"không thuộc phạm vi", vẫn cần lý do. Không kiểm tra nợ học phí/trạng thái học như đơn khác.

**MCP `ctsv.ask_staff`** (cần xác nhận, rủi ro `ghi`):
`ask_staff(ma_sv [INJECTED], cau_hoi: str 10–1000, phong_ban: "dao_tao"|"ctsv"|"tai_chinh"|"khac"
= "khac")` → tạo đơn `hoi_dap`, `noi_dung = {cau_hoi, phong_ban}`, trả mã đơn + thông báo.
Docstring: dùng khi sinh viên muốn hỏi cán bộ, hoặc văn bản không có câu trả lời và sinh viên đồng
ý chuyển; viết lại câu hỏi đầy đủ, tự đứng được (cán bộ không thấy cuộc trò chuyện).
`LOAI_DON` thêm `"hoi_dap": "Câu hỏi gửi cán bộ"`; `get_request_status` với `hoi_dap` gọi
ghi chú là "Trả lời của cán bộ".

**assistant_api:** seed `cong_cu` (sửa `04_assistant_seed.sql` + script 09: `ask_staff`, `ghi`,
`can_xac_nhan=1`, bật); mẫu mô tả thẻ xác nhận trong `actions.describe`:
"Gửi câu hỏi tới <phòng ban> – "<câu hỏi rút gọn>""; nhãn `TOOL_LABELS`; system prompt thêm một
nguyên tắc: không tìm thấy căn cứ hoặc sinh viên muốn hỏi người thật → đề nghị gửi câu hỏi cho cán
bộ bằng `ask_staff` (sinh viên đồng ý mới gọi).
Nhắc việc (`reminders._requests`): `hoi_dap` + `hoan_tat` → "Câu hỏi của em đã được cán bộ trả lời",
mức `sap_toi`, câu hỏi soạn sẵn "Cán bộ trả lời câu hỏi <mã> của em thế nào?".

**Web:** nhãn loại `hoi_dap` ở trang "Đơn từ" (quản trị) và "Thủ tục của em"; với `hoi_dap` nút
chuyển trạng thái theo máy riêng, nút `hoan_tat` ghi "Trả lời", ô ghi chú đổi thành "Nội dung trả
lời" và bắt buộc; "Thủ tục của em" hiện câu hỏi + câu trả lời.

## Thực nghiệm (Chương 4)
`evaluation/run_verifier.py` + `datasets/verifier_cases.jsonl` (~30 ca): mỗi ca = câu hỏi, các đoạn
quy chế thật từ corpus, câu trả lời đúng, và một biến thể cài 1 ý sai (đổi số tín chỉ/mốc thời
gian/điều kiện). Đo: tỷ lệ phát hiện ý sai (recall), tỷ lệ báo nhầm trên câu đúng, độ trễ và token
thêm. Kết quả ghi `evaluation/results/`, mô tả trong `docs/09-danh-gia.md` và
`docs/chuong-4-thuc-nghiem.md`.

## Ảnh hưởng tới thực nghiệm sẵn có
Thêm `ask_staff` làm tập công cụ TN3 lớn hơn 1. Harness lọc công cụ theo cấu hình hiện có; nếu cần
so sánh đúng số cũ thì tắt `ask_staff` trong cấu hình thực nghiệm (ghi chú trong docs/09).

## Tài liệu cập nhật
docs/03 (cột `kiem_chung`, `hoi_dap`), docs/04 (SSE `verifying`/`verification`, `kiem_chung`),
docs/05 (`ask_staff`), docs/08 (giao diện), docs/10 (giám khảo + injection, `ask_staff` qua xác
nhận), CLAUDE.md (danh sách công cụ ctsv).

## Để lại cho người làm
Câu chữ prompt giám khảo, màu/kiểu gạch chân, bố cục ô trả lời ở trang "Đơn từ", số ca thực nghiệm
chính xác (25–35).
