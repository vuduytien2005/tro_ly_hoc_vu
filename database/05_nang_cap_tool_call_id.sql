-- =====================================================================
-- 05_nang_cap_tool_call_id.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- tin_nhan.tool_call_id: NVARCHAR(100) -> NVARCHAR(MAX).
-- Lý do: Gemini (qua LiteLLM) nhúng "thought signature" vào id lời gọi công cụ
-- (vd "call_..__thought__<base64>", ~650 ký tự) -> NVARCHAR(100) báo lỗi cắt chuỗi, trợ lý
-- trả "Lỗi hệ thống" ngay sau lần gọi công cụ đầu tiên. Claude dùng id ngắn nên không gặp.
-- Máy cài mới (chạy 02) đã có NVARCHAR(MAX); chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.tin_nhan') AND name = N'tool_call_id' AND max_length <> -1
)
    ALTER TABLE dbo.tin_nhan ALTER COLUMN tool_call_id NVARCHAR(MAX) NULL;
GO
SELECT name, max_length FROM sys.columns
WHERE object_id = OBJECT_ID(N'dbo.tin_nhan') AND name = N'tool_call_id';  -- -1 = MAX
GO
