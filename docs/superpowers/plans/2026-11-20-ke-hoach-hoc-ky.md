# Tư vấn kế hoạch học kỳ tới + đăng ký cả gói — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sinh viên hỏi "kỳ sau em nên đăng ký gì", trợ lý lập gói đăng ký chắc chắn (kèm lý do chọn/loại) và cho xác nhận cả gói bằng một thẻ, đăng ký nguyên khối.

**Architecture:**
- qlsv_api tính gói (thuần, lặp lại được) và đăng ký gói trong một giao dịch, dùng lại `registration_service.register`.
- MCP `dao_tao` thêm `plan_next_semester` (đọc) và `register_courses_bundle` (ghi, cần xác nhận).
- assistant_api dùng nguyên cơ chế thẻ hiện có, chỉ thêm mô tả thẻ nhiều dòng và kiểm tra trước cả gói.

**Tech Stack:** FastAPI, SQLAlchemy 2 + SQL Server, MCP SDK 2.x (`MCPServer`), pytest/respx, React + Vitest.

**Spec:** `docs/superpowers/specs/2026-11-20-ke-hoach-hoc-ky-design.md`

## Global Constraints
- Theo CLAUDE.md:
  - code tiếng Anh, chuỗi hiển thị tiếng Việt có dấu;
  - lỗi `{"detail","code"}`;
  - `ma_sv` là `MaSv` (INJECTED), ẩn khỏi schema;
  - khóa hàng bằng `lock_for_update` (không dùng `with_for_update`);
  - test CSDL rollback qua fixture `db` của `tests/qlsv/conftest.py`.
- Gói "tất cả hoặc không gì cả": một lớp lỗi → không lớp nào được ghi.
- Gói đi qua đúng 9 bước kiểm tra của `registration_service.register` (không viết lại quy tắc). **Không sửa `register()`.**
- Học kỳ đích = học kỳ đang mở đăng ký (`semester_service.open_registration_semester`); không có → 409 `KHONG_CO_HOC_KY_MO_DANG_KY`.
- Thứ tự ưu tiên học phần:
  1. học lại (id thuộc `summary.failed_course_ids`);
  2. bắt buộc (`bat_buoc`);
  3. `hoc_ky_goi_y` tăng dần;
  4. `ma_hp`.
- Trong một học phần: xét lớp theo `ma_lop` tăng dần, chọn lớp hợp lệ đầu tiên.
- Gói tối đa 8 lớp, mã lớp không trùng.
- Kỳ vọng dữ liệu mẫu (SV22001, `DEMO_NOW` 20/11/2026):
  - đề xuất `["IT004.02", "SE201.01"]`, tổng 6 tín chỉ;
  - bị loại: SE105 `DANG_HOC`, SE202 có lớp SE202.01 `LOP_DA_DAY`.
- Commit sau mỗi task. Message tiếng Việt, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus
1. **Sinh viên đã đăng ký sẵn một lớp ở học kỳ đích.** Gói không đề xuất lại học phần đó. Tín chỉ và lịch của lớp đó vẫn được tính, nên không đề xuất lớp trùng lịch với nó. Thuộc Task 1: `test_plan_counts_existing_registration`.
2. **Gói có hai lớp trùng lịch nhau, hoặc tổng tín chỉ vượt giới hạn** (dù từng lớp đứng riêng thì hợp lệ). Bundle phải báo lỗi và không ghi lớp nào. Thuộc Task 2: `test_bundle_conflict_inside_bundle_rolls_back`.
3. **Không có gì để đề xuất**, ví dụ SV21001 chỉ còn SE202 mà lớp đã đầy. Kết quả có `de_xuat` rỗng, có lý do loại, `thong_bao` nói rõ là không có gói. Trợ lý không tạo thẻ. Thuộc Task 1: `test_plan_nothing_available`; Task 3: `test_plan_tool_empty_message`.
4. **LLM gửi `ma_lop` trùng lặp, hoặc danh sách rỗng.** Schema chặn ngay ở MCP: `min_length=1`, `max_length=8`. Bundle check trả 422 `DANH_SACH_LOP_KHONG_HOP_LE` khi có mã trùng. Thuộc Task 2: `test_bundle_rejects_duplicates`.
5. **Ngoài thời gian đăng ký** (`AFTER_REGISTRATION`). Lập kế hoạch trả 409 `KHONG_CO_HOC_KY_MO_DANG_KY`, không lỗi 500. Thuộc Task 1: `test_plan_no_open_semester`.

