"""Matched displayable-color reference games, independent of inference backends."""

from __future__ import annotations

import math
import random
from dataclasses import asdict

from colorref.colors import (
    color_distance_lab,
    hex_to_rgb,
    lab_to_rgb,
    normalize_hex,
    rgb_to_hex,
    rgb_to_hsv,
    rgb_to_lab,
)
from colorref.parsing import extract_hex, extract_lab
from colorref.teachers import AxisOracle

REGIMES = (
    "explicit_grounded",
    "prototype_mediated",
    "compound_associative",
    "abstract_idiosyncratic",
)
VARIANTS = {"hex": "hex", "lab_plain": "lab", "lab_axis_legend": "lab"}


def validate_config(cfg: dict, templates: dict) -> None:
    variants = cfg["study"]["variants"]
    if {x["id"]: x["output_space"] for x in variants} != VARIANTS or len(variants) != 3:
        raise ValueError("Require exactly HEX, plain LAB, and LAB axis-legend variants")
    if set(templates) != set(VARIANTS) or any(
        set(value) != {"initial", "revision"} for value in templates.values()
    ):
        raise ValueError("Every variant needs frozen initial and revision prompts")
    for variant, value in templates.items():
        value["initial"].format(raw_name="test")
        value["revision"].format(
            raw_name="test", previous_guess="test", feedback="test"
        )
        if not all(isinstance(x, str) and x.strip() for x in value.values()):
            raise ValueError(f"Empty template for {variant}")
    n = cfg["study"]["examples_per_regime"]
    turns = cfg["execution"]["max_turns"]
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError("examples_per_regime must be a positive integer")
    if isinstance(turns, bool) or not isinstance(turns, int) or turns <= 0:
        raise ValueError("max_turns must be a positive integer")
    threshold = float(cfg["execution"]["convergence_delta_e"])
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("convergence_delta_e must be positive and finite")
    teacher = cfg["teacher"]
    if teacher["type"] != "axis_oracle" or teacher["max_feedback_constraints"] != 3:
        raise ValueError(
            "This study uses the deterministic three-constraint axis oracle"
        )
    if set(teacher["min_delta"]) != {"lab_l", "lab_a", "lab_b", "hsv_s"} or any(
        not math.isfinite(float(x)) or float(x) <= 0
        for x in teacher["min_delta"].values()
    ):
        raise ValueError("Require positive finite thresholds for all four oracle axes")
    model = cfg["model"]
    if model["temperature"] != 0 or model.get("enable_thinking") is not False:
        raise ValueError(
            "The matched study requires temperature 0 and thinking disabled"
        )
    if int(model["max_tokens"]) <= 0:
        raise ValueError("max_tokens must be positive")


def select_examples(frame, per_regime: int, seed: int) -> list[dict]:
    """Require exact quotas; sample from stable ID order without silent shortfalls."""
    required = {"example_id", "raw_name", "hex", "regime_label"}
    if not required.issubset(frame.columns):
        raise ValueError(
            f"Missing dataset columns: {sorted(required - set(frame.columns))}"
        )
    if frame["example_id"].isna().any() or frame["example_id"].duplicated().any():
        raise ValueError("Dataset example IDs must be present and unique")
    selected = []
    for regime in REGIMES:
        pool = frame[frame["regime_label"] == regime].sort_values("example_id")
        if len(pool) < per_regime:
            raise ValueError(f"{regime}: need {per_regime} examples, found {len(pool)}")
        for row in pool.sample(n=per_regime, random_state=seed).to_dict("records"):
            identifier = str(row["example_id"])
            name = row["raw_name"]
            color = normalize_hex(row["hex"])
            if not isinstance(name, str) or not name.strip() or color is None:
                raise ValueError(f"Invalid description or target HEX for {identifier}")
            selected.append(
                {
                    "example_id": identifier,
                    "raw_name": name,
                    "hex": color,
                    "regime_label": regime,
                }
            )
    if len({x["example_id"] for x in selected}) != len(selected):
        raise ValueError("Example IDs collide after string normalization")
    return selected


def build_tasks(cfg: dict, examples: list[dict]) -> list[dict]:
    n = cfg["study"]["examples_per_regime"]
    if len(examples) != 4 * n or any(
        sum(x["regime_label"] == regime for x in examples) != n for regime in REGIMES
    ):
        raise ValueError("Frozen examples do not meet the four regime quotas")
    if len({x["example_id"] for x in examples}) != len(examples):
        raise ValueError("Duplicate example IDs")
    rng = random.Random(cfg["seed"])
    ordered = list(examples)
    rng.shuffle(ordered)
    tasks = []
    for example in ordered:
        variants = list(VARIANTS)
        rng.shuffle(variants)
        for variant in variants:
            tasks.append(
                {
                    "slot": len(tasks),
                    "condition_id": f"{variant}:{example['example_id']}",
                    "variant": variant,
                    "output_space": VARIANTS[variant],
                    "example": example,
                }
            )
    return tasks


