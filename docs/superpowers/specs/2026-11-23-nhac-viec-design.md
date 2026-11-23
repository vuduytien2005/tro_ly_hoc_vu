# Thiết kế: Nhắc việc chủ động cho sinh viên

Ngày: 23/11/2026. Người dùng giao Claude tự quyết phương án ("em tự làm").

## Mục đích
Hiện trợ lý chỉ trả lời khi sinh viên hỏi. Nhắc việc giúp sinh viên **không bỏ lỡ hạn**: học phí
còn nợ sắp đến hạn, lịch thi trong 2 tuần tới, sách thư viện sắp hết hạn / quá hạn. Mỗi lời nhắc
có nút "Hỏi trợ lý" mở khung chat với câu hỏi soạn sẵn (vd "Gia hạn sách … giúp em") — nối nhắc
việc với vòng lặp Agent và cơ chế xác nhận đã có.

## Mục tiêu / không làm
- Có: chuông trên thanh bên trang sinh viên, huy hiệu số việc cần chú ý, danh sách nhắc việc.
- Có: tôn trọng đủ quy tắc bảo mật (quy tắc 1, 3, 6) — không có đường đọc dữ liệu mới.
- Không: email / thông báo đẩy, bộ lập lịch chạy nền, lưu trạng thái "đã đọc" (để hướng phát triển).
- Không: nhắc hạn đăng ký học phần — chưa có công cụ MCP nào trả `dang_ky_den`; thêm công cụ mới
  làm đổi tập công cụ của thực nghiệm TN3/TN4 nên để sau.
- Chống mục tiêu: không được gọi thẳng `tlhv_qlsv` hay qlsv_api bỏ qua MCP.

## Phương án đã cân nhắc
1. **Gọi lại các công cụ MCP đọc có sẵn qua `call_direct` (CHỌN).** Giống trang "Thủ tục của em":
   `ma_sv` tiêm từ JWT, công cụ tắt thì bỏ qua, mỗi lần gọi ghi `luot_goi_cong_cu`. Không thêm
   công cụ, không đổi CSDL, không ảnh hưởng thực nghiệm.
2. Gọi thẳng qlsv_api như `qlsv_directory.py`: nhanh hơn nhưng mở thêm ngoại lệ kiến trúc và bỏ
   qua nhật ký/bật-tắt công cụ — trái tinh thần đề tài.
3. Bộ lập lịch chạy nền + bảng `nhac_viec` + email: đầy đủ hơn nhưng cần CSDL mới, SMTP, tiến trình
   nền — quá lớn so với lợi ích demo.

## Thiết kế
**Backend** `GET /api/my/reminders` (router `my_requests.py`, chỉ sinh viên):
- Gọi `get_tuition_status`, `get_exam_schedule`, `get_borrowed_books`. Nguồn nào lỗi hoặc công cụ
  đang tắt thì bỏ qua và ghi tên vào `nguon_loi` (không làm hỏng cả danh sách).
- Hàm thuần `build_reminders(tuition, exams, borrows, today)` (module `assistant_api/reminders.py`):
  - Học phí: `con_no > 0` và hạn ≤ 30 ngày tới hoặc đã quá → `khan` nếu quá hạn hoặc ≤ 7 ngày,
    ngược lại `sap_toi`.
  - Lịch thi: ngày thi trong [hôm nay, +14 ngày] → `khan` nếu ≤ 3 ngày, ngược lại `sap_toi`.
  - Sách: quá hạn hoặc ≤ 7 ngày → `khan` nếu quá hạn hoặc ≤ 2 ngày, ngược lại `sap_toi`.
  - Sắp theo mức độ (khẩn trước) rồi theo hạn.
- "Hôm nay" lấy từ `src.shared.time.now()` (tôn trọng `DEMO_NOW`, đồng bộ với qlsv_api).
- Trả `{ngay: "YYYY-MM-DD", nhac_viec: [{loai, muc_do, tieu_de, chi_tiet, han, con_ngay,
  cau_hoi}], nguon_loi: [...]}`.
- Ghi nhật ký với lý do "Nhắc việc tự động (trang sinh viên)".

**Web**: nút chuông cạnh tiêu đề thanh bên (`StudentLayout`), huy hiệu = số việc `khan`+`sap_toi`;
bấm mở danh sách; mỗi mục có nút "Hỏi trợ lý" → `/chat` với `state.prefill`, ChatPage đặt sẵn câu
hỏi vào ô nhập (không tự gửi). TanStack Query `staleTime` 5 phút để không ghi nhật ký dồn dập.

## Để lại cho người làm
Văn phong lời nhắc, biểu tượng, vị trí popover.
