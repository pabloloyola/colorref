"""Failure-aware terminal and observed-prefix analysis of sequential control."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median

import numpy as np

from colorref.magnitude_control import ARMS
from colorref.magnitude_reports import average, cluster_effect, fmt
from colorref.magnitude_transfer import endpoint
from colorref.quantifiers import DIRECTION_SPECS


def group_endpoints(endpoints):
    groups = {}
    for row in endpoints:
        groups.setdefault(row["case_id"], {})[row["arm"]] = row
    return groups


def effects(cfg, groups):
    common = [g for g in groups.values() if all(g[a]["valid"] for a in ARMS)]
    result = []
    for cohort in ("common_triplets", "available_pairs"):
        for right in ("calibrated", "numeric"):
            cases = (
                common
                if cohort == "common_triplets"
                else [
                    g
                    for g in groups.values()
                    if g["bare"]["valid"] and g[right]["valid"]
                ]
            )
            for measure in ("error", "calls", "converged"):
                values = [g[right][measure] - g["bare"][measure] for g in cases]
                result.append(
                    {
                        "cohort": cohort,
                        "right": right,
                        "measure": measure,
                        **cluster_effect(
                            values,
                            [g["bare"]["base_id"] for g in cases],
                            cfg["analysis"]["resamples"],
                            cfg["analysis"]["seed"],
                        ),
                    }
                )
    return common, result


def common_table(common):
    return [
        {
            "arm": arm,
            "n": len(common),
            "mean_error": average([g[arm] for g in common], lambda r: r["error"]),
            "median_error": median(g[arm]["error"] for g in common) if common else None,
            "mean_gain": average([g[arm] for g in common], lambda r: r["gain"]),
            "mean_calls": average([g[arm] for g in common], lambda r: r["calls"]),
            "converged": sum(g[arm]["converged"] for g in common),
        }
        for arm in ARMS
    ]


def subset_stats(cfg, common, label):
    values = [g["calibrated"]["error"] - g["bare"]["error"] for g in common]
    return {
        "label": label,
        "arms": common_table(common),
        "effect": cluster_effect(
            values,
            [g["bare"]["base_id"] for g in common],
            cfg["analysis"]["resamples"],
            cfg["analysis"]["seed"],
        ),
        "median_difference": median(values) if values else None,
        "wins": sum(v < -0.01 for v in values),
        "ties": sum(abs(v) <= 0.01 for v in values),
        "losses": sum(v > 0.01 for v in values),
    }


def analyze(cfg, plan, checkpoints):
    endpoints = [
        endpoint(g, checkpoints.get(g["condition_id"], []), cfg, plan)
        for g in plan["games"]
    ]
    groups = group_endpoints(endpoints)
    common, contrasts = effects(cfg, groups)
    result = {
        "parent_run_id": plan["parent_run_id"],
        "planned_games": len(plan["games"]),
        "fresh_starts": len(plan["starts"]),
        "targets": len(plan["evaluation_cases"]),
        "exclusions": len(plan["feasibility_exclusions"]),
        "maximum_generations": len(plan["games"]) * cfg["execution"]["max_revisions"],
        "max_revisions": cfg["execution"]["max_revisions"],
        "threshold": cfg["study"]["convergence_delta_e"],
        "common_triplets": len(common),
        "common_accuracy": common_table(common),
        "effects": contrasts,
        "endpoints": endpoints,
        "completion": [],
        "prefixes": [],
        "diagnostics": [],
        "numeric_misses": [],
        "failures": [],
        "subgroups": [],
        "per_start": [],
        "coverage": [],
    }
    parsed = []
    for game in plan["games"]:
        records = checkpoints.get(game["condition_id"], [])
        parsed.extend(r for r in records if r["parse_ok"])
        for r in records:
            if not r["parse_ok"]:
                result["failures"].append(
                    {
                        "game": game["condition_id"],
                        "turn": r["turn"],
                        "reason": r["parse_reason"],
                        "prompt": r["prompt"],
                        "response": r["raw_response"],
                        "generation": r.get("generation"),
                    }
                )
    for arm in ARMS:
        outcomes = [r for r in endpoints if r["arm"] == arm]
        records = [
            r
            for g in plan["games"]
            if g["arm"] == arm
            for r in checkpoints.get(g["condition_id"], [])
        ]
        rows = [r for r in records if r["parse_ok"]]
        stops = Counter(r["status"] for r in outcomes)
        result["completion"].append(
            {
                "arm": arm,
                "planned": len(outcomes),
                "statuses": dict(stops),
                "valid_terminals": sum(r["valid"] for r in outcomes),
                "zero_call_stops": sum(r["zero_call_stop"] for r in outcomes),
                "generated": len(records),
                "parsed": len(rows),
                "parse_failures": len(records) - len(rows),
                "all_planned_converged": sum(r["converged"] for r in outcomes),
                "all_planned_convergence_rate": sum(r["converged"] for r in outcomes)
                / len(outcomes)
                if outcomes
                else None,
                "stop_turn_counts": dict(
                    Counter(r["calls"] for r in outcomes if r["valid"])
                ),
            }
        )
        result["diagnostics"].append(
            {
                "arm": arm,
                "parsed_revisions": len(rows),
                "harmful_revisions": sum(r["metrics"]["gain"] < -1e-9 for r in rows),
                "beyond_improvement_bound": sum(
                    r["metrics"]["improvement_step_bound"] is not None
                    and r["metrics"]["displayed_movement_norm"]
                    > r["metrics"]["improvement_step_bound"] + 1e-9
                    for r in rows
                ),
                "reversed_direction_revisions": sum(
                    r["direction"] != r["original_direction"] for r in rows
                ),
                **{
                    k: average(rows, lambda r, key=k: r["metrics"].get(key))
                    for k in (
                        "native_requested_signed_step",
                        "displayed_requested_signed_step",
                        "displayed_off_axis_drift",
                        "displayed_direction_followed",
                        "numeric_native_execution_error",
                        "numeric_display_execution_error",
                        "numeric_expected_target_disagreement",
                    )
                },
                "projection_mean": average(rows, lambda r: r["projection_delta_e"]),
                "projection_over_1": sum(r["projection_delta_e"] > 1 for r in rows),
                "mean_prompt_tokens": average(
                    records, lambda r: r.get("prompt_tokens")
                ),
                "mean_output_tokens": average(
                    records, lambda r: r.get("generation", {}).get("generated_tokens")
                ),
                "known_prompt_token_records": sum(
                    r.get("prompt_tokens") is not None for r in records
                ),
                "known_output_token_records": sum(
                    r.get("generation", {}).get("generated_tokens") is not None
                    for r in records
                ),
                "total_known_prompt_tokens": sum(
                    r.get("prompt_tokens") or 0 for r in records
                ),
                "total_known_output_tokens": sum(
                    r.get("generation", {}).get("generated_tokens") or 0
                    for r in records
                ),
                "emitted_axis_corrections": len(records),
            }
        )
    result["generated"] = sum(r["generated"] for r in result["completion"])
    result["parsed"] = len(parsed)
    for budget in (1, 3):
        prefix = [
            endpoint(g, checkpoints.get(g["condition_id"], []), cfg, plan, budget)
            for g in plan["games"]
        ]
        cohort, contrast = effects(cfg, group_endpoints(prefix))
        result["prefixes"].append(
            {
                "budget": budget,
                "common_triplets": len(cohort),
                "accuracy": common_table(cohort),
                "effects": contrast,
                "outcomes": prefix,
            }
        )
    numeric = [r for r in parsed if r["arm"] == "numeric"]
    errors = [r["metrics"]["numeric_native_execution_error"] for r in numeric]
    result["numeric_execution"] = {
        "parsed": len(errors),
        "within_0_01": sum(e <= 0.01 for e in errors),
        "within_1": sum(e <= 1 for e in errors),
        "above_1": sum(e > 1 for e in errors),
        "mean": mean(errors) if errors else None,
        "median": median(errors) if errors else None,
        "p95": float(np.quantile(errors, 0.95)) if errors else None,
        "max": max(errors) if errors else None,
    }
    for r in sorted(
        numeric,
        key=lambda r: r["metrics"]["numeric_native_execution_error"],
        reverse=True,
    ):
        if r["metrics"]["numeric_native_execution_error"] <= 0.01:
            continue
        result["numeric_misses"].append(
            {
                "condition_id": r["condition_id"],
                "turn": r["turn"],
                "expected_lab": r["expected_numeric_lab"],
                "actual_lab": r["native_lab"],
                "coordinate_residual": [
                    a - e for a, e in zip(r["native_lab"], r["expected_numeric_lab"])
                ],
                "native_error": r["metrics"]["numeric_native_execution_error"],
                "projection_delta_e": r["projection_delta_e"],
                "prompt": r["prompt"],
                "response": r["raw_response"],
                "generation": r.get("generation"),
            }
        )
    for direction in DIRECTION_SPECS:
        result["subgroups"].append(
            subset_stats(
                cfg,
                [g for g in common if g["bare"]["direction"] == direction],
                direction,
            )
        )
    for distance in cfg["study"]["target_steps"]:
        result["subgroups"].append(
            subset_stats(
                cfg,
                [g for g in common if g["bare"]["distance"] == distance],
                f"distance_{distance:g}",
            )
        )
        for direction in DIRECTION_SPECS:
            cohort = [
                g
                for g in common
                if g["bare"]["distance"] == distance
                and g["bare"]["direction"] == direction
            ]
            result["subgroups"].append(
                subset_stats(cfg, cohort, f"{direction}/{distance:g}")
            )
    for start in plan["starts"]:
        identifier = start["base_id"]
        cohort = [g for g in common if g["bare"]["base_id"] == identifier]
        omitted = [
            g["calibrated"]["error"] - g["bare"]["error"]
            for g in common
            if g["bare"]["base_id"] != identifier
        ]
        result["per_start"].append(
            {
                "base_id": identifier,
                "hex": start["state"]["hex"],
                "n": len(cohort),
                "arms": common_table(cohort),
                "mean_difference": mean(
                    g["calibrated"]["error"] - g["bare"]["error"] for g in cohort
                )
                if cohort
                else None,
                "leave_one_start_out_mean": mean(omitted)
                if cohort and omitted
                else None,
            }
        )
    for direction in DIRECTION_SPECS:
        for distance in cfg["study"]["target_steps"]:
            result["coverage"].append(
                {
                    "direction": direction,
                    "distance": distance,
                    "planned": len(plan["starts"]),
                    "included": sum(
                        c["direction"] == direction
                        and c["requested_distance"] == distance
                        for c in plan["evaluation_cases"]
                    ),
                    "excluded": dict(
                        Counter(
                            c["reason"]
                            for c in plan["feasibility_exclusions"]
                            if c["direction"] == direction
                            and c["requested_distance"] == distance
                        )
                    ),
                }
            )
    return result


def effect_fmt(row):
    return fmt(row["mean"]) + (
        f" [{fmt(row['low'])}, {fmt(row['high'])}]" if row["low"] is not None else ""
    )


def accuracy_lines(table):
    lines = [
        "| Arm | N | Mean final ΔE | Median ΔE | Gain | Mean calls | Converged N |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r['arm']} | {r['n']} | {fmt(r['mean_error'])} | {fmt(r['median_error'])} | {fmt(r['mean_gain'])} | {fmt(r['mean_calls'])} | {r['converged']} |"
        for r in table
    ]
    return lines


def report(result, run_id):
    lines = [
        f"# Sequential magnitude transfer: {run_id}",
        "",
        f"- Parent run: {result['parent_run_id']}",
        f"- Fresh starts: {result['fresh_starts']}; feasible targets: {result['targets']}; exclusions: {result['exclusions']}",
        f"- Generated revisions: {result['generated']} / {result['maximum_generations']} maximum; parsed: {result['parsed']}",
        f"- Common valid terminal triplets: {result['common_triplets']} / {result['targets']}",
        f"- Frozen calibration; no new calibration responses. Stop at displayed ΔE ≤ {result['threshold']:g}; cap {result['max_revisions']} revisions.",
        "- Each response uses a fresh context and displayed uint8 sRGB state. Corrections remain on the original axis; sign can reverse.",
        "",
        "## Completion on all planned games",
        "",
        "| Arm | Planned | Valid terminals | Zero-call stops | Generated | Parsed | Failed | Pending | Unavailable mapping | Converged / planned |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["completion"]:
        lines.append(
            f"| {r['arm']} | {r['planned']} | {r['valid_terminals']} | {r['zero_call_stops']} | {r['generated']} | {r['parsed']} | {r['parse_failures']} | {r['statuses'].get('pending', 0)} | {r['statuses'].get('unavailable_calibration', 0)} | {r['all_planned_converged']} / {r['planned']} |"
        )
    lines += [
        "",
        "Unfinished runs have provisional all-planned success counts. Parse failures do not acquire an imputed endpoint.",
        "",
        "## Primary terminal accuracy and generation cost (common triplets)",
        "",
        *accuracy_lines(result["common_accuracy"]),
        "",
        "## Paired terminal effects (right minus bare)",
        "",
        "Starting-color cluster percentile 95% intervals; costs count saved generated responses, including failed parsing. Convergence differences are proportions.",
        "",
        "| Cohort | Right arm | Measure | Cases | Starts | Difference [95% interval] |",
        "|---|---|---|---:|---:|---:|",
    ]
    for r in result["effects"]:
        lines.append(
            f"| {r['cohort']} | {r['right']} | {r['measure']} | {r['cases']} | {r['starting_colors']} | {effect_fmt(r)} |"
        )
    for p in result["prefixes"]:
        lines += [
            "",
            f"## Observed budget-{p['budget']} prefixes",
            "",
            "Earlier stopped states are retained at no extra cost. A valid prefix survives a later failure; unfinished earlier prefixes are excluded.",
            "",
            *accuracy_lines(p["accuracy"]),
        ]
    lines += [
        "",
        "## Stopping outcomes",
        "",
        "| Arm | Terminal/pending reasons | Valid stop-turn counts |",
        "|---|---|---|",
    ]
    for r in result["completion"]:
        lines.append(f"| {r['arm']} | {r['statuses']} | {r['stop_turn_counts']} |")
    lines += [
        "",
        "## Generated parsed revision diagnostics",
        "",
        "| Arm | Parsed | Harmful | Beyond bound | Reversed sign | Native step | Displayed step | Off-axis drift | Projection ΔE | Projection >1 N |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["diagnostics"]:
        lines.append(
            f"| {r['arm']} | {r['parsed_revisions']} | {r['harmful_revisions']} | {r['beyond_improvement_bound']} | {r['reversed_direction_revisions']} | {fmt(r['native_requested_signed_step'])} | {fmt(r['displayed_requested_signed_step'])} | {fmt(r['displayed_off_axis_drift'])} | {fmt(r['projection_mean'])} | {r['projection_over_1']} |"
        )
    lines += [
        "",
        "Steps follow each revision's requested direction. The Euclidean improvement bound is 2 d cos(theta). No output projection error filters responses.",
        "",
        "## Token cost",
        "",
        "| Arm | Known prompt tokens (records) | Known output tokens (records) | Mean prompt / output | Emitted axis corrections |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in result["diagnostics"]:
        lines.append(
            f"| {r['arm']} | {r['total_known_prompt_tokens']} ({r['known_prompt_token_records']}) | {r['total_known_output_tokens']} ({r['known_output_token_records']}) | {fmt(r['mean_prompt_tokens'])} / {fmt(r['mean_output_tokens'])} | {r['emitted_axis_corrections']} |"
        )
    n = result["numeric_execution"]
    lines += [
        "",
        "## Numeric execution tails",
        "",
        f"- Parsed numeric revisions: {n['parsed']}; native error ≤0.01: {n['within_0_01']}; ≤1: {n['within_1']}; >1: {n['above_1']}.",
        f"- Mean / median / p95 / max native error: {fmt(n['mean'])} / {fmt(n['median'])} / {fmt(n['p95'])} / {fmt(n['max'])}.",
        "- Expected coordinates, every miss above 0.01, raw prompts/responses, and generation diagnostics are retained in metrics/transfer_analysis.json.",
        "",
        "## Exploratory direction/distance breakdown (common terminal cohort)",
        "",
        "| Group | N | Bare ΔE | Calibrated ΔE | Numeric ΔE | Calibrated − bare [95% interval] | Median paired Δ | Wins / ties / losses |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in result["subgroups"]:
        a = {x["arm"]: x for x in r["arms"]}
        lines.append(
            f"| {r['label']} | {r['effect']['cases']} | {fmt(a['bare']['mean_error'])} | {fmt(a['calibrated']['mean_error'])} | {fmt(a['numeric']['mean_error'])} | {effect_fmt(r['effect'])} | {fmt(r['median_difference'])} | {r['wins']} / {r['ties']} / {r['losses']} |"
        )
    lines += [
        "",
        "## Per-start and leave-one-start-out means",
        "",
        "| Start | HEX | N | Calibrated − bare | Mean after omitting start |",
        "|---|---|---:|---:|---:|",
    ]
    for r in result["per_start"]:
        lines.append(
            f"| {r['base_id']} | {r['hex']} | {r['n']} | {fmt(r['mean_difference'])} | {fmt(r['leave_one_start_out_mean'])} |"
        )
    lines += [
        "",
        "## Frozen target feasibility",
        "",
        "| Direction | Units | Included / planned | Exclusions |",
        "|---|---:|---:|---|",
    ]
    for r in result["coverage"]:
        lines.append(
            f"| {r['direction']} | {r['distance']} | {r['included']} / {r['planned']} | {r['excluded']} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "This is target-known stopping with supplied colors, one model and prompt, and a small fixed RGB-range sample. It is not model-only stopping, human perceptual calibration or downstream creative editing. Exact numeric instructions add precision and coordinate holds. The original axis is fixed; off_axis_residual is a valid nonconverged ending, not a repaired color. Failed parsing and unavailable mappings remain in all-planned completion counts; common terminal and prefix cohorts exclude failures separately, with available-pair sensitivity. No terminal error is imputed from a failed/pending prefix. Backend execution errors remain pending and may consume work not counted as saved responses. Cluster intervals resample whole starting colors with pooled case weights, condition on observed valid endpoints, and do not remove failure-selection bias, capture generation randomness or establish population generalization. Subgroups and 0.01 win/tie tolerance are exploratory, without multiplicity adjustment. Leave-one-start-out means are descriptive, not grounds to remove colors. Full prefix contrasts, numeric tails, failure prompts, endpoint reasons and costs remain in the JSON. No evaluation output refits the frozen mapping, replaces starts or alters prompts.",
    ]
    return "\n".join(lines) + "\n"
