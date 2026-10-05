"""Tests for revision-prompt feedback formatting."""

from colorref.games import format_revision_feedback_text


def test_accumulate_false_uses_latest_only() -> None:
    s = format_revision_feedback_text(["a", "b", "c"], accumulate=False)
    assert s == "c"


def test_accumulate_true_numbers_rounds() -> None:
    s = format_revision_feedback_text(["only"], accumulate=True)
    assert s == "only"
    s2 = format_revision_feedback_text(["first", "second"], accumulate=True)
    assert "Round 1: first" in s2 and "Round 2: second" in s2


def test_empty_history() -> None:
    assert format_revision_feedback_text([], accumulate=False) == ""
    assert format_revision_feedback_text([], accumulate=True) == ""
