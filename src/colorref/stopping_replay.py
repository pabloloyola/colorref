"""Target-threshold stopping on saved trajectories, with no best-state lookahead."""

from __future__ import annotations

import json
import math
from statistics import mean

import numpy as np

from colorref.interface_analysis import COMPARISONS, paired_bootstrap
from colorref.interface_study import REGIMES, VARIANTS
from colorref.shared_start_study import supplied_start


def replay(start, records, max_turns, threshold):
    """Inspect only prefixes; a later failure cannot undo an earlier stop."""
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("Stopping threshold must be positive and finite")
    if start["projected_error_delta_e"] <= threshold:
        return {
            "status": "threshold",
            "turn": 0,
            "error": start["projected_error_delta_e"],
        }
    for turn, row in enumerate(records, start=1):
        if not row["parse_ok"]:
            return {"status": "parse_failure", "turn": turn, "error": None}
        if row["projected_error_delta_e"] <= threshold:
            return {
                "status": "threshold",
                "turn": turn,
                "error": row["projected_error_delta_e"],
            }
    if len(records) == max_turns:
        return {
            "status": "budget_exhausted",
            "turn": max_turns,
            "error": records[-1]["projected_error_delta_e"],
        }
    return {"status": "pending", "turn": len(records), "error": None}


def analyze(cfg, plan, checkpoints, threshold=None, resamples=5000, seed=13):
    cutoff = float(
        cfg["execution"]["convergence_delta_e"] if threshold is None else threshold
    )
    if not math.isfinite(cutoff) or cutoff <= 0:
        raise ValueError("Stopping threshold must be positive and finite")
    turns = cfg["execution"]["max_turns"]
    games = []
    for task in plan["tasks"]:
        start = supplied_start(task)
        records = checkpoints.get(task["slot"], [])
        outcome = replay(start, records, turns, cutoff)
        full = len(records) == turns and all(r["parse_ok"] for r in records)
        first_hit = outcome["turn"] if outcome["status"] == "threshold" else None
        final_error = records[-1]["projected_error_delta_e"] if full else None
        games.append(
            {
                "condition_id": task["condition_id"],
                "example_id": task["example"]["example_id"],
                "description": task["example"]["raw_name"],
                "regime": task["example"]["regime_label"],
                "variant": task["variant"],
                "initial_error": start["projected_error_delta_e"],
                "fixed_full": full,
                "saved_response_count": len(records),
                "fixed_error": final_error,
                "fixed_converged": final_error <= cutoff if full else None,
                "stop_status": outcome["status"],
                "stop_error": outcome["error"],
                "stop_turn": outcome["turn"],
                "first_threshold_turn": first_hit,
                "stop_converged": outcome["error"] <= cutoff
                if outcome["error"] is not None
                else None,
                "saved_calls": turns - outcome["turn"] if full else None,
                "initially_converged": start["projected_error_delta_e"] <= cutoff,
                "converged_then_lost": full
                and first_hit is not None
                and final_error > cutoff,
                "errors_by_turn": [
                    start["projected_error_delta_e"],
                    *[r["projected_error_delta_e"] for r in records],
                ],
            }
        )
    grouped = {}
    for row in games:
        grouped.setdefault(row["example_id"], {})[row["variant"]] = row
    common = [
        i for i in sorted(grouped) if all(grouped[i][v]["fixed_full"] for v in VARIANTS)
    ]
    strata = [grouped[i]["hex"]["regime"] for i in common]
    summaries = []
    within = []
    for variant in VARIANTS:
        rows = [grouped[i][variant] for i in common]
        differences = np.array(
            [
                [
                    r["stop_error"] - r["fixed_error"],
                    r["stop_turn"] - turns,
                    int(r["stop_converged"]) - int(r["fixed_converged"]),
                ]
                for r in rows
            ],
            dtype=float,
        ).reshape(len(rows), 3)
        estimates = paired_bootstrap(differences, strata, resamples, seed)
        within.append(
            {
                "variant": variant,
                "n": len(rows),
                "error_delta": estimates[0],
                "calls_delta": estimates[1],
                "convergence_rate_delta": estimates[2],
            }
        )
        summaries.append(
            {
                "variant": variant,
                "n": len(rows),
                "mean_fixed_error": mean(r["fixed_error"] for r in rows)
                if rows
                else None,
                "mean_stop_error": mean(r["stop_error"] for r in rows)
                if rows
                else None,
                "fixed_converged_n": sum(r["fixed_converged"] for r in rows),
                "stop_converged_n": sum(r["stop_converged"] for r in rows),
                "fixed_calls": turns * len(rows),
                "stop_calls": sum(r["stop_turn"] for r in rows),
                "mean_stop_calls": mean(r["stop_turn"] for r in rows) if rows else None,
                "saved_calls": sum(r["saved_calls"] for r in rows),
                "stop_turn_counts": {
                    str(t): sum(r["stop_turn"] == t for r in rows)
                    for t in range(turns + 1)
                },
                "initially_converged_n": sum(r["initially_converged"] for r in rows),
                "converged_then_lost_n": sum(r["converged_then_lost"] for r in rows),
            }
        )
    between = []
    for policy in ("fixed", "stop"):
        for left, right in COMPARISONS:
            differences = np.array(
                [
                    [
                        grouped[i][right][f"{policy}_error"]
                        - grouped[i][left][f"{policy}_error"]
                    ]
                    for i in common
                ],
                dtype=float,
            ).reshape(len(common), 1)
            estimate = paired_bootstrap(differences, strata, resamples, seed)[0]
            between.append(
                {
                    "policy": policy,
                    "left": left,
                    "right": right,
                    "error_delta": estimate,
                }
            )
    return {
        "threshold": cutoff,
        "threshold_source": "frozen_config"
        if threshold is None
        else "explicit_analysis_override",
        "max_turns": turns,
        "planned_examples": len(grouped),
        "common_examples": len(common),
        "common_example_ids": common,
        "common_regime_counts": {r: strata.count(r) for r in REGIMES},
        "bootstrap": {"resamples": resamples, "seed": seed},
        "games": games,
        "summaries": summaries,
        "within_interface_effects": within,
        "between_interface_effects": between,
        "lost_convergence_cases": [
            r for r in games if r["example_id"] in common and r["converged_then_lost"]
        ],
        "available_outcome_counts": [
            {
                "variant": v,
                "planned": sum(r["variant"] == v for r in games),
                "fixed_full": sum(r["variant"] == v and r["fixed_full"] for r in games),
                "threshold_stops": sum(
                    r["variant"] == v and r["stop_status"] == "threshold" for r in games
                ),
                "budget_exhausted": sum(
                    r["variant"] == v and r["stop_status"] == "budget_exhausted"
                    for r in games
                ),
                "parse_failure_before_stop": sum(
                    r["variant"] == v and r["stop_status"] == "parse_failure"
                    for r in games
                ),
                "pending": sum(
                    r["variant"] == v and r["stop_status"] == "pending" for r in games
                ),
            }
            for v in VARIANTS
        ],
    }


