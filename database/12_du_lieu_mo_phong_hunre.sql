-- =====================================================================
-- 12_du_lieu_mo_phong_hunre.sql — Dữ liệu MÔ PHỎNG theo thông tin công khai của
-- Trường Đại học Tài nguyên và Môi trường Hà Nội (HUNRE). CSDL "tlhv_qlsv".
-- Bổ sung 26/11/2026. KHÔNG sửa dữ liệu cũ (TN3/TN4 dựa vào SV22001, IT004.02...).
-- Chạy sau 03 và 11; chạy lại an toàn (đã có ngành 7850101 thì bỏ qua).
--
-- LẤY THEO VĂN BẢN THẬT (hunre.edu.vn):
--   * Ngành Quản lý tài nguyên và môi trường, mã 7850101 (Thông tin tuyển sinh 2026).
--   * 61 học phần: mã, tên, số tín chỉ, học kỳ trong kế hoạch chuẩn, bắt buộc/tự chọn,
--     học phần tiên quyết — theo Bản mô tả CTĐT ngành QLTN&MT (ký 09/9/2024).
--     Tổng 122 tín chỉ (75 bắt buộc), chưa gồm GDTC và GDQP-AN.
--   * Điểm học phần = 40% quá trình + 60% thi kết thúc (Bản mô tả CTĐT).
--   * Học kỳ đầu trường đăng ký mặc định thời khóa biểu; từ học kỳ 2 sinh viên tự đăng ký.
--   * Mã sinh viên 10 chữ số, 2 số đầu = năm nhập học; lớp dạng ĐH<khóa><ngành><số>,
--     vd ĐH6C1 (Quy trình đăng ký môn học theo tín chỉ). Khóa nhập học 2024 -> ĐH14.
--   * Tân sinh viên 2026: học phí HK1 2026-2027 tạm thu 9.026.000 đ, hạn 15/9/2026
--     (Hướng dẫn nhập học ĐHCQ 2026, đợt bổ sung).
-- MÔ PHỎNG (không có văn bản công khai): họ tên, ngày sinh, email, 5 số cuối mã SV,
--   giảng viên, phòng học, tiết học, lịch thi, điểm; đơn giá 475.000 đ/tín chỉ (nằm trong
--   khoảng 435.600–548.100 đ/tín chỉ mà các trang tổng hợp đưa tin, chưa đối chiếu văn bản gốc).
--
-- Tình huống:
--   2411100101 Nguyễn Thị Thu Hà  K24 ĐH14QM1: học đều, đã đăng ký trước 2 lớp HK2
--   2411100102 Trần Đức Long      K24 ĐH14QM1: F Ngoại ngữ 1 nên chưa học được Ngoại ngữ 2
--                                  (tiên quyết), nộp học phí HK1 2026-2027 một phần
--   2411100103 Lê Phương Anh      K24 ĐH14QM2: học giỏi, có IELTS
--   2611100105 Phạm Minh Khôi     K26 ĐH16QM1: tân sinh viên, đã nộp 9.026.000 đ tạm thu
--   2611100117 Hoàng Bảo Ngọc     K26 ĐH16QM1: tân sinh viên, đã nộp 9.026.000 đ tạm thu
-- HK2 2026-2027 có MTQM186.01 trùng giờ MTCM117.01 (minh họa "lọc lớp không trùng thời gian").
-- Tài khoản trợ lý: chạy scripts/seed_users.py (email <mã SV>@truong.example, mật khẩu Sv@123456).
-- File sinh bằng script; điểm chữ theo thang của hệ thống giả lập (A >= 8,5 ... F < 4,0).
-- =====================================================================
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET NOCOUNT ON;
GO
USE tlhv_qlsv;
GO
IF EXISTS (SELECT 1 FROM nganh WHERE ma_nganh = N'7850101')
BEGIN
    PRINT N'Dữ liệu mô phỏng HUNRE đã có, bỏ qua.';
    SET NOEXEC ON;
END
GO
BEGIN TRANSACTION;

INSERT INTO nganh (ma_nganh, ten_nganh) VALUES (N'7850101', N'Quản lý tài nguyên và môi trường');
IF NOT EXISTS (SELECT 1 FROM khoa_hoc WHERE ma_khoa = N'K24')
    INSERT INTO khoa_hoc (ma_khoa, nam_bat_dau) VALUES (N'K24', 2024);
IF NOT EXISTS (SELECT 1 FROM khoa_hoc WHERE ma_khoa = N'K26')
    INSERT INTO khoa_hoc (ma_khoa, nam_bat_dau) VALUES (N'K26', 2026);

INSERT INTO chuong_trinh (nganh_id, khoa_hoc_id, tong_tin_chi, gpa_toi_thieu, yeu_cau_ngoai_ngu)
SELECT n.id, k.id, 122, 2.00, 1
FROM nganh n CROSS JOIN khoa_hoc k
WHERE n.ma_nganh = N'7850101' AND k.ma_khoa IN (N'K24', N'K26');

