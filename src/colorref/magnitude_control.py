"""Frozen single-axis calibration and held-out targets; no model imports."""

from __future__ import annotations

import math
import random
from statistics import median

from colorref.colors import color_distance_lab, lab_to_rgb, rgb_to_hex
from colorref.interface_study import color_from_hex, parse_response
from colorref.quantifier_study import plan_digest
from colorref.quantifiers import DIRECTION_SPECS, make_instruction, measure_update

WORDINGS = ("baseline", "a_little", "somewhat", "much")
ARMS = ("bare", "calibrated", "numeric")


def prompt(template, base, instruction):
    return template.format(
        base_lab="LAB({:.6f}, {:.6f}, {:.6f})".format(*base["lab"]),
        instruction=instruction,
    )


def validate_config(cfg):
    study = cfg["study"]
    for key in ("calibration_colors", "evaluation_colors"):
        if type(study[key]) is not int or study[key] < 1:
            raise ValueError("Split sizes must be positive integers")
    low, high = study["rgb_channel_range"]
    if type(low) is not int or type(high) is not int or not 0 <= low < high <= 255:
        raise ValueError("Invalid fixed RGB candidate range")
    if (high - low + 1) ** 3 < sum(
        study[k] for k in ("calibration_colors", "evaluation_colors")
    ) + len(study["exclude_hex"]) + len(study["exclude_lab"]):
        raise ValueError("Candidate pool is too small")
    for key in ("convergence_delta_e", "max_target_projection_delta_e"):
        if not math.isfinite(study[key]) or study[key] <= 0:
            raise ValueError("Thresholds must be finite and positive")
    distances = study["target_steps"]
    if (
        not distances
        or len(set(distances)) != len(distances)
        or any(
            not math.isfinite(d) or d <= study["convergence_delta_e"] for d in distances
        )
    ):
        raise ValueError("Unique target steps must exceed the stopping threshold")
    if cfg["analysis"]["resamples"] < 100:
        raise ValueError("At least 100 cluster resamples are required")
    if cfg["model"]["max_tokens"] <= 0 or cfg["model"]["temperature"] < 0:
        raise ValueError("Invalid generation parameters")
    if not cfg["experiment_name"] or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in cfg["experiment_name"]
    ):
        raise ValueError("Unsafe experiment name")


def build_plan(cfg, template):
    """Choose splits independently of feasibility/outputs, then freeze all targets."""
    validate_config(cfg)
    study = cfg["study"]
    excluded = {color_from_hex(h)["hex"] for h in study["exclude_hex"]}
    excluded.update(rgb_to_hex(*lab_to_rgb(*lab)) for lab in study["exclude_lab"])
    rng = random.Random(cfg["seed"])
    low, high = study["rgb_channel_range"]
    splits = {"calibration": [], "evaluation": []}
    seen = set(excluded)
    draws = 0
    rejected = []
    for split, count in (
        ("calibration", study["calibration_colors"]),
        ("evaluation", study["evaluation_colors"]),
    ):
        while len(splits[split]) < count:
            draws += 1
            if draws > 100000:
                raise ValueError("Could not choose unique candidate colors")
            value = rgb_to_hex(*(rng.randint(low, high) for _ in range(3)))
            if value in seen:
                rejected.append(
                    {"draw": draws, "hex": value, "reason": "excluded_or_duplicate"}
                )
                continue
            seen.add(value)
            splits[split].append(
                {
                    "base_id": f"{split}_{len(splits[split]):02d}",
                    "state": color_from_hex(value),
                }
            )
    tasks = []
    for base in splits["calibration"]:
        for direction in DIRECTION_SPECS:
            for wording in WORDINGS:
                instruction = make_instruction(wording, direction)
                tasks.append(
                    {
                        "condition_id": f"{base['base_id']}:{direction}:{wording}",
                        "phase": "calibration",
                        "base_id": base["base_id"],
                        "start": base["state"],
                        "direction": direction,
                        "wording": wording,
                        "instruction": instruction,
                        "constraint_count": 1,
                        "prompt": prompt(template, base["state"], instruction),
                    }
                )
    rng.shuffle(tasks)
    cases, exclusions = build_targets(splits["evaluation"], study)
    rng.shuffle(cases)
    return {
        "schema_version": 1,
        "template": template,
        "splits": splits,
        "excluded_hex": sorted(excluded),
        "candidate_rejections": rejected,
        "calibration_tasks": tasks,
        "evaluation_cases": cases,
        "feasibility_exclusions": exclusions,
    }


