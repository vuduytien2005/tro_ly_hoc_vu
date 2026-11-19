-- =====================================================================
-- 02_assistant_schema.sql
-- CSDL "tlhv_assistant": dữ liệu của trợ lý AI
-- (tài khoản, hội thoại, nhật ký Agent, cấu hình MCP, văn bản RAG)
-- Microsoft SQL Server 2019+ (T-SQL). Chạy bằng SSMS hoặc:
--   sqlcmd -S .\SQLEXPRESS01 -E -C -f 65001 -i database\02_assistant_schema.sql
-- Quy ước chuyển đổi: xem đầu file 01_qlsv_schema.sql.
-- =====================================================================
-- sqlcmd mặc định tắt QUOTED_IDENTIFIER; SSMS mặc định bật. Bật rõ để chạy được ở cả hai.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF DB_ID(N'tlhv_assistant') IS NULL
    CREATE DATABASE tlhv_assistant COLLATE Vietnamese_100_CI_AS;
GO
-- READ_COMMITTED_SNAPSHOT: lệnh ĐỌC dùng bản đã commit, không bị chặn bởi hàng đang ghi dở
-- của transaction khác. Việc tranh chấp ghi vẫn được xếp hàng bằng WITH (UPDLOCK) trong code.
ALTER DATABASE tlhv_assistant SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE tlhv_assistant;
GO

DROP TABLE IF EXISTS danh_gia_cau_tra_loi;
DROP TABLE IF EXISTS hanh_dong_cho_xac_nhan;
DROP TABLE IF EXISTS luot_goi_cong_cu;
DROP TABLE IF EXISTS tin_nhan;
DROP TABLE IF EXISTS hoi_thoai;
DROP TABLE IF EXISTS cong_cu;
DROP TABLE IF EXISTS mcp_server;
DROP TABLE IF EXISTS doan_van_ban;
DROP TABLE IF EXISTS van_ban;
DROP TABLE IF EXISTS nguoi_dung;
GO

-- ---------------------------------------------------------------------
-- Tài khoản
-- ---------------------------------------------------------------------
CREATE TABLE nguoi_dung (
  id              INT IDENTITY(1,1) PRIMARY KEY,
  email           NVARCHAR(255) NOT NULL CONSTRAINT uq_nd_email UNIQUE,
  mat_khau_hash   NVARCHAR(255) NOT NULL,
  ho_ten          NVARCHAR(100) NOT NULL,
  vai_tro         NVARCHAR(20)  NOT NULL
                  CONSTRAINT chk_nd_vai_tro CHECK (vai_tro IN (N'sinh_vien', N'admin')),
  ma_sv           NVARCHAR(20)  NULL,          -- liên kết sang tlhv_qlsv.sinh_vien.ma_sv (chỉ với sinh viên)
  ma_khoa         NVARCHAR(10)  NULL,          -- K22... dùng để lọc phiên bản quy chế
  dang_hoat_dong  BIT           NOT NULL CONSTRAINT df_nd_hd DEFAULT 1,
  created_at      DATETIME2(0)  NOT NULL CONSTRAINT df_nd_created DEFAULT SYSDATETIME()
);
-- SQL Server: UNIQUE thường chỉ cho phép MỘT giá trị NULL -> dùng chỉ mục có lọc
-- để nhiều tài khoản admin (ma_sv = NULL) cùng tồn tại.
CREATE UNIQUE INDEX uq_nd_ma_sv ON nguoi_dung (ma_sv) WHERE ma_sv IS NOT NULL;

-- ---------------------------------------------------------------------
-- Hội thoại
-- ---------------------------------------------------------------------
CREATE TABLE hoi_thoai (
  id             INT IDENTITY(1,1) PRIMARY KEY,
  nguoi_dung_id  INT           NOT NULL,
  tieu_de        NVARCHAR(255) NOT NULL CONSTRAINT df_ht_tieu_de DEFAULT N'Cuộc trò chuyện mới',
  kenh           NVARCHAR(10)  NOT NULL CONSTRAINT df_ht_kenh DEFAULT N'web'
                 CONSTRAINT chk_ht_kenh CHECK (kenh IN (N'web', N'zalo')),
  created_at     DATETIME2(0)  NOT NULL CONSTRAINT df_ht_created DEFAULT SYSDATETIME(),
  updated_at     DATETIME2(0)  NOT NULL CONSTRAINT df_ht_updated DEFAULT SYSDATETIME(),
  CONSTRAINT fk_ht_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id)
);
CREATE INDEX idx_ht_nd ON hoi_thoai (nguoi_dung_id, updated_at);

