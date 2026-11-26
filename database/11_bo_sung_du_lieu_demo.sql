-- =====================================================================
-- 11_bo_sung_du_lieu_demo.sql — Bổ sung dữ liệu demo cho "tlhv_qlsv" (KHÔNG sửa dữ liệu cũ).
-- Bổ sung 25/11/2026: thêm 9 sinh viên với tình huống đa dạng, ngành Hệ thống thông tin
-- (6 học phần, chương trình 24 tín chỉ), khóa K26, 8 lớp học phần, lịch thi, học phí,
-- chứng chỉ, đơn từ, 6 đầu sách và 4 lượt mượn.
--
-- KHÔNG thêm lớp cho học phần cũ ở HK2 2026-2027 và không đụng 5 sinh viên cũ, để các
-- kịch bản thực nghiệm (TN3/TN4) vẫn đúng. Chạy sau 03_qlsv_seed.sql; chạy lại an toàn
-- (đã có SV22004 thì bỏ qua). Sinh từ script, điểm tổng kết = 0,4 × QT + 0,6 × thi.
--
-- Tình huống từng sinh viên:
--   SV22004 Đỗ Thị Hạnh        CNPM K22: bị cảnh báo học vụ: 2 học phần F chưa học lại, GPA thấp
--   SV22005 Vũ Đức Mạnh        CNPM K22: nợ học phí: HK2 2025-2026 nộp một phần, HK1 2026-2027 chưa nộp (quá hạn)
--   SV22006 Ngô Thanh Tâm      CNPM K22: đang bảo lưu năm học 2026-2027 (đơn đã duyệt)
--   SV22007 Phan Thùy Linh     CNPM K22: học lực xuất sắc (GPA > 3,6), có IELTS
--   SV21002 Trịnh Quang Khải   CNPM K21: đủ điều kiện tốt nghiệp: đủ 38 tín chỉ, đủ chứng chỉ
--   SV21003 Mai Phương Thảo    CNPM K21: đủ tín chỉ nhưng chưa có chứng chỉ ngoại ngữ, GDQP đang chờ duyệt
--   SV26001 Lý Gia Bảo         CNPM K26: tân sinh viên K26, học kỳ đầu, chưa có điểm
--   SV22101 Châu Ngọc Lan      HTTT K22: ngành Hệ thống thông tin, học tốt
--   SV23101 Tạ Minh Quân       HTTT K23: ngành Hệ thống thông tin, đang học IS102, nộp học phí một phần
-- Tài khoản trợ lý: chạy scripts/seed_users.py (tự thêm các sinh viên này nếu đã có trong qlsv).
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET NOCOUNT ON;
GO
USE tlhv_qlsv;
GO
IF EXISTS (SELECT 1 FROM sinh_vien WHERE ma_sv = N'SV22004')
BEGIN
    PRINT N'Dữ liệu bổ sung đã có, bỏ qua.';
    SET NOEXEC ON;
END
GO
BEGIN TRANSACTION;

IF NOT EXISTS (SELECT 1 FROM nganh WHERE ma_nganh = N'HTTT')
    INSERT INTO nganh (ma_nganh, ten_nganh) VALUES (N'HTTT', N'Hệ thống thông tin');
IF NOT EXISTS (SELECT 1 FROM khoa_hoc WHERE ma_khoa = N'K26')
    INSERT INTO khoa_hoc (ma_khoa, nam_bat_dau) VALUES (N'K26', 2026);

-- Chương trình: CNPM K26 (sao chép CNPM K22), HTTT K22 và K23 (24 tín chỉ)
INSERT INTO chuong_trinh (nganh_id, khoa_hoc_id, tong_tin_chi, gpa_toi_thieu, yeu_cau_ngoai_ngu)
SELECT n.id, k.id, v.tc, 2.00, 1
FROM (VALUES (N'CNPM', N'K26', 38), (N'HTTT', N'K22', 24), (N'HTTT', N'K23', 24)) AS v (nganh, khoa, tc)
JOIN nganh n ON n.ma_nganh = v.nganh JOIN khoa_hoc k ON k.ma_khoa = v.khoa;

INSERT INTO hoc_phan (ma_hp, ten_hp, so_tin_chi) VALUES
(N'IS101', N'Nhập môn hệ thống thông tin', 3),
(N'IS102', N'Phân tích nghiệp vụ', 3),
(N'IS201', N'Kho dữ liệu', 3),
(N'IS202', N'Hệ thống hoạch định nguồn lực doanh nghiệp (ERP)', 3),
(N'IS203', N'Thương mại điện tử', 3),
(N'IS204', N'Khai phá dữ liệu', 3);

