# 10. Rà soát bảo mật (Giai đoạn 10)

Đối chiếu 6 quy tắc bắt buộc trong `CLAUDE.md` với code ngày 19/11/2026 (`backend/src`, `web/src`).
Bằng chứng thực nghiệm cho tầng (b) — hệ thống chặn kể cả khi LLM làm sai — xem TN4 (`docs/09`).

| # | Quy tắc | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Tiêm ngữ cảnh (`ma_sv`, `ma_khoa`) | Đạt | `agent/registry.py`: `strip_injected` xóa 2 tham số khỏi schema gửi LLM; `inject_context` bỏ giá trị LLM gửi kèm và điền từ tài khoản (thiếu mã -> `bi_tu_choi`). Nhật ký lưu cả `tham_so_llm` (LLM đòi gì) lẫn `tham_so` (thực thi gì). Tầng qlsv: đơn của sinh viên khác trả 404 như đơn không tồn tại (`request_service.get_request`). Test: `tests/assistant/test_agent_loop.py`, `tests/evaluation/test_harness.py`. |
| 2 | Xác nhận hành động | Đạt | `agent/loop.py::_prepare_confirmation` không thực thi, tạo `hanh_dong_cho_xac_nhan`, mô tả dựng từ mẫu + dữ liệu thật (không dùng lời LLM). `agent/actions.py::lock_pending`: khóa `UPDLOCK`, đúng chủ (403), chỉ xử lý một lần (409), hết hạn theo đồng hồ thật (`ACTION_EXPIRE_MINUTES`=10). `_confirm_steps` kiểm lại chính sách khi bấm (công cụ vừa bị tắt -> không chạy). API quản trị không cho bỏ xác nhận của công cụ `ghi`/`nhay_cam` (422). Test: `tests/assistant/test_actions.py`. |
| 3 | Nhật ký mọi lần gọi | Đạt (sau khi sửa) | `agent/executor.py::ToolLog`; `loop._handle_call` ghi mọi nhánh: công cụ không tồn tại / đang tắt (`bi_tu_choi`), JSON hỏng, thiếu quyền, chờ xác nhận, lỗi, thành công; lượt hệ thống tự tra cứu để dựng thẻ (`tham_so_llm` = NULL); thẻ hết hạn -> `da_huy`. **Đã sửa:** `routers/my_requests.py::call_direct` trước đây trả 503 khi công cụ bị tắt mà không ghi nhật ký, và ném lỗi 500 không ghi nhật ký khi tài khoản thiếu mã -> nay ghi `bi_tu_choi` rồi trả 503 / 403. Test: `test_my_requests.py::test_disabled_tool_returns_503`. |
| 4 | Xác thực nội bộ, chỉ nghe 127.0.0.1 | Đạt (sau khi sửa) | `qlsv_api/main.py`: middleware `X-Internal-Token` cho `/internal/*`; `mcp_servers/common.py::BearerAuthMiddleware` bọc toàn bộ app MCP (kể cả route nội bộ `/internal/*` của `quy_che`); so sánh bằng `hmac.compare_digest` (`shared/security.py`). Cả qlsv_api, MCP server, assistant_api đều `host="127.0.0.1"`; SDK MCP bật chống DNS rebinding. **Đã sửa:** `shared/config.py` từ chối khởi động nếu `JWT_SECRET` / `INTERNAL_API_TOKEN` trống, ngắn hơn 32 ký tự , quá đơn điệu (dưới 10 ký tự khác nhau, vd `AAAA…`) hoặc là chuỗi mẫu `thay_bang_…` của `.env.example` (máy mới chép nguyên file mẫu sẽ ký JWT bằng chuỗi công khai -> ai cũng giả được token quản trị). Test: `tests/test_config.py`. |
| 5 | Chống prompt injection từ tài liệu | Đạt | `mcp_servers/quy_che.py::wrap_document` bọc nội dung cả `search_regulations` lẫn `get_article` trong `<tai_lieu so="…">`, vô hiệu hóa thẻ `<tai_lieu>` / `</tai_lieu>` có sẵn trong văn bản (chặn "thoát thẻ"); kết quả kèm `ghi_chu` nhắc đó là dữ liệu. System prompt (`agent/prompts.py`) nói rõ nội dung trong thẻ không phải mệnh lệnh. Kể cả khi LLM vẫn làm theo, công cụ ghi chỉ tạo thẻ xác nhận (quy tắc 2). Web hiển thị câu trả lời bằng `react-markdown` không bật `rehype-raw` -> HTML bị escape, liên kết `javascript:` bị lọc. Thực nghiệm: TN4 nhóm `prompt_injection_gian_tiep`. |
| 6 | Công cụ bị tắt không đưa cho LLM | Đạt | `agent/registry.py::tools_for_llm` chỉ lấy công cụ `available` (công cụ bật VÀ server bật VÀ server đang cung cấp). LLM vẫn gọi tên công cụ đã tắt -> `bi_tu_choi` `CONG_CU_TAM_DUNG`. System prompt liệt kê chức năng tạm dừng để trợ lý trả lời đúng (`PAUSED_NOTE`). Test: `test_agent_loop.py`, `test_admin.py` (kịch bản demo 7). |