---

### Task 1: qlsv_api — lập kế hoạch học kỳ (`planning_service`)

**Files:**
- Create: `backend/src/qlsv_api/services/planning_service.py`
- Modify:
  - `backend/src/qlsv_api/schemas.py`: thêm `PlannedSection`, `ExcludedSection`, `ExcludedCourse`, `SemesterPlanOut`;
  - `backend/src/qlsv_api/routers/registrations.py`: thêm route.
- Test: `backend/tests/qlsv/test_planning.py`

**Interfaces:**
- Produces:
  - `planning_service.plan_next_semester(db: Session, ma_sv: str, now: datetime) -> SemesterPlanOut`
  - Route: `GET /internal/students/{ma_sv}/semester-plan` → `SemesterPlanOut`. Chỉ đọc, không cần `run_in_transaction`.
  - Schemas (kế thừa `Schema` như các schema khác trong file):
    - `PlannedSection{ma_lop, ma_hp, ten_hp, tin_chi:int, lich:str, bat_buoc:bool, ly_do_chon:str}`
    - `ExcludedSection{ma_lop, ma_loi, ly_do}`
    - `ExcludedCourse{ma_hp, ten_hp, ma_loi, ly_do, lop: list[ExcludedSection] = []}`
    - `SemesterPlanOut{hoc_ky:str (ma_hoc_ky), ten_hoc_ky:str, tin_chi_toi_da:int, tin_chi_da_dang_ky:int, de_xuat:list[PlannedSection], tong_tin_chi_de_xuat:int, bi_loai:list[ExcludedCourse]}`
  - Mã lỗi loại:
    - cấp học phần: `DANG_HOC`, `CHUA_DAT_TIEN_QUYET`, `KHONG_CO_LOP_MO`, `KHONG_CON_LOP_PHU_HOP` (mọi lớp đều bị loại; chi tiết nằm trong `lop`);
    - cấp lớp: `LOP_DA_DAY`, `TRUNG_LICH`, `VUOT_TIN_CHI_TOI_DA`.
  - `lich` dùng `schedule_label(lop)`. `ly_do_chon` gồm: "Học lại (đã bị điểm F)", "Bắt buộc, học kỳ gợi ý N", "Tự chọn".

