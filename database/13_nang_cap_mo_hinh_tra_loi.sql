-- =====================================================================
-- 13_nang_cap_mo_hinh_tra_loi.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- 26/11/2026: tin_nhan.mo_hinh = mô hình ngôn ngữ đã viết câu trả lời (LLM_MODEL, hoặc
-- LLM_FALLBACK_MODEL khi mô hình chính hết hạn mức / quá tải). Tin nhắn cũ: NULL.
-- Dùng cho Thống kê > An toàn & độ tin cậy (tỉ lệ câu trả lời phải dùng mô hình dự phòng).
-- Máy cài mới (chạy 02) đã có; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO

IF COL_LENGTH(N'dbo.tin_nhan', N'mo_hinh') IS NULL
    ALTER TABLE dbo.tin_nhan ADD mo_hinh NVARCHAR(100) NULL;
GO
