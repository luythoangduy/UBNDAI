# Demo Script — UBNDAI

> Kịch bản demo cho buổi chấm. Kèm lệnh chuẩn bị, lời thoại, phương án dự phòng, và các câu hỏi giám khảo nhiều khả năng sẽ hỏi.
>
> **Nguyên tắc dẫn dắt:** *Outcome first, Technology second, Proof always.* Không mở đầu bằng kiến trúc. Không đi tuần tự từng màn hình. Mỗi thao tác phải trả lời một câu hỏi mà giám khảo đang nghĩ trong đầu.

---

## 1. Chuẩn bị trước khi lên trình bày

Chạy **15 phút trước**, không phải 2 phút trước.

```bash
# Một lệnh dựng toàn bộ demo (Windows)
powershell -File scripts/demo.ps1
# → build frontend, seed dữ liệu demo, chạy uvicorn ở 127.0.0.1:8000
```

Hoặc thủ công:

```bash
alembic upgrade head                 # DB local hay thiếu migration
python scripts/seed_db.py            # tạo case-demo-001, document-demo-001
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

**Danh sách kiểm trước khi bắt đầu:**

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/procedures | head -c 200
python scripts/eval_identify.py      # phải in [OK], exit 0
```

| Kiểm | Vì sao |
|---|---|
| Đã đóng hết tiến trình uvicorn cũ | Tiến trình cũ phục vụ code cũ và đã từng làm rối cả buổi kiểm chứng |
| Tắt extension trình duyệt (Grammarly, ...) | Đã từng chèn thanh lạ vào ô chat và bị nhầm là lỗi sản phẩm |
| Mở sẵn 2 tab: `/citizen` và `/officer` | Không chuyển tab giữa lúc nói |
| Có sẵn 1 ảnh giấy tờ để tải lên | Không tìm file khi đang demo |
| Đã tải xong trang một lần | Lần tải đầu chậm hơn |

**Phương án dự phòng:** nếu mạng hỏng, hệ thống **vẫn chạy** — nhận diện thủ tục, checklist và rule engine không cần LLM hay mạng. Chỉ mất phần hỏi đáp mở và kéo nguồn live. Biết trước điều này để không hoảng.

---

## 2. Kịch bản 5 phút

Phân bổ theo khung pitching: Hook 10% · Vấn đề 15% · Giải pháp 15% · **Demo 20%** · Kinh doanh 20% · Tầm nhìn & Đề nghị 20%.

### [0:00–0:30] Hook — mở bằng con số, không bằng công nghệ

> "Một người dân đi xin giấy phép xây dựng. Họ tra trên Cổng Dịch vụ công, thấy danh sách 5 loại giấy tờ, chuẩn bị đủ, lên phường. Cán bộ nói thiếu — vì 2 trong 5 loại đó không áp dụng cho trường hợp của họ, còn 1 loại khác thì lại cần mà danh sách không nói rõ. Họ về, chuẩn bị lại, đi lần hai.
>
> Vòng lặp đó là thứ chúng tôi xoá."

**Không nói** ở đoạn này: LangGraph, RAG, model nào. Chưa ai quan tâm.

### [0:30–1:15] Vấn đề — vì sao công cụ hiện có không giải quyết được

Ba nguyên nhân gốc, nói nhanh:

1. Thủ tục có **điều kiện phụ thuộc tình huống** — trang tra cứu liệt kê *toàn bộ*, kể cả phần chỉ áp dụng cho một số trường hợp.
2. Người dân **không biết mình không biết gì** — tìm kiếm chỉ trả lời câu đã hỏi, không hỏi ngược.
3. Sai sót chỉ lộ ra **tại quầy** — không có vòng kiểm tra nào trước khi nộp.

> "Chi phí kép: người dân mất thời gian đi lại, cán bộ mất thời gian xử lý hồ sơ không hợp lệ thay vì hồ sơ hợp lệ."

### [1:15–2:00] Giải pháp — một câu, rồi chuyển sang chứng minh

> "UBNDAI hướng dẫn theo đúng tình huống của từng người, và kiểm tra hồ sơ trước khi họ rời nhà. Mọi câu trả lời đều truy vết được về nguồn công bố chính thức."

Nhấn vế cuối, vì đó là điều khiến cơ quan nhà nước dám dùng:

> "Đây là điểm khác biệt quan trọng nhất. Một chatbot thông thường có thể trả lời trôi chảy nhưng không chịu trách nhiệm được về nội dung. Cơ quan hành chính không thể triển khai thứ như vậy."

### [2:00–3:00] Demo — **đây là phần phải tập nhiều nhất**

Chỉ diễn **ba** thao tác. Không đi hết tính năng.