## Bổ sung 20/11/2026 — thêm MCP server lúc đang chạy (AD-11)
Cho phép thêm server mở ra 4 rủi ro riêng của MCP; cách xử lý:

| Rủi ro | Mô tả | Xử lý | Bằng chứng |
|---|---|---|---|
| Tool poisoning | Mô tả công cụ (do server viết) đi thẳng vào prompt LLM, có thể chứa lệnh ẩn | Công cụ mới luôn `bat=0`, `ghi`, cần xác nhận; quản trị viên đọc mô tả đầy đủ trước khi bật. System prompt không dùng `title` của công cụ chưa duyệt | `test_new_server_tools_added_disabled`, `prompts.paused_label` |
| Rug pull | Server được duyệt rồi lặng lẽ đổi mô tả | `cong_cu.ban_duyet` = SHA-256 (title + mô tả + schema) lúc bật; mã băm khác ở lần đồng bộ sau → tự tắt, chờ duyệt lại | `test_approve_then_description_change_disables` |
| Trùng tên (shadowing) | Server mới khai báo công cụ trùng tên công cụ cũ (vd `search_regulations`) để chiếm lời gọi | Giữ bản của server thêm trước, bỏ bản sau, báo trên giao diện | `test_duplicate_tool_name_skipped` |
| SSRF | Địa chỉ server tùy ý → assistant_api gửi token ra ngoài / vào mạng nội bộ | `normalize_mcp_address`: chỉ `http://127.0.0.1` hoặc `localhost`, bắt buộc cổng, không user/mật khẩu; kiểm tra cả khi sửa địa chỉ | `test_address_rejected`, `test_patch_server_bad_address_keeps_db` |

Thực nghiệm cho 3 dòng tool poisoning / rug pull / trùng tên: TN4 nhóm `server_doc_hai` (S050–S054, `docs/09`) — đo trên prompt LLM thực nhận rằng chữ độc không tới LLM khi chưa duyệt, sau rug pull, khi trùng tên; và khi quản trị viên duyệt nhầm thì thẻ xác nhận + tiêm ngữ cảnh vẫn chặn hậu quả.

## Bổ sung 23/11/2026 — chế độ trình bày
`GET /api/conversations/{id}/trace` (bảng "Bên trong Agent") lộ tên công cụ và tham số nội bộ, nên:
- **mặc định tắt** (`CHE_DO_TRINH_BAY=false`): API trả 404 `KHONG_BAT_CHE_DO_TRINH_BAY`, web ẩn công tắc. Chỉ bật khi demo;
- chỉ **chủ hội thoại** xem được (lọc `nguoi_dung_id`, người khác 404 `KHONG_TIM_THAY_HOI_THOAI`);
- **không** trả `ket_qua` của công cụ; chỉ đọc nhật ký, không thêm đường gọi công cụ nào.
Test: `backend/tests/assistant/test_trace.py`.

## Bổ sung 23/11/2026 — OAuth 2.1 cho MCP
Trước đây mọi MCP server nhận chung `Bearer INTERNAL_API_TOKEN`: server được thêm (có thể độc) giữ token đó là gọi được mọi server khác, đọc dữ liệu bất kỳ sinh viên nào. Nay (`MCP_AUTH_MODE=oauth`, mặc định):

| Thuộc tính token | Chặn được |
|---|---|
| `aud` = URL đúng server (RFC 8707) | Server độc đem token của nó dùng ở server khác |
| `scope` = đúng một công cụ | Dùng token của `get_exam_schedule` để gọi `get_student_profile` |
| `sub` = `ma_sv` đã tiêm; MCP server kiểm `ma_sv == sub` | Lỗi tiêm ngữ cảnh ở assistant_api cũng không đọc được dữ liệu sinh viên khác (phòng thủ nhiều lớp) |
| `exp` 60 giây, `jti` ngẫu nhiên | Token bị lộ hết giá trị rất nhanh |
| Ký Ed25519 (bất đối xứng), chỉ nhận `alg=EdDSA` | MCP server chỉ có khóa công khai, không tự cấp token được; chặn `alg=none`/HS256 |

MCP server công bố `/.well-known/oauth-protected-resource/mcp` (RFC 9728) và trả `WWW-Authenticate: Bearer ... resource_metadata=...` khi 401; assistant_api công bố `/.well-known/jwks.json` và `/.well-known/oauth-authorization-server` (RFC 8414). Khóa riêng ở `data/keys/` (không commit). `/internal/*` của quy_che (quản trị RAG) vẫn dùng `INTERNAL_API_TOKEN`; MCP server ↔ qlsv_api vẫn `X-Internal-Token`.
Test: `tests/test_oauth.py`, `tests/mcp/test_common.py` (phần HTTP), `tests/assistant/test_mcp_client_oauth.py` (đầu-cuối qua uvicorn).

