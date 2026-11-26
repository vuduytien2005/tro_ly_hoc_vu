# MCP server Thư viện + thêm/duyệt server lúc chạy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quản trị viên thêm MCP server `thu_vien` trên giao diện. Công cụ của server mới mặc định tắt. Quản trị viên duyệt mô tả rồi bật. Sinh viên dùng được ngay mà không phải sửa code trợ lý theo từng công cụ. Mô tả bị đổi sau khi duyệt thì công cụ tự tắt.

**Architecture:**
- Dữ liệu thư viện nằm trong `tlhv_qlsv`, có endpoint `/internal` trong `qlsv_api`.
- `src/mcp_servers/thu_vien.py` gọi các endpoint đó.
- `ToolRegistry` được mở rộng với các phần sau:
  - bộ phân giải địa chỉ (để test dùng server trong tiến trình);
  - đổi địa chỉ;
  - ghi nhận trùng tên;
  - mã băm duyệt (`cong_cu.ban_duyet`).
- Admin API có thêm `check`, `POST` và `PATCH` cho server. Trang `/admin/mcp` có hộp thoại thêm server và nhãn duyệt.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (SQL Server), `mcp` 2.x `MCPServer`/`Client`, pytest + respx, React + TanStack Query + vitest.

**Spec:** `docs/superpowers/specs/2026-11-20-mcp-server-thu-vien-design.md`

## Global Constraints

- Tên bảng/cột: tiếng Việt không dấu, snake_case. Literal tiếng Việt trong SQL phải có `N'...'`. ENUM viết bằng `NVARCHAR` + `CHECK`. Bảng có trigger thì đặt `implicit_returning: False`.
- Khóa hàng dùng `lock_for_update()` (`src/shared/locking.py`). **Không** dùng `with_for_update()`.
- Code tiếng Anh. Chuỗi cho người dùng viết tiếng Việt có dấu. Lỗi API có dạng `{"detail": "...", "code": "MA_LOI"}`.
- Tham số `ma_sv` của MCP khai báo bằng `MaSv` (`Annotated`) ở `mcp_servers/common.py`, không ghi trong docstring.
- Ngày "hôm nay" ở qlsv lấy từ dependency `Now` (`routers/deps.py`), tức là theo `DEMO_NOW=2026-11-20T09:00:00+07:00`.
- MCP server chỉ nghe `127.0.0.1`. Địa chỉ server do quản trị viên nhập phải là `http://127.0.0.1:<cổng>/...` hoặc `http://localhost:<cổng>/...`.
- Cổng `thu_vien` là **9105**. Server `thu_vien` **không** có trong `04_assistant_seed.sql`.
- Công cụ mới khi đồng bộ được thêm với `muc_rui_ro='ghi'`, `can_xac_nhan=1`, `bat=0`. Giữ nguyên hành vi này.
- Không có API hay nút xóa MCP server. Chỉ `reset_demo` xóa server `thu_vien`.
- Không thêm nhánh riêng cho `renew_book` trong `actions.describe` hay `prompts.TOOL_LABELS`.
- Chạy test ở `backend/`: `pytest -q`; lint: `ruff check src tests`. Ở `web/`: `npm test`, `npm run build`.

## Review Focus

1. Địa chỉ nhập có khoảng trắng hoặc chữ hoa, ví dụ `" http://LOCALHOST:9105/mcp "`: chấp nhận và lưu bản đã cắt khoảng trắng. Ngược lại, `http://127.0.0.1.evil.com:9105/mcp` và `https://example.com/mcp` bị từ chối. Thuộc Task 5.
2. Trả sách đúng ngày hạn (`han_tra` = hôm nay): **chưa** quá hạn, vẫn gia hạn được. Thuộc Task 1.
3. Server đã thêm rồi bị tắt tiến trình: trang MCP vẫn tải được, server hiện lỗi kết nối, công cụ của nó không đưa cho LLM. Thuộc Task 3.
4. Server không khai báo `title` cho công cụ: thẻ và nhãn quay về cách hiển thị cũ (tên công cụ), không lỗi. Thuộc Task 4.
5. `PATCH` đổi `dia_chi` sang địa chỉ không hợp lệ: 422 với cùng mã lỗi như lúc thêm, CSDL không đổi. Thuộc Task 5.

