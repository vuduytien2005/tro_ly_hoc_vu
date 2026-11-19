# 05. Thiết kế MCP servers

## Nguyên tắc chung
- Python SDK chính thức `mcp` **2.x**, lớp `MCPServer` (`from mcp.server.mcpserver import MCPServer`; bản 1.x gọi là `FastMCP`). Transport **streamable HTTP**, endpoint `/mcp`, lắng nghe `127.0.0.1`.
  - Chế độ `stateless_http=True` + `json_response=True`: mỗi lệnh gọi độc lập, không giữ phiên, trả JSON (tool không cần streaming).
  - SDK tự bật **chống DNS rebinding** khi host là `127.0.0.1` (Host lạ → 421).
  (Claude: kiểm tra cú pháp hiện hành của SDK trước khi viết — API của SDK có thể đã thay đổi.)
- Mỗi server một file trong `backend/src/mcp_servers/`, dùng chung `common.py`:
  - `QlsvClient`: httpx.AsyncClient tới `QLSV_API_URL` với header `X-Internal-Token`.
  - `BearerAuthMiddleware` (ASGI thuần) kiểm `Authorization: Bearer {INTERNAL_API_TOKEN}` bằng `hmac.compare_digest`, bọc ngoài ứng dụng của SDK; sai/thiếu → 401 `{"detail","code"}`. (Không dùng `token_verifier`/`AuthSettings` của SDK vì đó là luồng OAuth đầy đủ, thừa cho token nội bộ.)
  - Hàm `to_tool_error(code, message)` + decorator `@tool_errors`: lỗi nghiệp vụ từ qlsv_api, mất kết nối (`QLSV_KHONG_KET_NOI`), quá giờ (`QLSV_QUA_THOI_GIAN`), lỗi bất ngờ (`LOI_HE_THONG`, không lộ chi tiết) đều thành dict lỗi có cấu trúc.
  - `path_segment()`: mã hóa tham số do LLM sinh khi ghép vào URL (chặn `../`).
- **Tham số đầu tiên** của tool dữ liệu cá nhân là `ma_sv: MaSv` với `MaSv = Annotated[str, Field(description="Mã sinh viên. [INJECTED] Do hệ thống điền, không yêu cầu người dùng cung cấp.")]`.
  **Ghi chú `[INJECTED]` đặt ở mô tả tham số, KHÔNG đặt trong docstring**: SDK đưa nguyên docstring vào `description` của tool, nên nếu viết trong docstring thì dù assistant_api xóa `ma_sv` khỏi schema, LLM vẫn đọc thấy tham số này. Đặt trong schema thì xóa thuộc tính là mất hết dấu vết (có test kiểm tra).
- **Docstring viết tiếng Việt, rõ ràng, có ví dụ khi nào dùng** — vì LLM đọc docstring để chọn tool. Đây là một nội dung thực nghiệm (mô tả tool tốt/xấu ảnh hưởng độ chính xác chọn tool).
- Kết quả trả về: dict JSON gọn, khóa tiếng Việt không dấu, có `thong_bao` ngắn tóm tắt cho LLM. Không trả dữ liệu thừa (giảm token).
- Lỗi nghiệp vụ trả về `{"thanh_cong": false, "ma_loi": "...", "thong_bao": "..."}` (không ném exception) để LLM giải thích được cho sinh viên.

## 1. Server `dao_tao` (:9101)
| Tool | Tham số (ngoài ma_sv) | Trả về (rút gọn) | Rủi ro / xác nhận |
|---|---|---|---|
| `get_student_profile` | – | ho_ten, lop, nganh, khoa, trang_thai | đọc |
| `get_transcript` | `ma_hoc_ky: str \| None` | danh sách {ma_hp, ten_hp, tin_chi, hoc_ky, diem_tong_ket, diem_chu, lan_hoc}, gpa_tich_luy, tin_chi_tich_luy | đọc |
| `get_exam_schedule` | `ma_hoc_ky: str \| None` | {ma_lop, ten_hp, ngay_thi, gio, phong, hinh_thuc} | đọc |
| `get_current_schedule` | `ma_hoc_ky: str \| None` | {ma_lop, ten_hp, thu, tiet, phong, giang_vien} | đọc |
| `get_graduation_progress` | – | xem API graduation-progress | đọc |
| `search_course_sections` | `tu_khoa: str`, `ma_hoc_ky: str \| None` | {ma_lop, ma_hp, ten_hp, tin_chi, giang_vien, lich, con_trong} (tối đa 10) | đọc |
| `register_course` | `ma_lop: str`, `chi_kiem_tra: bool = False` [SYSTEM, ẩn khỏi LLM] | {thanh_cong, ma_lop, ten_hp, lich} hoặc lỗi; `chi_kiem_tra=true` → gọi `/registrations/check`, không ghi | **ghi, xác nhận** |
| `cancel_course_registration` | `ma_lop: str` | {thanh_cong} hoặc lỗi | **ghi, xác nhận** |