INSERT INTO hoc_phan (ma_hp, ten_hp, so_tin_chi) VALUES
  (N'LCML101', N'Triết học Mác - Lênin', 3),
  (N'LCML102', N'Kinh tế chính trị Mác - Lênin', 2),
  (N'LCML103', N'Chủ nghĩa xã hội khoa học', 2),
  (N'LCTT101', N'Tư tưởng Hồ Chí Minh', 2),
  (N'LCLS101', N'Lịch sử Đảng Cộng sản Việt Nam', 2),
  (N'LCPL101', N'Pháp luật đại cương', 2),
  (N'CTKU101', N'Tin học đại cương', 2),
  (N'NNTA164', N'Ngoại ngữ 1', 3),
  (N'NNTA165', N'Ngoại ngữ 2', 3),
  (N'MTQM102', N'Môi trường và phát triển', 2),
  (N'MTQM104', N'Tăng trưởng xanh và bền vững', 2),
  (N'KTKH142', N'Chuyển đổi số tài nguyên và môi trường', 2),
  (N'KĐTO106', N'Xác suất thống kê', 2),
  (N'KĐHH106', N'Địa lý kinh tế', 2),
  (N'KĐVL108', N'Đại cương về khoa học Trái đất', 2),
  (N'KĐTO116', N'Toán ứng dụng', 2),
  (N'KĐHH103', N'Hóa học ứng dụng', 2),
  (N'KĐVL105', N'Vật lý ứng dụng', 2),
  (N'MTKA105', N'Hóa học môi trường', 2),
  (N'MTQM106', N'Quản lý môi trường', 2),
  (N'MTQT102', N'Sinh thái học', 2),
  (N'MTQT106', N'Kinh tế tài nguyên và môi trường', 3),
  (N'MTQM108', N'Hệ thống pháp luật về tài nguyên và môi trường', 3),
  (N'MTQM105', N'Kinh tế học biến đổi khí hậu', 3),
  (N'MTQM158', N'Kinh tế học về kiểm soát ô nhiễm', 3),
  (N'MTQM157', N'Kinh tế tuần hoàn', 3),
  (N'MTQT115', N'Tiếng Anh chuyên ngành', 3),
  (N'MTQT113', N'Điều tra đánh giá đa dạng sinh học', 3),
  (N'MTQM124', N'Quản lý môi trường đô thị, công nghiệp và làng nghề', 2),
  (N'MTCM126', N'Sản xuất sạch hơn và phòng ngừa ô nhiễm', 2),
  (N'MTQT107', N'Truyền thông về tài nguyên và môi trường', 3),
  (N'MTQM188', N'Đánh giá tác động môi trường', 3),
  (N'MTQT103', N'Bảo tồn đa dạng sinh học', 3),
  (N'MTQM190', N'Kỹ thuật kiểm toán môi trường', 2),
  (N'MTQT114', N'Kỹ năng nghiên cứu tài nguyên và môi trường', 2),
  (N'MTQM107', N'Thực tập nghề nghiệp', 2),
  (N'MTKA107', N'Độc học môi trường', 2),
  (N'MTCM117', N'Công nghệ môi trường', 3),
  (N'MTKA112', N'Quan trắc và phân tích môi trường', 3),
  (N'MTQM191', N'Thanh tra tài nguyên và môi trường', 2),
  (N'MTQM185', N'Ứng dụng công nghệ thông tin trong quản lý tài nguyên và môi trường', 3),
  (N'MTQM186', N'Đồ án ứng dụng công nghệ thông tin trong quản lý tài nguyên và môi trường', 2),
  (N'MTQM128', N'Đồ án đánh giá tác động môi trường', 2),
  (N'MTQM193', N'Quy hoạch bảo vệ môi trường và tài nguyên', 3),
  (N'MTCM122', N'Quản lý chất thải rắn và chất thải nguy hại', 3),
  (N'MTQM189', N'Hệ thống quản lý môi trường', 3),
  (N'MTKA131', N'Sức khỏe – An toàn – Môi trường (HSE)', 2),
  (N'MTQM133', N'Mô hình hóa môi trường', 3),
  (N'MTQM195', N'Tư vấn các thủ tục hành chính về môi trường', 3),
  (N'MTQT118', N'Kiểm kê khí nhà kính', 3),
  (N'MTQT147', N'Đánh giá, quản lý rủi ro và phục hồi hệ sinh thái', 2),
  (N'MTQM125', N'Đồ án quản lý môi trường đô thị, công nghiệp và làng nghề', 2),
  (N'MTKA140', N'Thông tin môi trường', 2),
  (N'MTQT145', N'Đồ án truyền thông về tài nguyên và môi trường', 3),
  (N'MTQT140', N'Thực tập điều tra đánh giá đa dạng sinh học', 3),
  (N'MTKA149', N'Thực tập quan trắc và phân tích môi trường', 2),
  (N'MTQT141', N'Thực tập kinh tế môi trường', 3),
  (N'KBQB107', N'Quản lý tổng hợp vùng bờ biển', 3),
  (N'MTCM161', N'Đồ án công nghệ môi trường', 3),
  (N'BKPB117', N'Đồ án nghiên cứu biến đổi khí hậu', 3),
  (N'MTQT116', N'Khóa luận tốt nghiệp', 10);