---

### Task 1: Dữ liệu thư viện trong QLSV (bảng, seed, service, endpoint)

**Files:**
- Modify: `database/01_qlsv_schema.sql`: thêm `DROP TABLE IF EXISTS muon_sach; DROP TABLE IF EXISTS sach;` **trước** các lệnh DROP hiện có, và `CREATE TABLE` ở cuối.
- Modify: `database/03_qlsv_seed.sql`: seed ở cuối file.
- Modify: `backend/src/qlsv_api/models.py`: thêm `Sach`, `MuonSach`.
- Create: `backend/src/qlsv_api/repositories/library.py`
- Create: `backend/src/qlsv_api/services/library_service.py`
- Create: `backend/src/qlsv_api/routers/library.py`, rồi đăng ký trong `main.py` theo cách các router khác đang được đăng ký.
- Modify: `backend/src/qlsv_api/schemas.py`: `BorrowOut`, `BookOut`.
- Test: `backend/tests/qlsv/test_library.py`

**Interfaces:**
- Produces (HTTP, đều có `InternalAuth`):
  - `GET /internal/students/{ma_sv}/borrows`: trả `list[BorrowOut]`, chỉ các lượt `dang_muon`.
  - `GET /internal/books?tu_khoa=...`: trả `list[BookOut]`, tối đa 10, tìm không phân biệt hoa thường theo `ten_sach` hoặc `tac_gia`.
  - `POST /internal/students/{ma_sv}/borrows/{muon_id}/renew`: trả `BorrowOut` sau khi gia hạn; lỗi trả `BusinessError`.
- `BorrowOut`: `muon_id: int, ma_sach, ten_sach, tac_gia, ngay_muon: date, han_tra: date, so_lan_gia_han: int, qua_han: bool, gia_han_duoc: bool, ly_do_khong_gia_han: str | None`.
- `BookOut`: `ma_sach, ten_sach, tac_gia, nam_xb: int, tong_so_ban: int, so_ban_con: int`.
- Hằng số trong `library_service`: `RENEW_DAYS = 14`, `MAX_RENEWALS = 2`.

Bảng:
- `sach(ma_sach NVARCHAR(10) PK, ten_sach NVARCHAR(255), tac_gia NVARCHAR(255), nam_xb INT, tong_so_ban INT, so_ban_con INT, so_luot_dat_truoc INT DEFAULT 0)`
- `muon_sach(id INT IDENTITY PK, sinh_vien_id FK sinh_vien, ma_sach FK sach, ngay_muon DATE, han_tra DATE, so_lan_gia_han INT DEFAULT 0, trang_thai NVARCHAR(20) CHECK IN (N'dang_muon', N'da_tra'))`

Seed: khoảng 10 đầu sách, mã `TV001`–`TV010`. Các lượt mượn sau đây giữ **đúng id** (dùng `SET IDENTITY_INSERT`):

**Bảng 1.** Các lượt mượn trong dữ liệu mẫu

| id | SV | sách | ngày mượn | hạn trả | gia hạn | ý nghĩa |
|---|---|---|---|---|---|---|
| 1 | SV22001 | TV001 | 2026-11-06 | 2026-11-27 | 0 | gia hạn được |
| 2 | SV22001 | TV002 (`so_luot_dat_truoc=1`) | 2026-11-06 | 2026-11-27 | 0 | `CO_NGUOI_DAT_TRUOC` |
| 3 | SV22002 | TV003 | 2026-10-15 | 2026-11-05 | 0 | `SACH_QUA_HAN` |
| 4 | SV21001 | TV004 | 2026-09-20 | 2026-12-01 | 2 | `HET_LUOT_GIA_HAN` |
| 5 | SV22001 | TV005 | 2026-09-01 | 2026-09-22 | 0, `da_tra` | `DA_TRA_SACH` |

