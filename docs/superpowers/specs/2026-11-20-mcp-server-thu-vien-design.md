# Thiết kế: thêm MCP server lúc đang chạy + server Thư viện (ý 1)

## Mục đích

Tên đề tài bắt đầu bằng "Nghiên cứu giao thức MCP". Hội đồng sẽ hỏi: dùng MCP thì được gì so với gọi API trực tiếp?

Câu trả lời mạnh nhất là demo trực tiếp:
1. Quản trị viên khai báo một **dịch vụ mới (Thư viện)** trên giao diện.
2. Hệ thống tự phát hiện công cụ của dịch vụ đó.
3. Quản trị viên **duyệt** rồi bật.
4. Sinh viên hỏi và dùng được ngay.

Không sửa dòng code nào của trợ lý, không khởi động lại.

Kèm theo là một điểm an toàn cho khóa luận. Mô tả công cụ của server lạ đi thẳng vào prompt của LLM, nên có thể bị cài lệnh (*tool poisoning*). Lớp chặn là: công cụ mới **mặc định tắt**, quản trị viên đọc mô tả rồi mới bật.

## Đã chốt với người dùng

- Làm ý 1 trong tuần 1. Ý 3 (tư vấn kế hoạch học kỳ) làm tuần 2. Ý 5 (thực nghiệm so sánh) làm tuần 3. Thời gian còn lại khoảng 3 tuần.
- Dịch vụ minh họa là **Thư viện**, gồm 3 công cụ: xem sách đang mượn, tìm sách, gia hạn sách (thao tác ghi, cần xác nhận).
- Dữ liệu đặt theo **phương án A**: bảng mới trong `tlhv_qlsv` và endpoint mới trong `qlsv_api`. Server `thu_vien` gọi qua `X-Internal-Token`, giống 3 server nghiệp vụ hiện có.

## Các phương án đã cân nhắc (vị trí dữ liệu)

| Phương án | Đánh đổi | Kết quả |
|---|---|---|
| A. Bảng trong `tlhv_qlsv` + endpoint `qlsv_api` | Dùng lại reset, test rollback, harness; câu chuyện "bên thứ ba" kém tự nhiên hơn chút | **Chọn** |
| B. Server tự giữ dữ liệu JSON trong bộ nhớ | Chân thực "bên thứ ba"; mất dữ liệu khi khởi động lại, không rollback, phải tự viết reset/test | Loại |
| C. CSDL riêng `tlhv_thu_vien` | Chân thực nhất; tốn script tạo CSDL, cấu hình, reset | Loại (không đáng với 3 tuần) |

## Hiện trạng (đã có, không phải làm)

- Bảng `mcp_server` (tên, mô tả, `dia_chi`, `bat`). `ToolRegistry.sync` đọc bảng này và kết nối từng server. `ensure_fresh` tự đồng bộ lại sau mỗi 30 giây khi có server lỗi. API `POST /api/admin/mcp-servers/refresh` đã có.
- Công cụ lạ được tự thêm vào `cong_cu` với `muc_rui_ro='ghi'`, `can_xac_nhan=1`, `bat=0`.
- `PATCH /api/admin/tools/{id}` không cho bỏ xác nhận ở công cụ `ghi`/`nhay_cam`.
- Tiêm `ma_sv` áp dụng cho mọi công cụ có khai báo tham số `ma_sv`, kể cả công cụ của server mới.

## Phần phải làm

### 1. Dữ liệu thư viện (`database/`, `qlsv_api`)

- Bảng `sach`: `ma_sach` (khóa, vd `TV001`), `ten_sach`, `tac_gia`, `nam_xb`, `tong_so_ban`, `so_ban_con`, `so_luot_dat_truoc`.
- Bảng `muon_sach`:
  - cột: `id`, `sinh_vien_id` (FK `sinh_vien`), `ma_sach` (FK), `ngay_muon`, `han_tra`, `so_lan_gia_han` (mặc định 0), `trang_thai` (`dang_muon` | `da_tra`, NVARCHAR + CHECK);
  - đặt `implicit_returning: False` nếu có trigger.