INSERT INTO hoc_phan_tien_quyet (hoc_phan_id, tien_quyet_id)
SELECT a.id, b.id FROM (VALUES
  (N'NNTA165', N'NNTA164'),
  (N'MTQM186', N'MTQM185'),
  (N'MTQM128', N'MTQM188'),
  (N'MTQM125', N'MTQM124'),
  (N'MTQT145', N'MTQT107'),
  (N'MTKA149', N'MTKA112'),
  (N'MTQT141', N'MTQT106'),
  (N'MTCM161', N'MTCM117')
) AS v (hp, tq)
JOIN hoc_phan a ON a.ma_hp = v.hp JOIN hoc_phan b ON b.ma_hp = v.tq;

-- Kế hoạch đào tạo chuẩn (học kỳ gợi ý 1–8, bắt buộc/tự chọn) theo Bản mô tả CTĐT; dùng cho K24 và K26
INSERT INTO chuong_trinh_hoc_phan (chuong_trinh_id, hoc_phan_id, hoc_ky_goi_y, bat_buoc)
SELECT c.id, hp.id, v.goi_y, v.bb FROM (VALUES
  (N'LCML101', 2, 1),
  (N'LCML102', 2, 1),
  (N'LCML103', 3, 1),
  (N'LCTT101', 4, 1),
  (N'LCLS101', 5, 1),
  (N'LCPL101', 1, 1),
  (N'CTKU101', 1, 1),
  (N'NNTA164', 1, 1),
  (N'NNTA165', 2, 1),
  (N'MTQM102', 1, 0),
  (N'MTQM104', 1, 0),
  (N'KTKH142', 1, 0),
  (N'KĐTO106', 1, 1),
  (N'KĐHH106', 1, 0),
  (N'KĐVL108', 2, 0),
  (N'KĐTO116', 2, 0),
  (N'KĐHH103', 2, 0),
  (N'KĐVL105', 1, 0),
  (N'MTKA105', 3, 1),
  (N'MTQM106', 3, 1),
  (N'MTQT102', 1, 1),
  (N'MTQT106', 2, 1),
  (N'MTQM108', 3, 0),
  (N'MTQM105', 3, 0),
  (N'MTQM158', 3, 0),
  (N'MTQM157', 3, 0),
  (N'MTQT115', 4, 1),
  (N'MTQT113', 3, 1),
  (N'MTQM124', 5, 1),
  (N'MTCM126', 6, 1),
  (N'MTQT107', 7, 1),
  (N'MTQM188', 7, 1),
  (N'MTQT103', 6, 1),
  (N'MTQM190', 5, 1),
  (N'MTQT114', 3, 1),
  (N'MTQM107', 4, 1),
  (N'MTKA107', 4, 1),
  (N'MTCM117', 6, 1),
  (N'MTKA112', 4, 1),
  (N'MTQM191', 4, 0),
  (N'MTQM185', 5, 0),
  (N'MTQM186', 6, 0),
  (N'MTQM128', 7, 0),
  (N'MTQM193', 5, 0),
  (N'MTCM122', 7, 0),
  (N'MTQM189', 4, 0),
  (N'MTKA131', 7, 0),
  (N'MTQM133', 7, 0),
  (N'MTQM195', 6, 0),
  (N'MTQT118', 7, 0),
  (N'MTQT147', 7, 0),
  (N'MTQM125', 6, 0),
  (N'MTKA140', 7, 0),
  (N'MTQT145', 7, 0),
  (N'MTQT140', 5, 0),
  (N'MTKA149', 6, 0),
  (N'MTQT141', 5, 0),
  (N'KBQB107', 7, 0),
  (N'MTCM161', 7, 0),
  (N'BKPB117', 6, 0),
  (N'MTQT116', 8, 1)
) AS v (ma_hp, goi_y, bb)
JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp
CROSS JOIN (SELECT c.id FROM chuong_trinh c JOIN nganh n ON n.id = c.nganh_id WHERE n.ma_nganh = N'7850101') AS c;

-- Họ tên, ngày sinh, email hư cấu; mã SV 10 chữ số, 2 số đầu = năm nhập học (giống định dạng thật)
INSERT INTO sinh_vien (ma_sv, ho_ten, email, ngay_sinh, gioi_tinh, nganh_id, khoa_hoc_id, lop, trang_thai)
SELECT v.ma_sv, v.ho_ten, v.ma_sv + N'@truong.example', v.ngay_sinh, v.gioi_tinh, n.id, k.id, v.lop, N'dang_hoc'
FROM (VALUES
  (N'2411100101', N'Nguyễn Thị Thu Hà', N'2006-04-17', N'nu', N'K24', N'ĐH14QM1'),
  (N'2411100102', N'Trần Đức Long', N'2006-10-02', N'nam', N'K24', N'ĐH14QM1'),
  (N'2411100103', N'Lê Phương Anh', N'2006-01-23', N'nu', N'K24', N'ĐH14QM2'),
  (N'2611100105', N'Phạm Minh Khôi', N'2008-06-11', N'nam', N'K26', N'ĐH16QM1'),
  (N'2611100117', N'Hoàng Bảo Ngọc', N'2008-12-29', N'nu', N'K26', N'ĐH16QM1')
) AS v (ma_sv, ho_ten, ngay_sinh, gioi_tinh, khoa, lop)
JOIN nganh n ON n.ma_nganh = N'7850101' JOIN khoa_hoc k ON k.ma_khoa = v.khoa;

