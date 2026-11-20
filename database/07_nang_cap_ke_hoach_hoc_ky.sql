-- =====================================================================
-- 07_nang_cap_ke_hoach_hoc_ky.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- Thêm 2 công cụ của server dao_tao (ý tưởng 3 — tư vấn kế hoạch học kỳ tới):
--   plan_next_semester      (đọc, không cần xác nhận)
--   register_courses_bundle (ghi, cần xác nhận — một thẻ cho cả gói)
-- Máy cài mới (chạy 04) đã có; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
INSERT INTO cong_cu (mcp_server_id, ten, mo_ta, muc_rui_ro, can_xac_nhan, bat)
SELECT s.id, v.ten, v.mo_ta, v.muc_rui_ro, v.can_xac_nhan, 1
FROM mcp_server AS s
CROSS JOIN (VALUES
    (N'plan_next_semester',      N'Lập kế hoạch đăng ký học kỳ tới', N'doc', 0),
    (N'register_courses_bundle', N'Đăng ký cả gói lớp học phần',     N'ghi', 1)
) AS v (ten, mo_ta, muc_rui_ro, can_xac_nhan)
WHERE s.ten = N'dao_tao'
  AND NOT EXISTS (SELECT 1 FROM cong_cu AS c WHERE c.mcp_server_id = s.id AND c.ten = v.ten);
GO
SELECT ten, muc_rui_ro, can_xac_nhan, bat FROM cong_cu
WHERE ten IN (N'plan_next_semester', N'register_courses_bundle');
GO
