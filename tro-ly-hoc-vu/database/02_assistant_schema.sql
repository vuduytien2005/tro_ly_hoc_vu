-- =====================================================================
-- 02_assistant_schema.sql
-- CSDL "assistant": dữ liệu của trợ lý AI
-- (tài khoản, hội thoại, nhật ký Agent, cấu hình MCP, văn bản RAG)
-- MySQL 8.x
-- =====================================================================

CREATE DATABASE IF NOT EXISTS assistant
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE assistant;

SET FOREIGN_KEY_CHECKS = 0;
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
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Tài khoản
-- ---------------------------------------------------------------------
CREATE TABLE nguoi_dung (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(255) NOT NULL UNIQUE,
  mat_khau_hash VARCHAR(255) NOT NULL,
  ho_ten        VARCHAR(100) NOT NULL,
  vai_tro       ENUM('sinh_vien','admin') NOT NULL,
  ma_sv         VARCHAR(20)  NULL UNIQUE,   -- liên kết sang qlsv.sinh_vien.ma_sv (chỉ với sinh viên)
  ma_khoa       VARCHAR(10)  NULL,          -- K22... dùng để lọc phiên bản quy chế
  dang_hoat_dong TINYINT(1)  NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Hội thoại
-- ---------------------------------------------------------------------
CREATE TABLE hoi_thoai (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  nguoi_dung_id INT          NOT NULL,
  tieu_de       VARCHAR(255) NOT NULL DEFAULT 'Cuộc trò chuyện mới',
  kenh          ENUM('web','zalo') NOT NULL DEFAULT 'web',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_ht_nd (nguoi_dung_id, updated_at),
  CONSTRAINT fk_ht_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id)
) ENGINE=InnoDB;

