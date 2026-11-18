-- =====================================================================
-- 03_qlsv_seed.sql — Dữ liệu mẫu cho hệ thống QLSV giả lập
-- Dữ liệu THU NHỎ để demo: chương trình chỉ gồm 12 học phần (38 tín chỉ).
-- Có thể sinh thêm dữ liệu bằng script ở Giai đoạn 2.
-- Thời điểm demo giả định: tháng 11/2026, đang học HK1 2026-2027,
-- đang mở đăng ký học phần HK2 2026-2027.
-- =====================================================================
USE qlsv;

INSERT INTO nganh (id, ma_nganh, ten_nganh) VALUES
(1, 'CNPM', 'Công nghệ phần mềm');

INSERT INTO khoa_hoc (id, ma_khoa, nam_bat_dau) VALUES
(1, 'K21', 2021),
(2, 'K22', 2022),
(3, 'K23', 2023);

INSERT INTO chuong_trinh (id, nganh_id, khoa_hoc_id, tong_tin_chi, gpa_toi_thieu, yeu_cau_ngoai_ngu) VALUES
(1, 1, 1, 38, 2.00, 1),
(2, 1, 2, 38, 2.00, 1),
(3, 1, 3, 38, 2.00, 1);

INSERT INTO hoc_phan (id, ma_hp, ten_hp, so_tin_chi) VALUES
(1,  'IT001', 'Nhập môn lập trình', 3),
(2,  'IT002', 'Lập trình hướng đối tượng', 3),
(3,  'IT003', 'Cấu trúc dữ liệu và giải thuật', 4),
(4,  'IT004', 'Cơ sở dữ liệu', 3),
(5,  'IT005', 'Mạng máy tính', 3),
(6,  'SE101', 'Nhập môn công nghệ phần mềm', 3),
(7,  'SE102', 'Phân tích thiết kế hệ thống', 3),
(8,  'SE103', 'Kiểm thử phần mềm', 3),
(9,  'SE104', 'Quản lý dự án phần mềm', 3),
(10, 'SE105', 'Phát triển ứng dụng web', 4),
(11, 'SE201', 'Trí tuệ nhân tạo ứng dụng', 3),
(12, 'SE202', 'Điện toán đám mây', 3);

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

INSERT INTO hoc_ky (id, ma_hoc_ky, ten, ngay_bat_dau, ngay_ket_thuc, dang_ky_tu, dang_ky_den, tin_chi_toi_da, tin_chi_toi_da_canh_bao) VALUES
(1, '2023-2024-HK1', 'Học kỳ 1 năm học 2023-2024', '2023-09-04', '2024-01-14', NULL, NULL, 25, 14),
(2, '2023-2024-HK2', 'Học kỳ 2 năm học 2023-2024', '2024-02-19', '2024-06-30', NULL, NULL, 25, 14),
(3, '2024-2025-HK1', 'Học kỳ 1 năm học 2024-2025', '2024-09-02', '2025-01-12', NULL, NULL, 25, 14),
(4, '2024-2025-HK2', 'Học kỳ 2 năm học 2024-2025', '2025-02-17', '2025-06-29', NULL, NULL, 25, 14),
(5, '2025-2026-HK1', 'Học kỳ 1 năm học 2025-2026', '2025-09-01', '2026-01-11', NULL, NULL, 25, 14),
(6, '2025-2026-HK2', 'Học kỳ 2 năm học 2025-2026', '2026-02-23', '2026-07-05', NULL, NULL, 25, 14),
(7, '2026-2027-HK1', 'Học kỳ 1 năm học 2026-2027', '2026-08-31', '2027-01-10', NULL, NULL, 25, 14),
(8, '2026-2027-HK2', 'Học kỳ 2 năm học 2026-2027', '2027-02-22', '2027-07-04', '2026-11-15 08:00:00', '2026-12-20 23:59:59', 25, 14);

