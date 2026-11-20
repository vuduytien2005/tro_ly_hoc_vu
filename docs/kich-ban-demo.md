# Kịch bản demo 10 phút trước hội đồng

Dựa trên `docs/01-dac-ta-yeu-cau.md` mục 6. Thiết kế: `docs/superpowers/specs/2026-11-20-kich-ban-demo-design.md`.

**Mục tiêu:** sau 10 phút, hội đồng nhớ được ba điều:
1. Trợ lý trả lời quy chế **có trích dẫn**.
2. Trợ lý **làm được thủ tục thật** qua MCP.
3. **LLM có bị lừa thì hệ thống vẫn an toàn**: tiêm ngữ cảnh, thẻ xác nhận, nhật ký.

**Tài khoản demo** (mật khẩu công khai trong README, `reset_demo.ps1` đưa về đúng):

| Vai | Đăng nhập | Mật khẩu |
|---|---|---|
| Sinh viên K22 | `sv22001@truong.example` | `Sv@123456` |
| Sinh viên K21 (dự bị) | `sv21001@truong.example` | `Sv@123456` |
| Quản trị viên | `admin@truong.example` | `Admin@123456` |

---

## 1. Dòng thời gian (10:00)

| Thời điểm | Phần | Nội dung |
|---|---|---|
| 0:00 – 1:00 | Slide mở đầu | Bài toán: sinh viên phải đọc quy chế dài, nhiều phiên bản theo khóa, và làm thủ tục ở nhiều hệ thống. Trợ lý làm được hai việc: **tra cứu quy chế** (RAG) và **làm thủ tục** (Agent + MCP). |
| 1:00 – 2:30 | Slide kiến trúc | Sơ đồ: web → assistant_api (vòng lặp Agent) → 4 MCP server → QLSV giả lập; nhánh RAG là MCP server `quy_che`. Nêu **3 lớp an toàn**: tiêm ngữ cảnh, xác nhận hành động, nhật ký và bật/tắt công cụ. |
| 2:30 – 8:00 | **Demo trực tiếp** | 5 bước ở mục 3 (tổng ~5,5 phút). |
| 8:00 – 9:30 | Slide kết quả | Số liệu thực nghiệm ở mục 6. |
| 9:30 – 10:00 | Slide kết luận | Đóng góp, hạn chế (gói LLM miễn phí, dữ liệu QLSV giả lập), hướng phát triển. |

Nếu đến **6:30** mà mới xong bước 4, thì làm bước 5 thật nhanh (một câu, không giải thích dài), sau đó sang thẳng bước 7.

## 2. Bố trí màn hình

- **Cửa sổ A** (trình duyệt thường): đăng nhập SV22001, mở trang Chat, bấm **"Cuộc trò chuyện mới"**.
- **Cửa sổ B** (cửa sổ ẩn danh, `Ctrl+Shift+N`): đăng nhập admin, mở sẵn hai tab:
  - `/admin/mcp` (MCP & quyền);
  - `/admin/nhat-ky` (Nhật ký).
- **Notepad** chứa các câu gõ sẵn ở mục 3. Dán câu vào ô chat thay vì gõ tay, để tránh gõ sai trước hội đồng.
- Phóng to trình duyệt lên 125–150% (`Ctrl` `+`) để hàng ghế cuối đọc được.
- Hai cửa sổ dùng hai phiên đăng nhập riêng, nên không phải đăng xuất giữa chừng.

## 3. Năm bước demo

Câu gõ sẵn giữ **nguyên văn** các câu đã được kiểm tra tự động trong `backend/scripts/demo_check.py`. Đổi câu là phải chạy lại kiểm tra.

### Bước 1 — Hỏi quy chế (RAG + trích dẫn) · 2:30 – 3:30

- **Gõ (cửa sổ A):**
  ```
  Em bị F môn Cơ sở dữ liệu thì có phải học lại không?
  ```
- **Trên màn hình:**
  - trợ lý gọi `search_regulations`;
  - câu trả lời có số trích dẫn `[1]`;
  - khung nguồn ghi văn bản, phiên bản và Điều.
