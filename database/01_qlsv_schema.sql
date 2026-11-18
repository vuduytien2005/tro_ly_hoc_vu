-- =====================================================================
-- 01_qlsv_schema.sql
-- CSDL "tlhv_qlsv": Hệ thống quản lý sinh viên GIẢ LẬP
-- Đóng vai hệ thống thật của trường để AI Agent thao tác qua MCP.
-- Microsoft SQL Server 2019+ (T-SQL). Chạy bằng SSMS hoặc:
--   sqlcmd -S .\SQLEXPRESS01 -E -C -f 65001 -i database\01_qlsv_schema.sql
-- Quy ước chuyển đổi từ thiết kế gốc (MySQL):
--   ENUM      -> NVARCHAR + CHECK      JSON     -> NVARCHAR(MAX) + CHECK ISJSON
--   TINYINT(1)-> BIT                    DATETIME -> DATETIME2(0) (giờ Việt Nam)
--   ON UPDATE CURRENT_TIMESTAMP -> TRIGGER AFTER UPDATE
-- Mọi cột chuỗi dùng NVARCHAR (Unicode) để lưu tiếng Việt có dấu.
-- =====================================================================
-- sqlcmd mặc định tắt QUOTED_IDENTIFIER; SSMS mặc định bật. Bật rõ để chạy được ở cả hai.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF DB_ID(N'tlhv_qlsv') IS NULL
    CREATE DATABASE tlhv_qlsv COLLATE Vietnamese_100_CI_AS;
GO
-- READ_COMMITTED_SNAPSHOT: lệnh ĐỌC dùng bản đã commit, không bị chặn bởi hàng đang ghi dở
-- của transaction khác. Việc tranh chấp ghi vẫn được xếp hàng bằng WITH (UPDLOCK) trong code.
ALTER DATABASE tlhv_qlsv SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE tlhv_qlsv;
GO

-- Xóa theo thứ tự con -> cha để không vướng khóa ngoại
DROP TABLE IF EXISTS don_tu;
DROP TABLE IF EXISTS chung_chi;
DROP TABLE IF EXISTS hoc_phi;
DROP TABLE IF EXISTS lich_thi;
DROP TABLE IF EXISTS ket_qua_hoc_tap;
DROP TABLE IF EXISTS dang_ky_hoc_phan;
DROP TABLE IF EXISTS lop_hoc_phan;
DROP TABLE IF EXISTS hoc_ky;
DROP TABLE IF EXISTS chuong_trinh_hoc_phan;
DROP TABLE IF EXISTS hoc_phan_tien_quyet;
DROP TABLE IF EXISTS hoc_phan;
DROP TABLE IF EXISTS sinh_vien;
DROP TABLE IF EXISTS chuong_trinh;
DROP TABLE IF EXISTS khoa_hoc;
DROP TABLE IF EXISTS nganh;
GO

-- Ngành đào tạo
CREATE TABLE nganh (
  id         INT IDENTITY(1,1) PRIMARY KEY,
  ma_nganh   NVARCHAR(20)  NOT NULL CONSTRAINT uq_nganh_ma UNIQUE,
  ten_nganh  NVARCHAR(255) NOT NULL
);

-- Khóa tuyển sinh (K21, K22...) – quyết định phiên bản quy chế áp dụng
CREATE TABLE khoa_hoc (
  id           INT IDENTITY(1,1) PRIMARY KEY,
  ma_khoa      NVARCHAR(10) NOT NULL CONSTRAINT uq_khoa_hoc_ma UNIQUE,
  nam_bat_dau  SMALLINT     NOT NULL
);

-- Chương trình đào tạo của một ngành cho một khóa
CREATE TABLE chuong_trinh (
  id                 INT IDENTITY(1,1) PRIMARY KEY,
  nganh_id           INT          NOT NULL,
  khoa_hoc_id        INT          NOT NULL,
  tong_tin_chi       SMALLINT     NOT NULL,
  gpa_toi_thieu      DECIMAL(3,2) NOT NULL CONSTRAINT df_ct_gpa DEFAULT 2.00,
  yeu_cau_ngoai_ngu  BIT          NOT NULL CONSTRAINT df_ct_nn DEFAULT 1,
  CONSTRAINT uq_ct UNIQUE (nganh_id, khoa_hoc_id),
  CONSTRAINT fk_ct_nganh FOREIGN KEY (nganh_id)    REFERENCES nganh(id),
  CONSTRAINT fk_ct_khoa  FOREIGN KEY (khoa_hoc_id) REFERENCES khoa_hoc(id)
);

