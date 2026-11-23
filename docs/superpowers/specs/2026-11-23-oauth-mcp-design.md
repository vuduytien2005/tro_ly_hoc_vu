# Thiết kế: Xác thực OAuth 2.1 (token JWT ngắn hạn, gắn đối tượng) cho MCP

Ngày: 23/11/2026. Người dùng giao Claude tự quyết phương án.

## Vấn đề của cách cũ
assistant_api gửi **cùng một** `Authorization: Bearer <INTERNAL_API_TOKEN>` tới MỌI MCP server —
kể cả server quản trị viên thêm bằng URL (`thu_vien`, hay server độc ở TN4 `server_doc_hai`).
Một server độc nhận được token này có thể **dùng lại** nó gọi thẳng `dao_tao`/`ctsv` với bất kỳ
`ma_sv` nào: token không hết hạn, không gắn server, không gắn công cụ, không gắn người dùng.

## Mục tiêu / không làm
- Có: token theo mô hình OAuth 2.1 / MCP Authorization — MCP server là *resource server*,
  assistant_api là *authorization server* (đồng thời là client duy nhất).
  - `aud` = URL MCP server (RFC 8707 resource indicator) → token cho `thu_vien` không dùng được ở `dao_tao`.
  - `scope` = `mcp:tool:<tên>` cho một lần gọi, `mcp:tools.list` cho liệt kê → chỉ gọi được đúng công cụ đó.
  - `sub` = `ma_sv` của sinh viên đang đăng nhập; MCP server từ chối nếu tham số `ma_sv` ≠ `sub`
    (**phòng thủ nhiều lớp** cho quy tắc tiêm ngữ cảnh: lỗi ở assistant_api cũng không lộ dữ liệu SV khác).
  - `exp` = 60 giây; ký **Ed25519 (EdDSA)** — MCP server chỉ có khóa CÔNG KHAI (JWKS), không tự ký được.
  - MCP server công bố `/.well-known/oauth-protected-resource` (RFC 9728); 401 kèm
    `WWW-Authenticate: Bearer error="invalid_token", resource_metadata="…"`.
- Không: endpoint `/oauth/token` qua HTTP, đăng ký client động, luồng ủy quyền có trình duyệt — client
  và authorization server cùng tiến trình, cấp token là lời gọi hàm (tương đương grant
  `client_credentials` + resource indicator). Nêu rõ trong khóa luận.
- Không đổi: `/internal/*` của quy_che (assistant_api quản trị RAG) và MCP → qlsv_api vẫn dùng
  token nội bộ; thực nghiệm (server chạy trong tiến trình, không qua HTTP) không đổi.

## Phương án đã cân nhắc
1. **JWT EdDSA tự cấp + middleware ASGI của dự án, đặt `AccessToken` vào context của SDK (CHỌN).**
   Dùng kiểu `AccessToken`/`get_access_token()` của SDK `mcp` để công cụ đọc token; giữ định dạng lỗi
   `{detail, code}` của dự án; không chạm thuộc tính riêng của `MCPServer`.
2. Bật `MCPServer(auth=AuthSettings(...), token_verifier=...)` của SDK: đúng chuẩn hơn về hình thức
   nhưng phải cấu hình lúc tạo đối tượng ở mức module (cần cổng/URL ngay khi import), lỗi 401 không
   theo định dạng dự án, và `/internal/*` của quy_che vẫn cần middleware riêng.
3. HMAC (HS256) dùng chung khóa: đơn giản nhưng server nào kiểm được thì cũng ký được → server độc tự
   cấp token cho `dao_tao`. Loại.

## Thiết kế
- `src/shared/oauth.py`: khóa Ed25519 tự sinh lần đầu tại `OAUTH_KEY_PATH` (mặc định
  `data/keys/mcp_oauth_ed25519.pem`, không commit); `jwks()`; `issue_mcp_token(resource, tool, subject)`;
  `JwtVerifier` (tải JWKS từ `{issuer}/.well-known/jwks.json`, lưu đệm, tải lại khi gặp `kid` lạ);
  `resource_aliases(url)` (`127.0.0.1` ≡ `localhost`).
- assistant_api: `GET /.well-known/jwks.json`, `GET /.well-known/oauth-authorization-server`
  (issuer, jwks_uri, grant_types_supported, scopes_supported).
- MCP server (`common.build_app(mcp, port)`): đường `/mcp` cần JWT hợp lệ (`MCP_AUTH_MODE=oauth`,
  mặc định) hoặc token nội bộ (`token`, chế độ cũ để so sánh/khẩn cấp); `/internal/*` giữ token nội bộ.
  `tool_errors` (bọc mọi công cụ) kiểm `scope` có `mcp:tool:<tên>` và `ma_sv == sub` khi có token.
- `McpClient`: mỗi lần gọi (vốn đã mở kết nối mới) cấp token riêng: `aud` = URL server,
  `scope` theo công cụ, `sub` = `args["ma_sv"]` (đã tiêm từ JWT đăng nhập) hoặc `assistant_api`.
