# 06. Thiết kế RAG

## 1. Nguồn văn bản
Đặt PDF/DOCX vào `data/van_ban/`, tải lên qua trang quản trị (hoặc `scripts/ingest_folder.py` đọc file `data/van_ban/danh_muc.csv`).

> **Lưu ý (GĐ8):** `ingest_folder.py` là tiến trình riêng ghi thẳng vào ChromaDB. Nếu server `quy_che` đang chạy thì nó KHÔNG thấy vector mới (Chroma giữ chỉ mục trong RAM từng tiến trình, xem docs/02 mục 8) → chạy script khi quy_che đã tắt, hoặc khởi động lại quy_che sau khi nạp. Tải lên qua trang quản trị không gặp vấn đề này (quy_che tự lập chỉ mục).
Gợi ý nguồn: quy chế đào tạo, sổ tay sinh viên, quy định học phí, hướng dẫn đăng ký học phần, quy định xét tốt nghiệp của chính trường bạn (văn bản công khai); quy chế đào tạo trình độ đại học của Bộ GD&ĐT (kiểm tra số hiệu văn bản hiện hành).
Để thực nghiệm **phiên bản theo khóa**, cần ít nhất 2 phiên bản của cùng một văn bản (bản cũ áp dụng cho khóa cũ, bản mới cho khóa mới). Nếu trường không có, tạo một "bản sửa đổi giả lập" và ghi rõ trong khóa luận.

`danh_muc.csv`:
```csv
ten_tep,ten,loai,phien_ban,ap_dung_tu_khoa,ap_dung_den_khoa,ngay_hieu_luc
quy_che_2021.pdf,Quy chế đào tạo trình độ đại học,quy_che,2021,,21,2021-08-01
quy_che_2023.pdf,Quy chế đào tạo trình độ đại học,quy_che,2023,22,,2023-08-01
```

## 2. Pipeline lập chỉ mục (`backend/src/rag/`)
```
loader.py    → đọc PDF (pymupdf, giữ số trang) / DOCX (python-docx) → [(trang, text)]
cleaner.py   → bỏ header/footer lặp, số trang, ghép dòng bị ngắt, chuẩn hóa Unicode NFC
chunker.py   → chia đoạn (3 chiến lược, chọn theo van_ban.chien_luoc_chunk)
embedder.py  → sentence-transformers, chuẩn hóa vector, batch
indexer.py   → ghi doan_van_ban (SQL Server) + upsert ChromaDB (collection "quy_che")
              + làm mới chỉ mục BM25 trong bộ nhớ
keyword.py   → chỉ mục BM25 (rank-bm25) dựng từ doan_van_ban, tách từ tiếng Việt
retriever.py → hybrid search + lọc phiên bản + (tuỳ chọn) rerank
```

### Chiến lược chia đoạn
| Chiến lược | Cách làm | Ghi chú |
|---|---|---|
| `theo_dieu` (mặc định) | Nhận diện `Chương [IVXLC]+`, `Điều \d+\.`, khoản `^\d+\.`; mỗi Điều là 1 đoạn; Điều dài > `CHUNK_MAX_TOKENS` (512) thì tách theo Khoản | Đầu mỗi đoạn thêm tiền tố ngữ cảnh: `"{ten_van_ban} ({phien_ban}) – {chuong} – {dieu}\n"` |
| `co_dinh` | Cửa sổ 400 token, chồng lấn 60 | Mốc so sánh (baseline) |
| `ngu_nghia` | Tách câu, gộp câu liên tiếp khi độ tương đồng embedding > ngưỡng | Thực nghiệm thêm, làm sau cùng |

Văn bản không có cấu trúc Điều (thông báo, hướng dẫn) → tự động rơi về `co_dinh`.

### Metadata trong ChromaDB
```json
{"van_ban_id": 3, "doan_id": 120, "loai": "quy_che", "phien_ban": "2023",
 "ap_dung_tu": 22, "ap_dung_den": 99, "dieu": "Điều 12. Đăng ký học phần", "trang": 8}
```
`ap_dung_tu`/`ap_dung_den` là số nguyên 2 chữ số; NULL trong CSDL → 0 / 99 trong Chroma.

### Mô hình embedding
- Mặc định: `intfloat/multilingual-e5-base` (nhẹ, chạy CPU được). Lưu ý tiền tố `"query: "` cho câu hỏi và `"passage: "` cho đoạn văn bản.
- So sánh: `BAAI/bge-m3` (mạnh hơn, nặng hơn).
- Đổi mô hình = lập chỉ mục lại toàn bộ (collection riêng theo tên mô hình: `quy_che__{slug_model}`).

## 3. Truy xuất (`retriever.search(cau_hoi, ma_khoa, top_k)`)
1. `k = int(ma_khoa[1:])` (K22 → 22).
2. **Vector:** Chroma query top 20, `where = {"$and": [{"ap_dung_tu": {"$lte": k}}, {"ap_dung_den": {"$gte": k}}]}`.
3. **Từ khóa: BM25 trong Python** (`rank-bm25`, lớp `BM25Okapi`), top 20.
   - Kho đoạn: các `doan_van_ban` thuộc `van_ban` có `trang_thai = 'da_lap_chi_muc'` và phiên bản áp dụng cho khóa `k`
     (`(ap_dung_tu_khoa IS NULL OR ap_dung_tu_khoa <= k) AND (ap_dung_den_khoa IS NULL OR ap_dung_den_khoa >= k)`).
   - Tách từ: chuẩn hóa Unicode NFC → chữ thường → tách theo ký tự không phải chữ/số; giữ cả âm tiết 1–2 ký tự
     ("đi", "kỳ", "nợ") vì tiếng Việt có nhiều âm tiết ngắn mang nghĩa. Thêm bigram âm tiết (vd "học_lại") để bắt cụm từ.
   - Chỉ mục dựng trong bộ nhớ khi service khởi động và dựng lại sau mỗi lần lập chỉ mục/xóa văn bản
     (quy mô vài nghìn đoạn → dựng lại dưới 1 giây).
   - **Vì sao không dùng Full-Text Search của SQL Server:** bản Express mặc định không cài thành phần này, và bộ tách từ
     của nó không xử lý tốt âm tiết tiếng Việt. BM25 tự cài đặt thì độc lập với hệ quản trị CSDL, kiểm soát được cách tách từ,
     và là phương pháp chuẩn để so sánh trong các nghiên cứu về RAG.
