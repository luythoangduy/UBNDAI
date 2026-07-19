"""Tiếng Việt đời thường không được khớp tự tin vào bất kỳ thủ tục nào.

Vì sao cần bộ test riêng thay vì dựa vào eval nhận diện:

`scripts/eval_identify.py` đo trên các câu người dân HỎI VỀ THỦ TỤC — nó trả lời
"nhận đúng thủ tục không". Nó không trả lời được "có nhận bừa khi người ta nói
chuyện khác không", vì mọi câu trong đó đều có một thủ tục đúng để so.

Hai lỗi nghiêm trọng nhất từng gặp đều thuộc loại thứ hai và **không** nằm trong
bộ eval nào — chúng chỉ lộ ra khi rà dữ liệu thủ công:

  "cho NHỎ nhà tôi mượn giấy tờ"   -> tam_tru  (điểm 1.0)
      alias "ở nhờ" fold thành "o nho", nằm gọn giữa "cho nho".
  "nộp hồ sơ vào CUỐI năm"         -> ket_hon  (điểm 1.0)
      alias "cưới" fold thành "cuoi", trùng khít "cuối".

Bỏ dấu gộp nhiều từ khác nghĩa thành một chuỗi, nên mỗi alias mới là một cơ hội
va chạm. Bộ câu mồi dưới đây là lưới an toàn: thêm alias gây khớp bừa vào tiếng
Việt thông thường sẽ làm test này đỏ ngay, trước khi tới tay người dân.

Khớp tự tin = điểm >= identify_min_relevance, tức đủ để hệ thống CHỐT thủ tục
thay vì hỏi lại (AGENTS.md §5: thà nói "chưa đủ căn cứ" còn hơn đoán).
"""

import pytest

from src.config import settings
from src.services.catalog import load_catalog
from src.services.retrieval import _identity_score

# Câu tiếng Việt đời thường. Không câu nào là yêu cầu làm thủ tục hành chính,
# nhưng tất cả đều chứa từ dễ va chạm với alias sau khi bỏ dấu.
DECOYS = [
    # "cuoi" — đồng tự của "cưới" (ket_hon)
    "nộp hồ sơ vào cuối năm có được không",
    "cuối cùng thì cần giấy tờ gì",
    "sinh viên năm cuối cần thực tập",
    # "o nho" — lọt giữa "cho nhỏ" (alias "ở nhờ" của tam_tru)
    "cho nhỏ nhà tôi mượn giấy tờ",
    # "chung minh" — đồng tự của "chứng minh" (can_cuoc)
    "tụi mình về chung một nhà",
    "chung cư nhà mình mất điện",
    "minh bạch thông tin là cần thiết",
    # "khai" + "sinh" rời nhau — required_token_groups là túi từ
    "khai báo y tế khi nhập cảnh",
    # Câu trung tính, không liên quan gì tới thủ tục
    "hôm nay trời đẹp quá",
    "cho tôi hỏi giờ làm việc của cơ quan",
    "cảm ơn bạn nhiều nhé",
    "tôi muốn hỏi về học phí đại học",
]


@pytest.mark.parametrize("query", DECOYS)
def test_everyday_vietnamese_does_not_confidently_match_a_procedure(query: str):
    threshold = settings.identify_min_relevance
    matched = {
        procedure_id: round(score, 3)
        for procedure_id, procedure in load_catalog().items()
        if (score := _identity_score(query, procedure)) >= threshold
    }
    assert not matched, (
        f"câu đời thường «{query}» bị khớp tự tin vào {matched} "
        f"(ngưỡng {threshold}). Thường là do một alias quá ngắn hoặc trùng đồng tự "
        f"sau khi bỏ dấu — xem docs/KnowledgeBase-Guide.md §5."
    )
