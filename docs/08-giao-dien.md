# 08. Thiết kế giao diện

Tham khảo bộ mockup đã vẽ (màn hình "Sinh viên – Hỏi đáp", "Nâng cao 1 – Trợ lý cá nhân hóa & làm thủ tục", "Admin – Quản lý tài liệu", "Admin – Thống kê"). Có thể chụp ảnh mockup đặt vào `docs/mockups/` rồi bảo Claude "làm giống ảnh này".

## Phong cách
- Font: Be Vietnam Pro (Google Fonts), hỗ trợ tiếng Việt tốt.
- Màu: nền `#F5F7FB`; xanh đậm `#0F1F4B` (sidebar); xanh chính `#1D4ED8` (nút, tin nhắn người dùng); nhấn vàng `#F59E0B` (biểu tượng trợ lý); xanh lá `#065F46`/`#ECFDF5` (thành công); cam `#9A3412`/`#FFF7ED` (cảnh báo); đỏ `#991B1B`/`#FEF2F2` (lỗi).
- Bo góc 10–18px, viền `#E3E8F0`, không đổ bóng đậm. Vùng bấm tối thiểu 44px.
- Icon: `lucide-react`.
- **Phím Esc** đóng hộp thoại / ngăn trượt (đổi mật khẩu, chi tiết đơn ở "Thủ tục của em", ngăn chi tiết ở các trang quản trị; hook `web/src/lib/useEscape.ts`), trừ khi đang gõ trong ô nhiều dòng (tránh mất câu trả lời cán bộ đang soạn).
- **Đổi mật khẩu** (bổ sung 26/11/2026): nút chìa khóa cạnh nút đăng xuất ở cuối menu (sinh viên và quản trị) mở hộp thoại Mật khẩu hiện tại / Mật khẩu mới / Nhập lại; kiểm tra ngay trên trình duyệt (`web/src/lib/account.ts`) rồi gọi `POST /api/auth/change-password`. Hộp thoại render qua portal vào `body` (menu điện thoại trượt bằng `transform` sẽ kẹp phần tử `fixed`).
- **Khung báo lỗi trang** (`ErrorBoundary`, bổ sung 26/11/2026): bọc nội dung trang trong cả hai layout; trang gặp lỗi khi hiển thị → khung "Trang này gặp sự cố…" + nút "Tải lại trang" thay cho trang trắng, menu vẫn dùng được, chuyển trang là hết lỗi. Không tải được phần mã của trang (vừa build lại) → "Trang vừa được cập nhật phiên bản mới…".

## Cây trang
```
/login
/                       → chuyển tới /chat
/chat                   → cuộc trò chuyện mới
/chat/:id               → cuộc trò chuyện
/hoc-tap                → Học tập của em (bổ sung 26/11/2026)
/thu-tuc                → Thủ tục của em
/admin                  → chuyển tới /admin/tong-quan
/admin/tong-quan        → Tổng quan (bổ sung 26/11/2026)
/admin/tai-lieu
/admin/tai-lieu/:id     → xem các đoạn
/admin/thu-truy-xuat
/admin/mcp
/admin/nhat-ky
/admin/don-tu           → Đơn từ (duyệt đơn, bổ sung 23/11/2026)
```

*Hình 8.1. Cây trang của giao diện web (sinh viên và quản trị).*

