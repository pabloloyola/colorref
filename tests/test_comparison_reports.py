"""Tests for comparison report helpers."""

from colorref.comparison_reports import (
    condition_label_from_run_id,
    max_constraints_from_label,
    teacher_family_from_label,
)


def test_condition_label_bandwidth_runs():
    assert (
        condition_label_from_run_id(
            "20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000"
        )
        == "axis_c3"
    )
    assert (
        condition_label_from_run_id(
            "20260516_121822_feedback_minimal_main_qwen3_14b_minimal_oracle_main_1000"
        )
        == "minimal_c1"
    )
    assert (
        condition_label_from_run_id(
            "20260518_014252_oneshot_main_4000_qwen3_14b_main_4000"
        )
        == "oneshot"
    )
    assert (
        condition_label_from_run_id(
            "20260518_034542_feedback_template_llm_vocab_main_4000_qwen3_14b_template_oracle_llm_vocab_main_4000"
        )
        == "template_oracle_llm_vocab"
    )


def test_max_constraints_from_label():
    assert max_constraints_from_label("axis_c3") == 3
    assert max_constraints_from_label("minimal_c1") == 1
    assert max_constraints_from_label("oneshot") == 0


def test_teacher_family_from_label():
    assert teacher_family_from_label("axis_c2") == "axis"
    assert teacher_family_from_label("template_c1") == "template"
    assert teacher_family_from_label("llm_teacher_hex_only") == "llm"
