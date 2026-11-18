# web — Giao diện trợ lý học vụ

React 19 + Vite + TypeScript + TailwindCSS 4 + React Router + TanStack Query.

```powershell
npm install
npm run dev     # http://localhost:5173 (proxy /api, /health -> assistant_api :8000)
npm test        # vitest: bộ tách SSE, trích dẫn, đồng hồ đếm ngược
npm run build   # kiểm tra kiểu + đóng gói vào dist/
```

Cấu trúc `src/`:
- `lib/` — `api.ts` (fetch + JWT + lỗi `{detail, code}`), `sse.ts` (đọc SSE từ POST), `auth.tsx`, `format.ts`, `types.ts`
- `components/` — `StudentLayout` (sidebar), `chat/*` (câu trả lời + trích dẫn, chip công cụ, thẻ xác nhận, đánh giá, ô nhập)
- `pages/` — `LoginPage`, `ChatPage`, `ProceduresPage` ("Thủ tục của em"), `AdminPlaceholder` (GĐ8)