- [ ] **Step 1: Viết test lỗi trước** (`tests/qlsv/test_planning.py`, dùng fixture `db`, `DEMO_NOW`, `AFTER_REGISTRATION`):
  - `test_plan_sv22001`:
    - `[s.ma_lop for s in out.de_xuat] == ["IT004.02", "SE201.01"]`, `out.tong_tin_chi_de_xuat == 6`, `out.hoc_ky == "2026-2027-HK2"`, `out.tin_chi_toi_da == 25`;
    - `de_xuat[0].ly_do_chon` chứa "Học lại";
    - `{c.ma_hp: c.ma_loi for c in out.bi_loai} == {"SE105": "DANG_HOC", "SE202": "KHONG_CON_LOP_PHU_HOP"}`;
    - lớp con của SE202: `[("SE202.01", "LOP_DA_DAY")]`.
  - `test_plan_counts_existing_registration`:
    - đăng ký trước `IT004.03` cho SV22001 bằng `registration_service.register` rồi `db.commit()`;
    - IT004 không còn trong `de_xuat` và không có trong `bi_loai`;
    - `out.tin_chi_da_dang_ky == 3`; `de_xuat` là `["SE201.01"]`.
  - `test_plan_conflict_with_chosen`:
    - dời SE201.01 sang `thu=2, tiet_bat_dau=1, tiet_ket_thuc=3` (trùng IT004.02) bằng `update(LopHocPhan)` rồi `db.commit()`;
    - SE201 bị loại với lớp `("SE201.01", "TRUNG_LICH")`, và `ly_do` nêu "IT004.02".
  - `test_plan_credit_limit`:
    - đặt `HocKy.tin_chi_toi_da = 4` cho học kỳ 8;
    - `de_xuat == ["IT004.02"]`, SE201 có lớp `VUOT_TIN_CHI_TOI_DA`.
  - `test_plan_missing_prerequisite`: SV22002 (đã đạt IT001, SE101, IT002) → SE201 `CHUA_DAT_TIEN_QUYET` (thiếu IT003), `ly_do` chứa "IT003".
  - `test_plan_nothing_available`: SV21001 → `de_xuat == []`, `bi_loai[0].ma_hp == "SE202"`.
  - `test_plan_no_open_semester`: `now=AFTER_REGISTRATION` → `BusinessError` code `KHONG_CO_HOC_KY_MO_DANG_KY`, status 409.
  - `test_plan_route` (fixture `client`): `GET /internal/students/SV22001/semester-plan` → 200, `json()["de_xuat"][0]["ma_lop"] == "IT004.02"`; `SV99999` → 404.
- [ ] **Step 2: Chạy** `cd backend; pytest tests/qlsv/test_planning.py -q`. Mong đợi: FAIL (ImportError `planning_service`).
- [ ] **Step 3: Viết code.** Thuật toán thuần trong `planning_service`:
  1. **Ứng viên**: học phần trong chương trình (`student_repo.get_program` + `list_program_courses`) chưa thuộc `summary.passed_course_ids`.
  2. **Đã đăng ký ở học kỳ đích** (`registration_repo.list_active_in_semester`): bỏ khỏi ứng viên, không ghi lý do. Lớp của chúng là "lịch đã chiếm" và cộng vào tín chỉ.
  3. **Đang học**: có đăng ký `da_dang_ky` ở `semester_service.current_semester(db, now)`, học kỳ này khác học kỳ đích, và học phần chưa có kết quả ở học kỳ đó → `DANG_HOC`. `ly_do` nêu mã lớp đang học.
  4. **Tiên quyết**: dùng `section_repo.list_prerequisites`; thiếu → `CHUA_DAT_TIEN_QUYET`, `ly_do` liệt kê `ma_hp - ten_hp`.
  5. **Lớp mở**: lấy lớp của học kỳ đích theo học phần, đếm chỗ bằng `section_repo.count_registered`; không có lớp → `KHONG_CO_LOP_MO`.
  6. Sắp xếp theo thứ tự ưu tiên ở Global Constraints. Giới hạn tín chỉ: `tin_chi_toi_da_canh_bao` nếu `summary.canh_bao_hoc_vu`, ngược lại `tin_chi_toi_da`.
  7. Duyệt tham lam. Phần kiểm tra trùng lịch dùng lại `registration_service._overlaps` (đổi tên thành `overlaps`, giữ alias `_overlaps`, nếu muốn import công khai). Không có lớp nào → `KHONG_CON_LOP_PHU_HOP` kèm danh sách `lop`.
  8. Truy vấn lớp của học kỳ theo học phần: thêm `section_repo.list_in_semester(db, hoc_ky_id: int, hoc_phan_ids: Iterable[int]) -> list[LopHocPhan]`, sắp theo `ma_lop`.
- [ ] **Step 4: Chạy** `pytest tests/qlsv -q` và `ruff check src tests`. Mong đợi: PASS, sạch.
- [ ] **Step 5: Commit:** `git commit -m "QLSV: lập kế hoạch học kỳ tới (gói đề xuất + lý do loại)"`

### Task 2: qlsv_api — đăng ký cả gói (nguyên khối)

