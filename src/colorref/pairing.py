"""Shared-example alignment and case selection for oracle vs LLM teacher pairs.

Identifies examples present in both a reference (oracle/template-oracle) and a
comparison (LLM teacher) run, computes per-example trajectory statistics, audits
LLM feedback directional correctness, and classifies each example into one of the
five case types defined in spec §4.4.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from colorref.colors import color_distance_lab
from colorref.teachers import _compute_candidate_deltas, detect_constraints

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_hex(h: str | None) -> str | None:
    if not h:
        return None
    h = str(h).strip()
    return h if h.startswith("#") else f"#{h}"


def _lab_tuple(row: pd.Series, prefix: str = "guess") -> tuple[float, float, float] | None:
    try:
        return (
            float(row[f"{prefix}_lab_l"]),
            float(row[f"{prefix}_lab_a"]),
            float(row[f"{prefix}_lab_b"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _true_lab(row: pd.Series) -> tuple[float, float, float] | None:
    try:
        return (float(row["true_lab_l"]), float(row["true_lab_a"]), float(row["true_lab_b"]))
    except (KeyError, TypeError, ValueError):
        return None


def _true_hsv(row: pd.Series) -> tuple[float, float, float] | None:
    try:
        return (float(row["true_hsv_h"]), float(row["true_hsv_s"]), float(row["true_hsv_v"]))
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Per-example stats from a trajectory parquet
# ---------------------------------------------------------------------------

def _extract_example_stats(
    traj: pd.DataFrame,
    example_id: int,
    run_id: str,
) -> dict[str, Any]:
    """Return initial_error, final_error, initial_hex, final_hex for one example."""
    sub = traj[traj["example_id"] == example_id].sort_values("turn")
    if sub.empty:
        return {}
    row0 = sub.iloc[0]
    row_last = sub.iloc[-1]
    return {
        "run_id": run_id,
        "initial_hex": _norm_hex(str(row0.get("guess_hex", ""))),
        "final_hex": _norm_hex(str(row_last.get("guess_hex", ""))),
        "initial_error": float(row0["error_lab"]) if pd.notna(row0.get("error_lab")) else None,
        "final_error": float(row_last["error_lab"]) if pd.notna(row_last.get("error_lab")) else None,
        "num_turns": len(sub),
        "initial_lab": _lab_tuple(row0),
        "final_lab": _lab_tuple(row_last),
        "target_lab": _true_lab(row0),
        "target_hsv": _true_hsv(row0),
        "true_hex": _norm_hex(str(row0["true_hex"])) if pd.notna(row0.get("true_hex")) else None,
        "regime_label": str(row0.get("regime_label", "")),
        "raw_name": str(row0.get("raw_name", "")),
    }


# ---------------------------------------------------------------------------
# Feedback precision for LLM teachers
# ---------------------------------------------------------------------------

_MIN_DELTA_DEFAULT = {
    "lab_l": 2.0,
    "lab_a": 3.0,
    "lab_b": 3.0,
    "hsv_s": 0.05,
}


def _compute_turn_feedback_precision(
    traj_sub: pd.DataFrame,
    fb_sub: pd.DataFrame,
    min_delta: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute constraint detection and directional precision for one LLM example.

    Returns:
        detected_constraints  – total detected direction keywords across all turns
        correct_constraints   – number that match oracle direction on same axis
        precision             – correct / detected (or 0 if none detected)
    """
    min_delta = min_delta or _MIN_DELTA_DEFAULT

    traj_by_turn: dict[int, pd.Series] = {
        int(r["turn"]): r
        for _, r in traj_sub.iterrows()
    }

    detected_total = 0
    correct_total = 0

    for _, fb_row in fb_sub.iterrows():
        turn = int(fb_row["turn"])
        feedback_text = str(fb_row.get("feedback_text", ""))
        detected = detect_constraints(feedback_text)
        detected_total += len(detected)

        # Build color dicts to compute oracle candidates at this turn
        # The feedback is given on the guess at `turn` (before revision)
        guess_row = traj_by_turn.get(turn)
        if guess_row is None or len(detected) == 0:
            continue

        guess_lab = _lab_tuple(guess_row)
        guess_hsv = (
            float(guess_row.get("guess_hsv_h", 0)),
            float(guess_row.get("guess_hsv_s", 0)),
            float(guess_row.get("guess_hsv_v", 0)),
        )
        target_lab = _true_lab(guess_row)
        target_hsv = _true_hsv(guess_row)

        if not (guess_lab and target_lab and target_hsv):
            continue

        target_cd = {"lab": target_lab, "hsv": target_hsv}
        guess_cd = {"lab": guess_lab, "hsv": guess_hsv}

        try:
            oracle_candidates = _compute_candidate_deltas(target_cd, guess_cd, min_delta)
        except Exception:
            continue

        oracle_by_axis: dict[str, int] = {c["axis"]: c["sign"] for c in oracle_candidates}

        for d in detected:
            axis = d["axis"]
            sign = d["sign"]
            if axis in oracle_by_axis and oracle_by_axis[axis] == sign:
                correct_total += 1

    precision = correct_total / detected_total if detected_total > 0 else 0.0
    return {
        "llm_detected_constraints": detected_total,
        "llm_correct_constraints": correct_total,
        "llm_precision": precision,
    }