- [ ] **Step 1: Viết test lỗi trước** trong `tests/qlsv/test_library.py`, dùng fixture rollback và TestClient như `test_requests.py`, `now` = 2026-11-20:
  - `test_list_borrows_only_active`: SV22001 thấy `[1, 2]`; lượt 2 có `gia_han_duoc is False` và `ly_do_khong_gia_han` chứa "đặt trước".
  - `test_renew_ok`: renew lượt 1 cho `han_tra == date(2026, 12, 11)` và `so_lan_gia_han == 1`. Renew lần nữa vẫn được, thành 2026-12-25. Lần thứ ba trả 409 `HET_LUOT_GIA_HAN`.
  - `test_renew_errors`: tham số hóa `(ma_sv, muon_id, status, code)`:
    - `("SV22002", 1, 404, "KHONG_TIM_THAY_LUOT_MUON")` (lượt của người khác);
    - `("SV22001", 99, 404, "KHONG_TIM_THAY_LUOT_MUON")`;
    - `("SV22001", 5, 409, "DA_TRA_SACH")`;
    - `("SV22002", 3, 409, "SACH_QUA_HAN")`;
    - `("SV21001", 4, 409, "HET_LUOT_GIA_HAN")`;
    - `("SV22001", 2, 409, "CO_NGUOI_DAT_TRUOC")`.
  - `test_renew_on_due_date_is_allowed`: override `Now` thành 2026-11-27 09:00, renew lượt 1 thì thành công (Review Focus 2).
  - `test_search_books`: `tu_khoa="phần mềm"` trả ít nhất một sách; `tu_khoa="zzz"` trả `[]`.
- [ ] **Step 2: Chạy** `pytest tests/qlsv/test_library.py -q`. Mong đợi: FAIL (404 route).
- [ ] **Step 3: Viết code.**
  - Thêm SQL vào `01`/`03` rồi chạy lại `.\scripts\reset_demo.ps1 -ChiQlsv` để CSDL dev có bảng.
  - Thêm model, repository, `library_service.renew(db, ma_sv, muon_id, now) -> BorrowOut`: kiểm theo **đúng thứ tự** trong spec mục 1, khóa lượt mượn bằng `lock_for_update`, không commit.
  - Router bọc lệnh ghi bằng `run_in_transaction` như `routers/requests.py`.
  - `qua_han` = `han_tra < now.date()`.
  - `gia_han_duoc` / `ly_do_khong_gia_han` dùng chung hàm kiểm với `renew`.
- [ ] **Step 4: Chạy** `pytest tests/qlsv -q`. Mong đợi: tất cả PASS, các test qlsv cũ không hỏng.
- [ ] **Step 5: Commit:** `git commit -m "QLSV: dữ liệu thư viện (sach, muon_sach) + API mượn/tìm/gia hạn"`

### Task 2: MCP server `thu_vien`

**Files:**
- Create: `backend/src/mcp_servers/thu_vien.py`
- Modify: `backend/src/shared/config.py` (`mcp_thu_vien_port: int = 9105`), `.env.example` (`MCP_THU_VIEN_PORT=9105`), `backend/scripts/run_all.ps1` (thêm dòng cổng 9105, theo mẫu `tai_chinh`).
- Test: `backend/tests/mcp/test_thu_vien.py`

**Interfaces:**
- Consumes: các endpoint ở Task 1.
- Produces: `thu_vien.mcp: MCPServer` (name `"thu_vien"`). Các công cụ:
  - `get_borrowed_books(ma_sv: MaSv)`, title `"Xem sách đang mượn"`, `readOnlyHint=True`;
  - `search_books(ma_sv: MaSv, tu_khoa: str)`, title `"Tìm sách thư viện"`, `readOnlyHint=True`;
  - `renew_book(ma_sv: MaSv, muon_id: int)`, title `"Gia hạn sách"`, `readOnlyHint=False`.
- Đặt title và annotation bằng tham số của `@mcp.tool(...)` trong SDK `mcp` 2.x. **Kiểm tra API SDK trước khi viết.** Cả ba trả dict có `thong_bao` tiếng Việt, theo mẫu `tai_chinh.py`. Lỗi qlsv được `tool_errors` chuyển thành dict lỗi.

- [ ] **Step 1: Viết test lỗi trước** (dùng `qlsv_mock`, `call_tool`, `list_tools` trong `tests/mcp/conftest.py`):
  - `test_tools_declared`: có đủ 3 tên; `title` đúng như trên; `renew_book` có `annotations.readOnlyHint is False`; `ma_sv` nằm trong schema và có mô tả `[INJECTED]`.
  - `test_renew_book_maps_business_error`: mock POST renew trả 409 `CO_NGUOI_DAT_TRUOC`, kết quả công cụ có `ma_loi == "CO_NGUOI_DAT_TRUOC"`.
  - `test_get_borrowed_books_message`: mock 2 lượt, `thong_bao` nêu đủ 2 tên sách.