- Script SQL nối tiếp đánh số hiện có. Seed nằm cùng `03_qlsv_seed.sql` hoặc một file mới chạy trong `reset_demo.ps1`. Người viết chọn, miễn `reset_demo.ps1` đưa được về trạng thái sạch.
- Seed (ngày demo 20/11/2026):
  - SV22001 mượn 2 cuốn. Cuốn 1 còn hạn, chưa gia hạn lần nào, **gia hạn được**. Cuốn 2 có người đặt trước, **không gia hạn được**.
  - SV22002 có 1 cuốn **quá hạn**.
  - SV21001 có 1 cuốn đã gia hạn 2 lần.
  - Khoảng 10 đầu sách công nghệ phần mềm. Nội dung tự đặt, không lấy dữ liệu thật của thư viện nào.
- Endpoint `/internal/...` (đặt tên theo kiểu `qlsv_api` hiện có):
  - danh sách sách đang mượn của một sinh viên;
  - tìm sách theo từ khóa (tên/tác giả), trả kèm số bản còn;
  - gia hạn một lượt mượn của chính sinh viên đó.
- Quy tắc gia hạn, kiểm theo thứ tự, mỗi lỗi một mã:
  1. Lượt mượn tồn tại và **thuộc sinh viên** (không thuộc thì trả như không tồn tại, giống đơn từ): `KHONG_TIM_THAY_LUOT_MUON`.
  2. Chưa trả: `DA_TRA_SACH`.
  3. Chưa quá hạn: `SACH_QUA_HAN`.
  4. Chưa gia hạn đủ 2 lần: `HET_LUOT_GIA_HAN`.
  5. Không có người đặt trước: `CO_NGUOI_DAT_TRUOC`.
  6. Đạt cả 5 điều kiện: `han_tra += 14 ngày`, `so_lan_gia_han += 1`.
- Khóa hàng bằng `lock_for_update()`, không dùng `with_for_update()`.
- Ngày "hôm nay" lấy theo cơ chế `DEMO_NOW` sẵn có.

### 2. MCP server `thu_vien` (`src/mcp_servers/thu_vien.py`, cổng **9105**)

- Theo khuôn `tai_chinh.py`: `MCPServer`, `@tool_errors`, `MaSv` (`Annotated`, mô tả `[INJECTED]`).
- Ba công cụ, mỗi công cụ **khai báo `title` tiếng Việt** và annotation MCP (`readOnlyHint`):
  - `get_borrowed_books(ma_sv)`, title "Xem sách đang mượn": danh sách, hạn trả, số lần đã gia hạn, có gia hạn được không và vì sao.
  - `search_books(ma_sv, tu_khoa)`, title "Tìm sách thư viện": nhận `ma_sv` để thống nhất tiêm ngữ cảnh và ghi nhật ký; người viết có thể bỏ nếu không cần.
  - `renew_book(ma_sv, ma_muon)`, title "Gia hạn sách", `readOnlyHint=False`: trả kết quả hoặc mã lỗi theo quy tắc trên.
- Thêm `mcp_thu_vien_port: int = 9105` vào `shared/config.py`, thêm vào `.env.example` và `run_all.ps1`.
- **Không** thêm vào seed `04_assistant_seed.sql`, vì server này được thêm *trên giao diện* lúc demo.
- `90_reset_demo_assistant.sql` xóa server `thu_vien` và công cụ của nó, để demo lại được từ đầu.
  - Lưu ý khóa ngoại: `luot_goi_cong_cu.mcp_server` là chuỗi, không phải FK, nên nhật ký cũ không chặn việc xóa.
  - Reset vốn đã xóa nhật ký.

### 3. Trợ lý: dùng `title` của MCP thay cho chuỗi viết riêng (sửa chung, một lần)