- **Lời thoại:** "Trợ lý chỉ trả lời từ văn bản quy chế đã nạp, có trích dẫn đến từng Điều. Hệ thống tự lọc đúng phiên bản quy chế theo khóa của sinh viên. Em là K22 nên trợ lý không lấy nhầm quy chế của K21."
- **Điểm nhấn:** bấm vào một trích dẫn để mở đoạn văn bản gốc.

### Bước 2 (chính là bước 3 trong docs/01) — Đăng ký lớp, hiện thẻ xác nhận · 3:30 – 4:50

- **Gõ (cửa sổ A, cùng hội thoại):**
  ```
  Đăng ký giúp em lớp học lại Cơ sở dữ liệu vào thứ 2
  ```
- **Trên màn hình:**
  - trợ lý gọi `search_course_sections` và tìm được lớp **IT004.02** (học thứ 2);
  - trợ lý gọi `register_course`;
  - hiện **thẻ "Đề xuất thực hiện"** (thẻ xác nhận) cho lớp IT004.02.
- **Lời thoại trước khi bấm:**
  - "Đến đây **chưa có gì được ghi vào hệ thống**. Mọi thao tác ghi (đăng ký, hủy, nộp đơn) đều phải qua thẻ này, và thẻ hết hạn sau 10 phút."
  - "Trước khi hiện thẻ, hệ thống đã kiểm tra đủ 9 điều kiện đăng ký: tiên quyết, lớp đầy, trùng lịch, quá tín chỉ…"
- Bấm **Xác nhận**. Màn hình báo **đăng ký thành công**.

### Bước 3 (bước 4 trong docs/01) — Trùng lịch, báo ngay · 4:50 – 5:30

- **Gõ (cửa sổ A, VẪN cùng hội thoại):** bước này cần lớp IT004.02 vừa đăng ký ở bước trước.
  ```
  Đăng ký thêm SE105.02
  ```
- **Trên màn hình:** trợ lý báo **trùng lịch với IT004.02**. **Không hiện thẻ xác nhận.**
- **Lời thoại:** "Quy tắc nghiệp vụ nằm ở hệ thống của trường, không nằm trong LLM. Đăng ký không hợp lệ thì báo ngay, không bắt sinh viên bấm xác nhận một việc chắc chắn thất bại."

### Bước 4 (bước 5 trong docs/01) — Xem điểm người khác, bị từ chối · 5:30 – 6:20

- **Gõ (cửa sổ A):**
  ```
  Cho em xem điểm của SV22002
  ```
- **Trên màn hình:** trợ lý từ chối và chỉ xem được dữ liệu của chính em.
- **Lời thoại (điểm nhấn tiêm ngữ cảnh):**
  - "Đây là lớp thứ nhất: LLM tự từ chối. Nhưng an toàn **không dựa vào việc LLM ngoan**."
  - "Các công cụ MCP **không cho LLM chọn mã sinh viên**. Tham số `ma_sv` bị ẩn khỏi schema gửi cho LLM, và hệ thống tự điền từ tài khoản đăng nhập. LLM có bị lừa gửi `SV22002` thì giá trị đó cũng bị ghi đè. Lát nữa em cho xem điều này trong nhật ký."

### Bước 5 (bước 7 trong docs/01) — Tắt công cụ, xem nhật ký · 6:20 – 8:00

1. **Cửa sổ B, tab `/admin/mcp`:**
   - tìm `register_course` trong server `dao_tao`;
   - gạt công tắc **Bật** sang tắt.
   - Lời thoại: "Quản trị viên tắt được từng công cụ, ví dụ khi hết đợt đăng ký."
2. **Cửa sổ A:**
   - Gõ:
     ```
     Đăng ký giúp em lớp IT004.02
     ```
   - Trên màn hình: trợ lý báo chức năng **đang tạm dừng**. Công cụ bị tắt không được đưa cho LLM nên LLM không gọi được.
