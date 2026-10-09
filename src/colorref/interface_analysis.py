"""Paired trajectory analysis using saved observations only (no inference)."""

from __future__ import annotations

import json
import re
from statistics import mean

import numpy as np
from colorref.colors import color_distance_lab
from colorref.interface_study import REGIMES, VARIANTS, is_complete

COMPARISONS = (
    ("hex", "lab_plain"),
    ("lab_plain", "lab_axis_legend"),
    ("hex", "lab_axis_legend"),
)


def paired_bootstrap(matrix, regimes, resamples=5000, seed=13):
    """Resample whole examples within regimes, retaining every paired column."""
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or len(values) != len(regimes) or not np.isfinite(values).all():
        raise ValueError(
            "Require a finite examples-by-metrics matrix and matching regimes"
        )
    if resamples < 100:
        raise ValueError("At least 100 bootstrap resamples are required")
    if any(regime not in REGIMES for regime in regimes):
        raise ValueError("Unknown semantic regime")
    n, width = values.shape
    if n == 0:
        return [{"n": 0, "mean": None, "low": None, "high": None} for _ in range(width)]
    point = values.mean(axis=0)
    if n == 1:
        return [{"n": 1, "mean": float(x), "low": None, "high": None} for x in point]
    rng = np.random.default_rng(seed)
    draws = np.zeros((resamples, width))
    for regime in REGIMES:
        indices = [i for i, value in enumerate(regimes) if value == regime]
        if not indices:
            continue
        selected = rng.choice(indices, size=(resamples, len(indices)), replace=True)
        draws += values[selected].sum(axis=1)
    draws /= n
    limits = np.quantile(draws, [0.025, 0.975], axis=0)
    return [
        {
            "n": n,
            "mean": float(point[i]),
            "low": float(limits[0, i]),
            "high": float(limits[1, i]),
        }
        for i in range(width)
    ]


def _full(records, turns):
    return len(records) == turns + 1 and all(row["parse_ok"] for row in records)


def _outcomes(records):
    errors = [row["projected_error_delta_e"] for row in records]
    return np.array(
        [errors[0], errors[-1], errors[0] - errors[-1], errors[-1] - min(errors)]
    )


