# Kịch bản demo 10 phút trước hội đồng

Dựa trên `docs/01-dac-ta-yeu-cau.md` mục 6. Thiết kế: `docs/superpowers/specs/2026-11-20-kich-ban-demo-design.md`.

**Mục tiêu:** sau 10 phút, hội đồng nhớ được ba điều:
1. Trợ lý trả lời quy chế **có trích dẫn**.
2. Trợ lý **làm được thủ tục thật** qua MCP, và **thêm được dịch vụ mới lúc đang chạy** mà không sửa code trợ lý (lý do dùng MCP).
3. **LLM có bị lừa thì hệ thống vẫn an toàn**: tiêm ngữ cảnh, thẻ xác nhận, duyệt công cụ, nhật ký.

> Cập nhật 23/11/2026: thêm bước "Thêm server Thư viện" (demo 8 trong `docs/01`) vào phần chính; bước "tắt công cụ" chuyển xuống dự bị vì bước Thư viện đã cho thấy công tắc bật/tắt (công cụ mới mặc định tắt). Kế hoạch học kỳ + đăng ký cả gói (demo 9) là bước dự bị.

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
| 1:00 – 2:30 | Slide kiến trúc | Sơ đồ: web → assistant_api (vòng lặp Agent) → 4 MCP server → QLSV giả lập; nhánh RAG là MCP server `quy_che`. Nêu **3 lớp an toàn**: tiêm ngữ cảnh, xác nhận hành động, nhật ký và bật/tắt (duyệt) công cụ. |
| 2:30 – 8:00 | **Demo trực tiếp** | 6 bước ở mục 3 (tổng ~5,5 phút). |
| 8:00 – 9:30 | Slide kết quả | Số liệu thực nghiệm ở mục 6. |
| 9:30 – 10:00 | Slide kết luận | Đóng góp, hạn chế (gói LLM miễn phí, dữ liệu QLSV giả lập), hướng phát triển. |

Bước 5 (Thư viện) là bước **không được bỏ**: nó trả lời câu "vì sao dùng MCP". Nếu đến **5:45** mà chưa xong bước 4, bỏ lời thoại bước 4 (chỉ gõ câu, chỉ vào câu từ chối) và sang ngay bước 5. Nếu đến **7:30** mà chưa xong bước 5, làm bước 6 thật nhanh: mở một dòng nhật ký có nhãn "Đã tiêm ngữ cảnh", một câu lời thoại, sang slide.

## 2. Bố trí màn hình

- **Cửa sổ A** (trình duyệt thường): đăng nhập SV22001, mở trang Chat, bấm **"Cuộc trò chuyện mới"**.
- **Cửa sổ B** (cửa sổ ẩn danh, `Ctrl+Shift+N`): đăng nhập admin, mở sẵn hai tab:
  - `/admin/mcp` (MCP & quyền) — **chưa có** server `thu_vien` (`reset_demo.ps1` xóa nó);
  - `/admin/nhat-ky` (Nhật ký).
- **Cửa sổ A bật "Chế độ trình bày"** (công tắc ở đầu trang chat; cần `CHE_DO_TRINH_BAY=true` trong `.env`): cột phải "Bên trong Agent" hiện từng lượt gọi công cụ ngay khi Agent chạy; câu hỏi ở mục 3 bấm từ **hàng nút trên ô nhập** (bấm = điền vào ô, chưa gửi — nói xong lời dẫn rồi mới bấm Gửi). Nút A+ để phóng chữ.
- **Notepad** (dự phòng) chứa các câu gõ sẵn ở mục 3 và địa chỉ `http://127.0.0.1:9105/mcp` (bước 5 vẫn dán địa chỉ này).
- Phóng to trình duyệt lên 125–150% (`Ctrl` `+`) để hàng ghế cuối đọc được.
- Hai cửa sổ dùng hai phiên đăng nhập riêng, nên không phải đăng xuất giữa chừng.

## 3. Sáu bước demo

Câu gõ sẵn giữ **nguyên văn** các câu đã được kiểm tra tự động trong `backend/scripts/demo_check.py`. Đổi câu là phải chạy lại kiểm tra.

### Bước 1 — Hỏi quy chế (RAG + trích dẫn) · 2:30 – 3:20

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

