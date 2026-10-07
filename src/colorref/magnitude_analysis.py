"""Exploratory CPU audits of frozen magnitude outputs; never fit on evaluation."""

from __future__ import annotations

import math
from collections import Counter
from statistics import mean, median

import numpy as np

from colorref.magnitude_control import ARMS
from colorref.magnitude_reports import average, cluster_effect, fmt
from colorref.quantifiers import DIRECTION_SPECS

PAIR_TOLERANCE = 0.01
NUMERIC_TOLERANCE = 0.01


def distribution(values):
    return {
        "n": len(values),
        "mean": mean(values) if values else None,
        "median": median(values) if values else None,
        "p95": float(np.quantile(values, 0.95)) if values else None,
        "max": max(values) if values else None,
    }


def parsed(task, rows):
    row = rows.get(task["condition_id"])
    return task["status"] == "generate" and row is not None and row["parse_ok"]


def summarize(cases, rows, cfg):
    """Statistics use common parsed triplets; completion retains every planned case."""
    common = [g for g in cases if all(parsed(g[a], rows) for a in ARMS)]
    starts = [g["bare"]["base_id"] for g in common]
    deltas = [
        rows[g["calibrated"]["condition_id"]]["metrics"]["projected_target_error"]
        - rows[g["bare"]["condition_id"]]["metrics"]["projected_target_error"]
        for g in common
    ]
    arms = {}
    for arm in ARMS:
        planned = [g[arm] for g in cases]
        observed = [
            rows[t["condition_id"]] for t in planned if t["condition_id"] in rows
        ]
        matched = [rows[g[arm]["condition_id"]] for g in common]
        arms[arm] = {
            "planned": len(planned),
            "generated": len(observed),
            "parsed": sum(r["parse_ok"] for r in observed),
            "pending": sum(
                t["status"] == "generate" and t["condition_id"] not in rows
                for t in planned
            ),
            "assigned_stops": sum(
                t["status"] == "assigned_threshold_stop" for t in planned
            ),
            "unavailable_mapping": sum(
                t["status"] == "unavailable_calibration" for t in planned
            ),
            **{
                key: average(matched, lambda r, k=key: r["metrics"].get(k))
                for key in (
                    "projected_target_error",
                    "native_target_error",
                    "gain",
                    "displayed_requested_signed_step",
                    "native_requested_signed_step",
                    "displayed_off_axis_drift",
                    "alignment",
                    "movement_distance_ratio",
                )
            },
            "projection_delta_e": average(matched, lambda r: r["projection_delta_e"]),
            "converged": sum(r["metrics"]["converged"] for r in matched),
            "worsened": sum(r["metrics"]["gain"] < -PAIR_TOLERANCE for r in matched),
            "no_gain_within_tolerance": sum(
                abs(r["metrics"]["gain"]) <= PAIR_TOLERANCE for r in matched
            ),
            "beyond_improvement_bound": sum(
                r["metrics"]["improvement_step_bound"] is not None
                and r["metrics"]["displayed_movement_norm"]
                > r["metrics"]["improvement_step_bound"] + 1e-9
                for r in matched
            ),
            "mean_signed_projection_step_change": average(
                matched,
                lambda r: (
                    r["metrics"]["displayed_requested_signed_step"]
                    - r["metrics"]["native_requested_signed_step"]
                ),
            ),
        }
    calibrated = [rows[g["calibrated"]["condition_id"]] for g in common]
    predicted_gap = [
        abs(r["calibrated_median"] - r["axis_residual"]) for r in calibrated
    ]
    transfer_mismatch = [
        abs(r["metrics"]["displayed_requested_signed_step"] - r["calibrated_median"])
        for r in calibrated
    ]
    return {
        "planned_cases": len(cases),
        "common_cases": len(common),
        "common_starting_colors": len(set(starts)),
        "mean_starting_error": mean(g["bare"]["starting_error_delta_e"] for g in common)
        if common
        else None,
        "arms": arms,
        "calibrated_minus_bare": cluster_effect(
            deltas, starts, cfg["analysis"]["resamples"], cfg["analysis"]["seed"]
        ),
        "median_paired_error_delta": median(deltas) if deltas else None,
        "wins": sum(x < -PAIR_TOLERANCE for x in deltas),
        "ties": sum(abs(x) <= PAIR_TOLERANCE for x in deltas),
        "losses": sum(x > PAIR_TOLERANCE for x in deltas),
        "calibrated_selected_wordings": dict(
            Counter(r["selected_wording"] for r in calibrated)
        ),
        "calibrated_median_target_gap": distribution(predicted_gap),
        "calibrated_step_transfer_mismatch": distribution(transfer_mismatch),
    }


