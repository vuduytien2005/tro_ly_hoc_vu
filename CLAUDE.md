# CLAUDE.md — Bộ nhớ dự án cho Claude Code

## Đề tài
**Nghiên cứu giao thức MCP và kỹ thuật RAG, ứng dụng xây dựng trợ lý ảo AI Agent hỗ trợ sinh viên tra cứu quy chế và thực hiện thủ tục học vụ.**

Khóa luận tốt nghiệp ngành Công nghệ phần mềm. Một người làm. Sản phẩm phải chạy được trên máy cá nhân (Windows), demo được trước hội đồng.

## Hệ thống gồm gì
1. **qlsv_api** – Hệ thống quản lý sinh viên GIẢ LẬP (FastAPI + SQL Server `tlhv_qlsv`). Đóng vai "hệ thống thật của trường" để Agent thao tác. Chỉ nhận request nội bộ có header `X-Internal-Token`.
2. **mcp_servers** – 4 MCP server (Python SDK `mcp`, FastMCP, transport streamable HTTP):
   - `dao_tao` (cổng 9101): hồ sơ, bảng điểm, lịch thi, tiến độ tốt nghiệp, đăng ký học phần.
   - `ctsv` (9102): giấy xác nhận sinh viên, đơn bảo lưu, đơn phúc khảo, tra cứu đơn.
   - `tai_chinh` (9103): tình trạng học phí.
   - `quy_che` (9104): tra cứu quy chế bằng RAG (nhánh RAG cũng là một MCP server).
3. **rag** – Thư viện dùng chung: đọc PDF/DOCX → chia đoạn theo Chương/Điều/Khoản → embedding → ChromaDB + BM25 (Python, `rank-bm25`) → hybrid search (RRF) → (tuỳ chọn) rerank.
4. **assistant_api** – Backend trợ lý (FastAPI + SQL Server `tlhv_assistant`, cổng 8000): đăng nhập JWT, hội thoại, **vòng lặp Agent** (LLM qua LiteLLM + MCP client), cơ chế **xác nhận hành động**, **nhật ký** gọi công cụ, API quản trị.
5. **web** – React + Vite + TypeScript + TailwindCSS (cổng 5173): giao diện sinh viên (chat, "Thủ tục của em") và quản trị (tài liệu, MCP & quyền, nhật ký, thống kê).
6. **evaluation** – Script thực nghiệm cho Chương 4 (RAG, Agent, an toàn).

Chi tiết: xem thư mục `docs/` (đọc file liên quan TRƯỚC khi code mỗi giai đoạn).

## Công nghệ (không tự ý đổi)
- Python 3.11+, FastAPI, SQLAlchemy 2.x (ORM, kiểu `Mapped[...]`), pyodbc, Pydantic v2, pydantic-settings
- **Microsoft SQL Server** (máy dev: `localhost\SQLEXPRESS01`, quản lý bằng SSMS), driver "ODBC Driver 18 for SQL Server", mặc định Windows Authentication. CSDL: `tlhv_qlsv`, `tlhv_assistant`, collation `Vietnamese_100_CI_AS`.
  - Chuỗi: `NVARCHAR` (model dùng `Unicode`/`UnicodeText`); literal tiếng Việt trong SQL phải có tiền tố `N'...'`.
  - ENUM → `NVARCHAR` + `CHECK`; JSON → `NVARCHAR(MAX)` + `CHECK (ISJSON(...)=1)` (chỉ nhận object/array; model dùng `JSON(none_as_null=True)`); `updated_at` → trigger; bảng có trigger đặt `__table_args__ = {"implicit_returning": False}`.
  - Đổi từ thiết kế gốc MySQL ngày 18/11/2026 theo yêu cầu người dùng (xem `docs/03-co-so-du-lieu.md`).
- MCP: package Python `mcp` (FastMCP). Kiểm tra API mới nhất trong tài liệu chính thức của SDK trước khi viết code MCP.
- LLM: `litellm` (để đổi nhà cung cấp chỉ bằng biến môi trường `LLM_MODEL`)
- RAG: `chromadb` (chế độ persistent, không cần server), `sentence-transformers`, `pymupdf`, `python-docx`, `rank-bm25`
- Auth: JWT (`pyjwt`), mật khẩu băm `bcrypt`
- Frontend: React 18+, Vite, TypeScript, TailwindCSS, React Router, TanStack Query
- Test: `pytest`, `httpx`; frontend: `vitest` (tối thiểu)