def build_targets(starts, study):
    """Freeze target feasibility independently of generated responses."""
    cases, exclusions = [], []
    for base in starts:
        for direction, d in DIRECTION_SPECS.items():
            for distance in study["target_steps"]:
                candidate = base["state"]["lab"].copy()
                candidate[d.index] += d.sign * distance
                key = f"{base['base_id']}:{direction}:{distance:g}"
                common = {
                    "case_id": key,
                    "base_id": base["base_id"],
                    "start": base["state"],
                    "direction": direction,
                    "requested_distance": distance,
                    "candidate_lab": candidate,
                }
                if not 0 <= candidate[0] <= 100 or any(
                    not -128 <= x <= 127 for x in candidate[1:]
                ):
                    exclusions.append(
                        {**common, "reason": "candidate_outside_prompt_bounds"}
                    )
                    continue
                target = color_from_hex(rgb_to_hex(*lab_to_rgb(*candidate)))
                projection = color_distance_lab(candidate, target["lab"])
                residual = d.sign * (
                    target["lab"][d.index] - base["state"]["lab"][d.index]
                )
                if projection > study["max_target_projection_delta_e"] or residual <= 0:
                    exclusions.append(
                        {
                            **common,
                            "reason": "target_projection_or_direction",
                            "projection_delta_e": projection,
                        }
                    )
                    continue
                initial = color_distance_lab(base["state"]["lab"], target["lab"])
                cases.append(
                    {
                        **common,
                        "target": target,
                        "target_projection_delta_e": projection,
                        "axis_residual": residual,
                        "starting_error_delta_e": initial,
                        "initially_converged": initial <= study["convergence_delta_e"],
                    }
                )
    return cases, exclusions


def score(task, text):
    row = {**task, "raw_response": text, **parse_response(text, "lab")}
    if not row["parse_ok"]:
        row["metrics"] = None
        return row
    start = task["start"]["lab"]
    native, displayed = row["native_lab"], row["displayed_state"]["lab"]
    native_start = [round(x, 6) for x in start]
    metrics = {
        f"{prefix}_{key}": value
        for prefix, state, base in (
            ("native", native, native_start),
            ("displayed", displayed, start),
        )
        for key, value in measure_update(
            tuple(base), tuple(state), task["direction"]
        ).items()
    }
    if task["phase"] == "evaluation":
        target = task["target"]["lab"]
        ideal = [t - s for t, s in zip(target, start)]
        update = [t - s for t, s in zip(displayed, start)]
        initial = task["starting_error_delta_e"]
        movement = metrics["displayed_movement_norm"]
        alignment = (
            max(
                -1.0,
                min(
                    1.0,
                    sum(x * y for x, y in zip(ideal, update)) / (initial * movement),
                ),
            )
            if initial > 0 and movement > 1e-12
            else None
        )
        error = color_distance_lab(displayed, target)
        metrics.update(
            {
                "projected_target_error": error,
                "native_target_error": color_distance_lab(native, target),
                "gain": initial - error,
                "alignment": alignment,
                "movement_distance_ratio": movement / initial if initial else None,
                "improvement_step_bound": 2 * initial * alignment
                if alignment is not None
                else None,
                "converged": error <= task["convergence_delta_e"],
            }
        )
        expected = task.get("expected_numeric_lab")
        if expected is not None:
            expected_display = color_from_hex(rgb_to_hex(*lab_to_rgb(*expected)))
            metrics.update(
                {
                    "numeric_native_execution_error": color_distance_lab(
                        native, expected
                    ),
                    "numeric_display_execution_error": color_distance_lab(
                        displayed, expected_display["lab"]
                    ),
                    "numeric_expected_projection_delta_e": color_distance_lab(
                        expected, expected_display["lab"]
                    ),
                    "numeric_expected_target_disagreement": color_distance_lab(
                        expected_display["lab"], target
                    ),
                }
            )
    row["metrics"] = metrics
    return row