INSERT INTO sinh_vien (id, ma_sv, ho_ten, email, ngay_sinh, gioi_tinh, nganh_id, khoa_hoc_id, lop, trang_thai) VALUES
(1, 'SV22001', 'Nguyễn Văn An',     'sv22001@truong.example', '2004-03-12', 'nam', 1, 2, '22CNPM1', 'dang_hoc'),
(2, 'SV22002', 'Trần Thị Bình',     'sv22002@truong.example', '2004-07-25', 'nu',  1, 2, '22CNPM1', 'dang_hoc'),
(3, 'SV21001', 'Lê Minh Cường',     'sv21001@truong.example', '2003-01-09', 'nam', 1, 1, '21CNPM1', 'dang_hoc'),
(4, 'SV23001', 'Phạm Thu Dung',     'sv23001@truong.example', '2005-11-30', 'nu',  1, 3, '23CNPM1', 'dang_hoc'),
(5, 'SV22003', 'Hoàng Gia Huy',     'sv22003@truong.example', '2004-05-18', 'nam', 1, 2, '22CNPM2', 'dang_hoc');

-- Kết quả học tập: diem_tong_ket = 0.4*qt + 0.6*thi
-- Thang chữ: A>=8.5(4.0) B+>=8.0(3.5) B>=7.0(3.0) C+>=6.5(2.5) C>=5.5(2.0) D+>=5.0(1.5) D>=4.0(1.0) F<4.0(0)
INSERT INTO ket_qua_hoc_tap (sinh_vien_id, hoc_phan_id, hoc_ky_id, diem_qua_trinh, diem_thi, diem_tong_ket, diem_chu, diem_he_4, lan_hoc) VALUES
-- SV22001 Nguyễn Văn An: rớt Cơ sở dữ liệu (dùng cho kịch bản học lại)
(1, 1, 1, 8.00, 7.50, 7.70, 'B',  3.00, 1),
(1, 6, 2, 8.50, 8.00, 8.20, 'B+', 3.50, 1),
(1, 2, 2, 7.00, 6.50, 6.70, 'C+', 2.50, 1),
(1, 3, 3, 7.50, 7.00, 7.20, 'B',  3.00, 1),
(1, 5, 3, 6.00, 5.50, 5.70, 'C',  2.00, 1),
(1, 4, 4, 4.00, 2.50, 3.10, 'F',  0.00, 1),
(1, 7, 5, 8.00, 8.50, 8.30, 'B+', 3.50, 1),
(1, 8, 6, 9.00, 8.50, 8.70, 'A',  4.00, 1),
(1, 9, 6, 7.50, 7.00, 7.20, 'B',  3.00, 1),
-- SV22002 Trần Thị Bình
(2, 1, 1, 7.00, 7.00, 7.00, 'B',  3.00, 1),
(2, 6, 2, 6.00, 6.00, 6.00, 'C',  2.00, 1),
(2, 2, 2, 5.00, 5.50, 5.30, 'D+', 1.50, 1),
-- SV21001 Lê Minh Cường: gần tốt nghiệp, còn thiếu SE202
(3, 1, 1, 9.00, 8.50, 8.70, 'A',  4.00, 1),
(3, 2, 2, 8.00, 8.00, 8.00, 'B+', 3.50, 1),
(3, 3, 3, 7.00, 7.50, 7.30, 'B',  3.00, 1),
(3, 4, 2, 8.50, 9.00, 8.80, 'A',  4.00, 1),
(3, 5, 3, 7.00, 6.00, 6.40, 'C',  2.00, 1),
(3, 6, 3, 8.00, 9.00, 8.60, 'A',  4.00, 1),
(3, 7, 4, 7.50, 8.00, 7.80, 'B',  3.00, 1),
(3, 8, 4, 8.00, 7.00, 7.40, 'B',  3.00, 1),
(3, 9, 5, 9.00, 9.00, 9.00, 'A',  4.00, 1),
(3, 10, 5, 8.00, 8.50, 8.30, 'B+', 3.50, 1),
(3, 11, 6, 7.00, 8.00, 7.60, 'B',  3.00, 1),
-- SV23001 Phạm Thu Dung
(4, 1, 3, 8.00, 9.00, 8.60, 'A',  4.00, 1),
(4, 6, 4, 7.00, 7.50, 7.30, 'B',  3.00, 1),
-- SV22003 Hoàng Gia Huy: rớt rồi học lại Nhập môn lập trình
(5, 1, 1, 4.00, 3.00, 3.40, 'F',  0.00, 1),
(5, 1, 2, 6.00, 5.00, 5.40, 'D+', 1.50, 2);

