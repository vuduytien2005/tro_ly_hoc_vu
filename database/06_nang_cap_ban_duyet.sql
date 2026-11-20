-- =====================================================================
-- 06_nang_cap_ban_duyet.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- cong_cu.ban_duyet: mã băm SHA-256 (mô tả + title + input schema) của công cụ tại lúc quản trị
-- viên bật. Mô tả trên MCP server khác bản đã duyệt -> hệ thống tự tắt công cụ (chống "rug pull").
-- NULL = chưa duyệt; công cụ cũ đang bật được ghi mã băm ở lần đồng bộ đầu tiên.
-- Máy cài mới (chạy 02) đã có cột; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.cong_cu') AND name = N'ban_duyet'
)
    ALTER TABLE dbo.cong_cu ADD ban_duyet NVARCHAR(64) NULL;
GO