def fit_mapping(cfg, plan, calibration):
    """Only after all calibration outputs (including failures) are checkpointed."""
    tasks = plan["calibration_tasks"]
    if set(calibration) != {t["condition_id"] for t in tasks}:
        raise ValueError("Complete calibration is required before fitting")
    table = {}
    for direction in DIRECTION_SPECS:
        table[direction] = []
        for wording in WORDINGS:
            rows = [
                calibration[t["condition_id"]]
                for t in tasks
                if t["direction"] == direction and t["wording"] == wording
            ]
            parsed = [r for r in rows if r["parse_ok"]]
            steps = [r["metrics"]["displayed_requested_signed_step"] for r in parsed]
            value = median(steps) if steps else None
            table[direction].append(
                {
                    "wording": wording,
                    "planned": len(rows),
                    "parsed": len(parsed),
                    "nonpositive": sum(x <= 0 for x in steps),
                    "displayed_median_step": value,
                    "native_median_step": median(
                        r["metrics"]["native_requested_signed_step"] for r in parsed
                    )
                    if parsed
                    else None,
                    "usable": wording != "baseline" and value is not None and value > 0,
                }
            )
    return {
        "table": table,
        "model_prompt_sha256": plan_digest(
            [cfg["model"], {"template": plan["template"], "precision_decimals": 6}]
        ),
        "calibration_outputs_sha256": plan_digest(
            [calibration[t["condition_id"]] for t in tasks]
        ),
        "tie_rule": "absolute distance, smaller median, a_little then somewhat then much",
    }


def choose_phrase(mapping, direction, residual):
    candidates = [x for x in mapping["table"][direction] if x["usable"]]
    return (
        min(
            candidates,
            key=lambda x: (
                abs(x["displayed_median_step"] - residual),
                x["displayed_median_step"],
                WORDINGS.index(x["wording"]),
            ),
        )
        if candidates
        else None
    )


def evaluation_tasks(cfg, plan, mapping):
    tasks = []
    for case in plan["evaluation_cases"]:
        choice = choose_phrase(mapping, case["direction"], case["axis_residual"])
        d = DIRECTION_SPECS[case["direction"]]
        for arm in ARMS:
            expected = None
            instruction, status, selected = None, "generate", None
            if case["initially_converged"]:
                status = "assigned_threshold_stop"
            elif arm == "calibrated" and choice is None:
                status = "unavailable_calibration"
            elif arm == "numeric":
                expected = [round(x, 6) for x in case["start"]["lab"]]
                step = round(
                    abs(round(case["target"]["lab"][d.index], 6) - expected[d.index]), 6
                )
                expected[d.index] = round(expected[d.index] + d.sign * step, 6)
                instruction = f"{'Increase' if d.sign > 0 else 'Decrease'} the {('L', 'a', 'b')[d.index]} coordinate by exactly {step:.6f} units. Leave the other coordinates unchanged."
            else:
                selected = choice["wording"] if arm == "calibrated" else "baseline"
                instruction = make_instruction(selected, case["direction"])
            tasks.append(
                {
                    **case,
                    "condition_id": f"{case['case_id']}:{arm}",
                    "phase": "evaluation",
                    "arm": arm,
                    "status": status,
                    "selected_wording": selected,
                    "calibrated_median": choice["displayed_median_step"]
                    if arm == "calibrated" and choice
                    else None,
                    "instruction": instruction,
                    "constraint_count": 1 if instruction else 0,
                    "holds_other_coordinates": arm == "numeric",
                    "expected_numeric_lab": expected,
                    "convergence_delta_e": cfg["study"]["convergence_delta_e"],
                    "prompt": prompt(plan["template"], case["start"], instruction)
                    if instruction
                    else None,
                }
            )
    return tasks
