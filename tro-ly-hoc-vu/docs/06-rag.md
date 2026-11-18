# 06. Thiết kế RAG

## 1. Nguồn văn bản
Đặt PDF/DOCX vào `data/van_ban/`, tải lên qua trang quản trị (hoặc `scripts/ingest_folder.py` đọc file `data/van_ban/danh_muc.csv`).
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
indexer.py   → ghi doan_van_ban (MySQL) + upsert ChromaDB (collection "quy_che")
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
`ap_dung_tu`/`ap_dung_den` là số nguyên 2 chữ số; NULL trong MySQL → 0 / 99 trong Chroma.

### Mô hình embedding
- Mặc định: `intfloat/multilingual-e5-base` (nhẹ, chạy CPU được). Lưu ý tiền tố `"query: "` cho câu hỏi và `"passage: "` cho đoạn văn bản.
- So sánh: `BAAI/bge-m3` (mạnh hơn, nặng hơn).
- Đổi mô hình = lập chỉ mục lại toàn bộ (collection riêng theo tên mô hình: `quy_che__{slug_model}`).

## 3. Truy xuất (`retriever.search(cau_hoi, ma_khoa, top_k)`)
1. `k = int(ma_khoa[1:])` (K22 → 22).
2. **Vector:** Chroma query top 20, `where = {"$and": [{"ap_dung_tu": {"$lte": k}}, {"ap_dung_den": {"$gte": k}}]}`.
3. **Từ khóa:** MySQL
   ```sql
   SELECT d.id, MATCH(d.noi_dung) AGAINST (:q IN NATURAL LANGUAGE MODE) AS diem
   FROM doan_van_ban d JOIN van_ban v ON v.id = d.van_ban_id
   WHERE v.trang_thai = 'da_lap_chi_muc'
     AND (v.ap_dung_tu_khoa IS NULL OR v.ap_dung_tu_khoa <= :k)
     AND (v.ap_dung_den_khoa IS NULL OR v.ap_dung_den_khoa >= :k)
     AND MATCH(d.noi_dung) AGAINST (:q IN NATURAL LANGUAGE MODE)
   ORDER BY diem DESC LIMIT 20;
   ```
4. **Hợp nhất RRF:** `score(d) = Σ 1 / (60 + rank_i(d))` trên 2 danh sách.
5. **Rerank (tuỳ chọn, `RERANK_ENABLED=true`):** cross-encoder `BAAI/bge-reranker-v2-m3` trên top 15.
6. Trả `top_k` đoạn, đánh số `so` = 1..top_k.
7. Cờ cấu hình cho thực nghiệm: `use_vector`, `use_keyword`, `use_version_filter`, `use_rerank`.

## 4. Sinh câu trả lời
Nằm trong vòng lặp Agent (LLM nhận kết quả tool `search_regulations`). System prompt bắt buộc trích dẫn `[so]`. Backend hậu kiểm: số trích dẫn trong câu trả lời phải nằm trong danh sách đoạn đã trả về; số lạ bị loại khỏi `citations` và ghi cảnh báo vào log (phục vụ đo "trích dẫn sai").

## 5. Kiểm thử
- `tests/rag/test_chunker.py`: văn bản mẫu có Chương/Điều/Khoản → số đoạn và tiêu đề đúng.
- `tests/rag/test_retriever.py`: dữ liệu nhỏ 2 phiên bản → K21 chỉ nhận đoạn bản cũ, K22 chỉ nhận bản mới.
