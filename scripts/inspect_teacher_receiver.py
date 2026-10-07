"""CPU-only message-equivalence and information-budget audit of saved revisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.teacher_fidelity import CONDITIONS  # noqa: E402
from run_interface_study import run_lock, write_json  # noqa: E402
from run_teacher_receiver_study import load_plan, load_rows  # noqa: E402


def inspect(cfg, plan, rows, snapshot):
    cases = {}
    for task in plan["tasks"]:
        cases.setdefault(task["case_id"], {})[task["arm"]] = task
    observations = []
    for case_id, group in cases.items():
        oracle_task = group["oracle"]
        oracle = rows.get(oracle_task["condition_id"])
        for arm in CONDITIONS:
            task = group[arm]
            response = rows.get(task["condition_id"])
            teacher = snapshot["rows"][task["teacher_condition_id"]]
            metrics = teacher["metrics"]
            additions = metrics["additions"]
            valid = {c["direction"] for c in teacher["all_candidates"]}
            paired = bool(response and oracle and response["record"]["parse_ok"] and oracle["record"]["parse_ok"])
            tags = ["all", "identical_feedback" if task["feedback_text"] == oracle_task["feedback_text"] else "different_feedback"]
            if metrics["keyword_set_equal"]:
                tags.append("lexical_set_equal")
            if additions:
                tags.extend(["lexical_additions", "additions_all_threshold_valid" if set(additions) <= valid else "additions_not_all_threshold_valid"])
            observations.append({
                "case_id": case_id, "condition_id": task["condition_id"], "arm": arm,
                "example_id": task["example_id"], "regime": task["regime"], "bandwidth": task["bandwidth"],
                "tags": tags, "paired_parsed": paired,
                "teacher_feedback": task["feedback_text"], "oracle_feedback": oracle_task["feedback_text"],
                "identical_prompts": task["prompt"] == oracle_task["prompt"],
                "teacher_lexical_additions": additions,
                "threshold_valid_directions": sorted(valid),
                "teacher_lexical_metrics": metrics,
                "arm_error": response["metrics"]["error"] if paired else None,
                "oracle_error": oracle["metrics"]["error"] if paired else None,
                "error_difference": response["metrics"]["error"] - oracle["metrics"]["error"] if paired else None,
                "arm_raw_response": response["record"]["raw_response"] if response else None,
                "oracle_raw_response": oracle["record"]["raw_response"] if oracle else None,
                "same_raw_response": response["record"]["raw_response"] == oracle["record"]["raw_response"] if response and oracle else None,
                "same_displayed_color": response["record"]["displayed_state"]["hex"] == oracle["record"]["displayed_state"]["hex"] if paired else None,
            })
    summaries = []
    for arm in CONDITIONS:
        for tag in ("all", "identical_feedback", "different_feedback", "lexical_set_equal", "lexical_additions", "additions_all_threshold_valid", "additions_not_all_threshold_valid"):
            selected = [r for r in observations if r["arm"] == arm and tag in r["tags"]]
            parsed = [r for r in selected if r["paired_parsed"]]
            differences = [r["error_difference"] for r in parsed]
            summaries.append({
                "arm": arm, "group": tag, "planned": len(selected), "paired": len(parsed),
                "examples": len({r["example_id"] for r in parsed}),
                "mean_difference": mean(differences) if differences else None,
                "median_difference": median(differences) if differences else None,
                "summed_difference": sum(differences) if differences else None,
                "wins": sum(d < -0.01 for d in differences), "ties": sum(abs(d) <= 0.01 for d in differences),
                "losses": sum(d > 0.01 for d in differences),
                "identical_prompt_different_raw": sum(r["identical_prompts"] and r["same_raw_response"] is False for r in parsed),
                "identical_prompt_different_color": sum(r["identical_prompts"] and r["same_displayed_color"] is False for r in parsed),
            })
    return {"planned_case_pairs": len(observations), "summary": summaries, "pairs": observations}


def fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def report(result):
    lines = [
        "# Saved teacher-receiver message audit", "",
        "Differences are teacher arm minus canonical oracle; negative favors the teacher arm.",
        "Groups overlap except identical/different feedback, which partition every arm's cases.", "",
        "| Arm | Group | Paired / planned | Examples | Mean ΔE difference | Median difference | Sum difference | Wins / ties / losses | Identical-prompt different colors |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for s in result["summary"]:
        lines.append(f"| {s['arm']} | {s['group']} | {s['paired']} / {s['planned']} | {s['examples']} | {fmt(s['mean_difference'])} | {fmt(s['median_difference'])} | {fmt(s['summed_difference'])} | {s['wins']} / {s['ties']} / {s['losses']} | {s['identical_prompt_different_color']} |")
    lines.extend(["", "## Restricted zero-shot messages with lexical additions", ""])
    for row in result["pairs"]:
        if row["arm"] != "restricted_0" or "lexical_additions" not in row["tags"]:
            continue
        lines.extend([
            f"### {row['condition_id']}", "",
            f"Added keywords: {row['teacher_lexical_additions']}; threshold-valid directions: {row['threshold_valid_directions']}.",
            f"Paired parsed: {row['paired_parsed']}; teacher-minus-oracle error: {fmt(row['error_difference'])}.",
            "", "```text", "Teacher: " + row["teacher_feedback"], "Oracle: " + row["oracle_feedback"], "```", "",
        ])
    lines.extend(["## Limits", "", "This is an exploratory audit of already saved outputs, with no inference, prompt repair, case replacement or fitted controller. Group labels come from the frozen lexical audit and are not semantic judgments for natural comparisons. Added primitive directions are checked against all threshold-qualified oracle candidates; threshold validity does not guarantee useful movement, optimal wording or magnitude. Supplied-set fidelity, information budget and target accuracy are distinct. Group sums describe where the observed paired mean originates, not a causal effect of adding information: cases were not randomized to faithful versus unfaithful teacher outputs. Literal text equivalence and actual prompt equivalence are retained separately; identical greedy prompts do not constitute a proof of backend determinism. Wins/ties use an exploratory 0.01 ΔE tolerance. These subgroup summaries have no population intervals, and multiple cases share each starting example. Pending or unparsed endpoints receive no imputed errors. Original primary reports, prompts, plans and checkpoints are preserved. Full pair text, raw responses, score flags and equivalence checks remain in metrics/receiver_message_audit.json."])
    return "\n".join(lines) + "\n"


def inspect_run(directory):
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        rows = load_rows(directory, cfg, plan, metadata)
        snapshot = json.loads((directory / "inputs/parent_snapshot.json").read_text())
        result = inspect(cfg, plan, rows, snapshot)
        write_json(directory / "metrics/receiver_message_audit.json", result)
        (directory / "reports/receiver_message_audit.md").write_text(report(result))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    print(report(inspect_run(args.run)))


if __name__ == "__main__":
    main()
