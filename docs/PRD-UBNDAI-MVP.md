# PRD — UBNDAI MVP

> Yêu cầu sản phẩm cho bản MVP: giải quyết vấn đề gì, cho ai, phạm vi tới đâu, và **cố ý không làm gì**.
>
> Tài liệu này mô tả **trạng thái đã xây xong**, không phải kế hoạch. Những gì chưa có nằm ở §7–§8.

---

## 1. Vấn đề

Vòng lặp lãng phí trong tiếp nhận hồ sơ hành chính:

```
Người dân tra thủ tục  →  chuẩn bị theo cách hiểu của mình
        ↑                          ↓
   bổ sung, đi lại      ←   cán bộ phát hiện thiếu/sai, trả lại
```

Mỗi vòng tốn **một lượt đi lại của người dân** và **một lượt kiểm tra của cán bộ**.

Ba nguyên nhân gốc:

1. Thủ tục có **điều kiện phụ thuộc tình huống**, nhưng trang tra cứu liệt kê *toàn bộ* thành phần hồ sơ kể cả phần không áp dụng.
2. Người dân **không biết mình không biết gì** — công cụ tìm kiếm chỉ trả lời câu đã hỏi, không hỏi ngược.
3. Sai sót chỉ lộ ra **tại quầy** — không có vòng kiểm tra nào trước khi nộp.

---

## 2. Người dùng

| Nhóm | Vai trò | Trả tiền? |
|---|---|---|
| **Người dân** | Chuẩn bị hồ sơ | Không — miễn phí vĩnh viễn |
| **Cán bộ tiếp nhận** (UBND cấp xã, Công an cấp xã/tỉnh) | Xử lý hồ sơ, xác nhận phát hiện | Đơn vị trả |
| **Cơ quan quản lý cấp tỉnh** | Theo dõi điểm nghẽn thủ tục | Có (giai đoạn sau) |

Chi tiết phân khúc và mô hình kinh doanh: `docs/business-viability-pilot.md`.

---

## 3. Tuyên bố giá trị

> **UBNDAI giúp cơ quan hành chính tăng tỷ lệ hồ sơ đạt ngay lần nộp đầu tiên, bằng cách hướng dẫn người dân theo đúng tình huống của họ và kiểm tra hồ sơ trước khi nộp — mọi câu trả lời đều truy vết được về nguồn công bố chính thức.**

Vế cuối là điều kiện cần để bán được, không phải tính năng cộng thêm. Một chatbot trả lời trôi chảy nhưng không chịu trách nhiệm được về nội dung thì cơ quan nhà nước không thể triển khai.

---

## 4. Phạm vi MVP — đã xây xong

### 4.1 Luồng người dân

| # | Yêu cầu | Trạng thái | Bằng chứng |
|---|---|:---:|---|
| P1 | Hỏi bằng ngôn ngữ tự nhiên, hệ thống nhận diện thủ tục | ✅ | `EVAL-EVIDENCE` TC4 |
| P2 | Không chắc thì **hỏi lại**, không đoán | ✅ | TC3 · chốt nhầm 0/60 |
| P3 | Hỏi làm rõ trước khi chốt checklist | ✅ | TC3 `pending_action` |
| P4 | Checklist **lọc theo tình huống** | ✅ | TC1 — 3/4/5 mục tuỳ trả lời |
| P5 | Mục không áp dụng hiện kèm **lý do**, không bị giấu | ✅ | TC2 |
| P6 | Mỗi mục truy vết về `DocumentRequirement` + nguồn công bố | ✅ | TC7 |
| P7 | Tải giấy tờ lên, OCR trích xuất trường | ✅ | `test_ocr_pipeline` 19/19 |
| P8 | OCR không chắc → chuyển người thật, không tự điền | ✅ | `GUARDRAILS` lớp 5 |
| P9 | Sinh bản nháp đơn (HTML/DOCX) từ template | ✅ | `/api/v1/drafts/*` |
| P10 | Nộp hồ sơ, theo dõi dòng thời gian | ✅ | `/api/v1/citizen/*` |

### 4.2 Luồng cán bộ

| # | Yêu cầu | Trạng thái |
|---|---|:---:|
| O1 | Danh sách hồ sơ, nhận xử lý, chuyển trạng thái qua state machine | ✅ |
| O2 | Xem phát hiện; **chấp nhận / bác bỏ / chuyển cấp** | ✅ |
| O3 | Xem và sửa trường OCR trích xuất | ✅ |
| O4 | Tạo yêu cầu bổ sung gửi người dân | ✅ |
| O5 | Dashboard: phân bố trạng thái, loại hồ sơ, bất thường | ✅ |
| O6 | Cách ly theo tổ chức — không đọc được hồ sơ đơn vị khác | ✅ |

> **O2 là yêu cầu thiết kế, không phải tiện ích.** Cán bộ **luôn** phải bác bỏ được phát hiện của AI. Đi kèm ràng buộc ở §5.

### 4.3 Nền tảng