-- Kết quả 4 học kỳ đầu của K24: tổng kết = 0,4 × quá trình + 0,6 × thi (tỉ lệ 40/60 của CTĐT)
INSERT INTO ket_qua_hoc_tap (sinh_vien_id, hoc_phan_id, hoc_ky_id, diem_qua_trinh, diem_thi, diem_tong_ket, diem_chu, diem_he_4, lan_hoc)
SELECT sv.id, hp.id, hk.id, v.qt, v.thi, v.tk, v.chu, v.h4, 1 FROM (VALUES
  (N'2411100101', N'LCPL101', N'2024-2025-HK1', 6.50, 7.50, 7.10, N'B', 3.00),
  (N'2411100101', N'CTKU101', N'2024-2025-HK1', 8.50, 8.50, 8.50, N'A', 4.00),
  (N'2411100101', N'NNTA164', N'2024-2025-HK1', 9.00, 6.50, 7.50, N'B', 3.00),
  (N'2411100101', N'MTQM102', N'2024-2025-HK1', 7.00, 8.50, 7.90, N'B', 3.00),
  (N'2411100101', N'MTQT102', N'2024-2025-HK1', 8.50, 8.50, 8.50, N'A', 4.00),
  (N'2411100101', N'KĐTO106', N'2024-2025-HK1', 8.00, 8.50, 8.30, N'B+', 3.50),
  (N'2411100101', N'KĐHH106', N'2024-2025-HK1', 8.50, 9.00, 8.80, N'A', 4.00),
  (N'2411100101', N'KĐVL105', N'2024-2025-HK1', 8.00, 8.50, 8.30, N'B+', 3.50),
  (N'2411100101', N'LCML101', N'2024-2025-HK2', 8.00, 7.00, 7.40, N'B', 3.00),
  (N'2411100101', N'LCML102', N'2024-2025-HK2', 6.50, 8.50, 7.70, N'B', 3.00),
  (N'2411100101', N'NNTA165', N'2024-2025-HK2', 6.50, 6.50, 6.50, N'C+', 2.50),
  (N'2411100101', N'MTQT106', N'2024-2025-HK2', 7.50, 6.50, 6.90, N'C+', 2.50),
  (N'2411100101', N'KĐVL108', N'2024-2025-HK2', 8.00, 6.50, 7.10, N'B', 3.00),
  (N'2411100101', N'LCML103', N'2025-2026-HK1', 9.00, 8.00, 8.40, N'B+', 3.50),
  (N'2411100101', N'MTKA105', N'2025-2026-HK1', 9.00, 7.50, 8.10, N'B+', 3.50),
  (N'2411100101', N'MTQM106', N'2025-2026-HK1', 7.00, 8.00, 7.60, N'B', 3.00),
  (N'2411100101', N'MTQM108', N'2025-2026-HK1', 7.50, 7.50, 7.50, N'B', 3.00),
  (N'2411100101', N'MTQM105', N'2025-2026-HK1', 7.50, 8.00, 7.80, N'B', 3.00),
  (N'2411100101', N'MTQT113', N'2025-2026-HK1', 9.00, 8.50, 8.70, N'A', 4.00),
  (N'2411100101', N'MTQT114', N'2025-2026-HK1', 9.00, 6.50, 7.50, N'B', 3.00),
  (N'2411100101', N'LCTT101', N'2025-2026-HK2', 9.00, 7.50, 8.10, N'B+', 3.50),
  (N'2411100101', N'MTQT115', N'2025-2026-HK2', 6.50, 8.50, 7.70, N'B', 3.00),
  (N'2411100101', N'MTQM107', N'2025-2026-HK2', 8.50, 7.50, 7.90, N'B', 3.00),
  (N'2411100101', N'MTKA107', N'2025-2026-HK2', 7.50, 8.00, 7.80, N'B', 3.00),
  (N'2411100101', N'MTKA112', N'2025-2026-HK2', 7.00, 9.00, 8.20, N'B+', 3.50),
  (N'2411100101', N'MTQM191', N'2025-2026-HK2', 9.00, 9.00, 9.00, N'A', 4.00),
  (N'2411100101', N'MTQM189', N'2025-2026-HK2', 8.50, 7.50, 7.90, N'B', 3.00),
  (N'2411100102', N'LCPL101', N'2024-2025-HK1', 5.00, 7.50, 6.50, N'C+', 2.50),
  (N'2411100102', N'CTKU101', N'2024-2025-HK1', 6.00, 6.00, 6.00, N'C', 2.00),
  (N'2411100102', N'NNTA164', N'2024-2025-HK1', 4.00, 2.50, 3.10, N'F', 0.00),
  (N'2411100102', N'MTQM102', N'2024-2025-HK1', 6.50, 6.50, 6.50, N'C+', 2.50),
  (N'2411100102', N'MTQT102', N'2024-2025-HK1', 5.00, 6.50, 5.90, N'C', 2.00),
  (N'2411100102', N'KĐTO106', N'2024-2025-HK1', 7.00, 7.00, 7.00, N'B', 3.00),
  (N'2411100102', N'KĐHH106', N'2024-2025-HK1', 6.50, 5.00, 5.60, N'C', 2.00),
  (N'2411100102', N'KĐVL105', N'2024-2025-HK1', 6.50, 7.00, 6.80, N'C+', 2.50),
  (N'2411100102', N'LCML101', N'2024-2025-HK2', 7.00, 6.50, 6.70, N'C+', 2.50),
  (N'2411100102', N'LCML102', N'2024-2025-HK2', 6.50, 7.00, 6.80, N'C+', 2.50),
  (N'2411100102', N'MTQT106', N'2024-2025-HK2', 5.00, 4.00, 4.40, N'D', 1.00),
  (N'2411100102', N'KĐVL108', N'2024-2025-HK2', 6.00, 6.50, 6.30, N'C', 2.00),
  (N'2411100102', N'LCML103', N'2025-2026-HK1', 7.00, 6.50, 6.70, N'C+', 2.50),
  (N'2411100102', N'MTKA105', N'2025-2026-HK1', 7.00, 7.00, 7.00, N'B', 3.00),
  (N'2411100102', N'MTQM106', N'2025-2026-HK1', 5.00, 7.00, 6.20, N'C', 2.00),
  (N'2411100102', N'MTQM108', N'2025-2026-HK1', 5.50, 5.50, 5.50, N'C', 2.00),
  (N'2411100102', N'MTQM105', N'2025-2026-HK1', 5.00, 7.50, 6.50, N'C+', 2.50),
  (N'2411100102', N'MTQT113', N'2025-2026-HK1', 7.00, 7.50, 7.30, N'B', 3.00),
  (N'2411100102', N'MTQT114', N'2025-2026-HK1', 5.00, 7.50, 6.50, N'C+', 2.50),
  (N'2411100102', N'LCTT101', N'2025-2026-HK2', 7.00, 6.50, 6.70, N'C+', 2.50),
  (N'2411100102', N'MTQT115', N'2025-2026-HK2', 6.50, 5.50, 5.90, N'C', 2.00),
  (N'2411100102', N'MTQM107', N'2025-2026-HK2', 6.50, 5.50, 5.90, N'C', 2.00),
  (N'2411100102', N'MTKA107', N'2025-2026-HK2', 5.00, 7.50, 6.50, N'C+', 2.50),
  (N'2411100102', N'MTKA112', N'2025-2026-HK2', 7.50, 6.50, 6.90, N'C+', 2.50),
  (N'2411100102', N'MTQM191', N'2025-2026-HK2', 7.50, 6.50, 6.90, N'C+', 2.50),
  (N'2411100102', N'MTQM189', N'2025-2026-HK2', 7.50, 7.00, 7.20, N'B', 3.00),
  (N'2411100103', N'LCPL101', N'2024-2025-HK1', 9.00, 10.00, 9.60, N'A', 4.00),
  (N'2411100103', N'CTKU101', N'2024-2025-HK1', 9.50, 9.00, 9.20, N'A', 4.00),
  (N'2411100103', N'NNTA164', N'2024-2025-HK1', 10.00, 10.00, 10.00, N'A', 4.00),
  (N'2411100103', N'MTQM102', N'2024-2025-HK1', 9.50, 9.50, 9.50, N'A', 4.00),
  (N'2411100103', N'MTQT102', N'2024-2025-HK1', 9.50, 8.50, 8.90, N'A', 4.00),
  (N'2411100103', N'KĐTO106', N'2024-2025-HK1', 9.00, 9.00, 9.00, N'A', 4.00),
  (N'2411100103', N'KĐHH106', N'2024-2025-HK1', 8.00, 8.00, 8.00, N'B+', 3.50),
  (N'2411100103', N'KĐVL105', N'2024-2025-HK1', 8.50, 10.00, 9.40, N'A', 4.00),
  (N'2411100103', N'LCML101', N'2024-2025-HK2', 9.50, 10.00, 9.80, N'A', 4.00),
  (N'2411100103', N'LCML102', N'2024-2025-HK2', 9.50, 9.00, 9.20, N'A', 4.00),
  (N'2411100103', N'NNTA165', N'2024-2025-HK2', 8.50, 9.00, 8.80, N'A', 4.00),
  (N'2411100103', N'MTQT106', N'2024-2025-HK2', 9.50, 9.50, 9.50, N'A', 4.00),
  (N'2411100103', N'KĐVL108', N'2024-2025-HK2', 10.00, 9.50, 9.70, N'A', 4.00),
  (N'2411100103', N'LCML103', N'2025-2026-HK1', 9.50, 10.00, 9.80, N'A', 4.00),
  (N'2411100103', N'MTKA105', N'2025-2026-HK1', 8.00, 9.00, 8.60, N'A', 4.00),
  (N'2411100103', N'MTQM106', N'2025-2026-HK1', 9.00, 9.50, 9.30, N'A', 4.00),
  (N'2411100103', N'MTQM108', N'2025-2026-HK1', 8.00, 9.50, 8.90, N'A', 4.00),
  (N'2411100103', N'MTQM105', N'2025-2026-HK1', 10.00, 9.00, 9.40, N'A', 4.00),
  (N'2411100103', N'MTQT113', N'2025-2026-HK1', 9.50, 8.50, 8.90, N'A', 4.00),
  (N'2411100103', N'MTQT114', N'2025-2026-HK1', 9.50, 9.50, 9.50, N'A', 4.00),
  (N'2411100103', N'LCTT101', N'2025-2026-HK2', 8.00, 9.00, 8.60, N'A', 4.00),
  (N'2411100103', N'MTQT115', N'2025-2026-HK2', 9.50, 9.00, 9.20, N'A', 4.00),
  (N'2411100103', N'MTQM107', N'2025-2026-HK2', 8.00, 8.50, 8.30, N'B+', 3.50),
  (N'2411100103', N'MTKA107', N'2025-2026-HK2', 9.50, 8.50, 8.90, N'A', 4.00),
  (N'2411100103', N'MTKA112', N'2025-2026-HK2', 9.50, 8.00, 8.60, N'A', 4.00),
  (N'2411100103', N'MTQM191', N'2025-2026-HK2', 8.00, 8.00, 8.00, N'B+', 3.50),
  (N'2411100103', N'MTQM189', N'2025-2026-HK2', 9.50, 10.00, 9.80, N'A', 4.00)
) AS v (ma_sv, ma_hp, ma_hk, qt, thi, tk, chu, h4)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

