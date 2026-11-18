# 07. Kế hoạch thực hiện và câu lệnh cho Claude CLI

## Cách làm việc
1. Mở thư mục dự án trong VS Code → Terminal → gõ `claude`.
2. Mỗi giai đoạn: gõ `/giai-doan <số>` (lệnh tùy chỉnh trong `.claude/commands/`) **hoặc** dán prompt bên dưới.
3. Bật **Plan mode** (Shift+Tab) để Claude trình bày kế hoạch trước; đọc kỹ rồi mới cho làm.
4. Xong giai đoạn: tự kiểm tra theo "Tiêu chí hoàn thành" → `git add . && git commit -m "Giai đoạn N: ..."` → gõ `/clear` trước giai đoạn mới cho gọn ngữ cảnh.
5. Gặp lỗi: dán nguyên thông báo lỗi cho Claude, kèm bạn đã làm gì.

Ước lượng khối lượng (một người, làm đều đặn): GĐ 0–2 ~2 tuần, GĐ 3–5 ~3 tuần, GĐ 6–8 ~3 tuần, GĐ 9–10 ~2 tuần. Viết khóa luận song song.

---

## Giai đoạn 0 — Chuẩn bị môi trường (tự làm, không cần Claude)
- Cài: Python 3.11+, Node.js 20 LTS+, Git, SQL Server (Express trở lên) + SSMS, ODBC Driver 18 for SQL Server, VS Code (extension Python, Pylance, ESLint, Tailwind CSS IntelliSense), Claude Code.
- Tạo CSDL theo `docs/03-co-so-du-lieu.md`: chạy 4 script SQL trong SSMS hoặc bằng `sqlcmd`.
- Sao chép `.env.example` → `.env`, sửa `DB_SERVER`, điền khóa API LLM, chuỗi bí mật.
- `git init` và commit lần đầu.

**Hoàn thành khi:** SSMS thấy 2 CSDL `tlhv_qlsv`, `tlhv_assistant` có dữ liệu mẫu (tiếng Việt hiển thị đúng dấu).

---

## Giai đoạn 1 — Khung backend + kết nối CSDL
```
Đọc CLAUDE.md, docs/02-kien-truc.md, docs/03-co-so-du-lieu.md.
Thực hiện Giai đoạn 1:
1. Tạo backend/pyproject.toml (dependencies theo CLAUDE.md, nhóm [dev] có pytest, httpx, respx, ruff) và cấu trúc thư mục backend/src như CLAUDE.md.
2. src/shared/config.py: pydantic-settings đọc .env ở thư mục gốc dự án (đường dẫn tuyệt đối tính từ file).
3. src/shared/db.py: hai engine SQLAlchemy riêng cho tlhv_qlsv và tlhv_assistant (mssql+pyodbc, ODBC Driver 18, Windows Authentication mặc định, pool_pre_ping), session factory, dependency cho FastAPI.
4. src/shared/time.py: hàm now() trả giờ Asia/Ho_Chi_Minh, ưu tiên DEMO_NOW.
5. Model ORM (SQLAlchemy 2.x, Mapped[]) khớp CHÍNH XÁC với database/01 và 02 — không tạo bảng bằng ORM, chỉ ánh xạ.
6. scripts/seed_users.py: tạo 6 tài khoản như bảng trong docs/03 (bcrypt), lấy ma_khoa từ qlsv. Chạy lại không bị trùng.
7. tests/test_db.py: kiểm tra đọc được 5 sinh viên và 16 công cụ.
Chưa làm API. Trình bày kế hoạch trước khi code.
```
**Hoàn thành khi:** `pip install -e ".[dev]"` chạy được, `python scripts/seed_users.py` tạo 6 tài khoản, `pytest` xanh.

---

## Giai đoạn 2 — Hệ thống QLSV giả lập (qlsv_api)
```
Đọc CLAUDE.md, docs/03-co-so-du-lieu.md (mục quy tắc nghiệp vụ), docs/04-api.md (phần A).
Thực hiện Giai đoạn 2: xây src/qlsv_api (FastAPI, cổng 8001, chỉ 127.0.0.1).
- Middleware kiểm tra X-Internal-Token cho mọi route /internal.
- Tách tầng: routers/ (HTTP) → services/ (nghiệp vụ) → repositories/ (truy vấn). Nghiệp vụ không phụ thuộc FastAPI.
- Cài đủ quy tắc: GPA tích lũy, tín chỉ tích lũy, tiến độ tốt nghiệp, 9 kiểm tra khi đăng ký học phần với đúng mã lỗi, hủy đăng ký, đơn từ (sinh ma_don, kiểm tra nợ học phí khi bảo lưu).
- Dùng shared.time.now() cho mọi so sánh thời gian.
- Test pytest cho TỪNG mã lỗi đăng ký dựa trên dữ liệu mẫu (vd SV22001 đăng ký SE105.02 sau IT004.02 → TRUNG_LICH; SE202.01 → LOP_DA_DAY; SV22001 đăng ký SE104.01 → DA_DAT_HOC_PHAN).
  Test chạy trên CSDL thật nhưng bọc mỗi test trong transaction rồi rollback.
- Thêm scripts/generate_more_data.py (tuỳ chọn): sinh thêm 50 sinh viên ngẫu nhiên có điểm hợp lệ để demo thống kê.
```
**Hoàn thành khi:** `/docs` của qlsv_api gọi thử được; giá trị khớp dữ liệu mẫu: **SV22001 tích lũy 25 tín chỉ, GPA 3.06** (chưa đạt IT004, SE105, SE201, SE202); **SV21001 tích lũy 35 tín chỉ, GPA 3.36** (chỉ thiếu SE202); test xanh.