Ví dụ docstring:
```python
@mcp.tool()
@tool_errors
async def register_course(
    ma_sv: MaSv,
    ma_lop: Annotated[str, Field(description='Mã lớp học phần, ví dụ "IT004.02".')],
) -> dict[str, Any]:
    """Đăng ký một lớp học phần cho sinh viên trong học kỳ đang mở đăng ký.

    Dùng khi sinh viên muốn đăng ký / học lại / học thêm một môn và đã xác định được mã lớp.
    Nếu chưa biết mã lớp, gọi search_course_sections trước.
    Thao tác này cần sinh viên xác nhận trên giao diện.
    """
```

## 2. Server `ctsv` (:9102)
| Tool | Tham số | Trả về | Rủi ro / xác nhận |
|---|---|---|---|
| `request_student_certificate` | `muc_dich: str`, `so_ban: int = 1` (1–5) | {ma_don, trang_thai, du_kien} | **ghi, xác nhận** |
| `submit_deferral_request` | `ly_do: str`, `so_hoc_ky: int = 1` (1–2), `tu_hoc_ky: str` | {ma_don} hoặc lỗi (NO_HOC_PHI...) | **nhạy cảm, xác nhận** |
| `submit_regrade_request` | `ma_hp: str`, `ly_do: str` | {ma_don} hoặc lỗi | **ghi, xác nhận** |
| `list_my_requests` | `trang_thai: str \| None` | [{ma_don, loai_don, trang_thai, created_at}] | đọc |
| `get_request_status` | `ma_don: str` | chi tiết đơn | đọc |

- Tool ghi (cả `dao_tao`) **không tự kiểm tra xác nhận**: việc chặn thuộc assistant_api (bảng `cong_cu.can_xac_nhan`). MCP server chỉ thực thi khi được gọi, nên có thể dùng lại với ứng dụng MCP khác — khi đó ứng dụng đó phải tự xin xác nhận người dùng.
- Đơn do trợ lý tạo gửi `tao_boi = "tro_ly_ai"` sang qlsv_api (phân biệt với đơn sinh viên tự nộp).
- Lỗi nghiệp vụ hay gặp (từ qlsv_api, giữ nguyên mã): `TRUNG_LICH`, `LOP_DA_DAY`, `VUOT_TIN_CHI_TOI_DA`, `CHUA_DAT_TIEN_QUYET`, `DA_DANG_KY_HOC_PHAN`, `NGOAI_THOI_GIAN_DANG_KY`, `CHUA_DANG_KY_LOP`, `NO_HOC_PHI`, `SV_KHONG_DANG_HOC`, `KHONG_CO_DIEM_HOC_KY_GAN_NHAT`.

## 3. Server `tai_chinh` (:9103)
| Tool | Tham số | Trả về | Rủi ro |
|---|---|---|---|
| `get_tuition_status` | `ma_hoc_ky: str \| None` | {phai_nop, da_nop, con_no, han_nop, trang_thai} | đọc |

## 4. Server `quy_che` (:9104) — nhánh RAG
| Tool | Tham số | Trả về | Rủi ro |
|---|---|---|---|
| `search_regulations` | `ma_khoa: str` [INJECTED], `cau_hoi: str`, `top_k: int = 5` (≤ 8) | `{"doan": [{"so", "doan_id", "van_ban_id", "van_ban", "phien_ban", "dieu", "khoan", "trang", "noi_dung"}], "ghi_chu": "..."}` — `noi_dung` bọc trong `<tai_lieu>...</tai_lieu>` | đọc |
| `get_article` | `van_ban_id: int`, `dieu: str` | toàn văn các đoạn thuộc Điều đó | đọc |

- `search_regulations` không cần `ma_sv`, chỉ cần `ma_khoa` để lọc phiên bản.
- Thẻ `<tai_lieu ...>` / `</tai_lieu>` có sẵn trong văn bản bị vô hiệu hóa (đổi `<` thành `[`) để tài liệu không "thoát" khỏi thẻ.
- Truy xuất (embedding, CPU nặng) chạy trong thread riêng (`anyio.to_thread`) để không chặn server.
- Lỗi: `MA_KHOA_KHONG_HOP_LE`, `VAN_BAN_KHONG_TON_TAI`, `DIEU_KHONG_TON_TAI`, `DIEU_KHONG_HOP_LE`.
- `assistant_api` dùng trường `so`, `van_ban`, `dieu`, `trang` để dựng sự kiện `citations`.

## 5. Kiểm thử MCP server
- Unit test gọi trực tiếp hàm tool (qlsv_api thay bằng `respx` mock).
- Kiểm thử thủ công: `npx @modelcontextprotocol/inspector` → kết nối `http://127.0.0.1:9101/mcp` kèm header Authorization.
- Test bảo mật: gọi MCP server không có / sai token → bị từ chối.

## 6. Mở rộng (hướng phát triển, ghi vào khóa luận)
- Kết nối chính các MCP server này với ứng dụng MCP khác (vd Claude Desktop) để minh chứng tính chuẩn hóa của giao thức.
- Thêm server `thu_vien` (mượn/gia hạn sách) mà không sửa assistant_api.