def numeric_audit(tasks, rows):
    planned = [t for t in tasks if t["arm"] == "numeric"]
    observed = [rows[t["condition_id"]] for t in planned if t["condition_id"] in rows]
    good = [r for r in observed if r["parse_ok"]]
    errors = [r["metrics"]["numeric_native_execution_error"] for r in good]
    misses = []
    for row in good:
        error = row["metrics"]["numeric_native_execution_error"]
        if error <= NUMERIC_TOLERANCE:
            continue
        d = DIRECTION_SPECS[row["direction"]]
        residual = [
            a - e for a, e in zip(row["native_lab"], row["expected_numeric_lab"])
        ]
        misses.append(
            {
                "condition_id": row["condition_id"],
                "base_id": row["base_id"],
                "direction": row["direction"],
                "requested_distance": row["requested_distance"],
                "prompted_start_lab": [round(x, 6) for x in row["start"]["lab"]],
                "expected_lab": row["expected_numeric_lab"],
                "actual_lab": row["native_lab"],
                "coordinate_residual": residual,
                "requested_axis_residual": residual[d.index],
                "other_coordinate_residual_norm": math.sqrt(
                    sum(x * x for i, x in enumerate(residual) if i != d.index)
                ),
                "native_execution_error": error,
                "projected_execution_error": row["metrics"][
                    "numeric_display_execution_error"
                ],
                "hidden_target_error": row["metrics"]["projected_target_error"],
                "projection_delta_e": row["projection_delta_e"],
                "prompt": row["prompt"],
                "raw_response": row["raw_response"],
                "generation": row.get("generation"),
            }
        )
    misses.sort(key=lambda r: (-r["native_execution_error"], r["condition_id"]))
    return {
        "planned": len(planned),
        "generated": len(observed),
        "parsed": len(good),
        "parse_failures": len(observed) - len(good),
        "exact_within_0_01": sum(x <= NUMERIC_TOLERANCE for x in errors),
        "within_1": sum(x <= 1 for x in errors),
        "over_1": sum(x > 1 for x in errors),
        "native_error_distribution": distribution(errors),
        "displayed_execution_error_distribution": distribution(
            [r["metrics"]["numeric_display_execution_error"] for r in good]
        ),
        "total_native_error": sum(errors),
        "largest_error_share_of_total": max(errors) / sum(errors)
        if errors and sum(errors) > 0
        else None,
        "misses": misses,
    }


