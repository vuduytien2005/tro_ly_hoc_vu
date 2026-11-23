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
| POST | `/internal/students/{ma_sv}/registrations/check` | Body `{ma_lop}` → 200 `trang_thai: "hop_le"` hoặc 409 như trên; chỉ kiểm tra, KHÔNG ghi (dùng trước khi tạo thẻ xác nhận) |
| DELETE | `/internal/students/{ma_sv}/registrations/{ma_lop}` | Hủy (chỉ trong thời gian đăng ký) |
| GET | `/internal/students/{ma_sv}/semester-plan` | Kế hoạch học kỳ đang mở đăng ký (chỉ đọc): `{hoc_ky, ten_hoc_ky, tin_chi_toi_da, tin_chi_da_dang_ky, de_xuat[{ma_lop, ma_hp, ten_hp, tin_chi, lich, bat_buoc, ly_do_chon}], tong_tin_chi_de_xuat, bi_loai[{ma_hp, ten_hp, ma_loi, ly_do, lop[{ma_lop, ma_loi, ly_do}]}]}`. Không có học kỳ mở đăng ký → 409 `KHONG_CO_HOC_KY_MO_DANG_KY` |
| POST | `/internal/students/{ma_sv}/registrations/bundle` | Body `{ma_lop: [..]}` (1–8 mã, không trùng) → 201 `{thanh_cong, trang_thai: "da_dang_ky", lop[], tong_tin_chi}`. Nguyên khối: một lớp lỗi → 409 với mã lỗi của lớp đó, `detail` bắt đầu "Lớp {ma_lop}: …", không lớp nào được ghi. Mã trùng → 422 `DANH_SACH_LOP_KHONG_HOP_LE` |
| POST | `/internal/students/{ma_sv}/registrations/bundle/check` | Như trên nhưng chỉ kiểm tra (ghi tạm rồi rollback) → 200 `trang_thai: "hop_le"` |
| POST | `/internal/students/{ma_sv}/requests` | Body `{loai_don, noi_dung, tao_boi}` → `{ma_don, trang_thai}` |
| GET | `/internal/students/{ma_sv}/requests?trang_thai=` | Danh sách đơn `[{ma_don, loai_don, trang_thai, tao_boi, created_at}]` |
| GET | `/internal/students/{ma_sv}/requests/{ma_don}` | Chi tiết đơn (404 nếu không thuộc sinh viên này) |
| GET | `/internal/requests?trang_thai=&loai_don=&page=&page_size=` | (Cán bộ, bổ sung 23/11/2026) Mọi đơn, mới nhất trước → `{tong, trang_so, so_moi_trang, don: [RequestOut + ma_sv, ho_ten]}` |
| PATCH | `/internal/requests/{ma_don}` | (Cán bộ) Body `{trang_thai, ghi_chu_xu_ly}`. Máy trạng thái (23/11/2026): `moi_tao → dang_xu_ly \| da_duyet \| tu_choi`, `dang_xu_ly → da_duyet \| tu_choi`, `da_duyet → hoan_tat`; sai bước → 409 `CHUYEN_TRANG_THAI_KHONG_HOP_LE`, đơn đã kết thúc → 409 `DON_DA_KET_THUC`, từ chối thiếu ghi chú → 422 `CAN_LY_DO_TU_CHOI`. Khóa hàng `UPDLOCK` |
| GET | `/internal/semesters/current` | Học kỳ hiện tại và học kỳ đang mở đăng ký |
| GET | `/internal/students/{ma_sv}/borrows` | (Thư viện, SV-11) Sách đang mượn `[{muon_id, ma_sach, ten_sach, tac_gia, ngay_muon, han_tra, so_lan_gia_han, qua_han, gia_han_duoc, ly_do_khong_gia_han}]` |
| GET | `/internal/books?tu_khoa=` | Tìm sách theo tên / tác giả (≤ 10) `[{ma_sach, ten_sach, tac_gia, nam_xb, tong_so_ban, so_ban_con}]` |
| POST | `/internal/students/{ma_sv}/borrows/{muon_id}/renew` | Gia hạn +14 ngày → một lượt mượn như trên. 404 `KHONG_TIM_THAY_LUOT_MUON` (cả khi lượt mượn của SV khác); 409 `DA_TRA_SACH`, `SACH_QUA_HAN`, `HET_LUOT_GIA_HAN`, `CO_NGUOI_DAT_TRUOC` |
| GET | `/internal/students?q=&trang_thai=&page=&page_size=` | (Phòng đào tạo, AD-10) `{tong, trang_so, so_moi_trang, sinh_vien: [hồ sơ như trên]}`; `q` tìm trong mã SV / họ tên / email / lớp |
| GET | `/internal/programs` | Các cặp ngành – khóa có chương trình đào tạo `[{ma_nganh, ten_nganh, ma_khoa}]` (chỉ những cặp này gán được cho SV) |
| POST | `/internal/students` | (Phòng đào tạo) `{ma_sv, ho_ten, email, ngay_sinh, gioi_tinh (nam/nu/khac), ma_nganh, ma_khoa, lop, trang_thai?}` → 201 hồ sơ. Mã SV viết hoa, email viết thường. Lỗi: 409 `SV_DA_TON_TAI` / `EMAIL_DA_TON_TAI`; 422 `NGANH_KHONG_TON_TAI`, `KHOA_HOC_KHONG_TON_TAI`, `CHUONG_TRINH_KHONG_TON_TAI`, `NGAY_SINH_KHONG_HOP_LE` |
| PATCH | `/internal/students/{ma_sv}` | (Phòng đào tạo) Gửi trường cần đổi (như trên, trừ `ma_sv` — không đổi được). Đổi `trang_thai` có tác dụng nghiệp vụ: khác `dang_hoc` thì không đăng ký học phần / nộp đơn được. Không có API xóa (SV đã có điểm, đơn → chuyển trạng thái `thoi_hoc`) |

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
| GET | `/api/conversations/{id}/trace` | SV (chủ hội thoại) | **Chế độ trình bày** (chỉ khi `CHE_DO_TRINH_BAY=true`, ngược lại 404 `KHONG_BAT_CHE_DO_TRINH_BAY`). `{luot_goi: [{id, thoi_diem, ten_cong_cu, nhan, mcp_server, tham_so_llm, tham_so_he_thong_dien, trang_thai, ly_do, thoi_gian_ms}]}` đọc từ `luot_goi_cong_cu`, theo thứ tự `id`. `tham_so_llm = null`: hệ thống tự gọi. `tham_so_he_thong_dien`: tham số LLM không gửi hoặc gửi khác (bị ghi đè), vd `{ma_sv}`. **Không** trả `ket_qua`. |
| POST | `/api/messages/{id}/feedback` | SV | `{diem: 1\|-1, gop_y?}`; gửi lại thì ghi đè; chỉ đánh giá được câu trả lời trong hội thoại của mình |

