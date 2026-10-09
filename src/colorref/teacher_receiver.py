"""Matched one-revision reception of frozen teacher messages, without inference."""

from __future__ import annotations

import copy
import random
from collections import Counter
from statistics import mean

import numpy as np

from colorref.interface_study import score_record
from colorref.quantifier_study import plan_digest
from colorref.shared_start_study import supplied_start
from colorref.teacher_fidelity import (
    CONDITIONS,
    build_plan as teacher_plan,
    score as teacher_score,
)

ARMS = (*CONDITIONS, "oracle")


def validate_snapshot(snapshot):
    cfg, plan, metadata = (snapshot[k] for k in ("config", "plan", "metadata"))
    parent = snapshot["parent_snapshot"]
    if (
        metadata.get("schema_version") != 1
        or metadata.get("study_kind") != "oracle_assisted_teacher_fidelity"
        or metadata["config_sha256"] != plan_digest([cfg])
        or metadata["plan_sha256"] != plan_digest([plan])
        or metadata["parent_snapshot_sha256"] != plan_digest([parent])
        or metadata["required_model_revision"]
        != parent["metadata"].get("resolved_model_revision")
        or teacher_plan(cfg, parent, plan["templates"]) != plan
    ):
        raise ValueError("Teacher snapshot failed integrity validation")
    rows = snapshot["rows"]
    if set(rows) != {t["condition_id"] for t in plan["tasks"]}:
        raise ValueError(
            "Require every planned teacher response, including empty outputs"
        )
    for task in plan["tasks"]:
        row = rows[task["condition_id"]]
        expected = teacher_score(task, row["raw_response"])
        if row["run_id"] != metadata["run_id"] or any(
            row.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("Frozen teacher response failed reproduction")


def study_config(snapshot, name, output_root=None):
    parent = snapshot["parent_snapshot"]["config"]
    model = copy.deepcopy(parent["model"])
    model["alias"] = model.get("alias", "guesser") + "_teacher_receiver"
    return {
        "experiment_name": name,
        "seed": 61,
        "model": model,
        "output": {"run_root": str(output_root or parent["output"]["run_root"])},
        "execution": {
            "convergence_delta_e": parent["execution"]["convergence_delta_e"]
        },
        "analysis": copy.deepcopy(snapshot["config"]["analysis"]),
    }


def build_plan(cfg, snapshot):
    validate_snapshot(snapshot)
    if cfg != study_config(snapshot, cfg["experiment_name"], cfg["output"]["run_root"]):
        raise ValueError(
            "Receiver configuration differs from declared inherited protocol"
        )
    template = snapshot["parent_snapshot"]["plan"]["templates"]["hex"]["revision"]
    groups = {}
    for task in snapshot["plan"]["tasks"]:
        groups.setdefault(task["case_id"], {})[task["condition"]] = task
    tasks, rng = [], random.Random(cfg["seed"])
    for case_id, group in groups.items():
        if set(group) != set(CONDITIONS):
            raise ValueError("Teacher case must have all four conditions")
        base = group[CONDITIONS[0]]
        for t in group.values():
            if any(
                t[k] != base[k]
                for k in ("example", "required", "bandwidth", "oracle_feedback")
            ):
                raise ValueError(
                    "Teacher conditions have mismatched starts or supplied constraints"
                )
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            source = group[arm]["condition_id"] if arm != "oracle" else None
            text = (
                snapshot["rows"][source]["raw_response"]
                if source
                else base["oracle_feedback"]
            )
            example = copy.deepcopy(base["example"])
            prompt = template.format(
                raw_name=example["raw_name"],
                previous_guess=example["shared_start_hex"],
                feedback=text,
            )
            tasks.append(
                {
                    "slot": len(tasks),
                    "condition_id": case_id + ":" + arm,
                    "case_id": case_id,
                    "arm": arm,
                    "example_id": base["example_id"],
                    "regime": base["regime"],
                    "bandwidth": base["bandwidth"],
                    "example": example,
                    "variant": "hex",
                    "output_space": "hex",
                    "required": copy.deepcopy(base["required"]),
                    "feedback_text": text,
                    "teacher_condition_id": source,
                    "prompt": prompt,
                    "teacher_empty": not text.strip(),
                    "teacher_mentions_target_hex": example["hex"].lower()
                    in text.lower(),
                }
            )
    return {
        "parent_run_id": snapshot["metadata"]["run_id"],
        "template": template,
        "tasks": tasks,
    }


def score(task, text, cfg):
    start = supplied_start(task)
    # This measures movement against supplied oracle constraints, not a lexical
    # guess about what the teacher's wording means.
    feedback = {
        "text": task["feedback_text"],
        "metadata": {"all_constraints": task["required"]},
    }
    record = score_record(task, [start], task["prompt"], feedback, text)
    error = record["projected_error_delta_e"]
    initial = start["projected_error_delta_e"]
    return {
        **task,
        "record": record,
        "metrics": {
            "starting_error": initial,
            "error": error,
            "gain": initial - error if error is not None else None,
            "converged": error <= cfg["execution"]["convergence_delta_e"]
            if error is not None
            else None,
            "initially_converged": initial <= cfg["execution"]["convergence_delta_e"],
            "oracle_constraint_satisfaction": record["constraint_satisfaction"],
            "alignment": record["directional_alignment"],
        },
    }


def average(values):
    usable = [v for v in values if v is not None]
    return mean(usable) if usable else None


def paired(tasks, rows, left, right, cfg):
    groups = {}
    for task in tasks:
        groups.setdefault(task["case_id"], {})[task["arm"]] = task
    values = {}
    for group in groups.values():
        a, b = (rows.get(group[arm]["condition_id"]) for arm in (left, right))
        if not a or not b or not a["record"]["parse_ok"] or not b["record"]["parse_ok"]:
            continue
        delta = b["metrics"]["error"] - a["metrics"]["error"]
        values.setdefault(a["regime"], {}).setdefault(a["example_id"], []).append(delta)
    count = sum(len(v) for g in values.values() for v in g.values())
    clusters = sum(len(g) for g in values.values())
    difference = (
        sum(sum(v) for g in values.values() for v in g.values()) / count
        if count
        else None
    )
    interval = None
    if clusters >= 2:
        rng = np.random.default_rng(cfg["analysis"]["seed"])
        sums = np.zeros(cfg["analysis"]["resamples"])
        sizes = np.zeros_like(sums)
        for group in values.values():
            entries = list(group.values())
            draw = rng.integers(len(entries), size=(len(sums), len(entries)))
            sums += np.array([sum(v) for v in entries])[draw].sum(axis=1)
            sizes += np.array([len(v) for v in entries])[draw].sum(axis=1)
        interval = np.quantile(sums / sizes, [0.025, 0.975]).tolist()
    return {
        "left": left,
        "right": right,
        "cases": count,
        "examples": clusters,
        "difference": difference,
        "interval": interval,
    }


def analyze(cfg, plan, rows):
    grouped = {}
    for task in plan["tasks"]:
        grouped.setdefault(task["case_id"], {})[task["arm"]] = task
    common = {
        case
        for case, group in grouped.items()
        if all(
            t["condition_id"] in rows and rows[t["condition_id"]]["record"]["parse_ok"]
            for t in group.values()
        )
    }
    primary, completion, by_budget = [], [], []
    for arm in ARMS:
        tasks = [t for t in plan["tasks"] if t["arm"] == arm]
        available = [
            rows[t["condition_id"]] for t in tasks if t["condition_id"] in rows
        ]
        parsed = [r for r in available if r["record"]["parse_ok"]]
        completion.append(
            {
                "arm": arm,
                "planned": len(tasks),
                "completed": len(available),
                "parsed": len(parsed),
                "failed": len(available) - len(parsed),
                "pending": len(tasks) - len(available),
                "converged_all_planned": sum(r["metrics"]["converged"] for r in parsed),
                "empty_teacher_messages": sum(t["teacher_empty"] for t in tasks),
                "teacher_mentions_target_hex": sum(
                    t["teacher_mentions_target_hex"] for t in tasks
                ),
                "mean_error_available": average(r["metrics"]["error"] for r in parsed),
                "mean_prompt_tokens": average(
                    r.get("prompt_tokens") for r in available
                ),
                "mean_output_tokens": average(
                    r["generation"]["generated_tokens"] for r in available
                ),
            }
        )
        selected = [r for r in parsed if r["case_id"] in common]
        primary.append(summarize(arm, selected))
        for budget in (1, 3):
            by_budget.append(
                {
                    "bandwidth": budget,
                    **summarize(arm, [r for r in selected if r["bandwidth"] == budget]),
                }
            )
    contrasts = [(arm, "oracle") for arm in CONDITIONS] + [
        ("natural_0", "natural_4"),
        ("restricted_0", "restricted_4"),
        ("natural_0", "restricted_0"),
        ("natural_4", "restricted_4"),
    ]
    effects = []
    for cohort, tasks in [
        ("common_quintets", [t for t in plan["tasks"] if t["case_id"] in common]),
        ("available_pairs", plan["tasks"]),
    ]:
        for left, right in contrasts:
            effects.append({"cohort": cohort, **paired(tasks, rows, left, right, cfg)})
    return {
        "planned": len(plan["tasks"]),
        "completed": len(rows),
        "common_cases": len(common),
        "common_examples": len(
            {t["example_id"] for t in plan["tasks"] if t["case_id"] in common}
        ),
        "completion": completion,
        "primary": primary,
        "effects": effects,
        "by_budget": by_budget,
        "failures": [r for r in rows.values() if not r["record"]["parse_ok"]],
        "close_start_drift": [
            r for r in rows.values() if r["metrics"]["initially_converged"]
        ],
        "input_counts_by_regime": dict(
            Counter(t["regime"] for t in plan["tasks"] if t["arm"] == "oracle")
        ),
    }


def summarize(arm, rows):
    return {
        "arm": arm,
        "n": len(rows),
        **{
            key: average(r["metrics"][key] for r in rows)
            for key in (
                "starting_error",
                "error",
                "gain",
                "oracle_constraint_satisfaction",
                "alignment",
            )
        },
        "alignment_n": sum(r["metrics"]["alignment"] is not None for r in rows),
        "converged": sum(r["metrics"]["converged"] for r in rows),
        "projection_error": average(r["record"]["projection_delta_e"] for r in rows),
    }


def fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def report(result, cfg, plan, run_id):
    lines = [
        f"# Matched teacher-feedback reception: {run_id}",
        "",
        f"- Parent teacher run: {plan['parent_run_id']}",
        f"- Completed revisions: {result['completed']} / {result['planned']}; common parsed cases: {result['common_cases']}.",
        f"- Common examples: {result['common_examples']}; c1/c3 stay together during resampling.",
        f"- Guesser: {cfg['model']['model_name']} via {cfg['model']['provider']}; output budget {cfg['model']['max_tokens']} tokens.",
        "- Every case has five arms with identical supplied HEX starts and one fresh-context revision.",
        "- Original teacher text is passed unchanged. No target coordinates, constraint JSON or review labels are appended to the guesser prompt.",
        "",
        "## Completion",
        "",
        "| Arm | Completed / planned | Parsed | Failed | Pending | Converged / planned | Empty teacher inputs | Teacher target-HEX mentions | Prompt / output tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in result["completion"]:
        lines.append(
            f"| {s['arm']} | {s['completed']} / {s['planned']} | {s['parsed']} | {s['failed']} | {s['pending']} | {s['converged_all_planned']} / {s['planned']} | {s['empty_teacher_messages']} | {s['teacher_mentions_target_hex']} | {fmt(s['mean_prompt_tokens'])} / {fmt(s['mean_output_tokens'])} |"
        )
    lines.extend(
        [
            "",
            "## Accuracy on common parsed quintets",
            "",
            "| Arm | N | Starting ΔE | Revised ΔE | Gain | Oracle constraint satisfaction | Alignment (N) | Converged N |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for s in result["primary"]:
        lines.append(
            f"| {s['arm']} | {s['n']} | {fmt(s['starting_error'])} | {fmt(s['error'])} | {fmt(s['gain'])} | {fmt(s['oracle_constraint_satisfaction'])} | {fmt(s['alignment'])} ({s['alignment_n']}) | {s['converged']} |"
        )
    lines.extend(
        [
            "",
            "## Paired error effects",
            "",
            "Right minus left; negative favors right. Percentile 95% intervals resample whole examples within regimes.",
            "",
            "| Cohort | Left → right | Cases | Examples | Δ error [95% interval] |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for s in result["effects"]:
        interval = (
            " [" + ", ".join(fmt(v) for v in s["interval"]) + "]"
            if s["interval"]
            else ""
        )
        lines.append(
            f"| {s['cohort']} | {s['left']} → {s['right']} | {s['cases']} | {s['examples']} | {fmt(s['difference'])}{interval} |"
        )
    lines.extend(
        [
            "",
            "## Exploratory bandwidth breakdown (same common cohort)",
            "",
            "| Budget | Arm | N | Revised ΔE | Gain |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for s in result["by_budget"]:
        lines.append(
            f"| {s['bandwidth']} | {s['arm']} | {s['n']} | {fmt(s['error'])} | {fmt(s['gain'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "This evaluates one supplied-start revision with oracle-assisted messages from the same model family, not unaided teacher geometry or full interactive games. Canonical feedback costs no teacher generation; the earlier teacher and start-generation costs are excluded from these revision counts. All parent teacher outputs must be completed before planning, including empty text; none is repaired or selected by semantic audit labels. Teacher-authored target HEX mentions are flagged but not filtered. All arms use HEX outputs, so parsed native and displayed LAB coincide and projection error is zero. Constraint satisfaction uses the supplied oracle directions, not inferred teacher intent. Fixed revisions include close starts; their drift records and all failed prompts/responses remain in metrics/receiver_analysis.json. Empty or malformed guesser outputs complete a failed response, never receive an imputed color or retry; backend exceptions remain pending. Accuracy excludes parse failures through explicitly matched cohorts and available-pair sensitivity. Pooled intervals retain whole examples, both bandwidths and observed regime counts; singleton strata have no resampling variation and a one-example cohort has no interval. Intervals condition on observed parsed outputs, do not remove failure-selection bias or establish generation-randomness uncertainty, population generalization, independent human judgments or multiplicity-adjusted significance. Frozen teacher snapshots and new response checkpoints retain provenance.",
        ]
    )
    return "\n".join(lines) + "\n"