CREATE TABLE sinh_vien (
  id           INT IDENTITY(1,1) PRIMARY KEY,
  ma_sv        NVARCHAR(20)  NOT NULL CONSTRAINT uq_sv_ma UNIQUE,
  ho_ten       NVARCHAR(100) NOT NULL,
  email        NVARCHAR(255) NOT NULL CONSTRAINT uq_sv_email UNIQUE,
  ngay_sinh    DATE          NOT NULL,
  gioi_tinh    NVARCHAR(10)  NOT NULL
               CONSTRAINT chk_sv_gioi_tinh CHECK (gioi_tinh IN (N'nam', N'nu', N'khac')),
  nganh_id     INT           NOT NULL,
  khoa_hoc_id  INT           NOT NULL,
  lop          NVARCHAR(20)  NOT NULL,
  trang_thai   NVARCHAR(20)  NOT NULL CONSTRAINT df_sv_trang_thai DEFAULT N'dang_hoc'
               CONSTRAINT chk_sv_trang_thai
               CHECK (trang_thai IN (N'dang_hoc', N'bao_luu', N'thoi_hoc', N'tot_nghiep')),
  created_at   DATETIME2(0)  NOT NULL CONSTRAINT df_sv_created DEFAULT SYSDATETIME(),
  CONSTRAINT fk_sv_nganh FOREIGN KEY (nganh_id)    REFERENCES nganh(id),
  CONSTRAINT fk_sv_khoa  FOREIGN KEY (khoa_hoc_id) REFERENCES khoa_hoc(id)
);

CREATE TABLE hoc_phan (
  id          INT IDENTITY(1,1) PRIMARY KEY,
  ma_hp       NVARCHAR(20)  NOT NULL CONSTRAINT uq_hp_ma UNIQUE,
  ten_hp      NVARCHAR(255) NOT NULL,
  so_tin_chi  TINYINT       NOT NULL,
  mo_ta       NVARCHAR(MAX) NULL
);

-- hoc_phan_id yêu cầu đã học đạt tien_quyet_id
CREATE TABLE hoc_phan_tien_quyet (
  hoc_phan_id    INT NOT NULL,
  tien_quyet_id  INT NOT NULL,
  CONSTRAINT pk_hptq PRIMARY KEY (hoc_phan_id, tien_quyet_id),
  CONSTRAINT fk_tq_hp FOREIGN KEY (hoc_phan_id)   REFERENCES hoc_phan(id),
  CONSTRAINT fk_tq_tq FOREIGN KEY (tien_quyet_id) REFERENCES hoc_phan(id)
);

CREATE TABLE chuong_trinh_hoc_phan (
  chuong_trinh_id  INT     NOT NULL,
  hoc_phan_id      INT     NOT NULL,
  hoc_ky_goi_y     TINYINT NOT NULL,
  bat_buoc         BIT     NOT NULL CONSTRAINT df_cthp_bb DEFAULT 1,
  CONSTRAINT pk_cthp PRIMARY KEY (chuong_trinh_id, hoc_phan_id),
  CONSTRAINT fk_cthp_ct FOREIGN KEY (chuong_trinh_id) REFERENCES chuong_trinh(id),
  CONSTRAINT fk_cthp_hp FOREIGN KEY (hoc_phan_id)     REFERENCES hoc_phan(id)
);

CREATE TABLE hoc_ky (
  id                       INT IDENTITY(1,1) PRIMARY KEY,
  ma_hoc_ky                NVARCHAR(20)  NOT NULL CONSTRAINT uq_hk_ma UNIQUE,  -- vd: 2026-2027-HK2
  ten                      NVARCHAR(100) NOT NULL,
  ngay_bat_dau             DATE          NOT NULL,
  ngay_ket_thuc            DATE          NOT NULL,
  dang_ky_tu               DATETIME2(0)  NULL,     -- NULL = không mở đăng ký
  dang_ky_den              DATETIME2(0)  NULL,
  tin_chi_toi_da           TINYINT       NOT NULL CONSTRAINT df_hk_tc DEFAULT 25,
  tin_chi_toi_da_canh_bao  TINYINT       NOT NULL CONSTRAINT df_hk_tccb DEFAULT 14  -- SV bị cảnh báo học vụ
);

