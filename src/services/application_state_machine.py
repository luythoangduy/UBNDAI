"""Pure state-transition rules for the officer application workflow."""

from __future__ import annotations


class InvalidApplicationTransition(ValueError):
    """Raised when a requested application status transition is not legal."""


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"collecting", "submitted_for_precheck"}),
    "collecting": frozenset({"submitted_for_precheck"}),
    "submitted_for_precheck": frozenset({"ocr_processing"}),
    "ocr_processing": frozenset({"precheck_processing", "awaiting_officer_review"}),
    "precheck_processing": frozenset({"awaiting_officer_review", "precheck_ready"}),
    "awaiting_officer_review": frozenset({"in_officer_review", "needs_citizen_update", "escalated"}),
    "in_officer_review": frozenset({"needs_citizen_update", "precheck_ready", "done", "escalated", "closed"}),
    "needs_citizen_update": frozenset({"resubmitted", "closed"}),
    "resubmitted": frozenset({"ocr_processing"}),
    "precheck_ready": frozenset({"submitted", "in_officer_review", "closed"}),
    "escalated": frozenset({"in_officer_review", "closed"}),
    "submitted": frozenset({"processing", "closed"}),
    "processing": frozenset({"done", "needs_citizen_update", "closed"}),
    "ready": frozenset({"processing", "closed"}),
    "need_more_info": frozenset({"resubmitted", "closed"}),
}


def can_transition(current_status: str, target_status: str) -> bool:
    return target_status in ALLOWED_TRANSITIONS.get(current_status, frozenset())


def require_transition(current_status: str, target_status: str) -> str:
    if not can_transition(current_status, target_status):
        raise InvalidApplicationTransition(
            f"Cannot transition application from {current_status!r} to {target_status!r}"
        )
    return target_status


__all__ = ["ALLOWED_TRANSITIONS", "InvalidApplicationTransition", "can_transition", "require_transition"]
