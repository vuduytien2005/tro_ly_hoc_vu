-- =====================================================================
-- 01_qlsv_schema.sql
-- CSDL "qlsv": Hệ thống quản lý sinh viên GIẢ LẬP
-- Đóng vai hệ thống thật của trường để AI Agent thao tác qua MCP.
-- MySQL 8.x
-- =====================================================================

CREATE DATABASE IF NOT EXISTS qlsv
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE qlsv;

SET FOREIGN_KEY_CHECKS = 0;
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
SET FOREIGN_KEY_CHECKS = 1;

-- Ngành đào tạo
CREATE TABLE nganh (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  ma_nganh   VARCHAR(20)  NOT NULL UNIQUE,
  ten_nganh  VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- Khóa tuyển sinh (K21, K22...) – quyết định phiên bản quy chế áp dụng
CREATE TABLE khoa_hoc (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  ma_khoa      VARCHAR(10) NOT NULL UNIQUE,
  nam_bat_dau  SMALLINT    NOT NULL
) ENGINE=InnoDB;

-- Chương trình đào tạo của một ngành cho một khóa
CREATE TABLE chuong_trinh (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  nganh_id           INT          NOT NULL,
  khoa_hoc_id        INT          NOT NULL,
  tong_tin_chi       SMALLINT     NOT NULL,
  gpa_toi_thieu      DECIMAL(3,2) NOT NULL DEFAULT 2.00,
  yeu_cau_ngoai_ngu  TINYINT(1)   NOT NULL DEFAULT 1,
  UNIQUE KEY uq_ct (nganh_id, khoa_hoc_id),
  CONSTRAINT fk_ct_nganh FOREIGN KEY (nganh_id)    REFERENCES nganh(id),
  CONSTRAINT fk_ct_khoa  FOREIGN KEY (khoa_hoc_id) REFERENCES khoa_hoc(id)
) ENGINE=InnoDB;

CREATE TABLE sinh_vien (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  ma_sv        VARCHAR(20)  NOT NULL UNIQUE,
  ho_ten       VARCHAR(100) NOT NULL,
  email        VARCHAR(255) NOT NULL UNIQUE,
  ngay_sinh    DATE         NOT NULL,
  gioi_tinh    ENUM('nam','nu','khac') NOT NULL,
  nganh_id     INT          NOT NULL,
  khoa_hoc_id  INT          NOT NULL,
  lop          VARCHAR(20)  NOT NULL,
  trang_thai   ENUM('dang_hoc','bao_luu','thoi_hoc','tot_nghiep') NOT NULL DEFAULT 'dang_hoc',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sv_nganh FOREIGN KEY (nganh_id)    REFERENCES nganh(id),
  CONSTRAINT fk_sv_khoa  FOREIGN KEY (khoa_hoc_id) REFERENCES khoa_hoc(id)
) ENGINE=InnoDB;

CREATE TABLE hoc_phan (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  ma_hp       VARCHAR(20)  NOT NULL UNIQUE,
  ten_hp      VARCHAR(255) NOT NULL,
  so_tin_chi  TINYINT      NOT NULL,
  mo_ta       TEXT         NULL
) ENGINE=InnoDB;

-- hoc_phan_id yêu cầu đã học đạt tien_quyet_id
CREATE TABLE hoc_phan_tien_quyet (
  hoc_phan_id    INT NOT NULL,
  tien_quyet_id  INT NOT NULL,
  PRIMARY KEY (hoc_phan_id, tien_quyet_id),
  CONSTRAINT fk_tq_hp FOREIGN KEY (hoc_phan_id)   REFERENCES hoc_phan(id),
  CONSTRAINT fk_tq_tq FOREIGN KEY (tien_quyet_id) REFERENCES hoc_phan(id)
) ENGINE=InnoDB;

CREATE TABLE chuong_trinh_hoc_phan (
  chuong_trinh_id  INT        NOT NULL,
  hoc_phan_id      INT        NOT NULL,
  hoc_ky_goi_y     TINYINT    NOT NULL,
  bat_buoc         TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (chuong_trinh_id, hoc_phan_id),
  CONSTRAINT fk_cthp_ct FOREIGN KEY (chuong_trinh_id) REFERENCES chuong_trinh(id),
  CONSTRAINT fk_cthp_hp FOREIGN KEY (hoc_phan_id)     REFERENCES hoc_phan(id)
) ENGINE=InnoDB;

CREATE TABLE hoc_ky (
  id                       INT AUTO_INCREMENT PRIMARY KEY,
  ma_hoc_ky                VARCHAR(20)  NOT NULL UNIQUE,   -- vd: 2026-2027-HK2
  ten                      VARCHAR(100) NOT NULL,
  ngay_bat_dau             DATE         NOT NULL,
  ngay_ket_thuc            DATE         NOT NULL,
  dang_ky_tu               DATETIME     NULL,              -- NULL = không mở đăng ký
  dang_ky_den              DATETIME     NULL,
  tin_chi_toi_da           TINYINT      NOT NULL DEFAULT 25,
  tin_chi_toi_da_canh_bao  TINYINT      NOT NULL DEFAULT 14  -- áp dụng cho SV bị cảnh báo học vụ
) ENGINE=InnoDB;

CREATE TABLE lop_hoc_phan (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  ma_lop         VARCHAR(30)  NOT NULL UNIQUE,  -- vd: IT004.02
  hoc_phan_id    INT          NOT NULL,
  hoc_ky_id      INT          NOT NULL,
  giang_vien     VARCHAR(100) NOT NULL,
  si_so_toi_da   SMALLINT     NOT NULL,
  thu            TINYINT      NOT NULL,          -- 2..7 = Thứ 2..Thứ 7, 8 = Chủ nhật
  tiet_bat_dau   TINYINT      NOT NULL,
  tiet_ket_thuc  TINYINT      NOT NULL,
  phong          VARCHAR(20)  NOT NULL,
  CONSTRAINT chk_tiet CHECK (tiet_bat_dau <= tiet_ket_thuc),
  CONSTRAINT chk_thu  CHECK (thu BETWEEN 2 AND 8),
  CONSTRAINT fk_lhp_hp FOREIGN KEY (hoc_phan_id) REFERENCES hoc_phan(id),
  CONSTRAINT fk_lhp_hk FOREIGN KEY (hoc_ky_id)   REFERENCES hoc_ky(id)
) ENGINE=InnoDB;

CREATE TABLE dang_ky_hoc_phan (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  sinh_vien_id       INT      NOT NULL,
  lop_hoc_phan_id    INT      NOT NULL,
  trang_thai         ENUM('da_dang_ky','da_huy') NOT NULL DEFAULT 'da_dang_ky',
  thoi_gian_dang_ky  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  thoi_gian_huy      DATETIME NULL,
  UNIQUE KEY uq_dk (sinh_vien_id, lop_hoc_phan_id),
  CONSTRAINT fk_dk_sv  FOREIGN KEY (sinh_vien_id)    REFERENCES sinh_vien(id),
  CONSTRAINT fk_dk_lhp FOREIGN KEY (lop_hoc_phan_id) REFERENCES lop_hoc_phan(id)
) ENGINE=InnoDB;

-- Điểm tổng kết = 0.4 * quá trình + 0.6 * thi (quy ước của hệ thống giả lập)
CREATE TABLE ket_qua_hoc_tap (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  sinh_vien_id    INT          NOT NULL,
  hoc_phan_id     INT          NOT NULL,
  hoc_ky_id       INT          NOT NULL,
  diem_qua_trinh  DECIMAL(4,2) NOT NULL,
  diem_thi        DECIMAL(4,2) NOT NULL,
  diem_tong_ket   DECIMAL(4,2) NOT NULL,
  diem_chu        VARCHAR(2)   NOT NULL,   -- A, B+, B, C+, C, D+, D, F
  diem_he_4       DECIMAL(3,2) NOT NULL,
  lan_hoc         TINYINT      NOT NULL DEFAULT 1,
  UNIQUE KEY uq_kq (sinh_vien_id, hoc_phan_id, lan_hoc),
  CONSTRAINT fk_kq_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id),
  CONSTRAINT fk_kq_hp FOREIGN KEY (hoc_phan_id)  REFERENCES hoc_phan(id),
  CONSTRAINT fk_kq_hk FOREIGN KEY (hoc_ky_id)    REFERENCES hoc_ky(id)
) ENGINE=InnoDB;