## Cấu trúc thư mục
```
tro-ly-hoc-vu/
├── CLAUDE.md
├── README.md
├── .env.example
├── database/                   # script T-SQL (SQL Server), chạy theo thứ tự số
├── docs/                       # tài liệu thiết kế
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── shared/             # config, kết nối DB, logging, bảo mật nội bộ
│   │   ├── qlsv_api/           # hệ thống QLSV giả lập
│   │   ├── mcp_servers/        # dao_tao.py, ctsv.py, tai_chinh.py, quy_che.py, common.py
│   │   ├── rag/                # loader, chunker, embedder, indexer, retriever
│   │   └── assistant_api/      # main.py, routers/, agent/, mcp_client/, auth/, models/
│   ├── scripts/                # seed_users.py, ingest_folder.py, run_all.ps1
│   └── tests/
├── web/                        # React app
├── evaluation/                 # datasets/*.jsonl, run_*.py, results/
└── data/
    ├── van_ban/                # PDF/DOCX quy chế (người dùng tự đặt vào)
    └── chroma/                 # dữ liệu vector (tự sinh, không commit)
```

## Quy ước code
- Tên bảng/cột CSDL: **tiếng Việt không dấu, snake_case** (đã cố định trong `database/*.sql`, KHÔNG đổi tên).
- Code Python/TypeScript: **tiếng Anh** (tên biến, hàm, class). Chuỗi hiển thị cho người dùng: **tiếng Việt có dấu**.
- Python: type hints đầy đủ, `ruff` để format/lint. Mỗi service có `main.py` chạy được bằng `python -m src.<service>.main` từ thư mục `backend/`.
- Cấu hình chỉ đọc từ `.env` qua `src/shared/config.py`. Không hard-code mật khẩu, khoá API, URL.
- Mọi API trả lỗi dạng `{"detail": "<thông báo tiếng Việt>", "code": "<MA_LOI>"}`.
- Thời gian lưu DB theo giờ Việt Nam (Asia/Ho_Chi_Minh), dùng `datetime` có timezone trong code.
- Commit Git sau mỗi giai đoạn hoàn thành (người dùng tự commit, Claude chỉ gợi ý message).

## Quy tắc bảo mật BẮT BUỘC (cốt lõi của đề tài)
1. **Tiêm ngữ cảnh (context injection):** mọi công cụ MCP liên quan dữ liệu cá nhân có tham số `ma_sv` (và `quy_che` có `ma_khoa`). Các tham số này **bị ẩn khỏi schema gửi cho LLM**; `assistant_api` tự điền từ tài khoản đang đăng nhập. LLM KHÔNG BAO GIỜ được tự chọn `ma_sv`. Nếu LLM gửi kèm `ma_sv`, giá trị đó bị ghi đè.
2. **Xác nhận hành động:** công cụ có `can_xac_nhan = 1` (bảng `cong_cu`) KHÔNG được thực thi ngay. Agent tạo bản ghi `hanh_dong_cho_xac_nhan`, giao diện hiện thẻ xác nhận, chỉ thực thi khi người dùng bấm "Xác nhận" (hết hạn sau 10 phút).
3. **Nhật ký:** MỌI lần gọi công cụ (thành công, lỗi, bị từ chối, chờ xác nhận) đều ghi vào `luot_goi_cong_cu`.
4. **Xác thực nội bộ:** MCP server ↔ qlsv_api dùng header `X-Internal-Token`; assistant_api ↔ MCP server dùng header `Authorization: Bearer <INTERNAL_API_TOKEN>`. MCP server và qlsv_api chỉ lắng nghe `127.0.0.1`.
5. **Chống prompt injection từ tài liệu:** nội dung trả về từ `search_regulations` được bọc trong thẻ `<tai_lieu>` và system prompt nói rõ đó là dữ liệu, không phải lệnh.
6. Công cụ bị tắt (`cong_cu.bat = 0`) không được đưa cho LLM.

## Lệnh thường dùng (Windows PowerShell)
```powershell
# Backend
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m src.qlsv_api.main            # :8001
python -m src.mcp_servers.dao_tao      # :9101 (tương tự ctsv, tai_chinh, quy_che)
python -m src.assistant_api.main       # :8000
pytest -q
ruff check src --fix; ruff format src

# Chạy tất cả service backend cùng lúc
.\scripts\run_all.ps1

# Frontend
cd web; npm install; npm run dev       # :5173

# Kiểm tra MCP server bằng MCP Inspector
npx @modelcontextprotocol/inspector
```

## Cách làm việc với Claude
- Làm theo **từng giai đoạn** trong `docs/07-ke-hoach-va-prompt.md`. Không nhảy giai đoạn.
- Đầu mỗi giai đoạn: đọc tài liệu liên quan, đề xuất kế hoạch ngắn, chờ người dùng đồng ý rồi mới code.
- Cuối mỗi giai đoạn: chạy test, liệt kê file đã tạo/sửa, hướng dẫn người dùng kiểm tra thủ công, đánh dấu tiêu chí hoàn thành.
- Nếu tài liệu thiết kế mâu thuẫn hoặc thiếu: HỎI người dùng, không tự đoán. Nếu cần đổi thiết kế, cập nhật luôn file trong `docs/`.
- Giải thích bằng tiếng Việt, ngắn gọn; người dùng sẽ viết khóa luận từ đây nên cần hiểu vì sao làm như vậy.