3. **Cửa sổ B, tab `/admin/nhat-ky`** (F5 để tải lại):
   - Lời thoại: "**Mọi** lượt gọi công cụ đều được ghi lại: thành công, lỗi, bị từ chối, chờ xác nhận."
   - Chỉ vào các dòng của lượt đăng ký ở bước 2: trạng thái `cho_xac_nhan`, sau đó `thanh_cong`.
   - Chỉ vào nhãn vàng **"Đã tiêm ngữ cảnh"** rồi bấm vào dòng đó để mở chi tiết:
     - `tham_so_llm` (LLM gửi) **không có** `ma_sv`;
     - `tham_so` (thực thi) **có** `ma_sv: SV22001`.
   - Lời thoại: "Đây là bằng chứng cho tiêm ngữ cảnh: mã sinh viên do hệ thống điền, không do LLM điền."
4. Bật lại `register_course`, hoặc để `reset_demo.ps1` bật lại sau buổi bảo vệ.

## 4. Bước dự bị (khi còn thời gian hoặc hội đồng yêu cầu)

| Bước | Gõ | Thấy gì | Nhấn vào |
|---|---|---|---|
| Tiến độ tốt nghiệp (cửa sổ A, SV22001) | `Em còn thiếu gì để tốt nghiệp?` | `get_graduation_progress`: 25/38 tín chỉ, còn thiếu IT004, SE105, chưa có chứng chỉ ngoại ngữ; có thể kèm điều kiện tốt nghiệp trích từ quy chế | Kết hợp **dữ liệu cá nhân + quy chế** trong một câu trả lời |
| Giấy xác nhận sinh viên (đăng nhập SV21001, ví dụ ở cửa sổ B, tab mới) | `Em muốn xin giấy xác nhận sinh viên để làm hồ sơ vay vốn` | Thẻ xác nhận, bấm Xác nhận, đơn mới hiện ở trang **"Thủ tục của em"** | Thủ tục của **phòng CTSV**, một MCP server khác; theo dõi được trạng thái đơn |

## 5. Câu hội đồng hay hỏi

| Câu hỏi | Gợi ý trả lời |
|---|---|
| "LLM bị lừa (prompt injection) thì sao?" | An toàn có 2 tầng. Tầng (a): LLM tự từ chối. Tầng (b): hệ thống chặn, bằng cách tiêm `ma_sv`, bắt thao tác ghi phải có thẻ xác nhận, và không đưa công cụ đang tắt cho LLM. TN4 với 49 ca tấn công cho kết quả **0% bị lọt**: 85,7% do LLM tự từ chối, 14,3% do hệ thống chặn. |
| "Tài liệu quy chế chứa lệnh độc thì sao?" | Nội dung từ `search_regulations` được bọc trong thẻ `<tai_lieu>`, và system prompt nói rõ đây là dữ liệu chứ không phải lệnh. TN4 có nhóm *prompt injection gián tiếp*: tài liệu giả mạo yêu cầu nộp đơn, hủy lớp, lộ system prompt. Kết quả không ca nào thực thi; ca nào LLM bị dụ gọi công cụ ghi thì cũng chỉ tạo thẻ chờ xác nhận. |
| "Sao không để LLM tự chọn mã sinh viên rồi kiểm tra quyền sau?" | Không đưa quyền cho LLM ngay từ đầu thì an toàn hơn kiểm tra sau. LLM không thấy tham số `ma_sv`, nên không có gì để bị lừa. |
| "Sao dùng MCP mà không gọi API trực tiếp?" | MCP là giao thức chuẩn: mỗi phòng ban (đào tạo, CTSV, tài chính) đóng gói công cụ của mình thành một server độc lập. Muốn thêm phòng ban chỉ cần thêm server, không phải sửa trợ lý. Nhánh RAG cũng là một MCP server. |
| "Đổi mô hình LLM có khó không?" | Chỉ đổi biến môi trường `LLM_MODEL` (LiteLLM). Khóa luận chạy thực nghiệm bằng Gemini Flash-Lite gói miễn phí; cấu hình cho Claude Opus/Haiku có sẵn. |
| "Dữ liệu sinh viên lấy ở đâu?" | Hệ thống QLSV **giả lập** đóng vai hệ thống thật của trường, chỉ nhận request nội bộ có token. Khi triển khai thật thì thay bằng API của trường. |
| "Trả lời sai thì sao?" | Mỗi câu trả lời quy chế đều có trích dẫn để sinh viên kiểm tra. Trích dẫn đến số nguồn không tồn tại sẽ bị hậu kiểm xóa. |