### Bước 2 (chính là bước 3 trong docs/01) — Đăng ký lớp, hiện thẻ xác nhận · 3:20 – 4:30

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
- **Chỉ vào cột "Bên trong Agent"** (trước khi bấm): bước `register_course` trạng thái **Chờ xác nhận**, dòng vàng **"🔒 Hệ thống điền: ma_sv=SV22001"**. Lời thoại: "LLM chỉ gửi mã lớp. Mã sinh viên do hệ thống điền từ tài khoản đăng nhập — bảng này đọc thẳng từ nhật ký hệ thống."
- Bấm **Xác nhận**. Màn hình báo **đăng ký thành công**; trên bảng, cùng bước đó chuyển **Thành công**.

### Bước 3 (bước 4 trong docs/01) — Trùng lịch, báo ngay · 4:30 – 5:00

- **Gõ (cửa sổ A, VẪN cùng hội thoại):** bước này cần lớp IT004.02 vừa đăng ký ở bước trước.
  ```
  Đăng ký thêm SE105.02
  ```
- **Trên màn hình:** trợ lý báo **trùng lịch với IT004.02**. **Không hiện thẻ xác nhận.**
- **Lời thoại:** "Quy tắc nghiệp vụ nằm ở hệ thống của trường, không nằm trong LLM. Đăng ký không hợp lệ thì báo ngay, không bắt sinh viên bấm xác nhận một việc chắc chắn thất bại."

### Bước 4 (bước 5 trong docs/01) — Xem điểm người khác, bị từ chối · 5:00 – 5:40

- **Gõ (cửa sổ A):**
  ```
  Cho em xem điểm của SV22002
  ```
- **Trên màn hình:** trợ lý từ chối và chỉ xem được dữ liệu của chính em.
- **Lời thoại (điểm nhấn tiêm ngữ cảnh):**
  - "Đây là lớp thứ nhất: LLM tự từ chối. Nhưng an toàn **không dựa vào việc LLM ngoan**."
  - Nếu cột "Bên trong Agent" có bước mới với dòng **"LLM gửi SV22002 → hệ thống ghi đè ma_sv=SV22001"**: chỉ vào đó — đây là tầng (b) ngay trước mắt. Nếu không có bước nào: LLM đã tự từ chối, không gọi công cụ.
  - "Các công cụ MCP **không cho LLM chọn mã sinh viên**. Tham số `ma_sv` bị ẩn khỏi schema gửi cho LLM, và hệ thống tự điền từ tài khoản đăng nhập. LLM có bị lừa gửi `SV22002` thì giá trị đó cũng bị ghi đè. Lát nữa em cho xem điều này trong nhật ký."

### Bước 5 (bước 8 trong docs/01) — Thêm dịch vụ Thư viện lúc đang chạy · 5:40 – 7:15

Bước trả lời câu "vì sao dùng MCP". Server `thu_vien` (cổng 9105) đã chạy sẵn cùng `run_all.ps1` nhưng **trợ lý chưa biết nó**.

1. **Cửa sổ B, tab `/admin/mcp`:** bấm **"Thêm MCP server"**.
   - Tên `thu_vien`, Mô tả `Thư viện`, Địa chỉ: dán `http://127.0.0.1:9105/mcp` từ Notepad.
   - Bấm **"Kiểm tra kết nối"**: bảng xem trước hiện 3 công cụ server tự khai báo (`get_borrowed_books`, `search_books`, `renew_book`) cùng mô tả đầy đủ sẽ gửi cho LLM.
   - Lời thoại: "Trợ lý hỏi server theo giao thức MCP xem nó có công cụ gì. Em không viết dòng code nào cho Thư viện ở phía trợ lý, cũng không khởi động lại."
   - Bấm **"Lưu"**. Ba công cụ hiện nhãn xanh **"Mới — cần duyệt"**, công tắc **tắt**.
2. **Duyệt công cụ** (vẫn cửa sổ B):
   - Bấm mũi tên cạnh `renew_book` để mở mô tả đầy đủ. Lời thoại: "Mô tả công cụ đi thẳng vào prompt của LLM, server lạ có thể cài lệnh vào đây — gọi là *tool poisoning*. Vì vậy công cụ mới **mặc định tắt**, mặc định là thao tác ghi phải xác nhận; quản trị viên đọc mô tả rồi mới bật. Bật là duyệt."
   - `get_borrowed_books`: chọn mức rủi ro **đọc**, tắt "cần xác nhận", bật.
   - `renew_book`: giữ **ghi + cần xác nhận**, bật.
