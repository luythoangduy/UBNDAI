# Khả thi kinh doanh & Lộ trình pilot

> **Quy ước về số liệu.** Tài liệu này phân biệt rõ ba loại con số:
> - **[ĐO]** — đo trực tiếp từ mã nguồn/hệ thống trong repo này, có thể tái lập bằng lệnh ghi kèm.
> - **[MÔ HÌNH]** — suy ra từ số [ĐO] bằng công thức được ghi rõ, có thể kiểm tra lại.
> - **[CẦN SỐ LIỆU THẬT]** — chưa có nguồn xác thực. **Không được dùng trong pitch nếu chưa bổ sung nguồn.**
>
> Quy ước này theo `AGENTS.md` §5 (không bịa dữ liệu) và nguyên tắc pitching *"nếu dùng số liệu cụ thể, phải luôn có nguồn xác thực"*.

---

## 1. Tóm tắt điều hành

UBNDAI bán **tỷ lệ hồ sơ được tiếp nhận ngay lần nộp đầu tiên**, không bán chatbot.

Người trả tiền là **cơ quan hành chính** (UBND cấp xã và đơn vị tương đương), không phải người dân. Người dân dùng miễn phí — đây là điều kiện bắt buộc về mặt chính trị lẫn đạo đức đối với dịch vụ công, đồng thời là điều khiến sản phẩm có thể được cơ quan nhà nước bảo trợ triển khai.

Điểm mấu chốt về khả thi: **chi phí biến đổi cho mỗi hồ sơ là ~0,016 USD (~420 VNĐ)** [MÔ HÌNH, §6]. Ở mức đó, chi phí AI không phải là rào cản triển khai — rào cản là quy trình phê duyệt và chất lượng dữ liệu thủ tục. Điều này định hình toàn bộ lộ trình pilot ở §7: ta tối ưu cho **niềm tin và tính đúng đắn**, không tối ưu cho chi phí.

---

## 2. Bài toán và chi phí của hiện trạng

Vòng lặp lãng phí trong tiếp nhận hồ sơ hành chính hiện nay:

1. Người dân tra cứu thủ tục trên Cổng DVC → nội dung viết theo ngôn ngữ văn bản pháp quy, không theo tình huống cụ thể của họ.
2. Người dân chuẩn bị hồ sơ theo cách hiểu của mình.
3. Cán bộ tiếp nhận phát hiện thiếu/sai giấy tờ → trả lại.
4. Người dân bổ sung → quay lại bước 2.

Mỗi vòng lặp tiêu tốn **một lượt đi lại của người dân** và **một lượt kiểm tra của cán bộ**. Đây là chi phí kép: chi phí xã hội (thời gian, đi lại của công dân) và chi phí vận hành (thời gian cán bộ dành cho hồ sơ không hợp lệ thay vì hồ sơ hợp lệ).

Ba nguyên nhân gốc mà sản phẩm này nhắm vào:

| Nguyên nhân gốc | Vì sao công cụ hiện có không giải quyết được | UBNDAI xử lý thế nào |
|---|---|---|
| Thủ tục có **điều kiện phụ thuộc tình huống** | Trang tra cứu liệt kê *toàn bộ* thành phần hồ sơ, kể cả phần chỉ áp dụng cho một số trường hợp | Rule engine khai báo (`rules/*.yaml`) + câu hỏi làm rõ, sinh checklist đúng theo tình huống |
| Người dân **không biết mình không biết gì** | Tìm kiếm chỉ trả lời câu đã hỏi, không hỏi ngược | LangGraph node `clarify` chủ động hỏi trước khi chốt checklist |
| Sai sót chỉ lộ ra **tại quầy** | Không có vòng kiểm tra nào trước khi nộp | OCR + kiểm tra tính đầy đủ trước khi người dân rời nhà |

