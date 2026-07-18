"""Prompt tập trung cho thao tác sửa bản nháp từ workspace chat-first."""

DRAFT_REVISION_SYSTEM = """Bạn là trợ lý biên tập văn bản hành chính Việt Nam.
Chỉ sửa theo đúng yêu cầu của người dùng. Giữ nguyên mọi dữ kiện, số hiệu, ngày tháng,
tên cơ quan và placeholder chưa được cung cấp. Không tự thêm căn cứ pháp lý hoặc dữ kiện.
Trả về duy nhất HTML hợp lệ dùng các thẻ: h1, h2, h3, p, strong, em, u, ul, ol, li, br.
Không dùng markdown, script, style, link, ảnh hoặc code fence."""


def draft_revision_user_prompt(*, html: str, instruction: str, selected_text: str | None) -> str:
    scope = (
        f"Chỉ ưu tiên sửa đoạn được chọn sau (nếu tìm thấy trong HTML):\n{selected_text}"
        if selected_text
        else "Sửa toàn bộ văn bản ở mức tối thiểu cần thiết."
    )
    return f"""Yêu cầu sửa: {instruction}

Phạm vi: {scope}

HTML hiện tại:
{html}
"""
