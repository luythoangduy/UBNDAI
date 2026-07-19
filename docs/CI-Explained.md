# CI Explained — UBNDAI

> Giải thích pipeline CI: chạy gì, chặn gì, và **vì sao chặn cái đó mà không chặn cái kia**.

---

## 1. Pipeline

`.github/workflows/ci.yml` — chạy trên `push` vào `main` và trên mọi `pull_request`.

```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11.9"
      - run: pip install -e ".[dev]"
      - run: ruff check src/ tests/
      - run: pytest tests/ -v --tb=short
      - name: Eval nhận diện thủ tục (chốt nhầm phải = 0)
        run: python scripts/eval_identify.py
```

| Bước | Chặn khi | Thời gian |
|---|---|---|
| `ruff check src/ tests/` | Có lỗi lint | vài giây |
| `pytest tests/ -v` | Bất kỳ test nào fail | ~20 s |
| `python scripts/eval_identify.py` | **Có ca chốt nhầm thủ tục** | ~10 s |

Toàn bộ pipeline chạy **offline**: không cần LLM API key, không cần index Chroma, không cần dịch vụ ngoài.

---

## 2. Vì sao CI chạy được mà không cần API key

Đây là tính chất thiết kế, không phải may mắn, và nó đáng nói vì nhiều dự án AI không làm được:

| Thành phần | Cách suy giảm mềm khi thiếu phụ thuộc |
|---|---|
| Nhận diện thủ tục | Chưa index Chroma → chỉ BM25. Chưa build cache BM25 → **BM25 in-memory dựng thẳng từ `data/procedures/*.json`** |
| Định tuyến ý định | Rule-based chạy trước; không có LLM key → vẫn định tuyến được (`src/agents/nodes/planner.py:239`) |
| Kiểm tra hồ sơ | Rule engine khai báo, không cần LLM. AI checker tự bỏ qua khi thiếu key (`ai_checker.py:54`) |
| Kéo nguồn live | Thất bại → dùng snapshot có checksum, trạng thái `fallback` |

Hệ quả thực tế: **clone repo xong là chạy được ngay**, không cần model hay index. Điều này quan trọng cho hackathon (giám khảo tự chạy được) và cho môi trường cơ quan nhà nước có thể chặn API ngoài.

---

## 3. Cổng eval nhận diện thủ tục

Bước CI mới nhất, và là bước có triết lý riêng.

```bash
python scripts/eval_identify.py   # exit 1 nếu có bất kỳ ca chốt nhầm nào
```

**Chặn trên `chốt nhầm == 0`, KHÔNG chặn trên độ chính xác.**

Lý do tách bạch hai chỉ số này:

| | Độ chính xác (độ phủ) | Tỉ lệ chốt nhầm |
|---|---|---|
| Bản chất | Dao động theo từ vựng catalog | Đúng/sai rạch ròi |
| Khi thêm thủ tục mới | Gần như chắc chắn giảm tạm thời | Không có lý do gì để tăng |
| Hậu quả khi xấu đi | Người dân phải chọn thủ tục thủ công — tốn một lượt hội thoại | Người dân chuẩn bị **đúng một bộ giấy tờ cho sai một thủ tục** — tốn một chuyến đi |
| Đặt ngưỡng cứng | Tạo test giòn, đội sẽ nới liên tục cho tới khi vô nghĩa | Hợp lý |

Đặt ngưỡng cứng lên độ chính xác là cái bẫy quen thuộc: mỗi lần nó fail vì lý do chính đáng, người ta nới ngưỡng, và sau vài lần cổng đó không còn bảo vệ gì. Chốt nhầm thì khác — không có "chốt nhầm chính đáng".

Cổng này đã được kiểm cả hai nhánh: thêm một alias sai lệch vào catalog → exit 1 kèm thông báo rõ; gỡ ra → exit 0.

Chi tiết phương pháp và baseline: `docs/EVAL-METRICS.md`.

---

## 4. Những gì CI **chưa** chặn

Ghi ra để không ai tưởng CI xanh là đủ.

| Khoảng trống | Rủi ro | Hiện đang dựa vào |
|---|---|---|
| **Tính đúng đắn của dữ liệu thủ tục** | **Cao nhất** — căn cứ pháp lý sai vẫn qua được mọi test | Người kiểm duyệt. Xem `docs/GUARDRAILS.md` |
| Chất lượng câu trả lời node `answer` | Trung bình | Chưa có phép đo nào |
| Frontend (TypeScript, Playwright) | Trung bình | Chưa nằm trong CI |
| Latency | Thấp | Chưa đo |
| Nguồn công bố đổi hạ tầng | Trung bình | `test_procedure_source_urls.py` khoá định dạng URL, nhưng **chạy offline** nên không phát hiện được URL chết |

Điểm cuối đáng chú ý: test URL nguồn cố ý **không gọi mạng** để CI không phụ thuộc vào việc Cổng DVC có sống hay không. Đánh đổi là nó chỉ bắt được lỗi cấu hình (trỏ sai host, sai mã thủ tục), không bắt được lỗi "URL đúng định dạng nhưng đã chết". Loại lỗi thứ hai **đã từng xảy ra với cả 5 thủ tục** — hiện phải phát hiện thủ công.

---

## 5. Test đang fail trên local

`tests/test_application_migrations.py::test_application_migration_round_trip_preserves_baseline_data`

Fail trên máy local với `no such table: application_cases`, nhưng **CI xanh trên 5 lần chạy `main` gần nhất** (kiểm bằng `gh run list`). Đây là artifact môi trường local, không phải lỗi sản phẩm.

Tôi đã từng nhiều lần gọi nhầm nó là "lỗi có sẵn" trước khi thực sự kiểm CI — ghi lại đây để người sau không mất thời gian lặp lại.

Nếu gặp trên máy mình:

```bash
alembic upgrade head          # DB local thường thiếu migration
python -m pytest -q
```

---

## 6. Chạy toàn bộ cổng CI trên máy mình

```bash
ruff check src/ tests/
python -m pytest -q
python scripts/eval_identify.py
```

Ba lệnh này là đúng những gì CI chạy. Chạy được cả ba thì PR sẽ xanh.

---

## 7. Đề xuất bổ sung

Xếp theo giá trị trên công sức:

1. **Đưa frontend vào CI** — `tsc --noEmit` và build. Rẻ, bắt được lỗi kiểu trước khi deploy.
2. **Job kiểm URL nguồn có gọi mạng**, chạy theo lịch (`schedule:`) chứ không chặn PR — phát hiện nguồn chết mà không làm CI phụ thuộc mạng.
3. **Cache `pip install`** bằng `actions/cache` để rút thời gian chạy.
4. **Kiểm alias mới tự động**: cảnh báo khi alias fold xuống dưới 3 token hoặc trùng đồng tự với từ thông dụng (bài học `docs/EVAL-METRICS.md` §4b).