#### Thao tác 1 — Hướng dẫn theo tình huống *(khoảng 30 giây)*

Gõ vào ô chat:

```
tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ 2 tầng
```

Hệ thống **hỏi lại** trước khi chốt checklist:

> *"Công trình có thuộc diện phải thẩm duyệt thiết kế phòng cháy chữa cháy không?"*

Trả lời `không`. Checklist hiện ra — **và nói thẳng điều quan trọng**:

> "Chú ý: checklist này có 3 mục, không phải 5. Hai mục kia đã bị loại vì không áp dụng cho trường hợp vừa mô tả. Đó chính là vòng lặp ở đầu bài — bị xoá ngay tại đây."

#### Thao tác 2 — Truy vết nguồn *(khoảng 30 giây)*

Chỉ vào khối "Đã kiểm chứng nguồn" bên phải:

> "Mỗi mục trong checklist truy về một yêu cầu giấy tờ cụ thể trong danh mục đã được kiểm duyệt, kèm liên kết tới trang công bố trên Cổng Dịch vụ công. Không có mục nào do mô hình tự nghĩ ra."

Nếu khối hiện trạng thái `fallback` ("dùng snapshot đã kiểm duyệt") — **đừng né, hãy dùng nó**:

> "Ở đây hệ thống đang nói thật rằng nó không đọc được trang gốc ngay lúc này nên đang dùng bản snapshot có checksum. Chúng tôi cố tình không gắn dấu 'đã kiểm chứng' cho thứ chưa thực sự đọc được — kể cả khi request trả về HTTP 200."

Đó là một trong những câu ăn điểm nhất của cả buổi.

#### Thao tác 3 — Cổng cán bộ *(khoảng 30 giây)*

Chuyển tab `/officer`, mở một hồ sơ có cảnh báo:

> "Cán bộ thấy các phát hiện, và luôn có quyền bác bỏ phát hiện của AI. Quan trọng hơn: AI **không thể** gắn nhãn 'lỗi' cho hồ sơ. Chỉ rule engine khai báo mới làm được điều đó."

Nếu giám khảo tỏ ra quan tâm, mở `src/models/validation.py:28` và chỉ vào validator — nhưng chỉ khi họ hỏi.

### [3:00–4:00] Khả thi kinh doanh

> "Người dân dùng miễn phí. Cơ quan hành chính trả tiền — thuê bao theo đơn vị hành chính cộng phí triển khai.
>
> Chi phí biến đổi mỗi hồ sơ là khoảng **420 đồng**. Con số này tính từ hệ thống thật, không phải ước lượng: chúng tôi đo tỉ lệ token tiếng Việt bằng API đếm token trên chính prompt của mình — 2,17 ký tự một token, tức tốn gần gấp đôi tiếng Anh.
>
> Ở mức chi phí đó, miễn phí cho người dân là bền vững chứ không phải trợ giá tạm thời. Và nút thắt mở rộng **không phải hạ tầng** — mà là kiểm duyệt dữ liệu thủ tục."

Chốt bằng chỉ số:

> "Chúng tôi đo một chỉ số duy nhất: **tỷ lệ hồ sơ được tiếp nhận ngay lần nộp đầu tiên**. Không đo lượt chat — người dân dùng ít mà xong việc mới là kết quả tốt."

### [4:00–5:00] Tầm nhìn & Đề nghị

Lộ trình 3 giai đoạn, mỗi giai đoạn bác bỏ một giả định:

1. **Một xã, năm thủ tục** — kiểm chứng: hướng dẫn theo tình huống có thật sự tăng tỷ lệ đạt lần đầu không.
2. **Mở rộng nhóm thủ tục** — đo chi phí biên thêm một thủ tục.
3. **Nhân rộng trong tỉnh** — kiểm chứng bộ thủ tục kiểm duyệt có dùng lại được không.

Kết bằng **Đề nghị cụ thể**, không kết bằng lời cảm ơn chung chung:

> "Chúng tôi cần một UBND cấp xã đồng ý chạy pilot Giai đoạn 1 và cho tiếp cận số liệu tỷ lệ hồ sơ trả lại hiện tại."

---

## 3. Câu hỏi giám khảo sẽ hỏi

Chuẩn bị sẵn, trả lời ngắn.

**"Làm sao đảm bảo AI không nói sai luật?"**
> Kiến trúc, không phải lời dặn trong prompt. Nội dung pháp lý đi qua danh mục và rule khai báo, không qua mô hình. Và `ValidationIssue` chặn ở tầng kiểu dữ liệu: AI **không thể** phát severity `error` — thử tạo cũng ném exception. Chi tiết ở `docs/GUARDRAILS.md`.

