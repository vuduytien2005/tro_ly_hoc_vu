# 08. Thiết kế giao diện

Tham khảo bộ mockup đã vẽ (màn hình "Sinh viên – Hỏi đáp", "Nâng cao 1 – Trợ lý cá nhân hóa & làm thủ tục", "Admin – Quản lý tài liệu", "Admin – Thống kê"). Có thể chụp ảnh mockup đặt vào `docs/mockups/` rồi bảo Claude "làm giống ảnh này".

## Phong cách
- Font: Be Vietnam Pro (Google Fonts), hỗ trợ tiếng Việt tốt.
- Màu: nền `#F5F7FB`; xanh đậm `#0F1F4B` (sidebar); xanh chính `#1D4ED8` (nút, tin nhắn người dùng); nhấn vàng `#F59E0B` (biểu tượng trợ lý); xanh lá `#065F46`/`#ECFDF5` (thành công); cam `#9A3412`/`#FFF7ED` (cảnh báo); đỏ `#991B1B`/`#FEF2F2` (lỗi).
- Bo góc 10–18px, viền `#E3E8F0`, không đổ bóng đậm. Vùng bấm tối thiểu 44px.
- Icon: `lucide-react`.

## Cây trang
```
/login
/                       → chuyển tới /chat
/chat                   → cuộc trò chuyện mới
/chat/:id               → cuộc trò chuyện
/thu-tuc                → Thủ tục của em
/admin                  → Thống kê
/admin/tai-lieu
/admin/tai-lieu/:id     → xem các đoạn
/admin/thu-truy-xuat
/admin/mcp
/admin/nhat-ky
```

## Trang chat (quan trọng nhất)
- **Sidebar trái** (nền xanh đậm): logo, nút "Cuộc trò chuyện mới", danh sách hội thoại gần đây, liên kết "Thủ tục của em", thông tin sinh viên ở đáy.
- **Khung chat:** tin người dùng căn phải nền xanh; tin trợ lý căn trái nền trắng.
- **Chip tiến trình** phía trên câu trả lời khi đang xử lý: "Đang tra cứu quy chế…", "Đang xem bảng điểm của em…", chuyển ✓ khi xong. Nhãn lấy từ map tên tool → câu tiếng Việt ở frontend.
- **Trích dẫn:** `[1]` hiển thị dạng nút nhỏ; bên dưới câu trả lời có các thẻ "Nguồn tham khảo" (văn bản, Điều, trang). Bấm `[n]` mở popover: tên văn bản (phiên bản), Điều/Khoản/trang và trích đoạn (`trich_doan`, ≤ 300 ký tự).
- **Thẻ xác nhận hành động:** viền xanh nhạt, tiêu đề "Đề xuất thực hiện", mô tả, đồng hồ "Hết hạn sau 09:41", hai nút "Hủy" / "Xác nhận". Sau khi xử lý: chuyển thành trạng thái "Đã xác nhận ✓" hoặc "Đã hủy" (không bấm lại được).
  - Cài đặt (GĐ7): sau khi bấm, thẻ biến mất và trong luồng chat hiện dòng trạng thái từ tin hệ thống lưu ở backend ("Đã xác nhận: <mô tả>" nền xanh lá / "Đã hủy: <mô tả>"), nên tải lại trang vẫn đúng. Hết giờ (theo `het_han_luc`) thì thẻ khóa nút, hiện "Đã hết hạn". Backend trả 409 (đã xử lý / hết hạn) thì thẻ hiện thông báo lỗi.
- **Đánh giá:** nút 👍/👎 (dùng icon, không dùng emoji) dưới câu trả lời; 👎 mở ô góp ý.
- **Ô nhập:** textarea tự giãn, Enter gửi, Shift+Enter xuống dòng; dòng nhắc "Câu trả lời do AI tạo, hãy đối chiếu văn bản gốc".
- **Câu hỏi gợi ý** khi hội thoại trống: "Em còn thiếu gì để tốt nghiệp?", "Lịch thi của em", "Học lại môn bị F thế nào?", "Xin giấy xác nhận sinh viên".

## Trang "Thủ tục của em"
Bảng/thẻ đơn: mã đơn, loại, ngày tạo, người tạo (Sinh viên / Trợ lý AI), trạng thái (badge màu). Bấm xem chi tiết nội dung đơn và ghi chú xử lý.

## Trang quản trị
- **Tài liệu:** vùng kéo thả, form khai báo phiên bản + khóa áp dụng, bảng trạng thái (Đang xử lý / Đã lập chỉ mục / Lỗi), số đoạn.
- **Thử truy xuất:** ô câu hỏi + chọn khóa + bật/tắt từng thành phần (vector, từ khóa, lọc phiên bản, rerank) → danh sách đoạn kèm điểm. Rất hữu ích để minh họa trong khóa luận.
- **MCP & quyền:** nhóm theo server (chấm xanh/đỏ trạng thái kết nối), mỗi tool một dòng: tên, mô tả, mức rủi ro (select), cần xác nhận (switch), bật (switch).
- **Nhật ký:** bảng thời gian, người dùng, server/tool, trạng thái, thời gian xử lý; bấm dòng mở ngăn chi tiết JSON. Nếu `tham_so_llm` khác `tham_so` → tô vàng "Đã tiêm ngữ cảnh".
- **Thống kê:** 4 thẻ số liệu, biểu đồ chủ đề/tool dùng nhiều, danh sách câu trả lời bị đánh giá "chưa đúng".