def analyze(cfg, plan, bundle, rows):
    tasks = bundle["evaluation_tasks"] if bundle else []
    grouped = {}
    for task in tasks:
        grouped.setdefault(task["case_id"], {})[task["arm"]] = task
    groups = list(grouped.values())
    result = {
        "analysis_kind": "exploratory_saved_output_breakdown",
        "pair_tie_tolerance_delta_e": PAIR_TOLERANCE,
        "numeric_exact_tolerance_delta_e": NUMERIC_TOLERANCE,
        "global": summarize(groups, rows, cfg),
        "by_direction": [],
        "by_distance": [],
        "by_direction_distance": [],
        "by_start": [],
        "leave_one_start_out": [],
        "available_pair": None,
        "numeric": numeric_audit(tasks, rows),
    }
    for direction in DIRECTION_SPECS:
        selected = [g for g in groups if g["bare"]["direction"] == direction]
        result["by_direction"].append(
            {"direction": direction, **summarize(selected, rows, cfg)}
        )
    for distance in cfg["study"]["target_steps"]:
        selected = [g for g in groups if g["bare"]["requested_distance"] == distance]
        result["by_distance"].append(
            {"requested_distance": distance, **summarize(selected, rows, cfg)}
        )
    for direction in DIRECTION_SPECS:
        for distance in cfg["study"]["target_steps"]:
            selected = [
                g
                for g in groups
                if g["bare"]["direction"] == direction
                and g["bare"]["requested_distance"] == distance
            ]
            result["by_direction_distance"].append(
                {
                    "direction": direction,
                    "requested_distance": distance,
                    **summarize(selected, rows, cfg),
                }
            )
    for base in plan["splits"]["evaluation"]:
        key = base["base_id"]
        selected = [g for g in groups if g["bare"]["base_id"] == key]
        result["by_start"].append(
            {
                "base_id": key,
                "hex": base["state"]["hex"],
                **summarize(selected, rows, cfg),
            }
        )
    common = [g for g in groups if all(parsed(g[a], rows) for a in ARMS)]
    keys = sorted({g["bare"]["base_id"] for g in common})
    for key in keys:
        remaining = [g for g in common if g["bare"]["base_id"] != key]
        deltas = [
            rows[g["calibrated"]["condition_id"]]["metrics"]["projected_target_error"]
            - rows[g["bare"]["condition_id"]]["metrics"]["projected_target_error"]
            for g in remaining
        ]
        result["leave_one_start_out"].append(
            {
                "omitted_base_id": key,
                "remaining_cases": len(remaining),
                "mean_error_delta": mean(deltas) if deltas else None,
            }
        )
    available = [
        g for g in groups if all(parsed(g[a], rows) for a in ("bare", "calibrated"))
    ]
    differences = [
        rows[g["calibrated"]["condition_id"]]["metrics"]["projected_target_error"]
        - rows[g["bare"]["condition_id"]]["metrics"]["projected_target_error"]
        for g in available
    ]
    result["available_pair"] = cluster_effect(
        differences,
        [g["bare"]["base_id"] for g in available],
        cfg["analysis"]["resamples"],
        cfg["analysis"]["seed"],
    )
    return result


def effect_text(effect):
    value = fmt(effect["mean"])
    return value + (
        f" [{fmt(effect['low'])}, {fmt(effect['high'])}]"
        if effect["low"] is not None
        else ""
    )