- `ToolSpec` lấy thêm `title` (và `annotations`) từ `list_tools`.
- `prompts.tool_label`: không có trong `TOOL_LABELS` thì dùng "Đang dùng: {title}". `paused_label` làm tương tự.
- `actions.describe`, nhánh mặc định: "{title}" kèm tham số rút gọn, **bỏ `ma_sv`** khỏi phần hiển thị. Ví dụ: "Gia hạn sách (ma_muon: 12)".
  - Mô tả thẻ vẫn dựng từ dữ liệu, không dùng lời của LLM (giữ nguyên nguyên tắc cũ).
  - Người viết có thể tra thêm tên sách để thẻ dễ đọc hơn, nhưng **không** được thêm nhánh riêng cho `renew_book`. Mục tiêu là chứng minh không phải sửa trợ lý theo từng công cụ.
- Giữ nguyên các nhánh riêng hiện có (đăng ký, giấy xác nhận…).

### 4. Quản trị: thêm và duyệt server (API + trang MCP & quyền)

- `POST /api/admin/mcp-servers/check`:
  - Body: `{dia_chi}`.
  - Kết nối thử bằng Bearer `INTERNAL_API_TOKEN`, trả danh sách công cụ: tên, title, mô tả, schema đã ẩn tham số tiêm, gợi ý `readOnlyHint`.
  - **Không ghi CSDL.** Dùng cho nút "Kiểm tra kết nối".
- `POST /api/admin/mcp-servers`:
  - Body: `{ten, mo_ta, dia_chi}`.
  - Kiểm hợp lệ, lưu, gọi `registry.sync`, trả về server cùng công cụ (đều đang **tắt**).
- `PATCH /api/admin/mcp-servers/{id}`: sửa `mo_ta`, `dia_chi`, `bat`. **Không có xóa** (giống trang Sinh viên: chỉ tắt). Xóa hẳn chỉ làm bằng `reset_demo`.
- Ràng buộc, lỗi trả dạng `{"detail","code"}`:
  - `ten`: chữ thường không dấu, số, gạch dưới, tối đa 50 ký tự, không trùng.
  - `dia_chi`: chỉ chấp nhận `http://127.0.0.1:<cổng>/...` hoặc `http://localhost:<cổng>/...`. Lý do:
    - đúng quy tắc 4 (server chỉ nghe trên máy);
    - chặn việc dùng trợ lý để gọi ra địa chỉ tùy ý (SSRF);
    - không gửi `INTERNAL_API_TOKEN` ra ngoài máy.
  - Không kết nối được: vẫn cho lưu và báo trạng thái lỗi kết nối (giống server đang tắt), hoặc từ chối. **Người viết chọn: từ chối với mã `MCP_KHONG_KET_NOI_DUOC`**, vì demo cần thấy công cụ ngay.
- Giao diện `/admin/mcp`:
  - Nút **"Thêm MCP server"** mở hộp thoại: tên, mô tả, địa chỉ, nút "Kiểm tra kết nối" xem trước công cụ, rồi "Lưu".
  - Công cụ chưa từng được bật có nhãn **"Mới — cần duyệt"**.
  - Mỗi công cụ mở xem được **mô tả đầy đủ và tham số** (đây là chỗ quản trị viên "duyệt" chống tool poisoning).
  - Có gợi ý "Server tự khai báo: chỉ đọc" lấy từ `readOnlyHint`, kèm ghi chú đây là thông tin do server tự nói, không tin tuyệt đối. Không tự đổi mức rủi ro theo gợi ý này.
- Nhật ký và thống kê hiện sẵn tên server `thu_vien` (cột chuỗi), không phải làm gì thêm.

### 4b. Duyệt mô tả công cụ và phát hiện mô tả bị đổi sau khi duyệt

*(Claude đề xuất, người dùng có thể bỏ.)* Mô tả công cụ được đọc **trực tiếp từ server mỗi lần đồng bộ**. Một server đã được duyệt vẫn có thể lén đổi mô tả sau đó để cài lệnh (gọi là *rug pull*).

