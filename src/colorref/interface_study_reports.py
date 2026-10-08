"""CPU-only summaries of matched reference games."""

from __future__ import annotations

import csv
import json
from statistics import mean

from colorref.interface_study import REGIMES, VARIANTS, is_complete


def _mean(values):
    values = [x for x in values if x is not None]
    return mean(values) if values else None


def _fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def game_summary(task, records, turns):
    full = len(records) == turns + 1 and all(x["parse_ok"] for x in records)
    initial = records[0] if records and records[0]["parse_ok"] else {}
    final = records[-1] if full else {}
    errors = [x["projected_error_delta_e"] for x in records if x["parse_ok"]]
    return {
        "condition_id": task["condition_id"],
        "example_id": task["example"]["example_id"],
        "regime_label": task["example"]["regime_label"],
        "variant": task["variant"],
        "completed": is_complete(records, turns),
        "full_trajectory": full,
        "responses": len(records),
        "parse_failures": sum(not x["parse_ok"] for x in records),
        "initial_projected_error": initial.get("projected_error_delta_e"),
        "final_projected_error": final.get("projected_error_delta_e"),
        "final_native_error": final.get("native_error_delta_e"),
        "projected_gain": initial["projected_error_delta_e"]
        - final["projected_error_delta_e"]
        if full
        else None,
        "best_projected_error": min(errors) if full else None,
        "final_best_gap": final["projected_error_delta_e"] - min(errors)
        if full
        else None,
        "mean_projection_error": _mean([x["projection_delta_e"] for x in records]),
        "projection_over_1_n": sum(
            x["parse_ok"] and x["projection_delta_e"] > 1 for x in records
        ),
        "mean_constraint_satisfaction": _mean(
            [x["constraint_satisfaction"] for x in records]
        ),
        "mean_directional_alignment": _mean(
            [x["directional_alignment"] for x in records]
        ),
    }


