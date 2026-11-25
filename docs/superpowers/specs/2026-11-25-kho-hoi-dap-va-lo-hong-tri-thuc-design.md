# Kho hỏi đáp cán bộ + trang "Lỗ hổng tri thức" — thiết kế (25/11/2026)

Người dùng chọn: **1A + 2A** ("đồng ý làm luôn"). Nối tiếp
`2026-11-23-kiem-chung-va-hoi-can-bo-design.md` (kiểm chứng câu trả lời + `ask_staff`).

## Vì sao
Câu trả lời của cán bộ cho một câu hỏi (`hoi_dap`) hiện chỉ đến được MỘT sinh viên; câu hỏi tương tự
lần sau trợ lý vẫn "không có căn cứ". Khép vòng: trợ lý trả lời → tự kiểm chứng → thiếu căn cứ thì
chuyển cán bộ → câu trả lời của cán bộ (đã biên tập) thành tri thức RAG → quản trị thấy chỗ còn thiếu.

## Phạm vi
- Mục tiêu: (1) quản trị đưa cặp hỏi–đáp đã biên tập vào kho, trợ lý tìm & trích dẫn được ngay;
  (2) trang gom các "lỗ hổng": ý bị giám khảo gắn `khong_co_can_cu`, câu hỏi gửi cán bộ, lượt 👎.
- Không làm: gom nhóm câu hỏi giống nhau (2B, để sau); xem toàn bộ hội thoại của sinh viên từ trang
  quản trị (không mở thêm quyền đọc dữ liệu); công cụ MCP mới.
- Phản mục tiêu: thông tin cá nhân của sinh viên lọt vào kho (kho trả cho MỌI sinh viên).

## Cách làm đã chọn
**1A — kho là một "văn bản" đặc biệt.**
- CSDL (nâng cấp `10`): `van_ban.loai` thêm `hoi_dap`; bảng mới `kho_hoi_dap(id, cau_hoi, tra_loi,
  phong_ban, ma_don NULL, tin_nhan_id NULL → tin_nhan ON DELETE SET NULL, nguoi_tao_id, created_at,
  updated_at)` — nguồn sự thật để sửa/gỡ.
- Một bản ghi `van_ban` duy nhất: ten "Hỏi đáp cán bộ", loai `hoi_dap`, phien_ban "kho", áp dụng mọi
  khóa, không có tệp (`duong_dan_tep` rỗng). assistant_api tạo khi có mục đầu tiên; mỗi lần thêm/sửa/
  gỡ → nhờ quy_che lập chỉ mục lại (đường nội bộ sẵn có); kho rỗng → xóa văn bản đó.
- quy_che `index_van_ban`: loai `hoi_dap` → đoạn dựng từ `kho_hoi_dap` (mỗi mục một đoạn: chuong = tên
  phòng ban, dieu = "Hỏi đáp: <câu hỏi>", nội dung "Câu hỏi … / Trả lời (phòng, ngày) …") thay vì đọc tệp.
  `rag.indexer` tách `index_chunks()` dùng chung.
- Tìm kiếm, trích dẫn [n], bọc `<tai_lieu>`, giám khảo: không đổi. Đoạn trả về thêm trường `loai` (dữ
  liệu trả về, KHÔNG đổi docstring/schema → mã băm duyệt giữ nguyên) để web ẩn nút "Mở văn bản gốc".
- Trang Tài liệu: văn bản kho hiện trong danh sách; tải tệp/xóa từ trang này bị từ chối (quản lý ở
  trang Tri thức); lập chỉ mục lại được.
- **Bảo vệ thông tin cá nhân:** form biên tập cảnh báo; backend từ chối 422 `CO_THONG_TIN_CA_NHAN` nếu
  câu hỏi/trả lời chứa mã SV (`SV` + 5 số), email, số điện thoại (≥ 9 chữ số liền).

**2A — danh sách gộp các nguồn**, `GET /api/admin/knowledge/gaps?ngay=30&nguon=`:
- `khong_can_cu`: tin nhắn có `kiem_chung` với ý `khong_co_can_cu` (ý + lý do + câu hỏi sinh viên ngay
  trước đó trong hội thoại);
- `khong_tim_thay` (**thêm khi thử trên hệ thống thật**: câu "văn bản không đề cập" — loại lỗ hổng
  hay gặp nhất — không có ý nào nên giám khảo không lưu gì, trang trống): giám khảo trả `{"y": []}` giờ là
  kết quả hợp lệ `tong = 0` (không còn coi là lỗi), tin nhắn `kiem_chung.tong = 0` là lỗ hổng;
- `danh_gia_xau`: đánh giá −1 (góp ý + câu hỏi + trích câu trả lời);
- `hoi_can_bo`: đơn `hoi_dap` từ qlsv (câu hỏi, phòng ban, trạng thái, trả lời nếu có); qlsv lỗi →
  bỏ nguồn đó, báo trong `nguon_loi`.
- KHÔNG trả mã SV/tên cho hai nguồn từ chat (tối thiểu hóa dữ liệu). Mục đã có trong kho (liên kết
  `tin_nhan_id`/`ma_don`) đánh dấu `da_vao_kho`.
- Mỗi mục có nút "Viết câu trả lời vào kho" → form điền sẵn.

## Giao diện
Trang quản trị mới **"Tri thức"** (`/admin/tri-thuc`): hai thẻ "Lỗ hổng tri thức" | "Kho hỏi đáp"
(trạng thái lập chỉ mục, danh sách, sửa, gỡ). Trang "Đơn từ": câu hỏi `hoi_dap` đã trả lời có nút
"Đưa vào kho hỏi đáp". Chat: trích dẫn từ kho hiện nhãn "Cán bộ trả lời", không có nút mở tệp.

## Việc (thứ tự làm, mỗi việc test trước)
1. CSDL `10` + `02` + model `KhoHoiDap`, Enum loai; test_db.
2. `rag.indexer.index_chunks`, quy_che lập chỉ mục kho; `loai` trong đoạn trả về + `collect_sources`.
3. Router `admin_knowledge`: CRUD kho + kiểm tra thông tin cá nhân + lập chỉ mục lại; trang Tài liệu
   chặn xóa/tệp với văn bản kho.
4. `GET /gaps`.
5. Web: `lib/knowledge.ts` (+test), trang Tri thức, nút ở Đơn từ, nhãn trích dẫn.
6. Tài liệu: docs/03, 04, 06?/08, 10, chương 4 (nếu cần), CLAUDE.md.
