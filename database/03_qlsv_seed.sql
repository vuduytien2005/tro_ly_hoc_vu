-- =====================================================================
-- 03_qlsv_seed.sql — Dữ liệu mẫu cho hệ thống QLSV giả lập (SQL Server)
-- Dữ liệu THU NHỎ để demo: chương trình chỉ gồm 12 học phần (38 tín chỉ).
-- Có thể sinh thêm dữ liệu bằng script ở Giai đoạn 2.
-- Thời điểm demo giả định: tháng 11/2026, đang học HK1 2026-2027,
-- đang mở đăng ký học phần HK2 2026-2027.
-- LƯU Ý: chuỗi tiếng Việt phải có tiền tố N'...' (Unicode), nếu không sẽ mất dấu.
-- Chạy sau 01_qlsv_schema.sql (script 01 xóa và tạo lại bảng).
-- =====================================================================
-- sqlcmd mặc định tắt QUOTED_IDENTIFIER; SSMS mặc định bật. Bật rõ để chạy được ở cả hai.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE tlhv_qlsv;
GO
SET NOCOUNT ON;

SET IDENTITY_INSERT nganh ON;
INSERT INTO nganh (id, ma_nganh, ten_nganh) VALUES
(1, N'CNPM', N'Công nghệ phần mềm');
SET IDENTITY_INSERT nganh OFF;

SET IDENTITY_INSERT khoa_hoc ON;
INSERT INTO khoa_hoc (id, ma_khoa, nam_bat_dau) VALUES
(1, N'K21', 2021),
(2, N'K22', 2022),
(3, N'K23', 2023);
SET IDENTITY_INSERT khoa_hoc OFF;

SET IDENTITY_INSERT chuong_trinh ON;
INSERT INTO chuong_trinh (id, nganh_id, khoa_hoc_id, tong_tin_chi, gpa_toi_thieu, yeu_cau_ngoai_ngu) VALUES
(1, 1, 1, 38, 2.00, 1),
(2, 1, 2, 38, 2.00, 1),
(3, 1, 3, 38, 2.00, 1);
SET IDENTITY_INSERT chuong_trinh OFF;

SET IDENTITY_INSERT hoc_phan ON;
INSERT INTO hoc_phan (id, ma_hp, ten_hp, so_tin_chi) VALUES
(1,  N'IT001', N'Nhập môn lập trình', 3),
(2,  N'IT002', N'Lập trình hướng đối tượng', 3),
(3,  N'IT003', N'Cấu trúc dữ liệu và giải thuật', 4),
(4,  N'IT004', N'Cơ sở dữ liệu', 3),
(5,  N'IT005', N'Mạng máy tính', 3),
(6,  N'SE101', N'Nhập môn công nghệ phần mềm', 3),
(7,  N'SE102', N'Phân tích thiết kế hệ thống', 3),
(8,  N'SE103', N'Kiểm thử phần mềm', 3),
(9,  N'SE104', N'Quản lý dự án phần mềm', 3),
(10, N'SE105', N'Phát triển ứng dụng web', 4),
(11, N'SE201', N'Trí tuệ nhân tạo ứng dụng', 3),
(12, N'SE202', N'Điện toán đám mây', 3);
SET IDENTITY_INSERT hoc_phan OFF;

-- (học phần, học phần tiên quyết)
INSERT INTO hoc_phan_tien_quyet (hoc_phan_id, tien_quyet_id) VALUES
(2, 1), (3, 2), (4, 1), (7, 6), (8, 6), (9, 6), (10, 2), (11, 3), (12, 5);

-- Chương trình K22 (id 2), rồi sao chép cho K21 và K23
INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc) VALUES
(2, 1, 1, 1), (2, 6, 2, 1), (2, 2, 2, 1), (2, 3, 3, 1), (2, 5, 3, 1),
(2, 4, 4, 1), (2, 7, 5, 1), (2, 8, 6, 1), (2, 9, 6, 1), (2, 10, 7, 1),
(2, 11, 8, 0), (2, 12, 8, 0);

INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc)
SELECT 1, hoc_phan_id, hoc_ky_goi_y, bat_buoc FROM chuong_trinh_hoc_phan WHERE chuong_trinh_id = 2;
INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc)
SELECT 3, hoc_phan_id, hoc_ky_goi_y, bat_buoc FROM chuong_trinh_hoc_phan WHERE chuong_trinh_id = 2;