def analyze(cfg, tasks, checkpoints, resamples=5000, seed=13):
    turns = cfg["execution"]["max_turns"]
    grouped = {}
    failures = []
    for task in tasks:
        records = checkpoints.get(task["slot"], [])
        grouped.setdefault(task["example"]["example_id"], {})[task["variant"]] = (
            task,
            records,
        )
        for row in records:
            if not row["parse_ok"]:
                failures.append(
                    {
                        "condition_id": task["condition_id"],
                        "description": task["example"]["raw_name"],
                        "variant": task["variant"],
                        "turn": row["turn"],
                        "parse_reason": row["parse_reason"],
                        "raw_response": row["raw_response"],
                        "prompt": row["prompt"],
                        "arithmetic_text": bool(
                            re.search(r"\d(?:\.\d+)?\s*[+-]\s*\d", row["raw_response"])
                        ),
                    }
                )
    common = [
        identifier
        for identifier in sorted(grouped)
        if all(_full(grouped[identifier][v][1], turns) for v in VARIANTS)
    ]
    regimes = [grouped[i]["hex"][0]["example"]["regime_label"] for i in common]
    columns = [(variant, turn) for variant in VARIANTS for turn in range(turns + 1)]
    matrix = np.array(
        [
            [grouped[i][v][1][t]["projected_error_delta_e"] for v, t in columns]
            for i in common
        ],
        dtype=float,
    ).reshape(len(common), len(columns))
    estimates = paired_bootstrap(matrix, regimes, resamples, seed)
    curves = [
        {
            "variant": v,
            "turn": t,
            "projected_error": estimate,
            "native_error": mean(
                grouped[i][v][1][t]["native_error_delta_e"] for i in common
            )
            if common
            else None,
        }
        for (v, t), estimate in zip(columns, estimates)
    ]
    paired = []
    for cohort in ("common_triplets", "available_pairs"):
        for left, right in COMPARISONS:
            identifiers = (
                common
                if cohort == "common_triplets"
                else [
                    i
                    for i in sorted(grouped)
                    if _full(grouped[i][left][1], turns)
                    and _full(grouped[i][right][1], turns)
                ]
            )
            strata = [
                grouped[i][left][0]["example"]["regime_label"] for i in identifiers
            ]
            differences = np.array(
                [
                    _outcomes(grouped[i][right][1]) - _outcomes(grouped[i][left][1])
                    for i in identifiers
                ],
                dtype=float,
            ).reshape(len(identifiers), 4)
            intervals = paired_bootstrap(differences, strata, resamples, seed)
            paired.append(
                {
                    "cohort": cohort,
                    "left": left,
                    "right": right,
                    "n": len(identifiers),
                    "regime_counts": {r: strata.count(r) for r in REGIMES},
                    "metrics": dict(
                        zip(
                            ("initial_error", "final_error", "gain", "final_best_gap"),
                            intervals,
                        )
                    ),
                }
            )
    controls = []
    overshoots = []
    threshold = cfg["execution"]["convergence_delta_e"]
    for variant in VARIANTS:
        initial_close = lost_close = improved = worsened = final_best = stationary = 0
        gaps = []
        best_turns = [0] * (turns + 1)
        for identifier in common:
            task, records = grouped[identifier][variant]
            errors = [row["projected_error_delta_e"] for row in records]
            best = min(range(len(errors)), key=errors.__getitem__)
            best_turns[best] += 1
            close = errors[0] <= threshold
            initial_close += close
            lost_close += close and errors[-1] > threshold
            improved += errors[-1] < errors[0] - 1e-8
            worsened += errors[-1] > errors[0] + 1e-8
            gap = errors[-1] - errors[best]
            gaps.append(gap)
            final_best += gap <= 1e-8
            stationary += sum(
                color_distance_lab(
                    a["displayed_state"]["lab"], b["displayed_state"]["lab"]
                )
                <= 1e-8
                for a, b in zip(records, records[1:])
            )
            if gap > 1e-8:
                overshoots.append(
                    {
                        "condition_id": task["condition_id"],
                        "description": task["example"]["raw_name"],
                        "variant": variant,
                        "regime_label": task["example"]["regime_label"],
                        "errors_by_turn": errors,
                        "first_best_turn": best,
                        "final_best_gap": gap,
                    }
                )
        controls.append(
            {
                "variant": variant,
                "n": len(common),
                "initially_converged_n": initial_close,
                "initially_converged_then_lost_n": lost_close,
                "improved_n": improved,
                "worsened_n": worsened,
                "final_is_best_n": final_best,
                "mean_final_best_gap": mean(gaps) if gaps else None,
                "zero_movement_revisions_n": stationary,
                "revision_opportunities": len(common) * turns,
                "first_best_turn_counts": best_turns,
            }
        )
    return {
        "bootstrap": {
            "resamples": resamples,
            "seed": seed,
            "method": "paired, stratified percentile bootstrap",
            "interval": 0.95,
        },
        "planned_games": len(tasks),
        "completed_games": sum(
            is_complete(checkpoints.get(t["slot"], []), turns) for t in tasks
        ),
        "planned_examples": len(grouped),
        "common_examples": len(common),
        "common_example_ids": common,
        "common_regime_counts": {r: regimes.count(r) for r in REGIMES},
        "curves": curves,
        "paired_effects": paired,
        "control_diagnostics": controls,
        "largest_overshoots": sorted(
            overshoots, key=lambda x: (-x["final_best_gap"], x["condition_id"])
        )[:10],
        "parse_failures": failures,
    }


def _number(value):
    return "n/a" if value is None else f"{value:.3f}"


def _interval(estimate):
    point = _number(estimate["mean"])
    return (
        point
        if estimate["low"] is None
        else f"{point} [{estimate['low']:.3f}, {estimate['high']:.3f}]"
    )