def color_from_hex(value: str) -> dict:
    rgb = hex_to_rgb(value)
    return {
        "hex": rgb_to_hex(*rgb),
        "rgb": list(rgb),
        "lab": list(rgb_to_lab(*rgb)),
        "hsv": list(rgb_to_hsv(*rgb)),
    }


def parse_response(text: str, output_space: str) -> dict:
    """Retain native coordinates, but normalize every usable state through uint8 sRGB."""
    if output_space == "hex":
        value, meta = extract_hex(text)
        state = color_from_hex(value) if value else None
        native = state["lab"] if state else None
    elif output_space == "lab":
        native, meta = extract_lab(text)
        state = color_from_hex(rgb_to_hex(*lab_to_rgb(*native))) if native else None
    else:
        raise ValueError(f"Unsupported output space: {output_space}")
    return {
        "parse_ok": state is not None,
        "parse_reason": meta["reason"],
        "native_lab": list(native) if native is not None else None,
        "displayed_state": state,
        "projection_delta_e": color_distance_lab(native, state["lab"])
        if state
        else None,
    }


def is_complete(records: list[dict], max_turns: int) -> bool:
    return bool(records) and (
        not records[-1]["parse_ok"] or len(records) == max_turns + 1
    )


def next_prompt(
    task: dict, records: list[dict], cfg: dict, templates: dict
) -> tuple[str, dict | None]:
    template = templates[task["variant"]]
    example = task["example"]
    if not records:
        return template["initial"].format(raw_name=example["raw_name"]), None
    if is_complete(records, cfg["execution"]["max_turns"]):
        raise ValueError("Completed game has no next prompt")
    state = records[-1]["displayed_state"]
    oracle = AxisOracle(
        max_feedback_constraints=cfg["teacher"]["max_feedback_constraints"],
        min_delta=cfg["teacher"]["min_delta"],
    )
    feedback = asdict(
        oracle.give_feedback(
            color_from_hex(example["hex"]), state, example, len(records) - 1
        )
    )
    previous = (
        state["hex"]
        if task["output_space"] == "hex"
        else "LAB({:.6f}, {:.6f}, {:.6f})".format(*state["lab"])
    )
    return template["revision"].format(
        raw_name=example["raw_name"], previous_guess=previous, feedback=feedback["text"]
    ), feedback


def score_record(
    task: dict, records: list[dict], prompt: str, feedback: dict | None, text: str
) -> dict:
    parsed = parse_response(text, task["output_space"])
    target = color_from_hex(task["example"]["hex"])
    state = parsed["displayed_state"]
    constraints = feedback["metadata"].get("all_constraints", []) if feedback else []
    satisfaction = None
    alignment = None
    if state and records:
        prior_lab = records[-1]["displayed_state"]["lab"]
        update = [x - p for x, p in zip(state["lab"], prior_lab)]
        ideal = [x - p for x, p in zip(target["lab"], prior_lab)]
        denominator = math.sqrt(sum(x * x for x in update) * sum(x * x for x in ideal))
        if denominator > 1e-12:
            alignment = max(
                -1.0, min(1.0, sum(x * y for x, y in zip(update, ideal)) / denominator)
            )
    if state and constraints:
        keys = {
            "lab_l": ("lab", 0),
            "lab_a": ("lab", 1),
            "lab_b": ("lab", 2),
            "hsv_s": ("hsv", 1),
        }
        prior = records[-1]["displayed_state"]
        satisfaction = sum(
            (
                state[keys[c["axis"]][0]][keys[c["axis"]][1]]
                - prior[keys[c["axis"]][0]][keys[c["axis"]][1]]
            )
            * c["sign"]
            > 1e-8
            for c in constraints
        ) / len(constraints)
    return {
        "turn": len(records),
        "prompt": prompt,
        "feedback": feedback,
        "raw_response": text,
        **parsed,
        "native_error_delta_e": color_distance_lab(target["lab"], parsed["native_lab"])
        if state
        else None,
        "projected_error_delta_e": color_distance_lab(target["lab"], state["lab"])
        if state
        else None,
        "constraint_satisfaction": satisfaction,
        "directional_alignment": alignment,
        "constraint_count": len(constraints),
    }


def validate_checkpoint(
    task: dict, records: list[dict], cfg: dict, templates: dict
) -> None:
    """Rebuild prompts, feedback, parsing, and scores; reject incompatible checkpoints."""
    prior = []
    for row in records:
        prompt, feedback = next_prompt(task, prior, cfg, templates)
        expected = score_record(task, prior, prompt, feedback, row["raw_response"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(
                f"Checkpoint does not match frozen game: {task['condition_id']}"
            )
        prior.append(row)