CREATE TABLE lop_hoc_phan (
  id             INT IDENTITY(1,1) PRIMARY KEY,
  ma_lop         NVARCHAR(30)  NOT NULL CONSTRAINT uq_lhp_ma UNIQUE,  -- vd: IT004.02
  hoc_phan_id    INT           NOT NULL,
  hoc_ky_id      INT           NOT NULL,
  giang_vien     NVARCHAR(100) NOT NULL,
  si_so_toi_da   SMALLINT      NOT NULL,
  thu            TINYINT       NOT NULL,          -- 2..7 = Thứ 2..Thứ 7, 8 = Chủ nhật
  tiet_bat_dau   TINYINT       NOT NULL,
  tiet_ket_thuc  TINYINT       NOT NULL,
  phong          NVARCHAR(20)  NOT NULL,
  CONSTRAINT chk_tiet CHECK (tiet_bat_dau <= tiet_ket_thuc),
  CONSTRAINT chk_thu  CHECK (thu BETWEEN 2 AND 8),
  CONSTRAINT fk_lhp_hp FOREIGN KEY (hoc_phan_id) REFERENCES hoc_phan(id),
  CONSTRAINT fk_lhp_hk FOREIGN KEY (hoc_ky_id)   REFERENCES hoc_ky(id)
);

CREATE TABLE dang_ky_hoc_phan (
  id                 INT IDENTITY(1,1) PRIMARY KEY,
  sinh_vien_id       INT          NOT NULL,
  lop_hoc_phan_id    INT          NOT NULL,
  trang_thai         NVARCHAR(20) NOT NULL CONSTRAINT df_dk_trang_thai DEFAULT N'da_dang_ky'
                     CONSTRAINT chk_dk_trang_thai CHECK (trang_thai IN (N'da_dang_ky', N'da_huy')),
  thoi_gian_dang_ky  DATETIME2(0) NOT NULL CONSTRAINT df_dk_tg DEFAULT SYSDATETIME(),
  thoi_gian_huy      DATETIME2(0) NULL,
  CONSTRAINT uq_dk UNIQUE (sinh_vien_id, lop_hoc_phan_id),
  CONSTRAINT fk_dk_sv  FOREIGN KEY (sinh_vien_id)    REFERENCES sinh_vien(id),
  CONSTRAINT fk_dk_lhp FOREIGN KEY (lop_hoc_phan_id) REFERENCES lop_hoc_phan(id)
);

-- Điểm tổng kết = 0.4 * quá trình + 0.6 * thi (quy ước của hệ thống giả lập)
CREATE TABLE ket_qua_hoc_tap (
  id              INT IDENTITY(1,1) PRIMARY KEY,
  sinh_vien_id    INT          NOT NULL,
  hoc_phan_id     INT          NOT NULL,
  hoc_ky_id       INT          NOT NULL,
  diem_qua_trinh  DECIMAL(4,2) NOT NULL,
  diem_thi        DECIMAL(4,2) NOT NULL,
  diem_tong_ket   DECIMAL(4,2) NOT NULL,
  diem_chu        NVARCHAR(2)  NOT NULL,   -- A, B+, B, C+, C, D+, D, F
  diem_he_4       DECIMAL(3,2) NOT NULL,
  lan_hoc         TINYINT      NOT NULL CONSTRAINT df_kq_lan DEFAULT 1,
  CONSTRAINT uq_kq UNIQUE (sinh_vien_id, hoc_phan_id, lan_hoc),
  CONSTRAINT fk_kq_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id),
  CONSTRAINT fk_kq_hp FOREIGN KEY (hoc_phan_id)  REFERENCES hoc_phan(id),
  CONSTRAINT fk_kq_hk FOREIGN KEY (hoc_ky_id)    REFERENCES hoc_ky(id)
);

CREATE TABLE lich_thi (
  id               INT IDENTITY(1,1) PRIMARY KEY,
  lop_hoc_phan_id  INT          NOT NULL,
  ngay_thi         DATE         NOT NULL,
  gio_bat_dau      TIME(0)      NOT NULL,
  phong            NVARCHAR(20) NOT NULL,
  hinh_thuc        NVARCHAR(20) NOT NULL
                   CONSTRAINT chk_lt_hinh_thuc
                   CHECK (hinh_thuc IN (N'tu_luan', N'trac_nghiem', N'van_dap', N'do_an')),
  CONSTRAINT fk_lt_lhp FOREIGN KEY (lop_hoc_phan_id) REFERENCES lop_hoc_phan(id)
);