# ---------------------------------------------------------------------------
# Case type classification
# ---------------------------------------------------------------------------

def _classify_case_types(row: dict[str, Any]) -> list[str]:
    """Return a list of matching case types (may be empty)."""
    types = []

    oracle_init = row.get("oracle_initial_error")
    oracle_final = row.get("oracle_final_error")
    oracle_ri = row.get("oracle_relative_improvement")
    llm_init = row.get("llm_initial_error")
    llm_final = row.get("llm_final_error")
    llm_ri = row.get("llm_relative_improvement")
    init_dist = row.get("initial_guess_distance_lab")
    precision = row.get("llm_precision", 1.0)
    detected = row.get("llm_detected_constraints", 0)
    correct = row.get("llm_correct_constraints", 0)

    # Case 1: LLM failure, oracle success
    if (oracle_final is not None and oracle_final < 10
            and llm_final is not None and llm_final > 25
            and llm_ri is not None and llm_ri <= 0):
        types.append("case1_llm_fail_oracle_success")

    # Case 2: Same (or close) initial guess, divergent trajectory
    if (init_dist is not None and init_dist < 5
            and oracle_final is not None and llm_final is not None
            and oracle_final + 20 < llm_final):
        types.append("case2_same_init_divergent")

    # Case 3: LLM wrong-direction feedback
    if (precision < 0.4
            and detected > 0
            and (detected - correct) > 0):
        types.append("case3_llm_wrong_direction")

    # Case 5: Overcorrection / regression (LLM)
    if (llm_init is not None and llm_init < 10
            and llm_final is not None and llm_final > llm_init + 20):
        types.append("case5_overcorrection_regression")

    return types