> **[CẦN SỐ LIỆU THẬT]** Tỷ lệ hồ sơ bị trả lại lần đầu, số lượt đi lại trung bình mỗi hồ sơ, thời gian cán bộ xử lý một hồ sơ bị trả lại. Nguồn cần lấy: báo cáo kiểm soát TTHC của địa phương pilot, hoặc số liệu Bộ phận Một cửa. **Đây là con số quan trọng nhất còn thiếu** — nó là mẫu số của toàn bộ luận điểm ROI ở §5.

---

## 3. Nhóm khách hàng mục tiêu

Ba nhóm, phân biệt rõ giữa **người dùng** (dùng sản phẩm) và **người mua** (ký hợp đồng, trả tiền).

### 3.1 UBND cấp xã / Bộ phận Một cửa — **người mua chính**

- **Ai**: Đơn vị tiếp nhận trực tiếp 5 nhóm thủ tục đã triển khai trong hệ thống: khai sinh, kết hôn, tạm trú, căn cước, giấy phép xây dựng.
- **Vấn đề nhức nhối**: Khối lượng hồ sơ không hợp lệ chiếm thời gian cán bộ; chỉ số hài lòng và chỉ số giải quyết đúng hạn là tiêu chí đánh giá của đơn vị.
- **Vì sao họ mua**: Cải thiện chỉ số mà không cần tăng biên chế.
- **Đã có gì trong sản phẩm**: Cổng cán bộ (tổng quan / hồ sơ / cảnh báo), phân quyền theo vai trò, cảnh báo phân tầng `error` (từ rule engine) vs `warning`/`info` (từ AI).
- **Ngân sách lấy từ đâu**: [CẦN SỐ LIỆU THẬT] — cần xác định mục chi nào chi trả được (chi thường xuyên CNTT? đề án chuyển đổi số cấp tỉnh?). Đây là câu hỏi quyết định vòng đời bán hàng.

### 3.2 Người dân — **người dùng, không trả tiền**

- **Ai**: Người chuẩn bị hồ sơ cho 5 thủ tục trên, đặc biệt nhóm ít thành thạo văn bản hành chính.
- **Vấn đề**: Không biết cần giấy tờ gì cho *trường hợp của mình*.
- **Vì sao dùng**: Trả lời theo tình huống, có trích dẫn nguồn chính thức, kiểm tra trước khi nộp.
- **Vì sao miễn phí**: Thu phí người dân cho việc tiếp cận thủ tục hành chính là không chấp nhận được về mặt chính sách. Miễn phí cũng là điều kiện để cơ quan nhà nước đứng ra bảo trợ triển khai.

### 3.3 Cơ quan quản lý cấp tỉnh — **người mua mở rộng**

- **Ai**: Sở/ngành phụ trách kiểm soát TTHC và chuyển đổi số.
- **Vấn đề**: Không có dữ liệu định lượng về *chỗ nào* trong quy trình người dân bị vướng.
- **Vì sao mua**: Dữ liệu tổng hợp về điểm nghẽn thủ tục — sản phẩm phụ của việc vận hành, không cần xây thêm.
- **Trạng thái**: Chưa xây dashboard tổng hợp. Đây là hạng mục Giai đoạn 3 (§7).

---

## 4. Đề xuất giá trị

Phát biểu một câu:

> **UBNDAI giúp cơ quan hành chính tăng tỷ lệ hồ sơ đạt ngay lần nộp đầu tiên, bằng cách hướng dẫn người dân theo đúng tình huống của họ và kiểm tra hồ sơ trước khi nộp — mọi câu trả lời đều truy vết được về nguồn công bố chính thức.**

Vế cuối là điểm khác biệt phòng thủ được. Một chatbot thông thường có thể trả lời trôi chảy nhưng không chịu trách nhiệm được về nội dung; một cơ quan nhà nước không thể triển khai thứ như vậy. Kiến trúc grounding của hệ thống (`AGENTS.md` §5) là **điều kiện cần để bán được**, không phải tính năng cộng thêm:

- Mọi mục trong checklist truy về một `DocumentRequirement` trong catalog — không có mục nào do mô hình tự sinh.
- Thiếu căn cứ → hệ thống nói *"chưa đủ căn cứ"*, không đoán.
- Chỉ rule engine mới phát `error`; AI chỉ được phát `warning`/`info`.
- OCR độ tin cậy thấp (< 0,85) → chuyển `needs_human_review`, không tự quyết.
- Nguồn trích dẫn kiểm chứng bằng test tự động (`tests/test_procedure_source_urls.py`) — URL nguồn phải trỏ đúng mã thủ tục quốc gia của chính thủ tục đó.

---

## 5. Mô hình kinh doanh

**Thuê bao theo đơn vị hành chính + phí triển khai ban đầu.**

| Thành phần | Nội dung | Căn cứ |
|---|---|---|
| Phí triển khai (một lần) | Số hoá và kiểm duyệt bộ thủ tục của địa phương, tích hợp, đào tạo cán bộ | Chi phí thật nằm ở **kiểm duyệt dữ liệu thủ tục**, không nằm ở phần mềm — xem §6.3 |
| Thuê bao (định kỳ) | Vận hành, cập nhật khi văn bản pháp quy thay đổi, hỗ trợ | Chi phí biến đổi rất thấp (§6), nên thuê bao chủ yếu bù đắp việc **duy trì tính đúng đắn của dữ liệu** |
| Người dân | Miễn phí vĩnh viễn | §3.2 |

**Mức giá: [CẦN SỐ LIỆU THẬT].** Không đưa con số cụ thể vào pitch khi chưa có căn cứ. Cần: quy mô ngân sách CNTT thực tế của một UBND cấp xã, và giá tham chiếu của các hệ thống một cửa điện tử đang dùng.

**Luận điểm ROI (khung công thức, chưa có số):**

```
Tiết kiệm/năm = (số hồ sơ/năm) × (tỷ lệ trả lại hiện tại − tỷ lệ trả lại sau triển khai)
                × (chi phí xử lý một lượt trả lại)
```

Cả ba biến đều đang là [CẦN SỐ LIỆU THẬT]. Giai đoạn 1 của pilot (§7) được thiết kế **chính là để đo hai biến đầu**.

---

## 6. Kinh tế đơn vị

Đây là phần được tính từ hệ thống thật, không phải ước lượng thị trường.

### 6.1 Số liệu đầu vào [ĐO]

| Thông số | Giá trị | Nguồn |
|---|---|---|
| Model chat | `claude-haiku-4-5` | `src/config.py:38` |
| Giá | 1,00 USD/1M token vào · 5,00 USD/1M token ra | Bảng giá Anthropic hiện hành |
| **Tỉ lệ token tiếng Việt** | **2,17 ký tự/token** | Đo bằng `POST /v1/messages/count_tokens` trên chính prompt planner của hệ thống: 2.703 ký tự → 1.245 token |
| Prompt planner (tĩnh) | 2.594 ký tự | `src/agents/prompts/planner.py` |
| Prompt answer (tĩnh) | 562 ký tự | `src/agents/prompts/answer.py` |
| Ngữ cảnh answer | top-3 đoạn | `src/agents/nodes/answer.py:` lát cắt `[:3]` |
| Cache kết quả nguồn | TTL 3.600 s (120 s khi nguồn lỗi) | `src/config.py:17,21` |

> **Vì sao tỉ lệ 2,17 quan trọng.** Tiếng Anh thường ~4 ký tự/token. Tiếng Việt ở đây tốn token **gần gấp đôi** trên cùng một lượng chữ. Mọi mô hình chi phí quy chiếu từ số liệu tiếng Anh sẽ **thấp hơn thực tế khoảng 2 lần**. Con số này được đo trực tiếp, không suy đoán.

### 6.2 Chi phí mỗi lượt và mỗi hồ sơ [MÔ HÌNH]

Điểm kiến trúc quan trọng: **luồng hướng dẫn chính không gọi LLM.** Node `identify` dùng truy hồi lai (BM25 + vector), `checklist` sinh từ catalog + rule engine. LLM chỉ được gọi ở hai chỗ:

- `planner` — chỉ khi ý định là `general_question`/`unknown` (`src/agents/nodes/planner.py:155`)
- `answer` — hỏi đáp mở

| Lượt | Token vào | Token ra | Chi phí |
|---|---|---|---|
| Planner (structured output) | 1.245 [ĐO] | ~80 | ~0,0017 USD |
| Answer (prompt + 3 đoạn + lịch sử) | ~2.200 | ~280 | ~0,0036 USD |

**Một phiên chuẩn bị hồ sơ** (giả định 8 lượt, trong đó ~3 lượt chạm planner và ~3 lượt chạm answer):

```
3 × 0,0017 + 3 × 0,0036 ≈ 0,016 USD/hồ sơ  (~420 VNĐ ở tỷ giá 26.000 VNĐ/USD)
```

*Giả định cần kiểm chứng ở pilot:* số lượt mỗi phiên, tỷ lệ lượt chạm LLM, độ dài câu trả lời. Đây là các biến duy nhất trong công thức trên chưa được đo trên người dùng thật.

### 6.3 Chi phí chưa định lượng được

| Khoản | Trạng thái |
|---|---|
| OCR (`gpt-5-mini`, `reasoning_effort=minimal`) | **[CẦN SỐ LIỆU THẬT]** — chưa xác minh bảng giá gpt-5-mini. Có cache theo hash ảnh (`ocr_cache_size=128`) nên nộp lại cùng ảnh không tốn phí. Mỗi hồ sơ ~3–5 tài liệu. |
| Hạ tầng (Render + Vercel) | **[CẦN SỐ LIỆU THẬT]** — chưa xác minh giá gói. Là chi phí cố định, không theo hồ sơ. |
| **Kiểm duyệt dữ liệu thủ tục** | **Đây mới là chi phí chi phối.** Cần chuyên môn pháp lý người thật, không tự động hoá được. Xem cảnh báo bên dưới. |

> **Bài học đã trả giá trong chính dự án này.** Trong quá trình rà soát, catalog được phát hiện có **căn cứ pháp lý bịa** (một luật và một nghị định không tồn tại) cùng ghi chú sai về miễn giấy phép xây dựng — nếu đến tay người dân có thể dẫn tới việc xây dựng không phép. Toàn bộ 5 URL nguồn cũng đã chết do Cổng DVC đổi hạ tầng. Điều này chứng minh: **giá trị và chi phí thật của sản phẩm nằm ở việc duy trì dữ liệu thủ tục đúng và còn hiệu lực**, không nằm ở tầng mô hình. Mô hình định giá phải phản ánh đúng điều đó.

### 6.4 Hệ quả chiến lược

Chi phí biến đổi ~420 VNĐ/hồ sơ nghĩa là:

- Chi phí **không** phải rào cản mở rộng quy mô. Không cần "tối ưu chi phí AI" trong 12 tháng đầu.
- Miễn phí cho người dân là bền vững, không phải trợ giá tạm thời.
- Nút thắt tăng trưởng là **quy trình phê duyệt của cơ quan** và **năng lực kiểm duyệt dữ liệu**, không phải hạ tầng.
- Vì vậy pilot (§7) đo **độ chính xác và niềm tin**, không đo chi phí.

---

## 7. Lộ trình pilot

Nguyên tắc: mỗi giai đoạn phải **bác bỏ được một giả định cụ thể** trước khi sang giai đoạn sau.

### Giai đoạn 1 — Một đơn vị, năm thủ tục

**Phạm vi**: 1 UBND cấp xã; đúng 5 thủ tục đã có trong hệ thống.

**Giả định cần kiểm chứng**: *Người dân được hướng dẫn theo tình huống sẽ nộp hồ sơ hợp lệ ngay lần đầu ở tỷ lệ cao hơn rõ rệt.*

