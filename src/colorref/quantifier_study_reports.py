"""CPU-only summaries and paired comparisons for the matched quantifier study."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean

from colorref.quantifiers import pairwise_monotonicity


def _number(value: object) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.3f}"


def _mean(rows: list[dict], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return mean(values) if values else None


def _rate(rows: list[dict], field: str, predicate) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return mean(float(predicate(value)) for value in values) if values else None


def _valid(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["parse_ok"]]


def _paired_rows(rows: list[dict], variants: list[str]) -> list[dict]:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["pair_key"], {})[row["prompt_variant"]] = row
    pairs = []
    fields = (
        "requested_signed_step",
        "direction_followed",
        "off_axis_drift",
        "lab_projection_delta_e",
        "control_error_delta_e",
        "projected_requested_signed_step",
        "projected_direction_followed",
    )
    for pair_key, values in grouped.items():
        if not all(variant in values for variant in variants):
            continue
        left, right = (values[variant] for variant in variants)
        pair = {
            "pair_key": pair_key,
            "base_id": left["base_id"],
            "direction": left["direction"],
            "condition_kind": left["condition_kind"],
            "condition_name": left["condition_name"],
            "left_parse_ok": left["parse_ok"],
            "right_parse_ok": right["parse_ok"],
            "both_parsed": bool(left["parse_ok"] and right["parse_ok"]),
        }
        for field in fields:
            for label, row in (("left", left), ("right", right)):
                pair[f"{label}_{field}"] = row.get(field)
            pair[f"delta_{field}"] = (
                float(right[field]) - float(left[field])
                if pair["both_parsed"]
                and left.get(field) is not None
                and right.get(field) is not None
                else None
            )
        pairs.append(pair)
    return pairs


def write_study_reports(
    rows: list[dict], conditions: list[dict], cfg: dict, run_dir: Path
) -> None:
    """Only parsed observations enter movement means; pairing is by condition."""
    reports = run_dir / "reports"
    metrics = run_dir / "metrics"
    reports.mkdir(exist_ok=True)
    metrics.mkdir(exist_ok=True)
    variants = [item["id"] for item in cfg["study"]["prompt_variants"]]
    paired = _paired_rows(rows, variants)
    condition_names = (
        list(cfg["study"]["quantifiers"])
        + [f"numeric_{float(step):g}" for step in cfg["study"]["numeric_steps"]]
        + ["no_change"]
    )
    lines = [
        f"# Matched quantifier study: {run_dir.name}",
        "",
        f"- Completed: {len(rows)} / {len(conditions)}",
        f"- Parsed: {sum(bool(row['parse_ok']) for row in rows)} / {len(rows)}",
        f"- Matched completed pairs: {len(paired)} / {len(conditions) // 2}",
        "- Each response is generated in a fresh context.",
        "- Movement statistics use parsed responses; failed parsing remains in counts.",
        "- Statistics are descriptive for these fixed anchors, not population confidence intervals.",
        "",
        "## Paired prompt comparison",
        "",
        f"Deltas are {variants[1]} minus {variants[0]} on identical starting colors and instructions.",
        "Only pairs with both outputs parsed enter metric deltas.",
        "",
        "| Condition | Completed pairs | Both parsed | Δ signed step | Δ native direction-follow rate | Δ off-axis drift | Δ projection error | Δ control error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in condition_names:
        subset = [row for row in paired if row["condition_name"] == name]
        parsed = [row for row in subset if row["both_parsed"]]
        columns = [
            _number(_mean(parsed, f"delta_{field}"))
            for field in (
                "requested_signed_step",
                "direction_followed",
                "off_axis_drift",
                "lab_projection_delta_e",
                "control_error_delta_e",
            )
        ]
        lines.append(
            f"| {name} | {len(subset)} | {len(parsed)} | " + " | ".join(columns) + " |"
        )
    lines += [
        "",
        "Control error is distance from the exact specified target, not a color-name target.",
        "No-change has no requested direction. No-change movement is its control error.",
    ]
    for variant in variants:
        completed = [row for row in rows if row["prompt_variant"] == variant]
        planned = [row for row in conditions if row["prompt_variant"] == variant]
        parsed = _valid(completed)
        wording = [row for row in completed if row["condition_kind"] == "wording"]
        monotonicity = pairwise_monotonicity(wording)
        lines += [
            "",
            f"## Prompt: {variant}",
            "",
            f"- Completed: {len(completed)} / {len(planned)}; parsed: {len(parsed)} / {len(completed)}",
            f"- Nondecreasing quantifier pairs: {monotonicity['monotonicity_ordered_pairs']} / {monotonicity['monotonicity_comparisons']}",
            f"- Strictly increasing pairs: {monotonicity['monotonicity_strict_pairs']} / {monotonicity['monotonicity_comparisons']}",
            f"- Tied pairs: {monotonicity['monotonicity_tied_pairs']}",
            "The bare instruction is excluded from ordinal scoring.",
            "",
            "| Wording | Completed | Parsed | Mean signed step | Median signed step | Native follow rate | Projected follow rate | Off-axis drift | Mean projection ΔE | Projection > 1 rate | Mean headroom fraction |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name in cfg["study"]["quantifiers"]:
            group = [row for row in wording if row["condition_name"] == name]
            valid = _valid(group)
            steps = sorted(float(row["requested_signed_step"]) for row in valid)
            median = None
            if steps:
                middle = len(steps) // 2
                median = (
                    steps[middle]
                    if len(steps) % 2
                    else (steps[middle - 1] + steps[middle]) / 2
                )
            columns = [
                _number(_mean(valid, "requested_signed_step")),
                _number(median),
                _number(_mean(valid, "direction_followed")),
                _number(_mean(valid, "projected_direction_followed")),
                _number(_mean(valid, "off_axis_drift")),
                _number(_mean(valid, "lab_projection_delta_e")),
                _number(
                    _rate(valid, "lab_projection_delta_e", lambda value: value > 1)
                ),
                _number(_mean(valid, "numeric_headroom_fraction")),
            ]
            lines.append(
                f"| {name} | {len(group)} | {len(valid)} | "
                + " | ".join(columns)
                + " |"
            )
        lines += [
            "",
            "### Exact numeric and no-change controls",
            "",
            "| Control | Completed | Parsed | Mean target error ΔE | Error ≤ 0.01 rate | Error ≤ 1 rate | Mean signed step ratio | Mean projected target error ΔE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name in condition_names:
            if name in cfg["study"]["quantifiers"]:
                continue
            group = [row for row in completed if row["condition_name"] == name]
            valid = _valid(group)
            columns = [
                _number(_mean(valid, "control_error_delta_e")),
                _number(_mean(valid, "control_exact_within_0_01")),
                _number(_mean(valid, "control_within_1")),
                _number(_mean(valid, "numeric_step_ratio")),
                _number(_mean(valid, "projected_control_error_delta_e")),
            ]
            lines.append(
                f"| {name} | {len(group)} | {len(valid)} | "
                + " | ".join(columns)
                + " |"
            )
        lines += [
            "",
            "### Wording by requested direction",
            "",
            "| Direction | Wording | Parsed | Mean signed step | Wrong-sign N | Zero-step N | Mean projection ΔE |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for direction in cfg["study"]["directions"]:
            for name in cfg["study"]["quantifiers"]:
                valid = [
                    row
                    for row in parsed
                    if row["direction"] == direction and row["quantifier"] == name
                ]
                steps = [float(row["requested_signed_step"]) for row in valid]
                lines.append(
                    f"| {direction} | {name} | {len(valid)} | {_number(_mean(valid, 'requested_signed_step'))}"
                    f" | {sum(x < 0 for x in steps)} | {sum(x == 0 for x in steps)}"
                    f" | {_number(_mean(valid, 'lab_projection_delta_e'))} |"
                )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "The axis legend is a prompting intervention; it does not prove unaided perceptual understanding.",
        "Numeric controls explicitly name a coordinate and require other coordinates to stay fixed.",
        "Native LAB and projected sRGB behavior are reported separately; model outputs are not filtered by projection error.",
        "Numeric headroom uses the prompt bounds and is not distance to the sRGB gamut boundary.",
        "All trial prompts, raw responses, expected control targets, and metrics remain in raw_outputs/responses.jsonl.",
    ]
    (reports / "study_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if paired:
        with (metrics / "paired_trials.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(paired[0]))
            writer.writeheader()
            writer.writerows(paired)