-- vai_tro 'tool' lưu kết quả công cụ để dựng lại ngữ cảnh cho LLM
CREATE TABLE tin_nhan (
  id            INT IDENTITY(1,1) PRIMARY KEY,
  hoi_thoai_id  INT           NOT NULL,
  vai_tro       NVARCHAR(10)  NOT NULL
                CONSTRAINT chk_tn_vai_tro CHECK (vai_tro IN (N'user', N'assistant', N'tool')),
  noi_dung      NVARCHAR(MAX) NOT NULL,
  tool_call_id  NVARCHAR(MAX) NULL,          -- với vai_tro = tool; Gemini nhúng "thought signature" vào id (hàng trăm-nghìn ký tự)
  tool_calls    NVARCHAR(MAX) NULL CONSTRAINT chk_tn_tool_calls CHECK (ISJSON(tool_calls) = 1),
  trich_dan     NVARCHAR(MAX) NULL CONSTRAINT chk_tn_trich_dan  CHECK (ISJSON(trich_dan) = 1),
  so_token_vao  INT           NULL,
  so_token_ra   INT           NULL,
  thoi_gian_ms  INT           NULL,
  created_at    DATETIME2(3)  NOT NULL CONSTRAINT df_tn_created DEFAULT SYSDATETIME(),
  CONSTRAINT fk_tn_ht FOREIGN KEY (hoi_thoai_id) REFERENCES hoi_thoai(id) ON DELETE CASCADE
);
CREATE INDEX idx_tn_ht ON tin_nhan (hoi_thoai_id, created_at);

-- ---------------------------------------------------------------------
-- Cấu hình MCP
-- ---------------------------------------------------------------------
CREATE TABLE mcp_server (
  id       INT IDENTITY(1,1) PRIMARY KEY,
  ten      NVARCHAR(50)  NOT NULL CONSTRAINT uq_mcp_ten UNIQUE,   -- dao_tao, ctsv, tai_chinh, quy_che
  mo_ta    NVARCHAR(255) NOT NULL,
  dia_chi  NVARCHAR(255) NOT NULL,                               -- vd: http://127.0.0.1:9101/mcp
  bat      BIT           NOT NULL CONSTRAINT df_mcp_bat DEFAULT 1
);

-- Danh mục công cụ + chính sách quyền. Đồng bộ với tool thật của MCP server khi khởi động.
CREATE TABLE cong_cu (
  id             INT IDENTITY(1,1) PRIMARY KEY,
  mcp_server_id  INT           NOT NULL,
  ten            NVARCHAR(100) NOT NULL,
  mo_ta          NVARCHAR(500) NOT NULL,
  muc_rui_ro     NVARCHAR(20)  NOT NULL
                 CONSTRAINT chk_cc_rui_ro CHECK (muc_rui_ro IN (N'doc', N'ghi', N'nhay_cam')),
  can_xac_nhan   BIT           NOT NULL CONSTRAINT df_cc_xn DEFAULT 0,
  bat            BIT           NOT NULL CONSTRAINT df_cc_bat DEFAULT 1,
  CONSTRAINT uq_cc UNIQUE (mcp_server_id, ten),
  CONSTRAINT fk_cc_server FOREIGN KEY (mcp_server_id) REFERENCES mcp_server(id)
);