**Files:**
- Modify:
  - `backend/src/qlsv_api/services/registration_service.py`: thêm `register_bundle`;
  - `backend/src/qlsv_api/schemas.py`: thêm `BundleIn`, `BundleOut`;
  - `backend/src/qlsv_api/routers/registrations.py`.
- Test: `backend/tests/qlsv/test_registration.py` (thêm test)

**Interfaces:**
- Produces:
  - `registration_service.register_bundle(db, ma_sv: str, ma_lops: list[str], now: datetime, dry_run: bool = False) -> BundleOut`
  - `BundleIn{ma_lop: list[NonEmptyStr]}` (Field `min_length=1, max_length=8`)
  - `BundleOut{thanh_cong: bool = True, trang_thai: "da_dang_ky"|"hop_le", lop: list[RegistrationOut], tong_tin_chi: int}`
  - Routes:
    - `POST /internal/students/{ma_sv}/registrations/bundle` → 201, chạy trong `run_in_transaction`;
    - `POST .../registrations/bundle/check` → 200, `finally: db.rollback()` như route `check` hiện có.
  - Lỗi:
    - mã lớp trùng (so sánh sau `strip().upper()`) → `invalid("DANH_SACH_LOP_KHONG_HOP_LE", ...)` (422);
    - lỗi của một lớp → `BusinessError(code gốc, f"Lớp {ma_lop}: {message gốc}", status gốc)`.
- Cách làm:
  - Gọi `register(db, ma_sv, ma_lop, now)` lần lượt cho từng lớp, theo `ma_lop` tăng dần (thứ tự khóa cố định, tránh deadlock), luôn với `dry_run=False` nhưng **chưa commit**.
  - Lớp sau tự thấy lớp trước, vì `list_active_in_semester` đọc trong cùng giao dịch sau `flush`.
  - `dry_run=True` thì cuối hàm `db.rollback()` do router lo. Trả `trang_thai="hop_le"` và từng `RegistrationOut.trang_thai="hop_le"`.
  - Ghi thành ruling nếu khác: dry_run của gói phải thật sự ghi tạm (flush) mới bắt được trùng lịch trong gói, rồi router rollback.

- [ ] **Step 1: Viết test lỗi trước:**
  - `test_bundle_success`: `register_bundle(db, "SV22001", ["SE201.01", "IT004.02"], DEMO_NOW)` rồi `db.commit()` → `tong_tin_chi == 6`, `[l.ma_lop for l in out.lop] == ["IT004.02", "SE201.01"]`, và có 2 dòng `DangKyHocPhan` `da_dang_ky` mới ở học kỳ 8.
  - `test_bundle_conflict_inside_bundle_rolls_back`:
    - `["IT004.02", "SE105.02"]` (trùng lịch nhau) → `BusinessError` code `TRUNG_LICH`, `message` bắt đầu "Lớp SE105.02";
    - sau `db.rollback()` không có đăng ký IT004.02 nào của SV22001.
  - `test_bundle_failure_on_one_class`: `["IT004.02", "SE202.01"]` → `LOP_DA_DAY`, không ghi lớp nào.
  - `test_bundle_rejects_duplicates`: `["IT004.02", "it004.02 "]` → `DANH_SACH_LOP_KHONG_HOP_LE`, status 422.
  - `test_bundle_routes` (fixture `client`):
    - `/bundle/check` với 2 lớp hợp lệ → 200 `trang_thai == "hop_le"`, rồi gọi lại vẫn 200 (không ghi);
    - `/bundle` → 201;
    - body `{"ma_lop": []}` → 422.
