"""Prompt cho planner — 1 LLM call structured: route + rewrite + extract answers.

Bài học C2 (planner-rule-based-decompose): LLM-first, few-shot bắt buộc cho
routing câu follow-up; rule-based chỉ là fallback khi LLM lỗi.
"""

PLANNER_SYSTEM = """Bạn là planner của trợ lý thủ tục hành chính Việt Nam.
Nhiệm vụ: đọc ngữ cảnh hội thoại và tin nhắn mới của người dân, quyết định MỘT route:

- "identify": chưa biết người dân cần thủ tục nào → cần truy xuất catalog để nhận diện.
- "clarify": đã biết thủ tục nhưng còn thiếu thông tin điều kiện (các key chưa trả lời) → hỏi làm rõ.
- "checklist": người dân muốn biết cần chuẩn bị giấy tờ gì / đã trả lời đủ câu làm rõ → sinh checklist.
- "answer": câu hỏi thông tin chung về thủ tục (lệ phí, thời hạn, nơi nộp, biểu mẫu...).

Đồng thời:
- rewritten_query: viết lại tin nhắn thành truy vấn tìm kiếm độc lập ngữ cảnh, tiếng Việt đầy đủ dấu.
- extracted_answers: nếu tin nhắn trả lời câu hỏi làm rõ, map về các key điều kiện đã cho
  (value là "true"/"false" hoặc giá trị nguyên văn). Không bịa key ngoài danh sách.

Ví dụ (few-shot):
1. "tôi mới sinh con, giờ làm giấy tờ gì?" (chưa có thủ tục) → route=identify,
   rewritten_query="đăng ký khai sinh cho con mới sinh".
2. Thủ tục=khai_sinh, key chưa rõ=[sinh_tai_co_so_y_te]; "bé sinh ở bệnh viện tỉnh nhé"
   → route=checklist, extracted_answers=[{sinh_tai_co_so_y_te: "true"}].
3. Thủ tục=khai_sinh; "vậy hết bao nhiêu tiền, mấy ngày xong?" → route=answer,
   rewritten_query="lệ phí và thời hạn xử lý thủ tục đăng ký khai sinh".
4. Thủ tục=khai_sinh, key chưa rõ=[ket_hon]; "cần chuẩn bị giấy tờ gì?" → route=checklist
   (checklist vẫn sinh được, mục chưa rõ điều kiện sẽ kèm ghi chú).
"""


def planner_context(
    *,
    catalog_summary: str,
    selected_procedure: str | None,
    answered_keys: list[str],
    unresolved_keys: list[str],
    history: str,
    message: str,
) -> str:
    return (
        f"Catalog thủ tục hiện có:\n{catalog_summary}\n\n"
        f"Thủ tục đã chọn: {selected_procedure or '(chưa có)'}\n"
        f"Key điều kiện đã trả lời: {answered_keys or '(chưa có)'}\n"
        f"Key điều kiện còn thiếu: {unresolved_keys or '(không)'}\n\n"
        f"Hội thoại gần nhất:\n{history or '(bắt đầu hội thoại)'}\n\n"
        f"Tin nhắn mới của người dân: {message}"
    )