def _selection_score(row: dict[str, Any]) -> float:
    """Higher is more illustrative.

    Score = oracle improvement - llm improvement + precision penalty.
    """
    oracle_imp = (row.get("oracle_initial_error") or 0) - (row.get("oracle_final_error") or 0)
    llm_imp = (row.get("llm_initial_error") or 0) - (row.get("llm_final_error") or 0)
    precision_pen = max(0.0, 0.5 - (row.get("llm_precision") or 0)) * 20
    return oracle_imp - llm_imp + precision_pen


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_run_data(
    run_dir: Path | str,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Load trajectories + feedback from a run directory.

    Returns (traj_df, fb_df, run_id).
    """
    run_dir = Path(run_dir)
    traj = pd.read_parquet(run_dir / "games" / "trajectories.parquet")
    fb_path = run_dir / "games" / "feedback.parquet"
    fb = pd.read_parquet(fb_path) if fb_path.exists() else pd.DataFrame()
    run_id = run_dir.name
    return traj, fb, run_id


def build_pair_case_table(
    oracle_run_dir: Path | str,
    llm_run_dir: Path | str,
    oracle_label: str | None = None,
    llm_label: str | None = None,
    min_delta: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build a case table for oracle vs LLM teacher on all shared examples.

    Returns a DataFrame with columns matching spec §4.5, sorted by
    selection_score descending.
    """
    oracle_run_dir = Path(oracle_run_dir)
    llm_run_dir = Path(llm_run_dir)

    oracle_traj, oracle_fb, oracle_run_id = load_run_data(oracle_run_dir)
    llm_traj, llm_fb, llm_run_id = load_run_data(llm_run_dir)

    shared_ids = sorted(set(oracle_traj["example_id"]) & set(llm_traj["example_id"]))
    logger.info("Shared examples: %d", len(shared_ids))

    # Detect teacher types from trajectory
    oracle_teacher = (
        str(oracle_traj["teacher_type"].iloc[0]) if not oracle_traj.empty else (oracle_label or "oracle")
    )
    llm_teacher = (
        str(llm_traj["teacher_type"].iloc[0]) if not llm_traj.empty else (llm_label or "llm_teacher")
    )

    rows = []
    for eid in shared_ids:
        o_stats = _extract_example_stats(oracle_traj, eid, oracle_run_id)
        l_stats = _extract_example_stats(llm_traj, eid, llm_run_id)

        if not o_stats or not l_stats:
            continue

        # Initial guess distance
        init_dist = None
        if o_stats["initial_lab"] and l_stats["initial_lab"]:
            try:
                init_dist = color_distance_lab(o_stats["initial_lab"], l_stats["initial_lab"])
            except Exception:
                pass

        # Relative improvement
        def _ri(init, final):
            if init and final and init > 0:
                return (init - final) / init
            return None

        oracle_ri = _ri(o_stats["initial_error"], o_stats["final_error"])
        llm_ri = _ri(l_stats["initial_error"], l_stats["final_error"])

        # LLM feedback precision
        llm_fb_sub = llm_fb[llm_fb["example_id"] == eid] if not llm_fb.empty else pd.DataFrame()
        llm_traj_sub = llm_traj[llm_traj["example_id"] == eid].sort_values("turn")
        precision_info = _compute_turn_feedback_precision(llm_traj_sub, llm_fb_sub, min_delta)

        row = {
            "example_id": eid,
            "raw_name": o_stats["raw_name"],
            "regime_label": o_stats["regime_label"],
            "target_hex": o_stats["true_hex"],
            "target_lab_l": o_stats["target_lab"][0] if o_stats["target_lab"] else None,
            "target_lab_a": o_stats["target_lab"][1] if o_stats["target_lab"] else None,
            "target_lab_b": o_stats["target_lab"][2] if o_stats["target_lab"] else None,
            "oracle_run_id": oracle_run_id,
            "llm_run_id": llm_run_id,
            "oracle_teacher_type": oracle_teacher,
            "llm_teacher_type": llm_teacher,
            "oracle_initial_hex": o_stats["initial_hex"],
            "llm_initial_hex": l_stats["initial_hex"],
            "initial_guess_distance_lab": init_dist,
            "oracle_initial_error": o_stats["initial_error"],
            "oracle_final_error": o_stats["final_error"],
            "oracle_relative_improvement": oracle_ri,
            "llm_initial_error": l_stats["initial_error"],
            "llm_final_error": l_stats["final_error"],
            "llm_relative_improvement": llm_ri,
            **precision_info,
        }

        case_types = _classify_case_types(row)
        row["case_type"] = "|".join(case_types) if case_types else "none"
        row["selection_score"] = _selection_score(row)

        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("selection_score", ascending=False).reset_index(drop=True)
    return df


def select_top_cases(
    case_df: pd.DataFrame,
    n_per_type: int = 8,
    also_top_score: int = 10,
) -> pd.DataFrame:
    """Return a curated subset: top-N per case type + overall top-N by score."""
    parts = []

    # Top by score overall
    parts.append(case_df.head(also_top_score))

    # Top per case type
    for case_type_prefix in [
        "case1_llm_fail_oracle_success",
        "case2_same_init_divergent",
        "case3_llm_wrong_direction",
        "case5_overcorrection_regression",
    ]:
        mask = case_df["case_type"].str.contains(case_type_prefix, na=False)
        parts.append(case_df[mask].head(n_per_type))

    combined = pd.concat(parts).drop_duplicates(subset=["example_id"]).reset_index(drop=True)
    return combined.sort_values("selection_score", ascending=False).reset_index(drop=True)