def write_reports(cfg, tasks, checkpoints, run_dir):
    if cfg["study"].get("design") == "grounding_replication":
        return write_grounding_report(cfg, tasks, checkpoints, run_dir)
    turns = cfg["execution"]["max_turns"]
    summaries = [game_summary(t, checkpoints.get(t["slot"], []), turns) for t in tasks]
    grouped = {}
    for row in summaries:
        grouped.setdefault(row["example_id"], {})[row["variant"]] = row
    completed_triplets = [
        x for x in grouped.values() if all(r["completed"] for r in x.values())
    ]
    full_triplets = [
        x for x in grouped.values() if all(r["full_trajectory"] for r in x.values())
    ]
    common_ids = {x["hex"]["example_id"] for x in full_triplets}
    common = [row for row in summaries if row["example_id"] in common_ids]
    comparisons = [
        ("hex", "lab_plain"),
        ("lab_plain", "lab_axis_legend"),
        ("hex", "lab_axis_legend"),
    ]
    pairs = []
    for group in full_triplets:
        for left, right in comparisons:
            a, b = group[left], group[right]
            pairs.append(
                {
                    "example_id": a["example_id"],
                    "regime_label": a["regime_label"],
                    "left": left,
                    "right": right,
                    **{
                        f"delta_{field}": b[field] - a[field]
                        for field in (
                            "initial_projected_error",
                            "final_projected_error",
                            "projected_gain",
                            "final_native_error",
                        )
                    },
                }
            )
    reports, metrics = run_dir / "reports", run_dir / "metrics"
    reports.mkdir(exist_ok=True)
    metrics.mkdir(exist_ok=True)
    (metrics / "games.json").write_text(
        json.dumps(summaries, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    for filename, rows in (("games.csv", summaries), ("paired_deltas.csv", pairs)):
        with (metrics / filename).open("w", encoding="utf-8", newline="") as stream:
            if rows:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    lines = [
        f"# Matched output-interface study: {run_dir.name}",
        "",
        f"- Completed games: {sum(x['completed'] for x in summaries)} / {len(tasks)}",
        f"- Saved responses: {sum(x['responses'] for x in summaries)} / {len(tasks) * (turns + 1)} maximum",
        f"- Parse failures: {sum(x['parse_failures'] for x in summaries)}",
        f"- Completed matched triplets: {len(completed_triplets)} / {len(grouped)}",
        f"- Matched triplets with all {turns + 1} responses parsed: {len(full_triplets)} / {len(grouped)}",
        f"- Model: {cfg['model']['model_name']} via {cfg['model']['provider']}",
        f"- Feedback: deterministic axis_oracle, at most 3 constraints; {turns} fixed rounds.",
        "- Each generation has a fresh context. Only the latest feedback is shown.",
        "- The oracle and next prompt use clipped, rounded uint8 sRGB states in every condition.",
        "- Target LAB is recomputed from target HEX. Projected LAB error is the primary comparison.",
        "",
        "## Completion by interface",
        "",
        "| Interface | Completed | Full parsed trajectories | Parse failures |",
        "|---|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [x for x in summaries if x["variant"] == variant]
        lines.append(
            f"| {variant} | {sum(x['completed'] for x in rows)} / {len(rows)} | {sum(x['full_trajectory'] for x in rows)} | {sum(x['parse_failures'] for x in rows)} |"
        )
    lines += [
        "",
        "## Accuracy on the common matched set",
        "",
        "All means below use only examples with full parsed trajectories under all three interfaces.",
        "",
        "| Interface | N | Initial projected ΔE | Final projected ΔE | Projected gain | Final native ΔE | Final–best gap | Constraint satisfaction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [x for x in common if x["variant"] == variant]
        values = [
            _fmt(_mean([x[k] for x in rows]))
            for k in (
                "initial_projected_error",
                "final_projected_error",
                "projected_gain",
                "final_native_error",
                "final_best_gap",
                "mean_constraint_satisfaction",
            )
        ]
        lines.append(f"| {variant} | {len(rows)} | " + " | ".join(values) + " |")
    lines += [
        "",
        "## Convergence and alignment (common set)",
        "",
        f"Convergence is final projected ΔE ≤ {cfg['execution']['convergence_delta_e']:g}; it does not stop generation. Alignment is cosine similarity between a displayed-state update and the ideal target correction, excluding zero-length vectors.",
        "",
        "| Interface | N | Converged N | Convergence rate | Mean directional alignment |",
        "|---|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [x for x in common if x["variant"] == variant]
        converged = sum(
            x["final_projected_error"] <= cfg["execution"]["convergence_delta_e"]
            for x in rows
        )
        lines.append(
            f"| {variant} | {len(rows)} | {converged} | {_fmt(converged / len(rows) if rows else None)} | {_fmt(_mean([x['mean_directional_alignment'] for x in rows]))} |"
        )
    lines += [
        "",
        "## Paired differences",
        "",
        "Right minus left on the common matched set. Negative error differences favor the right interface; positive gain differences indicate greater correction.",
        "",
        "| Left → right | N | Δ initial projected error | Δ final projected error | Δ projected gain |",
        "|---|---:|---:|---:|---:|",
    ]
    for left, right in comparisons:
        rows = [x for x in pairs if x["left"] == left and x["right"] == right]
        values = [
            _fmt(_mean([x[k] for x in rows]))
            for k in (
                "delta_initial_projected_error",
                "delta_final_projected_error",
                "delta_projected_gain",
            )
        ]
        lines.append(f"| {left} → {right} | {len(rows)} | " + " | ".join(values) + " |")
    lines += [
        "",
        "## Final projected error by regime (common set)",
        "",
        "| Regime | N | HEX | Plain LAB | LAB with legend |",
        "|---|---:|---:|---:|---:|",
    ]
    for regime in REGIMES:
        rows = [x for x in common if x["regime_label"] == regime]
        values = [
            _fmt(_mean([x["final_projected_error"] for x in rows if x["variant"] == v]))
            for v in VARIANTS
        ]
        lines.append(f"| {regime} | {len(rows) // 3} | " + " | ".join(values) + " |")
    lines += [
        "",
        "## Projection diagnostics (all parsed saved states)",
        "",
        "| Interface | Parsed states | Mean projection ΔE | Projection ΔE > 1 N |",
        "|---|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = [
            row
            for task in tasks
            if task["variant"] == variant
            for row in checkpoints.get(task["slot"], [])
            if row["parse_ok"]
        ]
        lines.append(
            f"| {variant} | {len(rows)} | {_fmt(_mean([x['projection_delta_e'] for x in rows]))} | {sum(x['projection_delta_e'] > 1 for x in rows)} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "This is a balanced diagnostic sample, not a reproduction of the paper's full evaluation. Adaptive feedback messages may differ because guesses differ; the policy and thresholds are identical. The axis legend is an instruction intervention. LAB bounds are encoding bounds, not the sRGB gamut. Both clipping and uint8 rounding contribute to projection error. Fixed rounds continue even after a close guess; parse failures terminate that game and remain in completion counts. Accuracy means exclude failed or unfinished matched triplets; inspect denominators before comparing. Constraint satisfaction concerns displayed-state movement and includes HSV saturation. Descriptive paired differences do not establish population significance or resolve ambiguous crowdsourced targets.",
        "",
    ]
    (reports / "interface_summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_grounding_report(cfg, tasks, checkpoints, run_dir):
    """Paired initial/final HEX evidence with failures and timing kept separate."""
    from colorref.interface_analysis import paired_bootstrap

    if any(t["variant"] != "hex" for t in tasks):
        raise ValueError("Grounding report requires HEX-only tasks")
    turns = cfg["execution"]["max_turns"]
    summaries = [game_summary(t, checkpoints.get(t["slot"], []), turns) for t in tasks]
    full = [r for r in summaries if r["full_trajectory"]]
    estimates = paired_bootstrap(
        [[r["initial_projected_error"], r["final_projected_error"], r["projected_gain"]] for r in full],
        [r["regime_label"] for r in full],
        cfg.get("analysis", {}).get("resamples", 5000),
        cfg.get("analysis", {}).get("seed", 13),
    ) if full else []
    latencies = [r["latency_s"] for rows in checkpoints.values() for r in rows
                 if r.get("latency_s") is not None]
    result = {
        "planned": len(tasks), "completed": sum(r["completed"] for r in summaries),
        "full_parsed": len(full), "parse_failures": sum(r["parse_failures"] for r in summaries),
        "saved_responses": sum(r["responses"] for r in summaries),
        "maximum_generations": len(tasks) * (turns + 1),
        "estimates": dict(zip(("initial_error", "final_error", "gain"), estimates)),
        "known_latency_responses": len(latencies), "mean_generation_latency_s": _mean(latencies),
        "games": summaries,
    }
    threshold = cfg["execution"]["convergence_delta_e"]
    result["initial_converged"] = sum(r["initial_projected_error"] <= threshold for r in full)
    result["final_converged"] = sum(r["final_projected_error"] <= threshold for r in full)
    (run_dir / "metrics/grounding_analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    lines = [f"# Fresh grounding replication: {run_dir.name}", "",
             f"- Completed games: {result['completed']} / {len(tasks)}",
             f"- Fully parsed paired initial/final examples: {len(full)} / {len(tasks)}",
             f"- Parse failures: {result['parse_failures']}",
             f"- Saved responses: {result['saved_responses']} / {result['maximum_generations']} maximum",
             f"- Model: {cfg['model']['model_name']} via {cfg['model']['provider']}",
             f"- HEX output; axis oracle with at most three constraints; {turns} fixed revisions.",
             "- Each initial prediction is also the one-shot baseline; no duplicate initial generation.",
             "", "## Paired target error", "",
             "| Quantity | N | Mean | 95% percentile interval |",
             "|---|---:|---:|---|" ]
    for name, e in result["estimates"].items():
        interval = "n/a" if e["low"] is None else f"[{e['low']:.3f}, {e['high']:.3f}]"
        lines.append(f"| {name} | {e['n']} | {_fmt(e['mean'])} | {interval} |")
    lines += ["", f"- Initially/finally converged on the paired cohort: {result['initial_converged']} / {result['final_converged']} (threshold {threshold}).",
              "", "## Regime coverage and outcomes", "",
              "| Regime | Planned | Full parsed | Initial error | Final error | Gain |",
              "|---|---:|---:|---:|---:|---:|"]
    for regime in REGIMES:
        rows = [r for r in full if r["regime_label"] == regime]
        planned = sum(r["regime_label"] == regime for r in summaries)
        cells = [_fmt(_mean([r[k] for r in rows])) for k in ("initial_projected_error", "final_projected_error", "projected_gain")]
        lines.append(f"| {regime} | {planned} | {len(rows)} | " + " | ".join(cells) + " |")
    lines += ["", "## Timing", "",
              f"- Mean saved generation latency: {_fmt(_mean(latencies))} seconds ({len(latencies)} known responses).",
              "Latency excludes model loading, checkpoint/report overhead, and unsaved backend failures. Partial-run estimates are provisional; HEX throughput does not predict longer LAB or teacher generations.",
              "", "## Limits", "",
              "Balanced regime sampling estimates an equal-regime benchmark, not corpus-frequency performance. Intervals resample whole descriptions within regimes and retain paired initial/final states; generations are not independent examples. They do not measure human target agreement, model randomness, or population generalization. Accuracy excludes failed/pending trajectories; completion remains visible. Fixed rounds continue after close guesses. More feedback also provides more information; this alone does not isolate sequential adaptation from a matched information budget. An unfinished run is not final evidence.", ""]
    (run_dir / "reports/grounding_summary.md").write_text("\n".join(lines))
