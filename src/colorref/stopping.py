"""Per-example and aggregate convergence metrics for longer-turn analysis.

Implements the stopping, best-so-far, marginal-gain, regression, plateau,
and trajectory-stability metrics defined in spec §2.5.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Per-example convergence statistics
# ---------------------------------------------------------------------------

def compute_per_example_convergence(
    traj_df: pd.DataFrame,
    example_id: int,
) -> dict[str, Any]:
    """Compute convergence statistics for a single example.

    Expects traj_df columns: turn, error_lab, guess_hex (optional), parse_ok.
    Returns a dict of scalars.
    """
    sub = (
        traj_df[traj_df["example_id"] == example_id]
        .sort_values("turn")
        .reset_index(drop=True)
    )
    if sub.empty:
        return {"example_id": example_id, "num_states": 0}

    errors = sub["error_lab"].values
    turns = sub["turn"].values

    # Best-so-far
    best_errors = np.minimum.accumulate(errors)
    best_error = float(best_errors[-1])
    best_turn = int(np.argmin(errors))

    # Final
    final_error = float(errors[-1])

    # Final-vs-best gap
    final_best_gap = final_error - best_error

    # Regression (final > initial)
    initial_error = float(errors[0])
    regressed = bool(final_error > initial_error)

    # Last step length
    last_step_length = None
    if len(errors) >= 2:
        last_step_length = float(abs(errors[-1] - errors[-2]))

    # Stable: last step < 2.0
    stable = None if last_step_length is None else bool(last_step_length < 2.0)

    # Turn-level regression count (error_{t+1} > error_t)
    turn_regressions = int(np.sum(np.diff(errors) > 0))

    return {
        "example_id": example_id,
        "num_states": len(sub),
        "initial_error": initial_error,
        "final_error": final_error,
        "best_error": best_error,
        "best_turn": best_turn,
        "final_best_gap": final_best_gap,
        "regressed": regressed,
        "turn_regressions": turn_regressions,
        "last_step_length": last_step_length,
        "stable": stable,
    }


def compute_all_per_example(traj_df: pd.DataFrame) -> pd.DataFrame:
    """Apply compute_per_example_convergence over all unique examples."""
    rows = [
        compute_per_example_convergence(traj_df, eid)
        for eid in sorted(traj_df["example_id"].unique())
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Aggregate turn-level curves
# ---------------------------------------------------------------------------

def compute_turn_curves(traj_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate mean error and best-so-far error at each turn.

    Returns a DataFrame indexed by turn with columns:
      mean_error, std_error, n_examples,
      mean_best_error, marginal_gain, regression_rate
    """
    # Pivot to (example_id × turn) matrix
    valid = traj_df[traj_df["parse_ok"].fillna(True) & traj_df["error_lab"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()

    pivot = (
        valid.pivot_table(index="example_id", columns="turn", values="error_lab", aggfunc="first")
        .sort_index(axis=1)
    )

    turns = sorted(pivot.columns)

    rows = []
    for t in turns:
        # Errors available up to and including turn t
        sub_cols = [c for c in turns if c <= t]
        best_so_far = pivot[sub_cols].min(axis=1)

        col_t = pivot[t]
        prev_col = pivot[t - 1] if (t - 1) in pivot.columns else None

        n_valid = int(col_t.notna().sum())
        mean_e = float(col_t.mean()) if n_valid > 0 else float("nan")
        std_e = float(col_t.std()) if n_valid > 1 else float("nan")
        mean_best = float(best_so_far.mean()) if n_valid > 0 else float("nan")

        # Marginal gain: best_{t-1} → best_t
        if t > 0 and (t - 1) in pivot.columns:
            prev_sub = [c for c in turns if c <= t - 1]
            prev_best = pivot[prev_sub].min(axis=1)
            marginal_gain = float((prev_best - best_so_far).mean())
        else:
            marginal_gain = float("nan")

        # Turn-level regression rate: error_{t} > error_{t-1}
        if prev_col is not None:
            both_valid = col_t.notna() & prev_col.notna()
            regressed = (col_t[both_valid] > prev_col[both_valid]).sum()
            regression_rate = float(regressed) / int(both_valid.sum()) if both_valid.sum() > 0 else float("nan")
        else:
            regression_rate = float("nan")

        rows.append({
            "turn": t,
            "mean_error": mean_e,
            "std_error": std_e,
            "n_examples": n_valid,
            "mean_best_error": mean_best,
            "marginal_gain": marginal_gain,
            "regression_rate": regression_rate,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plateau detection
# ---------------------------------------------------------------------------

def find_plateau_turn(turn_curve_df: pd.DataFrame, threshold: float = 1.0) -> int | None:
    """Find first turn where mean_best_error improvement over next 2 turns < threshold.

    spec §2.5.5: plateau_turn = first t such that mean_best_error_t - mean_best_error_{t+2} < threshold

    Returns None if not found.
    """
    df = turn_curve_df.sort_values("turn").reset_index(drop=True)
    turns = df["turn"].tolist()
    best_errors = dict(zip(turns, df["mean_best_error"].tolist()))

    for t in turns:
        t2 = t + 2
        if t2 not in best_errors:
            return None
        improvement = best_errors[t] - best_errors[t2]
        if improvement < threshold:
            return int(t)

    return None


# ---------------------------------------------------------------------------
# Convergence-rate curve (fraction converged by each turn)
# ---------------------------------------------------------------------------

def compute_convergence_rate_curve(
    traj_df: pd.DataFrame,
    threshold: float = 5.0,
) -> pd.DataFrame:
    """Fraction of examples that have converged (best_so_far < threshold) by turn t."""
    valid = traj_df[traj_df["error_lab"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()

    pivot = (
        valid.pivot_table(index="example_id", columns="turn", values="error_lab", aggfunc="first")
        .sort_index(axis=1)
    )
    turns = sorted(pivot.columns)
    n_total = len(pivot)

    rows = []
    for t in turns:
        sub_cols = [c for c in turns if c <= t]
        best_so_far = pivot[sub_cols].min(axis=1)
        converged = (best_so_far < threshold).sum()
        rows.append({
            "turn": t,
            "converged_count": int(converged),
            "total": n_total,
            "convergence_rate": float(converged) / n_total if n_total > 0 else 0.0,
        })

    return pd.DataFrame(rows)