## Trang chat (quan trọng nhất)
- **Sao chép câu trả lời** (bổ sung 26/11/2026): nút đầu hàng 👍/👎 dưới mỗi câu trả lời đã lưu; chép chữ thường (bỏ `**`, `#`, liên kết Markdown) kèm mục "Nguồn:" liệt kê trích dẫn; biểu tượng đổi thành ✓ trong 2 giây. Trình duyệt không cấp clipboard (mở qua IP LAN, không phải localhost/https) → báo bôi đen để chép.
- **Ngày giờ tin nhắn** (bổ sung 26/11/2026, `dayLabel` / `formatTime` / `dayBreaks` trong `web/src/lib/conversations.ts`): dòng phân cách trước tin đầu tiên của mỗi ngày ("Hôm nay", "Hôm qua", "Thứ Hai, 23/11/2026" — tính theo giờ Việt Nam), giờ gửi `HH:mm` nhỏ dưới tin của sinh viên và đầu câu trả lời của trợ lý.
- **Tự cuộn** (sửa 26/11/2026, `isNearBottom` trong `web/src/lib/format.ts`): chỉ cuộn theo chữ mới khi đang ở cách đáy ≤ 80px; sinh viên cuộn lên đọc lại thì giữ nguyên vị trí và hiện nút nổi **"Cuộn xuống cuối"**; gửi câu hỏi mới hoặc đổi hội thoại thì lại theo dõi cuối. (Trước đây mỗi chữ mới đều kéo về cuối, không đọc lại được khi đang trả lời.)
- **Bộ đếm ký tự** ô nhập: hiện `n/2000` khi đã dùng từ 90% (cam), chạm giới hạn thì đỏ (khớp giới hạn 2000 ký tự của backend).
- **Danh sách hội thoại** (thanh trái, bổ sung 26/11/2026, `web/src/lib/conversations.ts`): ô **"Tìm cuộc trò chuyện"** lọc theo tiêu đề, không phân biệt dấu / hoa thường ("hoc phi" khớp "Học phí"); nhóm theo lần cập nhật cuối, tính theo ngày giờ Việt Nam: Hôm nay / 7 ngày qua / 30 ngày qua / Cũ hơn. Mỗi hội thoại có nút Đổi tên, **Tải về máy** (tệp `.txt` gồm câu hỏi, câu trả lời, giờ, nguồn trích dẫn từng câu và dòng lưu ý "chỉ để tham khảo"; tên tệp không dấu), Xóa.
- **Sidebar trái** (nền xanh đậm): logo, **chuông nhắc việc** (huy hiệu đỏ = có việc khẩn, cam = sắp tới; mở danh sách học phí / lịch thi / sách sắp đến hạn, nút "Hỏi trợ lý" mở /chat với câu hỏi soạn sẵn trong ô nhập, không tự gửi — bổ sung 23/11/2026), nút "Cuộc trò chuyện mới", danh sách hội thoại gần đây, liên kết "Thủ tục của em", thông tin sinh viên ở đáy.
- **Khung chat:** tin người dùng căn phải nền xanh; tin trợ lý căn trái nền trắng.
- **Chip tiến trình** phía trên câu trả lời khi đang xử lý: "Đang tra cứu quy chế…", "Đang xem bảng điểm của em…", chuyển ✓ khi xong. Nhãn lấy từ map tên tool → câu tiếng Việt ở frontend.
- **Trích dẫn:** `[1]` hiển thị dạng nút nhỏ; bên dưới câu trả lời có các thẻ "Nguồn tham khảo" (văn bản, Điều, trang). Bấm `[n]` mở popover: tên văn bản (phiên bản), Điều/Khoản/trang và trích đoạn (`trich_doan`, ≤ 300 ký tự).
- **Thẻ xác nhận hành động:** viền xanh nhạt, tiêu đề "Đề xuất thực hiện", mô tả, đồng hồ "Hết hạn sau 09:41", hai nút "Hủy" / "Xác nhận". Sau khi xử lý: chuyển thành trạng thái "Đã xác nhận ✓" hoặc "Đã hủy" (không bấm lại được).
  - Cài đặt (GĐ7): sau khi bấm, thẻ biến mất và trong luồng chat hiện dòng trạng thái từ tin hệ thống lưu ở backend ("Đã xác nhận: <mô tả>" nền xanh lá / "Đã hủy: <mô tả>"), nên tải lại trang vẫn đúng. Hết giờ (theo `het_han_luc`) thì thẻ khóa nút, hiện "Đã hết hạn". Backend trả 409 (đã xử lý / hết hạn) thì thẻ hiện thông báo lỗi.