---

## Giai đoạn 3 — MCP servers đọc dữ liệu (dao_tao, tai_chinh, ctsv phần đọc)
```
Đọc CLAUDE.md, docs/05-mcp-servers.md.
Kiểm tra tài liệu chính thức mới nhất của Python MCP SDK (FastMCP, streamable HTTP, cách thêm middleware xác thực) trước khi viết.
Thực hiện Giai đoạn 3:
- src/mcp_servers/common.py: QlsvClient, xác thực Bearer INTERNAL_API_TOKEN, chuẩn trả lỗi.
- dao_tao.py (chỉ các tool đọc), tai_chinh.py, ctsv.py (chỉ list_my_requests, get_request_status).
- Docstring tiếng Việt theo mẫu trong tài liệu.
- Mỗi file chạy được bằng python -m src.mcp_servers.<ten>.
- Test: gọi hàm tool với qlsv_api mock bằng respx; test sai token bị từ chối.
- scripts/run_all.ps1: mở mỗi service backend trong một cửa sổ PowerShell riêng.
Hướng dẫn tôi kiểm tra bằng MCP Inspector.
```
**Hoàn thành khi:** MCP Inspector liệt kê tool và gọi `get_transcript` với `ma_sv=SV22001` ra đúng bảng điểm.

---

## Giai đoạn 4 — RAG + server quy_che
```
Đọc CLAUDE.md, docs/06-rag.md.
Thực hiện Giai đoạn 4:
- src/rag: loader, cleaner, chunker (3 chiến lược; làm theo_dieu và co_dinh trước), embedder, indexer, retriever (hybrid RRF giữa vector Chroma và BM25 Python, lọc phiên bản, rerank tuỳ chọn, các cờ bật/tắt cho thực nghiệm).
- scripts/ingest_folder.py đọc data/van_ban/danh_muc.csv.
- src/mcp_servers/quy_che.py với search_regulations, get_article (bọc nội dung trong <tai_lieu>).
- Test chunker với một đoạn văn bản quy chế mẫu tự tạo trong tests/fixtures; test lọc phiên bản với 2 phiên bản giả.
- In ra thời gian lập chỉ mục và số đoạn.
Tôi sẽ đặt 2-3 file PDF vào data/van_ban/ để thử thật.
```
**Hoàn thành khi:** lập chỉ mục thành công các PDF thật; thử `search_regulations("học lại môn bị F", ma_khoa="K22")` ra đúng Điều.

---

## Giai đoạn 5 — assistant_api: xác thực, hội thoại, vòng lặp Agent (chỉ tool đọc)
```
Đọc CLAUDE.md, docs/02-kien-truc.md (mục 2-7), docs/04-api.md (phần B: auth, hội thoại).
Thực hiện Giai đoạn 5:
- Auth JWT (login, me), phân quyền SV/AD bằng dependency.
- mcp_client/: kết nối các MCP server (streamable HTTP, header Bearer), list_tools, call_tool, tự kết nối lại khi lỗi.
- agent/registry.py: đồng bộ cong_cu với server (mục 7 docs/02), lọc tool đang bật, ẩn tham số ma_sv/ma_khoa khỏi schema, tiêm ngữ cảnh.
- agent/llm.py: bọc litellm (stream + tool calling) và FakeLLM cho test.
- agent/loop.py: vòng lặp theo mục 3 docs/02, MAX_STEPS=6, ghi luot_goi_cong_cu cho mọi lần gọi (cả tham_so_llm và tham_so), lưu tin_nhan (kể cả tool), hậu kiểm trích dẫn.
- agent/prompts.py: system prompt theo mục 4 docs/02.
- Router hội thoại + endpoint SSE gửi tin nhắn (sự kiện theo mục 5 docs/02).
- Giai đoạn này: các tool can_xac_nhan=1 tạm thời trả "chưa hỗ trợ" (làm ở GĐ 6).
- Test vòng lặp bằng FakeLLM: (a) câu hỏi quy chế gọi search_regulations; (b) LLM cố gửi ma_sv="SV22002" → bị ghi đè thành SV22001 và nhật ký lưu cả hai; (c) tool bị tắt → bi_tu_choi.
Cho tôi lệnh curl để thử SSE.
```
**Hoàn thành khi:** dùng curl đăng nhập SV22001, hỏi "Điểm môn Cơ sở dữ liệu của em?" và "Học lại môn F thế nào?" → trả lời đúng, có trích dẫn; bảng `luot_goi_cong_cu` có bản ghi.

---

