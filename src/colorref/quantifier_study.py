"""Matched quantifier-study conditions and measurements (no inference imports)."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re

from colorref.colors import color_distance_lab, lab_to_rgb, rgb_to_lab
from colorref.prompts import render_quantifier_calibration
from colorref.quantifiers import (
    DIRECTION_SPECS,
    get_quantifier,
    make_instruction,
    measure_update,
    numerical_headroom,
)

_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _identifier(value: object) -> str:
    result = str(value)
    if not _ID.fullmatch(result):
        raise ValueError(f"Unsafe or empty condition identifier: {result!r}")
    return result


def _lab(value: object) -> tuple[float, float, float]:
    result = tuple(float(x) for x in value)
    if len(result) != 3 or not all(math.isfinite(x) for x in result):
        raise ValueError("Each LAB state must contain three finite coordinates")
    if not 0 <= result[0] <= 100 or not all(-128 <= x <= 127 for x in result[1:]):
        raise ValueError(f"LAB state outside the declared prompt bounds: {result}")
    return result


def projected_lab(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    return rgb_to_lab(*lab_to_rgb(*lab))


def control_target(
    base_lab: tuple[float, float, float], direction: str, step: float
) -> tuple[float, float, float]:
    d = DIRECTION_SPECS[direction]
    target = list(base_lab)
    target[d.index] += d.sign * step
    return _lab(target)


def numeric_instruction(direction: str, step: float) -> str:
    d = DIRECTION_SPECS[direction]
    coordinate = ("L", "a", "b")[d.index]
    verb = "Increase" if d.sign > 0 else "Decrease"
    return f"{verb} the {coordinate} coordinate by exactly {step:g} units. Leave the other coordinates unchanged."


def build_conditions(cfg: dict, templates: dict[str, str]) -> list[dict]:
    """Build paired conditions with frozen rendered prompts and seeded order."""
    if cfg.get("interface", {}).get("output_space") != "lab":
        raise ValueError("The matched study requires native LAB output")
    study = cfg["study"]
    variants = [_identifier(item["id"]) for item in study["prompt_variants"]]
    if len(variants) != 2 or len(set(variants)) != 2 or set(templates) != set(variants):
        raise ValueError(
            "Exactly two distinct prompt variants and their templates are required"
        )
    if not study.get("include_no_change"):
        raise ValueError("The matched study requires a no-change control")
    steps = [float(x) for x in study["numeric_steps"]]
    if (
        not steps
        or len(steps) != len(set(steps))
        or not all(math.isfinite(x) and x > 0 for x in steps)
    ):
        raise ValueError("Numeric steps must be unique, positive finite values")
    directions = list(study["directions"])
    if len(set(directions)) != len(directions) or any(
        x not in DIRECTION_SPECS for x in directions
    ):
        raise ValueError("Directions must be unique supported LAB directions")
    quantifiers = list(study["quantifiers"])
    if len(set(quantifiers)) != len(quantifiers):
        raise ValueError("Quantifiers must be unique")
    for name in quantifiers:
        get_quantifier(name)

    bases = study["base_colors"]
    ids = [_identifier(item["id"]) for item in bases]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Starting colors must have unique IDs")
    threshold = float(study.get("max_control_projection_delta_e", 1.0))
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("Control projection threshold must be positive")

    pairs = []
    for base in bases:
        base_id = _identifier(base["id"])
        base_lab = _lab(base["lab"])
        # The model receives exactly this rounded state; use it for scoring too.
        if any(abs(x - round(x, 2)) > 1e-8 for x in base_lab):
            raise ValueError("Starting coordinates must have at most two decimals")
        if color_distance_lab(base_lab, projected_lab(base_lab)) >= threshold:
            raise ValueError(f"Starting color {base_id} has excessive projection error")
        common = {"base_id": base_id, "base_lab": list(base_lab)}
        for direction in directions:
            for name in quantifiers:
                pairs.append(
                    {
                        **common,
                        "direction": direction,
                        "condition_kind": "wording",
                        "condition_name": name,
                        "quantifier": name,
                        "instruction": make_instruction(name, direction),
                        "expected_lab": None,
                        "requested_numeric_step": None,
                    }
                )
            for step in steps:
                target = control_target(base_lab, direction, step)
                if color_distance_lab(target, projected_lab(target)) >= threshold:
                    raise ValueError(
                        f"Numeric control {base_id}/{direction}/{step:g} has excessive projection error"
                    )
                pairs.append(
                    {
                        **common,
                        "direction": direction,
                        "condition_kind": "numeric",
                        "condition_name": f"numeric_{step:g}",
                        "quantifier": None,
                        "instruction": numeric_instruction(direction, step),
                        "expected_lab": list(target),
                        "requested_numeric_step": step,
                    }
                )
        pairs.append(
            {
                **common,
                "direction": "none",
                "condition_kind": "no_change",
                "condition_name": "no_change",
                "quantifier": None,
                "instruction": "Keep the current color exactly unchanged.",
                "expected_lab": list(base_lab),
                "requested_numeric_step": 0.0,
            }
        )

    rng = random.Random(cfg.get("seed", 13))
    rng.shuffle(pairs)
    conditions = []
    for pair in pairs:
        pair_key = f"{pair['base_id']}:{pair['condition_kind']}:{pair['direction']}:{pair['condition_name']}"
        variant_order = variants.copy()
        rng.shuffle(variant_order)
        for variant in variant_order:
            lightness, a, b = pair["base_lab"]
            condition = {
                **pair,
                "prompt_variant": variant,
                "pair_key": pair_key,
                "condition_id": f"{variant}:{pair_key}",
                "prompt": render_quantifier_calibration(
                    templates[variant],
                    f"LAB({lightness:.2f}, {a:.2f}, {b:.2f})",
                    pair["instruction"],
                ),
            }
            conditions.append(condition)
    if len({x["condition_id"] for x in conditions}) != len(conditions):
        raise ValueError("Duplicate study conditions")
    expected = study.get("expected_conditions")
    if expected is not None and int(expected) != len(conditions):
        raise ValueError(f"Expected {expected} conditions, built {len(conditions)}")
    return conditions


def plan_digest(conditions: list[dict]) -> str:
    encoded = json.dumps(
        conditions, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def score_prediction(
    condition: dict, predicted_lab: tuple[float, float, float]
) -> dict:
    """Measure native and projected updates; numeric controls have known targets."""
    base = tuple(condition["base_lab"])
    projected_base = projected_lab(base)
    projected = projected_lab(predicted_lab)
    result = {
        "native_movement_norm": color_distance_lab(base, predicted_lab),
        "projected_movement_norm": color_distance_lab(projected_base, projected),
        "lab_projection_delta_e": color_distance_lab(predicted_lab, projected),
        "base_projection_delta_e": color_distance_lab(base, projected_base),
        "control_error_delta_e": None,
        "control_exact_within_0_01": None,
        "control_within_1": None,
        "projected_control_error_delta_e": None,
        "numeric_step_ratio": None,
    }
    for prefix, lab in (
        ("base", base),
        ("guess", predicted_lab),
        ("projected_guess", projected),
    ):
        result.update(
            {f"{prefix}_lab_{axis}": value for axis, value in zip(("l", "a", "b"), lab)}
        )
    if condition["condition_kind"] != "no_change":
        native = measure_update(base, predicted_lab, condition["direction"])
        result.update(native)
        result.update(numerical_headroom(base, predicted_lab, condition["direction"]))
        projected_metrics = measure_update(
            projected_base, projected, condition["direction"]
        )
        result.update(
            {f"projected_{key}": value for key, value in projected_metrics.items()}
        )
    expected = condition["expected_lab"]
    if expected is not None:
        error = color_distance_lab(tuple(expected), predicted_lab)
        result.update(
            {
                "control_error_delta_e": error,
                "control_exact_within_0_01": float(error <= 0.01),
                "control_within_1": float(error <= 1.0),
                "projected_control_error_delta_e": color_distance_lab(
                    projected_lab(tuple(expected)), projected
                ),
            }
        )
    if condition["condition_kind"] == "numeric":
        result["numeric_step_ratio"] = (
            result["requested_signed_step"] / condition["requested_numeric_step"]
        )
    return result