INSERT INTO hoc_phan_tien_quyet (hoc_phan_id, tien_quyet_id)
SELECT a.id, b.id FROM (VALUES (N'IS102', N'IS101'), (N'IS201', N'IT004'), (N'IS204', N'IS201')) AS v (hp, tq)
JOIN hoc_phan a ON a.ma_hp = v.hp JOIN hoc_phan b ON b.ma_hp = v.tq;

INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc)
SELECT ct26.id, x.hoc_phan_id, x.hoc_ky_goi_y, x.bat_buoc
FROM chuong_trinh_hoc_phan x
JOIN chuong_trinh ct22 ON ct22.id = x.chuong_trinh_id
JOIN nganh n ON n.id = ct22.nganh_id AND n.ma_nganh = N'CNPM'
JOIN khoa_hoc k22 ON k22.id = ct22.khoa_hoc_id AND k22.ma_khoa = N'K22'
CROSS JOIN (SELECT c.id FROM chuong_trinh c JOIN nganh n2 ON n2.id = c.nganh_id
            JOIN khoa_hoc k ON k.id = c.khoa_hoc_id WHERE n2.ma_nganh = N'CNPM' AND k.ma_khoa = N'K26') AS ct26;

INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc)
SELECT c.id, hp.id, v.goi_y, v.bb
FROM (VALUES (N'IT001', 1, 1), (N'IS101', 2, 1), (N'IT004', 3, 1), (N'IS102', 4, 1), (N'IS201', 5, 1), (N'IS202', 6, 1), (N'IS203', 7, 1), (N'IS204', 8, 0)) AS v (ma_hp, goi_y, bb)
JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp
CROSS JOIN (SELECT c.id FROM chuong_trinh c JOIN nganh n ON n.id = c.nganh_id WHERE n.ma_nganh = N'HTTT') AS c;

INSERT INTO sinh_vien (ma_sv, ho_ten, email, ngay_sinh, gioi_tinh, nganh_id, khoa_hoc_id, lop, trang_thai)
SELECT v.ma_sv, v.ho_ten, LOWER(v.ma_sv) + N'@truong.example', v.ngay_sinh, v.gioi_tinh, n.id, k.id, v.lop, v.trang_thai
FROM (VALUES
  (N'SV22004', N'Đỗ Thị Hạnh', N'2004-09-02', N'nu', N'CNPM', N'K22', N'22CNPM2', N'dang_hoc'),
  (N'SV22005', N'Vũ Đức Mạnh', N'2004-12-14', N'nam', N'CNPM', N'K22', N'22CNPM2', N'dang_hoc'),
  (N'SV22006', N'Ngô Thanh Tâm', N'2004-02-27', N'nu', N'CNPM', N'K22', N'22CNPM1', N'bao_luu'),
  (N'SV22007', N'Phan Thùy Linh', N'2004-06-08', N'nu', N'CNPM', N'K22', N'22CNPM1', N'dang_hoc'),
  (N'SV21002', N'Trịnh Quang Khải', N'2003-04-21', N'nam', N'CNPM', N'K21', N'21CNPM1', N'dang_hoc'),
  (N'SV21003', N'Mai Phương Thảo', N'2003-10-03', N'nu', N'CNPM', N'K21', N'21CNPM2', N'dang_hoc'),
  (N'SV26001', N'Lý Gia Bảo', N'2008-01-15', N'nam', N'CNPM', N'K26', N'26CNPM1', N'dang_hoc'),
  (N'SV22101', N'Châu Ngọc Lan', N'2004-08-19', N'nu', N'HTTT', N'K22', N'22HTTT1', N'dang_hoc'),
  (N'SV23101', N'Tạ Minh Quân', N'2005-03-30', N'nam', N'HTTT', N'K23', N'23HTTT1', N'dang_hoc')
) AS v (ma_sv, ho_ten, ngay_sinh, gioi_tinh, nganh, khoa, lop, trang_thai)
JOIN nganh n ON n.ma_nganh = v.nganh JOIN khoa_hoc k ON k.ma_khoa = v.khoa;