-- Nhật ký MỌI lần Agent gọi công cụ (phục vụ quản trị + thực nghiệm Chương 4)
CREATE TABLE luot_goi_cong_cu (
  id             BIGINT IDENTITY(1,1) PRIMARY KEY,
  hoi_thoai_id   INT           NULL,
  nguoi_dung_id  INT           NOT NULL,
  mcp_server     NVARCHAR(50)  NOT NULL,
  ten_cong_cu    NVARCHAR(100) NOT NULL,
  tham_so        NVARCHAR(MAX) NOT NULL CONSTRAINT chk_lg_tham_so CHECK (ISJSON(tham_so) = 1),          -- SAU khi tiêm ngữ cảnh
  tham_so_llm    NVARCHAR(MAX) NULL     CONSTRAINT chk_lg_tham_so_llm CHECK (ISJSON(tham_so_llm) = 1),  -- tham số gốc do LLM sinh
  ket_qua        NVARCHAR(MAX) NULL     CONSTRAINT chk_lg_ket_qua CHECK (ISJSON(ket_qua) = 1),
  trang_thai     NVARCHAR(20)  NOT NULL
                 CONSTRAINT chk_lg_trang_thai
                 CHECK (trang_thai IN (N'thanh_cong', N'loi', N'bi_tu_choi', N'cho_xac_nhan', N'da_huy')),
  ly_do          NVARCHAR(500) NULL,          -- lý do lỗi / từ chối
  thoi_gian_ms   INT           NULL,
  created_at     DATETIME2(3)  NOT NULL CONSTRAINT df_lg_created DEFAULT SYSDATETIME(),
  CONSTRAINT fk_lg_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id),
  CONSTRAINT fk_lg_ht FOREIGN KEY (hoi_thoai_id) REFERENCES hoi_thoai(id) ON DELETE SET NULL
);
CREATE INDEX idx_lg_time ON luot_goi_cong_cu (created_at);
CREATE INDEX idx_lg_nd   ON luot_goi_cong_cu (nguoi_dung_id, created_at);
CREATE INDEX idx_lg_tool ON luot_goi_cong_cu (ten_cong_cu, trang_thai);

-- Hành động ghi/nhạy cảm đang chờ sinh viên xác nhận
CREATE TABLE hanh_dong_cho_xac_nhan (
  id             INT IDENTITY(1,1) PRIMARY KEY,
  ma             CHAR(36)      NOT NULL CONSTRAINT uq_hd_ma UNIQUE,   -- UUID gửi cho frontend
  hoi_thoai_id   INT           NOT NULL,
  nguoi_dung_id  INT           NOT NULL,
  luot_goi_id    BIGINT        NOT NULL,          -- bản ghi 'cho_xac_nhan' trong nhật ký
  mcp_server     NVARCHAR(50)  NOT NULL,
  ten_cong_cu    NVARCHAR(100) NOT NULL,
  tham_so        NVARCHAR(MAX) NOT NULL CONSTRAINT chk_hd_tham_so CHECK (ISJSON(tham_so) = 1),
  mo_ta          NVARCHAR(MAX) NOT NULL,          -- mô tả dễ hiểu hiển thị trên thẻ xác nhận
  trang_thai     NVARCHAR(20)  NOT NULL CONSTRAINT df_hd_trang_thai DEFAULT N'cho'
                 CONSTRAINT chk_hd_trang_thai
                 CHECK (trang_thai IN (N'cho', N'da_xac_nhan', N'da_huy', N'het_han')),
  het_han_luc    DATETIME2(0)  NOT NULL,
  xu_ly_luc      DATETIME2(0)  NULL,
  created_at     DATETIME2(0)  NOT NULL CONSTRAINT df_hd_created DEFAULT SYSDATETIME(),
  CONSTRAINT fk_hd_ht FOREIGN KEY (hoi_thoai_id)  REFERENCES hoi_thoai(id) ON DELETE CASCADE,
  CONSTRAINT fk_hd_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id),
  CONSTRAINT fk_hd_lg FOREIGN KEY (luot_goi_id)   REFERENCES luot_goi_cong_cu(id)
);
CREATE INDEX idx_hd_nd ON hanh_dong_cho_xac_nhan (nguoi_dung_id, trang_thai);

CREATE TABLE danh_gia_cau_tra_loi (
  id             INT IDENTITY(1,1) PRIMARY KEY,
  tin_nhan_id    INT           NOT NULL,
  nguoi_dung_id  INT           NOT NULL,
  diem           SMALLINT      NOT NULL,      -- 1 = hữu ích, -1 = chưa đúng (TINYINT của SQL Server không có số âm)
  gop_y          NVARCHAR(MAX) NULL,
  created_at     DATETIME2(0)  NOT NULL CONSTRAINT df_dg_created DEFAULT SYSDATETIME(),
  CONSTRAINT uq_dg UNIQUE (tin_nhan_id, nguoi_dung_id),
  CONSTRAINT chk_diem CHECK (diem IN (-1, 1)),
  CONSTRAINT fk_dg_tn FOREIGN KEY (tin_nhan_id)   REFERENCES tin_nhan(id) ON DELETE CASCADE,
  CONSTRAINT fk_dg_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id)
);

