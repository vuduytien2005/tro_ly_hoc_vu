# Thiết kế: Chế độ trình bày — bảng "Bên trong Agent" + tiện ích demo

## Mục đích

Ghi điểm trong 10 phút demo trước hội đồng. Hiện nay hội đồng chỉ thấy **kết quả** (câu trả lời, thẻ xác nhận). Bằng chứng mạnh nhất của đề tài là ba lớp an toàn, đặc biệt là tiêm ngữ cảnh. Bằng chứng này chỉ xuất hiện ở bước 6, sau khi chuyển tab Nhật ký, bấm F5 rồi mở JSON. Thao tác đó chậm và khó đọc trên máy chiếu.

Mục tiêu: ngay trong lúc Agent chạy, hội đồng **nhìn thấy** các việc sau:
- LLM chọn công cụ nào;
- LLM gửi tham số gì;
- hệ thống tự điền gì (`ma_sv`);
- thao tác nào phải chờ xác nhận;
- thao tác nào bị từ chối.

## Đã chốt với người dùng (23/11/2026)

- Làm **hướng A**: bảng "Bên trong Agent" đặt cạnh khung chat, bật bằng công tắc "Chế độ trình bày".
- Làm kèm **phần nhỏ của C**:
  - nút câu hỏi soạn sẵn thay cho Notepad;
  - Nhật ký tự tải lại;
  - phóng to chữ khi trình chiếu.
- Không làm sơ đồ MCP sống (hướng B).

## Các phương án đã cân nhắc

| Phương án | Đánh đổi | Kết quả |
|---|---|---|
| A. Bảng "Bên trong Agent" cạnh chat | An toàn hiện ngay ở bước 2 và bước 4; cần một API mới và một panel | **Chọn** |
| B. Sơ đồ MCP sống ở trang quản trị | Đẹp cho đúng bước 5; hội đồng phải nhìn sang cửa sổ admin | Loại |
| C. Gói an toàn khi demo | Giảm rủi ro gõ sai / F5; không tạo ấn tượng mới | Làm phần nhỏ, kèm A |
| Nguồn dữ liệu cho A: sự kiện SSE mới từ vòng lặp Agent | Tức thời hơn vài phần trăm giây; phải sửa lõi Agent đã có test và thực nghiệm | Loại (Claude quyết) |
| Nguồn dữ liệu cho A: đọc nhật ký `luot_goi_cong_cu` | Không đụng vòng lặp; "bảng chính là nhật ký" là lời thoại mạnh | **Chọn (Claude quyết)** |

## Thiết kế

### 1. Bật / tắt (Claude quyết)

- Biến `.env`: `CHE_DO_TRINH_BAY` (mặc định `false`), đọc qua `src/shared/config.py`. Thêm vào `.env.example`.
- `false` thì API mới trả 404 (`{"detail": "...", "code": "KHONG_BAT_CHE_DO_TRINH_BAY"}`) và web ẩn công tắc. Lý do: triển khai thật không lộ tên công cụ hay tham số nội bộ cho sinh viên.
- `GET /health` thêm `che_do_trinh_bay: bool`, để web biết có hiện công tắc hay không. Web đã gọi `/health` cho banner trạng thái.
- Trên web, công tắc "Chế độ trình bày" nằm ở đầu trang chat. Trạng thái lưu trong `localStorage`.

### 2. API `GET /api/conversations/{id}/trace`

- Chỉ **chủ hội thoại** gọi được. Hội thoại của người khác trả 404, giống các API hội thoại hiện có.
- Trả danh sách lượt gọi công cụ của hội thoại, theo thứ tự `id` tăng dần. Mỗi lượt gồm:
  - `id`, `thoi_diem`, `ten_cong_cu`, `nhan` (tiêu đề tiếng Việt: dùng `title` nếu có, không thì nhãn sẵn có), `mcp_server`;
  - `tham_so_llm` (`null` nghĩa là hệ thống tự gọi);
  - `tham_so_he_thong_dien`: các khóa có trong `tham_so` mà không có, hoặc khác giá trị, trong `tham_so_llm`. Ví dụ `{"ma_sv": "SV22001"}`;
  - `trang_thai`, `ly_do`, `thoi_gian_ms`.
- **Không** trả `ket_qua`. Kết quả có thể dài, và đã hiện trong câu trả lời.
- Giá trị của khóa LLM tự gửi rồi bị ghi đè (ví dụ LLM gửi `ma_sv=SV22002`) được giữ trong `tham_so_llm`. Panel hiện cả hai giá trị: "LLM gửi SV22002 → hệ thống ghi đè SV22001".
- Một lượt chờ xác nhận được cập nhật thành `thanh_cong` / `loi` khi sinh viên bấm. Trace đọc lại thì thấy trạng thái mới.

### 3. Panel "Bên trong Agent" (web)

