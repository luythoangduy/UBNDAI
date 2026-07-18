# Hackathon chat experience

Chat là điểm vào của flow công dân. Backend trả về action cards theo capability, không theo tên thủ tục:

- `send_message`: hỏi checklist, phí/thời hạn hoặc biểu mẫu.
- `start_form`: mở form schema đã duyệt.
- `open_url`: mở nguồn gốc chính thức.

Phạm vi hỏi đáp không bị giới hạn bởi các procedure ID trong catalog. Catalog chỉ bật
capability đã kiểm duyệt; thủ tục chưa có workflow tiếp tục qua raw source, legal RAG và
official search. Không có nguồn phù hợp thì chat trả cảnh báo rõ ràng, không tự suy đoán.

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

## Chat-first draft workspace

Luồng công dân dùng chat làm điểm vào chính: mô tả nhu cầu → xem các lựa chọn mẫu có
provenance → chọn mẫu registry → bổ sung field → sinh bản nháp trong drawer bên phải.
Mẫu tìm được từ live source nhưng chưa có schema nội bộ chỉ cho phép mở nguồn, không hiện
nút sinh tự động.

`POST /api/v1/drafts/generate` được gọi với `allow_incomplete: true` trong bước preview.
Field bắt buộc còn thiếu được đánh dấu vàng trong checklist và giữ placeholder trong bản
nháp. Drawer có thể đóng mà không xoá state; nút “Mở lại bản nháp” luôn xuất hiện cạnh chat.

Sửa bằng AI dùng `POST /api/v1/drafts/revise` với HTML hiện tại, instruction và selection
tuỳ chọn. Response chỉ là đề xuất HTML đã lọc; frontend hiển thị block diff thêm/xoá và chỉ
thay editor sau khi người dùng bấm áp dụng. Xuất DOCX luôn dùng `/drafts/export.docx` để giữ
đúng nội dung đã được người dùng duyệt.
