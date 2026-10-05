"""Tests for quantifier calibration specifications and metrics."""

from colorref.prompts import render_quantifier_calibration
from colorref.quantifiers import (
    make_instruction,
    measure_update,
    pairwise_monotonicity,
)


def test_instruction_phrasing() -> None:
    assert make_instruction("baseline", "more_blue") == "Make it more blue."
    assert make_instruction("a_little", "more_blue") == "Make it a little more blue."
    assert make_instruction("somewhat", "lighter") == "Make it somewhat lighter."
    assert make_instruction("much", "darker") == "Make it much darker."


def test_measure_update_uses_requested_sign() -> None:
    metrics = measure_update((50.0, 0.0, 0.0), (60.0, 2.0, 3.0), "more_blue")
    assert metrics["requested_signed_step"] == -3.0
    assert metrics["update_l"] == 10.0
    assert metrics["off_axis_drift"] == 10.198039027185569
    assert metrics["direction_followed"] == 0.0

    metrics = measure_update((50.0, 0.0, 0.0), (60.0, 2.0, -3.0), "more_blue")
    assert metrics["requested_signed_step"] == 3.0
    assert metrics["direction_followed"] == 1.0


def test_monotonicity_counts_ordered_pairs() -> None:
    rows = [
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 0, "parse_ok": True, "requested_signed_step": 1.0},
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 1, "parse_ok": True, "requested_signed_step": 2.0},
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 3, "parse_ok": True, "requested_signed_step": 2.0},
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 3
    assert result["monotonicity_ordered_pairs"] == 3
    assert result["monotonicity_rate"] == 1.0


def test_monotonicity_ignores_parse_failures() -> None:
    rows = [
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 0, "parse_ok": True, "requested_signed_step": 1.0},
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 1, "parse_ok": False, "requested_signed_step": None},
        {"base_id": "x", "direction": "lighter", "quantifier_rank": 2, "parse_ok": True, "requested_signed_step": 0.5},
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 1
    assert result["monotonicity_ordered_pairs"] == 0
    assert result["monotonicity_rate"] == 0.0


def test_prompt_renderer() -> None:
    rendered = render_quantifier_calibration(
        "Current: {base_lab}; Instruction: {instruction}",
        "LAB(50.00, 0.00, 0.00)",
        "Make it a little lighter.",
    )
    assert rendered == (
        "Current: LAB(50.00, 0.00, 0.00); "
        "Instruction: Make it a little lighter."
    )
