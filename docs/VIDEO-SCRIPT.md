# Kịch bản quay video demo — UBNDAI

> Video demo **3 phút**, quay màn hình + thuyết minh. Khác với `docs/DEMO-SCRIPT.md` (demo trực tiếp, có tương tác): video là một lần dựng, không sửa được sau khi nộp, nên phần chuẩn bị quan trọng hơn phần diễn.
>
> Nguyên tắc: **quay kết quả, không quay thao tác.** Người xem không cần thấy bạn gõ URL hay đăng nhập.

---

## PHẦN 0 — Chuẩn bị *(làm hết trước khi bấm ghi)*

### 0.1 Bắt buộc: khởi động lại server

```bash
# Tắt HẾT tiến trình uvicorn cũ, rồi:
alembic upgrade head
python scripts/seed_db.py
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

**Không được bỏ bước này.** `load_catalog()` cache theo vòng đời tiến trình — server chạy từ trước sẽ phục vụ catalog cũ. Đã xảy ra thật: server cũ hiển thị *"Nghị định 217/2026/NĐ-CP"*, một văn bản **không tồn tại**, đã bị gỡ khỏi dữ liệu từ lâu. Quay trúng cảnh đó rồi nộp thì mất luôn phần AI Safety.

**Kiểm bắt buộc trước khi ghi** — phải ra `0`:

```bash
curl -s http://127.0.0.1:8000/api/v1/procedures/giay_phep_xay_dung | grep -c "217/2026"
python scripts/eval_identify.py          # phải in [OK]
```

### 0.2 Môi trường quay

| Việc | Lý do |
|---|---|
| Trình duyệt ẩn danh, **tắt hết extension** | Grammarly từng chèn thanh lạ vào ô chat, trông như lỗi sản phẩm |
| Ẩn bookmark bar, đóng tab thừa | Khung hình sạch |
| Zoom trình duyệt 110–125% | Chữ đọc được khi video bị nén |
| Độ phân giải 1920×1080, 30 fps | Chuẩn nộp bài |
| Chuẩn bị sẵn ảnh sổ đỏ | Không tìm file khi đang quay |
| Tải trang một lần trước | Lần đầu chậm hơn |
| Tắt thông báo hệ thống | Popup Zalo/mail giữa video là hỏng |

### 0.3 Quay từng cảnh rời

Đừng cố quay một mạch 3 phút. Quay **6 cảnh riêng**, ghép sau. Hỏng cảnh nào quay lại cảnh đó.

---

## PHẦN 1 — Bảng phân cảnh

Tổng: **3:00**. Cột "Trên màn hình" là thứ người xem thấy; cột "Thuyết minh" đọc nguyên văn.

---

### Cảnh 1 — Vấn đề · `0:00–0:25`

**Trên màn hình:** Slide tiêu đề, hoặc animation đơn giản: người dân → quầy → bị trả lại → quay lại.

**Thuyết minh:**

> "Một người dân đi xin giấy phép xây dựng. Họ tra trên Cổng Dịch vụ công, thấy danh sách năm loại giấy tờ, chuẩn bị đủ, lên phường.
>
> Cán bộ nói thiếu. Vì hai trong năm loại đó không áp dụng cho trường hợp của họ, còn một loại khác thì cần mà danh sách không nói rõ.
>
> Họ về, chuẩn bị lại, đi lần hai."

**Ghi chú:** Không nói tên sản phẩm, không nói công nghệ. Chỉ dựng vấn đề.

---

### Cảnh 2 — Checklist theo tình huống · `0:25–1:05`

**Đây là cảnh quan trọng nhất. Quay lại tới khi mượt.**

**Trên màn hình:**
1. Màn hình chat, gõ: `tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ 2 tầng`
2. Hệ thống hỏi lại về thẩm duyệt PCCC → trả lời **không**
3. Hỏi tiếp về khu vực di tích → trả lời **không**
4. Checklist hiện ra — **zoom vào** hai mục mang nhãn *không áp dụng*

**Thuyết minh:**

> "UBNDAI không trả lời ngay. Nó hỏi lại trước.
>
> *(khi checklist hiện)* Danh mục gốc có năm thành phần. Nhưng với trường hợp vừa mô tả, chỉ **ba mục** thật sự phải chuẩn bị.
>
> Hai mục còn lại được đánh dấu *không áp dụng* — **kèm lý do**, chứ không bị giấu đi. Người dân thấy được vì sao nó không áp dụng với mình, và cán bộ kiểm chứng lại được.
>
> Đó chính là vòng lặp lúc nãy. Bị xoá ngay tại đây."

**Ghi chú kỹ thuật:** đã kiểm chứng số mục thay đổi thật theo câu trả lời — 3 / 4 / 5 (`docs/EVAL-EVIDENCE.md` TC1). Nếu muốn mạnh hơn, quay thêm 5 giây trả lời **có** cho PCCC để checklist tăng lên 4 mục.

---

### Cảnh 3 — Truy vết nguồn · `1:05–1:30`

**Trên màn hình:** Chỉ chuột vào khối "Đã kiểm chứng nguồn" bên phải, zoom vào một trích dẫn.

**Thuyết minh:**

> "Mỗi mục trong checklist truy về một yêu cầu giấy tờ cụ thể trong danh mục đã kiểm duyệt, kèm liên kết tới trang công bố trên Cổng Dịch vụ công. Không mục nào do mô hình tự nghĩ ra.
>
> Và khi hệ thống không đọc được trang gốc, nó **nói thẳng** là đang dùng bản lưu có checksum — thay vì gắn dấu *đã kiểm chứng* cho thứ nó chưa thực sự đọc được."

**Ghi chú:** Nếu khối hiện trạng thái `fallback`, **đừng quay lại cảnh khác** — đó chính là điều đang nói. Cứ để nguyên và chỉ vào nó.

---

### Cảnh 4 — Tải giấy tờ, OCR · `1:30–1:55`

**Trên màn hình:** Kéo ảnh sổ đỏ vào, hệ thống nhận diện loại giấy tờ, mục tương ứng chuyển trạng thái.

**Thuyết minh:**

> "Người dân chụp giấy tờ bằng điện thoại và tải lên. Hệ thống nhận diện loại giấy tờ, bóc các trường dữ liệu, và tự đối chiếu vào checklist.
>
> Chỗ nào nó không đủ chắc, nó **không im lặng điền vào** — nó đánh dấu cần người kiểm tra. Một ô điền sai trong tờ khai còn tệ hơn một ô để trống, vì ô trống thì người dân nhìn thấy."

**Ghi chú:** Chạy thử trước khi quay. Nếu ảnh không nhận đúng, thử ảnh chụp thẳng, đủ sáng, thấy rõ tiêu đề.

---

### Cảnh 5 — Cổng cán bộ · `1:55–2:20`

**Trên màn hình:** Chuyển sang `/officer`, mở một hồ sơ có cảnh báo, rê chuột qua ba nút *chấp nhận / bác bỏ / chuyển cấp*.

**Thuyết minh:**

> "Phía cán bộ, hồ sơ đến kèm các phát hiện của hệ thống. Cán bộ **luôn có quyền bác bỏ** phát hiện của AI.
>
> Quan trọng hơn: AI **không thể** kết luận một hồ sơ là sai. Ràng buộc đó nằm ở tầng kiểu dữ liệu — thử tạo cũng ném lỗi. Chỉ bộ quy tắc nghiệp vụ khai báo, thứ cán bộ đọc và ký duyệt được, mới có thẩm quyền đó."

---

### Cảnh 6 — Số đo & lời đề nghị · `2:20–3:00`

**Trên màn hình:** Slide số liệu — chữ to, mỗi dòng một ý.

```
Chốt nhầm thủ tục          0 / 60      (bộ đánh giá giữ riêng)
Kiểm thử tự động           335 · CI xanh
Chi phí AI mỗi hồ sơ       ~410 đ
5 thủ tục · 17 quy tắc · 75 endpoint
```

**Thuyết minh:**

> "Vài con số, tất cả đo được chứ không ước lượng.
>
> Chỉ số chúng tôi coi trọng nhất không phải độ chính xác, mà là **tỉ lệ chốt nhầm thủ tục: không ca nào trên sáu mươi**. Vì chốt nhầm thủ tục làm sai toàn bộ checklist phía sau. Khi không chắc, hệ thống hỏi lại — chứ không đoán.
>
> Chi phí AI mỗi hồ sơ khoảng bốn trăm mười đồng, tính từ giá token thật. Ở mức đó, miễn phí cho người dân là bền vững, không phải trợ giá tạm thời.
>
> Chúng tôi cần một UBND cấp xã đồng ý chạy thí điểm, và cho tiếp cận số liệu tỷ lệ hồ sơ bị trả lại hiện nay.
>
> Người dân không cần hiểu AI. Họ cần đi một lần là xong."

---

## PHẦN 2 — Không làm

| Đừng | Vì sao |
|---|---|
| Quay cảnh đăng nhập, gõ URL | Tốn 10 giây không nói lên điều gì |
| Đọc sơ đồ kiến trúc | Video demo là để thấy sản phẩm chạy |
| Nói "AI của chúng tôi rất thông minh" | Không kiểm chứng được |
| Ghép nhạc nền to | Át lời thuyết minh |
| Tua nhanh lúc hệ thống đang nghĩ | Cắt hẳn đoạn chờ, đừng tua |
| Nói "100% chính xác" | Sai. Độ phủ 60% trên bộ giữ riêng — nếu bị hỏi, nói thật |
| Quay bằng server chạy từ hôm trước | Catalog cũ, có thể lộ văn bản pháp luật bịa |

---

## PHẦN 3 — Danh sách kiểm trước khi nộp

Xem lại video và tick từng dòng:

- [ ] Không khung hình nào chứa `217/2026`, `135/2025`, hay `1.007262`
- [ ] Không lộ API key, token, đường dẫn cá nhân, email
- [ ] Không lộ dữ liệu cá nhân thật — chỉ dùng dữ liệu demo
- [ ] Chữ đọc được khi xem ở 720p
- [ ] Âm thanh không rè, không tạp âm nền
- [ ] Đủ 3 phút, không quá
- [ ] Có nói **Lời đề nghị** cụ thể ở cuối
- [ ] Có nêu ít nhất một giới hạn thật của sản phẩm

Dòng cuối là cố ý. Giám khảo hạng mục AI Safety thường tin một đội dám nêu giới hạn hơn một đội tuyên bố hoàn hảo.

---

## PHẦN 4 — Nếu quay hỏng và hết giờ

Ưu tiên giữ lại theo thứ tự này:

1. **Cảnh 2** (checklist theo tình huống) — không có cảnh này thì video không chứng minh được gì
2. **Cảnh 6** (số đo + lời đề nghị)
3. **Cảnh 3** (truy vết nguồn)
4. Cảnh 5 (cổng cán bộ)
5. Cảnh 4 (OCR)
6. Cảnh 1 (vấn đề — có thể thay bằng một câu nói đầu video)

Video 90 giây gồm cảnh 2 + 3 + 6 vẫn là một bài nộp tốt. Video 3 phút mà cảnh 2 bị lắp bắp thì không.
