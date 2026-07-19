# Deployment Guide — UBNDAI

> Cách triển khai hệ thống: kiến trúc hạ tầng, biến môi trường, quy trình deploy, và cách kiểm tra bản chạy có thật sự là bản mới nhất không.

---

## 1. Kiến trúc triển khai

Có **hai đường phục vụ frontend**, cùng tồn tại. Biết rõ đang dùng đường nào là điều kiện để gỡ lỗi 404.

```
                        Người dùng
                    ┌───────┴────────┐
                    ▼                ▼
        ┌───────────────────┐   (vào thẳng Render)
        │      Vercel       │        │
        │  ubndai.vercel.app│        │
        │  rewrites /api/*  │        │
        │  rewrites /* →    │        │
        │     index.html    │        │
        └─────────┬─────────┘        │
                  └──────────┬───────┘
                             ▼
              ┌──────────────────────────────┐
              │            Render            │  Docker multi-stage:
              │    c3-tthc-assistant         │   1. node:20 build frontend
              │      .onrender.com           │   2. python:3.11-slim + dist
              │                              │
              │  /api/v1/*   → FastAPI       │
              │  /citizen    → SPA (dist)    │
              │  /officer    → SPA (dist)    │
              │  /assets     → static        │
              └──────────────┬───────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
    PostgreSQL          Chroma + BM25       LLM API
    (Alembic)         (tuỳ chọn, có       (Anthropic ·
                       fallback)           OpenAI cho OCR)
```

**Đường 1 — qua Vercel.** Frontend không gọi thẳng backend; nó gọi `/api/*` cùng origin và Vercel rewrite sang Render (`frontend/vercel.json`). Không có CORS, không lộ URL backend trong bundle.

**Đường 2 — Render phục vụ cả hai.** Từ commit `5b3b2b6`, `Dockerfile` là multi-stage: stage `node:20-alpine` build `frontend/`, stage Python copy `frontend/dist` vào image. `src/main.py:83-99` mount `dist` qua `SPAStaticFiles` tại `/citizen`, `/officer` và `/assets` — chỉ mount khi thư mục tồn tại, nên chạy backend không có `dist` vẫn không lỗi.

> **Vì sao có đường 2.** Nó ra đời để sửa lỗi 404. Hệ quả đáng giá: container tự chứa, mở thẳng URL Render là dùng được cả hai cổng mà không cần Vercel. Với môi trường cơ quan nhà nước chỉ triển khai nội bộ một dịch vụ, đây là đường nên dùng.
>
> Đánh đổi: build image lâu hơn (phải `npm ci` + `npm run build`), và **bundle frontend bị đóng băng vào image** — sửa frontend thì phải build lại image, không chỉ redeploy Vercel.

---

## 2. Backend — Render (Docker)

`Dockerfile` ở gốc repo, **multi-stage**. Điểm đáng chú ý:

```dockerfile
FROM node:20-alpine AS frontend-builder     # stage 1: build SPA
WORKDIR /app/frontend
RUN npm ci && npm run build

FROM python:3.11-slim                        # stage 2: runtime
RUN useradd --create-home --uid 1000 user
USER user                              # không chạy bằng root
EXPOSE 7860
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head \
  && (python scripts/index_procedures.py --embedding-provider ${EMBEDDING_PROVIDER:-auto} \
      || echo 'Dense index unavailable; continuing with BM25') \
  && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-7860} \
      --proxy-headers --forwarded-allow-ips '*'"]
```

`COPY --from=frontend-builder /app/frontend/dist ./frontend/dist` đưa bundle đã build sang image runtime. Ảnh cuối **không** chứa Node hay `node_modules`.

Ba tính chất quan trọng của lệnh khởi động:

1. **`alembic upgrade head` chạy trước** — migration tự áp dụng khi deploy, không cần thao tác tay.
2. **Index dense được phép thất bại** — `|| echo ...` khiến container vẫn khởi động khi không dựng được Chroma, và hệ thống lùi về BM25. Đây là chủ ý: **thà chạy với truy hồi yếu hơn còn hơn không chạy**.
3. **`--proxy-headers --forwarded-allow-ips '*'`** — bắt buộc khi đứng sau reverse proxy của Render, nếu không mọi client IP đều thành IP của proxy.

`PORT` do Render cấp qua biến môi trường; mặc định 7860 chỉ dùng khi chạy local.

---

## 3. Frontend — Vercel