4. **Hợp nhất RRF:** `score(d) = Σ 1 / (60 + rank_i(d))` trên 2 danh sách.
5. **Rerank (tuỳ chọn, `RERANK_ENABLED=true`):** cross-encoder `BAAI/bge-reranker-v2-m3` trên top 15.
6. Trả `top_k` đoạn, đánh số `so` = 1..top_k.
7. Cờ cấu hình cho thực nghiệm: `use_vector`, `use_keyword`, `use_version_filter`, `use_rerank`.

## 4. Sinh câu trả lời
Nằm trong vòng lặp Agent (LLM nhận kết quả tool `search_regulations`). System prompt bắt buộc trích dẫn `[so]`. Backend hậu kiểm: số trích dẫn trong câu trả lời phải nằm trong danh sách đoạn đã trả về; số lạ bị loại khỏi `citations` và ghi cảnh báo vào log (phục vụ đo "trích dẫn sai").

## 5. Kiểm thử
- `tests/rag/test_chunking.py`: văn bản mẫu giả lập (`tests/rag/fixtures/quy_che_mau.txt`, 3 trang có header/footer,
  số trang, dòng bị ngắt) → làm sạch đúng, mỗi Điều 1 đoạn, tiêu đề/chương/trang đúng, Điều dài tách theo Khoản,
  rơi về `co_dinh` khi không có Điều; loader PDF/DOCX; BM25.
- `tests/rag/test_retriever.py`: 2 phiên bản giả (2021 → ≤K21, 2023 → ≥K22) → K21 chỉ nhận bản cũ, K22 chỉ nhận bản mới,
  kiểm tra riêng từng nhánh (chỉ vector / chỉ BM25); lập chỉ mục lại không trùng; RRF; rerank.
  Đã thử "đột biến" (bỏ bộ lọc phiên bản) → test thất bại, chứng tỏ test có ý nghĩa.
- `tests/rag/test_quy_che_server.py`: tool qua giao thức MCP, bọc `<tai_lieu>`, chặn thẻ giả trong tài liệu, lỗi.
- Test dùng `HashingEmbedder` (embedding giả, tất định) + Chroma trong thư mục tạm + CSDL rollback → không cần tải mô hình.

## 6. Quyết định cài đặt (Giai đoạn 4)
- **Làm sạch:** header/footer = dòng ở 2 dòng đầu/cuối trang lặp lại ≥ 50% số trang (so sánh sau khi thay chữ số bằng `#`),
  chỉ áp dụng khi ≥ 3 trang. Không nối dòng vào/qua dòng cấu trúc (Chương, Điều, khoản `1.`, điểm `a)`, gạch đầu dòng).
- **Nhận diện Điều chống nhầm câu dẫn chiếu:** tiêu đề phải dạng `Điều <số>.`/`Điều <số>:` và số Điều tăng dần
  (lớn hơn Điều trước tối đa 3) — "Điều 6 của Quy chế này" bị ngắt dòng không thành Điều mới.
- **Đếm token** bằng tokenizer của chính mô hình embedding (e5/bge-m3 cắt ở 512 token → đoạn không vượt quá).
  Phần mở đầu (trước Điều 1) chia theo `co_dinh`. Khoản quá dài → cửa sổ cố định, chồng lấn ≤ 1/4 cửa sổ.
- `ngu_nghia`: để Giai đoạn 8; hiện rơi về `theo_dieu` (có cảnh báo trong log).
- **Văn bản nhận diện theo (ten, loai, phien_ban)**; lập chỉ mục lại → xóa đoạn + vector cũ (idempotent).
  Ghi CSDL (flush) → upsert Chroma → commit; vector "mồ côi" (commit lỗi) bị retriever bỏ qua vì chỉ nhận vector có
  đoạn thuộc văn bản `da_lap_chi_muc`. Lỗi → `van_ban.trang_thai = 'loi'`, `van_ban.loi` ghi lý do.
- **Lọc phiên bản 2 lớp:** điều kiện `where` trong Chroma + kiểm tra lại ở CSDL khi đổi vector_id → doan_id.
- **BM25 tự làm mới:** mỗi lần tìm kiểm tra "dấu vết" `COUNT(van_ban), MAX(updated_at), COUNT(doan_van_ban)`;
  đổi thì dựng lại (cache theo khóa). Server `quy_che` đang chạy thấy ngay văn bản mới nạp bằng script.
- **`ma_khoa`** nhận `K22`/`k22`/`22`; sai định dạng → `MA_KHOA_KHONG_HOP_LE`.
- Kết quả `search_regulations` có thêm `van_ban_id` (để gọi `get_article`).
- Công cụ dòng lệnh: `scripts/ingest_folder.py` (in bảng thời gian đọc/chia/embedding và số đoạn),
  `scripts/try_search.py` (in hạng vector / BM25 / điểm RRF để gỡ lỗi; các cờ `--no-vector`, `--no-keyword`,
  `--no-filter`, `--rerank`).
