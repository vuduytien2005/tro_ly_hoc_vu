# tro_ly_hoc_vu — Trợ lý học vụ AI Agent (MCP + RAG)

**Đề tài:** Nghiên cứu giao thức MCP và kỹ thuật RAG, ứng dụng xây dựng trợ lý ảo AI Agent hỗ trợ sinh viên tra cứu quy chế và thực hiện thủ tục học vụ.

Bộ thiết kế này dùng để làm dự án bằng **VS Code + Claude Code (Claude CLI) + SQL Server (SSMS)**. Code sẽ do Claude Code sinh theo từng giai đoạn dựa trên tài liệu trong `docs/`.

## Bộ thiết kế gồm gì
| File | Nội dung |
|---|---|
| `CLAUDE.md` | "Bộ nhớ dự án": Claude Code tự đọc mỗi lần khởi động (công nghệ, cấu trúc, quy ước, quy tắc bảo mật) |
| `docs/01-dac-ta-yeu-cau.md` | Tác nhân, yêu cầu chức năng / phi chức năng, kịch bản demo |
| `docs/02-kien-truc.md` | Kiến trúc, luồng xử lý, vòng lặp Agent, system prompt, sự kiện SSE |
| `docs/03-co-so-du-lieu.md` | Hướng dẫn cài SQL Server, sơ đồ CSDL, quy tắc nghiệp vụ, tài khoản mẫu |
| `docs/04-api.md` | Đặc tả API của qlsv_api và assistant_api |
| `docs/05-mcp-servers.md` | 5 MCP server (4 có sẵn + `thu_vien` thêm khi demo) và 21 công cụ |
| `docs/06-rag.md` | Pipeline RAG: chia đoạn theo Điều, hybrid search, lọc phiên bản theo khóa |
| `docs/07-ke-hoach-va-prompt.md` | **10 giai đoạn + câu lệnh dán sẵn cho Claude** |
| `docs/08-giao-dien.md` | Thiết kế giao diện |
| `docs/09-danh-gia.md` | 4 nhóm thực nghiệm cho Chương 4 |
| `docs/10-ra-soat-bao-mat.md` | Rà soát 6 quy tắc bảo mật, hạn chế đã biết |
| `database/*.sql` | Script T-SQL tạo 2 CSDL SQL Server + dữ liệu mẫu (chạy theo thứ tự số) |
| `backend/` | Code Python (FastAPI, MCP, RAG) — sinh dần theo từng giai đoạn |
| `.claude/commands/` | Lệnh tắt: `/giai-doan <số>`, `/kiem-tra-bao-mat` |
| `.env.example` | Mẫu cấu hình |

## Cài đặt trên máy mới (Windows)
**Cần có sẵn:** Python 3.11+, Node.js 20+, Git, SQL Server (Express trở lên) + SSMS, ODBC Driver 18 for SQL Server, `sqlcmd`.

```powershell
git clone <địa chỉ repo> tro-ly-hoc-vu
cd tro-ly-hoc-vu\backend
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -DbServer "localhost\SQLEXPRESS01"
```
`setup.ps1` làm lần lượt (chạy lại an toàn, bước đã xong thì bỏ qua):
1. Kiểm tra Python, Node.js, sqlcmd, ODBC Driver 18.
2. Tạo `.env` từ `.env.example`, **tự sinh** `JWT_SECRET`, `INTERNAL_API_TOKEN` ngẫu nhiên (hệ thống từ chối khởi động nếu còn chuỗi mẫu — xem `docs/10`).
3. Chạy 4 file `database/01..04` (chỉ khi CSDL chưa có; `-TaoLaiCsdl` để xóa và tạo lại).
4. Tạo `backend\.venv`, `pip install -e ".[dev]"` (`-Eval` để cài thêm gói thực nghiệm).
5. Tạo 6 tài khoản demo (`seed_users.py`).
6. `npm ci` cho web.
7. Nếu chưa có văn bản quy chế: hỏi có nạp **bộ quy chế giả lập** `evaluation/corpus_demo` không (`-VanBanMau` để nạp luôn; lần đầu tải mô hình embedding ~1,1 GB). Văn bản thật (PDF/DOCX) nạp ở trang **Tài liệu** của quản trị viên.