-- Kết quả học tập (đã tính: tổng kết = 0,4 × QT + 0,6 × thi, quy đổi theo thang của trường)
INSERT INTO ket_qua_hoc_tap (sinh_vien_id, hoc_phan_id, hoc_ky_id, diem_qua_trinh, diem_thi, diem_tong_ket, diem_chu, diem_he_4, lan_hoc)
SELECT sv.id, hp.id, hk.id, v.qt, v.thi, v.tk, v.chu, v.h4, v.lan
FROM (VALUES
  (N'SV22004', N'IT001', N'2023-2024-HK1', 3.00, 3.50, 3.30, N'F', 0.00, 1),
  (N'SV22004', N'SE101', N'2023-2024-HK2', 5.00, 4.00, 4.40, N'D', 1.00, 1),
  (N'SV22004', N'IT002', N'2024-2025-HK1', 3.50, 2.50, 2.90, N'F', 0.00, 1),
  (N'SV22004', N'IT005', N'2024-2025-HK1', 5.00, 4.50, 4.70, N'D', 1.00, 1),
  (N'SV22004', N'SE102', N'2025-2026-HK1', 4.50, 3.00, 3.60, N'F', 0.00, 1),
  (N'SV22005', N'IT001', N'2023-2024-HK1', 7.00, 6.50, 6.70, N'C+', 2.50, 1),
  (N'SV22005', N'SE101', N'2023-2024-HK2', 7.50, 7.00, 7.20, N'B', 3.00, 1),
  (N'SV22005', N'IT002', N'2023-2024-HK2', 6.50, 6.00, 6.20, N'C', 2.00, 1),
  (N'SV22005', N'IT003', N'2024-2025-HK1', 6.00, 5.50, 5.70, N'C', 2.00, 1),
  (N'SV22005', N'IT005', N'2024-2025-HK1', 7.00, 7.50, 7.30, N'B', 3.00, 1),
  (N'SV22005', N'IT004', N'2024-2025-HK2', 6.50, 7.00, 6.80, N'C+', 2.50, 1),
  (N'SV22006', N'IT001', N'2023-2024-HK1', 8.00, 7.00, 7.40, N'B', 3.00, 1),
  (N'SV22006', N'SE101', N'2023-2024-HK2', 7.00, 7.50, 7.30, N'B', 3.00, 1),
  (N'SV22006', N'IT002', N'2023-2024-HK2', 7.50, 6.50, 6.90, N'C+', 2.50, 1),
  (N'SV22006', N'IT003', N'2024-2025-HK1', 6.50, 6.00, 6.20, N'C', 2.00, 1),
  (N'SV22007', N'IT001', N'2023-2024-HK1', 9.50, 9.00, 9.20, N'A', 4.00, 1),
  (N'SV22007', N'SE101', N'2023-2024-HK2', 9.00, 9.50, 9.30, N'A', 4.00, 1),
  (N'SV22007', N'IT002', N'2023-2024-HK2', 9.00, 8.50, 8.70, N'A', 4.00, 1),
  (N'SV22007', N'IT003', N'2024-2025-HK1', 8.50, 9.00, 8.80, N'A', 4.00, 1),
  (N'SV22007', N'IT005', N'2024-2025-HK1', 9.00, 9.00, 9.00, N'A', 4.00, 1),
  (N'SV22007', N'IT004', N'2024-2025-HK2', 9.50, 9.00, 9.20, N'A', 4.00, 1),
  (N'SV22007', N'SE102', N'2025-2026-HK1', 8.50, 8.00, 8.20, N'B+', 3.50, 1),
  (N'SV22007', N'SE103', N'2025-2026-HK2', 9.00, 8.50, 8.70, N'A', 4.00, 1),
  (N'SV22007', N'SE104', N'2025-2026-HK2', 8.50, 9.00, 8.80, N'A', 4.00, 1),
  (N'SV21002', N'IT001', N'2023-2024-HK1', 8.50, 8.00, 8.20, N'B+', 3.50, 1),
  (N'SV21002', N'SE101', N'2023-2024-HK1', 8.00, 8.50, 8.30, N'B+', 3.50, 1),
  (N'SV21002', N'IT002', N'2023-2024-HK2', 7.50, 8.00, 7.80, N'B', 3.00, 1),
  (N'SV21002', N'IT004', N'2023-2024-HK2', 8.00, 7.50, 7.70, N'B', 3.00, 1),
  (N'SV21002', N'IT003', N'2024-2025-HK1', 7.00, 7.50, 7.30, N'B', 3.00, 1),
  (N'SV21002', N'IT005', N'2024-2025-HK1', 8.00, 8.00, 8.00, N'B+', 3.50, 1),
  (N'SV21002', N'SE102', N'2024-2025-HK2', 8.50, 8.50, 8.50, N'A', 4.00, 1),
  (N'SV21002', N'SE103', N'2024-2025-HK2', 7.50, 7.00, 7.20, N'B', 3.00, 1),
  (N'SV21002', N'SE104', N'2025-2026-HK1', 8.00, 9.00, 8.60, N'A', 4.00, 1),
  (N'SV21002', N'SE105', N'2025-2026-HK1', 8.50, 8.00, 8.20, N'B+', 3.50, 1),
  (N'SV21002', N'SE201', N'2025-2026-HK2', 9.00, 8.50, 8.70, N'A', 4.00, 1),
  (N'SV21002', N'SE202', N'2025-2026-HK2', 8.00, 8.00, 8.00, N'B+', 3.50, 1),
  (N'SV21003', N'IT001', N'2023-2024-HK1', 7.00, 6.50, 6.70, N'C+', 2.50, 1),
  (N'SV21003', N'SE101', N'2023-2024-HK1', 6.50, 7.00, 6.80, N'C+', 2.50, 1),
  (N'SV21003', N'IT002', N'2023-2024-HK2', 6.00, 6.50, 6.30, N'C', 2.00, 1),
  (N'SV21003', N'IT004', N'2023-2024-HK2', 7.00, 6.00, 6.40, N'C', 2.00, 1),
  (N'SV21003', N'IT003', N'2024-2025-HK1', 6.50, 6.00, 6.20, N'C', 2.00, 1),
  (N'SV21003', N'IT005', N'2024-2025-HK1', 7.00, 7.00, 7.00, N'B', 3.00, 1),
  (N'SV21003', N'SE102', N'2024-2025-HK2', 7.50, 7.00, 7.20, N'B', 3.00, 1),
  (N'SV21003', N'SE103', N'2024-2025-HK2', 6.50, 6.50, 6.50, N'C+', 2.50, 1),
  (N'SV21003', N'SE104', N'2025-2026-HK1', 7.00, 7.50, 7.30, N'B', 3.00, 1),
  (N'SV21003', N'SE105', N'2025-2026-HK1', 7.50, 7.00, 7.20, N'B', 3.00, 1),
  (N'SV21003', N'SE201', N'2025-2026-HK2', 6.00, 6.50, 6.30, N'C', 2.00, 1),
  (N'SV21003', N'SE202', N'2025-2026-HK2', 7.00, 6.00, 6.40, N'C', 2.00, 1),
  (N'SV22101', N'IT001', N'2023-2024-HK1', 8.00, 8.50, 8.30, N'B+', 3.50, 1),
  (N'SV22101', N'IS101', N'2023-2024-HK2', 8.50, 9.00, 8.80, N'A', 4.00, 1),
  (N'SV22101', N'IT004', N'2024-2025-HK1', 7.50, 8.00, 7.80, N'B', 3.00, 1),
  (N'SV22101', N'IS102', N'2024-2025-HK2', 8.00, 7.50, 7.70, N'B', 3.00, 1),
  (N'SV22101', N'IS201', N'2025-2026-HK1', 8.50, 8.00, 8.20, N'B+', 3.50, 1),
  (N'SV22101', N'IS202', N'2025-2026-HK2', 7.00, 7.50, 7.30, N'B', 3.00, 1),
  (N'SV23101', N'IT001', N'2024-2025-HK1', 6.50, 7.00, 6.80, N'C+', 2.50, 1),
  (N'SV23101', N'IS101', N'2024-2025-HK2', 7.00, 6.00, 6.40, N'C', 2.00, 1),
  (N'SV23101', N'IT004', N'2025-2026-HK1', 6.00, 5.00, 5.40, N'D+', 1.50, 1)
) AS v (ma_sv, ma_hp, ma_hk, qt, thi, tk, chu, h4, lan)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

