# Thiết kế: RAG theo hiệu lực văn bản + mở văn bản gốc từ trích dẫn

Ngày: 23/11/2026. Người dùng giao Claude tự quyết phương án.

## Hiện trạng (trước thay đổi)
- Lọc theo khóa đã có: `ap_dung_tu_khoa`/`ap_dung_den_khoa` (Chroma + CSDL + BM25) — sinh viên K21
  nhận quy chế 2021, K22 nhận quy chế 2023.
- Trích dẫn đã có số trang (`doan_van_ban.trang`).
- Thiếu 1: `ngay_hieu_luc` lưu nhưng KHÔNG dùng → quy chế ban hành trước, áp dụng từ năm học sau, bị
  trích dẫn ngay.
- Thiếu 2: sinh viên thấy "trang 8" nhưng không mở được văn bản gốc để tự kiểm chứng.

## Mục tiêu / không làm
- Có: văn bản chưa đến ngày hiệu lực bị loại khỏi truy xuất (khi bật lọc phiên bản).
- Có: nút "Mở văn bản (trang N)" ở nguồn tham khảo; PDF mở đúng trang.
- Không: tự suy ra văn bản thay thế (cùng tên, khoảng khóa chồng nhau) — khoảng áp dụng khóa do
  quản trị viên khai báo vẫn là cách thay thế giữa các phiên bản.
- Không: thêm ngày hiệu lực vào metadata Chroma (phải lập chỉ mục lại) — lọc ở CSDL là đủ vì
  retriever vốn lọc lần 2 ở CSDL.
- Chống mục tiêu: không đổi kết quả thực nghiệm đã chạy. Kiểm tra: mọi `ngay_hieu_luc` trong
  `evaluation/corpus_*/danh_muc.csv` đều ở quá khứ.

## Phương án
1. **Lọc ngày hiệu lực ở CSDL, gộp vào điều kiện "áp dụng" (CHỌN):** một chỗ sửa (`_applies_to`),
   áp cho cả nhánh vector (lọc lần 2) và BM25; "hôm nay" theo `DEMO_NOW`; cache BM25 theo (khóa, ngày).
2. Thêm metadata ngày vào Chroma: lọc sớm hơn nhưng phải lập chỉ mục lại toàn bộ.
3. Để LLM tự đọc ngày hiệu lực trong ngữ cảnh: không chắc chắn, dễ sai.

Mở văn bản: endpoint `GET /api/documents/{id}/file` (mọi tài khoản đăng nhập; chỉ văn bản
`da_lap_chi_muc`; chỉ tệp trong `UPLOAD_DIR`). Web tải kèm JWT thành blob, mở tab mới, PDF thêm
`#page=N`. Không gửi token qua URL (quy tắc riêng tư: không đặt dữ liệu nhạy cảm vào query string).