- [ ] **Step 2: Chạy** `pytest tests/qlsv/test_registration.py -q`. Mong đợi: FAIL.
- [ ] **Step 3: Viết code.**
- [ ] **Step 4: Chạy** `pytest tests/qlsv -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit:** `git commit -m "QLSV: đăng ký cả gói lớp học phần trong một giao dịch"`

### Task 3: MCP `dao_tao` — `plan_next_semester`, `register_courses_bundle`; seed công cụ

**Files:**
- Modify:
  - `backend/src/mcp_servers/dao_tao.py`;
  - `database/04_assistant_seed.sql`: thêm 2 dòng sau `cancel_course_registration`, server 1 — `plan_next_semester` `'doc', 0, 1` ("Lập kế hoạch đăng ký học kỳ tới"), `register_courses_bundle` `'ghi', 1, 1` ("Đăng ký cả gói lớp học phần");
  - `database/90_reset_demo_assistant.sql`: thêm 2 dòng tương ứng vào bảng VALUES;
  - `backend/scripts/setup.ps1`: thêm `07_nang_cap_ke_hoach_hoc_ky.sql` vào vòng lặp nâng cấp;
  - `backend/scripts/demo_check.py`: 16 → 18.
- Create: `database/07_nang_cap_ke_hoach_hoc_ky.sql` — `INSERT` 2 công cụ nếu chưa có (theo `ten`, `mcp_server_id` lấy từ `mcp_server.ten = N'dao_tao'`). Chạy lại nhiều lần an toàn; giữ BOM/CRLF như file 06.
- Test: `backend/tests/mcp/test_dao_tao.py` (thêm test)

**Interfaces:**
- Consumes: route của Task 1 và Task 2.
- Produces (tools):
  - `plan_next_semester(ma_sv: MaSv) -> dict`:
    - trả `{hoc_ky, ten_hoc_ky, tin_chi_toi_da, tin_chi_da_dang_ky, de_xuat, tong_tin_chi_de_xuat, bi_loai, thong_bao}`;
    - `thong_bao` khi có gói: `"Đề xuất {n} lớp ({tc} tín chỉ) cho {ten_hoc_ky}: IT004.02 – Cơ sở dữ liệu; …. Không đề xuất: SE105 – … (lý do); …"`;
    - khi rỗng: bắt đầu bằng `"Không có lớp nào phù hợp để đề xuất cho {ten_hoc_ky}."`.
  - `register_courses_bundle(ma_sv: MaSv, ma_lop: Annotated[list[str], Field(min_length=1, max_length=8, description=...)], chi_kiem_tra: ChiKiemTra = False) -> dict`:
    - gọi `POST .../registrations/bundle` (hoặc `/bundle/check` khi `chi_kiem_tra`);
    - trả `{thanh_cong, lop: [{ma_lop, ten_hp, tin_chi, lich}], tong_tin_chi, thong_bao}`.
  - Docstring tiếng Việt nói rõ: dùng khi sinh viên hỏi kỳ sau nên học gì / lập kế hoạch; chỉ đăng ký các lớp lấy từ `plan_next_semester` hoặc sinh viên chỉ định; cần xác nhận; nguyên khối.
- Lưu ý test assistant: CSDL dev chưa có 2 dòng mới cho tới khi chạy 07. Sau Task 3, **chạy `07` trên CSDL dev** (sqlcmd như đã làm với 06).

- [ ] **Step 1: Viết test lỗi trước** (`tests/mcp/test_dao_tao.py`, respx `qlsv_mock`):
  - `test_plan_tool_message`: mock `GET /internal/students/SV22001/semester-plan` trả gói 2 lớp → `out["de_xuat"]` có 2 lớp, `thong_bao` chứa "IT004.02" và "6 tín chỉ".
  - `test_plan_tool_empty_message`: `de_xuat: []` → `thong_bao.startswith("Không có lớp nào phù hợp")`.
  - `test_bundle_tool_check_and_error`:
    - `chi_kiem_tra=True` gọi đúng route `/bundle/check`;
    - mock 409 `TRUNG_LICH` → `out["ma_loi"] == "TRUNG_LICH"`.
  - `test_bundle_tool_schema`: `list_tools` → `ma_lop` là `array`, `minItems == 1`, `maxItems == 8`; `ma_sv` có INJECTED_NOTE.
- [ ] **Step 2: Chạy** `pytest tests/mcp/test_dao_tao.py -q`. Mong đợi: FAIL.
- [ ] **Step 3: Viết code + SQL**, rồi chạy `07` trên CSDL dev.
- [ ] **Step 4: Chạy** `pytest tests/mcp tests/test_scripts.py -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit:** `git commit -m "MCP dao_tao: plan_next_semester, register_courses_bundle (+ seed, nâng cấp 07)"`