INSERT INTO lop_hoc_phan (ma_lop, hoc_phan_id, hoc_ky_id, giang_vien, si_so_toi_da, thu, tiet_bat_dau, tiet_ket_thuc, phong)
SELECT v.ma_lop, hp.id, hk.id, v.gv, v.si_so, v.thu, v.bd, v.kt, v.phong
FROM (VALUES
  (N'IT001.K26', N'IT001', N'2026-2027-HK1', N'ThS. Lâm Văn Đức', 80, 4, 1, 3, N'C1.101'),
  (N'SE101.K26', N'SE101', N'2026-2027-HK1', N'ThS. Hồ Thị Yến', 80, 6, 7, 9, N'C1.101'),
  (N'IS102.01', N'IS102', N'2026-2027-HK1', N'TS. Kiều Anh Tú', 50, 5, 1, 3, N'B3.204'),
  (N'IS203.01', N'IS203', N'2026-2027-HK1', N'ThS. Lục Thu Trang', 50, 3, 4, 6, N'B3.204'),
  (N'IS201.01', N'IS201', N'2026-2027-HK2', N'TS. Kiều Anh Tú', 50, 2, 4, 6, N'B3.205'),
  (N'IS202.01', N'IS202', N'2026-2027-HK2', N'ThS. Lục Thu Trang', 50, 4, 7, 9, N'B3.205'),
  (N'IS203.02', N'IS203', N'2026-2027-HK2', N'ThS. Lục Thu Trang', 50, 6, 1, 3, N'B3.206'),
  (N'IS204.01', N'IS204', N'2026-2027-HK2', N'TS. Quách Minh Nhật', 45, 5, 4, 6, N'B3.206')
) AS v (ma_lop, ma_hp, ma_hk, gv, si_so, thu, bd, kt, phong)
JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