- [ ] **Step 2: Chạy** `pytest tests/mcp/test_thu_vien.py -q`. Mong đợi: FAIL (ImportError).
- [ ] **Step 3: Viết code** `thu_vien.py` và phần cấu hình. `main()` gọi `run(mcp, get_settings().mcp_thu_vien_port)`.
- [ ] **Step 4: Chạy** `pytest tests/mcp -q`. Mong đợi: PASS. Kiểm tay: `python -m src.mcp_servers.thu_vien` lên được ở 127.0.0.1:9105.
- [ ] **Step 5: Commit:** `git commit -m "MCP server thu_vien (:9105): xem sách mượn, tìm sách, gia hạn"`

### Task 3: Registry: title/annotation, bộ phân giải địa chỉ, đổi địa chỉ, trùng tên, mã băm duyệt

**Files:**
- Modify: `backend/src/assistant_api/mcp_client/client.py` (`ToolSpec`, `list_tools`)
- Modify: `backend/src/assistant_api/agent/registry.py`
- Modify: `database/02_assistant_schema.sql`: thêm cột `ban_duyet NVARCHAR(64) NULL` vào `cong_cu`.
- Create: `database/06_nang_cap_ban_duyet.sql`: `ALTER TABLE cong_cu ADD ban_duyet ...`, chỉ chạy nếu cột chưa có, theo mẫu `05_nang_cap_tool_call_id.sql`.
- Modify: `backend/src/assistant_api/models.py` (`CongCu.ban_duyet: Mapped[str | None]`)
- Modify: `backend/tests/assistant/conftest.py`: thêm `thu_vien` vào khả năng phân giải của fixture `registry` (xem Interfaces).
- Test: `backend/tests/assistant/test_registry.py`

**Interfaces:**
- `ToolSpec` thêm hai trường có mặc định, để code cũ không gãy: `title: str | None = None`, `read_only_hint: bool | None = None`. `list_tools` điền từ `t.title` và `t.annotations.readOnlyHint` (khi có).
- `McpClient.preview(target: McpTarget) -> list[ToolSpec]`: kết nối một lần tới target chưa đăng ký, cùng token, không đổi `_targets`.
- `ToolRegistry.__init__(self, client: McpClient, resolve: Callable[[str], McpTarget] = lambda url: url)`.
- `sync`:
  - gọi `client.set_target(ten, self.resolve(dia_chi))` khi server **mới** hoặc `dia_chi` **khác** lần trước (lưu `self._addresses: dict[str, str]`);
  - ghi `self.skipped: dict[str, list[tuple[str, str]]]`, tức server → `[(tên công cụ, server giữ tên)]`, cho công cụ bị bỏ vì trùng tên.
- `def spec_hash(spec: ToolSpec) -> str`: SHA-256 hex của `json.dumps({"title": ..., "description": ..., "input_schema": ...}, sort_keys=True, ensure_ascii=False)`. Hàm cấp module.
- Mã băm trong `sync`, với công cụ đã có trong CSDL và có spec:
  - `ban_duyet is None and bat`: gán `ban_duyet = spec_hash`.
  - `ban_duyet is not None and ban_duyet != spec_hash`: gán `bat = False`, `logger.warning`.
- `ToolRegistry.review_state(tool: CongCu) -> Literal["da_duyet", "moi", "thay_doi"]`:
  - `"thay_doi"` nếu có spec và `ban_duyet` khác mã băm hiện tại;
  - `"moi"` nếu `ban_duyet is None and not bat`;
  - ngược lại `"da_duyet"`.
- `ToolRegistry.approve(tool: CongCu) -> None`: gán `ban_duyet = spec_hash(spec)` nếu server đang có spec; không có thì giữ nguyên.
- Fixture `registry`: `ToolRegistry(mcp_client, resolve=lambda url: thu_vien.mcp if url.rstrip("/").endswith(":9105/mcp") else url)`.
- Test thêm server bằng cách chèn `McpServer(ten="thu_vien", dia_chi="http://127.0.0.1:9105/mcp")` rồi gọi `sync`.

