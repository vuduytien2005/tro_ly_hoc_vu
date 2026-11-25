-- =====================================================================
-- 09_nang_cap_kiem_chung_hoi_dap.sql — Nâng cấp CSDL "tlhv_qlsv" và "tlhv_assistant" ĐÃ CÓ
-- (không mất dữ liệu). 23/11/2026, thiết kế:
-- docs/superpowers/specs/2026-11-23-kiem-chung-va-hoi-can-bo-design.md
--   1. tlhv_qlsv.don_tu.loai_don thêm 'hoi_dap' (câu hỏi sinh viên gửi cán bộ).
--   2. tlhv_assistant.cong_cu thêm công cụ ask_staff (server ctsv, ghi, cần xác nhận).
--   3. tlhv_assistant.tin_nhan thêm cột kiem_chung (kết quả LLM giám khảo kiểm chứng câu trả lời).
-- Máy cài mới (chạy 01, 02, 04) đã có; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ---------------------------------------------------------------------
-- 1. tlhv_qlsv: loại đơn hoi_dap
-- ---------------------------------------------------------------------
USE tlhv_qlsv;
GO
IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = N'chk_don_loai' AND definition NOT LIKE N'%hoi_dap%'
)
    ALTER TABLE dbo.don_tu DROP CONSTRAINT chk_don_loai;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'chk_don_loai')
    ALTER TABLE dbo.don_tu ADD CONSTRAINT chk_don_loai
        CHECK (loai_don IN (N'giay_xac_nhan_sv', N'bao_luu', N'phuc_khao', N'hoi_dap'));
GO

-- ---------------------------------------------------------------------
-- 2 + 3. tlhv_assistant: công cụ ask_staff, cột tin_nhan.kiem_chung
-- ---------------------------------------------------------------------
USE tlhv_assistant;
GO
INSERT INTO cong_cu (mcp_server_id, ten, mo_ta, muc_rui_ro, can_xac_nhan, bat)
SELECT s.id, N'ask_staff', N'Gửi câu hỏi cho cán bộ phòng ban', N'ghi', 1, 1
FROM mcp_server AS s
WHERE s.ten = N'ctsv'
  AND NOT EXISTS (SELECT 1 FROM cong_cu AS c WHERE c.mcp_server_id = s.id AND c.ten = N'ask_staff');
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.tin_nhan') AND name = N'kiem_chung'
)
    ALTER TABLE dbo.tin_nhan ADD kiem_chung NVARCHAR(MAX) NULL
        CONSTRAINT chk_tn_kiem_chung CHECK (ISJSON(kiem_chung) = 1);
GO
SELECT ten, muc_rui_ro, can_xac_nhan, bat FROM cong_cu WHERE ten = N'ask_staff';
GO
PRINT N'Đã nâng cấp: hoi_dap (tlhv_qlsv), ask_staff + tin_nhan.kiem_chung (tlhv_assistant).';
GO