def write_analysis(result, run_dir):
    reports, metrics = run_dir / "reports", run_dir / "metrics"
    reports.mkdir(exist_ok=True)
    metrics.mkdir(exist_ok=True)
    (metrics / "interface_analysis.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Saved-trajectory analysis: {run_dir.name}",
        "",
        f"- Completed games: {result['completed_games']} / {result['planned_games']}",
        f"- Common fully parsed examples: {result['common_examples']} / {result['planned_examples']}",
        f"- Common regime counts: {result['common_regime_counts']}",
        f"- Bootstrap: {result['bootstrap']['resamples']} resamples, seed {result['bootstrap']['seed']}; paired within-example and stratified by regime.",
        "",
        "## Error by turn (common matched set)",
        "",
        "Projected errors show means and 95% percentile intervals. Every turn uses the same examples.",
        "",
        "| Interface | Turn | N | Projected ΔE [95% interval] | Mean native ΔE |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result["curves"]:
        lines.append(
            f"| {row['variant']} | {row['turn']} | {row['projected_error']['n']} | {_interval(row['projected_error'])} | {_number(row['native_error'])} |"
        )
    for cohort, title in (
        ("common_triplets", "Paired effects on the common matched set"),
        ("available_pairs", "Sensitivity: all available fully parsed pairs"),
    ):
        lines += [
            "",
            f"## {title}",
            "",
            "Right minus left. Negative error deltas favor the right interface; positive gain deltas indicate larger correction. Different initial guesses prevent a causal comparison of feedback alone.",
            "",
            "| Left → right | N | Δ initial error [95% interval] | Δ final error [95% interval] | Δ gain [95% interval] | Δ final–best gap [95% interval] |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for row in result["paired_effects"]:
            if row["cohort"] == cohort:
                lines.append(
                    f"| {row['left']} → {row['right']} | {row['n']} | "
                    + " | ".join(
                        _interval(row["metrics"][k])
                        for k in (
                            "initial_error",
                            "final_error",
                            "gain",
                            "final_best_gap",
                        )
                    )
                    + " |"
                )
    lines += [
        "",
        "## Control diagnostics (common set)",
        "",
        "Convergence uses the run's threshold. Zero-movement revisions are counted on displayed states. A small final–best gap can accompany stagnation, not just good stopping behavior.",
        "",
        "| Interface | N | Initially converged | Initially converged then lost | Improved vs initial | Worsened vs initial | Final equals best | Zero-movement revisions / opportunities |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["control_diagnostics"]:
        lines.append(
            f"| {row['variant']} | {row['n']} | {row['initially_converged_n']} | {row['initially_converged_then_lost_n']} | {row['improved_n']} | {row['worsened_n']} | {row['final_is_best_n']} | {row['zero_movement_revisions_n']} / {row['revision_opportunities']} |"
        )
    lines += [
        "",
        "## Largest final–best gaps",
        "",
        "These are observed gaps, not evidence of their underlying cause. Earliest best turn is shown when tied.",
        "",
    ]
    for row in result["largest_overshoots"]:
        description = json.dumps(row["description"], ensure_ascii=False)
        lines.append(
            f"- {row['condition_id']} {description}: ΔE by turn = "
            + ", ".join(f"{x:.3f}" for x in row["errors_by_turn"])
            + f"; first best turn {row['first_best_turn']}; final–best gap {row['final_best_gap']:.3f}."
        )
    lines += [
        "",
        "## Parse failures",
        "",
        f"- Failed responses: {len(result['parse_failures'])}",
        "- Saved raw responses and prompts are included in metrics/interface_analysis.json.",
        "- Finish reasons and generated token counts were not recorded; truncation cannot be confirmed from these checkpoints.",
        "",
    ]
    for row in result["parse_failures"]:
        lines.append(
            f"- {row['condition_id']}, turn {row['turn']}: {row['parse_reason']}; arithmetic-text flag={row['arithmetic_text']}."
        )
    lines += [
        "",
        "## Scope of uncertainty",
        "",
        "The bootstrap resamples whole examples within each available regime, preserving its observed cohort size and all paired interfaces/turns. Point estimates retain the report's pooled example weighting; regimes are not reweighted equally after failures. Intervals describe empirical variation across sampled examples, conditional on fully parsed trajectories. They do not measure model-generation randomness, remove failure-selection bias, establish population generalization, or correct for multiple exploratory comparisons. Singleton strata have no within-stratum resampling variation; one-example cohorts receive no interval. The available-pairs table checks sensitivity to requiring all three interfaces to parse. Failed outcomes are not imputed or repaired. This analysis does not change prompts, token limits, checkpoints, or the original summary.",
        "",
    ]
    (reports / "interface_analysis.md").write_text("\n".join(lines), encoding="utf-8")
