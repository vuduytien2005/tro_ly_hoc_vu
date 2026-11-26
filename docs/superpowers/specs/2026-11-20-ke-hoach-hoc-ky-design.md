# Thiết kế: Tư vấn kế hoạch học kỳ tới + đăng ký cả gói (ý tưởng 3)

Ngày: 20/11/2026. Người quyết định: người dùng (chủ đề tài). Dự kiến: tuần 2 (khoảng 3 ngày).

## 1. Mục đích và lý do
Sinh viên hỏi *"Kỳ sau em nên đăng ký gì để kịp tốt nghiệp?"*. Trợ lý lập một **gói đăng ký**
cho học kỳ đang mở đăng ký, giải thích vì sao chọn và vì sao loại từng lớp, rồi hiện **một thẻ
xác nhận cho cả gói**. Sinh viên bấm Xác nhận một lần là đăng ký xong.

Lý do: đây là màn demo "Agent" đúng nghĩa trước hội đồng. Agent điều phối nhiều công cụ (lập kế
hoạch → giải thích, có thể tra quy chế → hành động có xác nhận), gặp đúng các "bẫy" thật: lớp đầy,
trùng lịch, môn đang học, môn đã đạt, thiếu tiên quyết.

## 2. Mục tiêu / không làm / tránh
- **Mục tiêu**
  - Gói đề xuất đúng và lặp lại được (cùng dữ liệu → cùng gói).
  - Có lý do cho từng lớp được chọn hoặc bị loại.
  - Xác nhận một lần; đăng ký nguyên khối.
- **Không làm**
  - Kế hoạch nhiều học kỳ (lộ trình đến lúc tốt nghiệp).
  - Tối ưu theo sở thích (giờ học, giảng viên).
  - Học cải thiện điểm (bản giả lập không cho).
  - Sửa gói ngay trên thẻ: sinh viên muốn đổi thì nói với trợ lý, trợ lý tạo thẻ mới.
- **Tránh** (coi là thất bại dù chạy được)
  - Đăng ký được một nửa gói sau khi sinh viên đã xác nhận cả gói.
  - Gói vượt tín chỉ tối đa hoặc chứa lớp trùng lịch.
  - LLM tự bịa lớp không có trong kết quả lập kế hoạch.
  - Vi phạm quy tắc bảo mật 1–3 (ma_sv tiêm từ tài khoản, có xác nhận, có nhật ký).

## 3. Các cách đã cân nhắc

**Bảng 1.** Các cách đã cân nhắc

| Cách | Mô tả | Đánh đổi |
|---|---|---|
| 1. LLM tự lập kế hoạch | LLM gọi lần lượt tiến độ, tìm lớp cho từng môn, tự loại rồi gọi đăng ký gói | "Agent" nhất, nhưng Gemini flash-lite hay sót bước → gói chưa tối ưu, demo chập chờn |
| **2. Công cụ tính toán chắc chắn (ĐÃ CHỌN)** | `plan_next_semester` (qlsv tính) trả gói + lý do; LLM giải thích rồi gọi `register_courses_bundle` | Đúng, lặp lại được, test được, đưa vào Chương 4 được; phần "suy luận" nằm trong code |
| 3. Lai | Công cụ trả danh sách lớp hợp lệ, LLM tự chọn | Vẫn phụ thuộc LLM ở bước khó nhất |

Xác nhận: đã cân nhắc (a) một thẻ cả gói, (b) mỗi lớp một thẻ, (c) chỉ tư vấn. Người dùng chọn **(a)**.

## 4. Thiết kế

### 4.1. qlsv_api — lập kế hoạch (chỉ đọc)
`GET /internal/students/{ma_sv}/semester-plan`. Học kỳ đích là học kỳ đang mở đăng ký; không có
thì 409 `KHONG_CO_HOC_KY_MO_DANG_KY`.

Thuật toán (thuần, không ngẫu nhiên):
1. **Ứng viên** = học phần trong chương trình của SV mà SV chưa đạt (giống "học phần còn thiếu"
   của tiến độ tốt nghiệp).