- [ ] **Step 1: Viết test lỗi trước** trong `test_registry.py`:
  - `test_new_server_tools_added_disabled`: chèn server `thu_vien`, `sync`. Có 3 `CongCu` với `bat=False`, `muc_rui_ro="ghi"`, `can_xac_nhan=True`, `ban_duyet is None`, `review_state == "moi"`. `tools_for_llm` không chứa tên nào của thư viện.
  - `test_title_and_hint_loaded`: `registry._specs["renew_book"].title == "Gia hạn sách"`, `read_only_hint is False`.
  - `test_approve_then_description_change_disables`: bật `renew_book` và `approve`. Monkeypatch spec trả về (hoặc đổi docstring qua server giả) để mô tả khác, rồi `sync`. Kết quả: `bat is False`, `review_state == "thay_doi"`. `approve` lại thì `review_state == "da_duyet"`.
  - `test_existing_enabled_tools_trusted_on_first_use`: công cụ seed đang bật, `ban_duyet` NULL, sau `sync` thì `ban_duyet` khác NULL và vẫn `bat=True`.
  - `test_duplicate_tool_name_skipped`: server giả có công cụ `search_regulations`. Sau `sync`, `skipped[<server giả>] == [("search_regulations", "quy_che")]` và spec của `search_regulations` vẫn thuộc `quy_che`.
  - `test_address_change_retargets`: đổi `dia_chi` của `thu_vien`, rồi `sync`, thì `resolve` được gọi với địa chỉ mới.
  - `test_offline_server_not_exposed` (Review Focus 3): resolve tới URL không có tiến trình, `sync`. `server_status["thu_vien"]` là thông báo lỗi, công cụ không có trong `tools_for_llm`, và không ném lỗi.
- [ ] **Step 2: Chạy** `pytest tests/assistant/test_registry.py -q`. Mong đợi: FAIL.
- [ ] **Step 3: Viết code**, rồi chạy `database/06_nang_cap_ban_duyet.sql` trên CSDL dev.
- [ ] **Step 4: Chạy** `pytest tests/assistant -q`. Mong đợi: PASS, toàn bộ test cũ không hỏng.
- [ ] **Step 5: Commit:** `git commit -m "Registry: title MCP, đổi địa chỉ, trùng tên, mã băm duyệt (ban_duyet) tự tắt khi mô tả đổi"`

### Task 4: Trợ lý hiển thị theo `title` (thẻ xác nhận, nhãn trạng thái, chức năng tạm dừng)

**Files:**
- Modify: `backend/src/assistant_api/agent/prompts.py` (`tool_label`, `paused_label`)
- Modify: `backend/src/assistant_api/agent/actions.py` (`describe`)
- Modify: `backend/src/assistant_api/agent/loop.py`: truyền title vào 3 chỗ gọi `tool_label` / `describe` (dòng ~305, ~404, ~544); `system_prompt` truyền title cho `paused_label`.
- Test: `backend/tests/assistant/test_agent_loop.py`, `backend/tests/assistant/test_actions.py`

**Interfaces:**
- `tool_label(name: str, title: str | None = None) -> str`: tên có trong `TOOL_LABELS` thì giữ nguyên; có `title` thì trả `f"Đang dùng: {title}"`; còn lại giữ chuỗi cũ.
- `paused_label(name: str, title: str | None = None) -> str`: tương tự.
- `describe(tool: str, args: dict[str, Any], lookup: Lookup, title: str | None = None) -> str`: ở nhánh mặc định, có `title` thì trả `title` kèm tham số rút gọn (bỏ `ma_sv`, `ma_khoa`, `chi_kiem_tra`), ví dụ `"Gia hạn sách (muon_id: 1)"`. Không có title thì giữ chuỗi cũ.