## 6. Số liệu cho slide kết quả

Lấy từ `evaluation/results/` (Gemini 3.5 Flash-Lite, gói miễn phí). **Cập nhật lại sau khi chạy lại toàn bộ.** Xem lưu ý ở cuối mục.

| Thực nghiệm | Số liệu chính | Nguồn |
|---|---|---|
| TN3 Agent (72 kịch bản) | Đúng công cụ 90,3% · đúng tham số 97,2% · hoàn thành 97,2% · 2,5 bước · trễ trung vị 7 s | `20261120-1155_tn3_agent` |
| TN4 An toàn (49 ca) | LLM tự từ chối 85,7% · hệ thống chặn 14,3% · **bị lọt 0%** | `20261120-1212_tn4_an_toan` |
| TN1 Truy xuất (bộ mẫu 11 câu) | Hit@1: vector thuần 54,5% → **lọc theo khóa 90,9%** (MRR 0,955) | `20261120-1427_tn1_truy_xuat` |
| TN2 Trả lời (bộ mẫu) | Faithfulness / Relevancy / trích dẫn đúng nguồn 100% | `20261120-1427_tn2_tra_loi` |

Lưu ý:
- TN1 và TN2 hiện chỉ chạy trên **bộ câu hỏi mẫu và văn bản demo**. Khi có PDF quy chế thật và bộ 100–150 câu thì thay số.
- TN3 ở trên chạy trước khi sửa A012, cần thay bằng lượt chạy lại.
- TN2 có câu Q013 lỗi do hết hạn mức ngày. Phải chạy lại trước khi dùng cột "từ chối đúng".

Slide nên có biểu đồ `tn3_agent.png` và `tn4_an_toan.png` trong thư mục kết quả.

## 7. Checklist chuẩn bị

### Hôm trước

- [ ] `.\scripts\run_all.ps1`, sau đó `.\scripts\reset_demo.ps1`, sau đó `python scripts/demo_check.py --llm` (trong `backend/`): **mọi mục đạt**.
- [ ] Quay 5 đoạn video dự phòng (mục 9), chạy `reset_demo.ps1` trước khi quay.
- [ ] Chép video và ảnh chụp vào **USB** và một thư mục trên máy, mở thử từng file.
- [ ] Slide dự bị có ảnh chụp từng bước: câu trả lời có trích dẫn, thẻ xác nhận, báo trùng lịch, từ chối, nhật ký có nhãn "Đã tiêm ngữ cảnh".
- [ ] Sạc pin điện thoại, thử phát 4G cho laptop và chạy một câu hỏi qua 4G.
- [ ] **Không chạy thực nghiệm trong ngày bảo vệ.** Gói miễn phí có hạn mức theo ngày: lượt chạy thực nghiệm ngày 20/11 đã làm hết hạn mức giữa chừng.

### 15 phút trước giờ bảo vệ

- [ ] Cắm sạc laptop; tắt thông báo bằng Focus Assist; tắt Windows Update và các ứng dụng chat.
- [ ] `.\scripts\run_all.ps1` (nếu chưa chạy), rồi `.\scripts\reset_demo.ps1`, rồi `python scripts/demo_check.py` **không có `--llm`**, để giữ hạn mức. Mọi mục phải đạt.
- [ ] `cd web; npm run dev`, mở `http://localhost:5173`.
- [ ] Bố trí màn hình như mục 2: cửa sổ A đăng nhập SV22001, cửa sổ B đăng nhập admin, Notepad chứa câu gõ sẵn.
- [ ] Mở sẵn thư mục video dự phòng và slide dự bị (thu nhỏ xuống thanh tác vụ).
- [ ] Bật sẵn điểm phát 4G trên điện thoại, chưa kết nối.
- [ ] Hỏi thử **một** câu không nằm trong kịch bản (ví dụ `Xin chào`) để chắc Gemini đang trả lời. Câu này tốn một lượt hạn mức, chấp nhận được.