`frontend/vercel.json`:

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://c3-tthc-assistant.onrender.com/api/:path*" },
    { "source": "/(.*)",       "destination": "/index.html" }
  ]
}
```

Thứ tự hai rule quan trọng: rule `/api/*` phải đứng **trước** rule catch-all, nếu không mọi request API sẽ bị nuốt vào `index.html`.

> **Khi đổi URL backend** (đổi service Render, đổi sang domain riêng), phải sửa `destination` ở đây. Đây là chỗ duy nhất hard-code URL backend.

---

## 4. Biến môi trường

Danh sách đầy đủ ở `.env.example`. Nhóm theo mức độ bắt buộc:

### Bắt buộc cho production

| Biến | Ghi chú |
|---|---|
| `DATABASE_URL` | PostgreSQL. Khi bắt đầu bằng `postgresql://` thì `database_persistence_enabled` **tự bật** (`src/config.py:88`) |
| `JWT_SECRET` | **Phải đổi** — mặc định là `change-me` |
| `LLM_API_KEY` | Anthropic. Thiếu → hệ thống vẫn chạy nhưng mất hỏi đáp mở |
| `APP_ENV` | Đặt `production` |
| `ENABLE_DEMO_AUTH` | Đặt `false` ở production thật |
| `DEMO_PASSWORD` | Đổi nếu còn bật demo auth |

### Nên đặt

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Hoặc `gemini` |
| `OCR_LLM_PROVIDER` / `OCR_LLM_API_KEY` / `OCR_LLM_MODEL` | `openai` / — / `gpt-5-mini` | **Key riêng**, không dùng chung với chatbot |
| `OCR_CONFIDENCE_THRESHOLD` | `0.85` | Dưới ngưỡng → `needs_human_review` |
| `EMBEDDING_PROVIDER` | `auto` | Phải khớp provider lúc index Chroma |
| `STORAGE_ROOT` | `./uploads/private` | Trên Render cần volume bền, nếu không tệp mất khi restart |
| `OFFICIAL_SOURCE_LIVE_FETCH` | `true` | Tắt nếu môi trường chặn mạng ngoài |

### Xác thực thật (thay demo auth)

`OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`, `OIDC_REDIRECT_URI`, `OIDC_REQUIRED_MFA_CLAIM` (mặc định `amr:mfa`).

> **Không commit `.env`.** Đã nằm trong `.gitignore`. Khai báo biến trong dashboard Render/Vercel.

---

## 5. Quy trình deploy

### Backend (Render)

1. Render theo dõi nhánh `main`, tự build lại từ `Dockerfile` khi có commit mới.
2. Migration tự chạy trong `CMD`.
3. Kiểm tra: `curl https://<render-url>/health`

### Frontend (Vercel)

1. Vercel theo dõi `main`, build `frontend/`.
2. Kiểm tra bằng cách mở app và gọi một endpoint qua rewrite.

### Không có deploy tự động?

```bash
# Backend — build và chạy thử cục bộ đúng như production
docker build -t ubndai .
docker run -p 7860:7860 --env-file .env ubndai

# Frontend
cd frontend && npm ci && npm run build
```

---

## 6. Kiểm tra bản đang chạy có phải bản mới nhất không

**Đây là bước hay bị bỏ sót nhất, và đã từng gây hiểu nhầm nghiêm trọng trong chính dự án này** — có thời điểm production chậm **9 commit** so với `main`, thiếu cả bản sửa lỗi hiển thị `[object Object]` cho người dùng, trong khi mọi người vẫn tưởng đang xem bản mới.

Cách kiểm nhanh, không cần truy cập dashboard:

| Kiểm | Cách | Bản cũ biểu hiện thế nào |
|---|---|---|
| Backend có bản sửa mới nhất | `curl -s https://<render-url>/health` | — |
| Lỗi 422 hiển thị đúng | Đăng nhập với mật khẩu quá ngắn | Bản cũ hiện `[object Object]` |
| Frontend là bundle mới | Xem DevTools → có class `cache-badge` không | Bản cũ **còn** `cache-badge` |
| Nguồn trích dẫn | Gửi một câu hỏi thủ tục, xem khối "Đã kiểm chứng nguồn" | Bản cũ trỏ `thutuc.dichvucong.gov.vn` (đã 503 toàn subdomain) |

Nếu thấy bất kỳ dấu hiệu nào ở cột phải: **production đang chạy code cũ**, cần redeploy từ `main` trên cả Vercel lẫn Render.

---

## 7. Sau khi deploy — danh sách kiểm

```bash
# 1. Backend sống
curl -s https://<render-url>/health

# 2. Catalog nạp được
curl -s https://<render-url>/api/v1/procedures | head -c 300

# 3. Luồng chat chạy trọn vẹn
curl -X POST https://<render-url>/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ"}'
```

Bước 3 là bước quan trọng nhất — nó đi qua toàn bộ đồ thị LangGraph. Phản hồi phải có `checklist` và `citations`. Nếu trả 500, xem log Render: nguyên nhân thường là thiếu biến môi trường hoặc migration chưa chạy, **không phải lỗi logic** (logic đã được 333 test phủ).

---

## 8. Sự cố thường gặp

| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| 500 ở mọi endpoint | Thiếu `DATABASE_URL` hoặc migration chưa chạy | Xem log khởi động, kiểm `alembic upgrade head` |
| `no such column: case_messages.response_json` | DB thiếu migration | `alembic upgrade head` |
| Chat trả lời nhưng không có citation | Index chưa dựng → chỉ BM25 | Chấp nhận được; chạy `scripts/index_procedures.py` nếu muốn dense |
| "Nguồn live chưa phản hồi" | Cổng DVC lỗi/chặn mạng | Tự hồi phục sau TTL 120 s. Nếu kéo dài, kiểm `OFFICIAL_SOURCE_LIVE_FETCH` |
| Tệp tải lên mất sau restart | `STORAGE_ROOT` trỏ vào ổ đĩa tạm | Gắn volume bền trên Render |
| Frontend gọi API ra 404 | Rewrite sai thứ tự hoặc sai URL backend | Kiểm `frontend/vercel.json` |
| Mở `/citizen` trên Render ra 404 | Image build thiếu `frontend/dist` | Kiểm log build stage `frontend-builder`; `main.py:84` chỉ mount khi thư mục tồn tại nên thiếu là im lặng bỏ qua |
| Sửa frontend rồi mà Render vẫn bản cũ | Bundle đóng băng trong image | Phải **build lại image**, redeploy không đủ |
| `[object Object]` khi đăng nhập sai | Frontend là bundle cũ | Redeploy frontend |
| **Sửa `data/procedures/*.json` rồi mà API vẫn trả nội dung cũ** | **Catalog cache theo vòng đời tiến trình** — xem cảnh báo dưới | **Khởi động lại tiến trình** |

> ### ⚠️ Catalog chỉ nạp một lần cho mỗi tiến trình
>
> `load_catalog()` (`src/services/catalog.py:19`) cache vào `_CACHE` và **không bao giờ nạp lại**. Sửa file JSON trên đĩa **không** có hiệu lực với tiến trình đang chạy.
>
> Đây không phải phiền toái nhỏ. Đã xảy ra thật: sau khi gỡ *"Luật Xây dựng số 135/2025/QH15"* và *"Nghị định 217/2026/NĐ-CP"* — **hai văn bản không tồn tại** — khỏi catalog, server chạy từ trước vẫn tiếp tục phục vụ chúng cho người dùng suốt nhiều giờ. File đã đúng, API vẫn sai.
>
> Hệ quả vận hành: **thu hồi một trích dẫn pháp lý sai không có hiệu lực cho tới khi khởi động lại tiến trình.** Với hệ thống hướng dẫn thủ tục hành chính, đó là khoảng trống cần biết rõ.
>
> **Cách kiểm bất cứ lúc nào** — so nội dung API đang phục vụ với file trên đĩa:
>
> ```bash
> curl -s http://127.0.0.1:8000/api/v1/procedures/giay_phep_xay_dung | grep -o "217/2026" && echo "SERVER ĐANG CHẠY CATALOG CŨ"
> python -c "import json;print(json.load(open('data/procedures/giay_phep_xay_dung.json',encoding='utf-8'))['legal_basis'])"
> ```
>
> Trên Render, mỗi lần deploy là một tiến trình mới nên catalog luôn tươi. Rủi ro nằm ở **máy dev chạy server lâu ngày** và ở bất kỳ môi trường nào cập nhật catalog mà không restart.

---

## 9. Bảo mật khi triển khai

| Việc | Trạng thái |
|---|---|
| Container không chạy bằng root | ✅ `USER user` trong Dockerfile |
| `.env` không lọt vào repo | ✅ `.gitignore` |
| Lỗi nội bộ không lộ ra client | ✅ handler ở `src/main.py`, chi tiết chỉ vào log |
| `JWT_SECRET` đã đổi khỏi `change-me` | ⚠️ **phải kiểm thủ công** |
| `ENABLE_DEMO_AUTH=false` ở production | ⚠️ **phải kiểm thủ công** |
| Tệp tải lên ở vùng riêng | ✅ `storage_root` |
| Hạn mức tải lên | ✅ 10 tệp · 10 MB/tệp |

> **Xoay khoá định kỳ.** Nếu một API key từng bị in ra log, terminal, hoặc chia sẻ trong chat — coi như đã lộ và **thu hồi ngay**, kể cả khi tin rằng không ai khác thấy. Thu hồi rẻ hơn nhiều so với điều tra xem ai đã dùng.
