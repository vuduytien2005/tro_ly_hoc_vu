# Thiết kế: Quy trình duyệt đơn hai phía

Ngày: 23/11/2026. Người dùng giao Claude tự quyết phương án.

## Mục đích
Hiện Agent nộp đơn (giấy xác nhận SV, bảo lưu, phúc khảo) xong là dừng: đơn nằm mãi ở `moi_tao`,
chỉ đổi được trạng thái bằng cách gọi thẳng `PATCH /internal/requests/{ma_don}` của qlsv_api. Tính
năng này hoàn thiện vòng đời: **cán bộ xử lý đơn trên trang quản trị**, sinh viên thấy kết quả và ghi
chú xử lý ở "Thủ tục của em" (đã có sẵn) hoặc hỏi trợ lý (`get_request_status` đã có sẵn).

## Mục tiêu / không làm
- Có: trang quản trị "Đơn từ" — lọc theo trạng thái / loại, xem nội dung, chuyển trạng thái kèm ghi chú.
- Có: máy trạng thái rõ ràng ở qlsv_api (nguồn sự thật), từ chối phải có lý do.
- Không: vai trò "cán bộ" riêng — CSDL chỉ có `sinh_vien`/`admin`; thêm vai trò cần nâng cấp CSDL và
  phân quyền mới. Quản trị viên đóng vai cán bộ phòng CTSV/đào tạo (như trang "Sinh viên (QLSV)").
- Không: hệ quả nghiệp vụ tự động (vd bảo lưu xong đổi `sinh_vien.trang_thai`) — để hướng phát triển.
- Không: công cụ MCP mới (không đổi tập công cụ của thực nghiệm).

## Phương án đã cân nhắc
1. **assistant_api gọi qlsv_api qua `QlsvDirectory` (CHỌN)** — đúng ngoại lệ đã có trong docs/02:
   thao tác của cán bộ, không phải hành động của Agent, nên không đi qua MCP/LLM.
2. Thêm công cụ MCP `review_request` cho Agent dùng ở phía cán bộ: thú vị nhưng đưa thao tác cán bộ
   vào tay LLM, cần tiêm vai trò, đổi thực nghiệm — quá rộng.
3. Cho cán bộ sửa thẳng CSDL `tlhv_qlsv`: trái kiến trúc (QLSV là nguồn sự thật qua API).

## Thiết kế
**Máy trạng thái** (qlsv_api `request_service.update_status`, khóa hàng `UPDLOCK`):
`moi_tao → dang_xu_ly | da_duyet | tu_choi`; `dang_xu_ly → da_duyet | tu_choi`;
`da_duyet → hoan_tat`; `tu_choi`, `hoan_tat` là trạng thái cuối (`DON_DA_KET_THUC`, 409).
Chuyển sai → 409 `CHUYEN_TRANG_THAI_KHONG_HOP_LE`. `tu_choi` thiếu ghi chú → 422 `CAN_LY_DO_TU_CHOI`.

**qlsv_api** `GET /internal/requests?trang_thai=&loai_don=&trang=&so_moi_trang=` — mọi đơn (mới nhất
trước) kèm `ma_sv`, `ho_ten`; trả `{tong, trang_so, so_moi_trang, don: [...]}`.

**assistant_api** (chỉ admin): `GET /api/admin/requests` (chuyển tham số), `PATCH
/api/admin/requests/{ma_don}` body `{trang_thai, ghi_chu_xu_ly}`; lỗi 4xx của qlsv chuyển nguyên văn.

**Web** `/admin/don-tu` "Đơn từ": bộ lọc trạng thái (mặc định "Mới tạo") và loại; bảng đơn; bấm một
đơn mở chi tiết (nội dung, ghi chú cũ), ô ghi chú, nút cho đúng các bước kế tiếp hợp lệ.

## Để lại cho người làm
Bố cục bảng, nhãn tiếng Việt của trạng thái/loại (dùng lại nhãn đã có nếu có).