SET IDENTITY_INSERT hoc_ky ON;
INSERT INTO hoc_ky (id, ma_hoc_ky, ten, ngay_bat_dau, ngay_ket_thuc, dang_ky_tu, dang_ky_den, tin_chi_toi_da, tin_chi_toi_da_canh_bao) VALUES
(1, N'2023-2024-HK1', N'Học kỳ 1 năm học 2023-2024', '2023-09-04', '2024-01-14', NULL, NULL, 25, 14),
(2, N'2023-2024-HK2', N'Học kỳ 2 năm học 2023-2024', '2024-02-19', '2024-06-30', NULL, NULL, 25, 14),
(3, N'2024-2025-HK1', N'Học kỳ 1 năm học 2024-2025', '2024-09-02', '2025-01-12', NULL, NULL, 25, 14),
(4, N'2024-2025-HK2', N'Học kỳ 2 năm học 2024-2025', '2025-02-17', '2025-06-29', NULL, NULL, 25, 14),
(5, N'2025-2026-HK1', N'Học kỳ 1 năm học 2025-2026', '2025-09-01', '2026-01-11', NULL, NULL, 25, 14),
(6, N'2025-2026-HK2', N'Học kỳ 2 năm học 2025-2026', '2026-02-23', '2026-07-05', NULL, NULL, 25, 14),
(7, N'2026-2027-HK1', N'Học kỳ 1 năm học 2026-2027', '2026-08-31', '2027-01-10', NULL, NULL, 25, 14),
(8, N'2026-2027-HK2', N'Học kỳ 2 năm học 2026-2027', '2027-02-22', '2027-07-04', '2026-11-15T08:00:00', '2026-12-20T23:59:59', 25, 14);
SET IDENTITY_INSERT hoc_ky OFF;

SET IDENTITY_INSERT sinh_vien ON;
INSERT INTO sinh_vien (id, ma_sv, ho_ten, email, ngay_sinh, gioi_tinh, nganh_id, khoa_hoc_id, lop, trang_thai) VALUES
(1, N'SV22001', N'Nguyễn Văn An',     N'sv22001@truong.example', '2004-03-12', N'nam', 1, 2, N'22CNPM1', N'dang_hoc'),
(2, N'SV22002', N'Trần Thị Bình',     N'sv22002@truong.example', '2004-07-25', N'nu',  1, 2, N'22CNPM1', N'dang_hoc'),
(3, N'SV21001', N'Lê Minh Cường',     N'sv21001@truong.example', '2003-01-09', N'nam', 1, 1, N'21CNPM1', N'dang_hoc'),
(4, N'SV23001', N'Phạm Thu Dung',     N'sv23001@truong.example', '2005-11-30', N'nu',  1, 3, N'23CNPM1', N'dang_hoc'),
(5, N'SV22003', N'Hoàng Gia Huy',     N'sv22003@truong.example', '2004-05-18', N'nam', 1, 2, N'22CNPM2', N'dang_hoc');
SET IDENTITY_INSERT sinh_vien OFF;

-- Kết quả học tập: diem_tong_ket = 0.4*qt + 0.6*thi
-- Thang chữ: A>=8.5(4.0) B+>=8.0(3.5) B>=7.0(3.0) C+>=6.5(2.5) C>=5.5(2.0) D+>=5.0(1.5) D>=4.0(1.0) F<4.0(0)
INSERT INTO ket_qua_hoc_tap (sinh_vien_id, hoc_phan_id, hoc_ky_id, diem_qua_trinh, diem_thi, diem_tong_ket, diem_chu, diem_he_4, lan_hoc) VALUES
-- SV22001 Nguyễn Văn An: rớt Cơ sở dữ liệu (dùng cho kịch bản học lại)
(1, 1, 1, 8.00, 7.50, 7.70, N'B',  3.00, 1),
(1, 6, 2, 8.50, 8.00, 8.20, N'B+', 3.50, 1),
(1, 2, 2, 7.00, 6.50, 6.70, N'C+', 2.50, 1),
(1, 3, 3, 7.50, 7.00, 7.20, N'B',  3.00, 1),
(1, 5, 3, 6.00, 5.50, 5.70, N'C',  2.00, 1),
(1, 4, 4, 4.00, 2.50, 3.10, N'F',  0.00, 1),
(1, 7, 5, 8.00, 8.50, 8.30, N'B+', 3.50, 1),
(1, 8, 6, 9.00, 8.50, 8.70, N'A',  4.00, 1),
(1, 9, 6, 7.50, 7.00, 7.20, N'B',  3.00, 1),
-- SV22002 Trần Thị Bình
(2, 1, 1, 7.00, 7.00, 7.00, N'B',  3.00, 1),
(2, 6, 2, 6.00, 6.00, 6.00, N'C',  2.00, 1),
(2, 2, 2, 5.00, 5.50, 5.30, N'D+', 1.50, 1),
-- SV21001 Lê Minh Cường: gần tốt nghiệp, còn thiếu SE202
(3, 1, 1, 9.00, 8.50, 8.70, N'A',  4.00, 1),
(3, 2, 2, 8.00, 8.00, 8.00, N'B+', 3.50, 1),
(3, 3, 3, 7.00, 7.50, 7.30, N'B',  3.00, 1),
(3, 4, 2, 8.50, 9.00, 8.80, N'A',  4.00, 1),
(3, 5, 3, 7.00, 6.00, 6.40, N'C',  2.00, 1),
(3, 6, 3, 8.00, 9.00, 8.60, N'A',  4.00, 1),
(3, 7, 4, 7.50, 8.00, 7.80, N'B',  3.00, 1),
(3, 8, 4, 8.00, 7.00, 7.40, N'B',  3.00, 1),
(3, 9, 5, 9.00, 9.00, 9.00, N'A',  4.00, 1),
(3, 10, 5, 8.00, 8.50, 8.30, N'B+', 3.50, 1),
(3, 11, 6, 7.00, 8.00, 7.60, N'B',  3.00, 1),
-- SV23001 Phạm Thu Dung
(4, 1, 3, 8.00, 9.00, 8.60, N'A',  4.00, 1),
(4, 6, 4, 7.00, 7.50, 7.30, N'B',  3.00, 1),
-- SV22003 Hoàng Gia Huy: rớt rồi học lại Nhập môn lập trình
(5, 1, 1, 4.00, 3.00, 3.40, N'F',  0.00, 1),
(5, 1, 2, 6.00, 5.00, 5.40, N'D+', 1.50, 2);

