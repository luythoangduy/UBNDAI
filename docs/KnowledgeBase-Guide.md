# Knowledge Base Guide — UBNDAI

> Cách tri thức thủ tục được tổ chức, đánh chỉ mục, truy hồi — và **cách thêm một thủ tục mới**.
>
> Điểm cần nắm trước: đây **không phải** một kho tài liệu để mô hình đọc tự do. Nó là **danh mục có cấu trúc** mà mọi mục trong checklist phải truy vết về được. Sự khác biệt đó là lý do hệ thống có thể dùng trong hành chính công.

---

## 1. Hai tầng tri thức

| Tầng | Nguồn | Vai trò | Mô hình được đụng vào? |
|---|---|---|---|
| **Danh mục thủ tục** | `data/procedures/*.json` | Nội dung pháp lý: thành phần hồ sơ, căn cứ, biểu mẫu | **Không** — chỉ đọc để trích |
| **Rule kiểm tra** | `rules/*.yaml` | Điều kiện hợp lệ của hồ sơ | **Không** — chỉ rule engine đọc |
| *(phụ)* Văn bản pháp luật | `data/legal/` + index riêng | Ngữ cảnh cho hỏi đáp mở | Có — qua top-3 đoạn |

Tầng 1 và 2 là **nguồn sự thật**. Tầng 3 chỉ phục vụ hỏi đáp mở và không được sinh ra checklist.

---

## 2. Cấu trúc một thủ tục

Ví dụ rút gọn từ `data/procedures/giay_phep_xay_dung.json`:

```json
{
  "id": "giay_phep_xay_dung",
  "national_code": "1.013225",
  "name": "Cấp giấy phép xây dựng mới đối với công trình cấp III, cấp IV và nhà ở riêng lẻ",
  "agency": "UBND cấp xã",
  "legal_basis": ["Luật Xây dựng năm 2014", "Nghị định 175/2024/NĐ-CP", ...],
  "processing_days": 15,
  "aliases": [...],
  "example_queries": [...],
  "negative_keywords": [...],
  "required_token_groups": [["giấy","phép","xây","dựng"], ...],
  "clarifying_questions": [...],
  "requirements": [...],
  "form_templates": [...],
  "source_url": "https://vpcp.dichvucong.gov.vn/...?ma_thu_tuc=1.013225"
}
```

### Trường phục vụ nhận diện

| Trường | Tác dụng | Cạm bẫy |
|---|---|---|
| `aliases` | Cách gọi dân dã. Khớp chính xác → điểm 1.0 | **Alias ngắn rất nguy hiểm** — xem §5 |
| `example_queries` | Câu hỏi mẫu, dùng cho fuzzy | — |
| `negative_keywords` | **Chặn cứng** → điểm 0.0, xét trước mọi thứ khác | Quá rộng sẽ chặn nhầm ca đúng |
| `required_token_groups` | Đủ nhóm token → 0.95 | **Túi từ, không xét liền kề** — "khai báo"+"sinh viên" từng khớp `['khai','sinh']` |

### Trường phục vụ checklist

`clarifying_questions` có `key`, và `requirements[].condition` tiêu thụ chính `key` đó:

```json
"clarifying_questions": [
  {"key": "cong_trinh_yeu_cau_pccc", "text": "...", "answer_type": "boolean"}
],
"requirements": [
  {"code": "giay_chung_nhan_tham_duyet_pccc",
   "condition": "answers.cong_trinh_yeu_cau_pccc == true",
   "condition_label": "Áp dụng khi công trình thuộc diện phải thẩm duyệt PCCC"}
]
```

Đây là cơ chế tạo ra checklist theo tình huống. `condition_label` là phần **hiển thị cho người dân** — bắt buộc viết dễ hiểu, vì mục không áp dụng vẫn hiện kèm lý do (`docs/EVAL-EVIDENCE.md` TC2).

---

## 3. Truy hồi

Ba tín hiệu, hợp nhất bằng reciprocal rank fusion:

| Tín hiệu | Vị trí | Mạnh ở |
|---|---|---|
| **Identity score** | `retrieval/__init__.py:119` | Khớp tên/alias/token — quyết định nhận diện thủ tục |
| **BM25** | `retrieval/bm25.py` | Từ khoá; có bản in-memory dựng thẳng từ catalog |
| **Vector** | `retrieval/chroma_client.py` + `embeddings.py` (BGE-M3) | Ngữ nghĩa |

### Thang điểm identity

```
negative_keywords khớp        → 0.0    (chặn cứng, xét TRƯỚC)
name/alias khớp trọn từ       → 1.0
đủ required_token_groups      → 0.95
còn lại                       → fuzzy: 0.7·phủ_cụm + 0.3·phủ_truy_vấn
```

Ba ngưỡng quyết định có chốt thủ tục hay không (`src/config.py:53-55`):

```python
identify_confidence_threshold = 0.55
identify_min_relevance        = 0.6
identify_min_margin           = 0.15
```

`identify_min_margin` là ngưỡng đáng giá nhất: hai thủ tục điểm sát nhau → **hỏi lại** thay vì chọn cái nhỉnh hơn.

### Suy giảm mềm

Chưa index Chroma → chỉ BM25. Chưa build cache BM25 → dựng in-memory từ `data/procedures/*.json`. Nhờ vậy **clone repo xong chạy được ngay**.

```bash
# Tuỳ chọn: dựng index dense + cache BM25
python scripts/index_procedures.py --build-bm25
```

---

## 4. Thêm một thủ tục mới