- **Kiểm chứng câu trả lời** (23/11/2026, chỉ câu trả lời có tra cứu quy chế): sau khi chữ hiện xong, dòng nhỏ "Đang kiểm chứng với văn bản…", rồi nhãn "Đã kiểm chứng x/y ý với văn bản" (xanh khi đủ, vàng khi thiếu; rê chuột thấy mô hình giám khảo). Ý không có căn cứ được **gạch chân chấm vàng**, rê chuột thấy lý do. Có ý thiếu căn cứ → nút **"Hỏi cán bộ"** điền sẵn ô chat "Mình muốn gửi câu hỏi này cho cán bộ phòng ban phụ trách." (không tự gửi; trợ lý sẽ đề nghị `ask_staff` và hiện thẻ xác nhận). Lịch sử tải lại vẫn hiện đúng (đọc `kiem_chung`).
- **Đánh giá:** nút 👍/👎 (dùng icon, không dùng emoji) dưới câu trả lời; 👎 mở ô góp ý.
- **Ô nhập:** textarea tự giãn, Enter gửi, Shift+Enter xuống dòng; dòng nhắc "Câu trả lời do AI tạo, hãy đối chiếu văn bản gốc".
- **Câu hỏi chưa được trả lời** (bổ sung 26/11/2026, `unansweredQuestion` trong `web/src/lib/format.ts`): lượt bị lỗi giữa chừng (vd mô hình hết hạn mức) chỉ lưu tin của sinh viên; mở lại hội thoại thì dưới câu hỏi cuối hiện khung vàng "Câu hỏi này chưa được trả lời…" kèm nút **"Gửi lại câu hỏi"** (không áp cho tin Xác nhận / Hủy). Lỗi ngay trong lượt vẫn hiện khung đỏ kèm "Thử lại" như trước.
- **Câu hỏi gợi ý** khi hội thoại trống (cá nhân hóa 26/11/2026, `web/src/lib/suggestions.ts`): tối đa 4 câu, ưu tiên tình trạng của chính sinh viên lấy từ `/api/my/overview` (cảnh báo học vụ → thiếu chứng chỉ / đủ điều kiện tốt nghiệp → nợ học phí → bảo lưu → môn F chưa học lại (tên môn thật) → GPA ≥ 3,6 hỏi học bổng → tân sinh viên hỏi tín chỉ); câu cá nhân hóa viền xanh + nhãn "Dành cho em". Thiếu thì bù câu mặc định "Em còn thiếu gì để tốt nghiệp?", "Lịch thi của em", "Học lại môn bị F thế nào?", "Xin giấy xác nhận sinh viên" (bỏ câu mặc định trùng chủ đề). API lỗi → chỉ câu mặc định.
- **Chế độ trình bày** (demo trước hội đồng; chỉ khi backend đặt `CHE_DO_TRINH_BAY=true`, `/health.che_do_trinh_bay`): thanh trên cùng có công tắc "Chế độ trình bày" (lưu `localStorage`) và nút A−/A+ (cỡ chữ gốc 100/115/130%). Bật thì:
  - cột phải **"Bên trong Agent"** (~360 px; màn hẹp xếp xuống dưới): mỗi lượt gọi công cụ một thẻ đánh số — nhãn tiếng Việt + tên kỹ thuật, huy hiệu trạng thái (màu như trang Nhật ký), "LLM gửi: …", dòng nền vàng **"🔒 Hệ thống điền: ma_sv=…"** hoặc "LLM gửi SV22002 → hệ thống ghi đè ma_sv=SV22001", lý do khi bị từ chối. Đọc từ `GET /api/conversations/{id}/trace` (nhật ký `luot_goi_cong_cu`), tải lại khi luồng báo `tool_end`/`pending_action`/`done` và sau khi xác nhận/hủy thẻ (không poll). Thẻ mới nổi bật ~1 giây. Chân bảng: "Bảng này đọc trực tiếp từ nhật ký hệ thống";
  - hàng nút **câu hỏi soạn sẵn** trên ô nhập (`web/src/lib/demoPrompts.ts`, nguyên văn `docs/kich-ban-demo.md`): bấm = điền vào ô, chưa gửi.

