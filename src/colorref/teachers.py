"""Teacher variants for the ColorRef feedback game.

Each teacher observes the target color and the model's current guess,
and returns a Feedback object with a text message and structured metadata.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Color dict type alias
# ---------------------------------------------------------------------------

ColorDict = dict  # keys: hex, rgb, lab, hsv


# ---------------------------------------------------------------------------
# Feedback dataclass
# ---------------------------------------------------------------------------

@dataclass
class Feedback:
    text: str
    teacher_type: str
    constraint_axis: str | None        # e.g. "lab_l", "lab_a", "lab_b", "hsv_s"
    constraint_direction: str | None   # e.g. "lighter", "darker"
    constraint_sign: int | None        # +1 or -1
    target_value: float | None
    guess_value: float | None
    delta: float | None                # raw target - guess
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base Teacher
# ---------------------------------------------------------------------------

class Teacher:
    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared oracle logic
# ---------------------------------------------------------------------------

# Approximate perceptual ranges for normalization (spec §11.2)
_RANGES: dict[str, float] = {
    "lab_l": 100.0,
    "lab_a": 200.0,
    "lab_b": 220.0,
    "hsv_s": 1.0,
}

# Minimum raw delta to consider an axis (spec §11.2)
_MIN_DELTA: dict[str, float] = {
    "lab_l": 2.0,
    "lab_a": 3.0,
    "lab_b": 3.0,
    "hsv_s": 0.05,
}

_AXIS_KEYS: dict[str, tuple[str, int]] = {
    # axis_name -> (color_dict_subkey, channel_index)
    "lab_l": ("lab", 0),
    "lab_a": ("lab", 1),
    "lab_b": ("lab", 2),
    "hsv_s": ("hsv", 1),
}

_POSITIVE_DIRECTION: dict[str, str] = {
    "lab_l": "lighter",
    "lab_a": "more red",
    "lab_b": "more yellow",
    "hsv_s": "more saturated",
}

_NEGATIVE_DIRECTION: dict[str, str] = {
    "lab_l": "darker",
    "lab_a": "more green",
    "lab_b": "more blue",
    "hsv_s": "more muted",
}


def _compute_candidate_deltas(
    target: ColorDict,
    guess: ColorDict,
    min_delta: dict[str, float] | None = None,
) -> list[dict]:
    """Compute normalized deltas for each candidate axis.

    Returns list of dicts sorted by abs(normalized_delta) descending,
    filtered by min_delta thresholds.
    """
    min_delta = min_delta or _MIN_DELTA
    candidates = []

    for axis, (key, idx) in _AXIS_KEYS.items():
        t_val = target[key][idx]
        g_val = guess[key][idx]
        raw_delta = t_val - g_val
        if abs(raw_delta) < min_delta.get(axis, 0.0):
            continue
        norm_delta = raw_delta / _RANGES[axis]
        direction = _POSITIVE_DIRECTION[axis] if raw_delta > 0 else _NEGATIVE_DIRECTION[axis]
        sign = 1 if raw_delta > 0 else -1
        candidates.append({
            "axis": axis,
            "direction": direction,
            "sign": sign,
            "raw_delta": raw_delta,
            "normalized_delta": norm_delta,
            "abs_norm": abs(norm_delta),
            "target_value": t_val,
            "guess_value": g_val,
        })

    candidates.sort(key=lambda x: x["abs_norm"], reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Minimal Oracle (spec §11.2)
# ---------------------------------------------------------------------------

class MinimalOracle(Teacher):
    """Give exactly one correction per turn: the axis with largest normalized error."""

    def __init__(
        self,
        min_delta: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        self.min_delta = min_delta or _MIN_DELTA

    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        candidates = _compute_candidate_deltas(target, guess, self.min_delta)

        if not candidates:
            return Feedback(
                text="Your guess looks close. Try again.",
                teacher_type="minimal_oracle",
                constraint_axis=None,
                constraint_direction=None,
                constraint_sign=None,
                target_value=None,
                guess_value=None,
                delta=None,
                metadata={"candidate_deltas": [], "reason": "all_axes_below_threshold"},
            )

        best = candidates[0]
        text = f"Make it {best['direction']}."

        return Feedback(
            text=text,
            teacher_type="minimal_oracle",
            constraint_axis=best["axis"],
            constraint_direction=best["direction"],
            constraint_sign=best["sign"],
            target_value=best["target_value"],
            guess_value=best["guess_value"],
            delta=best["raw_delta"],
            metadata={
                "selected_axis": best["axis"],
                "selected_direction": best["direction"],
                "raw_delta": best["raw_delta"],
                "normalized_delta": best["normalized_delta"],
                "candidate_deltas": candidates,
            },
        )


# ---------------------------------------------------------------------------
# Axis Oracle (spec §11.3)
# ---------------------------------------------------------------------------

class AxisOracle(Teacher):
    """Give up to max_feedback_constraints corrections per turn."""

    def __init__(
        self,
        max_feedback_constraints: int = 3,
        min_delta: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        self.max_n = max_feedback_constraints
        self.min_delta = min_delta or _MIN_DELTA

    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        candidates = _compute_candidate_deltas(target, guess, self.min_delta)

        if not candidates:
            return Feedback(
                text="Your guess looks close. Try again.",
                teacher_type="axis_oracle",
                constraint_axis=None,
                constraint_direction=None,
                constraint_sign=None,
                target_value=None,
                guess_value=None,
                delta=None,
                metadata={"candidate_deltas": [], "reason": "all_axes_below_threshold"},
            )

        selected = candidates[: self.max_n]
        directions = [c["direction"] for c in selected]

        if len(directions) == 1:
            text = f"Make it {directions[0]}."
        elif len(directions) == 2:
            text = f"Make it {directions[0]} and {directions[1]}."
        else:
            text = "Make it " + ", ".join(directions[:-1]) + f", and {directions[-1]}."

        # Report the primary axis in the top-level fields
        primary = selected[0]
        return Feedback(
            text=text,
            teacher_type="axis_oracle",
            constraint_axis=primary["axis"],
            constraint_direction=primary["direction"],
            constraint_sign=primary["sign"],
            target_value=primary["target_value"],
            guess_value=primary["guess_value"],
            delta=primary["raw_delta"],
            metadata={
                "selected_axes": [c["axis"] for c in selected],
                "selected_directions": directions,
                "candidate_deltas": candidates,
                "all_constraints": selected,
            },
        )


# ---------------------------------------------------------------------------
# Template Oracle (spec §11.4)
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, list[str]] = {
    "lighter":        ["Make it lighter.", "Move toward a brighter shade.", "It should have more lightness."],
    "darker":         ["Make it darker.", "Move toward a deeper shade.", "It should be less bright."],
    "more red":       ["Make it more red.", "Shift it toward red."],
    "more green":     ["Make it more green.", "Shift it toward green."],
    "more yellow":    ["Make it more yellow.", "Move it toward yellow."],
    "more blue":      ["Make it more blue.", "Move it toward blue.", "It should be cooler in the blue-yellow direction."],
    "more saturated": ["Make it more saturated.", "Make it more vivid."],
    "more muted":     ["Make it more muted.", "Make it less saturated.", "Tone it down."],
}


class TemplateOracle(Teacher):
    """Same axes as MinimalOracle but feedback text is chosen from paraphrase templates."""

    def __init__(
        self,
        seed: int = 13,
        max_feedback_constraints: int = 1,
        min_delta: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        self.seed = seed
        self.max_n = max_feedback_constraints
        self.min_delta = min_delta or _MIN_DELTA

    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        candidates = _compute_candidate_deltas(target, guess, self.min_delta)

        if not candidates:
            return Feedback(
                text="Your guess looks close. Try again.",
                teacher_type="template_oracle",
                constraint_axis=None,
                constraint_direction=None,
                constraint_sign=None,
                target_value=None,
                guess_value=None,
                delta=None,
                metadata={"candidate_deltas": [], "reason": "all_axes_below_threshold"},
            )

        selected = candidates[: self.max_n]
        parts = []
        for c in selected:
            direction = c["direction"]
            options = _TEMPLATES.get(direction, [f"Make it {direction}."])
            # Deterministic template selection based on example_id, turn, seed
            example_id = int(example.get("example_id", 0))
            idx = (example_id + turn + self.seed) % len(options)
            parts.append(options[idx])

        text = " ".join(parts)
        primary = selected[0]

        return Feedback(
            text=text,
            teacher_type="template_oracle",
            constraint_axis=primary["axis"],
            constraint_direction=primary["direction"],
            constraint_sign=primary["sign"],
            target_value=primary["target_value"],
            guess_value=primary["guess_value"],
            delta=primary["raw_delta"],
            metadata={
                "selected_axis": primary["axis"],
                "selected_direction": primary["direction"],
                "template_used": text,
                "candidate_deltas": candidates,
                "all_constraints": selected,
            },
        )


# ---------------------------------------------------------------------------
# LLM Teacher (spec §11.5)
# ---------------------------------------------------------------------------

# Keyword → (axis, sign) mapping for constraint detection (spec §18.2)
_KEYWORD_CONSTRAINTS: list[tuple[list[str], str, int]] = [
    (["darker", "deeper", "less bright"],        "lab_l", -1),
    (["lighter", "brighter"],                    "lab_l", +1),
    (["more red", "redder"],                     "lab_a", +1),
    (["more green", "greener"],                  "lab_a", -1),
    (["more yellow", "yellower"],                "lab_b", +1),
    (["more blue", "bluer"],                     "lab_b", -1),
    (["more saturated", "vivid", "more vivid"],  "hsv_s", +1),
    (["more muted", "less saturated", "duller"], "hsv_s", -1),
]

_AXIS_DIRECTION_MAP: dict[tuple[str, int], str] = {
    ("lab_l", -1): "darker",
    ("lab_l", +1): "lighter",
    ("lab_a", +1): "more red",
    ("lab_a", -1): "more green",
    ("lab_b", +1): "more yellow",
    ("lab_b", -1): "more blue",
    ("hsv_s", +1): "more saturated",
    ("hsv_s", -1): "more muted",
}


def detect_constraints(text: str) -> list[dict]:
    """Detect axis-sign constraints in feedback text by keyword matching."""
    text_lower = text.lower()
    found = []
    for keywords, axis, sign in _KEYWORD_CONSTRAINTS:
        for kw in keywords:
            if kw in text_lower:
                direction = _AXIS_DIRECTION_MAP.get((axis, sign), kw)
                found.append({"axis": axis, "sign": sign, "direction": direction, "keyword": kw})
                break
    return found


class LLMTeacher(Teacher):
    """Naturalistic feedback generated by a second LLM (v1 + v2 variants)."""

    def __init__(
        self,
        client,
        template: str,
        teacher_type: str = "llm_teacher_hex_only",
        max_tokens: int = 80,
        temperature: float = 0.0,
        include_lab: bool = False,
        oracle_assist: bool = False,
        max_feedback_constraints: int = 1,
        min_delta: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        self.client = client
        self.template = template
        self.teacher_type = teacher_type
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.include_lab = include_lab
        self.oracle_assist = oracle_assist
        self.max_n = max_feedback_constraints
        self.min_delta = min_delta or _MIN_DELTA

    def _oracle_constraints(self, target: ColorDict, guess: ColorDict) -> list[dict]:
        candidates = _compute_candidate_deltas(target, guess, self.min_delta)
        return candidates[: self.max_n]

    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        import json

        from colorref.prompts import render_llm_teacher

        extra: dict[str, Any] = {
            "max_clauses": self.max_n,
        }
        if self.include_lab:
            tl, ta, tb = target["lab"]
            gl, ga, gb = guess["lab"]
            extra["target_lab_l"] = f"{tl:.1f}"
            extra["target_lab_a"] = f"{ta:.1f}"
            extra["target_lab_b"] = f"{tb:.1f}"
            extra["guess_lab_l"] = f"{gl:.1f}"
            extra["guess_lab_a"] = f"{ga:.1f}"
            extra["guess_lab_b"] = f"{gb:.1f}"

        required = self._oracle_constraints(target, guess) if self.oracle_assist else []
        if required:
            extra["oracle_constraints_json"] = json.dumps(
                [{"direction": c["direction"], "axis": c["axis"]} for c in required],
                indent=2,
            )
        else:
            extra["oracle_constraints_json"] = "[]"

        prompt = render_llm_teacher(
            self.template,
            raw_name=str(example.get("raw_name", "")),
            target_hex=target["hex"],
            guess_hex=guess["hex"],
            **extra,
        )

        t0 = time.time()
        try:
            resp = self.client.generate(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            feedback_text = resp.text.strip()
            raw_output = resp.text
            error = resp.error
        except Exception as exc:
            feedback_text = "Try a different color."
            raw_output = ""
            error = str(exc)

        latency_s = time.time() - t0
        detected = detect_constraints(feedback_text)
        parse_ok = len(detected) > 0
        primary = detected[0] if detected else None

        return Feedback(
            text=feedback_text,
            teacher_type=self.teacher_type,
            constraint_axis=primary["axis"] if primary else None,
            constraint_direction=primary["direction"] if primary else None,
            constraint_sign=primary["sign"] if primary else None,
            target_value=None,
            guess_value=None,
            delta=None,
            metadata={
                "teacher_raw_output": raw_output,
                "teacher_feedback_text": feedback_text,
                "teacher_parse_ok": parse_ok,
                "teacher_detected_constraints": detected,
                "teacher_required_constraints": required,
                "all_constraints": required,
                "teacher_error": error,
                "latency_s": latency_s,
            },
        )


_LLM_VOCAB_TEMPLATES: dict[str, list[str]] = {
    **_TEMPLATES,
    "warmer": ["Make it warmer.", "Shift toward a warmer tone."],
    "cooler": ["Make it cooler.", "Shift toward a cooler tone."],
    "closer to gray": ["Move it closer to gray.", "Make it more neutral gray."],
    "less gray": ["Make it less gray.", "Add more chroma away from gray."],
}


class TemplateOracleLLMVocab(TemplateOracle):
    """Deterministic oracle using the LLM teacher vocabulary (v2 baseline)."""

    def give_feedback(
        self,
        target: ColorDict,
        guess: ColorDict,
        example: dict,
        turn: int,
    ) -> Feedback:
        candidates = _compute_candidate_deltas(target, guess, self.min_delta)
        if not candidates:
            return Feedback(
                text="Try adjusting the color.",
                teacher_type="template_oracle_llm_vocab",
                constraint_axis=None,
                constraint_direction=None,
                constraint_sign=None,
                target_value=None,
                guess_value=None,
                delta=None,
                metadata={"candidate_deltas": [], "all_constraints": []},
            )

        selected = candidates[: self.max_n]
        parts = []
        for c in selected:
            direction = c["direction"]
            options = _LLM_VOCAB_TEMPLATES.get(direction, [f"Make it {direction}."])
            example_id = int(example.get("example_id", 0))
            idx = (example_id + turn + self.seed) % len(options)
            parts.append(options[idx])

        text = " ".join(parts)
        primary = selected[0]
        return Feedback(
            text=text,
            teacher_type="template_oracle_llm_vocab",
            constraint_axis=primary["axis"],
            constraint_direction=primary["direction"],
            constraint_sign=primary["sign"],
            target_value=primary["target_value"],
            guess_value=primary["guess_value"],
            delta=primary["raw_delta"],
            metadata={
                "candidate_deltas": candidates,
                "all_constraints": selected,
            },
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_teacher(cfg: dict, teacher_client=None) -> Teacher:
    """Instantiate the correct Teacher from a teacher config dict.

    For llm_teacher, pass a pre-built LLMClient as teacher_client, or it will
    be built automatically from cfg['model'] using build_client().
    """
    teacher_type = cfg.get("type", "minimal_oracle")
    min_delta = cfg.get("min_delta")

    if teacher_type == "minimal_oracle":
        max_c = cfg.get("max_feedback_constraints", 1)
        if max_c != 1:
            import warnings
            warnings.warn(
                f"minimal_oracle ignores max_feedback_constraints={max_c}; using 1",
                stacklevel=2,
            )
        return MinimalOracle(min_delta=min_delta)

    if teacher_type == "axis_oracle":
        return AxisOracle(
            max_feedback_constraints=cfg.get("max_feedback_constraints", 3),
            min_delta=min_delta,
        )

    if teacher_type == "template_oracle":
        return TemplateOracle(
            seed=cfg.get("seed", 13),
            max_feedback_constraints=cfg.get("max_feedback_constraints", 1),
            min_delta=min_delta,
        )

    llm_types = {
        "llm_teacher": "llm_teacher_hex_only",
        "llm_teacher_hex_only": "llm_teacher_hex_only",
        "llm_teacher_lab_aware": "llm_teacher_lab_aware",
        "llm_teacher_oracle_assisted": "llm_teacher_oracle_assisted",
    }
    if teacher_type in llm_types:
        from colorref.llm_clients import build_client
        from colorref.prompts import load_template

        label = llm_types[teacher_type]
        client = teacher_client or build_client(cfg["model"])
        template = load_template(cfg["template_path"])
        model_cfg = cfg.get("model", {})
        return LLMTeacher(
            client=client,
            template=template,
            teacher_type=label,
            max_tokens=model_cfg.get("max_tokens", 80),
            temperature=model_cfg.get("temperature", 0.0),
            include_lab=(label == "llm_teacher_lab_aware"),
            oracle_assist=(label == "llm_teacher_oracle_assisted"),
            max_feedback_constraints=cfg.get("max_feedback_constraints", 1),
            min_delta=min_delta,
        )

    if teacher_type == "template_oracle_llm_vocab":
        return TemplateOracleLLMVocab(
            seed=cfg.get("seed", 13),
            max_feedback_constraints=cfg.get("max_feedback_constraints", 1),
            min_delta=min_delta,
        )

    raise ValueError(f"Unknown teacher type: {teacher_type!r}")