**Việc bắt buộc làm trước khi bật cho người dân**:
1. Cán bộ chuyên môn của đơn vị **kiểm duyệt và ký xác nhận** toàn bộ catalog 5 thủ tục — bao gồm căn cứ pháp lý, thành phần hồ sơ, biểu mẫu. Không bỏ qua bước này (xem §6.3).
2. Chốt đường cơ sở: tỷ lệ trả lại hồ sơ hiện tại của chính đơn vị đó.

**Tiêu chí nghiệm thu**:

| Chỉ số | Ngưỡng |
|---|---|
| Tỷ lệ hồ sơ đạt ngay lần nộp đầu (nhóm dùng UBNDAI so với đường cơ sở) | Cải thiện có ý nghĩa — ngưỡng chốt sau khi có đường cơ sở |
| Sai sót nội dung do cán bộ báo cáo | **0 sai sót về căn cứ pháp lý hoặc thành phần hồ sơ** — đây là tiêu chí loại trực tiếp |
| Tỷ lệ hội thoại kết thúc bằng "chưa đủ căn cứ" | Theo dõi — cao nghĩa là catalog thiếu, không phải mô hình kém |
| Cán bộ tiếp tục muốn dùng sau pilot | Có/Không |

**Điều kiện dừng**: Bất kỳ sai sót nào về căn cứ pháp lý đến tay người dân → dừng, truy nguyên, sửa quy trình kiểm duyệt trước khi chạy lại.

### Giai đoạn 2 — Mở rộng nhóm thủ tục, cùng đơn vị

**Giả định cần kiểm chứng**: *Quy trình bổ sung thủ tục mới đủ rẻ và đủ nhanh để nhân rộng.*

Đo cái cần đo: **chi phí biên để thêm một thủ tục** — bao nhiêu giờ công kiểm duyệt pháp lý cho mỗi thủ tục mới. Con số này quyết định mô hình kinh doanh có mở rộng được hay không, và hiện đang là ẩn số lớn nhất.

**Tiêu chí nghiệm thu**: chi phí biên mỗi thủ tục giảm dần theo số thủ tục đã làm (có hiệu ứng học tập), giữ nguyên tiêu chí 0 sai sót.

### Giai đoạn 3 — Nhân rộng trong tỉnh

**Giả định cần kiểm chứng**: *Bộ thủ tục kiểm duyệt ở đơn vị này dùng lại được cho đơn vị khác.*

Đây là giả định quyết định biên lợi nhuận. Nếu thủ tục ở cấp quốc gia đồng nhất, phần lớn công kiểm duyệt dùng lại được và biên lợi nhuận tốt. Nếu mỗi địa phương có biến thể riêng, mô hình trở thành dịch vụ triển khai theo dự án. **Chưa biết câu trả lời** — giai đoạn 3 tồn tại để trả lời câu này.

Hạng mục kèm theo: dashboard tổng hợp điểm nghẽn thủ tục cho cấp tỉnh (§3.3).

---

## 8. Chỉ số theo dõi

**Chỉ số Bắc Đẩu: tỷ lệ hồ sơ được tiếp nhận ngay lần nộp đầu tiên.**

Chọn chỉ số này vì nó là chỉ số duy nhất mà cả ba bên cùng có lợi khi nó tăng: người dân bớt đi lại, cán bộ bớt việc vô ích, cơ quan cải thiện chỉ số đánh giá. Nó cũng không thể bị "làm đẹp" bằng cách tăng lượt dùng.

**Chỉ số phụ trợ**:

| Nhóm | Chỉ số | Vì sao theo dõi |
|---|---|---|
| Tin cậy | Số sai sót nội dung được báo cáo | Tiêu chí loại — phải bằng 0 |
| Tin cậy | Tỷ lệ trả lời "chưa đủ căn cứ" | Đo độ phủ catalog, không phải chất lượng mô hình |
| Tin cậy | Tỷ lệ OCR rơi vào `needs_human_review` | Hiệu chỉnh ngưỡng 0,85 |
| Hiệu quả | Số lượt đi lại trung bình mỗi hồ sơ | Đại lượng đo chi phí xã hội |
| Hiệu quả | Thời gian cán bộ xử lý mỗi hồ sơ | Đại lượng đo ROI |
| Vận hành | Chi phí LLM mỗi hồ sơ | Kiểm chứng mô hình §6.2 trên số thật |

