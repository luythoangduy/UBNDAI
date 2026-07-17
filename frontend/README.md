# Frontend — TTHC Assist

React + Vite + TypeScript, phục vụ hai route cùng một bundle:

- `/citizen`: trợ lý hỏi đáp thủ tục có citation, tạo/cập nhật hồ sơ, upload giấy tờ, consent và nộp tiền kiểm.
- `/officer`: dashboard, tìm kiếm/lọc/sắp xếp queue, claim hồ sơ, workspace ba cột (tài liệu, dữ liệu biểu mẫu/OCR, findings), sửa OCR, chạy lại validation, yêu cầu bổ sung, chuyển cấp, đánh dấu đạt tiền kiểm và timeline.

## Chạy local

```bash
# Terminal 1, tại thư mục gốc dự án
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm install
npm run dev
```

Vite proxy `/api` tới `http://127.0.0.1:8000`. Tài khoản demo:

- Công dân: `citizen.demo` / `ChangeMe123!`
- Cán bộ: `officer.demo` / `ChangeMe123!`

## Kiểm tra

```bash
npm test
npm run build
```

Backend tự phục vụ `frontend/dist` tại `/citizen` và `/officer` sau khi build. Không dùng dữ liệu demo chứa PII thật. UI luôn hiển thị lưu ý rằng kết quả tiền kiểm không phải quyết định hành chính.
