# Authorization Spec — UBNDAI

> Mô hình xác thực và phân quyền: vai trò, cách cấp/kiểm token, ranh giới tổ chức, và **những gì chưa đủ cho production thật**.

---

## 1. Hai chế độ xác thực

| Chế độ | Dùng khi | Bật/tắt |
|---|---|---|
| **Demo auth** (username/password cứng) | Hackathon, demo, phát triển | `ENABLE_DEMO_AUTH` |
| **OIDC** (định danh tập trung, yêu cầu MFA) | Triển khai thật | Cấu hình `OIDC_*` |

Ở production thật **phải đặt `ENABLE_DEMO_AUTH=false`**. Đây là một trong hai mục phải kiểm thủ công trước khi mở cho người dùng (mục kia là `JWT_SECRET`) — xem `docs/Deployment-Guide.md` §9.

---

## 2. Vai trò

`src/services/auth.py` định nghĩa bốn danh tính demo:

| Tài khoản | `user_id` | `organization_id` | Vai trò |
|---|---|---|---|
| `officer.demo` | `officer-demo` | `org-demo` | `officer_reviewer` |
| `officer.other` | `officer-other` | **`org-other`** | `officer_reviewer` |
| `citizen.demo` | `citizen-demo` | `public` | `citizen` |
| `citizen.other` | `citizen-other` | `public` | `citizen` |

> **Vì sao có `officer.other` ở tổ chức khác.** Đây không phải tài khoản thừa — nó tồn tại để kiểm thử **cách ly theo tổ chức**: cán bộ thuộc `org-other` không được đọc hồ sơ của `org-demo`. Có sẵn hai tổ chức trong dữ liệu demo khiến lỗi rò rỉ chéo lộ ra trong test thay vì lộ ra ở pilot.

Tương tự, `citizen.other` để kiểm chứng công dân A không đọc được hồ sơ của công dân B.

---

## 3. Token

**Cấp** (`issue_token`, `auth.py:39`) — JWT chứa:

```python
{
  "user_id": ...,
  "organization_id": ...,
  "roles": sorted(identity.roles),
  "exp": now + JWT_ACCESS_TTL_MINUTES * 60      # mặc định 30 phút
}
```

**Kiểm** (`decode_token`, `auth.py:48`) — token sai hoặc hết hạn → `401` với thông điệp chung `"Invalid or expired access token"`. Không tiết lộ token sai ở điểm nào.

**Truyền** — Bearer token qua header `Authorization`.

`organization_id` nằm **trong token**, không phải tham số client gửi lên. Client không tự khai mình thuộc tổ chức nào.

---

## 4. Ba mức bảo vệ endpoint

| Dependency | Hành vi | Dùng ở |
|---|---|---|
| `current_claims` | Bắt buộc có token; thiếu → `401` | Endpoint cần đăng nhập |
| `optional_current_claims` | Có token thì giải mã, không có vẫn chạy | Chat cho khách chưa đăng nhập |
| `require_role(*roles)` | Thiếu vai trò → `403` | Endpoint cán bộ |

```python
# auth.py:80
def require_role(*roles: str):
    def dependency(claims: TokenClaims = Security(current_claims)) -> TokenClaims:
        if not set(roles).intersection(claims.roles):
            raise HTTPException(status_code=403, detail="Insufficient role")
```

Phân biệt `401` (chưa xác thực) và `403` (đã xác thực nhưng không đủ quyền) là đúng chuẩn và có ý nghĩa vận hành: `403` hàng loạt là dấu hiệu cấu hình vai trò sai, `401` hàng loạt là dấu hiệu token/đồng hồ lệch.

`optional_current_claims` tồn tại vì **luồng chat phải dùng được khi chưa đăng nhập** — bắt người dân đăng nhập chỉ để hỏi thủ tục cần giấy tờ gì là rào cản không cần thiết. Danh tính chỉ cần khi họ bắt đầu nộp hồ sơ thật.

---

## 5. OIDC

| Biến | Ý nghĩa |
|---|---|
| `OIDC_ISSUER_URL` | Nhà cung cấp định danh |
| `OIDC_CLIENT_ID` | Client ID |
| `OIDC_AUDIENCE` | Audience phải khớp |
| `OIDC_REDIRECT_URI` | Callback — mặc định `/api/v1/auth/oidc/callback` |
| `OIDC_REQUIRED_MFA_CLAIM` | **Mặc định `amr:mfa`** |

`OIDC_REQUIRED_MFA_CLAIM` đáng chú ý: hệ thống **yêu cầu bằng chứng MFA trong token**, không chỉ chấp nhận đăng nhập thành công. Với tài khoản cán bộ có quyền xem hồ sơ chứa dữ liệu cá nhân của người dân, đây là mức tối thiểu hợp lý.

**Bằng chứng:** `pytest tests/test_oidc.py` → 2/2 PASS

---

## 6. Dữ liệu cá nhân

| Cơ chế | Vị trí |
|---|---|
| Tệp tải lên lưu ở vùng riêng | `STORAGE_ROOT=./uploads/private` |
| Hạn mức tải lên | 10 tệp · 10 MB/tệp (`config.py:84-85`) |
| Lỗi nội bộ không lộ ra client | `src/main.py` — thông điệp chung, chi tiết chỉ vào log |
| Truy cập tệp qua endpoint có kiểm quyền | `/api/v1/officer/documents/{id}/content` |

Tệp **không** phục vụ qua đường tĩnh — mọi truy cập đi qua endpoint có kiểm token và vai trò.

---

## 7. Kiểm thử

```bash
pytest tests/test_oidc.py tests/test_officer_api.py \
       tests/test_officer_contracts.py tests/test_application_management_api.py -q
```

Nhóm test này phủ: cấp/giải mã token, chặn theo vai trò, và cách ly theo tổ chức.

---

## 8. Chưa đủ cho production thật

Ghi thẳng thay vì để người triển khai tự phát hiện.

| Khoảng trống | Rủi ro | Việc cần làm |
|---|---|---|
| **`JWT_SECRET` mặc định `change-me`** | **Cao** — ai biết giá trị mặc định đều ký được token hợp lệ | Đặt biến môi trường, kiểm trước khi mở |
| **`ENABLE_DEMO_AUTH` mặc định `true`** | **Cao** — tài khoản demo dùng được ở production | Đặt `false` |
| Không có refresh token | Trung bình | Cán bộ phải đăng nhập lại mỗi 30 phút |
| Không có thu hồi token | Trung bình | Token đã cấp còn hiệu lực tới hạn, kể cả khi khoá tài khoản |
| Không có rate limit đăng nhập | Trung bình | Thêm ở tầng reverse proxy hoặc middleware |
| Chưa có nhật ký kiểm toán ai xem hồ sơ nào | Trung bình–Cao | Với dữ liệu công dân, cơ quan quản lý thường yêu cầu |
| Vai trò còn thô (`officer_reviewer`) | Thấp–Trung bình | Thực tế có nhiều cấp: tiếp nhận, thẩm định, lãnh đạo ký |

Hai dòng đầu là **lỗi chặn triển khai**, không phải việc cần cải thiện dần. Chúng an toàn trong hackathon vì hệ thống chưa chứa dữ liệu thật — nhưng chính vì mặc định thuận tiện nên rất dễ bị mang nguyên sang môi trường thật.

Hai dòng cuối gắn với quy trình hành chính thật và nên làm cùng lúc với Giai đoạn 1 của pilot, khi đã biết cơ cấu vai trò thực tế của đơn vị.