**Chỉ số cố tình KHÔNG dùng**: số lượt chat, thời gian ở trên trang. Với sản phẩm này, người dân dùng *ít* mà xong việc là kết quả tốt. Tối ưu theo engagement sẽ dẫn sản phẩm đi sai hướng.

---

## 9. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Dữ liệu thủ tục sai/hết hiệu lực đến tay người dân | **Cao — nghiêm trọng nhất** | Grounding cưỡng chế bằng kiến trúc; cán bộ ký duyệt catalog trước khi bật; test tự động khoá URL nguồn; tiêu chí 0 sai sót là điều kiện dừng pilot |
| Nguồn công bố đổi hạ tầng, URL chết | **Cao — đã xảy ra một lần** | `tests/test_procedure_source_urls.py` chạy trong CI; snapshot có checksum làm dự phòng; TTL ngắn 120 s khi nguồn lỗi để tự hồi phục |
| Chi phí kiểm duyệt pháp lý không giảm theo quy mô | Trung bình–Cao | Chính là phép thử của Giai đoạn 2 và 3 |
| Vòng phê duyệt của cơ quan kéo dài | Trung bình | Bắt đầu từ 1 đơn vị, 5 thủ tục — phạm vi đủ nhỏ để phê duyệt trong thẩm quyền sẵn có |
| Phụ thuộc một nhà cung cấp mô hình | Thấp | `LLM_PROVIDER` đã trừu tượng hoá (`anthropic`/`gemini`); OCR đã tách riêng key và model |
| Dữ liệu cá nhân trong hồ sơ | Trung bình | Lưu trữ riêng (`storage_root`), phân quyền theo vai trò, OIDC + MFA đã có đường dẫn cấu hình |

---

## 10. Danh mục số liệu còn thiếu

Xếp theo mức độ ảnh hưởng tới luận điểm kinh doanh. **Không đưa con số bịa vào pitch để lấp các ô này.**

| # | Số liệu | Ảnh hưởng | Lấy ở đâu |
|---|---|---|---|
| 1 | Tỷ lệ hồ sơ bị trả lại hiện tại | Mẫu số của toàn bộ ROI | Báo cáo kiểm soát TTHC / Bộ phận Một cửa của địa phương pilot |
| 2 | Chi phí xử lý một lượt hồ sơ bị trả lại | Nhân tử của ROI | Phỏng vấn cán bộ + đo thời gian ở Giai đoạn 1 |
| 3 | Số giờ công kiểm duyệt mỗi thủ tục | Quyết định mô hình có mở rộng được không | Đo trực tiếp ở Giai đoạn 2 |
| 4 | Ngân sách CNTT thực tế của UBND cấp xã | Quyết định khung giá | Khảo sát / mục chi công khai |
| 5 | Giá gpt-5-mini và gói Render/Vercel | Hoàn thiện §6.3 | Bảng giá nhà cung cấp |
| 6 | Số lượt trung bình mỗi phiên | Kiểm chứng §6.2 | Log của Giai đoạn 1 |

---

## Phụ lục — Cách tái lập số liệu [ĐO]

```bash
# Tỉ lệ token tiếng Việt (2,17 ký tự/token)
# Gửi chính prompt planner của hệ thống tới /v1/messages/count_tokens
# với model claude-haiku-4-5 → 2.703 ký tự trả về 1.245 token.

# Kích thước prompt tĩnh
wc -m src/agents/prompts/planner.py src/agents/prompts/answer.py

# Các điểm gọi LLM trong toàn pipeline
grep -rn "ainvoke(" src/agents/ src/services/ --include="*.py"

# Cấu hình model và cache
grep -n "llm_model\|ocr_llm_model\|cache_ttl\|ocr_cache_size" src/config.py
```