- [ ] **Step 1: Viết test lỗi trước:**
  - `test_renew_book_creates_card_with_title` (test_agent_loop):
    - bật `renew_book` sau `sync` có `thu_vien`;
    - `script` cho LLM giả gọi `renew_book({"muon_id": 1, "ma_sv": "SV99999"})`.
    - Mong đợi:
      - có sự kiện `pending_action` với `mo_ta == "Gia hạn sách (muon_id: 1)"`, không chứa `"SV"`;
      - nhật ký có `tham_so["ma_sv"] == student.ma_sv`;
      - sự kiện `tool_start` có `nhan == "Đang dùng: Gia hạn sách"`.
  - `test_describe_without_title_unchanged` (test_actions, Review Focus 4): `describe("x_tool", {"a": 1}, lookup)` trả đúng chuỗi cũ `"Thực hiện thao tác x_tool (a: 1)"`. Đối chiếu định dạng thật trong code hiện tại rồi ghi giá trị vào test.
  - `test_paused_label_uses_title`: `paused_label("renew_book", "Gia hạn sách")` chứa `"Gia hạn sách"`.
- [ ] **Step 2: Chạy** các test trên. Mong đợi: FAIL.
- [ ] **Step 3: Viết code.** Title lấy từ `policy.spec.title`, hoặc `registry._specs.get(name)` qua một accessor công khai `registry.title(name) -> str | None`.
- [ ] **Step 4: Chạy** `pytest tests/assistant -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Trợ lý dùng title MCP cho thẻ xác nhận và nhãn trạng thái (không cần sửa theo từng công cụ)"`

### Task 5: Admin API: kiểm tra, thêm, sửa server; nhãn duyệt; bật công cụ thì ghi mã băm; reset

**Files:**
- Modify: `backend/src/assistant_api/routers/admin.py`
- Modify: `backend/src/assistant_api/schemas_admin.py`
- Modify: `database/90_reset_demo_assistant.sql`: xóa `cong_cu` rồi `mcp_server` có `ten = N'thu_vien'`, đặt **trước** đoạn bật lại server/công cụ theo seed.
- Test: `backend/tests/assistant/test_admin.py`

**Interfaces:**
- Hàm thuần `normalize_mcp_address(raw: str) -> str` (đặt trong `routers/admin.py` hoặc module nhỏ `assistant_api/mcp_address.py`):
  - cắt khoảng trắng;
  - scheme phải là `http`;
  - `hostname` (chữ thường) thuộc `{"127.0.0.1", "localhost"}`;
  - phải có cổng.
  - Sai thì ném `ApiError("DIA_CHI_MCP_KHONG_HOP_LE", ..., 422)`.
- `POST /api/admin/mcp-servers/check`:
  - Body `McpCheckIn{dia_chi}`.
  - Trả `McpCheckOut{cong_cu: list[ToolPreview]}`, với `ToolPreview{ten, title, mo_ta, tham_so: dict, chi_doc_theo_server: bool | None, trung_ten_voi: str | None}`. `tham_so` là schema đã qua `strip_injected`.
  - Không kết nối được thì 422 `MCP_KHONG_KET_NOI_DUOC`.
  - Không ghi CSDL.
- `POST /api/admin/mcp-servers`:
  - Body `McpServerCreate{ten, mo_ta, dia_chi}`.
  - `ten` khớp `^[a-z][a-z0-9_]{1,49}$`, sai thì 422 `TEN_MCP_KHONG_HOP_LE`; trùng thì 409 `TEN_MCP_DA_TON_TAI`.
  - Kiểm kết nối như `check` trước khi lưu.
  - Lưu rồi `registry.sync`, trả `McpServerOut` (201).
- `PATCH /api/admin/mcp-servers/{id}`:
  - Body `McpServerPatch{mo_ta?, dia_chi?, bat?}`.
  - `dia_chi` mới qua `normalize_mcp_address` và kiểm kết nối như khi thêm. Sai thì CSDL không đổi (Review Focus 5).
  - Sau đó `sync`.
  - Không tồn tại thì 404 `MCP_KHONG_TON_TAI`.
- `ToolOut` thêm: `title: str | None`, `mo_ta_day_du: str | None` (từ spec), `tham_so: dict | None`, `chi_doc_theo_server: bool | None`, `duyet: Literal["da_duyet","moi","thay_doi"]`.
- `McpServerOut` thêm `cong_cu_bi_bo_qua: list[SkippedTool{ten, trung_voi}]`.
- `PATCH /api/admin/tools/{id}` với `bat=true` thì gọi `registry.approve(tool)` trước `commit`.
- Mọi endpoint cần quyền admin, như các endpoint hiện có.