## Trang "Học tập của em" (`/hoc-tap`, bổ sung 26/11/2026)
Đọc `GET /api/my/overview` (không qua LLM; cache 5 phút, dùng chung với gợi ý ở chat). Ô **"Học kỳ"** ở đầu trang (mặc định "Hiện tại"; các lựa chọn: kỳ sau, các kỳ có trong bảng điểm) đổi thời khóa biểu, lịch thi, học phí sang kỳ đã chọn; kỳ chưa có dữ liệu hiện "Chưa có dữ liệu cho học kỳ này". Thẻ hồ sơ nền xanh đậm (họ tên, lớp, ngành, khóa, trạng thái học); ô cảnh báo màu kèm nút "Hỏi trợ lý" (đỏ: cảnh báo học vụ, nợ học phí; cam: thiếu chứng chỉ tốt nghiệp; xanh: đủ điều kiện tốt nghiệp); 3 thẻ số (GPA tích lũy, tín chỉ tích lũy có thanh tiến độ, học phí kỳ này); **thời khóa biểu dạng lưới tuần** (cột Thứ 2–7, thêm Chủ nhật nếu có lớp; hàng tiết 1–10 hoặc hơn; mỗi lớp một màu; điện thoại hiện danh sách); lịch thi; tiến độ tốt nghiệp (chứng chỉ ✓/✗, học phần còn thiếu); bảng điểm theo học kỳ (mở/thu gọn, F đỏ, A xanh, ghi "học lại"); khung học phí chi tiết khi còn nợ. Nút **"In / Lưu PDF"** (gọi hộp thoại in của trình duyệt; Ctrl+P cũng được): bản in ẩn menu, ô chọn học kỳ, nút "Hỏi trợ lý", mở hết các học kỳ trong bảng điểm, giữ màu nền, thêm dòng "Số liệu từ Trợ lý học vụ lúc … — bản tham khảo, không thay giấy xác nhận chính thức". Mục nào có công cụ đang tắt → "Chức năng này đang tạm dừng", lỗi → "Chưa tải được phần này", các mục khác vẫn hiện.

## Trang "Thủ tục của em"
- **Đơn vừa được xử lý** (bổ sung 26/11/2026, `web/src/lib/requestUpdates.ts`): menu "Thủ tục của em" có huy hiệu đỏ = số đơn đã đổi trạng thái kể từ lần em xem trước (danh sách tải lại mỗi 60 giây). Trong trang, đơn đó gắn nhãn "Mới cập nhật"; mở chi tiết đơn thì nhãn mất, hoặc bấm "Đánh dấu đã xem hết". Trạng thái "đã xem" chỉ lưu ở trình duyệt (localStorage, theo mã sinh viên) — không thêm bảng/API; lần đầu dùng thì ghi nhận im lặng mọi đơn đang có (không báo cả loạt đơn cũ), đơn em vừa gửi (còn "mới tạo") không tính.
Bảng/thẻ đơn: mã đơn, loại, ngày tạo, người tạo (Sinh viên / Trợ lý AI), trạng thái (badge màu). Bấm xem chi tiết nội dung đơn và ghi chú xử lý. Câu hỏi gửi cán bộ (`hoi_dap`): chi tiết hiện "Câu hỏi", "Gửi tới" (tên phòng ban) và mục **"Trả lời của cán bộ"**.

