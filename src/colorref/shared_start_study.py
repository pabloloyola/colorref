"""Shared displayed-state revisions; supplied starts are not generated responses."""

from __future__ import annotations

from colorref.colors import color_distance_lab, normalize_hex
from colorref.interface_study import (
    build_tasks,
    color_from_hex,
    next_prompt,
    score_record,
    validate_config,
)
from colorref.quantifier_study import plan_digest


def freeze_inputs(cfg, parent_plan, parent_metadata, checkpoints):
    """Use every parent HEX start, regardless of failures in other interfaces."""
    starts = {}
    provenance = {}
    for task in parent_plan["tasks"]:
        if task["variant"] != "hex":
            continue
        records = checkpoints.get(task["slot"], [])
        if not records or not records[0]["parse_ok"]:
            raise ValueError(f"Missing parsed parent HEX start: {task['condition_id']}")
        identifier = task["example"]["example_id"]
        if identifier in starts:
            raise ValueError("Duplicate parent HEX example")
        starts[identifier] = records[0]["displayed_state"]["hex"]
        provenance[identifier] = {
            "condition_id": task["condition_id"],
            "turn": 0,
            "record_sha256": plan_digest([records[0]]),
        }
    examples = []
    for example in parent_plan["examples"]:
        identifier = example["example_id"]
        if identifier not in starts:
            raise ValueError(f"No parent HEX start for example {identifier}")
        examples.append(
            {
                **example,
                "shared_start_hex": starts[identifier],
                "shared_start_state": color_from_hex(starts[identifier]),
                "parent_start": provenance[identifier],
            }
        )
    plan = {
        "templates": parent_plan["templates"],
        "examples": examples,
        "tasks": build_tasks(cfg, examples),
        "parent": {
            "run_id": parent_metadata["run_id"],
            "plan_sha256": parent_metadata["plan_sha256"],
            "config_sha256": parent_metadata["config_sha256"],
            "start_policy": "parent_hex_turn_0_displayed_state",
        },
    }
    validate_plan(cfg, plan)
    return plan


def supplied_start(task):
    """Synthetic turn zero is kept in the plan, never in response checkpoints."""
    example = task["example"]
    state = color_from_hex(example["shared_start_hex"])
    error = color_distance_lab(color_from_hex(example["hex"])["lab"], state["lab"])
    return {
        "record_kind": "supplied_start",
        "turn": 0,
        "parse_ok": True,
        "parse_reason": None,
        "raw_response": None,
        "prompt": None,
        "feedback": None,
        "native_lab": state["lab"],
        "displayed_state": state,
        "projection_delta_e": 0.0,
        "native_error_delta_e": error,
        "projected_error_delta_e": error,
        "constraint_satisfaction": None,
        "directional_alignment": None,
        "constraint_count": 0,
    }


def validate_plan(cfg, plan):
    validate_config(cfg, plan["templates"])
    if build_tasks(cfg, plan["examples"]) != plan["tasks"]:
        raise ValueError("Frozen shared-start examples do not match tasks")
    for example in plan["examples"]:
        value = example["shared_start_hex"]
        if (
            normalize_hex(value) != value
            or color_from_hex(value) != example["shared_start_state"]
        ):
            raise ValueError("Invalid frozen displayed starting state")
    grouped = {}
    for task in plan["tasks"]:
        seed = supplied_start(task)
        _, feedback = next_prompt(task, [seed], cfg, plan["templates"])
        grouped.setdefault(task["example"]["example_id"], []).append((seed, feedback))
    for observations in grouped.values():
        if any(value != observations[0] for value in observations[1:]):
            raise ValueError(
                "Shared starts or first oracle feedback differ across interfaces"
            )


def is_complete(records, turns):
    return bool(records) and (not records[-1]["parse_ok"] or len(records) == turns)


def revision_prompt(task, records, cfg, templates):
    if is_complete(records, cfg["execution"]["max_turns"]):
        raise ValueError("Completed shared-start game has no next revision")
    return next_prompt(task, [supplied_start(task), *records], cfg, templates)


def revision_record(task, records, prompt, feedback, text):
    return {
        **score_record(task, [supplied_start(task), *records], prompt, feedback, text),
        "record_kind": "generated_revision",
    }


def validate_checkpoint(task, records, cfg, templates):
    prior = []
    for row in records:
        prompt, feedback = revision_prompt(task, prior, cfg, templates)
        expected = revision_record(task, prior, prompt, feedback, row["raw_response"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(
                f"Checkpoint does not match shared-start game: {task['condition_id']}"
            )
        prior.append(row)


def generation_diagnostics(response):
    """Save only backend-observed fields; absence remains explicitly unknown."""
    raw = getattr(response, "raw", None) or {}
    choices = raw.get("choices") or []
    usage = raw.get("usage") or {}
    return {
        "generated_tokens": raw.get("generated_tokens", usage.get("completion_tokens")),
        "finish_reason": raw.get(
            "finish_reason", choices[0].get("finish_reason") if choices else None
        ),
        "finish_reason_source": raw.get(
            "finish_reason_source", "backend_reported" if choices else None
        ),
        "eos_reached": raw.get("eos_reached"),
        "token_limit_reached": raw.get("token_limit_reached"),
    }