### Task 4: assistant_api — thẻ cả gói, nhãn, system prompt; web giữ xuống dòng

**Files:**
- Modify:
  - `backend/src/assistant_api/agent/actions.py` (`describe`);
  - `backend/src/assistant_api/agent/prompts.py` (`TOOL_LABELS`, `SYSTEM_PROMPT`);
  - `web/src/components/chat/PendingActionCard.tsx`: thẻ `<p>` của `mo_ta` thêm `whitespace-pre-line`.
- Test:
  - `backend/tests/assistant/test_actions.py`;
  - `backend/tests/assistant/test_agent_loop.py`.

**Interfaces:**
- Consumes: tools Task 3.
- `describe("register_courses_bundle", args, lookup)`:
  - **Kiểm tra trước:** gọi `lookup("dao_tao", "register_courses_bundle", {"ma_sv", "ma_lop", "chi_kiem_tra": True})`. Lỗi nghiệp vụ (không thuộc `_INFRA_ERRORS`) → `ActionRejected(code, thong_bao)`.
  - **Mô tả:** tra từng lớp bằng `_section`.
    - Dòng 1: `"Đăng ký {n} lớp ({tc} tín chỉ) học kỳ tới:"`.
    - Mỗi lớp một dòng: `"• {ma_lop} – {ten_hp} ({tin_chi} tín chỉ), {lich}"`.
    - Tra lớp lỗi hạ tầng → `"• {ma_lop}"`.
- `TOOL_LABELS`: `plan_next_semester` → "Đang lập kế hoạch học kỳ tới"; `register_courses_bundle` → "Đang đăng ký cả gói học phần".
- `SYSTEM_PROMPT` thêm một gạch đầu dòng: "Sinh viên hỏi kỳ sau nên đăng ký gì / nhờ lập kế hoạch học kỳ: gọi plan_next_semester, chỉ đề xuất đúng các lớp trong kết quả và nêu lý do các môn bị loại; sinh viên đồng ý đăng ký cả gói thì gọi register_courses_bundle với đúng các mã lớp đó (một thẻ xác nhận)."

- [ ] **Step 1: Viết test lỗi trước:**
  - `test_describe_bundle_lists_each_class` (test_actions, lookup giả):
    - trả `hop_le` cho check;
    - trả lớp IT004.02 / SE201.01 cho `search_course_sections`;
    - kết quả `.splitlines()`: dòng 0 == "Đăng ký 2 lớp (6 tín chỉ) học kỳ tới:", dòng 1 bắt đầu "• IT004.02 – Cơ sở dữ liệu (3 tín chỉ)".
  - `test_describe_bundle_precheck_rejects`: check trả lỗi `TRUNG_LICH` → `ActionRejected` code `TRUNG_LICH`.
  - `test_plan_then_bundle_one_card` (test_agent_loop, FakeLLM + `qlsv_mock`):
    - LLM gọi `plan_next_semester` → text → (lượt 2) `register_courses_bundle {"ma_lop": ["IT004.02","SE201.01"]}`;
    - đúng **một** sự kiện `pending_action`, `ten_cong_cu == "register_courses_bundle"`;
    - nhật ký có dòng `cho_xac_nhan` với `tham_so["ma_sv"] == student.ma_sv`;
    - không có lời gọi `POST .../registrations/bundle` thật trước khi xác nhận (respx route `.called is False`).
- [ ] **Step 2: Chạy** test assistant liên quan. Mong đợi: FAIL.
- [ ] **Step 3: Viết code.**
- [ ] **Step 4: Chạy** `pytest -q` (toàn backend), `cd web; npm test; npm run build`. Mong đợi: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Trợ lý: thẻ xác nhận cả gói đăng ký, nhãn và hướng dẫn lập kế hoạch học kỳ"`

