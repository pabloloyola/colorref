"""Frozen-controller sequential transfer; no inference or evaluation fitting."""

from __future__ import annotations

import copy
import random

from colorref.colors import color_distance_lab, rgb_to_hex
from colorref.interface_study import color_from_hex
from colorref.magnitude_control import (
    ARMS,
    build_plan as build_parent_plan,
    build_targets,
    evaluation_tasks,
    evaluation_arms,
    fit_mapping,
    score,
)
from colorref.quantifier_study import plan_digest
from colorref.quantifiers import DIRECTION_SPECS

VALID_TERMINALS = {"threshold_stop", "budget_exhausted", "off_axis_residual"}


def validate_parent(snapshot):
    """Reproduce the calibration-only map and all frozen parent task scores."""
    cfg, plan, meta = snapshot["config"], snapshot["plan"], snapshot["metadata"]
    if evaluation_arms(cfg) != ARMS:
        raise ValueError("Sequential transfer currently supports the three-arm pilot; four-arm transfer requires its own protocol")
    if (
        meta.get("schema_version") != 1
        or meta["config_sha256"] != plan_digest([cfg])
        or meta["plan_sha256"] != plan_digest([plan])
        or build_parent_plan(cfg, plan["template"]) != plan
    ):
        raise ValueError("Parent magnitude plan failed validation")
    rows = snapshot["calibration"]
    if set(rows) != {t["condition_id"] for t in plan["calibration_tasks"]}:
        raise ValueError("Parent calibration is incomplete")
    for task in plan["calibration_tasks"]:
        row = rows[task["condition_id"]]
        expected = score(task, row["raw_response"])
        if row.get("run_id") != meta["run_id"] or any(
            row.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("Parent calibration checkpoint failed validation")
    mapping = fit_mapping(cfg, plan, rows)
    bundle = {
        "mapping": mapping,
        "evaluation_tasks": evaluation_tasks(cfg, plan, mapping),
    }
    if snapshot["controller"] != bundle:
        raise ValueError("Parent controller does not reproduce from calibration")
    expected_generated = sum(
        t["status"] == "generate" for t in bundle["evaluation_tasks"]
    )
    if snapshot["evaluation_completed"] != expected_generated:
        raise ValueError("Complete the parent evaluation before transfer")


def transfer_config(
    snapshot, experiment_name="magnitude_transfer_a100_40gb", output_root=None
):
    validate_parent(snapshot)
    parent = snapshot["config"]
    study = copy.deepcopy(parent["study"])
    study.pop("calibration_colors")
    study["evaluation_colors"] = 12
    study["exclude_hex"] = sorted(
        set(snapshot["plan"]["excluded_hex"])
        | {
            c["state"]["hex"]
            for split in snapshot["plan"]["splits"].values()
            for c in split
        }
    )
    return {
        "experiment_name": experiment_name,
        "seed": 47,
        "model": copy.deepcopy(parent["model"]),
        "study": study,
        "execution": {"max_revisions": 5, "axis_residual_tolerance": 0.01},
        "analysis": copy.deepcopy(parent["analysis"]),
        "output": {
            "run_root": str(output_root)
            if output_root is not None
            else parent["output"]["run_root"]
        },
    }


def build_plan(cfg, snapshot):
    validate_parent(snapshot)
    # Transfer choices are declared, not exposed as evaluation-tuning overrides.
    expected = transfer_config(
        snapshot, cfg["experiment_name"], cfg["output"]["run_root"]
    )
    if (
        cfg != expected
        or not cfg["experiment_name"]
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in cfg["experiment_name"]
        )
    ):
        raise ValueError("Transfer settings differ from the declared protocol")
    rng = random.Random(cfg["seed"])
    excluded = set(cfg["study"]["exclude_hex"])
    seen = set(excluded)
    low, high = cfg["study"]["rgb_channel_range"]
    starts, rejections = [], []
    for draw in range(1, 100001):
        value = rgb_to_hex(*(rng.randint(low, high) for _ in range(3)))
        if value in seen:
            rejections.append(
                {"draw": draw, "hex": value, "reason": "excluded_or_duplicate"}
            )
            continue
        seen.add(value)
        starts.append(
            {"base_id": f"transfer_{len(starts):02d}", "state": color_from_hex(value)}
        )
        if len(starts) == cfg["study"]["evaluation_colors"]:
            break
    else:
        raise ValueError("Could not select fresh transfer colors")
    cases, exclusions = build_targets(starts, cfg["study"])
    rng.shuffle(cases)
    games = [
        {**case, "arm": arm, "condition_id": f"{case['case_id']}:{arm}", "slot": slot}
        for slot, (case, arm) in enumerate((c, a) for c in cases for a in ARMS)
    ]
    return {
        "schema_version": 1,
        "study_kind": "sequential_magnitude_transfer",
        "parent_run_id": snapshot["metadata"]["run_id"],
        "parent_snapshot_sha256": plan_digest([snapshot]),
        "template": snapshot["plan"]["template"],
        "mapping": copy.deepcopy(snapshot["controller"]["mapping"]),
        "required_model_revision": snapshot["metadata"].get("resolved_model_revision"),
        "starts": starts,
        "candidate_rejections": rejections,
        "evaluation_cases": cases,
        "feasibility_exclusions": exclusions,
        "games": games,
    }