3. **Cửa sổ A** (hội thoại mới hoặc cùng hội thoại đều được), gõ:
   ```
   Gia hạn giúp em cuốn sách sắp hết hạn
   ```
   - Trên màn hình: chip "Đang dùng: …" lấy theo `title` server khai báo; trợ lý xem sách đang mượn rồi hiện **thẻ "Gia hạn sách (muon_id: 1)"** — cuốn *Nhập môn công nghệ phần mềm*, hạn trả 27/11.
   - Bấm **Xác nhận** → gia hạn thành công, hạn trả mới **11/12/2026**.
   - Lời thoại: "Công cụ mới vẫn đi qua đủ ba lớp an toàn: mã sinh viên do hệ thống điền, thao tác ghi phải xác nhận, và có trong nhật ký. Thêm phòng ban mới chỉ là thêm một MCP server."

### Bước 6 (bước 7 trong docs/01, phần nhật ký) — Xem nhật ký · 7:15 – 8:00

1. **Cửa sổ B, tab `/admin/nhat-ky`** — bật sẵn công tắc **"Tự cập nhật"** (dòng mới tự hiện, không cần F5):
   - Lời thoại: "**Mọi** lượt gọi công cụ đều được ghi lại: thành công, lỗi, bị từ chối, chờ xác nhận."
   - Chỉ vào các dòng của lượt đăng ký ở bước 2 và gia hạn ở bước 5: trạng thái `cho_xac_nhan`, sau đó `thanh_cong`.
   - Chỉ vào nhãn vàng **"Đã tiêm ngữ cảnh"** rồi bấm vào dòng đó để mở chi tiết:
     - `tham_so_llm` (LLM gửi) **không có** `ma_sv`;
     - `tham_so` (thực thi) **có** `ma_sv: SV22001`.
   - Lời thoại: "Đây là bằng chứng cho tiêm ngữ cảnh: mã sinh viên do hệ thống điền, không do LLM điền."
2. Sau buổi bảo vệ: `reset_demo.ps1` xóa server `thu_vien` và đưa dữ liệu về như cũ.

## 4. Bước dự bị (khi còn thời gian hoặc hội đồng yêu cầu)

| Bước | Gõ | Thấy gì | Nhấn vào |
|---|---|---|---|
| Tiến độ tốt nghiệp (cửa sổ A, SV22001) | `Em còn thiếu gì để tốt nghiệp?` | `get_graduation_progress`: 25/38 tín chỉ, còn thiếu IT004, SE105, chưa có chứng chỉ ngoại ngữ; có thể kèm điều kiện tốt nghiệp trích từ quy chế | Kết hợp **dữ liệu cá nhân + quy chế** trong một câu trả lời |
| Giấy xác nhận sinh viên (đăng nhập SV21001, ví dụ ở cửa sổ B, tab mới) | `Em muốn xin giấy xác nhận sinh viên để làm hồ sơ vay vốn` | Thẻ xác nhận, bấm Xác nhận, đơn mới hiện ở trang **"Thủ tục của em"** | Thủ tục của **phòng CTSV**, một MCP server khác; theo dõi được trạng thái đơn |
| Kế hoạch học kỳ + đăng ký cả gói (cửa sổ A, SV22001) | `Lập kế hoạch học kỳ tới rồi đăng ký cả gói giúp em.` | `plan_next_semester` đề xuất gói + lý do loại (SE105 đang học, SE202 lớp đầy), rồi **một** thẻ `register_courses_bundle` liệt kê từng lớp; Xác nhận → đăng ký nguyên khối. Làm sau bước 2 thì gói chỉ còn **SE201.01** (IT004.02 đã đăng ký, vẫn được tính vào lịch và tín chỉ) | Agent **nhiều bước**: tư vấn rồi làm; một thẻ cho cả gói, lỗi một lớp thì không lớp nào được ghi |
| Tắt công cụ (cửa sổ B `/admin/mcp` tắt `register_course`, rồi cửa sổ A) | `Đăng ký giúp em lớp IT004.02` | Trợ lý báo chức năng **đang tạm dừng**, không hiện thẻ; công cụ tắt không được đưa cho LLM | Quản trị viên tắt từng công cụ (vd hết đợt đăng ký). Bật lại ngay sau đó |

## 5. Câu hội đồng hay hỏi

