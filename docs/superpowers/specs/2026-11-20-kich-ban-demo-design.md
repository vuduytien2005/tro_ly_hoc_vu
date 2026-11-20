# Thiết kế: kịch bản demo 10 phút trước hội đồng

## Mục đích

Có một kịch bản bảo vệ chạy đúng 10 phút (gồm cả slide). Hội đồng cần thấy được ba điều:

1. Trợ lý trả lời đúng quy chế và có trích dẫn.
2. Trợ lý làm được thủ tục thật.
3. Hệ thống **an toàn** nhờ tiêm ngữ cảnh, thẻ xác nhận và nhật ký.

Sản phẩm là tệp `docs/kich-ban-demo.md`.

## Đã chốt với người dùng

- 10 phút là **toàn bộ** thời gian, kể cả slide. Chia như sau:
  - slide mở đầu ~1 phút;
  - slide kiến trúc ~1,5 phút;
  - **demo trực tiếp ~5,5 phút**;
  - slide kết quả và kết luận ~2 phút.
- Demo trực tiếp có 5 bước, lấy theo `docs/01` mục 6:
  - bước 1: RAG có trích dẫn;
  - bước 3: đăng ký IT004.02, hiện thẻ xác nhận;
  - bước 4: đăng ký SE105.02, báo trùng lịch ngay, không hiện thẻ;
  - bước 5: hỏi điểm SV22002, trợ lý từ chối;
  - bước 7: quản trị viên tắt `register_course`, sau đó xem nhật ký.
- Bước 2 (tiến độ tốt nghiệp) và bước 6 (SV21001 xin giấy xác nhận) để **dự bị**.
- Dự phòng **nhiều tầng (phương án A)**:
  - mất wifi thì phát 4G từ điện thoại;
  - LLM lỗi và thử lại một lần vẫn lỗi thì phát video quay sẵn **của đúng bước đó**, có 5 đoạn ngắn;
  - hỏng máy hoặc máy chiếu thì dùng ảnh chụp trong slide dự bị.

## Các phương án đã cân nhắc

| Phương án | Đánh đổi | Kết quả |
|---|---|---|
| A. Nhiều tầng: 4G → video từng bước → ảnh | Demo vẫn chạy thật; mỗi sự cố có lối thoát dưới 30 giây | **Chọn** |
| B. Chỉ phát một video | An toàn tuyệt đối nhưng kém thuyết phục, dễ bị yêu cầu "chạy câu khác" | Loại |
| C. Thêm LLM cục bộ (Ollama) | Chưa kiểm thử với hệ thống, mô hình nhỏ gọi công cụ kém, chậm | Loại: tăng rủi ro |

## Nội dung `docs/kich-ban-demo.md` (Claude tự quyết, người dùng có thể sửa)

1. **Bảng thời gian theo giây.** Mỗi bước có:
   - câu gõ sẵn (giữ nguyên câu trong `demo_check.py`);
   - kết quả mong đợi trên màn hình;
   - một câu lời thoại nhấn vào điểm an toàn.
2. **Bố trí màn hình.**
   - Hai cửa sổ trình duyệt, mỗi cửa sổ đăng nhập sẵn một tài khoản: SV22001, và admin trong cửa sổ ẩn danh.
   - Nhờ vậy không phải đăng xuất, đăng nhập giữa chừng.
   - Bước 3 và bước 4 dùng **cùng một hội thoại**, vì bước 4 cần lớp IT004.02 vừa đăng ký để báo trùng lịch.
3. **Điểm nhấn an toàn.**
   - Tiêm ngữ cảnh:
     - ở bước 5, LLM tự từ chối (tầng a);
     - ở bước 7, mở nhật ký: các lượt của bước 3 có nhãn vàng "Đã tiêm ngữ cảnh";
     - bấm vào dòng sẽ thấy `tham_so_llm` không có `ma_sv`, còn `tham_so` có (tầng b).
   - Xác nhận: thẻ ở bước 3 phải bấm "Xác nhận" thì mới ghi.
   - Kiểm tra trước: bước 4 báo trùng lịch, không hiện thẻ.
   - Tắt công cụ: bước 7.
   - Nhật ký: mọi lượt gọi đều có, kể cả lượt bị từ chối.
4. **Câu hỏi dự bị**: bước 2, bước 6, và các câu hội đồng hay hỏi kèm cách trả lời. Ví dụ:
   - "LLM bị lừa thì sao?";
   - "sao không cho LLM tự chọn mã sinh viên?";
   - "tài liệu chứa lệnh độc thì sao?" (dẫn số liệu TN4).
5. **Checklist trước giờ bảo vệ.**
   - Hôm trước:
     - chạy `demo_check.py --llm`;
     - quay video;
     - **không chạy thực nghiệm trong ngày bảo vệ**, để giữ hạn mức Gemini.
   - Trước giờ bảo vệ 15 phút:
     - chạy `run_all.ps1`, `reset_demo.ps1`, rồi `demo_check.py` (bản không gọi LLM);
     - đăng nhập sẵn hai cửa sổ;
     - mở video và slide dự bị;
     - bật sẵn 4G.
6. **Bảng xử lý sự cố.** Mỗi triệu chứng có: dấu hiệu nhận biết, việc cần làm, câu nói với hội đồng. Các triệu chứng:
   - mất mạng;
   - 429 hoặc hết hạn mức;
   - 503 quá tải;
   - LLM trả lời sai hay không gọi công cụ;
   - service không lên;
   - máy chiếu.
7. **Hướng dẫn quay video.**
   - Quay 5 đoạn, mỗi bước một đoạn, khoảng 30–60 giây.
   - Có thể dùng Xbox Game Bar (Win+Alt+R), có sẵn trên Windows.
   - Đặt tên theo bước.
   - Chạy `reset_demo.ps1` trước khi quay.

## Không làm

- Không sửa code hay giao diện.
- Không làm slide. Tài liệu chỉ nêu ý chính cho từng slide.
- Số liệu ở slide kết quả lấy từ lần chạy thực nghiệm toàn bộ đang chạy (20/11/2026). Nếu sau đó chạy lại thì cập nhật.
