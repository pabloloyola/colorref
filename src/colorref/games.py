"""Feedback game orchestration for the ColorRef experiment pipeline.

Implements the multi-turn game loop: initial guess → feedback → revision.
Returns structured trajectory and feedback records ready for persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from colorref.colors import (
    hex_to_rgb,
    rgb_to_lab,
    rgb_to_hsv,
    color_distance_lab,
)
from colorref.metrics import is_converged
from colorref.parsing import extract_hex
from colorref.prompts import render_oneshot, render_revision
from colorref.teachers import Feedback, Teacher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_and_convert(text: str) -> dict:
    """Parse a model output string into a color dict.

    Returns a dict with keys:
        parse_ok, parse_reason, hex, rgb, lab, hsv
    (color fields are None if parsing fails)
    """
    guess_hex, meta = extract_hex(text)
    if not guess_hex:
        return {
            "parse_ok": False,
            "parse_reason": meta.get("reason", "no_hex"),
            "hex": None, "rgb": None, "lab": None, "hsv": None,
        }
    try:
        rgb = hex_to_rgb(guess_hex)
        lab = rgb_to_lab(*rgb)
        hsv = rgb_to_hsv(*rgb)
        return {
            "parse_ok": True,
            "parse_reason": None,
            "hex": guess_hex,
            "rgb": rgb,
            "lab": lab,
            "hsv": hsv,
        }
    except Exception as exc:
        return {
            "parse_ok": False,
            "parse_reason": f"conversion_error: {exc}",
            "hex": None, "rgb": None, "lab": None, "hsv": None,
        }


def _color_dict_from_row(row: dict) -> dict:
    """Build a target color dict from a dataset row."""
    rgb = (int(row["rgb_r"]), int(row["rgb_g"]), int(row["rgb_b"]))
    lab = (float(row["lab_l"]), float(row["lab_a"]), float(row["lab_b"]))
    hsv = (float(row["hsv_h"]), float(row["hsv_s"]), float(row["hsv_v"]))
    return {"hex": str(row["hex"]), "rgb": rgb, "lab": lab, "hsv": hsv}


# ---------------------------------------------------------------------------
# Per-turn record builder
# ---------------------------------------------------------------------------

def _turn_record(
    run_id: str,
    example: dict,
    target: dict,
    turn: int,
    phase: str,
    prompt: str,
    raw_response: str,
    guess: dict,
    error_lab: float | None,
    feedback_prev: Feedback | None,
    model_alias: str,
    teacher_type: str,
    prompt_version: str,
) -> dict:
    fb = feedback_prev
    return {
        "run_id": run_id,
        "example_id": example["example_id"],
        "raw_name": example["raw_name"],
        "true_hex": target["hex"],
        "true_lab_l": target["lab"][0],
        "true_lab_a": target["lab"][1],
        "true_lab_b": target["lab"][2],
        "true_hsv_h": target["hsv"][0],
        "true_hsv_s": target["hsv"][1],
        "true_hsv_v": target["hsv"][2],
        "model_alias": model_alias,
        "teacher_type": teacher_type,
        "prompt_version": prompt_version,
        "turn": turn,
        "phase": phase,
        "prompt": prompt,
        "raw_response": raw_response,
        "guess_hex": guess["hex"],
        "parse_ok": guess["parse_ok"],
        "parse_reason": guess["parse_reason"],
        "guess_lab_l": guess["lab"][0] if guess["lab"] else None,
        "guess_lab_a": guess["lab"][1] if guess["lab"] else None,
        "guess_lab_b": guess["lab"][2] if guess["lab"] else None,
        "guess_hsv_h": guess["hsv"][0] if guess["hsv"] else None,
        "guess_hsv_s": guess["hsv"][1] if guess["hsv"] else None,
        "guess_hsv_v": guess["hsv"][2] if guess["hsv"] else None,
        "error_lab": error_lab,
        "feedback_prev_text": fb.text if fb else None,
        "feedback_prev_axis": fb.constraint_axis if fb else None,
        "feedback_prev_direction": fb.constraint_direction if fb else None,
        "feedback_prev_sign": fb.constraint_sign if fb else None,
        "feedback_prev_delta": fb.delta if fb else None,
        "regime_label": example.get("regime_label"),
        "abstraction_score": example.get("abstraction_score"),
        "explicitness_score": example.get("explicitness_score"),
        "prototype_score": example.get("prototype_score"),
        "rarity_score": example.get("rarity_score"),
        "hue_bin": example.get("hue_bin"),
        "lightness_bin": example.get("lightness_bin"),
        "saturation_bin": example.get("saturation_bin"),
        "value_bin": example.get("value_bin"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _feedback_record(
    run_id: str,
    example_id: int,
    turn: int,
    feedback: Feedback,
) -> dict:
    import json
    return {
        "run_id": run_id,
        "example_id": example_id,
        "turn": turn,
        "teacher_type": feedback.teacher_type,
        "feedback_text": feedback.text,
        "constraint_axis": feedback.constraint_axis,
        "constraint_direction": feedback.constraint_direction,
        "constraint_sign": feedback.constraint_sign,
        "target_value": feedback.target_value,
        "guess_value": feedback.guess_value,
        "delta": feedback.delta,
        "normalized_delta": (
            feedback.delta / {"lab_l": 100, "lab_a": 200, "lab_b": 220, "hsv_s": 1}.get(
                feedback.constraint_axis or "", 1
            )
            if feedback.delta is not None else None
        ),
        "all_candidate_deltas_json": json.dumps(
            feedback.metadata.get("candidate_deltas", []),
            default=float,
        ),
        "all_constraints_json": json.dumps(
            feedback.metadata.get("all_constraints", []),
            default=float,
        ),
        "teacher_raw_output": feedback.metadata.get("teacher_raw_output"),
        "teacher_parse_ok": feedback.metadata.get("teacher_parse_ok"),
        "teacher_correctness": feedback.metadata.get("teacher_correctness"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Per-example summary builder
# ---------------------------------------------------------------------------

def _example_summary(
    run_id: str,
    example: dict,
    target: dict,
    turn_records: list[dict],
    feedback_records: list[dict],
    model_alias: str,
    teacher_type: str,
    max_turns: int,
    convergence_delta_e: float,
) -> dict:
    import pandas as pd

    from colorref.example_summary import summarize_example_from_tables

    traj_df = pd.DataFrame(turn_records)
    fb_df = pd.DataFrame(feedback_records) if feedback_records else pd.DataFrame()
    summary = summarize_example_from_tables(
        traj_df,
        fb_df,
        max_turns_configured=max_turns,
        convergence_delta_e=convergence_delta_e,
    )
    summary["run_id"] = run_id
    summary["model_alias"] = model_alias
    summary["teacher_type"] = teacher_type
    summary["true_hex"] = target["hex"]
    return summary


# ---------------------------------------------------------------------------
# Main game runner
# ---------------------------------------------------------------------------

@dataclass
class GameResult:
    turn_records: list[dict] = field(default_factory=list)
    feedback_records: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def format_revision_feedback_text(
    feedback_text_rounds: list[str],
    *,
    accumulate: bool,
) -> str:
    """Build the feedback string passed into the revision prompt template.

    Parameters
    ----------
    feedback_text_rounds:
        Teacher natural-language strings in order (one entry per feedback round).
    accumulate:
        If False, only the latest round is shown (legacy behavior).
        If True, all rounds are shown, numbered, for a running transcript.

    Notes
    -----
    Structured fields on trajectory rows (``feedback_prev_*``) always refer to
    the current round only; the full string shown to the model is in ``prompt``.
    """
    if not feedback_text_rounds:
        return ""
    if not accumulate:
        return feedback_text_rounds[-1]
    if len(feedback_text_rounds) == 1:
        return feedback_text_rounds[0]
    return "\n".join(
        f"Round {i}: {text}" for i, text in enumerate(feedback_text_rounds, start=1)
    )


def run_game_for_example(
    example: dict,
    run_id: str,
    initial_template: str,
    revision_template: str,
    guesser,          # LLMClient
    teacher: Teacher,
    model_alias: str,
    teacher_type: str,
    prompt_version: str,
    max_turns: int = 3,
    convergence_delta_e: float = 5.0,
    max_tokens: int = 64,
    temperature: float = 0.0,
    stop_on_parse_failure: bool = False,
    accumulate_feedback: bool = False,
) -> GameResult:
    """Run the complete feedback game for a single example.

    Returns a GameResult with turn_records, feedback_records, and summary.

    accumulate_feedback
        When True, each revision prompt includes all prior teacher utterances
        (numbered), not only the feedback for the immediately previous guess.
    """
    result = GameResult()
    target = _color_dict_from_row(example)

    # --- Turn 0: initial guess ---
    prompt0 = render_oneshot(initial_template, raw_name=example["raw_name"])
    resp0 = guesser.generate(prompt0, max_tokens=max_tokens, temperature=temperature)
    guess = _parse_and_convert(resp0.text)

    error0 = (
        color_distance_lab(target["lab"], guess["lab"])
        if guess["parse_ok"] and guess["lab"] else None
    )

    result.turn_records.append(_turn_record(
        run_id, example, target, turn=0, phase="initial_guess",
        prompt=prompt0, raw_response=resp0.text, guess=guess,
        error_lab=error0, feedback_prev=None,
        model_alias=model_alias, teacher_type=teacher_type,
        prompt_version=prompt_version,
    ))

    if not guess["parse_ok"]:
        result.summary = _example_summary(
            run_id, example, target, result.turn_records, result.feedback_records,
            model_alias, teacher_type, max_turns, convergence_delta_e,
        )
        return result

    if error0 is not None and is_converged(error0, convergence_delta_e):
        result.summary = _example_summary(
            run_id, example, target, result.turn_records, result.feedback_records,
            model_alias, teacher_type, max_turns, convergence_delta_e,
        )
        return result

    # --- Turns 1..max_turns ---
    current_guess = guess
    current_error = error0
    feedback_text_history: list[str] = []

    for turn in range(max_turns):
        # teacher gives feedback on current guess
        feedback = teacher.give_feedback(target, current_guess, example, turn)
        result.feedback_records.append(_feedback_record(run_id, example["example_id"], turn, feedback))
        feedback_text_history.append(feedback.text)
        feedback_for_prompt = format_revision_feedback_text(
            feedback_text_history, accumulate=accumulate_feedback
        )

        # guesser revises
        revision_prompt = render_revision(
            revision_template,
            raw_name=example["raw_name"],
            previous_guess_hex=current_guess["hex"] or "#000000",
            feedback=feedback_for_prompt,
        )
        resp = guesser.generate(revision_prompt, max_tokens=max_tokens, temperature=temperature)
        next_guess = _parse_and_convert(resp.text)

        next_error = (
            color_distance_lab(target["lab"], next_guess["lab"])
            if next_guess["parse_ok"] and next_guess["lab"] else None
        )

        result.turn_records.append(_turn_record(
            run_id, example, target, turn=turn + 1, phase="revision",
            prompt=revision_prompt, raw_response=resp.text, guess=next_guess,
            error_lab=next_error, feedback_prev=feedback,
            model_alias=model_alias, teacher_type=teacher_type,
            prompt_version=prompt_version,
        ))

        if not next_guess["parse_ok"]:
            if stop_on_parse_failure:
                break
            # keep current_guess for next feedback if we continue
            # but since parse failed we stop gracefully
            break

        current_guess = next_guess
        current_error = next_error

        if current_error is not None and is_converged(current_error, convergence_delta_e):
            break

    result.summary = _example_summary(
        run_id, example, target, result.turn_records, result.feedback_records,
        model_alias, teacher_type, max_turns, convergence_delta_e,
    )
    return result
