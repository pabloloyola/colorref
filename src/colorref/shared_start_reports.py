"""First-revision and full-trajectory cohorts for the shared-start control."""

from __future__ import annotations

import json
from statistics import mean

import numpy as np

from colorref.colors import color_distance_lab
from colorref.interface_analysis import COMPARISONS, paired_bootstrap
from colorref.interface_study import REGIMES, VARIANTS
from colorref.shared_start_study import is_complete, revision_prompt, supplied_start


def _mean(values):
    values = [x for x in values if x is not None]
    return mean(values) if values else None


def summarize(cfg, plan, checkpoints, resamples=5000, seed=13):
    turns = cfg["execution"]["max_turns"]
    games = []
    failures = []
    projection = []
    for task in plan["tasks"]:
        records = checkpoints.get(task["slot"], [])
        start = supplied_start(task)
        _, feedback = revision_prompt(task, [], cfg, plan["templates"])
        first = records[0] if records and records[0]["parse_ok"] else None
        full = len(records) == turns and all(r["parse_ok"] for r in records)
        final = records[-1] if full else None
        errors = [start["projected_error_delta_e"]] + [
            r["projected_error_delta_e"] for r in records if r["parse_ok"]
        ]
        history = [start, *[r for r in records if r["parse_ok"]]]
        games.append(
            {
                "condition_id": task["condition_id"],
                "example_id": task["example"]["example_id"],
                "regime_label": task["example"]["regime_label"],
                "variant": task["variant"],
                "supplied_start_hex": start["displayed_state"]["hex"],
                "initial_error": start["projected_error_delta_e"],
                "initially_converged": start["projected_error_delta_e"]
                <= cfg["execution"]["convergence_delta_e"],
                "no_first_constraint": not feedback["metadata"].get("all_constraints"),
                "completed": is_complete(records, turns),
                "generated_responses": len(records),
                "first_parsed": first is not None,
                "full_trajectory": full,
                "first_error": first["projected_error_delta_e"] if first else None,
                "first_gain": start["projected_error_delta_e"]
                - first["projected_error_delta_e"]
                if first
                else None,
                "first_native_error": first["native_error_delta_e"] if first else None,
                "first_satisfaction": first["constraint_satisfaction"]
                if first
                else None,
                "first_alignment": first["directional_alignment"]
                if first and feedback["metadata"].get("all_constraints")
                else None,
                "first_movement": color_distance_lab(
                    start["displayed_state"]["lab"], first["displayed_state"]["lab"]
                )
                if first
                else None,
                "final_error": final["projected_error_delta_e"] if final else None,
                "final_gain": errors[0] - errors[-1] if full else None,
                "final_native_error": final["native_error_delta_e"] if final else None,
                "best_error": min(errors) if full else None,
                "final_best_gap": errors[-1] - min(errors) if full else None,
                "final_converged": errors[-1] <= cfg["execution"]["convergence_delta_e"]
                if full
                else None,
                "initially_converged_then_lost": errors[0]
                <= cfg["execution"]["convergence_delta_e"]
                < errors[-1]
                if full
                else None,
                "zero_movement_revisions": sum(
                    color_distance_lab(
                        a["displayed_state"]["lab"], b["displayed_state"]["lab"]
                    )
                    <= 1e-8
                    for a, b in zip(history, history[1:])
                )
                if full
                else None,
            }
        )
        for row in records:
            if row["parse_ok"]:
                projection.append(
                    {"variant": task["variant"], "delta_e": row["projection_delta_e"]}
                )
            else:
                failures.append(
                    {
                        "condition_id": task["condition_id"],
                        "turn": row["turn"],
                        "reason": row["parse_reason"],
                        "prompt": row["prompt"],
                        "raw_response": row["raw_response"],
                        "generation": row.get("generation"),
                    }
                )
    grouped = {}
    for row in games:
        grouped.setdefault(row["example_id"], {})[row["variant"]] = row
    common = {
        endpoint: [
            i for i in sorted(grouped) if all(grouped[i][v][flag] for v in VARIANTS)
        ]
        for endpoint, flag in (("first", "first_parsed"), ("final", "full_trajectory"))
    }
    effects = []
    for endpoint, flag in (("first", "first_parsed"), ("final", "full_trajectory")):
        for cohort in ("common_triplets", "available_pairs"):
            for left, right in COMPARISONS:
                ids = (
                    common[endpoint]
                    if cohort == "common_triplets"
                    else [
                        i
                        for i in sorted(grouped)
                        if grouped[i][left][flag] and grouped[i][right][flag]
                    ]
                )
                differences = np.array(
                    [
                        [
                            grouped[i][right][f"{endpoint}_error"]
                            - grouped[i][left][f"{endpoint}_error"],
                            grouped[i][right][f"{endpoint}_gain"]
                            - grouped[i][left][f"{endpoint}_gain"],
                        ]
                        for i in ids
                    ],
                    dtype=float,
                ).reshape(len(ids), 2)
                if not np.allclose(differences[:, 0], -differences[:, 1], atol=1e-10):
                    raise ValueError(
                        "Shared-start error/gain difference identity failed"
                    )
                regimes = [grouped[i][left]["regime_label"] for i in ids]
                estimates = paired_bootstrap(differences, regimes, resamples, seed)
                effects.append(
                    {
                        "endpoint": endpoint,
                        "cohort": cohort,
                        "left": left,
                        "right": right,
                        "n": len(ids),
                        "regime_counts": {r: regimes.count(r) for r in REGIMES},
                        "error_delta": estimates[0],
                        "gain_delta": estimates[1],
                    }
                )
    return {
        "planned_games": len(games),
        "planned_examples": len(grouped),
        "maximum_generations": len(games) * turns,
        "completed_games": sum(r["completed"] for r in games),
        "generated_responses": sum(r["generated_responses"] for r in games),
        "common_first_ids": common["first"],
        "common_final_ids": common["final"],
        "games": games,
        "effects": effects,
        "projection": projection,
        "parse_failures": failures,
        "bootstrap": {"resamples": resamples, "seed": seed},
    }


