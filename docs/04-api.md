# 04. Đặc tả API

Lỗi chung: `{"detail": "thông báo tiếng Việt", "code": "MA_LOI"}`. Thời gian dạng ISO 8601 có múi giờ +07:00.

## A. qlsv_api (nội bộ, :8001, chỉ 127.0.0.1)
Mọi request cần header `X-Internal-Token`. Tiền tố `/internal`. Có Swagger tại `/docs` để demo duyệt đơn.

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/internal/students/{ma_sv}` | Hồ sơ: họ tên, lớp, ngành, khóa, trạng thái |
| GET | `/internal/students/{ma_sv}/transcript?ma_hoc_ky=` | Bảng điểm (mọi lần học) + GPA tích lũy + tín chỉ tích lũy |
| GET | `/internal/students/{ma_sv}/graduation-progress` | `{tong_tin_chi_yeu_cau, tin_chi_tich_luy, gpa, gpa_toi_thieu, hoc_phan_con_thieu[], chung_chi{ngoai_ngu, gdtc, gdqp}, du_dieu_kien}` |
| GET | `/internal/students/{ma_sv}/schedule?ma_hoc_ky=` | Thời khóa biểu các lớp đã đăng ký (mặc định học kỳ hiện tại) |
| GET | `/internal/students/{ma_sv}/exam-schedule?ma_hoc_ky=` | Lịch thi |
| GET | `/internal/students/{ma_sv}/tuition?ma_hoc_ky=` | Học phí |
| GET | `/internal/course-sections?q=&ma_hoc_ky=` | Lớp học phần (mặc định học kỳ đang mở đăng ký), kèm `con_trong` |
| POST | `/internal/students/{ma_sv}/registrations` | Body `{ma_lop}` → 201 hoặc 409 với mã lỗi (xem 03) |
| DELETE | `/internal/students/{ma_sv}/registrations/{ma_lop}` | Hủy (chỉ trong thời gian đăng ký) |
| POST | `/internal/students/{ma_sv}/requests` | Body `{loai_don, noi_dung, tao_boi}` → `{ma_don, trang_thai}` |
| GET | `/internal/students/{ma_sv}/requests?trang_thai=` | Danh sách đơn |
| GET | `/internal/students/{ma_sv}/requests/{ma_don}` | Chi tiết đơn (404 nếu không thuộc sinh viên này) |
| PATCH | `/internal/requests/{ma_don}` | (Cán bộ) Body `{trang_thai, ghi_chu_xu_ly}` |
| GET | `/internal/semesters/current` | Học kỳ hiện tại và học kỳ đang mở đăng ký |

## B. assistant_api (công khai, :8000, tiền tố `/api`)
Header `Authorization: Bearer <JWT>` (trừ login). Quyền: `SV` = sinh viên, `AD` = admin.

### Xác thực
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/auth/login` | – | `{email, mat_khau}` → `{access_token, token_type, het_han_luc, nguoi_dung}`. Sai email hoặc mật khẩu đều trả 401 `SAI_THONG_TIN_DANG_NHAP` (không dò được email); tài khoản khóa 403 `TAI_KHOAN_BI_KHOA` |
| GET | `/api/auth/me` | SV, AD | Thông tin tài khoản |

### Hội thoại
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/conversations` | SV | Danh sách, mới nhất trước |
| POST | `/api/conversations` | SV | Tạo mới |
| PATCH | `/api/conversations/{id}` | SV | Đổi tiêu đề |
| DELETE | `/api/conversations/{id}` | SV | Xóa |
| GET | `/api/conversations/{id}/messages` | SV | `{tin_nhan: [{id, vai_tro, noi_dung, trich_dan, danh_gia, created_at}], hanh_dong_cho_xac_nhan: [{ma, ten_cong_cu, mo_ta, het_han_luc}]}` — ẩn tin tool và bước trung gian chỉ có tool_call |
| POST | `/api/conversations/{id}/messages` | SV | `{noi_dung}` → **SSE** (xem 02 mục 5). Tự đặt tiêu đề từ câu hỏi đầu |
| POST | `/api/messages/{id}/feedback` | SV | `{diem: 1\|-1, gop_y?}`; gửi lại thì ghi đè; chỉ đánh giá được câu trả lời trong hội thoại của mình |

Mã lỗi xác thực: `CHUA_DANG_NHAP`, `TOKEN_KHONG_HOP_LE`, `PHIEN_HET_HAN` (401), `KHONG_DU_QUYEN`, `TAI_KHOAN_BI_KHOA` (403). Hội thoại của người khác trả 404 `KHONG_TIM_THAY_HOI_THOAI` (không lộ việc id tồn tại). `GET /health` trả trạng thái từng MCP server.

### Hành động chờ xác nhận
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/actions/{ma}/confirm` | SV (chủ sở hữu) | Thực thi → **SSE** (`tool_start`, `tool_end`, `token`, `done`). Lỗi trước khi mở luồng (JSON): 404 `KHONG_TIM_THAY_HANH_DONG`, 403 `KHONG_DU_QUYEN`, 409 `HANH_DONG_DA_XU_LY`, 409 `HANH_DONG_HET_HAN` |
| POST | `/api/actions/{ma}/cancel` | SV (chủ sở hữu) | Hủy, log `da_huy` → JSON `{ma, trang_thai, tin_nhan}` (câu trả lời cố định "Đã hủy...", không gọi LLM). Lỗi như confirm |

### Thủ tục của em
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/my/requests?trang_thai=` | SV | Gọi tool `list_my_requests` trực tiếp (không qua LLM), tiêm ma_sv, ghi nhật ký (`hoi_thoai_id = NULL`). Tool tắt → 503 `CHUC_NANG_TAM_DUNG` |
| GET | `/api/my/requests/{ma_don}` | SV | Chi tiết (tool `get_request_status`); đơn không thuộc em → 404 `DON_KHONG_TON_TAI` |

### Quản trị
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/admin/documents` | AD | Danh sách văn bản |
| POST | `/api/admin/documents` | AD | multipart: `tep`, `ten`, `loai`, `phien_ban`, `ap_dung_tu_khoa?`, `ap_dung_den_khoa?`, `ngay_hieu_luc?`, `chien_luoc_chunk?` → lập chỉ mục nền (BackgroundTasks) |
| GET | `/api/admin/documents/{id}/chunks?page=` | AD | Xem các đoạn |
| POST | `/api/admin/documents/{id}/reindex` | AD | Lập chỉ mục lại |
| DELETE | `/api/admin/documents/{id}` | AD | Xóa văn bản + vector |
| POST | `/api/admin/rag/search` | AD | `{cau_hoi, ma_khoa, top_k}` → thử truy xuất (debug, kèm điểm) |
| GET | `/api/admin/mcp-servers` | AD | Server + trạng thái kết nối + công cụ |
| POST | `/api/admin/mcp-servers/refresh` | AD | Đồng bộ lại danh mục công cụ |
| PATCH | `/api/admin/tools/{id}` | AD | `{bat?, can_xac_nhan?, muc_rui_ro?}` |
| GET | `/api/admin/audit-logs` | AD | Lọc: `tu`, `den`, `nguoi_dung_id`, `ten_cong_cu`, `trang_thai`, phân trang |
| GET | `/api/admin/stats?tu=&den=` | AD | Số hội thoại, số câu hỏi, tỉ lệ hữu ích, thời gian phản hồi TB, top công cụ, top câu bị chê |