- Thêm cột `cong_cu.ban_duyet NVARCHAR(64) NULL`: mã băm SHA-256 của (mô tả + input schema) tại lúc quản trị viên bật công cụ. Có script nâng cấp cho CSDL đang chạy, theo kiểu `05_nang_cap_tool_call_id.sql`.
- Khi `sync`:
  - `ban_duyet` NULL và công cụ đang bật (công cụ cũ có sẵn từ seed): ghi mã băm hiện tại, tức là tin ở lần đầu.
  - `ban_duyet` khác mã băm hiện tại: **tự tắt công cụ** (`bat=0`), ghi log cảnh báo, giao diện hiện nhãn **"Mô tả đã thay đổi — cần duyệt lại"**.
- Khi quản trị viên bật công cụ (`PATCH bat=true`): ghi `ban_duyet` bằng mã băm hiện tại.
- Nhãn trên giao diện:
  - `ban_duyet` NULL và đang tắt: **"Mới — cần duyệt"**.
  - Mã băm lệch: **"Mô tả đã thay đổi — cần duyệt lại"**.
- Test: đổi mô tả của server giả rồi `sync` thì công cụ bị tắt; bật lại thì cập nhật mã băm.

### 4c. Trùng tên công cụ và đổi địa chỉ

- `sync` hiện **giữ công cụ của server có id nhỏ hơn** khi trùng tên, nên server mới không thể giả mạo công cụ cũ (ví dụ một `search_regulations` giả). Giữ nguyên cơ chế này, và cho quản trị viên thấy:
  - `check` và trang MCP đánh dấu công cụ trùng tên là "Trùng tên với công cụ của server X — bị bỏ qua".
- `PATCH` đổi `dia_chi` thì phải cập nhật lại target của `McpClient`. Hiện `sync` chỉ gọi `set_target` khi server chưa có trong client.

### 5. Test, tài liệu

- Test, theo mẫu hiện có (rollback CSDL, LLM giả, MCP trong tiến trình):
  - **qlsv:** đủ 6 nhánh gia hạn; sinh viên không gia hạn được sách của người khác.
  - **MCP:** 3 công cụ; `ma_sv` bị ẩn khỏi schema gửi LLM.
  - **Duyệt:** đổi mô tả thì công cụ bị tắt (4b); công cụ trùng tên bị bỏ qua (4c); đổi địa chỉ thì kết nối tới địa chỉ mới (4c).
  - **assistant:**
    - thêm server qua API thì công cụ xuất hiện ở trạng thái tắt;
    - chưa bật thì không đưa cho LLM;
    - bật rồi thì `renew_book` tạo thẻ, mô tả lấy từ `title` và không chứa `ma_sv`;
    - địa chỉ ngoài máy bị từ chối;
    - tên trùng bị từ chối;
    - `check` không ghi CSDL.
  - Thêm 1–2 dòng `demo_check.py` cho luồng thư viện, gồm cả bước thêm server.
- Tài liệu:
  - `docs/01`: thêm AD-11 "Thêm và duyệt MCP server" và SV-11 "Thư viện qua trợ lý".
  - `docs/02`, `docs/03` (bảng mới), `docs/04` (API mới), `docs/05` (server `thu_vien`), `docs/08` (hộp thoại, nhãn "Mới — cần duyệt").
  - `docs/10`: rủi ro tool poisoning, rug pull, trùng tên công cụ, cùng các lớp chặn.
  - `docs/kich-ban-demo.md`: cập nhật ở tuần 3, khi biết thời lượng của cả ý 3.

## Không làm

- Không cho đăng ký server ngoài máy (`https://...` công cộng), không quản lý token riêng cho từng server. Tất cả dùng chung `INTERNAL_API_TOKEN`; giới hạn này ghi trong `docs/10`.
- Không làm mượn/trả sách, đặt trước, phạt quá hạn. Chỉ có xem, tìm, gia hạn.
- Không tự suy mức rủi ro từ annotation của server.
- Chưa thêm kịch bản thư viện vào TN3/TN4. Quyết ở tuần 3 (ý 5).

## Để lại cho người viết

Tên endpoint `qlsv_api`, tên file SQL, bố cục hộp thoại, câu chữ thông báo lỗi tiếng Việt. Tất cả theo quy ước sẵn có trong repo.