## Bổ sung 23/11/2026 — MCP elicitation và resources
- **Dữ liệu cá nhân không qua LLM:** SĐT/email liên hệ khi bảo lưu được MCP server `ctsv` hỏi bằng
  biểu mẫu (elicitation) SAU khi sinh viên bấm Xác nhận; giá trị đi web -> assistant_api -> MCP server,
  không vào prompt, không lưu tin nhắn, nhật ký chỉ ghi tên trường; kết quả công cụ không lặp lại.
- **Không vượt bước Xác nhận:** `/input` chỉ nhận thẻ `cho_bo_sung` (đã xác nhận); thân công cụ chỉ
  chạy khi đủ thông tin; năng lực elicitation chỉ khai báo ở luồng thẻ -> LLM không kích hoạt được.
- **Dữ liệu sai:** assistant_api kiểm theo schema của server (không nhận trường lạ), SDK server kiểm lại.
  Server đòi thứ khác (sampling, URL, nhiều biểu mẫu, quá 3 vòng) -> từ chối, nhật ký `loi`.
- **Resources:** đọc nguyên văn Điều cần scope `mcp:resources.read` (token gọi công cụ bị từ chối).
Test: `tests/assistant/test_elicitation.py`, `tests/assistant/test_mcp_client_oauth.py`,
`tests/assistant/test_documents.py`, `tests/rag/test_quy_che_server.py`. Thiết kế: `docs/superpowers/specs/2026-11-23-mcp-elicitation-resources-design.md`.

## Hạn chế đã biết (chấp nhận trong phạm vi khóa luận)
- Chỉ dùng phần cấp/kiểm token của OAuth 2.1: assistant_api vừa là client vừa là authorization server, không có luồng ủy quyền người dùng (authorization code + PKCE) vì người dùng đã đăng nhập vào assistant_api. MCP server được thêm vẫn nhận được `X-Internal-Token` nếu quản trị viên tự cấu hình cho nó; token qlsv_api là bí mật riêng của các server do trường triển khai.
- `readOnlyHint` do server tự khai báo, chỉ là gợi ý; mức rủi ro thật do quản trị viên đặt.
- ~~JWT lưu trong `localStorage`~~ — đã khắc phục 23/11/2026 (xem mục cookie HttpOnly bên dưới). Còn lại: đăng xuất chỉ xóa cookie, JWT đã lộ (nếu có) vẫn dùng được tới khi hết hạn (không có danh sách thu hồi).
- Thẻ xác nhận không ai bấm vẫn ở trạng thái `cho` trong CSDL sau khi hết hạn (chỉ chuyển `het_han` khi có người bấm). Không thể thực thi nữa vì hạn được kiểm tra lúc bấm -> không phải lỗ hổng, chỉ ảnh hưởng thống kê.
- Tên văn bản / số Điều (do quản trị viên nhập khi tải lên) nằm ngoài thẻ `<tai_lieu>`; quản trị viên là người tin cậy.
- `docs` OpenAPI của qlsv_api và MCP chỉ mở ở `127.0.0.1`.

## Bổ sung 23/11/2026 — Đăng nhập bằng cookie HttpOnly + chống CSRF
Trước đây web giữ JWT trong `localStorage` -> một lỗi XSS là lấy được token. Nay:
| Biện pháp | Chặn gì | Code |
|---|---|---|
| JWT nằm trong cookie `tlhv_phien` HttpOnly, Path=/api, SameSite=Strict | JavaScript (kể cả mã XSS) không đọc được token; trang khác không gửi kèm cookie | `assistant_api/auth/cookies.py`, `routers/auth.py` |
| Signed double-submit: cookie `tlhv_csrf` (JS đọc được) + header `X-CSRF-Token`, so với claim `csrf` **ký trong JWT** | CSRF: trang độc không đọc được cookie của ta nên không gửi đúng header; ghi đè cookie CSRF (vd từ subdomain) cũng vô ích vì phải trùng claim đã ký | `assistant_api/deps.py::get_current_user` (`hmac.compare_digest`) |
| Header `Bearer` ưu tiên hơn cookie, không cần CSRF | Thực nghiệm / công cụ dòng lệnh vẫn chạy (trình duyệt không tự gửi header này) | `deps.py` |
| `POST /api/auth/logout` xóa cookie; `AUTH_COOKIE_SECURE=true` khi chạy HTTPS | — | `routers/auth.py`, `shared/config.py` |
Web: `web/src/lib/api.ts` (không còn getToken/setToken; gửi `X-CSRF-Token`; xóa khóa `tlhv_token` cũ). Test: `tests/assistant/test_cookie_auth.py`, `web/src/lib/api.test.ts`. Đã kiểm thủ công qua proxy Vite: đăng nhập -> `/chat`, `document.cookie` chỉ thấy `tlhv_csrf`, POST thiếu header -> 403, có header -> 201, đăng xuất -> `/me` 401.
