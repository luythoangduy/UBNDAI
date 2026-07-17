# Frontend — TTHC Assist (Owner: Dev C)

Sprint 0: khởi tạo bằng Vite + React + TypeScript, copy config từ `../../C2-App-108/frontend/` (vite.config.ts, tsconfig).

Hai mặt UI:

1. **Widget chat người dân** (nhúng được vào cổng DVC): hội thoại guidance (`POST /api/v1/chat`), render theo `ChatResponse.kind` (clarify → form câu hỏi, checklist → danh sách tick, answer → text + citation); upload ảnh giấy tờ; màn sửa trường OCR (bắt buộc hiện trường `needs_human_review`); thanh readiness + danh sách `ValidationIssue`.
2. **Dashboard cán bộ:** hàng đợi theo priority, tóm tắt hồ sơ, hàng chờ "AI chưa chắc chắn", biểu đồ metrics + banner `AnomalyAlert`, daily digest.

```bash
npm install
npm run dev   # proxy /api → localhost:8000
```