## Giai đoạn 6 — Tool ghi + cơ chế xác nhận
```
Đọc CLAUDE.md (quy tắc bảo mật), docs/02-kien-truc.md (mục 2, 3), docs/05-mcp-servers.md.
Thực hiện Giai đoạn 6:
- Thêm tool ghi: register_course, cancel_course_registration (dao_tao); request_student_certificate, submit_deferral_request, submit_regrade_request (ctsv).
- Luồng hanh_dong_cho_xac_nhan: tạo, sự kiện pending_action, endpoint confirm/cancel (SSE), hết hạn 10 phút, chỉ chủ sở hữu, không xác nhận 2 lần (khóa hàng bằng SELECT ... FOR UPDATE).
- mo_ta trên thẻ xác nhận sinh từ template theo từng tool (không để LLM tự viết), vd: "Đăng ký lớp IT004.02 – Cơ sở dữ liệu (3 tín chỉ), Thứ 2 tiết 1–3, phòng B2.101". Lấy thông tin lớp bằng search_course_sections trước khi tạo thẻ.
- Endpoint /api/my/requests.
- Test: xác nhận → đăng ký thành công; xác nhận lần 2 → lỗi; người khác xác nhận → 403; hết hạn → het_han; trùng lịch → LLM nhận lỗi TRUNG_LICH.
```
**Hoàn thành khi:** chạy trọn kịch bản demo 3, 4, 6 trong docs/01 bằng curl.

---

## Giai đoạn 7 — Web cho sinh viên
```
Đọc CLAUDE.md, docs/04-api.md, docs/08-giao-dien.md.
Thực hiện Giai đoạn 7: tạo web/ (Vite + React + TS + Tailwind + React Router + TanStack Query).
- Trang đăng nhập; layout sinh viên (sidebar hội thoại).
- Trang chat: đọc SSE bằng fetch + ReadableStream (không dùng EventSource vì cần POST và header), hiển thị token dần, chip trạng thái tool_start/tool_end, trích dẫn [n] bấm mở popover (văn bản, Điều, trang, trích đoạn), thẻ xác nhận với nút Xác nhận / Hủy và đồng hồ đếm hết hạn, nút đánh giá, câu hỏi gợi ý.
- Trang "Thủ tục của em".
- Markdown trong câu trả lời (react-markdown), responsive.
- Proxy Vite /api → http://127.0.0.1:8000.
```
**Hoàn thành khi:** thực hiện được toàn bộ kịch bản demo 1–6 trên trình duyệt.

---

## Giai đoạn 8 — Web quản trị
```
Đọc CLAUDE.md, docs/04-api.md (phần quản trị), docs/08-giao-dien.md.
Thực hiện Giai đoạn 8:
- Backend: các API /api/admin/* còn thiếu (documents + BackgroundTasks lập chỉ mục, chunks, rag/search, mcp-servers, tools PATCH, audit-logs, stats).
- Frontend: Tài liệu (tải lên, trạng thái, xem đoạn, lập chỉ mục lại), Thử truy xuất, MCP & quyền (bật/tắt tool, xác nhận, mức rủi ro), Nhật ký (lọc, xem JSON tham số/kết quả, tô màu tham_so_llm khác tham_so), Thống kê (thẻ số liệu + biểu đồ recharts).
- Phân quyền: sinh viên vào /admin bị chuyển hướng.
```
**Hoàn thành khi:** kịch bản demo 7 chạy được; tải PDF mới lên và hỏi được ngay.

---

## Giai đoạn 9 — Thực nghiệm (Chương 4)
```
Đọc CLAUDE.md, docs/09-danh-gia.md.
Thực hiện Giai đoạn 9:
- evaluation/datasets: tạo khung file jsonl và 10 mẫu ví dụ mỗi loại; tôi sẽ tự bổ sung đủ số lượng.
- evaluation/run_rag_retrieval.py, run_rag_answer.py, run_agent.py, run_security.py theo đúng mô tả, xuất CSV + bảng Markdown vào evaluation/results/<thoi_gian>/.
- Chạy được với nhiều cấu hình (đọc từ evaluation/configs/*.yaml).
- Script vẽ biểu đồ (matplotlib) cho từng thực nghiệm để đưa vào khóa luận.
```
**Hoàn thành khi:** có bảng kết quả và biểu đồ cho cả 4 nhóm thực nghiệm.

---

## Giai đoạn 10 — Hoàn thiện
```
Thực hiện Giai đoạn 10:
- Rà soát bảo mật theo checklist trong CLAUDE.md, liệt kê điểm chưa đạt.
- Xử lý lỗi thân thiện ở frontend (mất kết nối LLM, MCP server tắt).
- Cập nhật README: cài đặt từ đầu trên máy mới, chạy demo, tài khoản mẫu.
- Script reset_demo.ps1: chạy lại SQL seed + seed_users để demo luôn từ trạng thái sạch.
- Kiểm tra lại toàn bộ test, ruff, build frontend.
```
**Hoàn thành khi:** máy khác clone về làm theo README chạy được; kịch bản demo chạy trơn tru 3 lần liên tiếp.