def report(result, run_id):
    overall, numeric = result["global"], result["numeric"]
    lines = [
        f"# Magnitude pilot CPU audit: {run_id}",
        "",
        "Exploratory diagnostics of saved outputs; no new model responses or controller fitting.",
        "",
        f"- Common parsed triplets: {overall['common_cases']} / {overall['planned_cases']}; starting colors: {overall['common_starting_colors']}.",
        f"- Calibrated minus bare ΔE: {effect_text(overall['calibrated_minus_bare'])}.",
        f"- Median paired ΔE: {fmt(overall['median_paired_error_delta'])}.",
        f"- Calibrated wins / ties / losses: {overall['wins']} / {overall['ties']} / {overall['losses']} (0.01 ΔE tie tolerance).",
        f"- Available bare/calibrated pairs: {result['available_pair']['cases']}; {effect_text(result['available_pair'])}.",
        "",
        "## Common-cohort movement and target accuracy",
        "",
        "| Arm | Target ΔE | Converged N | Worsened N | Beyond improvement bound N | Native step | Displayed step | Projection ΔE | Off-axis drift |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, r in overall["arms"].items():
        lines.append(
            f"| {arm} | {fmt(r['projected_target_error'])} | {r['converged']} | {r['worsened']} | {r['beyond_improvement_bound']} | {fmt(r['native_requested_signed_step'])} | {fmt(r['displayed_requested_signed_step'])} | {fmt(r['projection_delta_e'])} | {fmt(r['displayed_off_axis_drift'])} |"
        )
    for heading, rows in (
        ("Requested distance", result["by_distance"]),
        ("Requested direction", result["by_direction"]),
        ("Direction and distance", result["by_direction_distance"]),
    ):
        lines += [
            "",
            f"## {heading}",
            "",
            "Negative paired differences favor calibrated wording. Bins may share starts; intervals are exploratory and not multiplicity-adjusted.",
            "",
            "| Direction / units | Common / planned | Starts | Bare ΔE | Calibrated ΔE | Numeric ΔE | Calibrated − bare [95% interval] | Wins / ties / losses | Median-target gap | Step-transfer mismatch |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in rows:
            label = " / ".join(
                str(r[k]) for k in ("direction", "requested_distance") if k in r
            )
            lines.append(
                f"| {label} | {r['common_cases']} / {r['planned_cases']} | {r['common_starting_colors']} | {fmt(r['arms']['bare']['projected_target_error'])} | {fmt(r['arms']['calibrated']['projected_target_error'])} | {fmt(r['arms']['numeric']['projected_target_error'])} | {effect_text(r['calibrated_minus_bare'])} | {r['wins']} / {r['ties']} / {r['losses']} | {fmt(r['calibrated_median_target_gap']['mean'])} | {fmt(r['calibrated_step_transfer_mismatch']['mean'])} |"
            )
    lines += [
        "",
        "Median-target gap is |selected calibration median − target-axis residual|.",
        "Step-transfer mismatch is |actual displayed step − selected calibration median|.",
        "These describe phrase resolution and transfer variability; they are not additive or causal components of target error.",
        "",
        "## Per-start means and leave-one-start-out sensitivity",
        "",
        "| Start | HEX | Common / planned | Bare ΔE | Calibrated ΔE | Δ error | Δ after omitting this start |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    omitted = {
        r["omitted_base_id"]: r["mean_error_delta"]
        for r in result["leave_one_start_out"]
    }
    for r in result["by_start"]:
        lines.append(
            f"| {r['base_id']} | {r['hex']} | {r['common_cases']} / {r['planned_cases']} | {fmt(r['arms']['bare']['projected_target_error'])} | {fmt(r['arms']['calibrated']['projected_target_error'])} | {fmt(r['calibrated_minus_bare']['mean'])} | {fmt(omitted.get(r['base_id']))} |"
        )
    lines += [
        "",
        "## Numeric execution error distribution",
        "",
        f"- Generated / planned: {numeric['generated']} / {numeric['planned']}; parsed: {numeric['parsed']}; parse failures: {numeric['parse_failures']}.",
        f"- Native error ≤ 0.01: {numeric['exact_within_0_01']}; ≤ 1: {numeric['within_1']}; > 1: {numeric['over_1']}.",
        f"- Native error mean / median / p95 / max: {' / '.join(fmt(numeric['native_error_distribution'][k]) for k in ('mean', 'median', 'p95', 'max'))}.",
        f"- Largest miss share of summed native errors: {fmt(numeric['largest_error_share_of_total'])}.",
        "",
        "### Largest native execution misses (up to ten)",
        "",
        "| Condition | Expected LAB | Actual LAB | Native error | Other-coordinate residual | Projection ΔE | Finish / tokens |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for r in numeric["misses"][:10]:
        gen = r["generation"] or {}
        lines.append(
            f"| {r['condition_id']} | {r['expected_lab']} | {r['actual_lab']} | {fmt(r['native_execution_error'])} | {fmt(r['other_coordinate_residual_norm'])} | {fmt(r['projection_delta_e'])} | {gen.get('finish_reason')} / {gen.get('generated_tokens')} |"
        )
    if not numeric["misses"]:
        lines.append("| None observed | | | | | | |")
    lines += [
        "",
        "## Interpretation",
        "",
        "All movement/error tables use common generated parsed triplets. Completion counts, available-pair sensitivity and unparsed/missing cases remain in the JSON. Zero-call stops are counted separately from generated responses. Cluster draws resample entire starting colors with their observed paired cases and retain pooled case weights; per-start means have no within-start bootstrap interval. Leave-one-start-out values are descriptive leverage checks, not new confidence intervals or reasons to drop colors. The improvement bound is 2 d cos(theta) for displayed movement magnitude; crossing it diagnoses harmful overshoot in Euclidean LAB, independent of sign compliance. Boundary projection and native requested steps are reported separately; these observations do not establish an internal reasoning mechanism or a perceptual-uniformity explanation. Numeric errors measure exact instructed coordinates separately from displayed targets; misses remain in performance estimates. All intervals and tie thresholds in this added audit are exploratory. No held-out responses refit medians, replace cases or alter prompts. The 12 evaluation starts are the sampling clusters; multiple directions/distances are not independent colors. Full miss prompts/responses and subgroup diagnostics are in metrics/magnitude_breakdown.json. Primary magnitude_summary.md and its original metrics remain unchanged.",
    ]
    return "\n".join(lines) + "\n"
