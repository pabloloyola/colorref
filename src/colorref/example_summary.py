"""Per-example trajectory summaries (v2 turn accounting and metrics)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from colorref.metrics import (
    absolute_improvement,
    constraint_satisfied,
    directional_alignment,
    is_converged,
    relative_improvement,
    trajectory_efficiency,
    trajectory_path_length,
)
from colorref.teachers import Feedback, detect_constraints

_EPSILON = 1e-8


def _constraints_for_feedback_row(fb_row: pd.Series) -> list[dict]:
    """Extract (axis, sign) constraints from feedback row metadata or text."""
    raw = fb_row.get("all_constraints_json")
    if raw is not None and pd.notna(raw) and str(raw).strip():
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, list) and parsed:
                return [
                    {"axis": c["axis"], "sign": c["sign"]}
                    for c in parsed
                    if c.get("axis") is not None and c.get("sign") is not None
                ]
        except (json.JSONDecodeError, TypeError):
            pass

    detected = detect_constraints(str(fb_row.get("feedback_text", "")))
    if detected:
        return [{"axis": d["axis"], "sign": d["sign"]} for d in detected]

    axis = fb_row.get("constraint_axis")
    sign = fb_row.get("constraint_sign")
    if axis is not None and sign is not None and pd.notna(axis) and pd.notna(sign):
        return [{"axis": axis, "sign": int(sign)}]

    return []


def _step_constraint_satisfaction(
    constraints: list[dict],
    prev_lab: tuple[float, float, float],
    next_lab: tuple[float, float, float],
    prev_hsv: tuple[float, float, float] | None,
    next_hsv: tuple[float, float, float] | None,
) -> float | None:
    if not constraints:
        return None
    results: list[float] = []
    for c in constraints:
        fb = Feedback(
            text="",
            teacher_type="",
            constraint_axis=c["axis"],
            constraint_direction=None,
            constraint_sign=c["sign"],
            target_value=None,
            guess_value=None,
            delta=None,
        )
        sat = constraint_satisfied(fb, prev_lab, next_lab, prev_hsv, next_hsv)
        if sat is not None:
            results.append(float(sat))
    if not results:
        return None
    return sum(results) / len(results)


def compute_turn_accounting(
    traj_sub: pd.DataFrame,
    fb_sub: pd.DataFrame,
    max_turns_configured: int,
    convergence_delta_e: float,
) -> dict[str, Any]:
    """v2 turn-count fields with documented invariants."""
    traj_sub = traj_sub.sort_values("turn")
    valid = traj_sub[traj_sub["parse_ok"]]

    num_feedback_rounds_issued = len(fb_sub)
    num_revision_attempts = int((traj_sub["turn"] > 0).sum())
    num_states = len(valid)

    converged_at_round: int | None = None
    for _, row in valid.iterrows():
        err = row.get("error_lab")
        if err is not None and pd.notna(err) and is_converged(float(err), convergence_delta_e):
            turn = int(row["turn"])
            converged_at_round = 0 if turn == 0 else turn
            break

    final_error = None
    if len(valid) > 0:
        fe = valid.iloc[-1]["error_lab"]
        if fe is not None and pd.notna(fe):
            final_error = float(fe)

    converged = (
        final_error is not None and is_converged(final_error, convergence_delta_e)
    )

    parse_failures = int((~traj_sub["parse_ok"].astype(bool)).sum())
    stopped_early = converged or (
        parse_failures > 0 and len(valid) == 0
    ) or (
        parse_failures > 0
        and len(valid) > 0
        and num_revision_attempts > 0
        and not bool(traj_sub.iloc[-1]["parse_ok"])
    )

    completed_all_rounds = (
        not converged
        and num_feedback_rounds_issued >= max_turns_configured
        and num_feedback_rounds_issued > 0
    )

    if converged and converged_at_round is not None and converged_at_round == 0:
        completed_all_rounds = False

    return {
        "max_turns_configured": max_turns_configured,
        "num_feedback_rounds_issued": num_feedback_rounds_issued,
        "num_revision_attempts": num_revision_attempts,
        "num_states": num_states,
        "converged_at_round": converged_at_round,
        "completed_all_rounds": completed_all_rounds,
        "converged": converged,
        "stopped_early": stopped_early,
    }


def summarize_example_from_tables(
    traj_sub: pd.DataFrame,
    fb_sub: pd.DataFrame,
    max_turns_configured: int = 3,
    convergence_delta_e: float = 5.0,
) -> dict[str, Any]:
    """Recompute full per-example summary from trajectory + feedback tables."""
    traj_sub = traj_sub.sort_values("turn")
    valid = traj_sub[traj_sub["parse_ok"]].copy()

    errors = [
        float(r["error_lab"])
        for _, r in valid.iterrows()
        if r["error_lab"] is not None and pd.notna(r["error_lab"])
    ]

    initial_error = errors[0] if errors else None
    final_error = errors[-1] if errors else None
    best_error = min(errors) if errors else None
    best_turn = None
    if best_error is not None:
        for _, r in valid.iterrows():
            if r["error_lab"] is not None and float(r["error_lab"]) == best_error:
                best_turn = int(r["turn"])
                break

    abs_imp = (
        absolute_improvement(initial_error, final_error)
        if initial_error is not None and final_error is not None
        else None
    )
    rel_imp = (
        relative_improvement(initial_error, final_error)
        if initial_error is not None and final_error is not None
        else None
    )

    labs = [
        (float(r["guess_lab_l"]), float(r["guess_lab_a"]), float(r["guess_lab_b"]))
        for _, r in valid.iterrows()
        if all(r.get(k) is not None and pd.notna(r.get(k)) for k in ("guess_lab_l", "guess_lab_a", "guess_lab_b"))
    ]
    path_len = trajectory_path_length(labs) if len(labs) >= 2 else 0.0
    traj_eff = (
        trajectory_efficiency(initial_error, final_error, path_len)
        if initial_error is not None and final_error is not None
        else None
    )

    alignments: list[float] = []
    valid_list = valid.to_dict("records")
    for i in range(len(valid_list) - 1):
        r0, r1 = valid_list[i], valid_list[i + 1]
        if all(r0.get(k) is not None for k in ("guess_lab_l", "guess_lab_a", "guess_lab_b", "true_lab_l", "true_lab_a", "true_lab_b")):
            if all(r1.get(k) is not None for k in ("guess_lab_l", "guess_lab_a", "guess_lab_b")):
                tgt = (float(r0["true_lab_l"]), float(r0["true_lab_a"]), float(r0["true_lab_b"]))
                c0 = (float(r0["guess_lab_l"]), float(r0["guess_lab_a"]), float(r0["guess_lab_b"]))
                c1 = (float(r1["guess_lab_l"]), float(r1["guess_lab_a"]), float(r1["guess_lab_b"]))
                a = directional_alignment(tgt, c0, c1)
                ideal = tuple(t - c for t, c in zip(tgt, c0))
                upd = tuple(n - c for n, c in zip(c1, c0))
                norm_i = sum(x * x for x in ideal) ** 0.5
                norm_u = sum(x * x for x in upd) ** 0.5
                if norm_i >= _EPSILON and norm_u >= _EPSILON:
                    alignments.append(a)

    mean_align = sum(alignments) / len(alignments) if alignments else None

    step_sats: list[float] = []
    constraints_per_step: list[int] = []
    for _, fb_row in fb_sub.iterrows():
        fb_turn = int(fb_row["turn"])
        prev_rec = traj_sub[traj_sub["turn"] == fb_turn]
        next_rec = traj_sub[traj_sub["turn"] == fb_turn + 1]
        if prev_rec.empty or next_rec.empty:
            continue
        p, n = prev_rec.iloc[0], next_rec.iloc[0]
        if not (p["parse_ok"] and n["parse_ok"]):
            continue
        constraints = _constraints_for_feedback_row(fb_row)
        constraints_per_step.append(len(constraints))
        prev_lab = (float(p["guess_lab_l"]), float(p["guess_lab_a"]), float(p["guess_lab_b"]))
        next_lab = (float(n["guess_lab_l"]), float(n["guess_lab_a"]), float(n["guess_lab_b"]))
        prev_hsv = (p.get("guess_hsv_h"), p.get("guess_hsv_s"), p.get("guess_hsv_v"))
        next_hsv = (n.get("guess_hsv_h"), n.get("guess_hsv_s"), n.get("guess_hsv_v"))
        if any(v is None or (isinstance(v, float) and pd.isna(v)) for v in prev_hsv + next_hsv):
            prev_hsv = next_hsv = None
        else:
            prev_hsv = tuple(float(x) for x in prev_hsv)  # type: ignore
            next_hsv = tuple(float(x) for x in next_hsv)  # type: ignore
        sat = _step_constraint_satisfaction(constraints, prev_lab, next_lab, prev_hsv, next_hsv)
        if sat is not None:
            step_sats.append(sat)

    mean_csat = sum(step_sats) / len(step_sats) if step_sats else None
    mean_constraints_issued = (
        sum(constraints_per_step) / len(constraints_per_step)
        if constraints_per_step
        else None
    )

    turn_info = compute_turn_accounting(
        traj_sub, fb_sub, max_turns_configured, convergence_delta_e
    )

    parse_failures = int((~traj_sub["parse_ok"].astype(bool)).sum())
    status = "max_turns"
    if parse_failures > 0 and len(valid) == 0:
        status = "parse_failed_turn0"
    elif turn_info["converged"]:
        status = "converged"

    first = traj_sub.iloc[0]
    return {
        "run_id": first.get("run_id"),
        "example_id": first.get("example_id"),
        "raw_name": first.get("raw_name"),
        "true_hex": first.get("true_hex"),
        "model_alias": first.get("model_alias"),
        "guesser_model_name": first.get("guesser_model_name"),
        "guesser_provider": first.get("guesser_provider"),
        "teacher_type": first.get("teacher_type"),
        "teacher_model_name": first.get("teacher_model_name"),
        "teacher_provider": first.get("teacher_provider"),
        "output_space": first.get("output_space", "hex"),
        "evaluation_space": first.get("evaluation_space", "lab"),
        "max_turns": max_turns_configured,
        "num_valid_turns": len(valid),
        "num_feedback_messages": len(fb_sub),
        "status": status,
        "initial_error_lab": initial_error,
        "final_error_lab": final_error,
        "absolute_improvement": abs_imp,
        "relative_improvement": rel_imp,
        "best_error_lab": best_error,
        "best_turn": best_turn,
        "trajectory_path_length": path_len,
        "trajectory_efficiency": traj_eff,
        "mean_directional_alignment": mean_align,
        "mean_constraint_satisfaction": mean_csat,
        "mean_constraints_issued": mean_constraints_issued,
        "parse_failure_count": parse_failures,
        "regime_label": first.get("regime_label"),
        "abstraction_score": first.get("abstraction_score"),
        "explicitness_score": first.get("explicitness_score"),
        "prototype_score": first.get("prototype_score"),
        "rarity_score": first.get("rarity_score"),
        "hue_bin": first.get("hue_bin"),
        "lightness_bin": first.get("lightness_bin"),
        "saturation_bin": first.get("saturation_bin"),
        "value_bin": first.get("value_bin"),
        **turn_info,
    }
