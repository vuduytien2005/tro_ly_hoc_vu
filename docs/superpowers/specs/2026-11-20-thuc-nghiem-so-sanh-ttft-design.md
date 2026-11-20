# Thiết kế: Thực nghiệm so sánh + đo thời gian đến token đầu tiên (ý tưởng 5)

Ngày: 20/11/2026. Người quyết định: người dùng (chủ đề tài). Cỡ: thay đổi nhỏ (thiết kế ngắn).

## Mục đích
Bổ sung minh chứng cho Chương 4:
- so sánh **mô tả công cụ đầy đủ và tối giản** (TN3);
- so sánh **có và không có reranker** (TN1);
- đo **NF-01**: token đầu tiên < 5 giây (docs/01).

Hiện thực nghiệm chỉ đo tổng thời gian trả lời. Cấu hình `agent_gemini_toi_gian`, `rag_R5`, `rag_R6` có sẵn nhưng chưa chạy lần nào.

## Mục tiêu / không làm / tránh
- **Mục tiêu**
  - Mọi lượt chạy TN2/TN3 có thêm 2 mốc thời gian.
  - TN3 có bảng so sánh theo từng `loai` kịch bản.
  - TN1 R5/R6 chạy được (mô hình đặt trên ổ D).
- **Không làm**
  - Viết bộ câu hỏi TN1/TN2 mới: chờ PDF thật, người dùng cung cấp trong vài ngày.
  - Đo qua HTTP với hệ thống đang chạy (cách B).
- **Tránh**
  - Tính thời gian giãn nhịp (Pacer) vào TTFT.
  - Tính thời gian của lượt "Xác nhận" vào TTFT.
  - Làm thay đổi kết quả các chỉ số hiện có.

## Các cách đã cân nhắc
| Cách | Mô tả | Đánh đổi |
|---|---|---|
| **A. Đo trong harness (ĐÃ CHỌN)** | `MeteredLLM` ghi mốc thời gian khi LLM sinh chữ đầu tiên / chọn xong công cụ | Không tốn thêm lượt Gemini, có sẵn cho mọi lượt TN2/TN3. Không tính mạng localhost → trình duyệt (không đáng kể; ghi rõ trong khóa luận) |
| B. Script HTTP streaming vào cổng 8000 | Đo đúng như trình duyệt | Tốn thêm lượt Gemini, ghi hội thoại vào CSDL dev, không dùng lại được kết quả TN2/TN3 |

Thứ tự làm, người dùng chọn "cách 1": làm công cụ đo, chạy TN3 đầy đủ/tối giản và đo thời gian ngay; TN1 reranker chờ PDF thật.

## Thiết kế
### 1. Hai mốc thời gian (`evaluation/harness.py`)
Tính từ lúc gửi tin nhắn đầu tiên của kịch bản, **trừ thời gian giãn nhịp đã chờ tính đến mốc đó**:
- `phan_hoi_dau_s`: thời điểm sinh viên thấy phản hồi đầu tiên. Đó là chữ đầu tiên của câu trả lời, hoặc lúc LLM trả về lời gọi công cụ (chip "Đang …" hiện ngay sau đó), tùy cái nào đến trước.
- `ttft_s`: thời điểm có chữ đầu tiên của câu trả lời (văn bản gửi cho sinh viên). NF-01 chấm theo mốc này.

Quy tắc đo:
- Chỉ đo trong lượt gửi tin đầu tiên; các lượt xác nhận tự động không tính.
- Không có chữ nào trước khi kết thúc lượt (vd lỗi) thì `ttft_s` để trống, không tính vào trung vị.

Vì sao có hai mốc: câu hỏi cần công cụ thì chữ đầu tiên chỉ đến sau khi công cụ chạy xong và LLM được gọi lần hai. Chip công cụ cho sinh viên biết hệ thống đang làm việc, nên khóa luận cần cả hai số.

### 2. Báo cáo
- **`chi_tiet.csv`** (TN2, TN3): thêm cột `phan_hoi_dau_s`, `ttft_s`.
- **Bảng tổng hợp**: thêm cột `TTFT trung vị (s)`, `TTFT P95 (s)`, `TTFT < 5 s` (tỉ lệ trên các câu có TTFT), `Phản hồi đầu trung vị (s)`.
- **TN3 có thêm `bang_theo_loai.md`**: mỗi `loai` × cấu hình một dòng, gồm số kịch bản, đúng công cụ, đúng tham số, hoàn thành, TTFT trung vị. Dùng để thấy mô tả tối giản ảnh hưởng mạnh nhất ở loại nào.

### 3. TN1 R5/R6
- Ổ C còn 1,9 GB; `bge-reranker-v2-m3` và `bge-m3` mỗi mô hình khoảng 2,2 GB.
- Đặt cache Hugging Face trên ổ D bằng biến môi trường người dùng `HF_HOME=D:\hf-cache`. Đây là thay đổi ngoài repo nên Claude hỏi trước khi đặt.
- Chép (không di chuyển) mô hình `multilingual-e5-base` sang cache mới để R1–R4 và các service không phải tải lại. Người dùng tự xóa bản cũ trên ổ C nếu muốn.
- Chạy thử R1–R6 trên bộ 11 câu hiện có, chỉ để kiểm tra chạy được. Không đưa vào khóa luận cho đến khi có PDF thật.

### 4. Chạy thật (Gemini, gói miễn phí)
- TN3 75 kịch bản × 2 cấu hình (`agent_gemini`, `agent_gemini_toi_gian`), khoảng 450 lượt gọi LLM. Đây cũng là lượt chạy lại TN3 sau ý tưởng 1 và 3.
- Người dùng quyết thời điểm chạy (hạn mức theo ngày); có thể chia theo `--limit`/ngày.
- Kết quả và nhận xét ghi vào `docs/09-danh-gia.md`.

## Ràng buộc
- Tuân thủ CLAUDE.md: code tiếng Anh, chuỗi hiển thị tiếng Việt, `ruff`.
- Không đổi ý nghĩa các cột cũ.
- Có test (`backend/tests/evaluation`) cho việc tính mốc thời gian:
  - trừ thời gian giãn nhịp;
  - bỏ qua lượt xác nhận;
  - TTFT trống khi không có chữ.

## Các quyết định Claude tự đưa ra (người dùng kiểm khi đọc)
1. NF-01 chấm theo `ttft_s` (chữ đầu tiên), báo thêm `phan_hoi_dau_s`.
2. Ngưỡng 5 giây báo dưới dạng tỉ lệ câu đạt, kèm trung vị và P95.
3. TN2 cũng có cột TTFT (cùng cơ chế, không tốn thêm), nhưng chạy lại TN2 thì chờ PDF.
4. Cache mô hình chuyển sang ổ D bằng `HF_HOME` (hỏi trước khi đặt).
