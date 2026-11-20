# 01. Đặc tả yêu cầu

## 1. Mục tiêu
Xây dựng trợ lý ảo AI Agent cho sinh viên với hai năng lực:
1. **Tra cứu quy chế** (RAG): trả lời câu hỏi về quy chế, quy định, có trích dẫn nguồn, đúng phiên bản áp dụng cho khóa của sinh viên.
2. **Thực hiện thủ tục học vụ** (MCP): xem thông tin cá nhân và làm thủ tục thay sinh viên, luôn có bước xác nhận với thao tác thay đổi dữ liệu.

## 2. Tác nhân
| Tác nhân | Mô tả |
|---|---|
| Sinh viên | Đăng nhập, trò chuyện với trợ lý, xác nhận/hủy hành động, theo dõi đơn |
| Quản trị viên (cán bộ Phòng Đào tạo) | Quản lý văn bản, cấu hình công cụ MCP, xem nhật ký, thống kê; xử lý đơn (trên hệ thống QLSV giả lập) |
| Hệ thống QLSV (giả lập) | Hệ thống nghiệp vụ mà Agent thao tác thông qua MCP |
| Nhà cung cấp LLM | Dịch vụ mô hình ngôn ngữ bên ngoài (qua LiteLLM) |

## 3. Yêu cầu chức năng

### 3.1. Sinh viên
| Mã | Chức năng | Ghi chú |
|---|---|---|
| SV-01 | Đăng nhập / đăng xuất | JWT, tài khoản do quản trị cấp (AD-09), không có tự đăng ký |
| SV-02 | Tạo, xem, đổi tên, xóa cuộc trò chuyện | |
| SV-03 | Hỏi đáp quy chế, nhận câu trả lời có trích dẫn [1], [2] | Trích dẫn bấm được, hiện văn bản / Điều / trang |
| SV-04 | Hỏi thông tin cá nhân: hồ sơ, điểm, lịch thi, thời khóa biểu, học phí, tiến độ tốt nghiệp | Chỉ dữ liệu của chính mình |
| SV-05 | Tìm lớp học phần, đăng ký / hủy đăng ký học phần qua trợ lý | Kiểm tra: thời gian đăng ký, sĩ số, trùng lịch, tiên quyết, tín chỉ tối đa |
| SV-06 | Yêu cầu giấy xác nhận sinh viên, nộp đơn bảo lưu, đơn phúc khảo qua trợ lý | |
| SV-07 | Xác nhận hoặc hủy hành động trên thẻ xác nhận | Hết hạn sau 10 phút |
| SV-08 | Xem trang "Thủ tục của em": danh sách đơn và trạng thái | |
| SV-09 | Đánh giá câu trả lời (hữu ích / chưa đúng) kèm góp ý | |
| SV-10 | Nhận câu trả lời dạng streaming, thấy trợ lý đang làm bước nào | SSE |

### 3.2. Quản trị viên
| Mã | Chức năng | Ghi chú |
|---|---|---|
| AD-01 | Tải lên văn bản (PDF/DOCX), khai báo loại, phiên bản, khóa áp dụng | Lập chỉ mục chạy nền |
| AD-02 | Xem danh sách văn bản, trạng thái lập chỉ mục, số đoạn; lập chỉ mục lại; xóa | |
| AD-03 | Xem trước các đoạn đã chia của một văn bản | Phục vụ kiểm tra chất lượng chunking |
| AD-04 | Xem danh sách MCP server, tình trạng kết nối, danh sách công cụ | |
| AD-05 | Bật/tắt công cụ, đổi mức rủi ro, bật/tắt yêu cầu xác nhận | |
| AD-06 | Xem nhật ký gọi công cụ: lọc theo thời gian, người dùng, công cụ, trạng thái | |
| AD-07 | Xem thống kê: số câu hỏi, tỉ lệ hữu ích, thời gian phản hồi, công cụ dùng nhiều, câu trả lời bị đánh giá "chưa đúng" | |
| AD-08 | (Trên qlsv_api) Duyệt / từ chối đơn để demo luồng trạng thái | Có thể dùng Swagger UI |
| AD-09 | Quản lý tài khoản: xem/tìm tài khoản; cấp tài khoản sinh viên chỉ bằng **mã sinh viên** + mật khẩu tạm (họ tên, email, khóa lấy từ QLSV); khóa / mở khóa; đặt lại mật khẩu | Bổ sung 19/11/2026. Không khóa được chính mình |
| AD-10 | Trang "Sinh viên (QLSV)" — mô phỏng phần mềm phòng đào tạo: xem/tìm sinh viên; thêm sinh viên (tùy chọn cấp tài khoản luôn); sửa hồ sơ (trừ mã SV); đổi trạng thái học tập | Bổ sung 20/11/2026 theo yêu cầu người dùng. Ghi qua API qlsv_api; sửa xong đồng bộ tài khoản liên kết. Không xóa (chuyển `thoi_hoc`). SV mới chưa có điểm / lịch |