## Trang quản trị
- **Tổng quan** (`/admin/tong-quan`, trang đầu sau khi đăng nhập quản trị, bổ sung 26/11/2026; `web/src/lib/adminOverview.ts`): chỉ gọi API sẵn có, dùng chung khóa truy vấn với huy hiệu menu / khung "Cần chú ý" / trang Tri thức. (1) **Việc cần xử lý** — 3 ô bấm được: đơn mới chưa xử lý → Đơn từ; sinh viên cần chú ý → Sinh viên; lỗ hổng tri thức 7 ngày chưa vào kho → Tri thức. (2) **Tình trạng hệ thống** — mô hình ngôn ngữ + từng MCP server (biểu tượng + chữ "Hoạt động / Đang tắt / Gián đoạn", gián đoạn lên đầu; `/health` tải lại mỗi 30 giây). (3) **7 ngày gần nhất** — câu hỏi, tỉ lệ hữu ích, tỉ lệ ý có căn cứ, tỉ lệ dùng mô hình dự phòng, link sang Thống kê. API nào lỗi thì ô đó hiện "—", các ô khác vẫn hiện.
- **Tài liệu:** vùng kéo thả, form khai báo phiên bản + khóa áp dụng, bảng trạng thái (Đang xử lý / Đã lập chỉ mục / Lỗi), số đoạn.
- **Thử truy xuất:** ô câu hỏi + chọn khóa + bật/tắt từng thành phần (vector, từ khóa, lọc phiên bản, rerank) → danh sách đoạn kèm điểm. Rất hữu ích để minh họa trong khóa luận.
- **MCP & quyền:** nhóm theo server (chấm xanh/đỏ trạng thái kết nối), mỗi tool một dòng: tên, mô tả, mức rủi ro (select), cần xác nhận (switch), bật (switch).
  - Nút **"Thêm MCP server"** (AD-11) mở hộp thoại Tên / Mô tả / Địa chỉ → **"Kiểm tra kết nối"** hiện bảng xem trước (title, tên, mô tả đầy đủ, tham số, "Server tự khai báo: chỉ đọc", cảnh báo trùng tên) → **"Lưu"** chỉ bấm được khi địa chỉ hiện tại đã kiểm tra thành công. Lỗi API hiện `detail` tiếng Việt.
  - Nhãn duyệt cạnh tên công cụ: **"Mới — cần duyệt"** (xanh) / **"Mô tả đã thay đổi — cần duyệt lại"** (vàng). Mũi tên cạnh tên mở rộng xem mô tả đầy đủ server gửi cho LLM + tham số (JSON, đã ẩn `ma_sv`/`ma_khoa`). Bật công cụ = duyệt.
  - Dưới server: "`x`: trùng tên với công cụ của server `y` — bị bỏ qua".
- **Nhật ký:** công tắc **"Tự cập nhật"** (3 giây/lần, dòng mới nổi bật ~1 giây — dùng khi demo, không phải F5); bảng thời gian, người dùng, server/tool, trạng thái, thời gian xử lý; bấm dòng mở ngăn chi tiết JSON. Nếu `tham_so_llm` khác `tham_so` → tô vàng "Đã tiêm ngữ cảnh".
- **Đơn từ** (bổ sung 23/11/2026): quản trị viên đóng vai cán bộ phòng CTSV. Lọc trạng thái (mặc định "Mới tạo") và loại đơn; bảng mã đơn, sinh viên, loại (kèm "Trợ lý AI"/"Sinh viên" tạo), thời điểm nộp, trạng thái. Nút "Xử lý" mở ngăn chi tiết: nội dung đơn, ô ghi chú gửi sinh viên (bắt buộc khi từ chối), chỉ hiện các nút bước kế tiếp hợp lệ (Nhận xử lý / Duyệt / Từ chối / Hoàn tất). Kết quả hiện ngay ở "Thủ tục của em".
  - *Bổ sung 26/11/2026 (`waitingAge`, `replyTemplates`, `insertTemplate` trong `web/src/lib/admin.ts`):* dưới thời điểm nộp có "Gửi hôm nay" / "Chờ N ngày" (tính theo ngày Việt Nam, chỉ với đơn chưa hoàn tất/từ chối); chờ quá 3 ngày thì thêm biểu tượng đồng hồ + chữ đậm màu cảnh báo. Ngăn chi tiết có hàng **câu mẫu** theo loại đơn, chỉ cho các bước còn làm được (vd giấy xác nhận: "Mời nhận giấy", "Thông tin chưa khớp"); bấm mẫu thì điền vào ô trống, hoặc nối xuống dòng mới nếu cán bộ đã gõ — không xóa chữ đang có. Cán bộ sửa lại cho đúng trường hợp trước khi gửi.