2. **Loại theo học phần**, mỗi học phần một lý do:
   - đang học: có đăng ký `da_dang_ky` ở học kỳ đang diễn ra (ngày hiện tại nằm trong
     `ngay_bat_dau..ngay_ket_thuc`, khác học kỳ đích) mà chưa có điểm → `DANG_HOC`;
   - đã đăng ký ở học kỳ đích → không đề xuất lại, nhưng tính vào tín chỉ và lịch;
   - thiếu tiên quyết → `CHUA_DAT_TIEN_QUYET` (nêu môn tiên quyết);
   - không có lớp mở ở học kỳ đích → `KHONG_CO_LOP_MO`.
3. **Thứ tự ưu tiên**: học lại (từng có điểm F) → bắt buộc → `hoc_ky_goi_y` nhỏ hơn → mã HP.
   Tự chọn (`bat_buoc = 0`) xếp sau bắt buộc.
4. **Tham lam theo thứ tự ưu tiên.** Với mỗi học phần, xét các lớp theo mã lớp. Chọn lớp đầu tiên
   còn chỗ, không trùng lịch với lớp đã đăng ký và lớp đã chọn, và tổng tín chỉ không vượt giới hạn
   (`tin_chi_toi_da`, hoặc `tin_chi_toi_da_canh_bao` khi bị cảnh báo học vụ — đúng như quy tắc
   đăng ký). Lớp bị bỏ ghi lý do `LOP_DA_DAY` / `TRUNG_LICH` (nêu lớp trùng) / `VUOT_TIN_CHI_TOI_DA`.
   Học phần không chọn được lớp nào thì vào danh sách loại, kèm lý do của từng lớp.
5. **Trả về**: `{hoc_ky, tin_chi_toi_da, tin_chi_da_dang_ky, de_xuat: [{ma_lop, ma_hp, ten_hp,
   tin_chi, lich, bat_buoc, ly_do_chon}], tong_tin_chi_de_xuat, bi_loai: [{ma_hp, ten_hp,
   ma_loi, ly_do, lop: [{ma_lop, ma_loi, ly_do}]?}]}`.

Kỳ vọng với dữ liệu mẫu (SV22001, DEMO_NOW 20/11/2026, học kỳ đích HK2 2026-2027):
- đề xuất **IT004.02** (học lại, bắt buộc; thứ 2 tiết 1–3) và **SE201.01** (tự chọn; thứ 3 tiết
  7–9), tổng 6 tín chỉ;
- loại SE105 (`DANG_HOC`: đang học SE105.01) và SE202 (lớp SE202.01 `LOP_DA_DAY`).

(Gói IT004.02 hay IT004.03 đều hợp lệ; thuật toán chọn lớp đầu tiên theo mã lớp nên ra IT004.02.)

### 4.2. qlsv_api — đăng ký cả gói (nguyên khối)
- `POST /internal/students/{ma_sv}/registrations/bundle` với `{ma_lop: [..]}` (1–8 lớp, không
  trùng).
- `POST .../registrations/bundle/check`: chỉ kiểm tra, không ghi.

Cả hai chạy `register(...)` lần lượt cho từng lớp **trong cùng một giao dịch**. Lớp sau được kiểm
với các lớp trước trong gói, nên trùng lịch / vượt tín chỉ *trong gói* cũng bị bắt. Lớp nào lỗi
thì rollback toàn bộ và trả 409 với `code` của lớp lỗi; `detail` nêu mã lớp. Thành công trả danh
sách lớp đã đăng ký + tổng tín chỉ. Dùng lại khóa hàng hiện có (`_lock_student`, `_lock_section`),
khóa theo thứ tự mã lớp để tránh deadlock.

### 4.3. MCP server `dao_tao` — 2 công cụ mới
- `plan_next_semester(ma_sv)` — đọc, không cần xác nhận. Mô tả: dùng khi sinh viên hỏi kỳ sau nên
  đăng ký gì / lập kế hoạch học kỳ. Trả kết quả 4.1 kèm `thong_bao` tóm tắt (gói, tổng tín chỉ,
  từng lý do loại).
- `register_courses_bundle(ma_sv, ma_lop: list[str], chi_kiem_tra=False)` — ghi, cần xác nhận.
  Mô tả: đăng ký cùng lúc nhiều lớp (thường là gói từ `plan_next_semester`), nguyên khối.