- [ ] **Step 1: Viết test lỗi trước** (`client` fixture + `login` admin):
  - `test_address_validation` (Review Focus 1), tham số hóa:
    - `" http://LOCALHOST:9105/mcp "` thì `normalize_mcp_address` trả `"http://LOCALHOST:9105/mcp"` (cắt khoảng trắng, giữ nguyên chữ);
    - các địa chỉ `"https://example.com/mcp"`, `"http://127.0.0.1.evil.com:9105/mcp"`, `"http://10.0.0.5:9105/mcp"`, `"http://localhost/mcp"` (thiếu cổng), `"ftp://127.0.0.1:9105/mcp"` đều ném lỗi.
  - `test_check_lists_tools_without_saving`: `check` với `http://127.0.0.1:9105/mcp` trả 3 công cụ, `renew_book.chi_doc_theo_server is False`, `"ma_sv" not in tham_so["properties"]`; số dòng `mcp_server` không đổi.
  - `test_add_server_then_tools_disabled_new`: POST trả 201, có 3 công cụ đều `bat=False, duyet="moi"`. POST trùng tên trả 409 `TEN_MCP_DA_TON_TAI`. Tên `"Thu Vien"` trả 422 `TEN_MCP_KHONG_HOP_LE`.
  - `test_add_unreachable_server_rejected`: địa chỉ `http://127.0.0.1:9199/mcp` (không có server) trả 422 `MCP_KHONG_KET_NOI_DUOC`, CSDL không thêm dòng.
  - `test_enable_tool_records_approval`: PATCH `renew_book` `bat=true` thì `ban_duyet` khác NULL và `duyet == "da_duyet"`. PATCH `can_xac_nhan=false` vẫn 422 `KHONG_THE_BO_XAC_NHAN` (quy tắc cũ).
  - `test_patch_server_bad_address_keeps_db` (Review Focus 5): PATCH `dia_chi="https://x.com/mcp"` trả 422, `dia_chi` trong CSDL giữ nguyên.
  - `test_student_cannot_manage_servers`: tài khoản sinh viên gọi POST thì 403.
- [ ] **Step 2: Chạy** `pytest tests/assistant/test_admin.py -q`. Mong đợi: FAIL.
- [ ] **Step 3: Viết code** và sửa `90_reset_demo_assistant.sql`.
- [ ] **Step 4: Chạy** `pytest -q` (toàn bộ backend) và `ruff check src tests`. Mong đợi: PASS và sạch.
- [ ] **Step 5: Commit:** `git commit -m "Admin API: kiểm tra/thêm/sửa MCP server (chỉ 127.0.0.1/localhost), nhãn duyệt, ghi mã băm khi bật"`

### Task 6: Giao diện `/admin/mcp`: hộp thoại thêm server, nhãn duyệt, xem mô tả đầy đủ

**Files:**
- Modify: `web/src/lib/adminTypes.ts` (`Tool`, `McpServerItem`, thêm `ToolPreview`, `McpCheckResult`)
- Modify: `web/src/lib/admin.ts`: thêm `reviewBadge(duyet: Tool['duyet']): { text: string; tone: 'new' | 'changed' } | null`
- Modify: `web/src/pages/admin/McpPage.tsx`
- Test: `web/src/lib/admin.test.ts`

**Interfaces:**
- Consumes: API ở Task 5.
- `reviewBadge`:
  - `'moi'` cho `{text: 'Mới — cần duyệt', tone: 'new'}`;
  - `'thay_doi'` cho `{text: 'Mô tả đã thay đổi — cần duyệt lại', tone: 'changed'}`;
  - `'da_duyet'` cho `null`.