- **Menu quản trị:** mục "Đơn từ" có huy hiệu đỏ = số đơn **mới tạo** chưa xử lý (bổ sung 26/11/2026; tải lại mỗi 30 giây và ngay khi xử lý xong một đơn; ẩn khi 0, tối đa "99+").
- **Sinh viên — khung "Cần chú ý"** (bổ sung 26/11/2026, trên bảng sinh viên): tiêu đề "Cần chú ý (n)" mở/thu gọn; chip lọc "Tất cả / Cảnh báo học vụ / Nợ học phí / Chưa đủ ĐK tốt nghiệp" kèm số; mỗi dòng: họ tên, mã SV · lớp · khóa, các lý do dạng nhãn (đỏ = khẩn, cam = chú ý) + chi tiết. Bấm tên → ô tìm kiếm của bảng điền mã SV.
- **Thống kê:** 4 thẻ số liệu, biểu đồ chủ đề/tool dùng nhiều, danh sách câu trả lời bị đánh giá "chưa đúng". Bổ sung 26/11/2026: khu **"An toàn & độ tin cậy"** (lượt gọi bị từ chối, lần LLM tự điền mã SV bị ghi đè, tỉ lệ sinh viên xác nhận hành động, tỉ lệ ý có căn cứ; 2 thanh màu tỉ lệ theo trạng thái lượt gọi và kết cục hành động cần xác nhận; khung **"Mô hình viết câu trả lời"**: mỗi mô hình một thanh, số câu, phần trăm, nhãn cam "dự phòng" cho `LLM_FALLBACK_MODEL`, tỉ lệ dùng dự phòng ở góc — nâng cấp CSDL 13; CSV có thêm mục này) và nút **"Xuất CSV"** (tạo ở trình duyệt từ số liệu đang hiển thị, BOM UTF-8 cho Excel, tên `thong-ke_<từ>_<đến>.csv`).

### Trang "Đơn từ" — câu hỏi gửi cán bộ (bổ sung 23/11/2026)
Bộ lọc loại có "Câu hỏi cán bộ". Mở một câu hỏi: hiện câu hỏi + phòng ban; ô nhập đổi thành
"Nội dung trả lời"; nút: "Nhận xử lý", **"Trả lời"** (= `hoan_tat`, bắt buộc có nội dung), "Từ
chối" (ngoài phạm vi, cần lý do). Không có nút "Duyệt".

### Trang "Tri thức" (`/admin/tri-thuc`, bổ sung 25/11/2026)
Hai thẻ:
- **Lỗ hổng tri thức** — chọn khoảng thời gian (7/30/90/365 ngày), 4 nút lọc kèm số đếm: *Thiếu căn cứ*
  (ý bị giám khảo gắn, gạch chân chấm vàng + lý do), *Không tìm thấy* (trợ lý đã tra cứu nhưng văn
  bản không có), *Hỏi cán bộ* (câu hỏi `hoi_dap`, trạng thái, câu trả lời của cán bộ), *Đánh giá 👎*
  (góp ý). Mỗi mục hiện câu hỏi của sinh viên (không có tên / mã SV), nhãn "Đã có trong kho" nếu đã
  viết, nút **"Viết câu trả lời vào kho"** (mở form điền sẵn).
- **Kho hỏi đáp** — dòng trạng thái ("Trợ lý đang dùng N mục" / đang lập chỉ mục (tự cập nhật mỗi 2 giây)
  / lỗi), danh sách mục (phòng ban, nguồn gốc, câu hỏi, trả lời) với nút Sửa / Gỡ.
Form thêm/sửa (ngăn kéo bên phải): khung cảnh báo "Kho trả cho MỌI sinh viên — bỏ tên, mã SV, số điện
thoại, email, hoàn cảnh riêng", cảnh báo tức thì khi gõ phải thông tin cá nhân, nút "Lưu và cập nhật
trợ lý". Trang "Đơn từ": câu hỏi `hoi_dap` đã trả lời có khung **"Đưa vào kho hỏi đáp"** → mở trang
Tri thức với form điền sẵn. Trang "Tài liệu": văn bản kho ghi "Hỏi đáp cán bộ · không có tệp, quản lý
ở trang Tri thức", nút xóa bị khóa. Chat: trích dẫn từ kho có nhãn xanh **"Cán bộ trả lời"**, không có
nút mở văn bản gốc.