-- Giảng viên, phòng, tiết học là mô phỏng (giờ từng tiết của trường không công bố công khai)
INSERT INTO lop_hoc_phan (ma_lop, hoc_phan_id, hoc_ky_id, giang_vien, si_so_toi_da, thu, tiet_bat_dau, tiet_ket_thuc, phong)
SELECT v.ma_lop, hp.id, hk.id, v.gv, v.si_so, v.thu, v.bd, v.kt, v.phong FROM (VALUES
  (N'LCLS101.01', N'LCLS101', N'2026-2027-HK1', N'ThS. Đinh Thị Hồng Nhung', 120, 2, 1, 2, N'A1.201'),
  (N'MTQM124.01', N'MTQM124', N'2026-2027-HK1', N'TS. Bùi Quang Thắng', 60, 2, 3, 4, N'B2.302'),
  (N'MTQM190.01', N'MTQM190', N'2026-2027-HK1', N'ThS. Nguyễn Thanh Hương', 60, 3, 1, 2, N'B2.302'),
  (N'MTQM185.01', N'MTQM185', N'2026-2027-HK1', N'TS. Vương Đình Khánh', 40, 4, 1, 3, N'C1.PM2'),
  (N'MTQM193.01', N'MTQM193', N'2026-2027-HK1', N'PGS.TS. Hà Minh Tuấn', 60, 5, 1, 3, N'B2.303'),
  (N'MTQT140.01', N'MTQT140', N'2026-2027-HK1', N'TS. Kim Thị Hạnh', 40, 6, 6, 8, N'B2.TN1'),
  (N'MTQT141.01', N'MTQT141', N'2026-2027-HK1', N'TS. Lương Văn Sơn', 40, 7, 1, 3, N'B2.303'),
  (N'KĐTO106.01', N'KĐTO106', N'2026-2027-HK1', N'ThS. Trịnh Văn Quyết', 80, 2, 1, 2, N'A2.105'),
  (N'LCPL101.01', N'LCPL101', N'2026-2027-HK1', N'ThS. Mạc Thu Trang', 120, 2, 6, 7, N'A1.201'),
  (N'CTKU101.01', N'CTKU101', N'2026-2027-HK1', N'ThS. Phí Hoàng Nam', 40, 3, 6, 8, N'C1.PM1'),
  (N'NNTA164.01', N'NNTA164', N'2026-2027-HK1', N'ThS. Cao Thị Lệ', 40, 4, 6, 8, N'A2.204'),
  (N'KĐHH106.01', N'KĐHH106', N'2026-2027-HK1', N'TS. Đoàn Thị Thanh', 80, 5, 1, 2, N'A2.105'),
  (N'MTQM102.01', N'MTQM102', N'2026-2027-HK1', N'TS. Bùi Quang Thắng', 80, 5, 6, 7, N'B2.301'),
  (N'MTQT102.01', N'MTQT102', N'2026-2027-HK1', N'TS. Kim Thị Hạnh', 80, 6, 1, 2, N'B2.301'),
  (N'KĐVL105.01', N'KĐVL105', N'2026-2027-HK1', N'ThS. Tạ Đức Hiếu', 80, 6, 3, 4, N'A2.106'),
  (N'LCML101.01', N'LCML101', N'2026-2027-HK2', N'TS. Lã Văn Thịnh', 120, 2, 1, 3, N'A1.201'),
  (N'LCML102.01', N'LCML102', N'2026-2027-HK2', N'ThS. Đinh Thị Hồng Nhung', 120, 3, 1, 2, N'A1.201'),
  (N'NNTA165.01', N'NNTA165', N'2026-2027-HK2', N'ThS. Cao Thị Lệ', 40, 4, 1, 3, N'A2.204'),
  (N'MTQT106.01', N'MTQT106', N'2026-2027-HK2', N'TS. Lương Văn Sơn', 80, 5, 1, 3, N'B2.301'),
  (N'KĐVL108.01', N'KĐVL108', N'2026-2027-HK2', N'ThS. Tạ Đức Hiếu', 80, 6, 1, 2, N'A2.106'),
  (N'NNTA164.02', N'NNTA164', N'2026-2027-HK2', N'ThS. Ông Thị Mai', 40, 7, 1, 3, N'A2.205'),
  (N'MTCM126.01', N'MTCM126', N'2026-2027-HK2', N'TS. Nghiêm Xuân Trường', 60, 2, 6, 7, N'B2.302'),
  (N'MTQT103.01', N'MTQT103', N'2026-2027-HK2', N'TS. Kim Thị Hạnh', 60, 3, 6, 8, N'B2.303'),
  (N'MTCM117.01', N'MTCM117', N'2026-2027-HK2', N'PGS.TS. Hà Minh Tuấn', 60, 4, 6, 8, N'B2.302'),
  (N'MTQM186.01', N'MTQM186', N'2026-2027-HK2', N'TS. Vương Đình Khánh', 40, 4, 6, 7, N'C1.PM2'),
  (N'MTCM117.02', N'MTCM117', N'2026-2027-HK2', N'PGS.TS. Hà Minh Tuấn', 60, 6, 6, 8, N'B2.302'),
  (N'MTQM125.01', N'MTQM125', N'2026-2027-HK2', N'TS. Bùi Quang Thắng', 40, 5, 6, 7, N'B2.304'),
  (N'MTQM195.01', N'MTQM195', N'2026-2027-HK2', N'ThS. Nguyễn Thanh Hương', 60, 5, 8, 10, N'B2.304'),
  (N'MTKA149.01', N'MTKA149', N'2026-2027-HK2', N'ThS. Đặng Minh Châu', 30, 7, 6, 7, N'B2.TN2')
) AS v (ma_lop, ma_hp, ma_hk, gv, si_so, thu, bd, kt, phong)
JOIN hoc_phan hp ON hp.ma_hp = v.ma_hp JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

