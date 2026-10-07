"""Export saved calibrated endings and numeric misses; never run inference."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.magnitude_transfer import endpoint  # noqa: E402
from run_magnitude_transfer import (  # noqa: E402
    load_checkpoints,
    load_plan,
    run_lock,
    write_json,
)


def inspect(cfg, plan, checkpoints, metadata):
    endings = {
        game["condition_id"]: endpoint(
            game, checkpoints.get(game["condition_id"], []), cfg, plan
        )
        for game in plan["games"]
    }
    cases = {}
    for end in endings.values():
        cases.setdefault(end["case_id"], {})[end["arm"]] = end
    nonconverged, misses = [], []
    for game in plan["games"]:
        rows = checkpoints.get(game["condition_id"], [])
        end = endings[game["condition_id"]]
        if (
            game["arm"] == "calibrated"
            and end["status"] != "pending"
            and not end["converged"]
        ):
            nonconverged.append(
                {
                    **end,
                    "start": game["start"],
                    "target": game["target"],
                    "initial_error": game["starting_error_delta_e"],
                    "matched_endpoints": cases[game["case_id"]],
                    "revisions": rows,
                }
            )
        if game["arm"] == "numeric":
            for row in rows:
                if not row["parse_ok"]:
                    continue
                error = row["metrics"]["numeric_native_execution_error"]
                if error <= 0.01:
                    continue
                misses.append(
                    {
                        "game": end,
                        "revision": row,
                        "revisions": rows,
                        "coordinate_residual": [
                            a - e
                            for a, e in zip(
                                row["native_lab"], row["expected_numeric_lab"]
                            )
                        ],
                    }
                )
    misses.sort(
        key=lambda item: item["revision"]["metrics"]["numeric_native_execution_error"],
        reverse=True,
    )
    return {
        "run_id": metadata["run_id"],
        "config_sha256": metadata["config_sha256"],
        "plan_sha256": metadata["plan_sha256"],
        "parent_snapshot_sha256": metadata["parent_snapshot_sha256"],
        "planned_games": len(plan["games"]),
        "generated": sum(len(rows) for rows in checkpoints.values()),
        "parsed": sum(row["parse_ok"] for rows in checkpoints.values() for row in rows),
        "completion": {
            arm: dict(Counter(e["status"] for e in endings.values() if e["arm"] == arm))
            for arm in ("bare", "calibrated", "numeric")
        },
        "numeric_miss_tolerance": 0.01,
        "calibrated_nonconverged": nonconverged,
        "numeric_misses": misses,
    }


def number(value):
    return "n/a" if value is None else f"{value:.3f}"


def report(result):
    lines = [
        f"# Saved magnitude-transfer inspection: {result['run_id']}",
        "",
        f"- Planned games: {result['planned_games']}; saved revisions: "
        f"{result['generated']}; parsed: {result['parsed']}.",
        f"- Completed calibrated nonconverged endings: "
        f"{len(result['calibrated_nonconverged'])}.",
        f"- Parsed numeric revisions with native execution error > 0.01: "
        f"{len(result['numeric_misses'])}.",
        "- CPU export only; no new responses or calibration fitting.",
        "",
        "## Completion by arm",
        "",
        "| Arm | Endpoint status counts |",
        "|---|---|",
    ]
    for arm, counts in result["completion"].items():
        lines.append(f"| {arm} | {counts} |")
    lines.extend(["", "## Calibrated nonconverged endings", ""])
    for end in result["calibrated_nonconverged"]:
        lines.extend(
            [
                f"### {end['condition_id']}",
                "",
                f"Status: {end['status']}; valid endpoint: {end['valid']}; "
                f"calls: {end['calls']}; final displayed error: {number(end['error'])}.",
                f"Start LAB: {end['start']['lab']}; target LAB: {end['target']['lab']}.",
                "",
                "Matched final errors / calls: "
                + "; ".join(
                    f"{arm}: {number(e['error'])} / {e['calls']} ({e['status']})"
                    for arm, e in end["matched_endpoints"].items()
                ),
                "",
                "Displayed error trace: "
                + " → ".join(
                    [number(end["initial_error"])]
                    + [
                        number(r["metrics"]["projected_target_error"])
                        if r["parse_ok"]
                        else "parse failure"
                        for r in end["revisions"]
                    ]
                ),
                "",
                "| Turn | Direction | Wording | Median | Native step | Displayed step | Off-axis drift | Projection ΔE |",
                "|---|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for r in end["revisions"]:
            m = r["metrics"] or {}
            lines.append(
                f"| {r['turn']} | {r['direction']} | {r['selected_wording']} | "
                f"{number(r['calibrated_median'])} | "
                f"{number(m.get('native_requested_signed_step'))} | "
                f"{number(m.get('displayed_requested_signed_step'))} | "
                f"{number(m.get('displayed_off_axis_drift'))} | "
                f"{number(r.get('projection_delta_e'))} |"
            )
        for r in end["revisions"]:
            lines.extend(
                [
                    "",
                    f"Turn {r['turn']} response (parse: {r['parse_ok']}):",
                    "",
                    "```text",
                    r["raw_response"],
                    "```",
                ]
            )
    if not result["calibrated_nonconverged"]:
        lines.append("None among completed games. Check pending counts above.")
    lines.extend(["", "## Numeric execution misses", ""])
    for item in result["numeric_misses"]:
        r, end = item["revision"], item["game"]
        lines.extend(
            [
                f"### {end['condition_id']}, revision {r['turn']}",
                "",
                f"Native execution error: {number(r['metrics']['numeric_native_execution_error'])}.",
                f"Expected LAB: {r['expected_numeric_lab']}; actual LAB: {r['native_lab']}.",
                f"Coordinate residual: {item['coordinate_residual']}.",
                f"Final game status: {end['status']}; calls: {end['calls']}; "
                f"final displayed error: {number(end['error'])}.",
                "Saved displayed error trace: "
                + " → ".join(
                    number(saved["metrics"]["projected_target_error"])
                    if saved["parse_ok"]
                    else "parse failure"
                    for saved in item["revisions"]
                ),
                f"Generation diagnostics: {r.get('generation', 'unknown')}.",
                "",
                "```text",
                r["prompt"],
                "Response: " + r["raw_response"],
                "```",
                "",
            ]
        )
    if not result["numeric_misses"]:
        lines.append("None among saved parsed revisions. Check pending counts above.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Pending games are not nonconverged endings. Failed or unavailable "
            "endpoints retain n/a error; saved earlier errors are not imputed as "
            "terminal errors. Numeric mistakes remain visible after later "
            "oracle-assisted recovery. The 0.01 cutoff is an execution diagnostic, "
            "not the stopping threshold. These traces do not identify an internal "
            "reasoning mechanism. Full validated revision records, prompts and "
            "input digests are in metrics/transfer_inspection.json. Original "
            "primary reports, checkpoints and frozen inputs are preserved.",
            "",
        ]
    )
    return "\n".join(lines)


def execute(directory):
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        checkpoints = load_checkpoints(directory, cfg, plan, metadata)
        result = inspect(cfg, plan, checkpoints, metadata)
        write_json(directory / "metrics/transfer_inspection.json", result)
        (directory / "reports/transfer_inspection.md").write_text(report(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.run)
    print(
        f"Exported {len(result['calibrated_nonconverged'])} calibrated endings "
        f"and {len(result['numeric_misses'])} numeric misses.\n"
        f"Report: {args.run / 'reports/transfer_inspection.md'}\n"
        f"JSON: {args.run / 'metrics/transfer_inspection.json'}"
    )


if __name__ == "__main__":
    main()