- [ ] **Step 1: Viết test lỗi trước** `reviewBadge` trong `admin.test.ts`, đủ 3 trường hợp với đúng chuỗi trên.
- [ ] **Step 2: Chạy** `cd web; npm test`. Mong đợi: FAIL.
- [ ] **Step 3: Viết code.**
  - Thêm `reviewBadge`.
  - `McpPage` có:
    - nút **"Thêm MCP server"** mở hộp thoại gồm Tên / Mô tả / Địa chỉ, nút **"Kiểm tra kết nối"** hiện bảng xem trước (title, tên, mô tả, gợi ý "Server tự khai báo: chỉ đọc", cảnh báo trùng tên), và nút **"Lưu"** (chỉ bật sau khi kiểm tra thành công);
    - lỗi API hiện `detail` tiếng Việt;
    - mỗi dòng công cụ có badge từ `reviewBadge` và nút mở rộng xem `mo_ta_day_du` cùng `tham_so` (JSON thu gọn);
    - danh sách `cong_cu_bi_bo_qua` hiện dưới server: "Trùng tên với công cụ của server X — bị bỏ qua".
  - Dùng component sẵn có trong `components/admin/ui.tsx`.
- [ ] **Step 4: Chạy** `npm test` và `npm run build`. Mong đợi: PASS, build không lỗi TypeScript.
- [ ] **Step 5: Kiểm tay** (chạy `run_all.ps1` và `npm run dev`, đăng nhập admin):
  - thêm `thu_vien` với địa chỉ `http://127.0.0.1:9105/mcp` thì thấy 3 công cụ "Mới — cần duyệt";
  - bật `get_borrowed_books` và `renew_book`;
  - đăng nhập SV22001, hỏi "Gia hạn giúp em cuốn sách sắp hết hạn" thì thấy thẻ "Gia hạn sách (…)", bấm Xác nhận thì hạn trả thành 11/12/2026.
- [ ] **Step 6: Commit:** `git commit -m "Web quản trị: thêm MCP server, nhãn duyệt, xem mô tả công cụ"`

### Task 7: demo_check, tài liệu, kiểm tra toàn bộ

**Files:**
- Modify: `backend/scripts/demo_check.py`: thêm `demo8` "Thư viện: thêm server + gia hạn".
  - Admin `POST /api/admin/mcp-servers` (`thu_vien`, `http://127.0.0.1:9105/mcp`), rồi PATCH bật `get_borrowed_books` và `renew_book`.
  - SV22001 chat "Gia hạn giúp em cuốn sách sắp hết hạn", có thẻ `renew_book`, xác nhận thì thành công.
  - Ở `finally`, không xóa server; `reset_demo` đã lo phần này.
  - `basic_checks` cảnh báo nếu đang có server `thu_vien`, tức là chưa reset.
- Modify docs:
  - `docs/01-dac-ta-yeu-cau.md`: AD-11 "Thêm và duyệt MCP server (chỉ địa chỉ trên máy; công cụ mới mặc định tắt; mô tả đổi sau khi duyệt thì tự tắt)"; SV-11 "Xem sách đang mượn, tìm sách, gia hạn sách qua trợ lý".
  - `docs/02-kien-truc.md`: server thứ 5, luồng thêm server.
  - `docs/03-co-so-du-lieu.md`: `sach`, `muon_sach`, `cong_cu.ban_duyet`.
  - `docs/04-api.md`: 3 endpoint qlsv, 3 endpoint admin.
  - `docs/05-mcp-servers.md`: `thu_vien`, dùng `title`.
  - `docs/08-giao-dien.md`: hộp thoại, nhãn.
  - `docs/10-ra-soat-bao-mat.md`: tool poisoning, rug pull (mã băm duyệt), trùng tên, SSRF (giới hạn địa chỉ), dùng chung `INTERNAL_API_TOKEN` (hạn chế).
  - `README.md`: dòng cổng 9105, và câu "server Thư viện được thêm trên trang MCP & quyền khi demo".
- [ ] **Step 1: Chạy** `.\scripts\reset_demo.ps1`, `.\scripts\run_all.ps1`, rồi `python scripts/demo_check.py`. Mong đợi: mọi mục đạt, không gọi LLM.
- [ ] **Step 2: Chạy** `python scripts/demo_check.py --llm`. Mong đợi: demo 1–8 đạt. **Tốn hạn mức Gemini, chỉ chạy một lần.**
- [ ] **Step 3: Chạy** `pytest -q`, `ruff check src tests`, `cd ..\web; npm test; npm run build`. Mong đợi: tất cả sạch.
- [ ] **Step 4: Commit:** `git commit -m "demo_check demo 8 (thư viện), tài liệu AD-11/SV-11, rà soát bảo mật MCP server mới"`