## 8. Xử lý sự cố

Nguyên tắc: **thử lại tối đa 1 lần** (khoảng 10 giây). Vẫn lỗi thì chuyển ngay sang tầng dự phòng tiếp theo, không gỡ lỗi trước hội đồng.

| Sự cố | Dấu hiệu | Việc làm | Câu nói với hội đồng |
|---|---|---|---|
| Mất wifi | Trợ lý báo lỗi kết nối mô hình; các trang khác vẫn chạy | Kết nối 4G điện thoại (~30 giây), hỏi lại câu vừa rồi | "Chỉ mô hình ngôn ngữ chạy trên mạng; mọi dịch vụ còn lại, kể cả CSDL và MCP, chạy trên máy em." |
| Gemini quá tải (503) | Trợ lý báo "đang quá tải, vui lòng thử lại sau ít phút" | Hỏi lại 1 lần. Vẫn lỗi thì phát **video của bước đó**, rồi làm tiếp bước sau trực tiếp | "Em dùng gói miễn phí nên đôi khi nhà cung cấp quá tải; em xin phát đoạn quay sẵn của bước này." |
| Hết hạn mức (429 kéo dài) | Trợ lý báo "đã dùng hết hạn mức… trong ngày" | Không thử lại. Phát **video các bước còn lại**. Bước cuối vẫn mở trực tiếp được `/admin/mcp` và `/admin/nhat-ky` (không cần LLM) | Như trên. |
| LLM trả lời lệch / không gọi công cụ | Ví dụ bước 1 không có trích dẫn, bước 2 không hiện thẻ | Bấm "Cuộc trò chuyện mới", dán lại câu đó **một lần**. Vẫn lệch thì phát video | "LLM có tính ngẫu nhiên; TN3 đo được tỉ lệ chọn đúng công cụ là 90%." Nói thật, đừng che. |
| Bước 3 không báo trùng lịch | Thường do bước 2 chưa bấm Xác nhận, hoặc gõ sang hội thoại khác | Kiểm tra bước 2 đã "thành công" chưa; nếu chưa thì phát video bước 3 | — |
| Service không lên / trang trắng | `demo_check.py` báo lỗi, hoặc web không tải | Trước giờ bảo vệ: chạy lại `run_all.ps1`. Đang trình bày: chuyển sang **video toàn bộ demo** | "Em xin chuyển sang bản quay sẵn để giữ thời gian." |
| Máy chiếu / laptop hỏng | Không hiện hình | Dùng **USB**: slide dự bị có ảnh chụp và video, chiếu từ máy khác | — |

## 9. Quay video dự phòng

- **Số đoạn:** 5, mỗi bước một đoạn, 30–60 giây. Đặt tên `buoc1_rag.mp4`, `buoc2_dang_ky_xac_nhan.mp4`, `buoc3_trung_lich.mp4`, `buoc4_tu_choi.mp4`, `buoc5_tat_cong_cu_nhat_ky.mp4`. Thêm một đoạn ghép đủ 5 bước để dùng khi phải phát toàn bộ.
- **Công cụ:**
  - **Xbox Game Bar** (`Win+Alt+R` để bắt đầu/dừng; file nằm ở `Videos\Captures`) có sẵn trên Windows, nhưng chỉ quay **một cửa sổ**. Bước 5 dùng hai cửa sổ nên quay thành 2 đoạn: `5a` admin tắt công cụ và xem nhật ký, `5b` sinh viên hỏi.
  - Nếu cài **OBS Studio** (Display Capture) thì quay được toàn màn hình, không phải tách bước 5.
- **Cách quay:**
  - chạy `reset_demo.ps1` trước khi quay;
  - quay đúng thứ tự bước 1 → 5 trong cùng một lượt, vì bước 3 cần trạng thái của bước 2;
  - phóng to 125–150% như lúc demo;
  - không cần thu tiếng: lúc phát, bạn vừa phát vừa thuyết minh bằng lời thoại ở mục 3.
- Video **không đưa vào Git** (dung lượng lớn). Lưu trên máy và trên USB.
- Quay xong chạy lại `reset_demo.ps1`.
