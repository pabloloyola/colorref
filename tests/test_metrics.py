"""Tests for src/colorref/metrics.py."""

import math
import pytest

from colorref.metrics import (
    lab_error,
    absolute_improvement,
    relative_improvement,
    per_turn_improvement,
    directional_alignment,
    constraint_satisfied,
    trajectory_path_length,
    trajectory_efficiency,
    is_converged,
    parse_success_rate,
)


# ---------------------------------------------------------------------------
# Minimal stub to avoid importing the full teachers module
# ---------------------------------------------------------------------------

class _FakeFeedback:
    def __init__(self, axis, sign):
        self.constraint_axis = axis
        self.constraint_sign = sign


# ---------------------------------------------------------------------------
# lab_error
# ---------------------------------------------------------------------------

class TestLabError:
    def test_zero_for_same(self):
        c = (50.0, 10.0, -20.0)
        assert lab_error(c, c) == 0.0

    def test_known_value(self):
        assert abs(lab_error((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) - 5.0) < 1e-9

    def test_symmetric(self):
        c1, c2 = (10.0, 20.0, 30.0), (40.0, 50.0, 60.0)
        assert abs(lab_error(c1, c2) - lab_error(c2, c1)) < 1e-12


# ---------------------------------------------------------------------------
# Improvement metrics
# ---------------------------------------------------------------------------

class TestImprovementMetrics:
    def test_absolute_positive(self):
        assert absolute_improvement(50.0, 30.0) == pytest.approx(20.0)

    def test_absolute_negative(self):
        assert absolute_improvement(30.0, 50.0) == pytest.approx(-20.0)

    def test_relative_perfect(self):
        r = relative_improvement(50.0, 0.0)
        assert abs(r - 1.0) < 1e-4

    def test_relative_no_change(self):
        assert abs(relative_improvement(50.0, 50.0)) < 1e-6

    def test_relative_epsilon_prevents_div_zero(self):
        r = relative_improvement(0.0, 0.0)
        assert math.isfinite(r)

    def test_per_turn_positive(self):
        assert per_turn_improvement(30.0, 20.0) == pytest.approx(10.0)

    def test_per_turn_negative(self):
        assert per_turn_improvement(20.0, 30.0) == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Directional alignment
# ---------------------------------------------------------------------------

class TestDirectionalAlignment:
    def test_perfect_alignment(self):
        target = (10.0, 0.0, 0.0)
        guess  = (0.0, 0.0, 0.0)
        # Moving exactly toward target
        next_guess = (5.0, 0.0, 0.0)
        a = directional_alignment(target, guess, next_guess)
        assert abs(a - 1.0) < 1e-9

    def test_perfect_misalignment(self):
        target = (10.0, 0.0, 0.0)
        guess  = (0.0, 0.0, 0.0)
        next_guess = (-5.0, 0.0, 0.0)  # moving away
        a = directional_alignment(target, guess, next_guess)
        assert a < 0.0

    def test_orthogonal(self):
        target = (10.0, 0.0, 0.0)
        guess  = (0.0, 0.0, 0.0)
        next_guess = (0.0, 5.0, 0.0)  # orthogonal move
        a = directional_alignment(target, guess, next_guess)
        assert abs(a) < 1e-9

    def test_zero_update_returns_near_zero(self):
        target = (10.0, 0.0, 0.0)
        guess  = (5.0, 0.0, 0.0)
        a = directional_alignment(target, guess, guess)  # no update
        assert abs(a) < 1e-6

    def test_already_at_target_returns_near_zero(self):
        c = (5.0, 3.0, 1.0)
        a = directional_alignment(c, c, (6.0, 3.0, 1.0))
        assert abs(a) < 1e-6


# ---------------------------------------------------------------------------
# Constraint satisfaction
# ---------------------------------------------------------------------------

class TestConstraintSatisfied:
    def test_lab_l_lighter_satisfied(self):
        fb = _FakeFeedback("lab_l", +1)
        prev = (40.0, 0.0, 0.0)
        nxt  = (50.0, 0.0, 0.0)
        assert constraint_satisfied(fb, prev, nxt) is True

    def test_lab_l_lighter_violated(self):
        fb = _FakeFeedback("lab_l", +1)
        prev = (50.0, 0.0, 0.0)
        nxt  = (40.0, 0.0, 0.0)
        assert constraint_satisfied(fb, prev, nxt) is False

    def test_lab_a_more_red_satisfied(self):
        fb = _FakeFeedback("lab_a", +1)
        prev = (50.0, 10.0, 0.0)
        nxt  = (50.0, 20.0, 0.0)
        assert constraint_satisfied(fb, prev, nxt) is True

    def test_lab_b_more_blue_satisfied(self):
        # more blue → lab_b decreases (sign = -1)
        fb = _FakeFeedback("lab_b", -1)
        prev = (50.0, 0.0, 20.0)
        nxt  = (50.0, 0.0, 10.0)
        assert constraint_satisfied(fb, prev, nxt) is True

    def test_hsv_s_more_saturated(self):
        fb = _FakeFeedback("hsv_s", +1)
        assert constraint_satisfied(
            fb,
            (50.0, 0.0, 0.0), (50.0, 0.0, 0.0),
            prev_guess_hsv=(0.0, 0.3, 0.8),
            next_guess_hsv=(0.0, 0.6, 0.8),
        ) is True

    def test_none_when_no_axis(self):
        fb = _FakeFeedback(None, None)
        assert constraint_satisfied(fb, (50.0, 0.0, 0.0), (50.0, 1.0, 0.0)) is None

    def test_none_when_no_movement_on_axis(self):
        fb = _FakeFeedback("lab_l", +1)
        c = (50.0, 0.0, 0.0)
        assert constraint_satisfied(fb, c, c) is None

    def test_hsv_s_without_hsv_tuples(self):
        fb = _FakeFeedback("hsv_s", +1)
        assert constraint_satisfied(fb, (50.0, 0.0, 0.0), (50.0, 0.0, 0.0)) is None


# ---------------------------------------------------------------------------
# Trajectory metrics
# ---------------------------------------------------------------------------

class TestTrajectoryMetrics:
    def test_path_length_two_points(self):
        guesses = [(0.0, 0.0, 0.0), (3.0, 4.0, 0.0)]
        assert abs(trajectory_path_length(guesses) - 5.0) < 1e-9

    def test_path_length_single_point(self):
        assert trajectory_path_length([(0.0, 0.0, 0.0)]) == 0.0

    def test_path_length_empty(self):
        assert trajectory_path_length([]) == 0.0

    def test_efficiency_positive(self):
        eff = trajectory_efficiency(50.0, 10.0, 20.0)
        assert eff == pytest.approx(40.0 / 20.0)

    def test_efficiency_zero_path_no_crash(self):
        eff = trajectory_efficiency(50.0, 30.0, 0.0)
        assert math.isfinite(eff)


# ---------------------------------------------------------------------------
# Convergence and parse metrics
# ---------------------------------------------------------------------------

class TestConvergence:
    def test_converged(self):
        assert is_converged(4.9, 5.0) is True

    def test_not_converged(self):
        assert is_converged(5.1, 5.0) is False

    def test_boundary(self):
        assert is_converged(5.0, 5.0) is False


class TestParseSuccessRate:
    def test_all_ok(self):
        assert parse_success_rate([True, True, True]) == pytest.approx(1.0)

    def test_none_ok(self):
        assert parse_success_rate([False, False]) == pytest.approx(0.0)

    def test_mixed(self):
        assert parse_success_rate([True, False, True, True]) == pytest.approx(0.75)

    def test_empty_is_nan(self):
        assert math.isnan(parse_success_rate([]))