- Thêm vào seed `04_assistant_seed.sql` (`plan_next_semester`: `doc`, 0; `register_courses_bundle`:
  `ghi`, 1) và vào danh sách đặt lại của `90_reset_demo_assistant.sql`. Tổng công cụ có sẵn:
  16 → 18 (cập nhật `demo_check`, tài liệu).

### 4.4. assistant_api — thẻ xác nhận cả gói
Dùng nguyên cơ chế thẻ hiện có (một hành động = một lời gọi `register_courses_bundle`). Chỉ thêm:
- `describe()` cho `register_courses_bundle`: kiểm tra trước cả gói bằng `chi_kiem_tra=True`, báo
  lỗi ngay thay vì hiện thẻ. Mô tả nhiều dòng tra từ `search_course_sections`:
  ```
  Đăng ký 2 lớp (6 tín chỉ) học kỳ 2 năm học 2026-2027:
  • IT004.02 – Cơ sở dữ liệu (3 tín chỉ), Thứ 2, tiết 1–3
  • SE201.01 – Trí tuệ nhân tạo ứng dụng (3 tín chỉ), Thứ 3, tiết 7–9
  ```
- `TOOL_LABELS`: "Đang lập kế hoạch học kỳ tới", "Đang đăng ký cả gói học phần".
- `system_prompt`: thêm một dòng — câu hỏi "kỳ sau học gì / lập kế hoạch" thì gọi
  `plan_next_semester`; chỉ đề xuất đúng các lớp trong `de_xuat`; muốn đăng ký cả gói thì gọi
  `register_courses_bundle`.

### 4.5. Web
`PendingActionCard`: `mo_ta` hiển thị giữ xuống dòng (`whitespace-pre-line`). Không thêm component mới.

### 4.6. Đánh giá và demo
- Thêm 3–4 kịch bản vào `evaluation/datasets/agent_scenarios.jsonl`:
  - SV22001 hỏi kế hoạch;
  - SV22001 "đăng ký cả gói giúp em" (chờ xác nhận `register_courses_bundle`);
  - SV21001 hỏi kế hoạch → chỉ còn SE202, lớp đầy → trợ lý báo không có gói, không hiện thẻ.
- `demo_check`: demo 9 "Tư vấn kế hoạch học kỳ + đăng ký cả gói".
- `docs/kich-ban-demo.md`: cân nhắc ở tuần 3 (thay hoặc thêm vào bước 3).

## 5. Ràng buộc
- Tuân thủ CLAUDE.md:
  - `ma_sv` tiêm từ tài khoản, ẩn khỏi schema;
  - bảng/cột tiếng Việt không dấu;
  - lỗi dạng `{"detail","code"}`;
  - khóa hàng bằng `lock_for_update`, không dùng `with_for_update`;
  - test chạm CSDL bọc trong transaction rồi rollback.
- Quy tắc nghiệp vụ đăng ký không đổi: gói đi qua đúng 9 bước kiểm tra của `register()`.

## 6. Để lại cho người làm
- Tên hàm/module bên trong qlsv (đặt trong `registration_service` hay module `planning_service`
  riêng — đề xuất module riêng).
- Nội dung chính xác của `thong_bao` và câu chữ của các lý do (tiếng Việt, ngắn).
- Giới hạn 8 lớp/gói là lựa chọn của Claude (đủ cho mọi học kỳ của dữ liệu mẫu).

## 7. Các quyết định Claude tự đưa ra (người dùng kiểm khi đọc)
1. Gói "tất cả hoặc không gì cả" (đã nêu trong hội thoại, người dùng không phản đối).
2. Thứ tự ưu tiên: học lại → bắt buộc → học kỳ gợi ý → tự chọn sau cùng.
3. Môn đang học ở học kỳ hiện tại thì không đề xuất (`DANG_HOC`) — hiện `register()` chưa chặn
   việc này; KHÔNG đổi `register()` (ngoài phạm vi).
4. Chọn lớp đầu tiên hợp lệ theo mã lớp (tham lam), không tìm tổ hợp tối ưu toàn cục — đủ cho dữ
   liệu và dễ giải thích.
5. Không cho sửa gói trên thẻ.