```bash
# 1. Tạo data/procedures/<id>.json  (theo cấu trúc §2)
# 2. Tạo rules/<id>.yaml            (nếu cần kiểm tra hợp lệ)
# 3. Kiểm ngay:
python -m pytest tests/test_procedure_source_urls.py -q   # URL nguồn hợp lệ
python scripts/eval_identify.py                            # chốt nhầm phải = 0
```

**Danh sách kiểm bắt buộc:**

| # | Việc | Vì sao |
|---|---|---|
| 1 | `source_url` trỏ `vpcp.dichvucong.gov.vn` với **đúng** `ma_thu_tuc` | Test khoá; trích dẫn mở ra thủ tục khác tệ hơn không trích dẫn |
| 2 | Mọi `legal_basis` là văn bản **có thật, còn hiệu lực** | Không test nào bắt được — xem §6 |
| 3 | Mỗi `requirements[].code` có `note` dẫn điều khoản | Để người dân/cán bộ đối chiếu |
| 4 | `condition` chỉ tham chiếu `key` có trong `clarifying_questions` | Sai key → điều kiện không bao giờ đúng |
| 5 | Alias mới **không** rút xuống ≤2 token sau khi bỏ dấu | §5 |
| 6 | `negative_keywords` loại các thủ tục dễ nhầm | Tránh hút nhầm truy vấn |
| 7 | Chạy `eval_identify.py` — chốt nhầm = 0 | Cổng CI |
| 8 | **Cán bộ chuyên môn ký duyệt** | Điều kiện bắt buộc của pilot Giai đoạn 1 |

---

## 5. Cạm bẫy khi viết alias *(đã trả giá thật)*

Ba lỗi đã xảy ra trong chính dự án này, đều dẫn tới **chốt nhầm thủ tục**:

| Cơ chế | Ví dụ | Hậu quả |
|---|---|---|
| `required_token_groups` là **túi từ**, không xét liền kề | `['khai','sinh']` khớp "**khai** báo … **sinh** viên" | Chốt `khai_sinh` cho câu hỏi về tạm trú |
| Cụm ≤2 token sau khi bỏ dấu cho điểm fuzzy quá cao | "chứng minh thư" → `{chung, minh}`, trùng "về **chung** … tụi **mình**" | Chốt `can_cuoc` cho câu hỏi về kết hôn |
| Bỏ dấu tạo **đồng tự** | "cưới" → `cuoi` ≡ "cuối" | Chốt `ket_hon` cho "nộp hồ sơ vào **cuối** năm" |

**Quy tắc rút ra:**

1. Alias nên **từ 3 token trở lên** sau khi bỏ dấu và loại token chung.
2. Trước khi thêm, kiểm cụm đó bỏ dấu ra chuỗi gì và chuỗi đó có trùng từ thông dụng nào không.
3. Tránh alias quá chung ("giấy tờ tùy thân" từng fuzzy-khớp mọi câu có "cần giấy tờ gì").
4. Thêm alias xong **phải** chạy `eval_identify.py`.

Kiểm nhanh cụm ngắn trong catalog:

```bash
python - << 'EOF'
import json, glob
from src.services.retrieval.common import tokenize
from src.services.retrieval import _IDENTITY_GENERIC_TOKENS as G
for p in sorted(glob.glob('data/procedures/*.json')):
    d = json.load(open(p, encoding='utf-8'))
    for a in d.get('aliases', []):
        t = set(tokenize(a)) - G
        if len(t) < 3:
            print(f"{d['id']:<20} «{a}» -> {sorted(t)}  ⚠ ngắn")
EOF
```

Chi tiết ba lỗi: `docs/EVAL-METRICS.md` §4 và §4b.

---

## 6. Rủi ro lớn nhất: dữ liệu sai

Không guardrail kỹ thuật nào bắt được **căn cứ pháp lý sai**, vì dữ liệu sai trông giống hệt dữ liệu đúng.

Đã xảy ra thật: catalog `giay_phep_xay_dung` từng chứa *"Luật Xây dựng số 135/2025/QH15"* và *"Nghị định 217/2026/NĐ-CP"* — **cả hai không tồn tại** — kèm ghi chú sai rằng nhà ở riêng lẻ được miễn giấy phép từ 01/7/2026. Nếu đến tay người dân, hậu quả là xây dựng không phép.

Cùng đợt: toàn bộ 5 `source_url` đã chết do Cổng DVC đổi hạ tầng.

**Hệ quả tới quy trình:**

- Cán bộ chuyên môn **ký duyệt** catalog trước khi bật cho người dân (pilot Giai đoạn 1).
- Tiêu chí **0 sai sót về căn cứ pháp lý** là điều kiện dừng pilot.
- Đây là lý do chi phí thật của sản phẩm nằm ở kiểm duyệt dữ liệu, không nằm ở tầng mô hình (`docs/business-viability-pilot.md` §6.3).

---

## 7. Đồng bộ với nguồn công bố

`docs/procedure-sync.md` mô tả quy trình. Công cụ:

```bash
python scripts/sync_procedures.py      # đồng bộ từ nguồn công bố
python scripts/index_procedures.py     # dựng lại index sau khi đổi catalog
```

Khi kéo nguồn live thất bại, hệ thống dùng snapshot có checksum và **nói rõ** trạng thái `fallback` — không gắn dấu "đã kiểm chứng" cho thứ chưa đọc được, kể cả khi HTTP trả 200 (`docs/GUARDRAILS.md` lớp 6).