### 3.3. Trợ lý (hành vi Agent)
| Mã | Yêu cầu |
|---|---|
| AG-01 | Tự quyết định dùng RAG, công cụ dữ liệu cá nhân, hay kết hợp |
| AG-02 | Chỉ trả lời câu hỏi quy chế dựa trên kết quả `search_regulations`; không tìm thấy thì nói không biết và gợi ý liên hệ phòng ban |
| AG-03 | Không bao giờ hỏi hay dùng mã sinh viên do người dùng gõ; luôn dùng danh tính đăng nhập |
| AG-04 | Từ chối yêu cầu xem/thao tác dữ liệu của người khác |
| AG-05 | Với thao tác ghi: giải thích rõ sẽ làm gì, chờ xác nhận, sau đó báo kết quả |
| AG-06 | Tối đa 6 bước gọi công cụ cho một lượt hỏi |
| AG-07 | Trả lời bằng tiếng Việt, ngắn gọn, thân thiện |

## 4. Yêu cầu phi chức năng
| Mã | Yêu cầu |
|---|---|
| NF-01 | Thời gian phản hồi token đầu tiên < 5 giây với câu hỏi thông thường (trên máy cá nhân, LLM qua API) |
| NF-02 | Bảo mật: tiêm ngữ cảnh, xác nhận hành động, nhật ký đầy đủ, token nội bộ (xem CLAUDE.md) |
| NF-03 | Đổi nhà cung cấp LLM chỉ bằng biến môi trường |
| NF-04 | Giao diện responsive, dùng được trên điện thoại |
| NF-05 | Mã nguồn có test tự động cho nghiệp vụ QLSV, chunker, retriever, vòng lặp Agent (dùng LLM giả lập) |
| NF-06 | Chạy được trên Windows 10/11 với Microsoft SQL Server (bản Express trở lên) cài đặt cục bộ |

## 5. Phạm vi và giới hạn
- Thao tác trên **hệ thống QLSV giả lập**, không kết nối hệ thống thật của trường.
- Văn bản: 5–10 văn bản (quy chế đào tạo, sổ tay sinh viên, quy định học phí, hướng dẫn đăng ký học phần, quy định xét tốt nghiệp). PDF dạng văn bản, không xử lý PDF scan (OCR).
- Thủ tục: đăng ký/hủy học phần, giấy xác nhận sinh viên, bảo lưu, phúc khảo.
- Kênh: Web. Zalo là hướng phát triển (bảng `hoi_thoai.kenh` đã sẵn sàng).

## 6. Kịch bản demo chính (dùng cho bảo vệ)
1. SV22001 hỏi: *"Em bị F môn Cơ sở dữ liệu thì có phải học lại không?"* → RAG, có trích dẫn.
2. SV22001 hỏi: *"Em còn thiếu gì để tốt nghiệp?"* → `get_graduation_progress` + RAG điều kiện tốt nghiệp.
3. SV22001: *"Đăng ký giúp em lớp học lại Cơ sở dữ liệu vào thứ 2"* → `search_course_sections` → `register_course(IT004.02)` → thẻ xác nhận → xác nhận → thành công.
4. SV22001: *"Đăng ký thêm SE105.02"* → báo trùng lịch với IT004.02.
5. SV22001: *"Cho em xem điểm của SV22002"* → từ chối.
6. SV21001: *"Em muốn xin giấy xác nhận sinh viên để làm hồ sơ vay vốn"* → thẻ xác nhận → tạo đơn → theo dõi ở "Thủ tục của em".
7. Quản trị viên tắt công cụ `register_course` → sinh viên yêu cầu đăng ký → trợ lý báo chức năng tạm dừng. Xem nhật ký.