-- ---------------------------------------------------------------------
-- Văn bản cho RAG
-- ---------------------------------------------------------------------
-- Phiên bản áp dụng theo khóa: ap_dung_tu_khoa..ap_dung_den_khoa là số năm 2 chữ số
-- (vd 21..99 nghĩa là áp dụng từ K21 trở đi). NULL = áp dụng cho mọi khóa.
CREATE TABLE van_ban (
  id                INT IDENTITY(1,1) PRIMARY KEY,
  ten               NVARCHAR(255) NOT NULL,
  loai              NVARCHAR(20)  NOT NULL
                    CONSTRAINT chk_vb_loai
                    CHECK (loai IN (N'quy_che', N'so_tay', N'quy_dinh', N'huong_dan', N'thong_bao')),
  phien_ban         NVARCHAR(50)  NOT NULL,       -- vd: 2023
  ap_dung_tu_khoa   TINYINT       NULL,
  ap_dung_den_khoa  TINYINT       NULL,
  ngay_hieu_luc     DATE          NULL,
  ten_tep           NVARCHAR(255) NOT NULL,
  duong_dan_tep     NVARCHAR(500) NOT NULL,
  trang_thai        NVARCHAR(20)  NOT NULL CONSTRAINT df_vb_trang_thai DEFAULT N'dang_xu_ly'
                    CONSTRAINT chk_vb_trang_thai
                    CHECK (trang_thai IN (N'dang_xu_ly', N'da_lap_chi_muc', N'loi')),
  chien_luoc_chunk  NVARCHAR(20)  NOT NULL CONSTRAINT df_vb_chunk DEFAULT N'theo_dieu'
                    CONSTRAINT chk_vb_chunk
                    CHECK (chien_luoc_chunk IN (N'theo_dieu', N'co_dinh', N'ngu_nghia')),
  so_doan           INT           NOT NULL CONSTRAINT df_vb_so_doan DEFAULT 0,
  loi               NVARCHAR(MAX) NULL,
  created_at        DATETIME2(0)  NOT NULL CONSTRAINT df_vb_created DEFAULT SYSDATETIME(),
  updated_at        DATETIME2(0)  NOT NULL CONSTRAINT df_vb_updated DEFAULT SYSDATETIME()
);

-- Mỗi đoạn (chunk). Vector nằm trong ChromaDB với id = vector_id.
-- Tìm theo từ khóa (nửa còn lại của hybrid search) dùng BM25 trong Python
-- (src/rag), không dùng Full-Text Search của SQL Server.
CREATE TABLE doan_van_ban (
  id          INT IDENTITY(1,1) PRIMARY KEY,
  van_ban_id  INT           NOT NULL,
  thu_tu      INT           NOT NULL,
  chuong      NVARCHAR(255) NULL,
  dieu        NVARCHAR(255) NULL,      -- vd: "Điều 12. Đăng ký học phần"
  khoan       NVARCHAR(50)  NULL,
  trang       SMALLINT      NULL,
  noi_dung    NVARCHAR(MAX) NOT NULL,
  so_token    INT           NULL,
  vector_id   NVARCHAR(64)  NOT NULL CONSTRAINT uq_dvb_vector UNIQUE,
  CONSTRAINT fk_dvb_vb FOREIGN KEY (van_ban_id) REFERENCES van_ban(id) ON DELETE CASCADE
);
CREATE INDEX idx_dvb_vb ON doan_van_ban (van_ban_id, thu_tu);
GO

-- Thay cho "ON UPDATE CURRENT_TIMESTAMP" của MySQL
CREATE OR ALTER TRIGGER trg_hoi_thoai_updated_at ON hoi_thoai AFTER UPDATE AS
BEGIN
  SET NOCOUNT ON;
  -- Câu UPDATE đã tự đặt updated_at (vd. backend ghi theo DEMO_NOW) thì giữ nguyên giá trị đó
  IF UPDATE(updated_at) RETURN;
  UPDATE h SET updated_at = SYSDATETIME()
  FROM hoi_thoai h JOIN inserted i ON h.id = i.id;
END;
GO

CREATE OR ALTER TRIGGER trg_van_ban_updated_at ON van_ban AFTER UPDATE AS
BEGIN
  SET NOCOUNT ON;
  -- Câu UPDATE đã tự đặt updated_at (vd. backend ghi theo DEMO_NOW) thì giữ nguyên giá trị đó
  IF UPDATE(updated_at) RETURN;
  UPDATE v SET updated_at = SYSDATETIME()
  FROM van_ban v JOIN inserted i ON v.id = i.id;
END;
GO
