-- =====================================================================
-- 08_nang_cap_elicitation.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- MCP elicitation (23/11/2026): sau khi sinh viên bấm "Xác nhận", MCP server có thể cần thêm
-- thông tin (vd số điện thoại liên hệ khi bảo lưu) -> thẻ chuyển 'cho_bo_sung', lưu yêu cầu của
-- server (thông điệp, schema biểu mẫu, request_state) vào yeu_cau_bo_sung; sinh viên điền biểu mẫu
-- thì assistant_api gọi lại công cụ kèm câu trả lời. Thiết kế:
-- docs/superpowers/specs/2026-11-23-mcp-elicitation-resources-design.md
-- Máy cài mới (chạy 02) đã có; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.hanh_dong_cho_xac_nhan') AND name = N'yeu_cau_bo_sung'
)
    ALTER TABLE dbo.hanh_dong_cho_xac_nhan ADD yeu_cau_bo_sung NVARCHAR(MAX) NULL
        CONSTRAINT chk_hd_yeu_cau_bo_sung CHECK (ISJSON(yeu_cau_bo_sung) = 1);
GO
IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = N'chk_hd_trang_thai' AND definition NOT LIKE N'%cho_bo_sung%'
)
    ALTER TABLE dbo.hanh_dong_cho_xac_nhan DROP CONSTRAINT chk_hd_trang_thai;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'chk_hd_trang_thai')
    ALTER TABLE dbo.hanh_dong_cho_xac_nhan ADD CONSTRAINT chk_hd_trang_thai
        CHECK (trang_thai IN (N'cho', N'cho_bo_sung', N'da_xac_nhan', N'da_huy', N'het_han'));
GO
PRINT N'Đã nâng cấp hanh_dong_cho_xac_nhan cho MCP elicitation.';
GO
