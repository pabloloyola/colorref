"""Tests for v2 turn accounting and per-example summaries."""

import pandas as pd
import pytest

from colorref.example_summary import compute_turn_accounting, summarize_example_from_tables


def _traj_row(turn, error, parse_ok=True, phase="revision"):
    return {
        "run_id": "test",
        "example_id": 1,
        "raw_name": "test red",
        "true_hex": "#ff0000",
        "true_lab_l": 50.0,
        "true_lab_a": 50.0,
        "true_lab_b": 40.0,
        "model_alias": "m",
        "teacher_type": "minimal_oracle",
        "turn": turn,
        "phase": "initial_guess" if turn == 0 else phase,
        "parse_ok": parse_ok,
        "error_lab": error,
        "guess_hex": "#808080",
        "guess_lab_l": 50.0 - turn * 5,
        "guess_lab_a": 50.0,
        "guess_lab_b": 40.0,
        "guess_hsv_h": 0.0,
        "guess_hsv_s": 0.5,
        "guess_hsv_v": 0.5,
        "regime_label": "explicit_grounded",
        "abstraction_score": 0.1,
        "explicitness_score": 0.9,
        "prototype_score": 0.5,
        "rarity_score": 0.5,
        "hue_bin": "red",
        "lightness_bin": "medium",
        "saturation_bin": "medium",
        "value_bin": "medium",
    }


def _fb_row(turn, direction="darker", axis="lab_l", sign=-1):
    return {
        "example_id": 1,
        "turn": turn,
        "teacher_type": "minimal_oracle",
        "feedback_text": f"Make it {direction}.",
        "constraint_axis": axis,
        "constraint_direction": direction,
        "constraint_sign": sign,
        "all_constraints_json": None,
    }


class TestTurnAccountingInitialConvergence:
    def test_converged_at_turn_zero(self):
        traj = pd.DataFrame([_traj_row(0, 3.0)])
        fb = pd.DataFrame()
        acc = compute_turn_accounting(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert acc["num_feedback_rounds_issued"] == 0
        assert acc["num_revision_attempts"] == 0
        assert acc["num_states"] == 1
        assert acc["converged_at_round"] == 0
        assert acc["converged"] is True
        assert acc["completed_all_rounds"] is False


class TestTurnAccountingAfterOneRevision:
    def test_converged_after_first_revision(self):
        traj = pd.DataFrame([
            _traj_row(0, 40.0, phase="initial_guess"),
            _traj_row(1, 3.0),
        ])
        fb = pd.DataFrame([_fb_row(0)])
        acc = compute_turn_accounting(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert acc["num_feedback_rounds_issued"] == 1
        assert acc["num_revision_attempts"] == 1
        assert acc["num_states"] == 2
        assert acc["converged_at_round"] == 1


class TestTurnAccountingMaxTurnsNoConvergence:
    def test_completed_all_rounds(self):
        rows = [_traj_row(0, 40.0, phase="initial_guess")]
        for t in range(1, 4):
            rows.append(_traj_row(t, 40.0 - t))
        traj = pd.DataFrame(rows)
        fb = pd.DataFrame([_fb_row(t) for t in range(3)])
        acc = compute_turn_accounting(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert acc["num_feedback_rounds_issued"] == 3
        assert acc["num_revision_attempts"] == 3
        assert acc["converged"] is False
        assert acc["completed_all_rounds"] is True


class TestParseFailureTurn0:
    def test_no_states(self):
        traj = pd.DataFrame([_traj_row(0, None, parse_ok=False, phase="initial_guess")])
        fb = pd.DataFrame()
        acc = compute_turn_accounting(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert acc["num_states"] == 0
        assert acc["converged_at_round"] is None


class TestParseFailureAfterRevision:
    def test_stopped_after_bad_revision(self):
        traj = pd.DataFrame([
            _traj_row(0, 40.0, phase="initial_guess"),
            _traj_row(1, None, parse_ok=False),
        ])
        fb = pd.DataFrame([_fb_row(0)])
        summary = summarize_example_from_tables(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert summary["num_feedback_rounds_issued"] == 1
        assert summary["num_revision_attempts"] == 1
        assert summary["num_states"] == 1
        assert summary["status"] != "converged"


class TestInvariants:
    def test_bounds(self):
        traj = pd.DataFrame([
            _traj_row(0, 40.0, phase="initial_guess"),
            _traj_row(1, 30.0),
            _traj_row(2, 20.0),
        ])
        fb = pd.DataFrame([_fb_row(0), _fb_row(1)])
        acc = compute_turn_accounting(traj, fb, max_turns_configured=3, convergence_delta_e=5.0)
        assert 0 <= acc["num_feedback_rounds_issued"] <= 3
        assert 0 <= acc["num_revision_attempts"] <= 3
        assert 1 <= acc["num_states"] <= 4