def _fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def _ci(value):
    return (
        _fmt(value["mean"])
        if value["low"] is None
        else f"{value['mean']:.3f} [{value['low']:.3f}, {value['high']:.3f}]"
    )


def write_reports(result, run_dir):
    (run_dir / "reports").mkdir(exist_ok=True)
    (run_dir / "metrics").mkdir(exist_ok=True)
    (run_dir / "metrics/stopping_replay.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Saved-trajectory stopping replay: {run_dir.name}",
        "",
        f"- Rule: stop at the first displayed state with ΔE ≤ {result['threshold']:g}, including the assigned starting state.",
        f"- Threshold source: {result['threshold_source']}",
        f"- Primary common fully parsed examples: {result['common_examples']} / {result['planned_examples']}",
        f"- Regime counts: {result['common_regime_counts']}",
        f"- Fixed cap: {result['max_turns']} revisions; replay performs zero new generations.",
        "",
        "## Fixed rounds versus threshold stopping (same common cohort)",
        "",
        "| Interface | N | Fixed final ΔE | Stopped ΔE | Fixed converged N | Stopped converged N | Fixed calls | Stopped calls | Saved calls |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["summaries"]:
        lines.append(
            f"| {r['variant']} | {r['n']} | {_fmt(r['mean_fixed_error'])} | {_fmt(r['mean_stop_error'])} | {r['fixed_converged_n']} | {r['stop_converged_n']} | {r['fixed_calls']} | {r['stop_calls']} | {r['saved_calls']} |"
        )
    lines += [
        "",
        "## Within-interface paired effects",
        "",
        "Stopped minus fixed, with 95% percentile intervals. Negative error means smaller target disagreement; negative calls means fewer generations. Convergence deltas are proportions, not percentage points.",
        "",
        "| Interface | N | Δ error [95% interval] | Δ calls [95% interval] | Δ convergence rate [95% interval] |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in result["within_interface_effects"]:
        lines.append(
            f"| {r['variant']} | {r['n']} | {_ci(r['error_delta'])} | {_ci(r['calls_delta'])} | {_ci(r['convergence_rate_delta'])} |"
        )
    lines += [
        "",
        "## Cross-interface error effects under each policy",
        "",
        "Right minus left on the same cohort; negative favors the right interface.",
        "",
        "| Policy | Left → right | N | Δ error [95% interval] |",
        "|---|---|---:|---:|",
    ]
    for r in result["between_interface_effects"]:
        lines.append(
            f"| {r['policy']} | {r['left']} → {r['right']} | {r['error_delta']['n']} | {_ci(r['error_delta'])} |"
        )
    lines += [
        "",
        "## Stop-turn distribution",
        "",
        "Turn zero is an assigned state and costs no generation. Reaching the threshold on the last turn saves no calls.",
        "",
        "| Interface | Stop turn counts | Initially close N | Reached threshold then lost N |",
        "|---|---|---:|---:|",
    ]
    for r in result["summaries"]:
        lines.append(
            f"| {r['variant']} | {json.dumps(r['stop_turn_counts'], sort_keys=True)} | {r['initially_converged_n']} | {r['converged_then_lost_n']} |"
        )
    lines += [
        "",
        "## Cases where fixed rounds lose reached convergence",
        "",
        "These are diagnostic trajectories, not a model-generated stopping policy.",
        "",
    ]
    for r in result["lost_convergence_cases"]:
        lines.append(
            f"- {r['condition_id']} {json.dumps(r['description'], ensure_ascii=False)}: first threshold turn {r['first_threshold_turn']}; errors {', '.join(_fmt(x) for x in r['errors_by_turn'])}."
        )
    lines += [
        "",
        "## Completion sensitivity (all planned games)",
        "",
        "A threshold hit completes the replay even when later saved revisions fail or remain pending. Accuracy/paired effects above still use the common fully parsed fixed-round cohort, so changed denominators cannot masquerade as policy benefits.",
        "",
        "| Interface | Planned | Fixed full | Threshold stops | Budget exhausted | Parse failure before stop | Pending |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["available_outcome_counts"]:
        lines.append(
            f"| {r['variant']} | {r['planned']} | {r['fixed_full']} | {r['threshold_stops']} | {r['budget_exhausted']} | {r['parse_failure_before_stop']} | {r['pending']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This is a target-known benchmark stopping diagnostic, not a learned or deployable model-only policy. It stops at the first qualifying saved prefix, never at the best state selected retrospectively. Prompts and feedback are identical up to stopping; no continuation is synthesized, failed output repaired, or unfinished endpoint imputed. Assigned starts cost zero calls. Earlier stopping can retain a worse error than a later still-converged fixed endpoint; error reduction is not guaranteed. Paired intervals resample whole common examples within semantic regimes, retaining observed regime sizes and pooled weighting. They condition on this cohort and starting-state policy, do not measure generation randomness or population generalization, and do not adjust for exploratory multiple comparisons. Singleton strata have no resampling variation; a one-example cohort has no interval. Explicit threshold overrides are labeled analysis sensitivity, not predeclared primary settings. Only stopping_replay.json and stopping_replay_summary.md are written; frozen plans, checkpoints, and original summaries are preserved.",
        "",
    ]
    (run_dir / "reports/stopping_replay_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