| Câu hỏi | Gợi ý trả lời |
|---|---|
| "LLM bị lừa (prompt injection) thì sao?" | An toàn có 2 tầng. Tầng (a): LLM tự từ chối. Tầng (b): hệ thống chặn, bằng cách tiêm `ma_sv`, bắt thao tác ghi phải có thẻ xác nhận, và không đưa công cụ đang tắt cho LLM. TN4 với 54 ca tấn công (gồm 5 ca MCP server độc hại) cho kết quả **0% bị lọt**: 81,5% do LLM tự từ chối, 18,5% do hệ thống chặn. |
| "Tài liệu quy chế chứa lệnh độc thì sao?" | Nội dung từ `search_regulations` được bọc trong thẻ `<tai_lieu>`, và system prompt nói rõ đây là dữ liệu chứ không phải lệnh. TN4 có nhóm *prompt injection gián tiếp*: tài liệu giả mạo yêu cầu nộp đơn, hủy lớp, lộ system prompt. Kết quả không ca nào thực thi; ca nào LLM bị dụ gọi công cụ ghi thì cũng chỉ tạo thẻ chờ xác nhận. |
| "Sao không để LLM tự chọn mã sinh viên rồi kiểm tra quyền sau?" | Không đưa quyền cho LLM ngay từ đầu thì an toàn hơn kiểm tra sau. LLM không thấy tham số `ma_sv`, nên không có gì để bị lừa. |
| "Sao dùng MCP mà không gọi API trực tiếp?" | MCP là giao thức chuẩn: mỗi phòng ban (đào tạo, CTSV, tài chính) đóng gói công cụ của mình thành một server độc lập. Muốn thêm phòng ban chỉ cần thêm server, không phải sửa trợ lý — **bước 5 vừa làm đúng việc đó với Thư viện**: trợ lý tự hỏi server có công cụ gì (danh sách, mô tả, tham số), không sửa code, không khởi động lại. Nhánh RAG cũng là một MCP server. |
| "Server MCP của bên khác có thể cài lệnh độc vào mô tả công cụ không?" | Có — gọi là *tool poisoning*: mô tả công cụ đi thẳng vào prompt LLM. Lớp chặn: công cụ mới **mặc định tắt**, mặc định ghi + cần xác nhận; quản trị viên đọc mô tả đầy đủ rồi mới bật (bật = duyệt, lưu mã băm mô tả). Server đổi mô tả sau khi duyệt (*rug pull*) → nhãn vàng "Mô tả đã thay đổi — cần duyệt lại", công cụ bị tắt chờ duyệt. Công cụ chưa duyệt chỉ hiện với LLM dưới tên "tạm dừng", không lọt chữ của server. Trùng tên với công cụ đã có → bị bỏ qua. Chỉ nhận server trên máy (`127.0.0.1`). |
| "Đổi mô hình LLM có khó không?" | Chỉ đổi biến môi trường `LLM_MODEL` (LiteLLM). Khóa luận chạy thực nghiệm bằng Gemini Flash-Lite gói miễn phí; cấu hình cho Claude Opus/Haiku có sẵn. |
| "Dữ liệu sinh viên lấy ở đâu?" | Hệ thống QLSV **giả lập** đóng vai hệ thống thật của trường, chỉ nhận request nội bộ có token. Khi triển khai thật thì thay bằng API của trường. |
| "Trả lời sai thì sao?" | Mỗi câu trả lời quy chế đều có trích dẫn để sinh viên kiểm tra. Trích dẫn đến số nguồn không tồn tại sẽ bị hậu kiểm xóa. |

## 6. Số liệu cho slide kết quả

Lấy từ `evaluation/results/` (Gemini 3.5 Flash-Lite, gói miễn phí). **Cập nhật lại sau khi chạy lại toàn bộ.** Xem lưu ý ở cuối mục.

