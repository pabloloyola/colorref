"""Trajectory-level metrics for the ColorRef experiment pipeline.

All distance / improvement metrics operate in CIELAB space.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from colorref.teachers import Feedback

_EPSILON = 1e-8

Color = tuple[float, float, float]  # (L, a, b) in LAB


# ---------------------------------------------------------------------------
# Basic error
# ---------------------------------------------------------------------------

def lab_error(target: Color, guess: Color) -> float:
    """Euclidean ΔE76 between target and guess in LAB."""
    return math.sqrt(sum((t - g) ** 2 for t, g in zip(target, guess)))


# ---------------------------------------------------------------------------
# Improvement metrics
# ---------------------------------------------------------------------------

def absolute_improvement(initial_error: float, final_error: float) -> float:
    """E_0 - E_T. Positive means the model improved."""
    return initial_error - final_error


def relative_improvement(initial_error: float, final_error: float) -> float:
    """(E_0 - E_T) / (E_0 + ε). Positive means improvement."""
    return (initial_error - final_error) / (initial_error + _EPSILON)


def per_turn_improvement(error_t: float, error_t1: float) -> float:
    """E_t - E_{t+1}. Positive when next guess is closer."""
    return error_t - error_t1


# ---------------------------------------------------------------------------
# Directional alignment
# ---------------------------------------------------------------------------

def directional_alignment(
    target: Color,
    current_guess: Color,
    next_guess: Color,
) -> float:
    """Cosine similarity between ideal direction and model update direction.

    ideal_dir  = target - current_guess
    update_dir = next_guess - current_guess

    Returns a value in [-1, 1], or 0.0 when either vector has zero norm.
    """
    ideal = tuple(t - c for t, c in zip(target, current_guess))
    update = tuple(n - c for n, c in zip(next_guess, current_guess))

    dot = sum(i * u for i, u in zip(ideal, update))
    norm_ideal = math.sqrt(sum(i**2 for i in ideal))
    norm_update = math.sqrt(sum(u**2 for u in update))

    denom = norm_ideal * norm_update + _EPSILON
    return dot / denom


# ---------------------------------------------------------------------------
# Constraint satisfaction
# ---------------------------------------------------------------------------

_AXIS_TO_IDX: dict[str, int] = {
    "lab_l": 0,
    "lab_a": 1,
    "lab_b": 2,
}

_HSV_AXIS_TO_IDX: dict[str, int] = {
    "hsv_s": 1,
}


def constraint_satisfied(
    feedback: "Feedback",
    prev_guess_lab: Color,
    next_guess_lab: Color,
    prev_guess_hsv: tuple[float, float, float] | None = None,
    next_guess_hsv: tuple[float, float, float] | None = None,
) -> bool | None:
    """Check whether the model's update satisfies the feedback constraint.

    Returns True / False, or None when no valid constraint can be evaluated.

    For LAB axes (lab_l, lab_a, lab_b): uses LAB coordinates.
    For HSV saturation (hsv_s): requires hsv tuples.
    """
    axis = feedback.constraint_axis
    sign = feedback.constraint_sign

    if axis is None or sign is None:
        return None

    if axis in _AXIS_TO_IDX:
        idx = _AXIS_TO_IDX[axis]
        delta = next_guess_lab[idx] - prev_guess_lab[idx]
        if abs(delta) < _EPSILON:
            return None
        return (sign > 0 and delta > 0) or (sign < 0 and delta < 0)

    if axis == "hsv_s":
        if prev_guess_hsv is None or next_guess_hsv is None:
            return None
        delta = next_guess_hsv[1] - prev_guess_hsv[1]
        if abs(delta) < _EPSILON:
            return None
        return (sign > 0 and delta > 0) or (sign < 0 and delta < 0)

    return None


# ---------------------------------------------------------------------------
# Trajectory path length and efficiency
# ---------------------------------------------------------------------------

def trajectory_path_length(guesses_lab: list[Color]) -> float:
    """Sum of step distances along the guess trajectory in LAB."""
    if len(guesses_lab) < 2:
        return 0.0
    return sum(
        lab_error(guesses_lab[i], guesses_lab[i + 1])
        for i in range(len(guesses_lab) - 1)
    )


def trajectory_efficiency(initial_error: float, final_error: float, path_length: float) -> float:
    """(E_0 - E_T) / (path_length + ε). Improvement per unit of movement."""
    return (initial_error - final_error) / (path_length + _EPSILON)


# ---------------------------------------------------------------------------
# Convergence
# ---------------------------------------------------------------------------

def is_converged(error: float, convergence_delta_e: float) -> bool:
    """True when error is below the convergence threshold."""
    return error < convergence_delta_e


# ---------------------------------------------------------------------------
# Parse metrics helpers
# ---------------------------------------------------------------------------

def parse_success_rate(parse_ok_flags: list[bool]) -> float:
    """Fraction of outputs that parsed successfully."""
    if not parse_ok_flags:
        return float("nan")
    return sum(parse_ok_flags) / len(parse_ok_flags)
