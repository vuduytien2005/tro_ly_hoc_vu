-- =====================================================================
-- 10_nang_cap_kho_hoi_dap.sql — Nâng cấp CSDL "tlhv_assistant" ĐÃ CÓ (không mất dữ liệu).
-- 25/11/2026, thiết kế: docs/superpowers/specs/2026-11-25-kho-hoi-dap-va-lo-hong-tri-thuc-design.md
--   1. van_ban.loai thêm 'hoi_dap' (văn bản "Hỏi đáp cán bộ", không có tệp, dựng từ kho_hoi_dap).
--   2. Bảng kho_hoi_dap: cặp hỏi–đáp cán bộ đã biên tập, được đưa vào RAG.
-- Máy cài mới (chạy 01, 02, 04) đã có; chạy lại script này nhiều lần vẫn an toàn.
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_assistant;
GO

-- 1. Loại văn bản hoi_dap
IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = N'chk_vb_loai' AND definition NOT LIKE N'%hoi_dap%'
)
    ALTER TABLE dbo.van_ban DROP CONSTRAINT chk_vb_loai;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'chk_vb_loai')
    ALTER TABLE dbo.van_ban ADD CONSTRAINT chk_vb_loai
        CHECK (loai IN (N'quy_che', N'so_tay', N'quy_dinh', N'huong_dan', N'thong_bao', N'hoi_dap'));
GO

-- 2. Kho hỏi đáp
IF OBJECT_ID(N'dbo.kho_hoi_dap', N'U') IS NULL
CREATE TABLE dbo.kho_hoi_dap (
  id            INT IDENTITY(1,1) PRIMARY KEY,
  cau_hoi       NVARCHAR(1000) NOT NULL,
  tra_loi       NVARCHAR(MAX)  NOT NULL,
  phong_ban     NVARCHAR(20)   NOT NULL
                CONSTRAINT chk_khd_phong_ban
                CHECK (phong_ban IN (N'dao_tao', N'ctsv', N'tai_chinh', N'khac')),
  ma_don        NVARCHAR(30)   NULL,     -- câu hỏi gốc (don_tu loại hoi_dap ở tlhv_qlsv), nếu có
  tin_nhan_id   INT            NULL,     -- câu trả lời thiếu căn cứ / bị đánh giá xấu, nếu có
  nguoi_tao_id  INT            NOT NULL,
  created_at    DATETIME2(0)   NOT NULL CONSTRAINT df_khd_created DEFAULT SYSDATETIME(),
  updated_at    DATETIME2(0)   NOT NULL CONSTRAINT df_khd_updated DEFAULT SYSDATETIME(),
  CONSTRAINT fk_khd_tn FOREIGN KEY (tin_nhan_id)  REFERENCES tin_nhan(id) ON DELETE SET NULL,
  CONSTRAINT fk_khd_nd FOREIGN KEY (nguoi_tao_id) REFERENCES nguoi_dung(id)
);
GO
SELECT name FROM sys.check_constraints WHERE name = N'chk_vb_loai';
SELECT COUNT(*) AS so_muc_kho FROM dbo.kho_hoi_dap;
GO
PRINT N'Đã nâng cấp: van_ban.loai hoi_dap + bảng kho_hoi_dap (tlhv_assistant).';
GO