| # | Yêu cầu | Trạng thái |
|---|---|:---:|
| F1 | Chạy được khi **không có** LLM key / index / mạng ngoài | ✅ TC8 |
| F2 | Thêm thủ tục = sửa JSON + YAML, **không sửa code** | ✅ |
| F3 | Xác thực JWT + phân quyền theo vai trò; hỗ trợ OIDC + MFA | ✅ |
| F4 | Migration tự chạy khi deploy | ✅ |
| F5 | CI có cổng an toàn riêng | ✅ `CI-Explained` |

---

## 5. Yêu cầu phi chức năng bắt buộc

Đây là các ràng buộc **không được đánh đổi** để lấy tính năng.

| # | Ràng buộc | Cưỡng chế bằng |
|---|---|---|
| N1 | **AI không được gắn nhãn `error` cho hồ sơ** | Kiểu dữ liệu — `validation.py:28` ném exception |
| N2 | Mọi mục checklist truy về `DocumentRequirement` | Kiến trúc — LLM không có đường chèn mục |
| N3 | Thiếu nguồn → nói "chưa đủ căn cứ", không đoán | Prompt + ngữ cảnh giới hạn top-3 |
| N4 | OCR dưới ngưỡng tin cậy → `needs_human_review` | Ngưỡng số 0,85 |
| N5 | Không gắn "đã kiểm chứng" cho nguồn chưa đọc được | Trạng thái `ready`/`fallback` tách bạch |
| N6 | Trích dẫn phải mở đúng thủ tục đó | Test CI |
| N7 | **Tỉ lệ chốt nhầm thủ tục = 0** | Cổng CI chặn merge |

N1 và N7 là hai ràng buộc quan trọng nhất. Chi tiết: `docs/GUARDRAILS.md`.

---

## 6. Cố ý **không** làm trong MVP

| Không làm | Vì sao |
|---|---|
| Nộp hồ sơ trực tiếp lên Cổng DVC quốc gia | Cần tích hợp và thoả thuận cấp bộ; ngoài phạm vi |
| Thanh toán phí trực tuyến | Không phải nút thắt của bài toán |
| Tự động **quyết định** hồ sơ hợp lệ hay không | Vượt thẩm quyền của phần mềm. AI đề xuất, người quyết định |
| Chatbot trả lời mọi lĩnh vực hành chính | 5 thủ tục làm đúng hơn 500 thủ tục làm ẩu |
| Ứng dụng di động riêng | Web responsive đủ cho MVP |
| Tối ưu chi phí LLM | ~410 VNĐ/hồ sơ — chưa phải vấn đề |
| Đo engagement (lượt chat, thời gian trên trang) | Người dân dùng **ít** mà xong việc mới là kết quả tốt |

Dòng cuối là quyết định sản phẩm có chủ đích: tối ưu theo engagement sẽ dẫn sản phẩm này đi sai hướng.

---

## 7. Độ phủ hiện tại

| Hạng mục | Số lượng |
|---|---|
| Thủ tục | **5** — khai sinh, kết hôn, tạm trú, căn cước, giấy phép xây dựng |
| Rule khai báo | **17** |
| Endpoint API | **75** |
| Test | **333 pass / 334** |

---

## 8. Khoảng trống đã biết

Xếp theo mức độ rủi ro.

| # | Khoảng trống | Mức | Ghi ở |
|---|---|:---:|---|
| 1 | **Tính đúng đắn dữ liệu thủ tục** — không test nào bắt được | **Cao** | `GUARDRAILS`, `KnowledgeBase-Guide` §6 |
| 2 | `JWT_SECRET` và `ENABLE_DEMO_AUTH` mặc định không an toàn | **Cao** | `Authorization-Spec` §8 |
| 3 | Độ phủ nhận diện 60% trên bộ held-out | Trung bình | `EVAL-METRICS` §5 |
| 4 | Chưa có eval cho chất lượng node `answer` | Trung bình | `EVAL-METRICS` §6 |
| 5 | Chưa có nhật ký kiểm toán ai xem hồ sơ nào | Trung bình | `Authorization-Spec` §8 |
| 6 | Chưa đo latency, chưa có telemetry usage | Thấp–TB | `COST-REPORT` §8 |
| 7 | Frontend chưa nằm trong CI | Thấp | `CI-Explained` §7 |
| 8 | Chưa có người dùng thật | — | `business-viability-pilot` §7 |

---

## 9. Tiêu chí thành công

**Chỉ số Bắc Đẩu: tỷ lệ hồ sơ được tiếp nhận ngay lần nộp đầu tiên.**

Chọn vì nó là chỉ số duy nhất mà cả ba bên cùng có lợi khi nó tăng — người dân bớt đi lại, cán bộ bớt việc vô ích, cơ quan cải thiện chỉ số đánh giá — và không thể "làm đẹp" bằng cách tăng lượt dùng.

Tiêu chí loại: **0 sai sót về căn cứ pháp lý đến tay người dân**. Đây là điều kiện dừng pilot, không phải chỉ tiêu phấn đấu.

Đầy đủ: `docs/business-viability-pilot.md` §8.