Mã lỗi xác thực: `CHUA_DANG_NHAP`, `TOKEN_KHONG_HOP_LE`, `PHIEN_HET_HAN` (401), `KHONG_DU_QUYEN`, `TAI_KHOAN_BI_KHOA` (403). Hội thoại của người khác trả 404 `KHONG_TIM_THAY_HOI_THOAI` (không lộ việc id tồn tại). `GET /health` (không cần đăng nhập) trả `mcp_server` (trạng thái từng MCP server), `gian_doan` (server đang không kết nối được — dò lại tối đa 15 giây/lần), `llm_da_cau_hinh`, `llm_co_khoa` (đã điền khóa API chưa; `null` = không xác định), `che_do_trinh_bay` (web hiện công tắc "Chế độ trình bày" khi `true`). Web đọc mỗi 30 giây để hiện banner; tool của server gián đoạn không đưa cho LLM và system prompt báo "đang gián đoạn" (khác "tạm dừng" do quản trị viên tắt).

### Hành động chờ xác nhận
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/actions/{ma}/confirm` | SV (chủ sở hữu) | Thực thi → **SSE** (`tool_start`, `tool_end`, `token`, `done`). Lỗi trước khi mở luồng (JSON): 404 `KHONG_TIM_THAY_HANH_DONG`, 403 `KHONG_DU_QUYEN`, 409 `HANH_DONG_DA_XU_LY`, 409 `HANH_DONG_HET_HAN` |
| POST | `/api/actions/{ma}/cancel` | SV (chủ sở hữu) | Hủy, log `da_huy` → JSON `{ma, trang_thai, tin_nhan}` (câu trả lời cố định "Đã hủy...", không gọi LLM). Lỗi như confirm |

### Thủ tục của em
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/my/requests?trang_thai=` | SV | Gọi tool `list_my_requests` trực tiếp (không qua LLM), tiêm ma_sv, ghi nhật ký (`hoi_thoai_id = NULL`). Trả `{don: [{ma_don, loai_don, trang_thai (nhãn tiếng Việt), ma_trang_thai (mã gốc, để tô màu nhãn), tao_boi ("Sinh viên"/"Trợ lý AI"), ngay_tao}], thong_bao}`. Tool tắt → 503 `CHUC_NANG_TAM_DUNG` |
| GET | `/api/my/requests/{ma_don}` | SV | Chi tiết (tool `get_request_status`): thêm `noi_dung`, `ghi_chu_xu_ly`, `cap_nhat_luc`, cũng có `ma_trang_thai`, `tao_boi`; đơn không thuộc em → 404 `DON_KHONG_TON_TAI` |
| GET | `/api/my/reminders` | SV | Nhắc việc (bổ sung 23/11/2026): gọi trực tiếp các tool đọc `get_tuition_status`, `get_exam_schedule`, `get_borrowed_books`, `list_my_requests` (tool tắt / server chưa cài → bỏ qua, KHÔNG gọi), tiêm ma_sv, ghi nhật ký lý do "Nhắc việc tự động (trang sinh viên)". Trả `{ngay, nhac_viec: [{loai (hoc_phi|lich_thi|sach|don), \|lich_thi\|sach), muc_do (khan\|sap_toi), tieu_de, chi_tiet, han, con_ngay, cau_hoi}], nguon_loi: [tên tool lỗi]}`. Quy tắc: học phí còn nợ, hạn ≤ 30 ngày (khẩn ≤ 7 hoặc quá hạn); thi trong 14 ngày (khẩn ≤ 3); sách hạn ≤ 7 ngày hoặc quá hạn (khẩn ≤ 2); đơn được duyệt / từ chối (khẩn) / hoàn tất trong 7 ngày. "Hôm nay" theo `DEMO_NOW` nếu có. Thiết kế: `docs/superpowers/specs/2026-11-23-nhac-viec-design.md` |
| GET | `/api/documents/{van_ban_id}/file` | Đăng nhập | Tệp gốc văn bản (bổ sung 23/11/2026), `Content-Disposition: inline`. Chỉ văn bản `da_lap_chi_muc`, chỉ tệp trong `UPLOAD_DIR`; khác → 404 `VAN_BAN_KHONG_TON_TAI`. Web mở từ nút "Mở văn bản (trang N)" ở nguồn tham khảo (PDF thêm `#page=N`) |
| GET | `/api/documents/{van_ban_id}/articles/{so_dieu}` | Đăng nhập | Nguyên văn một Điều (bổ sung 23/11/2026) → `{van_ban_id, so_dieu, noi_dung}`. Đọc **MCP resource** `quy-che://van-ban/{id}/dieu/{so}` (không qua LLM, không ghi `luot_goi_cong_cu` vì không phải gọi công cụ). Không có / số Điều sai → 404 `DIEU_KHONG_TON_TAI`; quy_che không chạy → 503 `DICH_VU_KHONG_KHA_DUNG` |

