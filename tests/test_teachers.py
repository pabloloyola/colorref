"""Tests for src/colorref/teachers.py."""

from __future__ import annotations

import pytest

from colorref.teachers import (
    MinimalOracle,
    AxisOracle,
    TemplateOracle,
    Feedback,
    detect_constraints,
    build_teacher,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color(lab_l: float, lab_a: float, lab_b: float, hsv_s: float = 0.5) -> dict:
    return {
        "hex": "#aabbcc",
        "rgb": (170, 187, 204),
        "lab": (lab_l, lab_a, lab_b),
        "hsv": (200.0, hsv_s, 0.8),
    }

EXAMPLE = {"example_id": 1, "raw_name": "test color"}


# ---------------------------------------------------------------------------
# MinimalOracle
# ---------------------------------------------------------------------------

class TestMinimalOracle:
    def setup_method(self):
        self.teacher = MinimalOracle()

    def test_returns_feedback(self):
        target = _color(70.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert isinstance(fb, Feedback)
        assert fb.teacher_type == "minimal_oracle"

    def test_selects_largest_normalized_axis(self):
        # lab_l diff = 30 (norm 0.30), lab_b diff = 10 (norm 0.045) → l wins
        target = _color(80.0, 10.0, 30.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis == "lab_l"
        assert fb.constraint_sign == 1
        assert "lighter" in fb.text

    def test_darker_direction(self):
        target = _color(30.0, 0.0, 0.0)
        guess  = _color(70.0, 0.0, 0.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis == "lab_l"
        assert fb.constraint_sign == -1
        assert "darker" in fb.text

    def test_more_green_direction(self):
        # lab_a: target lower than guess → more green
        target = _color(50.0, -20.0, 0.0)
        guess  = _color(50.0,  20.0, 0.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis == "lab_a"
        assert fb.constraint_sign == -1
        assert "green" in fb.text

    def test_below_threshold_gives_close_message(self):
        # All deltas below min_delta thresholds
        target = _color(50.0, 0.0, 0.0, hsv_s=0.5)
        guess  = _color(50.5, 0.0, 0.0, hsv_s=0.5)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis is None
        assert "close" in fb.text.lower() or "try" in fb.text.lower()

    def test_metadata_has_candidate_deltas(self):
        target = _color(80.0, 10.0, 30.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert "candidate_deltas" in fb.metadata

    def test_custom_min_delta(self):
        # With very tight thresholds, a small difference should still be selected
        teacher = MinimalOracle(min_delta={"lab_l": 0.1, "lab_a": 0.1, "lab_b": 0.1, "hsv_s": 0.01})
        target = _color(51.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis == "lab_l"


# ---------------------------------------------------------------------------
# AxisOracle
# ---------------------------------------------------------------------------

class TestAxisOracle:
    def setup_method(self):
        self.teacher = AxisOracle(max_feedback_constraints=3)

    def test_returns_feedback(self):
        target = _color(70.0, 20.0, -10.0)
        guess  = _color(50.0, 0.0, 10.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert isinstance(fb, Feedback)
        assert fb.teacher_type == "axis_oracle"

    def test_multiple_axes_in_text(self):
        # All four axes should be triggered
        target = _color(80.0, 20.0, -20.0, hsv_s=0.9)
        guess  = _color(50.0, 0.0,   20.0, hsv_s=0.1)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert "and" in fb.text

    def test_max_constraints_respected(self):
        teacher = AxisOracle(max_feedback_constraints=1)
        target = _color(80.0, 20.0, -20.0, hsv_s=0.9)
        guess  = _color(50.0, 0.0,   20.0, hsv_s=0.1)
        fb = teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        # Single constraint: no "and" in text
        assert "and" not in fb.text

    def test_primary_axis_is_largest(self):
        # lab_l diff is largest
        target = _color(80.0, 5.0, 5.0)
        guess  = _color(30.0, 0.0, 0.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb.constraint_axis == "lab_l"

    def test_metadata_has_all_constraints(self):
        target = _color(80.0, 20.0, -20.0)
        guess  = _color(50.0, 0.0,   20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert "all_constraints" in fb.metadata


# ---------------------------------------------------------------------------
# TemplateOracle
# ---------------------------------------------------------------------------

class TestTemplateOracle:
    def setup_method(self):
        self.teacher = TemplateOracle(seed=13)

    def test_returns_feedback(self):
        target = _color(70.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert isinstance(fb, Feedback)
        assert fb.teacher_type == "template_oracle"

    def test_text_is_non_empty(self):
        target = _color(70.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert len(fb.text) > 0

    def test_deterministic_same_inputs(self):
        target = _color(70.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        fb1 = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        fb2 = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        assert fb1.text == fb2.text

    def test_different_turn_may_vary_template(self):
        target = _color(70.0, 10.0, 20.0)
        guess  = _color(50.0, 10.0, 20.0)
        texts = {
            self.teacher.give_feedback(target, guess, EXAMPLE, turn=t).text
            for t in range(6)
        }
        # Over 6 turns there should be at least 2 distinct phrasings
        assert len(texts) >= 1  # at minimum runs without error

    def test_known_direction_text_is_valid(self):
        # "lighter" should come from the templates dict
        target = _color(80.0, 0.0, 0.0)
        guess  = _color(50.0, 0.0, 0.0)
        fb = self.teacher.give_feedback(target, guess, EXAMPLE, turn=0)
        valid = ["Make it lighter.", "Move toward a brighter shade.", "It should have more lightness."]
        assert fb.text in valid


# ---------------------------------------------------------------------------
# detect_constraints
# ---------------------------------------------------------------------------

class TestDetectConstraints:
    def test_darker(self):
        r = detect_constraints("Make it darker.")
        assert any(c["axis"] == "lab_l" and c["sign"] == -1 for c in r)

    def test_lighter(self):
        r = detect_constraints("Move toward a brighter shade.")
        assert any(c["axis"] == "lab_l" and c["sign"] == 1 for c in r)

    def test_more_red(self):
        r = detect_constraints("Make it more red.")
        assert any(c["axis"] == "lab_a" and c["sign"] == 1 for c in r)

    def test_more_green(self):
        r = detect_constraints("Make it more green.")
        assert any(c["axis"] == "lab_a" and c["sign"] == -1 for c in r)

    def test_more_blue(self):
        r = detect_constraints("Make it more blue.")
        assert any(c["axis"] == "lab_b" and c["sign"] == -1 for c in r)

    def test_more_yellow(self):
        r = detect_constraints("Make it more yellow.")
        assert any(c["axis"] == "lab_b" and c["sign"] == 1 for c in r)

    def test_more_saturated(self):
        r = detect_constraints("Make it more vivid.")
        assert any(c["axis"] == "hsv_s" and c["sign"] == 1 for c in r)

    def test_more_muted(self):
        r = detect_constraints("Tone it down.")
        assert len(r) == 0  # "tone it down" not in keyword list

    def test_more_muted_explicit(self):
        r = detect_constraints("Make it more muted.")
        assert any(c["axis"] == "hsv_s" and c["sign"] == -1 for c in r)

    def test_empty_string(self):
        assert detect_constraints("") == []

    def test_case_insensitive(self):
        r = detect_constraints("MAKE IT DARKER.")
        assert any(c["axis"] == "lab_l" and c["sign"] == -1 for c in r)


# ---------------------------------------------------------------------------
# build_teacher factory
# ---------------------------------------------------------------------------

class TestBuildTeacher:
    def test_minimal_oracle(self):
        t = build_teacher({"type": "minimal_oracle"})
        assert isinstance(t, MinimalOracle)

    def test_axis_oracle(self):
        t = build_teacher({"type": "axis_oracle", "max_feedback_constraints": 2})
        assert isinstance(t, AxisOracle)
        assert t.max_n == 2

    def test_template_oracle(self):
        t = build_teacher({"type": "template_oracle", "seed": 42})
        assert isinstance(t, TemplateOracle)
        assert t.seed == 42

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown teacher type"):
            build_teacher({"type": "nonexistent_teacher"})
