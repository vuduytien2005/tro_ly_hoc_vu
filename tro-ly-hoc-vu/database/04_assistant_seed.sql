-- =====================================================================
-- 04_assistant_seed.sql — Cấu hình MCP server và chính sách công cụ
-- Tài khoản người dùng KHÔNG tạo ở đây (cần băm mật khẩu bcrypt):
-- chạy backend/scripts/seed_users.py ở Giai đoạn 1.
-- =====================================================================
USE assistant;

INSERT INTO mcp_server (id, ten, mo_ta, dia_chi, bat) VALUES
(1, 'dao_tao',   'Đào tạo: hồ sơ, điểm, lịch thi, tốt nghiệp, đăng ký học phần', 'http://127.0.0.1:9101/mcp', 1),
(2, 'ctsv',      'Công tác sinh viên: giấy xác nhận, đơn bảo lưu, phúc khảo',     'http://127.0.0.1:9102/mcp', 1),
(3, 'tai_chinh', 'Tài chính: học phí',                                             'http://127.0.0.1:9103/mcp', 1),
(4, 'quy_che',   'Tra cứu quy chế, quy định bằng RAG',                             'http://127.0.0.1:9104/mcp', 1);

INSERT INTO cong_cu (mcp_server_id, ten, mo_ta, muc_rui_ro, can_xac_nhan, bat) VALUES
-- dao_tao
(1, 'get_student_profile',        'Xem hồ sơ sinh viên đang đăng nhập',                 'doc',      0, 1),
(1, 'get_transcript',             'Xem bảng điểm (toàn khóa hoặc theo học kỳ)',          'doc',      0, 1),
(1, 'get_exam_schedule',          'Xem lịch thi',                                        'doc',      0, 1),
(1, 'get_current_schedule',       'Xem thời khóa biểu các lớp đã đăng ký',               'doc',      0, 1),
(1, 'get_graduation_progress',    'Đối chiếu tiến độ với điều kiện tốt nghiệp',          'doc',      0, 1),
(1, 'search_course_sections',     'Tìm lớp học phần đang mở đăng ký',                    'doc',      0, 1),
(1, 'register_course',            'Đăng ký một lớp học phần',                            'ghi',      1, 1),
(1, 'cancel_course_registration', 'Hủy đăng ký một lớp học phần',                        'ghi',      1, 1),
-- ctsv
(2, 'request_student_certificate','Tạo yêu cầu cấp giấy xác nhận sinh viên',             'ghi',      1, 1),
(2, 'submit_deferral_request',    'Nộp đơn bảo lưu kết quả học tập',                     'nhay_cam', 1, 1),
(2, 'submit_regrade_request',     'Nộp đơn phúc khảo điểm thi',                          'ghi',      1, 1),
(2, 'list_my_requests',           'Xem danh sách đơn đã gửi',                            'doc',      0, 1),
(2, 'get_request_status',         'Xem trạng thái một đơn',                              'doc',      0, 1),
-- tai_chinh
(3, 'get_tuition_status',         'Xem tình trạng học phí',                              'doc',      0, 1),
-- quy_che
(4, 'search_regulations',         'Tìm đoạn văn bản quy chế liên quan đến câu hỏi',      'doc',      0, 1),
(4, 'get_article',                'Lấy toàn văn một Điều trong một văn bản',             'doc',      0, 1);