CREATE TABLE hoc_phi (
  id                INT IDENTITY(1,1) PRIMARY KEY,
  sinh_vien_id      INT           NOT NULL,
  hoc_ky_id         INT           NOT NULL,
  so_tien_phai_nop  DECIMAL(12,0) NOT NULL,
  so_tien_da_nop    DECIMAL(12,0) NOT NULL CONSTRAINT df_hphi_da_nop DEFAULT 0,
  han_nop           DATE          NOT NULL,
  trang_thai        NVARCHAR(20)  NOT NULL CONSTRAINT df_hphi_trang_thai DEFAULT N'chua_nop'
                    CONSTRAINT chk_hphi_trang_thai
                    CHECK (trang_thai IN (N'chua_nop', N'nop_mot_phan', N'da_nop')),
  CONSTRAINT uq_hp UNIQUE (sinh_vien_id, hoc_ky_id),
  CONSTRAINT fk_hphi_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id),
  CONSTRAINT fk_hphi_hk FOREIGN KEY (hoc_ky_id)    REFERENCES hoc_ky(id)
);

CREATE TABLE chung_chi (
  id                INT IDENTITY(1,1) PRIMARY KEY,
  sinh_vien_id      INT           NOT NULL,
  loai              NVARCHAR(20)  NOT NULL
                    CONSTRAINT chk_cc_loai CHECK (loai IN (N'ngoai_ngu', N'tin_hoc', N'gdtc', N'gdqp')),
  ten               NVARCHAR(255) NOT NULL,
  ngay_cap          DATE          NOT NULL,
  trang_thai_duyet  NVARCHAR(20)  NOT NULL CONSTRAINT df_cc_duyet DEFAULT N'cho_duyet'
                    CONSTRAINT chk_cc_duyet
                    CHECK (trang_thai_duyet IN (N'cho_duyet', N'da_duyet', N'tu_choi')),
  CONSTRAINT fk_cc_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id)
);

-- Đơn từ sinh viên gửi (qua cổng hoặc qua trợ lý AI)
CREATE TABLE don_tu (
  id              INT IDENTITY(1,1) PRIMARY KEY,
  ma_don          NVARCHAR(30)  NOT NULL CONSTRAINT uq_don_ma UNIQUE,   -- vd: DT-2026-0001
  sinh_vien_id    INT           NOT NULL,
  loai_don        NVARCHAR(30)  NOT NULL
                  CONSTRAINT chk_don_loai
                  CHECK (loai_don IN (N'giay_xac_nhan_sv', N'bao_luu', N'phuc_khao')),
  noi_dung        NVARCHAR(MAX) NOT NULL CONSTRAINT chk_don_json CHECK (ISJSON(noi_dung) = 1),
  trang_thai      NVARCHAR(20)  NOT NULL CONSTRAINT df_don_trang_thai DEFAULT N'moi_tao'
                  CONSTRAINT chk_don_trang_thai
                  CHECK (trang_thai IN (N'moi_tao', N'dang_xu_ly', N'da_duyet', N'tu_choi', N'hoan_tat')),
  ghi_chu_xu_ly   NVARCHAR(MAX) NULL,
  tao_boi         NVARCHAR(20)  NOT NULL CONSTRAINT df_don_tao_boi DEFAULT N'sinh_vien'
                  CONSTRAINT chk_don_tao_boi CHECK (tao_boi IN (N'sinh_vien', N'tro_ly_ai')),
  created_at      DATETIME2(0)  NOT NULL CONSTRAINT df_don_created DEFAULT SYSDATETIME(),
  updated_at      DATETIME2(0)  NOT NULL CONSTRAINT df_don_updated DEFAULT SYSDATETIME(),
  CONSTRAINT fk_don_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id)
);
CREATE INDEX idx_don_sv ON don_tu (sinh_vien_id, created_at);
GO

-- Thay cho "ON UPDATE CURRENT_TIMESTAMP" của MySQL
CREATE OR ALTER TRIGGER trg_don_tu_updated_at ON don_tu AFTER UPDATE AS
BEGIN
  SET NOCOUNT ON;
  -- Câu UPDATE đã tự đặt updated_at (vd. backend ghi theo DEMO_NOW) thì giữ nguyên giá trị đó
  IF UPDATE(updated_at) RETURN;
  UPDATE d SET updated_at = SYSDATETIME()
  FROM don_tu d JOIN inserted i ON d.id = i.id;
END;
GO
