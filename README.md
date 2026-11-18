# tro_ly_hoc_vu — Trợ lý học vụ AI Agent (MCP + RAG)

**Đề tài:** Nghiên cứu giao thức MCP và kỹ thuật RAG, ứng dụng xây dựng trợ lý ảo AI Agent hỗ trợ sinh viên tra cứu quy chế và thực hiện thủ tục học vụ.

Bộ thiết kế này dùng để làm dự án bằng **VS Code + Claude Code (Claude CLI) + MySQL**. Code sẽ do Claude Code sinh theo từng giai đoạn dựa trên tài liệu trong `docs/`.

## Bộ thiết kế gồm gì
| File | Nội dung |
|---|---|
| `CLAUDE.md` | "Bộ nhớ dự án": Claude Code tự đọc mỗi lần khởi động (công nghệ, cấu trúc, quy ước, quy tắc bảo mật) |
| `docs/01-dac-ta-yeu-cau.md` | Tác nhân, yêu cầu chức năng / phi chức năng, kịch bản demo |
| `docs/02-kien-truc.md` | Kiến trúc, luồng xử lý, vòng lặp Agent, system prompt, sự kiện SSE |
| `docs/03-co-so-du-lieu.md` | Hướng dẫn cài MySQL, sơ đồ CSDL, quy tắc nghiệp vụ, tài khoản mẫu |
| `docs/04-api.md` | Đặc tả API của qlsv_api và assistant_api |
| `docs/05-mcp-servers.md` | 4 MCP server và 16 công cụ |
| `docs/06-rag.md` | Pipeline RAG: chia đoạn theo Điều, hybrid search, lọc phiên bản theo khóa |
| `docs/07-ke-hoach-va-prompt.md` | **10 giai đoạn + câu lệnh dán sẵn cho Claude** |
| `docs/08-giao-dien.md` | Thiết kế giao diện |
| `docs/09-danh-gia.md` | 4 nhóm thực nghiệm cho Chương 4 |
| `database/*.sql` | Script tạo 2 CSDL MySQL + dữ liệu mẫu (chạy theo thứ tự số) |
| `.claude/commands/` | Lệnh tắt: `/giai-doan <số>`, `/kiem-tra-bao-mat` |
| `.env.example` | Mẫu cấu hình |
| `docker-compose.yml` | Tuỳ chọn: chạy MySQL bằng Docker |

## Bắt đầu
1. **Cài đặt:** Python 3.11+, Node.js 20+, Git, MySQL 8 + Workbench, VS Code, Claude Code.
2. **CSDL:** làm theo `docs/03-co-so-du-lieu.md` (sửa `my.ini`, tạo user `troly`, chạy 4 file SQL).
3. **Cấu hình:** sao chép `.env.example` thành `.env`, điền mật khẩu MySQL, chuỗi bí mật, `LLM_MODEL` và khóa API.
4. **Git:** `git init` → `git add .` → `git commit -m "Khởi tạo bộ thiết kế"`.
5. **Làm việc với Claude:** mở thư mục trong VS Code → Terminal → `claude` → gõ `/giai-doan 1`.
6. Lặp lại cho các giai đoạn 2 → 10 theo `docs/07-ke-hoach-va-prompt.md`. Commit sau mỗi giai đoạn, gõ `/clear` trước giai đoạn mới.

## Kiến trúc tóm tắt
```
Web (React) ──► assistant_api :8000 ──► LLM (LiteLLM)
                     │
                     └─► MCP client ──► dao_tao :9101 ┐
                                    ├─► ctsv    :9102 ├─► qlsv_api :8001 ─► MySQL qlsv
                                    ├─► tai_chinh:9103┘
                                    └─► quy_che :9104 ─► RAG ─► ChromaDB + MySQL assistant
```

## Mẹo dùng Claude Code hiệu quả
- Bật **Plan mode** (Shift+Tab) để duyệt kế hoạch trước khi Claude sửa file.
- Mỗi giai đoạn một phiên làm việc; dùng `/clear` để không bị tràn ngữ cảnh.
- Khi muốn đổi thiết kế: bảo Claude cập nhật file trong `docs/` trước, rồi mới sửa code. Tài liệu luôn khớp code thì viết khóa luận rất nhanh.
- Lưu lại các câu trả lời giải thích của Claude về "vì sao thiết kế như vậy": đó là nguyên liệu cho Chương 3.
- Đừng để Claude tự commit hay xóa dữ liệu; tự kiểm tra rồi mới commit.