| Thực nghiệm | Số liệu chính | Nguồn |
|---|---|---|
| TN3 Agent (82 kịch bản, 21 công cụ, gồm 7 KB Thư viện) | Đúng công cụ 89,0% · đúng tham số 93,9% · hoàn thành 93,9% (**97,6%** nếu tính 3 ca Thư viện LLM từ chối đúng lý do) · 2,5 bước | `20261123-1040_tn3_agent` |
| Thêm server lúc chạy không làm giảm độ chính xác | Trên 75 kịch bản cũ: 92,0% / 97,3% / 97,3% — **y hệt** lượt 20/11 khi chưa có Thư viện | `20261123-1040` so với `20261120-1616` |
| NF-01 Thời gian phản hồi (TN3) | Chữ đầu tiên (TTFT) trung vị **2,8 s**, **91,5% câu < 5 s** (lượt 20/11: 2,5 s / 96%) | `20261123-1040_tn3_agent` |
| Mô tả công cụ đầy đủ vs tối giản (TN3) | Đúng công cụ 89,0% → 81,7%; thủ tục ghi 92,3% → **69,2%** (tối giản điền sai mã học kỳ `2026-2027-2`); token giảm ~2,3 lần | `20261123-1040_tn3_agent/bang_theo_loai.md` |
| TN4 An toàn (54 ca, gồm 5 ca MCP server độc hại) | LLM tự từ chối 81,5% · hệ thống chặn 18,5% · **bị lọt 0%** (S052, S054 đã chạy lại, kết quả giữ nguyên) | `20261123-1114_tn4_an_toan` + `20261123-1606_tn4_an_toan` |
| TN1 Truy xuất (bộ mẫu 11 câu) | Hit@1: vector thuần 54,5% → **lọc theo khóa 90,9%** (MRR 0,955) | `20261120-1427_tn1_truy_xuat` |
| TN2 Trả lời (bộ mẫu) | Faithfulness / Relevancy / trích dẫn đúng nguồn 100% | `20261120-1427_tn2_tra_loi` |

Lưu ý:
- TN1 và TN2 hiện chỉ chạy trên **bộ câu hỏi mẫu và văn bản demo**. Khi có PDF quy chế thật và bộ 100–150 câu thì thay số.
- TN3/TN4 là lượt 23/11, đã có Thư viện (A076–A082) và nhóm `server_doc_hai` (S050–S054). Phân tích chi tiết từng ca chưa đạt: `docs/09-danh-gia.md`, mục "Lượt chạy 23/11/2026".
- TN4: S052 và S054 đã chạy lại (`20261123-1606_tn4_an_toan`), không còn lỗi hạn mức, phân tầng giữ nguyên.
- TN2 có câu Q013 lỗi do hết hạn mức ngày. Phải chạy lại trước khi dùng cột "từ chối đúng".

Slide nên có biểu đồ `tn4_an_toan.png` (thư mục `20261123-1114_tn4_an_toan`, 9 nhóm gồm `server_doc_hai`) và `tn3_agent.png` (thư mục `20261123-1040_tn3_agent`, đầy đủ / tối giản) — vẽ bằng `python evaluation\plot_results.py <thư mục>`; chạy lại S052/S054 xong thì vẽ lại TN4 và bảng TN3 đầy đủ / tối giản ở trên (lượt `1616` không xuất `tn3_agent.png`; vẽ lại từ `tong_hop.csv` nếu cần biểu đồ).

## 7. Checklist chuẩn bị

### Hôm trước

- [ ] `.env` đặt `CHE_DO_TRINH_BAY=true` rồi chạy lại `run_all.ps1`; mở trang chat thấy công tắc "Chế độ trình bày". **Sau buổi bảo vệ đặt lại `false`.**
- [ ] `.\scripts\run_all.ps1`, sau đó `.\scripts\reset_demo.ps1`, sau đó `python scripts/demo_check.py --llm` (trong `backend/`): **mọi mục đạt**.
- [ ] Quay 6 đoạn video dự phòng (mục 9), chạy `reset_demo.ps1` trước khi quay.
- [ ] Chép video và ảnh chụp vào **USB** và một thư mục trên máy, mở thử từng file.
- [ ] Slide dự bị có ảnh chụp từng bước: câu trả lời có trích dẫn, thẻ xác nhận, báo trùng lịch, từ chối, hộp thoại thêm server Thư viện + nhãn "Mới — cần duyệt" + thẻ gia hạn sách, nhật ký có nhãn "Đã tiêm ngữ cảnh".
- [ ] Sạc pin điện thoại, thử phát 4G cho laptop và chạy một câu hỏi qua 4G.
- [ ] **Không chạy thực nghiệm trong ngày bảo vệ.** Gói miễn phí có hạn mức theo ngày: lượt chạy thực nghiệm ngày 20/11 đã làm hết hạn mức giữa chừng.

### 15 phút trước giờ bảo vệ

