"""Intent taxonomy deterministic cho chat TTHC, bao gồm edge/out-of-scope cases."""

from __future__ import annotations

from dataclasses import dataclass

from src.models import IntentName
from src.services.retrieval.common import fold_ascii


@dataclass(frozen=True)
class IntentDetection:
    primary: IntentName
    intents: list[IntentName]
    confidence: float


_PATTERNS: list[tuple[IntentName, tuple[str, ...]]] = [
    ("checklist", ("giay to gi", "can giay to", "ho so gom", "thanh phan ho so", "chuan bi gi", "checklist")),
    ("fee", ("le phi", "phi bao nhieu", "bao nhieu tien", "mat tien", "mien phi")),
    ("processing_time", ("thoi han", "bao lau", "may ngay", "khi nao xong")),
    ("agency", ("co quan", "noi nop", "nop o dau", "nop tai dau", "cho nao")),
    ("legal_basis", ("can cu phap ly", "van ban nao", "luat nao", "quy dinh nao")),
    ("forms", ("bieu mau", "mau don", "to khai nao", "tai mau")),
    (
        "status_tracking",
        ("trang thai ho so", "ho so den dau", "den dau roi", "tra cuu ho so", "ma ho so"),
    ),
    ("submission", ("nop ho so", "gui ho so", "submit", "nop truc tuyen")),
    ("document_upload", ("tai len", "upload", "dinh kem", "gui anh", "gui file")),
    ("capabilities", ("ban lam duoc gi", "co the giup gi", "chuc nang", "pham vi ho tro")),
]

_ADMIN_HINTS = (
    "thu tuc", "dang ky", "ho so", "giay phep", "giay to", "khai sinh",
    "ket hon", "can cuoc", "cccd", "dat dai", "xay dung", "ho khau",
    "chung thuc", "cong chung", "ubnd", "dich vu cong",
)
_OUT_OF_SCOPE = (
    "thoi tiet", "nau an", "cong thuc mon", "viet code", "lap trinh",
    "bong da", "phim", "am nhac", "chung khoan", "tien ao", "benh gi",
    "trieu chung", "ke don", "boi toan", "tu vi",
)
_GREETINGS = {"xin chao", "chao", "hello", "hi", "alo"}
_THANKS = {"cam on", "cam on ban", "thanks", "thank you", "ok cam on"}


def detect_intents(message: str, *, has_selected_procedure: bool) -> IntentDetection:
    folded = " ".join(fold_ascii(message).split())
    if folded in _GREETINGS:
        return IntentDetection("greeting", ["greeting"], 1.0)
    if folded in _THANKS:
        return IntentDetection("thanks", ["thanks"], 1.0)
    if any(pattern in folded for pattern in _OUT_OF_SCOPE):
        return IntentDetection("out_of_scope", ["out_of_scope"], 0.98)

    found: list[IntentName] = []
    for intent, patterns in _PATTERNS:
        if any(_is_active_pattern(folded, pattern) for pattern in patterns):
            found.append(intent)

    has_admin_hint = any(hint in folded for hint in _ADMIN_HINTS)
    navigation_intents = {
        "status_tracking", "submission", "document_upload", "capabilities",
    }
    if (
        not has_selected_procedure
        and has_admin_hint
        and not navigation_intents.intersection(found)
    ):
        found.insert(0, "procedure_discovery")

    if found:
        unique = list(dict.fromkeys(found))
        return IntentDetection(_choose_primary(unique), unique, 0.95)
    if has_selected_procedure:
        return IntentDetection("general_question", ["general_question"], 0.55)
    if has_admin_hint:
        return IntentDetection("procedure_discovery", ["procedure_discovery"], 0.8)
    return IntentDetection("unknown", ["unknown"], 0.3)


def _choose_primary(intents: list[IntentName]) -> IntentName:
    precedence: tuple[IntentName, ...] = (
        "out_of_scope", "status_tracking", "submission", "document_upload",
        "capabilities", "fee", "processing_time", "agency", "legal_basis",
        "forms", "checklist", "procedure_discovery", "general_question",
    )
    return next(intent for intent in precedence if intent in intents)


def _is_active_pattern(text: str, pattern: str) -> bool:
    if pattern not in text:
        return False
    negated = (
        f"khong hoi {pattern}",
        f"khong can {pattern}",
        f"khong muon {pattern}",
        f"khong quan tam {pattern}",
        f"bo qua {pattern}",
    )
    return not any(phrase in text for phrase in negated)