def next_revision(game, records, cfg, plan):
    """Terminal reason or a scored-task input for precisely one fresh context."""
    if records and not records[-1]["parse_ok"]:
        return "parse_failure", None
    state = records[-1]["displayed_state"] if records else game["start"]
    error = color_distance_lab(state["lab"], game["target"]["lab"])
    if error <= cfg["study"]["convergence_delta_e"]:
        return "threshold_stop", None
    if len(records) >= cfg["execution"]["max_revisions"]:
        return "budget_exhausted", None
    index = DIRECTION_SPECS[game["direction"]].index
    residual = game["target"]["lab"][index] - state["lab"][index]
    if abs(residual) <= cfg["execution"]["axis_residual_tolerance"]:
        return "off_axis_residual", None
    direction = next(
        d.name
        for d in DIRECTION_SPECS.values()
        if d.index == index and d.sign == (1 if residual > 0 else -1)
    )
    case = {
        **game,
        "start": state,
        "direction": direction,
        "axis_residual": abs(residual),
        "starting_error_delta_e": error,
        "initially_converged": False,
    }
    task = next(
        t
        for t in evaluation_tasks(
            cfg,
            {"evaluation_cases": [case], "template": plan["template"]},
            plan["mapping"],
        )
        if t["arm"] == game["arm"]
    )
    if task["status"] != "generate":
        return "unavailable_calibration", None
    task.update(
        {
            "condition_id": f"{game['condition_id']}:revision_{len(records) + 1}",
            "game_id": game["condition_id"],
            "turn": len(records) + 1,
            "original_direction": game["direction"],
        }
    )
    return None, task


def validate_records(game, records, cfg, plan, run_id):
    if not isinstance(records, list):
        raise ValueError("Transfer records must be a revision list")
    prefix = []
    for row in records:
        reason, task = next_revision(game, prefix, cfg, plan)
        if reason is not None:
            raise ValueError("Transfer checkpoint continues after a terminal state")
        expected = score(task, row["raw_response"])
        if row.get("run_id") != run_id or any(
            row.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("Transfer checkpoint differs from frozen task/score")
        prefix.append(row)


def endpoint(game, records, cfg, plan, budget=None):
    """A budget prefix remains available even if a later revision fails."""
    selected = records if budget is None else records[:budget]
    reason, _ = next_revision(game, selected, cfg, plan)
    if (
        budget is not None
        and len(selected) == budget
        and selected[-1]["parse_ok"]
        and reason in (None, "unavailable_calibration")
    ):
        # Future policy availability cannot invalidate a completed budget prefix.
        reason = "prefix"
    elif reason is None:
        reason = "pending"
    valid = reason in VALID_TERMINALS or reason == "prefix"
    state = (
        selected[-1]["displayed_state"]
        if selected and selected[-1]["parse_ok"]
        else game["start"]
    )
    error = color_distance_lab(state["lab"], game["target"]["lab"]) if valid else None
    return {
        "condition_id": game["condition_id"],
        "case_id": game["case_id"],
        "base_id": game["base_id"],
        "arm": game["arm"],
        "direction": game["direction"],
        "distance": game["requested_distance"],
        "status": reason,
        "valid": valid,
        "calls": len(selected),
        "zero_call_stop": reason == "threshold_stop" and not selected,
        "error": error,
        "gain": game["starting_error_delta_e"] - error if valid else None,
        "converged": error is not None and error <= cfg["study"]["convergence_delta_e"],
    }