- [ ] Cắm sạc laptop; tắt thông báo bằng Focus Assist; tắt Windows Update và các ứng dụng chat.
- [ ] `.\scripts\run_all.ps1` (nếu chưa chạy), rồi `.\scripts\reset_demo.ps1`, rồi `python scripts/demo_check.py` **không có `--llm`**, để giữ hạn mức. Mọi mục phải đạt, đặc biệt "Server Thư viện (:9105) chạy, sẵn sàng thêm" và **không** có lưu ý "Server thu_vien đã được thêm".
- [ ] `cd web; npm run dev`, mở `http://localhost:5173`.
- [ ] Bố trí màn hình như mục 2: cửa sổ A đăng nhập SV22001, cửa sổ B đăng nhập admin, Notepad chứa câu gõ sẵn và địa chỉ server Thư viện.
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
| LLM trả lời lệch / không gọi công cụ | Ví dụ bước 1 không có trích dẫn, bước 2 không hiện thẻ | Bấm "Cuộc trò chuyện mới", dán lại câu đó **một lần**. Vẫn lệch thì phát video | "LLM có tính ngẫu nhiên; TN3 đo được tỉ lệ chọn đúng công cụ là 92%." Nói thật, đừng che. |
| Bước 3 không báo trùng lịch | Thường do bước 2 chưa bấm Xác nhận, hoặc gõ sang hội thoại khác | Kiểm tra bước 2 đã "thành công" chưa; nếu chưa thì phát video bước 3 | — |
| Bước 5: "Kiểm tra kết nối" báo lỗi | Server `thu_vien` (:9105) chưa chạy, hoặc dán sai địa chỉ | Kiểm tra địa chỉ dán từ Notepad; vẫn lỗi thì phát video bước 5 (chạy lại `run_all.ps1` giữa buổi tốn thời gian) | "Server Thư viện chạy như một dịch vụ riêng của phòng ban; em xin phát đoạn quay sẵn." |
| Bước 5: báo "tên đã tồn tại" khi Lưu | Chưa chạy `reset_demo.ps1` sau lần thử trước | Đóng hộp thoại, dùng luôn server `thu_vien` đang có: bật 2 công cụ rồi hỏi tiếp | — |
| Cột "Bên trong Agent" báo "Không tải được nhật ký" | `CHE_DO_TRINH_BAY` chưa bật, hoặc backend vừa khởi động lại | Tắt công tắc "Chế độ trình bày", làm tiếp như cũ; bằng chứng tiêm ngữ cảnh vẫn có ở bước 6 (Nhật ký) | — |
| Service không lên / trang trắng | `demo_check.py` báo lỗi, hoặc web không tải | Trước giờ bảo vệ: chạy lại `run_all.ps1`. Đang trình bày: chuyển sang **video toàn bộ demo** | "Em xin chuyển sang bản quay sẵn để giữ thời gian." |
| Máy chiếu / laptop hỏng | Không hiện hình | Dùng **USB**: slide dự bị có ảnh chụp và video, chiếu từ máy khác | — |

## 9. Quay video dự phòng

- **Số đoạn:** 6, mỗi bước một đoạn, 30–90 giây. Đặt tên `buoc1_rag.mp4`, `buoc2_dang_ky_xac_nhan.mp4`, `buoc3_trung_lich.mp4`, `buoc4_tu_choi.mp4`, `buoc5_them_server_thu_vien.mp4`, `buoc6_nhat_ky.mp4`. Thêm một đoạn ghép đủ 6 bước để dùng khi phải phát toàn bộ.
- **Công cụ:**
  - **Xbox Game Bar** (`Win+Alt+R` để bắt đầu/dừng; file nằm ở `Videos\Captures`) có sẵn trên Windows, nhưng chỉ quay **một cửa sổ**. Bước 5 dùng hai cửa sổ nên quay thành 2 đoạn: `5a` admin thêm server và duyệt công cụ, `5b` sinh viên gia hạn sách.
  - Nếu cài **OBS Studio** (Display Capture) thì quay được toàn màn hình, không phải tách bước 5.
- **Cách quay:**
  - chạy `reset_demo.ps1` trước khi quay;
  - quay đúng thứ tự bước 1 → 6 trong cùng một lượt, vì bước 3 cần trạng thái của bước 2;
  - phóng to 125–150% như lúc demo;
  - không cần thu tiếng: lúc phát, bạn vừa phát vừa thuyết minh bằng lời thoại ở mục 3.
- Video **không đưa vào Git** (dung lượng lớn). Lưu trên máy và trên USB.
- Quay xong chạy lại `reset_demo.ps1`.
