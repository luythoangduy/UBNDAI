# Hackathon chat experience

Chat là điểm vào của flow công dân. Backend trả về action cards theo capability, không theo tên thủ tục:

- `send_message`: hỏi checklist, phí/thời hạn hoặc biểu mẫu.
- `start_form`: mở form schema đã duyệt.
- `open_url`: mở nguồn gốc chính thức.

Mỗi response có thể chứa:

- `actions`: lựa chọn tiếp theo cho người dùng.
- `templates`: biểu mẫu cùng phiên bản, ngày kiểm tra và các căn cứ nguồn.
- `evidence`: trace tìm kiếm, nguồn Chính phủ, live fetch và cache.
- `cache`: Redis/memory, hit/miss và TTL.

## Redis

```powershell
docker compose -f docker-compose.cache.yml up -d
```

Cache key gồm procedure ID và fingerprint của catalog/checksum nguồn/template version. Khi nguồn hoặc phiên bản template đổi, key mới được tạo; kết quả cũ không được dùng cho response mới.

Nếu Redis không sẵn sàng, hệ thống dùng TTL memory cache và ghi đúng backend trong response. Lỗi cache không chặn chat.

## Source priority

Nguồn được gắn nhãn Chính phủ khi thuộc Cổng DVC, `*.gov.vn`, Cổng TTĐT Chính phủ, CSDL VBQPPL Bộ Tư pháp hoặc `vbpl.vn`. Template citation ưu tiên nguồn có vai trò `output_template`, sau đó mới đến văn bản hợp nhất/sửa đổi.

Live fetch chỉ chạy với URL official. Nếu nguồn live timeout hoặc lỗi, UI hiển thị fallback về snapshot có checksum; hệ thống không tuyên bố đã kiểm tra live.
