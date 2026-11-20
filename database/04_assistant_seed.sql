-- =====================================================================
-- 04_assistant_seed.sql — Cấu hình MCP server và chính sách công cụ (SQL Server)
-- Tài khoản người dùng KHÔNG tạo ở đây (cần băm mật khẩu bcrypt):
-- chạy backend/scripts/seed_users.py ở Giai đoạn 1.
-- Chạy sau 02_assistant_schema.sql (script 02 xóa và tạo lại bảng).
-- =====================================================================
-- sqlcmd mặc định tắt QUOTED_IDENTIFIER; SSMS mặc định bật. Bật rõ để chạy được ở cả hai.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
SET NOCOUNT ON;

SET IDENTITY_INSERT mcp_server ON;
INSERT INTO mcp_server (id, ten, mo_ta, dia_chi, bat) VALUES
(1, N'dao_tao',   N'Đào tạo: hồ sơ, điểm, lịch thi, tốt nghiệp, đăng ký học phần', N'http://127.0.0.1:9101/mcp', 1),
(2, N'ctsv',      N'Công tác sinh viên: giấy xác nhận, đơn bảo lưu, phúc khảo',     N'http://127.0.0.1:9102/mcp', 1),
(3, N'tai_chinh', N'Tài chính: học phí',                                             N'http://127.0.0.1:9103/mcp', 1),
(4, N'quy_che',   N'Tra cứu quy chế, quy định bằng RAG',                             N'http://127.0.0.1:9104/mcp', 1);
SET IDENTITY_INSERT mcp_server OFF;

INSERT INTO cong_cu (mcp_server_id, ten, mo_ta, muc_rui_ro, can_xac_nhan, bat) VALUES
-- dao_tao
(1, N'get_student_profile',        N'Xem hồ sơ sinh viên đang đăng nhập',                 N'doc',      0, 1),
(1, N'get_transcript',             N'Xem bảng điểm (toàn khóa hoặc theo học kỳ)',          N'doc',      0, 1),
(1, N'get_exam_schedule',          N'Xem lịch thi',                                        N'doc',      0, 1),
(1, N'get_current_schedule',       N'Xem thời khóa biểu các lớp đã đăng ký',               N'doc',      0, 1),
(1, N'get_graduation_progress',    N'Đối chiếu tiến độ với điều kiện tốt nghiệp',          N'doc',      0, 1),
(1, N'search_course_sections',     N'Tìm lớp học phần đang mở đăng ký',                    N'doc',      0, 1),
(1, N'register_course',            N'Đăng ký một lớp học phần',                            N'ghi',      1, 1),
(1, N'cancel_course_registration', N'Hủy đăng ký một lớp học phần',                        N'ghi',      1, 1),
(1, N'plan_next_semester',         N'Lập kế hoạch đăng ký học kỳ tới',                     N'doc',      0, 1),
(1, N'register_courses_bundle',    N'Đăng ký cả gói lớp học phần',                         N'ghi',      1, 1),
-- ctsv
(2, N'request_student_certificate',N'Tạo yêu cầu cấp giấy xác nhận sinh viên',             N'ghi',      1, 1),
(2, N'submit_deferral_request',    N'Nộp đơn bảo lưu kết quả học tập',                     N'nhay_cam', 1, 1),
(2, N'submit_regrade_request',     N'Nộp đơn phúc khảo điểm thi',                          N'ghi',      1, 1),
(2, N'list_my_requests',           N'Xem danh sách đơn đã gửi',                            N'doc',      0, 1),
(2, N'get_request_status',         N'Xem trạng thái một đơn',                              N'doc',      0, 1),
-- tai_chinh
(3, N'get_tuition_status',         N'Xem tình trạng học phí',                              N'doc',      0, 1),
-- quy_che
(4, N'search_regulations',         N'Tìm đoạn văn bản quy chế liên quan đến câu hỏi',      N'doc',      0, 1),
(4, N'get_article',                N'Lấy toàn văn một Điều trong một văn bản',             N'doc',      0, 1);
GO
