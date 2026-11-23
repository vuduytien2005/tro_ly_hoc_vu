# Khai thác thêm giao thức MCP: Resources và Elicitation (23/11/2026)

## Vì sao
Đề tài là "nghiên cứu giao thức MCP", nhưng hệ thống mới dùng một primitive (**tools** — do mô hình
điều khiển). MCP còn **resources** (do ỨNG DỤNG điều khiển) và **elicitation** (SERVER hỏi thẳng
người dùng). Thêm hai cái này, mỗi cái vào đúng chỗ nó có ích thật, để Chương 2–3 trình bày được
"ba kiểu điều khiển" và vì sao chọn kiểu nào cho việc nào.

## Mục tiêu / không làm
- Mục tiêu: (1) đọc nguyên văn một Điều quy chế từ trích dẫn mà KHÔNG qua LLM; (2) thu thông tin
  liên hệ cá nhân của đơn bảo lưu bằng biểu mẫu gửi thẳng tới MCP server — dữ liệu này KHÔNG đi qua
  LLM (nhà cung cấp mô hình là bên thứ ba).
- Không làm: sampling (server mượn LLM của client — chưa có nhu cầu), elicitation dạng URL,
  prompts. Không đổi mô tả / schema công cụ đã duyệt (mã băm `ban_duyet` giữ nguyên).
- Phản mục tiêu: TN1–TN4 đổi kết quả; elicitation xảy ra trong vòng lặp Agent không có người
  (không có giao diện để trả lời).

## Phương án đã xét
| Phương án | Đánh đổi | Chọn? |
|---|---|---|
| Elicitation kiểu cũ (≤ 2025-11-25): server gửi `elicitation/create` giữa lúc gọi, giữ kết nối chờ | Cần phiên + SSE; transport đang `stateless_http` + `json_response`; giữ request HTTP mở hàng phút chờ sinh viên gõ | Không |
| **Elicitation nhiều vòng phi trạng thái (MCP 2026-07-28, SDK 2.3)**: tool trả `InputRequiredResult` (`input_requests` + `request_state` có chữ ký), client gọi lại kèm `input_responses` | Hợp transport phi trạng thái; ghép được vào thẻ xác nhận có lưu CSDL; thân tool (ghi dữ liệu) chỉ chạy khi đủ thông tin | **Có** |
| LLM tự hỏi số điện thoại trong chat rồi truyền làm tham số | Đơn giản nhưng SĐT đi qua LLM + lưu lịch sử chat; LLM có thể bịa / sai định dạng | Không |
| Resources: thêm nút gọi tool `get_article` từ web | Tool là thứ của mô hình; gọi tool ngoài vòng Agent lẫn lộn hai vai trò | Không |
| **Resources** `quy-che://van-ban/{id}/dieu/{so}`, web đọc qua assistant_api | Đúng ngữ nghĩa "ứng dụng điều khiển"; không tốn lượt LLM | **Có** |

## Thiết kế

### Resources (quy_che)
- `quy-che://van-ban` (tĩnh): danh sách văn bản đã lập chỉ mục `{id, ten, phien_ban, ngay_hieu_luc}`.
- `quy-che://van-ban/{van_ban_id}/dieu/{so_dieu}` (template): nguyên văn Điều, dạng văn bản thuần
  (hiển thị cho NGƯỜI đọc, không bọc `<tai_lieu>` vì không đưa vào prompt).
- Dùng chung `_get_article` với tool `get_article`.
- OAuth: token đọc tài nguyên có scope `mcp:resources.read`; hàm đọc tài nguyên kiểm scope khi có token.
- assistant_api: `McpClient.read_resource`, `GET /api/documents/{id}/articles/{so}` (sinh viên đã
  đăng nhập; chỉ văn bản `da_lap_chi_muc`). Không ghi `luot_goi_cong_cu` (đây không phải gọi công
  cụ; quy tắc 3 áp cho công cụ).
- Web: nút "Đọc Điều N" trong danh sách nguồn, mở khung nguyên văn ngay dưới nguồn.

### Elicitation (ctsv `submit_deferral_request`)
- Tham số `lien_he: Annotated[LienHe | None, Resolve(ask_contact)]` — tham số do resolver điền
  KHÔNG có trong input schema (đã kiểm chứng) → LLM không thấy, mã băm duyệt không đổi.
- `ask_contact`: client không khai báo năng lực `elicitation.form` → trả `None` (không hỏi; TN1–TN4
  và vòng Agent thường không đổi). Có → `Elicit("…", LienHe)`: `so_dien_thoai` (bắt buộc, `^0\d{9}$`),
  `email_ca_nhan` (tùy chọn).
- Kết quả tool KHÔNG nhắc lại SĐT/email (kết quả đi vào lịch sử cho LLM).
- assistant_api chỉ khai báo năng lực elicitation ở luồng **thẻ xác nhận** (có người, có giao diện):
  1. Bấm Xác nhận → gọi tool → nhận `InputRequiredResult` → thẻ chuyển `cho_bo_sung`, lưu
     `yeu_cau_bo_sung` (thông điệp, schema, `request_state`), gia hạn 10 phút, nhật ký giữ
     `cho_xac_nhan` + lý do "chờ bổ sung (elicitation)"; SSE gửi lại `pending_action` có `bo_sung`.
  2. Web vẽ biểu mẫu từ `requestedSchema` ngay trong thẻ. "Gửi" → `POST /api/actions/{ma}/input
     {du_lieu}`: khóa hàng, kiểm chủ/hạn/trạng thái, kiểm `du_lieu` theo schema (server MCP cũng kiểm
     lại), đổi `da_xac_nhan`, COMMIT rồi gọi lại tool kèm `input_responses` + `request_state`.
  3. "Hủy" dùng endpoint hủy cũ (nhận cả `cho` và `cho_bo_sung`).
  - Nhật ký chỉ ghi TÊN trường đã bổ sung, không ghi giá trị. Tin nhắn người dùng lưu là
    "Đã gửi thông tin bổ sung qua biểu mẫu", không có giá trị.
  - Chỉ hỗ trợ `elicitation/create` dạng form; yêu cầu khác (sampling, roots, url) → lỗi
    `KHONG_HO_TRO_YEU_CAU_BO_SUNG`, nhật ký `loi`.
- CSDL: `database/08_nang_cap_elicitation.sql` — cột `yeu_cau_bo_sung NVARCHAR(MAX) NULL CHECK
  ISJSON`, thêm `cho_bo_sung` vào CHECK trạng thái.

## Để người làm tự quyết
Bố cục biểu mẫu, câu chữ thông điệp; số vòng bổ sung tối đa (đặt 3).