**"Nếu AI không biết thì sao?"**
> Nó nói "chưa đủ căn cứ" và khuyên hỏi cán bộ. Chúng tôi theo dõi tỷ lệ này như một chỉ số — nhưng đọc nó là *danh mục còn thiếu*, không phải *mô hình kém*.

**"Độ chính xác bao nhiêu?"**
> Trên bộ câu diễn đạt tự nhiên không có trong danh mục: 11/15. Trên bộ giữ riêng không dùng để tinh chỉnh: 9/15. Nhưng chỉ số chúng tôi thực sự chặn là **tỉ lệ chốt nhầm thủ tục — 0/60**, và nó là cổng CI chặn merge. Chốt nhầm làm sai toàn bộ checklist phía sau, nên tệ hơn nhiều so với thành thật hỏi lại.

> Trả lời như vậy mạnh hơn là nói "100%". Nếu ai đó nêu con số 30/30 in-catalog, hãy tự chỉ ra nó có tính vòng tròn trước khi giám khảo chỉ ra.

**"Khác gì ChatGPT?"**
> ChatGPT không biết thủ tục này thay đổi theo nghị định nào tháng trước, và không chịu trách nhiệm được. Chúng tôi khoá nội dung vào danh mục đã kiểm duyệt, có test tự động bắt buộc URL nguồn phải trỏ đúng mã thủ tục quốc gia của chính thủ tục đó.

**"Đã có người dùng thật chưa?"**
> Chưa. Đó là lý do Giai đoạn 1 của pilot tồn tại, và là lý do trong tài liệu kinh doanh chúng tôi đánh dấu rõ 6 số liệu còn thiếu thay vì điền số phỏng đoán.

> Trả lời thẳng. Bịa số liệu người dùng là cách nhanh nhất để mất niềm tin nếu bị hỏi sâu.

**"Team làm được bao nhiêu trong 48 giờ?"**
> 333 test, 75 endpoint, 5 thủ tục với 17 rule khai báo, CI có cổng an toàn riêng. Và hai lỗi thật đã tìm ra rồi sửa bằng eval giữ riêng — trong đó có một lỗi đặc thù tiếng Việt: bỏ dấu làm "chứng minh" trùng "chung mình", khiến hệ thống chốt nhầm thủ tục.

---

## 4. Những điều **không** làm

| Đừng | Vì sao |
|---|---|
| Mở đầu bằng sơ đồ kiến trúc | Sai thứ tự — outcome trước, công nghệ sau |
| Nói "AI của chúng tôi rất thông minh" | Không kiểm chứng được, và không phải điểm mạnh của sản phẩm này |
| Đi tuần tự hết mọi màn hình | Demo là để chứng minh một luận điểm, không phải hướng dẫn sử dụng |
| Né trạng thái `fallback` khi nó hiện | Đó là bằng chứng về tính trung thực — dùng nó |
| Báo "330/330 test PASS" | Có 1 test fail trên local. Nói thật kèm giải thích CI xanh sẽ đáng tin hơn |
| Đưa số liệu thị trường không nguồn | Bị hỏi nguồn mà không có là mất toàn bộ độ tin cậy đã xây |
| Sửa code trong lúc demo | Không bao giờ |

---

## 5. Nếu có sự cố

| Sự cố | Xử lý ngay |
|---|---|
| Backend không phản hồi | Chuyển sang tab đã tải sẵn, nói tiếp phần kinh doanh, quay lại sau |
| Chat trả lời chậm | "Đang gọi mô hình — trong lúc chờ, chú ý phần nguồn bên phải" |
| Không nhận diện được thủ tục | **Đây là hành vi đúng** — chỉ vào nó: "Hệ thống lùi về hỏi lại thay vì đoán bừa. Đó là thiết kế." |
| Mất mạng | Nhận diện thủ tục, checklist, rule engine vẫn chạy. Chỉ mất hỏi đáp mở |
| Trang trắng | Tải lại. Nếu vẫn trắng, dùng ảnh chụp màn hình dự phòng |

**Luôn có sẵn:** ảnh chụp màn hình của cả ba thao tác, để trong một thư mục mở sẵn.

---

## 6. Tài liệu dẫn chiếu khi bị hỏi sâu

| Câu hỏi về | Mở tài liệu |
|---|---|
| An toàn, grounding | `docs/GUARDRAILS.md` |
| Kiến trúc agent | `docs/Agent-Features.md` |
| Số đo, eval | `docs/EVAL-METRICS.md` |
| Chi phí, khách hàng, pilot | `docs/business-viability-pilot.md` |
| API | `docs/API-Reference.md` |
| Triển khai | `docs/Deployment-Guide.md` |
| CI | `docs/CI-Explained.md` |