### Quản trị
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/admin/documents` | AD | Danh sách văn bản `[{id, ten, loai, phien_ban, ap_dung_tu_khoa, ap_dung_den_khoa, ngay_hieu_luc, ten_tep, trang_thai, chien_luoc_chunk, so_doan, loi, created_at, updated_at}]` |
| POST | `/api/admin/documents` | AD | multipart: `tep` (PDF/DOCX/TXT ≤ 20 MB, kiểm tra cả nội dung), `ten`, `loai`, `phien_ban`, `ap_dung_tu_khoa?` (22 hoặc K22), `ap_dung_den_khoa?`, `ngay_hieu_luc?` (YYYY-MM-DD), `chien_luoc_chunk?` → 202, `trang_thai = dang_xu_ly`; server `quy_che` lập chỉ mục nền (docs/02 mục 8). Trùng (ten, loai, phien_ban) → thay thế tệp cũ. Lỗi: 415 `DINH_DANG_KHONG_HO_TRO` / `TEP_KHONG_HOP_LE`, 413 `TEP_QUA_LON`, 422 `TEP_RONG`, 409 `VAN_BAN_DANG_XU_LY`, 503 `QUY_CHE_KHONG_KET_NOI` (văn bản chuyển `loi`) |
| GET | `/api/admin/documents/{id}/chunks?page=&page_size=` | AD | `{tong, trang_so, so_moi_trang, doan: [{id, thu_tu, chuong, dieu, khoan, trang, so_token, noi_dung}]}` |
| POST | `/api/admin/documents/{id}/reindex` | AD | Lập chỉ mục lại từ tệp gốc → 202. Mất tệp gốc → 409 `TEP_GOC_KHONG_CON` |
| DELETE | `/api/admin/documents/{id}` | AD | Xóa văn bản + đoạn + vector (qua quy_che) + tệp gốc trong `data/van_ban/` → 204 |
| POST | `/api/admin/rag/search` | AD | `{cau_hoi, ma_khoa, top_k (1–20), use_vector, use_keyword, use_version_filter, use_rerank}` → `{thoi_gian_ms, ghi_chu: [...], doan: [{so, van_ban, phien_ban, dieu, khoan, trang, noi_dung, diem, hang_vector, hang_tu_khoa, diem_rerank}]}`. Lỗi 422 `THIEU_MA_KHOA`, `CAN_BAT_MOT_NHANH`, `MA_KHOA_KHONG_HOP_LE` |
| GET | `/api/admin/mcp-servers` | AD | `[{id, ten, mo_ta, dia_chi, bat, trang_thai ("ok" / "tắt" / lỗi kết nối), cong_cu: [{id, ten, mo_ta, muc_rui_ro, can_xac_nhan, bat, co_tren_server, title, mo_ta_day_du, tham_so, chi_doc_theo_server, duyet (da_duyet / moi / thay_doi)}], cong_cu_bi_bo_qua: [{ten, trung_voi}]}]` |
| POST | `/api/admin/mcp-servers/refresh` | AD | Kết nối lại, đồng bộ danh mục công cụ (tool mới thêm với `bat=0`) → như GET |
| POST | `/api/admin/mcp-servers/check` | AD | (AD-11) `{dia_chi}` → `{cong_cu: [{ten, title, mo_ta, tham_so (đã ẩn ma_sv/ma_khoa), chi_doc_theo_server, trung_ten_voi}]}`. Không ghi CSDL. 422 `DIA_CHI_MCP_KHONG_HOP_LE` (chỉ `http://127.0.0.1:<cổng>` hoặc `http://localhost:<cổng>`, không user/mật khẩu), 422 `MCP_KHONG_KET_NOI_DUOC` |
| POST | `/api/admin/mcp-servers` | AD | `{ten, mo_ta, dia_chi}` → 201 một server như GET (công cụ mới `bat=0`, `duyet=moi`). `ten` khớp `^[a-z][a-z0-9_]{1,49}$` → 422 `TEN_MCP_KHONG_HOP_LE`; trùng → 409 `TEN_MCP_DA_TON_TAI`; kiểm tra địa chỉ + kết nối như `check` trước khi lưu |
| PATCH | `/api/admin/mcp-servers/{id}` | AD | `{mo_ta?, dia_chi?, bat?}` → server như GET. Địa chỉ mới kiểm tra như khi thêm, sai thì CSDL giữ nguyên. 404 `MCP_KHONG_TON_TAI` |
| PATCH | `/api/admin/tools/{id}` | AD | `{bat?, can_xac_nhan?, muc_rui_ro?}` — có hiệu lực ngay ở lượt chat kế tiếp. `bat=true` = duyệt: ghi `ban_duyet` (mã băm mô tả hiện tại). Công cụ mức `ghi`/`nhay_cam` không được bỏ xác nhận → 422 `KHONG_THE_BO_XAC_NHAN` (bảo vệ quy tắc 2) |
| GET | `/api/admin/audit-logs` | AD | Lọc: `tu`, `den` (ngày, tính trọn ngày giờ VN), `nguoi_dung_id`, `ten_cong_cu`, `trang_thai`; `page`, `page_size` (≤ 100). `{tong, trang_so, so_moi_trang, luot_goi: [{id, created_at, nguoi_dung {id, ho_ten, email}, hoi_thoai_id, mcp_server, ten_cong_cu, trang_thai, ly_do, thoi_gian_ms, tham_so, tham_so_llm, da_tiem_ngu_canh}]}` — `da_tiem_ngu_canh = tham_so_llm` khác `tham_so` |
| GET | `/api/admin/audit-logs/{id}` | AD | Như một dòng ở trên + `ket_qua` |
| GET | `/api/admin/users?tu_khoa=&vai_tro=&page=&page_size=` | AD | (AD-09) `tu_khoa` tìm trong email / họ tên / mã SV. `{tong, trang_so, so_moi_trang, nguoi_dung: [{id, email, ho_ten, vai_tro, ma_sv, ma_khoa, dang_hoat_dong, created_at}]}` |
| POST | `/api/admin/users` | AD | `{ma_sv, mat_khau}` (mật khẩu tạm 8–72 ký tự, có chữ và số) → 201, một tài khoản như trên. Họ tên, email, `ma_khoa` đọc từ qlsv_api `GET /internal/students/{ma_sv}` (X-Internal-Token) — admin không tự nhập → `ma_sv` mà trợ lý tiêm luôn ứng với sinh viên có thật. Lỗi: 404 `SV_KHONG_TON_TAI`, 409 `TAI_KHOAN_DA_TON_TAI` (mã SV đã có tài khoản) / `EMAIL_DA_TON_TAI`, 422 `MAT_KHAU_YEU`, 503 `QLSV_KHONG_KET_NOI` |
| PATCH | `/api/admin/users/{id}` | AD | `{dang_hoat_dong}` khóa / mở khóa — có hiệu lực ngay ở request kế tiếp (JWT cũ bị từ chối 403 `TAI_KHOAN_BI_KHOA`). Tự khóa mình → 422 `KHONG_THE_KHOA_CHINH_MINH`; 404 `TAI_KHOAN_KHONG_TON_TAI` |
| POST | `/api/admin/users/{id}/reset-password` | AD | `{mat_khau}` (quy tắc như trên) → 204 |
| GET | `/api/admin/students?q=&trang_thai=&page=&page_size=` | AD | (AD-10) Chuyển tiếp `GET /internal/students`, mỗi sinh viên thêm `tai_khoan: {id, dang_hoat_dong} \| null` |
| GET | `/api/admin/students/programs` | AD | Chuyển tiếp `GET /internal/programs` (cho ô chọn ngành / khóa) |
| POST | `/api/admin/students` | AD | Body như `POST /internal/students` + `cap_tai_khoan?`, `mat_khau?` → 201 `{sinh_vien, tai_khoan \| null, canh_bao}`. Khi cấp tài khoản: kiểm tra mật khẩu, mã SV / email chưa có tài khoản TRƯỚC khi ghi QLSV. Lỗi nghiệp vụ của qlsv_api chuyển nguyên văn |
| PATCH | `/api/admin/students/{ma_sv}` | AD | Chuyển tiếp `PATCH /internal/students/{ma_sv}`, rồi ĐỒNG BỘ tài khoản liên kết (`ho_ten`, `email`, `ma_khoa`) — nếu không, trợ lý lọc quy chế theo khóa cũ. Email trùng tài khoản khác → 409 `EMAIL_DA_TON_TAI` (chặn trước khi ghi QLSV) |
| GET | `/api/admin/requests?trang_thai=&loai_don=&page=&page_size=` | AD | Duyệt đơn (23/11/2026): chuyển tiếp `GET /internal/requests` qua `QlsvDirectory` (thao tác cán bộ, không qua MCP/LLM) |
| PATCH | `/api/admin/requests/{ma_don}` | AD | Body `{trang_thai, ghi_chu_xu_ly}` → chuyển tiếp `PATCH /internal/requests/{ma_don}`; lỗi 4xx của qlsv_api chuyển nguyên văn. Thiết kế: `docs/superpowers/specs/2026-11-23-duyet-don-design.md` |
| GET | `/api/admin/stats?tu=&den=` | AD | Mặc định 30 ngày gần nhất. `{tu, den, so_hoi_thoai, so_cau_hoi (không tính tin "Xác nhận:/Hủy:" do hệ thống lưu), so_danh_gia, so_huu_ich, ti_le_huu_ich, thoi_gian_phan_hoi_tb_ms, so_luot_goi_cong_cu, top_cong_cu: [{ten_cong_cu, so_lan, so_loi}], theo_ngay: [{ngay, so_cau_hoi}], cau_bi_che: [{tin_nhan_id, hoi_thoai_id, nguoi_dung, cau_hoi, cau_tra_loi, gop_y, created_at}]}` |

### OAuth cho MCP (23/11/2026, công khai, không tiền tố `/api`)
| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/.well-known/oauth-authorization-server` | – | Metadata authorization server (RFC 8414): `issuer`, `jwks_uri`, `scopes_supported`, `token_endpoint_auth_methods_supported` |
| GET | `/.well-known/jwks.json` | – | Khóa CÔNG KHAI Ed25519 để MCP server kiểm token |
| GET | `http://127.0.0.1:<cổng MCP>/.well-known/oauth-protected-resource/mcp` | – | (Trên từng MCP server, RFC 9728) `{resource, authorization_servers, ...}`. `/mcp` thiếu hoặc sai token → 401 `THIEU_TOKEN` / `TOKEN_KHONG_HOP_LE` + `WWW-Authenticate: Bearer error="invalid_token", resource_metadata="..."` |
