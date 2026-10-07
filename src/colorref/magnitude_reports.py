"""Calibration diagnostics and paired held-out, starting-color cluster analysis."""

from __future__ import annotations

from collections import Counter
from statistics import mean

import numpy as np

from colorref.magnitude_control import ARMS, WORDINGS
from colorref.quantifiers import DIRECTION_SPECS


def cluster_effect(values, clusters, resamples=5000, seed=13):
    """Pooled case-weighted mean; resample entire starts, preserving paired cases."""
    if len(values) != len(clusters) or resamples < 100 or not all(np.isfinite(values)):
        raise ValueError("Require finite paired values and at least 100 resamples")
    keys = sorted(set(clusters))
    result = {
        "cases": len(values),
        "starting_colors": len(keys),
        "mean": mean(values) if values else None,
        "low": None,
        "high": None,
    }
    if len(keys) < 2:
        return result
    sums = np.array([sum(v for v, c in zip(values, clusters) if c == k) for k in keys])
    counts = np.array([clusters.count(k) for k in keys])
    draws = np.random.default_rng(seed).integers(
        0, len(keys), size=(resamples, len(keys))
    )
    estimates = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    result["low"], result["high"] = map(float, np.quantile(estimates, [0.025, 0.975]))
    return result


def average(rows, accessor):
    values = [accessor(r) for r in rows]
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def analyze(cfg, plan, calibration, mapping, tasks, evaluation):
    result = {
        "calibration_completed": len(calibration),
        "calibration_planned": len(plan["calibration_tasks"]),
        "calibration_parsed": sum(r["parse_ok"] for r in calibration.values()),
        "calibration": [],
        "mapping": mapping,
        "evaluation": [],
        "effects": [],
        "failures": [],
        "evaluation_cases": len(plan["evaluation_cases"]),
        "exclusions": len(plan["feasibility_exclusions"]),
    }
    for direction in DIRECTION_SPECS:
        for wording in WORDINGS:
            planned = [
                t
                for t in plan["calibration_tasks"]
                if t["direction"] == direction and t["wording"] == wording
            ]
            rows = [
                calibration[t["condition_id"]]
                for t in planned
                if t["condition_id"] in calibration
            ]
            parsed = [r for r in rows if r["parse_ok"]]
            result["calibration"].append(
                {
                    "direction": direction,
                    "wording": wording,
                    "planned": len(planned),
                    "completed": len(rows),
                    "parsed": len(parsed),
                    "displayed_mean_step": average(
                        parsed,
                        lambda r: r["metrics"]["displayed_requested_signed_step"],
                    ),
                    "off_axis_drift": average(
                        parsed, lambda r: r["metrics"]["displayed_off_axis_drift"]
                    ),
                    "direction_follow_rate": average(
                        parsed, lambda r: r["metrics"]["displayed_direction_followed"]
                    ),
                    "projection_delta_e": average(
                        parsed, lambda r: r["projection_delta_e"]
                    ),
                    "projection_over_1": sum(
                        r["projection_delta_e"] > 1 for r in parsed
                    ),
                }
            )
    # Only generated parsed records enter movement/accuracy. Assigned threshold
    # stops and unavailable phrases remain separately visible in counts.
    grouped = {}
    for t in tasks:
        grouped.setdefault(t["case_id"], {})[t["arm"]] = t
    for arm in ARMS:
        planned = [t for t in tasks if t["arm"] == arm]
        rows = [
            evaluation[t["condition_id"]]
            for t in planned
            if t["condition_id"] in evaluation
        ]
        parsed = [r for r in rows if r["parse_ok"]]
        result["evaluation"].append(
            {
                "arm": arm,
                "planned": len(planned),
                "assigned_threshold_stops": sum(
                    t["status"] == "assigned_threshold_stop" for t in planned
                ),
                "unavailable_calibration": sum(
                    t["status"] == "unavailable_calibration" for t in planned
                ),
                "generated": len(rows),
                "parsed": len(parsed),
                "parse_failures": len(rows) - len(parsed),
                "pending": sum(
                    t["status"] == "generate" and t["condition_id"] not in evaluation
                    for t in planned
                ),
                "selected_wordings": dict(
                    Counter(
                        t["selected_wording"] for t in planned if t["selected_wording"]
                    )
                ),
                **{
                    key: average(parsed, lambda r, k=key: r["metrics"].get(k))
                    for key in (
                        "projected_target_error",
                        "gain",
                        "displayed_requested_signed_step",
                        "displayed_off_axis_drift",
                        "displayed_direction_followed",
                        "alignment",
                        "movement_distance_ratio",
                        "converged",
                        "numeric_native_execution_error",
                        "numeric_display_execution_error",
                        "numeric_expected_target_disagreement",
                    )
                },
                "projection_delta_e": average(
                    parsed, lambda r: r["projection_delta_e"]
                ),
                "projection_over_1": sum(r["projection_delta_e"] > 1 for r in parsed),
                "mean_prompt_tokens": average(rows, lambda r: r.get("prompt_tokens")),
                "mean_generated_tokens": average(
                    rows, lambda r: r.get("generation", {}).get("generated_tokens")
                ),
            }
        )

    def usable(t):
        row = evaluation.get(t["condition_id"])
        return t["status"] == "generate" and row is not None and row["parse_ok"]

    common = [g for g in grouped.values() if all(usable(g[a]) for a in ARMS)]
    for cohort in ("common_triplets", "available_pairs"):
        for left, right in (("bare", "calibrated"), ("bare", "numeric")):
            cases = (
                common
                if cohort == "common_triplets"
                else [
                    g for g in grouped.values() if usable(g[left]) and usable(g[right])
                ]
            )
            values = [
                evaluation[g[right]["condition_id"]]["metrics"][
                    "projected_target_error"
                ]
                - evaluation[g[left]["condition_id"]]["metrics"][
                    "projected_target_error"
                ]
                for g in cases
            ]
            result["effects"].append(
                {
                    "cohort": cohort,
                    "left": left,
                    "right": right,
                    **cluster_effect(
                        values,
                        [g[left]["base_id"] for g in cases],
                        cfg["analysis"]["resamples"],
                        cfg["analysis"]["seed"],
                    ),
                }
            )
    result["common_triplets"] = len(common)
    result["common_accuracy"] = {
        arm: average(
            [evaluation[g[arm]["condition_id"]] for g in common],
            lambda r: r["metrics"]["projected_target_error"],
        )
        for arm in ARMS
    }
    for row in [*calibration.values(), *evaluation.values()]:
        if not row["parse_ok"]:
            result["failures"].append(
                {
                    "condition_id": row["condition_id"],
                    "phase": row["phase"],
                    "reason": row["parse_reason"],
                    "prompt": row["prompt"],
                    "response": row["raw_response"],
                    "generation": row.get("generation"),
                }
            )
    result["coverage"] = [
        {
            "direction": d,
            "distance": s,
            "planned_starts": cfg["study"]["evaluation_colors"],
            "included": sum(
                c["direction"] == d and c["requested_distance"] == s
                for c in plan["evaluation_cases"]
            ),
            "excluded": dict(
                Counter(
                    c["reason"]
                    for c in plan["feasibility_exclusions"]
                    if c["direction"] == d and c["requested_distance"] == s
                )
            ),
        }
        for d in DIRECTION_SPECS
        for s in cfg["study"]["target_steps"]
    ]
    return result


def fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def report(result, run_id):
    lines = [
        f"# Held-out magnitude control: {run_id}",
        "",
        f"- Calibration completed: {result['calibration_completed']} / {result['calibration_planned']}; parsed: {result['calibration_parsed']}",
        f"- Frozen held-out cases: {result['evaluation_cases']}; feasibility exclusions: {result['exclusions']}",
        f"- Common generated parsed triplets: {result['common_triplets']}",
        "- Displayed uint8 sRGB target error is primary; one fresh-context revision.",
        "",
        "## Calibration progress and diagnostics",
        "",
        "| Direction | Wording | Completed / planned | Parsed | Mean displayed step | Follow rate | Off-axis drift | Projection ΔE | Projection > 1 N |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["calibration"]:
        lines.append(
            f"| {r['direction']} | {r['wording']} | {r['completed']} / {r['planned']} | {r['parsed']} | {fmt(r['displayed_mean_step'])} | {fmt(r['direction_follow_rate'])} | {fmt(r['off_axis_drift'])} | {fmt(r['projection_delta_e'])} | {r['projection_over_1']} |"
        )
    lines += ["", "## Fitted displayed-state medians", ""]
    if result["mapping"] is None:
        lines += [
            "Mapping unavailable until every calibration response is saved; evaluation has not started."
        ]
    else:
        lines += [
            "| Direction | Wording | Parsed / planned | Nonpositive N | Median displayed step | Median native step | Usable graded phrase |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for direction, rows in result["mapping"]["table"].items():
            for r in rows:
                lines.append(
                    f"| {direction} | {r['wording']} | {r['parsed']} / {r['planned']} | {r['nonpositive']} | {fmt(r['displayed_median_step'])} | {fmt(r['native_median_step'])} | {r['usable']} |"
                )
    lines += [
        "",
        "## Held-out completion",
        "",
        "| Arm | Planned | Zero-call stops | Unavailable mapping | Generated | Parsed | Failed | Pending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["evaluation"]:
        lines.append(
            f"| {r['arm']} | {r['planned']} | {r['assigned_threshold_stops']} | {r['unavailable_calibration']} | {r['generated']} | {r['parsed']} | {r['parse_failures']} | {r['pending']} |"
        )
    lines += [
        "",
        "## Target accuracy on common generated parsed triplets",
        "",
        "| Arm | N | Mean displayed target ΔE |",
        "|---|---:|---:|",
    ]
    for arm in ARMS:
        lines.append(
            f"| {arm} | {result['common_triplets']} | {fmt(result['common_accuracy'][arm])} |"
        )
    lines += [
        "",
        "## Paired error effects (right minus left)",
        "",
        "Intervals resample whole starting colors, retaining all their observed paired cases.",
        "",
        "| Cohort | Comparison | Cases | Starts | Mean Δ error [95% interval] |",
        "|---|---|---:|---:|---:|",
    ]
    for r in result["effects"]:
        interval = (
            f" [{fmt(r['low'])}, {fmt(r['high'])}]" if r["low"] is not None else ""
        )
        lines.append(
            f"| {r['cohort']} | {r['left']} → {r['right']} | {r['cases']} | {r['starting_colors']} | {fmt(r['mean'])}{interval} |"
        )
    lines += [
        "",
        "## Generated-response diagnostics (all parsed, cohorts may differ)",
        "",
        "| Arm | Parsed | Mean gain | Follow rate | Off-axis drift | Projection ΔE | Projection > 1 N | Prompt tokens | Output tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["evaluation"]:
        lines.append(
            f"| {r['arm']} | {r['parsed']} | {fmt(r['gain'])} | {fmt(r['displayed_direction_followed'])} | {fmt(r['displayed_off_axis_drift'])} | {fmt(r['projection_delta_e'])} | {r['projection_over_1']} | {fmt(r['mean_prompt_tokens'])} | {fmt(r['mean_generated_tokens'])} |"
        )
    numeric = next(r for r in result["evaluation"] if r["arm"] == "numeric")
    lines += [
        "",
        "## Numeric execution control",
        "",
        f"- Mean native error against exact instructed coordinates: {fmt(numeric['numeric_native_execution_error'])}.",
        f"- Mean displayed error against the projected instructed result: {fmt(numeric['numeric_display_execution_error'])}.",
        f"- Mean instructed-result disagreement with hidden displayed target: {fmt(numeric['numeric_expected_target_disagreement'])}.",
    ]
    lines += [
        "",
        "## Feasibility coverage (frozen before inference)",
        "",
        "| Direction | Requested units | Included / planned starts | Exclusion reasons |",
        "|---|---:|---:|---|",
    ]
    for r in result["coverage"]:
        lines.append(
            f"| {r['direction']} | {r['distance']} | {r['included']} / {r['planned_starts']} | {r['excluded']} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "Calibration medians include wrong-direction and zero updates among parsed responses; failed parsing remains in counts. Only positive graded medians are candidates, and bare wording is unranked. Evaluation colors never fit the mapping. Output projection error never filters generated responses. This is one model, one prompt, a small fixed RGB-range pilot, not downstream creative editing or a human perceptual magnitude calibration. Exact numeric feedback includes greater precision and explicit coordinate holds, so it is an execution control rather than an information-matched wording arm. Six-decimal prompted coordinates, native target candidates and displayed targets are retained separately. Cluster intervals use a case-weighted pooled mean, condition on observed parsed pairs, and do not remove failure-selection bias or establish population generalization. Missing mappings, failed responses and pending work are not imputed. HSV saturation and multi-turn transfer require separate studies. Detailed movement, numeric execution, token, failure and projection diagnostics are in metrics/magnitude_analysis.json; prompts and raw responses are in per-response checkpoints.",
    ]
    return "\n".join(lines) + "\n"