SET IDENTITY_INSERT lop_hoc_phan ON;
INSERT INTO lop_hoc_phan (id, ma_lop, hoc_phan_id, hoc_ky_id, giang_vien, si_so_toi_da, thu, tiet_bat_dau, tiet_ket_thuc, phong) VALUES
-- Học kỳ đang học (HK1 2026-2027)
(1, N'SE105.01', 10, 7, N'ThS. Nguyễn Hữu Phước', 60, 3, 1, 4, N'A1.203'),
-- Học kỳ đang mở đăng ký (HK2 2026-2027)
(2, N'IT004.02', 4,  8, N'TS. Lê Thanh Hà',        60, 2, 1, 3, N'B2.101'),
(3, N'IT004.03', 4,  8, N'TS. Lê Thanh Hà',        60, 5, 7, 9, N'B2.101'),
(4, N'SE201.01', 11, 8, N'TS. Đặng Quốc Bảo',      50, 3, 7, 9, N'A1.305'),
(5, N'SE202.01', 12, 8, N'ThS. Vũ Minh Khang',      2, 4, 1, 3, N'A2.110'),  -- sĩ số 2: đã đầy (kịch bản lớp hết chỗ)
(6, N'SE105.02', 10, 8, N'ThS. Nguyễn Hữu Phước', 60, 2, 1, 4, N'A1.203'),  -- trùng lịch với IT004.02 (kịch bản trùng lịch)
(7, N'SE104.01', 9,  8, N'ThS. Trần Bảo Ngọc',     55, 6, 1, 3, N'B1.204');
SET IDENTITY_INSERT lop_hoc_phan OFF;

INSERT INTO dang_ky_hoc_phan (sinh_vien_id, lop_hoc_phan_id, trang_thai) VALUES
(1, 1, N'da_dang_ky'),
(2, 5, N'da_dang_ky'),
(4, 5, N'da_dang_ky');

INSERT INTO lich_thi (lop_hoc_phan_id, ngay_thi, gio_bat_dau, phong, hinh_thuc) VALUES
(1, '2027-01-05', '07:30:00', N'A1.203', N'tu_luan');

INSERT INTO hoc_phi (sinh_vien_id, hoc_ky_id, so_tien_phai_nop, so_tien_da_nop, han_nop, trang_thai) VALUES
(1, 7,  9800000, 9800000, '2026-10-15', N'da_nop'),
(2, 7,  9800000, 5000000, '2026-10-15', N'nop_mot_phan'),
(3, 7,  4900000, 4900000, '2026-10-15', N'da_nop'),
(4, 7, 10500000, 10500000,'2026-10-15', N'da_nop'),
(5, 7,  9800000,       0, '2026-10-15', N'chua_nop');

INSERT INTO chung_chi (sinh_vien_id, loai, ten, ngay_cap, trang_thai_duyet) VALUES
(1, N'gdtc',      N'Chứng chỉ Giáo dục thể chất',            '2024-06-20', N'da_duyet'),
(1, N'gdqp',      N'Chứng chỉ Giáo dục quốc phòng - an ninh', '2023-08-30', N'da_duyet'),
(3, N'gdtc',      N'Chứng chỉ Giáo dục thể chất',            '2023-06-15', N'da_duyet'),
(3, N'gdqp',      N'Chứng chỉ Giáo dục quốc phòng - an ninh', '2022-08-30', N'da_duyet'),
(3, N'ngoai_ngu', N'TOEIC 600',                               '2025-12-10', N'da_duyet');

INSERT INTO don_tu (ma_don, sinh_vien_id, loai_don, noi_dung, trang_thai, ghi_chu_xu_ly, tao_boi) VALUES
(N'DT-2026-0001', 3, N'giay_xac_nhan_sv',
 N'{"muc_dich": "Bổ sung hồ sơ xin việc", "so_ban": 1, "noi_nhan": "Phòng Công tác sinh viên"}',
 N'hoan_tat', N'Đã trả giấy xác nhận.', N'sinh_vien');
GO
