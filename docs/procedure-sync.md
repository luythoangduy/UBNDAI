# Đồng bộ thủ tục tự động

Luồng mới tách rõ hai tầng dữ liệu:

- `data/raw_documents`: bản nguồn bất biến theo SHA-256. `latest.json` chỉ con trỏ phiên bản hiện hành. Các section ở đây được đưa vào chat ngay và luôn mang `source_url`, `retrieved_at`, `source_hash`.
- `data/procedure_candidates`: kết quả structured extraction và quality report. Mọi candidate luôn bắt đầu ở `needs_review`; pipeline không tự ghi vào `data/procedures`.

Checklist, dynamic form, OCR mapping, validation YAML và DOCX chỉ được bật cho catalog có trạng thái `approved` hoặc `published`. Capability được tính tại runtime qua API, không suy ra ở frontend.

## Chạy đồng bộ

```powershell
python scripts/sync_procedures.py `
  --index-url https://dichvucong.gov.vn/p/home/dvc-tthc.html `
  --index-dense
```

Các tuỳ chọn:

- `--allowed-domain`: bổ sung domain chính thức cho connector riêng. Connector mặc định chỉ chấp nhận HTTPS và domain DVC trong allow-list.
- `--no-llm`: chỉ tải, checksum, tách section và index cho chat; không chạy structured extraction.
- `--index-dense`: upsert các section vừa thay đổi vào Chroma. Nếu dense index lỗi, raw store và BM25 chat vẫn hoạt động.

HTML được hỗ trợ trong connector DVC hiện tại. PDF được lưu ở ranh giới fetch nhưng chưa extract nếu chưa cài adapter PDF đáng tin cậy; pipeline sẽ ghi lỗi thay vì index nội dung nhị phân.

## API cho frontend

- `GET /api/v1/procedures`
- `GET /api/v1/procedures/{id}`
- `GET /api/v1/procedures/{id}/form-schema`
- `GET /api/v1/procedures/{id}/capabilities`

Frontend chỉ hiện nút soạn khi `dynamic_form=true`; upload OCR chỉ hiện khi `ocr_autofill=true`. Thủ tục raw chưa duyệt vẫn được chat trả lời có citation, nhưng yêu cầu checklist sẽ trả thông báo đang chờ kiểm duyệt.

## Quy trình duyệt

1. Kiểm tra candidate, provenance và các conflict về phí/thời hạn/địa phương.
2. Chuyển metadata đã duyệt thành catalog `data/procedures/*.json` với `status=approved`.
3. Kiểm duyệt riêng form fields, `ocr_sources`, rule YAML và draft template.
4. Chỉ đổi sang `published` khi evaluation và kiểm thử contract đạt yêu cầu.

Không tự thay thế catalog đang published khi checksum nguồn đổi. Phiên bản mới tiếp tục vào hàng chờ để cán bộ so sánh và duyệt.