### Task 5: Thực nghiệm, demo_check, tài liệu

**Files:**
- Modify:
  - `evaluation/datasets/agent_scenarios.jsonl`: thêm A073–A075, `loai: "nhieu_buoc"`:
    - A073 SV22001 "Kỳ sau em nên đăng ký những môn gì để kịp tốt nghiệp?" → `cong_cu_mong_doi: ["plan_next_semester"]`, `ket_qua_mong_doi: "thanh_cong"`;
    - A074 SV22001 "Lập kế hoạch học kỳ tới rồi đăng ký cả gói giúp em." → `["plan_next_semester","register_courses_bundle"]`, `tham_so_mong_doi: {"register_courses_bundle": {"ma_lop": ["IT004.02","SE201.01"]}}`, `can_xac_nhan: true`, `tu_dong_xac_nhan: true`, `ket_qua_mong_doi: "thanh_cong"`;
    - A075 SV21001 "Kỳ sau em đăng ký gì để tốt nghiệp?" → `["plan_next_semester"]`, `ket_qua_mong_doi: "thanh_cong"`; câu trả lời phải nêu lớp SE202.01 đã đầy (nếu dataset có trường chuỗi khớp, dùng `["đầy"]`).
    - Nếu `run_agent.py` so tham số list theo thứ tự, ghi ruling và so như tập hợp.
  - `backend/scripts/demo_check.py`: `demo9` "Kế hoạch học kỳ + đăng ký cả gói":
    - SV22001 hỏi câu A074;
    - kiểm `plan_next_semester` có trong `tool_names`;
    - đúng một thẻ `register_courses_bundle` có "IT004.02" và "SE201.01";
    - xác nhận → `("register_courses_bundle","thanh_cong")`.
    - Demo 9 chạy SAU demo 3, mà demo 3 đã đăng ký IT004.02. Vì vậy chạy demo9 với tài khoản sau reset, hoặc đặt demo9 trước demo3 — chọn **đặt trước demo 3** và ghi chú.
  - Tài liệu:
    - `docs/01-dac-ta-yeu-cau.md`: SV-12 "Hỏi kế hoạch học kỳ tới, nhận gói đề xuất kèm lý do, đăng ký cả gói bằng một lần xác nhận"; thêm kịch bản demo 9;
    - `docs/04-api.md`: 3 endpoint qlsv mới;
    - `docs/05-mcp-servers.md`: 2 tool mới trong bảng `dao_tao`;
    - `docs/03-co-so-du-lieu.md`: mục quy tắc lập kế hoạch + đăng ký gói;
    - `docs/09-danh-gia.md`: ghi chú A073–A075 và việc thêm 2 công cụ làm kết quả TN3 cũ không so trực tiếp được (chạy lại tuần 3);
    - `README.md`: dòng demo 9; "16 công cụ" → "18 công cụ";
    - `CLAUDE.md`: mục `dao_tao` thêm "lập kế hoạch học kỳ, đăng ký cả gói".
- [ ] **Step 1: Chạy** `pytest -q`, `ruff check src tests scripts`, kiểm tra JSON từng dòng mới bằng `python -c` (đọc file, `json.loads` mọi dòng không bắt đầu bằng `//`).
- [ ] **Step 2: Chạy** `python scripts/demo_check.py` trên assistant_api bản mới, ở cổng riêng nếu dịch vụ cũ đang chạy. Mong đợi: phần cơ bản đạt, "18 công cụ".
- [ ] **Step 3: (Khi có hạn mức LLM)** `python scripts/demo_check.py --llm`. Người dùng quyết thời điểm chạy.
- [ ] **Step 4: Commit:** `git commit -m "Kế hoạch học kỳ: kịch bản TN3 A073–A075, demo 9, tài liệu SV-12"`