Sau đó **tự điền khóa API** vào `.env` (`ANTHROPIC_API_KEY=...`, hoặc đổi `LLM_MODEL` sang nhà cung cấp khác). **Miễn phí:** tạo khóa ở https://aistudio.google.com/apikey rồi đặt `LLM_MODEL=gemini/gemini-3.5-flash-lite`, `GEMINI_API_KEY=...`, `LLM_RATE_LIMIT_WAIT_SECONDS=90` (gói miễn phí giới hạn 15 lượt/phút; hệ thống tự chờ rồi gọi lại). Không có khóa thì mọi thứ vẫn chạy, chỉ trợ lý chưa trả lời được (web hiện banner đỏ "Trợ lý chưa sẵn sàng").

**Demo trước hội đồng:** đặt `CHE_DO_TRINH_BAY=true` trong `.env` (rồi chạy lại `run_all.ps1`) để trang chat có công tắc **"Chế độ trình bày"**: bảng "Bên trong Agent" (lượt gọi công cụ, tham số hệ thống tự điền), câu hỏi soạn sẵn, phóng chữ. Mặc định `false`.

**Ổ C ít chỗ trống?** Mô hình Hugging Face (embedding ~1,1 GB; reranker, bge-m3 cho TN1 R5/R6 ~2,2 GB mỗi mô hình) mặc định lưu ở `%USERPROFILE%\.cache\huggingface`. Đặt cache sang ổ khác rồi mở lại terminal: `setx HF_HOME D:\hf-cache` (có thể chép thư mục `hub\models--...` đã tải sang `D:\hf-cache\hub\` để khỏi tải lại).

## Chạy hệ thống
```powershell
cd backend; .\scripts\run_all.ps1          # qlsv_api, 5 MCP server (gồm thu_vien :9105), assistant_api — tắt: .\scripts\run_all.ps1 -Stop
cd web; npm run dev                         # mở http://localhost:5173
python scripts\demo_check.py                # (thư mục backend, venv bật) kiểm tra nhanh, không tốn tiền
```
- Vite chuyển `/api/*` và `/health` sang `assistant_api` (`127.0.0.1:8000`), trình duyệt chỉ nói chuyện với cổng 5173.
- Kiểm tra code: `cd backend; pytest -q` · `cd web; npm test; npm run build`.

### Tài khoản demo
| Vai trò | Email | Mật khẩu | Ghi chú |
|---|---|---|---|
| Sinh viên | `sv22001@truong.example` | `Sv@123456` | K22, dùng cho demo 1–5, 7–9 |
| Sinh viên | `sv21001@truong.example` | `Sv@123456` | K21, demo 6 |
| Sinh viên | `sv22002@truong.example`, `sv23001@…`, `sv22003@…` | `Sv@123456` | |
| Quản trị | `admin@truong.example` | `Admin@123456` | trang Tài liệu, MCP & quyền, Nhật ký, Thống kê |

## Kịch bản demo (docs/01 mục 6)
Trước buổi demo: `.\scripts\reset_demo.ps1` → `.\scripts\run_all.ps1` → `python scripts\demo_check.py` (tất cả **ĐẠT**) → `npm run dev`.

| # | Đăng nhập | Thao tác | Kết quả mong đợi |
|---|---|---|---|
| 1 | sv22001 | Hỏi *"Em bị F môn Cơ sở dữ liệu thì có phải học lại không?"* | Chip "Tra cứu quy chế", câu trả lời có số trích dẫn [1]; bấm số → xem đoạn quy chế (bản K22). |
| 2 | sv22001 | *"Em còn thiếu gì để tốt nghiệp?"* | Chip tiến độ tốt nghiệp + quy chế; liệt kê tín chỉ/môn còn thiếu. |
| 3 | sv22001 | *"Đăng ký giúp em lớp học lại Cơ sở dữ liệu vào thứ 2"* | Thẻ xác nhận **IT004.02** có đếm ngược 10 phút → bấm **Xác nhận** → báo thành công. |
| 4 | sv22001 | (cùng hội thoại) *"Đăng ký thêm SE105.02"* → Xác nhận | Báo **trùng lịch** với IT004.02, không đăng ký. |
| 5 | sv22001 | *"Cho em xem điểm của SV22002"* | Từ chối: chỉ xem được dữ liệu của chính em (LLM không chọn được `ma_sv`). |
| 6 | sv21001 | *"Em muốn xin giấy xác nhận sinh viên để làm hồ sơ vay vốn"* → Xác nhận | Tạo đơn; mở **Thủ tục của em** thấy đơn mới. |
| 7 | admin → sv22001 | Admin: **MCP & quyền** → tắt `register_course`. SV: *"Đăng ký giúp em lớp IT004.02"* | Trợ lý báo chức năng **tạm dừng**; Admin → **Nhật ký** thấy lượt bị từ chối. |
| 8 | admin → sv22001 | Admin: **MCP & quyền** → **Thêm MCP server** `thu_vien`, `http://127.0.0.1:9105/mcp` → Kiểm tra kết nối → Lưu → bật `get_borrowed_books`, `renew_book`. SV: *"Gia hạn giúp em cuốn sách sắp hết hạn"* | Thẻ **"Gia hạn sách (muon_id: 1)"** → Xác nhận → hạn trả 11/12/2026. Server Thư viện được thêm trên trang MCP & quyền khi demo, không sửa code trợ lý. |
| 9 | sv22001 | *"Lập kế hoạch học kỳ tới rồi đăng ký cả gói giúp em"* | Chip "Đang lập kế hoạch học kỳ tới"; trợ lý nêu gói + lý do loại SE105 (đang học), SE202 (lớp đầy); **một** thẻ liệt kê từng lớp → Xác nhận → đăng ký cả gói. Sau reset: IT004.02 + SE201.01 (6 tín chỉ); sau demo 3: chỉ còn SE201.01. |

**Reset giữa các lần demo** (demo 3–4 làm đổi dữ liệu, demo 7 tắt công cụ):
```powershell
cd backend; .\scripts\reset_demo.ps1        # QLSV về mẫu, xóa hội thoại/nhật ký, bật lại công cụ, đặt lại mật khẩu demo
                                            # GIỮ văn bản đã lập chỉ mục. Service không cần tắt; trên web bấm F5.
.\scripts\reset_demo.ps1 -ChiQlsv           # chỉ dữ liệu QLSV
python scripts\demo_check.py --llm --lan 3  # chạy tự động demo 1–9 ba lần liên tiếp (TỐN TIỀN API), reset giữa các lần
```

## Xử lý sự cố
| Hiện tượng | Cách xử lý |
|---|---|
| Service không khởi động, báo `JWT_SECRET ... phải là chuỗi ngẫu nhiên` | Chạy lại `setup.ps1` (tự sinh) hoặc tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `Login timeout` / `Cannot open server` khi chạy SQL | `DB_SERVER` trong `.env` phải giống ô *Server name* của SSMS; bật dịch vụ SQL Server (SQLEXPRESS01) trong *Services*. |
| `Data source name not found` | Chưa cài **ODBC Driver 18 for SQL Server**. |
| Web hiện banner vàng *"Một số chức năng đang gián đoạn"* | MCP server tương ứng bị tắt/lỗi: xem cửa sổ của nó, chạy lại `run_all.ps1`. Trợ lý vẫn trả lời các câu khác; server sống lại thì tự hết sau ≤ 30 giây. |
| Banner đỏ *"Trợ lý chưa sẵn sàng"* | Chưa có khóa API trong `.env` (`ANTHROPIC_API_KEY`), sửa xong chạy lại `run_all.ps1`. |
| Banner đỏ *"Mất kết nối máy chủ trợ lý"* | `assistant_api` (cổng 8000) chưa chạy. |
| Lỗi giữa câu trả lời (mô hình quá tải, mất mạng) | Bấm **Thử lại** dưới thông báo lỗi để gửi lại câu hỏi. |
| Hỏi quy chế mà trợ lý nói không tìm thấy | Chưa có văn bản: admin → **Tài liệu** tải PDF/DOCX, hoặc `setup.ps1 -VanBanMau`. Nếu dùng `scripts/ingest_folder.py` thì phải tắt server `quy_che` trước. |
| Demo 3 báo "đã đăng ký rồi" / demo 7 vẫn tạm dừng | Quên reset: `.\scripts\reset_demo.ps1`. |
| Cổng 8000/9101… đang bị chiếm | `.\scripts\run_all.ps1 -Stop` rồi chạy lại. |

Hạn chế đã biết và kết quả rà soát bảo mật: `docs/10-ra-soat-bao-mat.md`.

## Phát triển cùng Claude Code
Mở thư mục trong VS Code → Terminal → `claude` → `/giai-doan <số>` theo `docs/07-ke-hoach-va-prompt.md` (commit sau mỗi giai đoạn, `/clear` trước giai đoạn mới); `/kiem-tra-bao-mat` để rà soát 6 quy tắc bảo mật.

## Thực nghiệm (Chương 4)
```powershell
# Từ thư mục gốc, venv backend đã kích hoạt; không cần bật service
pip install -e "backend[dev,eval]"
python evaluation\run_rag_retrieval.py      # TN1 truy xuất (không gọi LLM, miễn phí)
python evaluation\run_agent.py --dry-run    # kiểm tra đường ống TN3 bằng LLM giả (miễn phí)
python evaluation\run_agent.py --limit 10   # TN3 thật (tốn tiền API; script in token + chi phí)
python evaluation\run_security.py           # TN4;  python evaluation\run_rag_answer.py  # TN2
python evaluation\plot_results.py           # biểu đồ PNG cho lượt chạy mới nhất
```
Kết quả ở `evaluation/results/<thời gian>_<tn>/` (`bang.md`, `chi_tiet.csv`, `*.png`). Chi tiết, cách tính chỉ số và lý do thiết kế: `docs/09-danh-gia.md`.

## Kiến trúc tóm tắt
```
Web (React) ──► assistant_api :8000 ──► LLM (LiteLLM)
                     │
                     └─► MCP client ──► dao_tao :9101 ┐
                                    ├─► ctsv    :9102 ├─► qlsv_api :8001 ─► SQL Server tlhv_qlsv
                                    ├─► tai_chinh:9103┘
                                    ├─► quy_che :9104 ─► RAG ─► ChromaDB + BM25 + SQL Server tlhv_assistant
                                    └─► thu_vien :9105 ─► qlsv_api (thêm trên trang MCP & quyền khi demo)
```

## Mẹo dùng Claude Code hiệu quả
- Bật **Plan mode** (Shift+Tab) để duyệt kế hoạch trước khi Claude sửa file.
- Mỗi giai đoạn một phiên làm việc; dùng `/clear` để không bị tràn ngữ cảnh.
- Khi muốn đổi thiết kế: bảo Claude cập nhật file trong `docs/` trước, rồi mới sửa code. Tài liệu luôn khớp code thì viết khóa luận rất nhanh.
- Lưu lại các câu trả lời giải thích của Claude về "vì sao thiết kế như vậy": đó là nguyên liệu cho Chương 3.
- Đừng để Claude tự commit hay xóa dữ liệu; tự kiểm tra rồi mới commit.