-- vai_tro 'tool' lưu kết quả công cụ để dựng lại ngữ cảnh cho LLM
CREATE TABLE tin_nhan (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  hoi_thoai_id  INT          NOT NULL,
  vai_tro       ENUM('user','assistant','tool') NOT NULL,
  noi_dung      MEDIUMTEXT   NOT NULL,
  tool_call_id  VARCHAR(100) NULL,          -- với vai_tro = tool
  tool_calls    JSON         NULL,          -- với vai_tro = assistant có gọi công cụ
  trich_dan     JSON         NULL,          -- [{so, van_ban, dieu, khoan, trang, doan_id}]
  so_token_vao  INT          NULL,
  so_token_ra   INT          NULL,
  thoi_gian_ms  INT          NULL,
  created_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_tn_ht (hoi_thoai_id, created_at),
  CONSTRAINT fk_tn_ht FOREIGN KEY (hoi_thoai_id) REFERENCES hoi_thoai(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Cấu hình MCP
-- ---------------------------------------------------------------------
CREATE TABLE mcp_server (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  ten        VARCHAR(50)  NOT NULL UNIQUE,   -- dao_tao, ctsv, tai_chinh, quy_che
  mo_ta      VARCHAR(255) NOT NULL,
  dia_chi    VARCHAR(255) NOT NULL,          -- vd: http://127.0.0.1:9101/mcp
  bat        TINYINT(1)   NOT NULL DEFAULT 1
) ENGINE=InnoDB;

-- Danh mục công cụ + chính sách quyền. Đồng bộ với tool thật của MCP server khi khởi động.
CREATE TABLE cong_cu (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  mcp_server_id  INT          NOT NULL,
  ten            VARCHAR(100) NOT NULL,
  mo_ta          VARCHAR(500) NOT NULL,
  muc_rui_ro     ENUM('doc','ghi','nhay_cam') NOT NULL,
  can_xac_nhan   TINYINT(1)   NOT NULL DEFAULT 0,
  bat            TINYINT(1)   NOT NULL DEFAULT 1,
  UNIQUE KEY uq_cc (mcp_server_id, ten),
  CONSTRAINT fk_cc_server FOREIGN KEY (mcp_server_id) REFERENCES mcp_server(id)
) ENGINE=InnoDB;

-- Nhật ký MỌI lần Agent gọi công cụ (phục vụ quản trị + thực nghiệm Chương 4)
CREATE TABLE luot_goi_cong_cu (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  hoi_thoai_id   INT          NULL,
  nguoi_dung_id  INT          NOT NULL,
  mcp_server     VARCHAR(50)  NOT NULL,
  ten_cong_cu    VARCHAR(100) NOT NULL,
  tham_so        JSON         NOT NULL,      -- SAU khi tiêm ngữ cảnh
  tham_so_llm    JSON         NULL,          -- tham số gốc do LLM sinh (để phân tích)
  ket_qua        JSON         NULL,
  trang_thai     ENUM('thanh_cong','loi','bi_tu_choi','cho_xac_nhan','da_huy') NOT NULL,
  ly_do          VARCHAR(500) NULL,          -- lý do lỗi / từ chối
  thoi_gian_ms   INT          NULL,
  created_at     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_lg_time (created_at),
  INDEX idx_lg_nd (nguoi_dung_id, created_at),
  INDEX idx_lg_tool (ten_cong_cu, trang_thai),
  CONSTRAINT fk_lg_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id),
  CONSTRAINT fk_lg_ht FOREIGN KEY (hoi_thoai_id) REFERENCES hoi_thoai(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Hành động ghi/nhạy cảm đang chờ sinh viên xác nhận
CREATE TABLE hanh_dong_cho_xac_nhan (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  ma             CHAR(36)     NOT NULL UNIQUE,   -- UUID gửi cho frontend
  hoi_thoai_id   INT          NOT NULL,
  nguoi_dung_id  INT          NOT NULL,
  luot_goi_id    BIGINT       NOT NULL,          -- bản ghi 'cho_xac_nhan' trong nhật ký
  mcp_server     VARCHAR(50)  NOT NULL,
  ten_cong_cu    VARCHAR(100) NOT NULL,
  tham_so        JSON         NOT NULL,
  mo_ta          TEXT         NOT NULL,          -- mô tả dễ hiểu hiển thị trên thẻ xác nhận
  trang_thai     ENUM('cho','da_xac_nhan','da_huy','het_han') NOT NULL DEFAULT 'cho',
  het_han_luc    DATETIME     NOT NULL,
  xu_ly_luc      DATETIME     NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_hd_nd (nguoi_dung_id, trang_thai),
  CONSTRAINT fk_hd_ht FOREIGN KEY (hoi_thoai_id)  REFERENCES hoi_thoai(id) ON DELETE CASCADE,
  CONSTRAINT fk_hd_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id),
  CONSTRAINT fk_hd_lg FOREIGN KEY (luot_goi_id)   REFERENCES luot_goi_cong_cu(id)
) ENGINE=InnoDB;

CREATE TABLE danh_gia_cau_tra_loi (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  tin_nhan_id   INT        NOT NULL,
  nguoi_dung_id INT        NOT NULL,
  diem          TINYINT    NOT NULL,      -- 1 = hữu ích, -1 = chưa đúng
  gop_y         TEXT       NULL,
  created_at    DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_dg (tin_nhan_id, nguoi_dung_id),
  CONSTRAINT chk_diem CHECK (diem IN (-1, 1)),
  CONSTRAINT fk_dg_tn FOREIGN KEY (tin_nhan_id)   REFERENCES tin_nhan(id) ON DELETE CASCADE,
  CONSTRAINT fk_dg_nd FOREIGN KEY (nguoi_dung_id) REFERENCES nguoi_dung(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Văn bản cho RAG
-- ---------------------------------------------------------------------
-- Phiên bản áp dụng theo khóa: ap_dung_tu_khoa..ap_dung_den_khoa là số năm 2 chữ số
-- (vd 21..99 nghĩa là áp dụng từ K21 trở đi). NULL = áp dụng cho mọi khóa.
CREATE TABLE van_ban (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  ten               VARCHAR(255) NOT NULL,
  loai              ENUM('quy_che','so_tay','quy_dinh','huong_dan','thong_bao') NOT NULL,
  phien_ban         VARCHAR(50)  NOT NULL,       -- vd: 2023
  ap_dung_tu_khoa   TINYINT      NULL,
  ap_dung_den_khoa  TINYINT      NULL,
  ngay_hieu_luc     DATE         NULL,
  ten_tep           VARCHAR(255) NOT NULL,
  duong_dan_tep     VARCHAR(500) NOT NULL,
  trang_thai        ENUM('dang_xu_ly','da_lap_chi_muc','loi') NOT NULL DEFAULT 'dang_xu_ly',
  chien_luoc_chunk  ENUM('theo_dieu','co_dinh','ngu_nghia') NOT NULL DEFAULT 'theo_dieu',
  so_doan           INT          NOT NULL DEFAULT 0,
  loi               TEXT         NULL,
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Mỗi đoạn (chunk). Vector nằm trong ChromaDB với id = vector_id.
-- FULLTEXT dùng cho tìm theo từ khóa (nửa còn lại của hybrid search).
-- LƯU Ý: đặt innodb_ft_min_token_size=1 trong my.ini để không bỏ sót âm tiết tiếng Việt ngắn.
CREATE TABLE doan_van_ban (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  van_ban_id  INT          NOT NULL,
  thu_tu      INT          NOT NULL,
  chuong      VARCHAR(255) NULL,
  dieu        VARCHAR(255) NULL,      -- vd: "Điều 12. Đăng ký học phần"
  khoan       VARCHAR(50)  NULL,
  trang       SMALLINT     NULL,
  noi_dung    MEDIUMTEXT   NOT NULL,
  so_token    INT          NULL,
  vector_id   VARCHAR(64)  NOT NULL UNIQUE,
  INDEX idx_dvb_vb (van_ban_id, thu_tu),
  FULLTEXT INDEX ft_noi_dung (noi_dung),
  CONSTRAINT fk_dvb_vb FOREIGN KEY (van_ban_id) REFERENCES van_ban(id) ON DELETE CASCADE
) ENGINE=InnoDB;