INSERT INTO dang_ky_hoc_phan (sinh_vien_id, lop_hoc_phan_id, trang_thai)
SELECT sv.id, l.id, N'da_dang_ky' FROM (VALUES (N'SV26001', N'IT001.K26'), (N'SV26001', N'SE101.K26'), (N'SV23101', N'IS102.01'), (N'SV22101', N'IS203.01')) AS v (ma_sv, ma_lop)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN lop_hoc_phan l ON l.ma_lop = v.ma_lop;

INSERT INTO lich_thi (lop_hoc_phan_id, ngay_thi, gio_bat_dau, phong, hinh_thuc)
SELECT l.id, v.ngay, v.gio, v.phong, v.ht FROM (VALUES
  (N'IT001.K26', N'2027-01-06', N'07:30:00', N'C2.301', N'tu_luan'),
  (N'SE101.K26', N'2027-01-08', N'13:30:00', N'C2.302', N'trac_nghiem'),
  (N'IS102.01', N'2027-01-07', N'09:30:00', N'B3.204', N'tu_luan'),
  (N'IS203.01', N'2027-01-09', N'07:30:00', N'B3.204', N'do_an')
) AS v (ma_lop, ngay, gio, phong, ht) JOIN lop_hoc_phan l ON l.ma_lop = v.ma_lop;

INSERT INTO hoc_phi (sinh_vien_id, hoc_ky_id, so_tien_phai_nop, so_tien_da_nop, han_nop, trang_thai)
SELECT sv.id, hk.id, v.phai, v.da, v.han, v.tt FROM (VALUES
  (N'SV22004', N'2026-2027-HK1', 4900000, 4900000, N'2026-10-15', N'da_nop'),
  (N'SV22005', N'2025-2026-HK2', 7000000, 3500000, N'2026-04-05', N'nop_mot_phan'),
  (N'SV22005', N'2026-2027-HK1', 7000000, 0, N'2026-10-15', N'chua_nop'),
  (N'SV22007', N'2026-2027-HK1', 8400000, 8400000, N'2026-10-15', N'da_nop'),
  (N'SV21002', N'2026-2027-HK1', 0, 0, N'2026-10-15', N'da_nop'),
  (N'SV21003', N'2026-2027-HK1', 0, 0, N'2026-10-15', N'da_nop'),
  (N'SV26001', N'2026-2027-HK1', 2100000, 2100000, N'2026-10-15', N'da_nop'),
  (N'SV22101', N'2026-2027-HK1', 1050000, 1050000, N'2026-10-15', N'da_nop'),
  (N'SV23101', N'2026-2027-HK1', 1050000, 500000, N'2026-10-15', N'nop_mot_phan')
) AS v (ma_sv, ma_hk, phai, da, han, tt)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

