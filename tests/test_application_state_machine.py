import pytest

from src.services.application_state_machine import (
    InvalidApplicationTransition,
    can_transition,
    require_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("awaiting_officer_review", "in_officer_review"),
        ("awaiting_officer_review", "needs_citizen_update"),
        ("in_officer_review", "needs_citizen_update"),
        ("in_officer_review", "done"),
        ("needs_citizen_update", "resubmitted"),
        ("resubmitted", "ocr_processing"),
    ],
)
def test_supported_officer_transitions(current: str, target: str):
    assert can_transition(current, target)
    assert require_transition(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("awaiting_officer_review", "done"),
        ("done", "in_officer_review"),
        ("draft", "in_officer_review"),
        ("needs_citizen_update", "done"),
    ],
)
def test_unsupported_transitions_raise_conflict(current: str, target: str):
    assert not can_transition(current, target)
    with pytest.raises(InvalidApplicationTransition):
        require_transition(current, target)