INSERT INTO lop_hoc_phan (id, ma_lop, hoc_phan_id, hoc_ky_id, giang_vien, si_so_toi_da, thu, tiet_bat_dau, tiet_ket_thuc, phong) VALUES
-- Học kỳ đang học (HK1 2026-2027)
(1, 'SE105.01', 10, 7, 'ThS. Nguyễn Hữu Phước', 60, 3, 1, 4, 'A1.203'),
-- Học kỳ đang mở đăng ký (HK2 2026-2027)
(2, 'IT004.02', 4,  8, 'TS. Lê Thanh Hà',        60, 2, 1, 3, 'B2.101'),
(3, 'IT004.03', 4,  8, 'TS. Lê Thanh Hà',        60, 5, 7, 9, 'B2.101'),
(4, 'SE201.01', 11, 8, 'TS. Đặng Quốc Bảo',      50, 3, 7, 9, 'A1.305'),
(5, 'SE202.01', 12, 8, 'ThS. Vũ Minh Khang',      2, 4, 1, 3, 'A2.110'),  -- sĩ số 2: đã đầy (kịch bản lớp hết chỗ)
(6, 'SE105.02', 10, 8, 'ThS. Nguyễn Hữu Phước', 60, 2, 1, 4, 'A1.203'),  -- trùng lịch với IT004.02 (kịch bản trùng lịch)
(7, 'SE104.01', 9,  8, 'ThS. Trần Bảo Ngọc',     55, 6, 1, 3, 'B1.204');

INSERT INTO dang_ky_hoc_phan (sinh_vien_id, lop_hoc_phan_id, trang_thai) VALUES
(1, 1, 'da_dang_ky'),
(2, 5, 'da_dang_ky'),
(4, 5, 'da_dang_ky');

INSERT INTO lich_thi (lop_hoc_phan_id, ngay_thi, gio_bat_dau, phong, hinh_thuc) VALUES
(1, '2027-01-05', '07:30:00', 'A1.203', 'tu_luan');

INSERT INTO hoc_phi (sinh_vien_id, hoc_ky_id, so_tien_phai_nop, so_tien_da_nop, han_nop, trang_thai) VALUES
(1, 7,  9800000, 9800000, '2026-10-15', 'da_nop'),
(2, 7,  9800000, 5000000, '2026-10-15', 'nop_mot_phan'),
(3, 7,  4900000, 4900000, '2026-10-15', 'da_nop'),
(4, 7, 10500000, 10500000,'2026-10-15', 'da_nop'),
(5, 7,  9800000,       0, '2026-10-15', 'chua_nop');

INSERT INTO chung_chi (sinh_vien_id, loai, ten, ngay_cap, trang_thai_duyet) VALUES
(1, 'gdtc',      'Chứng chỉ Giáo dục thể chất',            '2024-06-20', 'da_duyet'),
(1, 'gdqp',      'Chứng chỉ Giáo dục quốc phòng - an ninh', '2023-08-30', 'da_duyet'),
(3, 'gdtc',      'Chứng chỉ Giáo dục thể chất',            '2023-06-15', 'da_duyet'),
(3, 'gdqp',      'Chứng chỉ Giáo dục quốc phòng - an ninh', '2022-08-30', 'da_duyet'),
(3, 'ngoai_ngu', 'TOEIC 600',                               '2025-12-10', 'da_duyet');

INSERT INTO don_tu (ma_don, sinh_vien_id, loai_don, noi_dung, trang_thai, ghi_chu_xu_ly, tao_boi) VALUES
('DT-2026-0001', 3, 'giay_xac_nhan_sv',
 JSON_OBJECT('muc_dich', 'Bổ sung hồ sơ xin việc', 'so_ban', 1, 'noi_nhan', 'Phòng Công tác sinh viên'),
 'hoan_tat', 'Đã trả giấy xác nhận.', 'sinh_vien');