-- HK1: K24 tự đăng ký (tháng 8), K26 được trường đăng ký mặc định; HK2: Thu Hà đã đăng ký trước 2 lớp
INSERT INTO dang_ky_hoc_phan (sinh_vien_id, lop_hoc_phan_id, trang_thai, thoi_gian_dang_ky)
SELECT sv.id, l.id, N'da_dang_ky', v.tg FROM (VALUES
  (N'2411100101', N'LCLS101.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQM124.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQM190.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQM185.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQM193.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQT140.01', N'2026-08-20T09:00:00'),
  (N'2411100101', N'MTQT141.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'LCLS101.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQM124.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQM190.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQM185.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQM193.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQT140.01', N'2026-08-20T09:00:00'),
  (N'2411100102', N'MTQT141.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'LCLS101.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQM124.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQM190.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQM185.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQM193.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQT140.01', N'2026-08-20T09:00:00'),
  (N'2411100103', N'MTQT141.01', N'2026-08-20T09:00:00'),
  (N'2611100105', N'KĐTO106.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'LCPL101.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'CTKU101.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'NNTA164.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'KĐHH106.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'MTQM102.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'MTQT102.01', N'2026-08-25T08:00:00'),
  (N'2611100105', N'KĐVL105.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'KĐTO106.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'LCPL101.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'CTKU101.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'NNTA164.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'KĐHH106.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'MTQM102.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'MTQT102.01', N'2026-08-25T08:00:00'),
  (N'2611100117', N'KĐVL105.01', N'2026-08-25T08:00:00'),
  (N'2411100101', N'MTCM126.01', N'2026-11-16T20:15:00'),
  (N'2411100101', N'MTQT103.01', N'2026-11-16T20:16:00')
) AS v (ma_sv, ma_lop, tg)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN lop_hoc_phan l ON l.ma_lop = v.ma_lop;

-- Lịch thi kết thúc HK1 2026-2027 (mô phỏng)
INSERT INTO lich_thi (lop_hoc_phan_id, ngay_thi, gio_bat_dau, phong, hinh_thuc)
SELECT l.id, v.ngay, v.gio, v.phong, v.ht FROM (VALUES
  (N'LCLS101.01', N'2026-12-28', N'07:30:00', N'A1.201', N'tu_luan'),
  (N'MTQM124.01', N'2026-12-30', N'09:30:00', N'B2.302', N'tu_luan'),
  (N'MTQM190.01', N'2027-01-04', N'07:30:00', N'B2.302', N'trac_nghiem'),
  (N'MTQM185.01', N'2027-01-05', N'13:30:00', N'C1.PM2', N'do_an'),
  (N'MTQM193.01', N'2027-01-06', N'07:30:00', N'B2.303', N'tu_luan'),
  (N'MTQT140.01', N'2027-01-07', N'13:30:00', N'B2.TN1', N'do_an'),
  (N'MTQT141.01', N'2027-01-08', N'09:30:00', N'B2.303', N'van_dap'),
  (N'KĐTO106.01', N'2026-12-28', N'13:30:00', N'A2.105', N'tu_luan'),
  (N'LCPL101.01', N'2026-12-29', N'07:30:00', N'A1.201', N'trac_nghiem'),
  (N'CTKU101.01', N'2026-12-31', N'07:30:00', N'C1.PM1', N'trac_nghiem'),
  (N'NNTA164.01', N'2027-01-04', N'13:30:00', N'A2.204', N'trac_nghiem'),
  (N'KĐHH106.01', N'2027-01-05', N'07:30:00', N'A2.105', N'tu_luan'),
  (N'MTQM102.01', N'2027-01-06', N'13:30:00', N'B2.301', N'tu_luan'),
  (N'MTQT102.01', N'2027-01-07', N'07:30:00', N'B2.301', N'tu_luan'),
  (N'KĐVL105.01', N'2027-01-08', N'13:30:00', N'A2.106', N'trac_nghiem')
) AS v (ma_lop, ngay, gio, phong, ht) JOIN lop_hoc_phan l ON l.ma_lop = v.ma_lop;

-- Học phí K24 = số tín chỉ đăng ký × 475.000 đ (đơn giá mô phỏng); K26 = 9.026.000 đ tạm thu khi nhập học (số thật)
INSERT INTO hoc_phi (sinh_vien_id, hoc_ky_id, so_tien_phai_nop, so_tien_da_nop, han_nop, trang_thai)
SELECT sv.id, hk.id, v.phai, v.da, v.han, v.tt FROM (VALUES
  (N'2411100101', N'2025-2026-HK2', 8075000, 8075000, N'2026-03-31', N'da_nop'),
  (N'2411100101', N'2026-2027-HK1', 8550000, 8550000, N'2026-10-15', N'da_nop'),
  (N'2411100102', N'2025-2026-HK2', 8075000, 8075000, N'2026-03-31', N'da_nop'),
  (N'2411100102', N'2026-2027-HK1', 8550000, 4000000, N'2026-10-15', N'nop_mot_phan'),
  (N'2411100103', N'2025-2026-HK2', 8075000, 8075000, N'2026-03-31', N'da_nop'),
  (N'2411100103', N'2026-2027-HK1', 8550000, 8550000, N'2026-10-15', N'da_nop'),
  (N'2611100105', N'2026-2027-HK1', 9026000, 9026000, N'2026-09-15', N'da_nop'),
  (N'2611100117', N'2026-2027-HK1', 9026000, 9026000, N'2026-09-15', N'da_nop')
) AS v (ma_sv, ma_hk, phai, da, han, tt)
JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv JOIN hoc_ky hk ON hk.ma_hoc_ky = v.ma_hk;

INSERT INTO chung_chi (sinh_vien_id, loai, ten, ngay_cap, trang_thai_duyet)
SELECT sv.id, v.loai, v.ten, v.ngay, v.tt FROM (VALUES
  (N'2411100101', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2025-01-20', N'da_duyet'),
  (N'2411100102', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2025-01-20', N'da_duyet'),
  (N'2411100103', N'gdqp', N'Chứng chỉ Giáo dục quốc phòng - an ninh', N'2025-01-20', N'da_duyet'),
  (N'2411100103', N'ngoai_ngu', N'IELTS 6.5', N'2026-06-14', N'da_duyet')
) AS v (ma_sv, loai, ten, ngay, tt) JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv;

INSERT INTO don_tu (ma_don, sinh_vien_id, loai_don, noi_dung, trang_thai, ghi_chu_xu_ly, tao_boi)
SELECT v.ma_don, sv.id, v.loai, v.nd, v.tt, v.gc, N'sinh_vien' FROM (VALUES
  (N'DT-2026-0201', N'2411100102', N'phuc_khao', N'{"ma_hp": "MTQT106", "ly_do": "Em nghĩ bài thi bị cộng sót điểm câu 3"}', N'hoan_tat', N'Đã phúc khảo, giữ nguyên điểm thi 4,0.'),
  (N'DT-2026-0202', N'2611100105', N'giay_xac_nhan_sv', N'{"muc_dich": "Bổ sung hồ sơ vay vốn tín dụng sinh viên", "so_ban": 2, "noi_nhan": "Phòng Công tác sinh viên"}', N'dang_xu_ly', NULL)
) AS v (ma_don, ma_sv, loai, nd, tt, gc) JOIN sinh_vien sv ON sv.ma_sv = v.ma_sv;

COMMIT TRANSACTION;
PRINT N'Đã thêm dữ liệu mô phỏng HUNRE.';
GO
SET NOEXEC OFF;
GO
SELECT sv.ma_sv, sv.ho_ten, sv.lop, k.ma_khoa, COUNT(kq.id) AS so_hp_co_diem
FROM tlhv_qlsv.dbo.sinh_vien sv
JOIN tlhv_qlsv.dbo.nganh n ON n.id = sv.nganh_id AND n.ma_nganh = N'7850101'
JOIN tlhv_qlsv.dbo.khoa_hoc k ON k.id = sv.khoa_hoc_id
LEFT JOIN tlhv_qlsv.dbo.ket_qua_hoc_tap kq ON kq.sinh_vien_id = sv.id
GROUP BY sv.ma_sv, sv.ho_ten, sv.lop, k.ma_khoa ORDER BY sv.ma_sv;
GO