CREATE TABLE lich_thi (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  lop_hoc_phan_id  INT         NOT NULL,
  ngay_thi         DATE        NOT NULL,
  gio_bat_dau      TIME        NOT NULL,
  phong            VARCHAR(20) NOT NULL,
  hinh_thuc        ENUM('tu_luan','trac_nghiem','van_dap','do_an') NOT NULL,
  CONSTRAINT fk_lt_lhp FOREIGN KEY (lop_hoc_phan_id) REFERENCES lop_hoc_phan(id)
) ENGINE=InnoDB;

CREATE TABLE hoc_phi (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  sinh_vien_id      INT           NOT NULL,
  hoc_ky_id         INT           NOT NULL,
  so_tien_phai_nop  DECIMAL(12,0) NOT NULL,
  so_tien_da_nop    DECIMAL(12,0) NOT NULL DEFAULT 0,
  han_nop           DATE          NOT NULL,
  trang_thai        ENUM('chua_nop','nop_mot_phan','da_nop') NOT NULL DEFAULT 'chua_nop',
  UNIQUE KEY uq_hp (sinh_vien_id, hoc_ky_id),
  CONSTRAINT fk_hphi_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id),
  CONSTRAINT fk_hphi_hk FOREIGN KEY (hoc_ky_id)    REFERENCES hoc_ky(id)
) ENGINE=InnoDB;

CREATE TABLE chung_chi (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  sinh_vien_id      INT          NOT NULL,
  loai              ENUM('ngoai_ngu','tin_hoc','gdtc','gdqp') NOT NULL,
  ten               VARCHAR(255) NOT NULL,
  ngay_cap          DATE         NOT NULL,
  trang_thai_duyet  ENUM('cho_duyet','da_duyet','tu_choi') NOT NULL DEFAULT 'cho_duyet',
  CONSTRAINT fk_cc_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id)
) ENGINE=InnoDB;

-- Đơn từ sinh viên gửi (qua cổng hoặc qua trợ lý AI)
CREATE TABLE don_tu (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  ma_don          VARCHAR(30) NOT NULL UNIQUE,   -- vd: DT-2026-0001
  sinh_vien_id    INT         NOT NULL,
  loai_don        ENUM('giay_xac_nhan_sv','bao_luu','phuc_khao') NOT NULL,
  noi_dung        JSON        NOT NULL,
  trang_thai      ENUM('moi_tao','dang_xu_ly','da_duyet','tu_choi','hoan_tat') NOT NULL DEFAULT 'moi_tao',
  ghi_chu_xu_ly   TEXT        NULL,
  tao_boi         ENUM('sinh_vien','tro_ly_ai') NOT NULL DEFAULT 'sinh_vien',
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_don_sv (sinh_vien_id, created_at),
  CONSTRAINT fk_don_sv FOREIGN KEY (sinh_vien_id) REFERENCES sinh_vien(id)
) ENGINE=InnoDB;