INSERT INTO chung_chi (sinh_vien_id, loai, ten, ngay_cap, trang_thai_duyet)
SELECT sv.id, v.loai, v.ten, v.ngay, v.tt FROM (VALUES
  (N'SV22007', N'ngoai_ngu', N'IELTS 7.0', N'2025-07-12', N'da_duyet'),
  (N'SV22007', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2023-08-30', N'da_duyet'),
  (N'SV21002', N'gdtc', N'Chứng chỉ Giáo dục thể chất', N'2023-06-15', N'da_duyet'),
  (N'SV21002', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2022-08-30', N'da_duyet'),
  (N'SV21002', N'ngoai_ngu', N'TOEIC 650', N'2025-11-20', N'da_duyet'),
  (N'SV21003', N'gdtc', N'Chứng chỉ Giáo dục thể chất', N'2023-06-15', N'da_duyet'),
  (N'SV21003', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2026-10-30', N'cho_duyet'),
  (N'SV22101', N'tin_hoc', N'Chứng chỉ ứng dụng CNTT nâng cao', N'2025-05-18', N'da_duyet')
) AS v (ma_sv, loai, ten, ngay, tt) JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv;

INSERT INTO don_tu (ma_don, sinh_vien_id, loai_don, noi_dung, trang_thai, ghi_chu_xu_ly, tao_boi)
SELECT v.ma_don, sv.id, v.loai, v.nd, v.tt, v.gc, v.tao FROM (VALUES
  (N'DT-2026-0101', N'SV22006', N'bao_luu', N'{"tu_hoc_ky": "2026-2027-HK1", "den_hoc_ky": "2026-2027-HK2", "ly_do": "Điều trị bệnh dài ngày, có giấy xác nhận của bệnh viện"}', N'da_duyet', N'Đã duyệt bảo lưu năm học 2026-2027. Nộp đơn trở lại học trước ngày 01/08/2027.', N'sinh_vien'),
  (N'DT-2026-0102', N'SV22007', N'giay_xac_nhan_sv', N'{"muc_dich": "Xin học bổng doanh nghiệp", "so_ban": 2, "noi_nhan": "Phòng Công tác sinh viên"}', N'dang_xu_ly', NULL, N'sinh_vien'),
  (N'DT-2026-0103', N'SV21002', N'giay_xac_nhan_sv', N'{"muc_dich": "Bổ sung hồ sơ xét tốt nghiệp", "so_ban": 1, "noi_nhan": "Phòng Đào tạo"}', N'hoan_tat', N'Đã trả giấy xác nhận.', N'sinh_vien')
) AS v (ma_don, ma_sv, loai, nd, tt, gc, tao) JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv;

INSERT INTO sach (ma_sach, ten_sach, tac_gia, nam_xb, tong_so_ban, so_ban_con, so_luot_dat_truoc) VALUES
(N'TV011', N'Kho dữ liệu và xử lý phân tích trực tuyến', N'Kiều Anh Tú', 2022, 4, 3, 0),
(N'TV012', N'Hệ thống ERP trong doanh nghiệp', N'Lục Thu Trang', 2023, 3, 0, 2),
(N'TV013', N'Thương mại điện tử căn bản', N'Đinh Quốc Huy', 2021, 5, 4, 0),
(N'TV014', N'Nhập môn khai phá dữ liệu', N'Quách Minh Nhật', 2024, 3, 2, 0),
(N'TV015', N'Phân tích nghiệp vụ cho người mới bắt đầu', N'Tô Hải Đăng', 2023, 4, 4, 0),
(N'TV016', N'Toán rời rạc', N'Lâm Văn Đức', 2020, 10, 8, 0);

INSERT INTO muon_sach (sinh_vien_id, ma_sach, ngay_muon, han_tra, so_lan_gia_han, trang_thai)
SELECT sv.id, v.ma_sach, v.muon, v.han, v.lan, v.tt FROM (VALUES
  (N'SV22101', N'TV011', N'2026-11-03', N'2026-11-24', 0, N'dang_muon'),
  (N'SV23101', N'TV014', N'2026-10-01', N'2026-10-22', 1, N'dang_muon'),
  (N'SV26001', N'TV016', N'2026-11-10', N'2026-12-01', 0, N'dang_muon'),
  (N'SV22004', N'TV012', N'2026-11-05', N'2026-11-26', 0, N'dang_muon')
) AS v (ma_sv, ma_sach, muon, han, lan, tt) JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv;

COMMIT TRANSACTION;
PRINT N'Đã bổ sung dữ liệu demo.';
GO
SET NOEXEC OFF;
GO
SELECT sv.ma_sv, sv.ho_ten, n.ma_nganh, k.ma_khoa, sv.trang_thai
FROM tlhv_qlsv.dbo.sinh_vien sv JOIN tlhv_qlsv.dbo.nganh n ON n.id = sv.nganh_id
JOIN tlhv_qlsv.dbo.khoa_hoc k ON k.id = sv.khoa_hoc_id ORDER BY sv.id;
GO