def _fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def _ci(estimate):
    return (
        _fmt(estimate["mean"])
        if estimate["low"] is None
        else f"{estimate['mean']:.3f} [{estimate['low']:.3f}, {estimate['high']:.3f}]"
    )


def write_reports(cfg, plan, checkpoints, run_dir, resamples=5000, seed=13):
    result = summarize(cfg, plan, checkpoints, resamples, seed)
    reports, metrics = run_dir / "reports", run_dir / "metrics"
    reports.mkdir(exist_ok=True)
    metrics.mkdir(exist_ok=True)
    (metrics / "shared_start_analysis.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    games = result["games"]
    lines = [
        f"# Shared-start output-interface study: {run_dir.name}",
        "",
        f"- Parent run: {plan['parent']['run_id']}",
        f"- Completed games: {result['completed_games']} / {result['planned_games']}",
        f"- Generated responses: {result['generated_responses']} / {result['maximum_generations']} maximum (assigned starts excluded)",
        f"- Parse failures: {len(result['parse_failures'])}",
        f"- Common first-revision examples: {len(result['common_first_ids'])} / {result['planned_examples']}",
        f"- Common full-trajectory examples: {len(result['common_final_ids'])} / {result['planned_examples']}",
        "- Starting states and first oracle corrections match across all three interfaces.",
        "",
        "## Completion by interface",
        "",
        "| Interface | Completed | First parsed | Full trajectory |",
        "|---|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [r for r in games if r["variant"] == variant]
        lines.append(
            f"| {variant} | {sum(r['completed'] for r in rows)} / {len(rows)} | {sum(r['first_parsed'] for r in rows)} | {sum(r['full_trajectory'] for r in rows)} |"
        )
    lines += [
        "",
        "## First revision (primary common cohort)",
        "",
        "| Interface | N | Starting ΔE | Revised ΔE | Gain | Constraint satisfaction (N) | Alignment (N) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [
            r
            for r in games
            if r["variant"] == variant and r["example_id"] in result["common_first_ids"]
        ]
        sat = [
            r["first_satisfaction"] for r in rows if r["first_satisfaction"] is not None
        ]
        alignment = [
            r["first_alignment"] for r in rows if r["first_alignment"] is not None
        ]
        lines.append(
            f"| {variant} | {len(rows)} | "
            + " | ".join(
                _fmt(_mean([r[k] for r in rows]))
                for k in ("initial_error", "first_error", "first_gain")
            )
            + f" | {_fmt(_mean(sat))} ({len(sat)}) | {_fmt(_mean(alignment))} ({len(alignment)}) |"
        )
    for endpoint in ("first", "final"):
        lines += [
            "",
            f"## Paired {endpoint}-revision effects",
            "",
            "Right minus left, with 95% percentile intervals. Negative error favors the right interface. Gain deltas are the negatives of error deltas because starts match.",
            "",
            "| Cohort | Left → right | N | Δ error [95% interval] | Δ gain [95% interval] |",
            "|---|---|---:|---:|---:|",
        ]
        for row in result["effects"]:
            if row["endpoint"] == endpoint:
                lines.append(
                    f"| {row['cohort']} | {row['left']} → {row['right']} | {row['n']} | {_ci(row['error_delta'])} | {_ci(row['gain_delta'])} |"
                )
    lines += [
        "",
        "## Final revision (secondary common full-trajectory cohort)",
        "",
        "| Interface | N | Final projected ΔE | Final native ΔE | Best ΔE | Final–best gap | Converged N | Zero-movement revisions |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [
            r
            for r in games
            if r["variant"] == variant and r["example_id"] in result["common_final_ids"]
        ]
        lines.append(
            f"| {variant} | {len(rows)} | "
            + " | ".join(
                _fmt(_mean([r[k] for r in rows]))
                for k in (
                    "final_error",
                    "final_native_error",
                    "best_error",
                    "final_best_gap",
                )
            )
            + f" | {sum(r['final_converged'] for r in rows)} | {sum(r['zero_movement_revisions'] for r in rows)} / {len(rows) * cfg['execution']['max_turns']} |"
        )
    lines += [
        "",
        "## Assigned-start drift controls (all available observations)",
        "",
        "Categories overlap. Initially converged uses the run threshold; no-constraint is defined by the first oracle message. First-revision counts remain valid after a later failure.",
        "",
        "| Interface | Category | Planned | First parsed | Mean first movement ΔE | Mean first gain | Full trajectories | Initially converged then lost |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        for flag in ("initially_converged", "no_first_constraint"):
            rows = [r for r in games if r["variant"] == variant and r[flag]]
            first = [r for r in rows if r["first_parsed"]]
            full = [r for r in rows if r["full_trajectory"]]
            lines.append(
                f"| {variant} | {flag} | {len(rows)} | {len(first)} | {_fmt(_mean([r['first_movement'] for r in first]))} | {_fmt(_mean([r['first_gain'] for r in first]))} | {len(full)} | {sum(r['initially_converged_then_lost'] for r in full)} |"
            )
    lines += [
        "",
        "## Projection diagnostic (generated parsed states only)",
        "",
        "| Interface | Parsed generated states | Mean projection ΔE | Projection > 1 N |",
        "|---|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        values = [r["delta_e"] for r in result["projection"] if r["variant"] == variant]
        lines.append(
            f"| {variant} | {len(values)} | {_fmt(_mean(values))} | {sum(x > 1 for x in values)} |"
        )
    lines += [
        "",
        "## Failed output diagnostics",
        "",
        "HF finish labels summarize observed output tokens; compatible APIs report their backend finish reason. EOS at the last allowed token can reach both EOS and the budget.",
        "",
        "| Condition | Revision | Generated tokens | Finish reason | Source |",
        "|---|---:|---:|---|---|",
    ]
    for row in result["parse_failures"]:
        generation = row.get("generation") or {}
        values = [
            generation.get(k)
            for k in ("generated_tokens", "finish_reason", "finish_reason_source")
        ]
        lines.append(
            f"| {row['condition_id']} | {row['turn']} | "
            + " | ".join(str(x) if x is not None else "unknown" for x in values)
            + " |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "Starts are supplied from the parent's HEX predictions, not predicted by each receiving interface. First feedback is identical; later adaptive messages can differ. All generations use a fresh context, latest feedback only, strict parsing, and fixed rounds including close starts. Native LAB and displayed uint8 sRGB errors differ; displayed error is primary. First-revision and final cohorts exclude failures separately; available-pair estimates check sensitivity to requiring a third interface to parse. The paired bootstrap resamples whole examples within regimes, retaining each observed cohort's sizes and pooled weights. These intervals do not quantify generation randomness, remove failure-selection bias, establish population generalization, or adjust for multiple comparisons. Singleton strata have no resampling variation; a one-example cohort has no interval. Results are conditional on the HEX-derived starting-state policy and this prompt intervention. No outputs are repaired or filtered by projection error. Backend-observed generation diagnostics remain in checkpoints; missing fields are unknown. Assigned starts never enter generated-response/projection counts. Full failure prompts/responses and per-game statistics are in metrics/shared_start_analysis.json.",
        "",
    ]
    (reports / "shared_start_summary.md").write_text("\n".join(lines), encoding="utf-8")
    return result
