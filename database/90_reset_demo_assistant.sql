-- =====================================================================
-- 90_reset_demo_assistant.sql
-- Đưa CSDL "tlhv_assistant" về trạng thái sạch để demo lại (backend/scripts/reset_demo.ps1 gọi).
--   XÓA : hội thoại, tin nhắn, nhật ký gọi công cụ, thẻ chờ xác nhận, đánh giá câu trả lời.
--   ĐẶT LẠI: bật/tắt, mức rủi ro, cần xác nhận của MCP server + công cụ theo 04_assistant_seed.sql
--            (sau demo 7 công cụ register_course bị tắt -> bật lại).
--   XÓA : tài khoản sinh viên mà hồ sơ không còn trong tlhv_qlsv (SV thêm trên web - AD-10 -
--         mất khi reset QLSV ở bước trước -> tài khoản mồ côi).
--   GIỮ : tài khoản demo (seed_users.py đặt lại mật khẩu), văn bản + đoạn đã lập chỉ mục.
-- Chạy được nhiều lần. Chỉ ĐỌC tlhv_qlsv (chạy SAU 01 + 03); không đụng CSDL QLSV cũ.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

-- Con -> cha để không vướng khóa ngoại
DELETE FROM danh_gia_cau_tra_loi;
DELETE FROM hanh_dong_cho_xac_nhan;
DELETE FROM luot_goi_cong_cu;
DELETE FROM tin_nhan;
DELETE FROM hoi_thoai;

-- Tài khoản mồ côi (hội thoại, nhật ký... của họ đã xóa ở trên -> không vướng khóa ngoại)
DELETE FROM nguoi_dung
WHERE vai_tro = N'sinh_vien'
  AND ma_sv IS NOT NULL
  AND ma_sv NOT IN (SELECT ma_sv FROM tlhv_qlsv.dbo.sinh_vien);

UPDATE s SET s.bat = 1, s.dia_chi = v.dia_chi
FROM mcp_server AS s
JOIN (VALUES
    (N'dao_tao',   N'http://127.0.0.1:9101/mcp'),
    (N'ctsv',      N'http://127.0.0.1:9102/mcp'),
    (N'tai_chinh', N'http://127.0.0.1:9103/mcp'),
    (N'quy_che',   N'http://127.0.0.1:9104/mcp')
) AS v (ten, dia_chi) ON v.ten = s.ten;

UPDATE c SET c.muc_rui_ro = v.muc_rui_ro, c.can_xac_nhan = v.can_xac_nhan, c.bat = 1
FROM cong_cu AS c
JOIN (VALUES
    (N'get_student_profile',         N'doc',      0),
    (N'get_transcript',              N'doc',      0),
    (N'get_exam_schedule',           N'doc',      0),
    (N'get_current_schedule',        N'doc',      0),
    (N'get_graduation_progress',     N'doc',      0),
    (N'search_course_sections',      N'doc',      0),
    (N'register_course',             N'ghi',      1),
    (N'cancel_course_registration',  N'ghi',      1),
    (N'request_student_certificate', N'ghi',      1),
    (N'submit_deferral_request',     N'nhay_cam', 1),
    (N'submit_regrade_request',      N'ghi',      1),
    (N'list_my_requests',            N'doc',      0),
    (N'get_request_status',          N'doc',      0),
    (N'get_tuition_status',          N'doc',      0),
    (N'search_regulations',          N'doc',      0),
    (N'get_article',                 N'doc',      0)
) AS v (ten, muc_rui_ro, can_xac_nhan) ON v.ten = c.ten;

COMMIT TRANSACTION;

SELECT
    (SELECT COUNT(*) FROM van_ban WHERE trang_thai = N'da_lap_chi_muc') AS van_ban_da_lap_chi_muc,
    (SELECT COUNT(*) FROM cong_cu WHERE bat = 1) AS cong_cu_dang_bat;
GO