```
┌─ Chat ───────────────────┬─ Bên trong Agent ─────────────────┐
│ Đăng ký lớp học lại CSDL │ ① Tìm lớp học phần      ✓ 120 ms  │
│                          │    LLM gửi: ma_hp=IT004, thu=2     │
│ [Thẻ xác nhận IT004.02]  │    🔒 Hệ thống điền: ma_sv=SV22001 │
│                          │ ② Đăng ký học phần   ⏸ chờ xác nhận│
│                          │    LLM gửi: ma_lop=IT004.02        │
│                          │    🔒 Hệ thống điền: ma_sv=SV22001 │
│                          │ ─ Bảng này đọc từ nhật ký hệ thống │
└──────────────────────────┴────────────────────────────────────┘
```
- Cột phải, rộng khoảng 360 px, chỉ hiện khi bật chế độ trình bày. Màn hẹp thì xếp xuống dưới chat.
- Mỗi lượt là một thẻ đánh số:
  - nhãn tiếng Việt và tên kỹ thuật (chữ nhỏ);
  - huy hiệu trạng thái (màu theo trạng thái nhật ký, cùng bảng màu trang Nhật ký);
  - dòng "LLM gửi: …";
  - dòng **tô vàng** "🔒 Hệ thống điền: …", dùng cùng màu nhãn "Đã tiêm ngữ cảnh" của trang Nhật ký.
- `tham_so_llm = null` → ghi "Hệ thống tự gọi (kiểm tra trước khi tạo thẻ)".
- `bi_tu_choi` → hiện `ly_do` màu đỏ.
- **Khi nào tải lại:**
  - nhận sự kiện SSE `tool_end` hoặc `pending_action`;
  - kết thúc luồng (`done`);
  - xác nhận hoặc hủy thẻ xong;
  - đổi hội thoại.
- Dùng TanStack Query, khóa `['trace', id]`, gọi `invalidate` ở các thời điểm trên. Không poll.
- Thẻ mới xuất hiện có hiệu ứng làm nổi bật ngắn (khoảng 1 giây), để hội đồng thấy "vừa có bước mới".
- Chân panel ghi: "Bảng này đọc trực tiếp từ nhật ký hệ thống (`luot_goi_cong_cu`)."

### 4. Phần nhỏ của C

- **Câu hỏi soạn sẵn:**
  - Khi bật chế độ trình bày, phía trên ô nhập có một hàng nút. Bấm nút thì **điền** câu vào ô nhập, chưa gửi, để người trình bày còn nói trước khi bấm Gửi.
  - Danh sách câu là các câu nguyên văn trong `docs/kich-ban-demo.md`:
    - bước 1–5: RAG, đăng ký, trùng lịch, xem điểm người khác, gia hạn sách;
    - dự bị: tiến độ tốt nghiệp, kế hoạch học kỳ.
  - Danh sách là hằng số trong web (`web/src/lib/demoPrompts.ts`), kèm chú thích "giữ khớp `demo_check.py`". Không lấy từ API.
- **Nhật ký tự tải lại:**
  - Trang `/admin/nhat-ky` có công tắc "Tự cập nhật", bật thì `refetchInterval` 3 giây.
  - Dòng mới có hiệu ứng nổi bật giống panel.
  - Công tắc này không phụ thuộc `CHE_DO_TRINH_BAY` (trang quản trị).
- **Phóng to chữ:**
  - Trong chế độ trình bày, có nút "A+ / A−" đổi cỡ chữ gốc của trang (`html { font-size }`) giữa 100%, 115% và 130%. Lưu `localStorage`.
  - Áp dụng cho trang chat. Trang quản trị có nút riêng ở đầu `AdminLayout`, dùng chung khóa `localStorage`.

### 5. Tài liệu

- `docs/04-api.md`: thêm API trace và trường `/health`.
- `docs/08-giao-dien.md`: mô tả chế độ trình bày.
- `docs/kich-ban-demo.md`:
  - mục 2: bật chế độ trình bày ở cửa sổ A, bỏ Notepad, giữ Notepad làm dự phòng;
  - bước 2 và bước 4: lời thoại chỉ vào dòng "🔒 Hệ thống điền";
  - bước 6 rút gọn: Nhật ký tự cập nhật, không F5;
  - checklist: đặt `CHE_DO_TRINH_BAY=true`.
- `docs/10`: ghi chế độ trình bày mặc định tắt, và lý do.
- `README.md`: biến `.env` mới.

## Mục tiêu / không mục tiêu

- **Mục tiêu:**
  - trong demo bước 2, panel hiện lượt `register_course` "chờ xác nhận" kèm dòng "Hệ thống điền: ma_sv=SV22001" **trước khi** người trình bày bấm Xác nhận;
  - bước 4 (xem điểm SV22002): nếu LLM có gọi công cụ, panel hiện "ghi đè";
  - `pytest`, `ruff`, `npm run build`, `vitest` đều sạch;
  - `demo_check.py` vẫn đạt (không đổi hành vi khi tắt chế độ).
- **Không mục tiêu:**
  - không hiện suy nghĩ hay văn bản trung gian của LLM, không hiện prompt;
  - không sửa vòng lặp Agent;
  - không làm sơ đồ MCP.
- **Phản mục tiêu:**
  - sinh viên xem được trace của hội thoại người khác;
  - chế độ trình bày làm lộ dữ liệu khi `CHE_DO_TRINH_BAY=false`;
  - panel làm chậm hoặc chặn luồng chat (trace lỗi thì panel báo lỗi nhỏ, chat vẫn chạy).

## Để lại cho người viết kế hoạch

- Tên component và file cụ thể, câu chữ tiếng Việt nhỏ, màu chính xác (theo bảng màu hiện có).
- Cách tính `tham_so_he_thong_dien` khi giá trị là danh sách / đối tượng: so sánh bằng `==`.
- `tham_so_he_thong_dien` tính ở backend (test pytest); web chỉ định dạng dòng "LLM gửi / Hệ thống điền / ghi đè" (test vitest tối thiểu cho hàm định dạng).
