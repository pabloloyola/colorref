"""Export a flat teacher–guesser interaction table from a completed feedback run.

Each row is one feedback round: the teacher's constraints/text (after the guesser
held color *C*) and the guesser's subsequent revision (new color *C'*), plus
optional structured teacher metadata from ``games/feedback.parquet``.

Color columns (guesser): ``guesser_guess_{hex,lab_l,lab_a,lab_b,hsv_h,hsv_s,hsv_v}_{before,after}``
where *before* is the guess the teacher reacted to and *after* is the guess after revision.
Target color: ``true_hex``, ``true_lab_l``, ``true_lab_a``, ``true_lab_b``.

Turn indexing (matches ``colorref.games.run_game_for_example``):
  - Trajectory ``turn=0``: initial guess (no prior teacher message).
  - ``feedback.parquet`` row ``turn=t``: teacher reacts to the guess active after
    trajectory turn ``t`` (initial guess for ``t=0``).
  - Trajectory ``turn=t+1``, ``phase=revision``: guesser response to that feedback.

Usage:
    uv run python scripts/export_teacher_guesser_interactions.py \\
        --run_dir runs/20260518_014303_feedback_axis_c3_main_4000_qwen3_14b_axis_oracle_main_4000

    uv run python scripts/export_teacher_guesser_interactions.py \\
        --run_dir runs/<run_id> --format csv --out /tmp/interactions.csv

    # CSV is also chosen automatically if --out ends with .csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build teacher–guesser interaction rows from trajectories + feedback.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run_dir", required=True, type=Path, help="Path to a run directory")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default under <run_dir>/reports/; extension .csv → CSV else Parquet)",
    )
    p.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default=None,
        help="Output format (default: infer from --out suffix, else parquet)",
    )
    p.add_argument(
        "--include_initial",
        action="store_true",
        help="Also emit turn-0 rows (guesser only; teacher fields null)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    traj_path = run_dir / "games" / "trajectories.parquet"
    if not traj_path.exists():
        logger.error("Missing %s", traj_path)
        sys.exit(1)

    traj = pd.read_parquet(traj_path).sort_values(["example_id", "turn"])
    fb_path = run_dir / "games" / "feedback.parquet"
    fb: pd.DataFrame | None
    if fb_path.exists():
        fb = pd.read_parquet(fb_path)
    else:
        fb = None
        logger.warning("No feedback.parquet; using only trajectory feedback_prev_* columns")

    # Colors the guesser held before this row (teacher feedback refers to the prior turn's guess).
    _guess_color_cols = [
        "guess_hex",
        "guess_lab_l",
        "guess_lab_a",
        "guess_lab_b",
        "guess_hsv_h",
        "guess_hsv_s",
        "guess_hsv_v",
    ]
    g = traj.groupby("example_id", sort=False)
    for c in _guess_color_cols:
        if c in traj.columns:
            suffix = c.replace("guess_", "")
            traj[f"guesser_guess_{suffix}_before"] = g[c].shift(1)

    revision = traj[traj["turn"] >= 1].copy()
    revision["teacher_feedback_turn"] = revision["turn"] - 1

    if fb is not None and len(fb) > 0:
        fb_sub = fb.rename(
            columns={
                "turn": "teacher_feedback_turn",
                "feedback_text": "teacher_feedback_text_fb",
            }
        )
        revision = revision.merge(
            fb_sub,
            on=["run_id", "example_id", "teacher_feedback_turn"],
            how="left",
            suffixes=("", "_from_feedback_table"),
        )

    # Prefer merged feedback text; fall back to fields duplicated on trajectory rows.
    if "teacher_feedback_text_fb" in revision.columns:
        revision["teacher_feedback_text"] = revision["teacher_feedback_text_fb"].fillna(
            revision["feedback_prev_text"]
        )
    else:
        revision["teacher_feedback_text"] = revision["feedback_prev_text"]

    out_cols = [
        "run_id",
        "example_id",
        "raw_name",
        "regime_label",
        "teacher_feedback_turn",
        "teacher_type",
        "model_alias",
        "guesser_guess_hex_before",
        "guesser_guess_lab_l_before",
        "guesser_guess_lab_a_before",
        "guesser_guess_lab_b_before",
        "guesser_guess_hsv_h_before",
        "guesser_guess_hsv_s_before",
        "guesser_guess_hsv_v_before",
        "teacher_feedback_text",
        "feedback_prev_axis",
        "feedback_prev_direction",
        "feedback_prev_sign",
        "feedback_prev_delta",
        "guesser_prompt",
        "guesser_raw_response",
        "guesser_guess_hex_after",
        "guesser_guess_lab_l_after",
        "guesser_guess_lab_a_after",
        "guesser_guess_lab_b_after",
        "guesser_guess_hsv_h_after",
        "guesser_guess_hsv_s_after",
        "guesser_guess_hsv_v_after",
        "guesser_parse_ok",
        "error_lab_after",
        "true_hex",
        "true_lab_l",
        "true_lab_a",
        "true_lab_b",
        "turn",
        "phase",
    ]

    revision = revision.rename(
        columns={
            "prompt": "guesser_prompt",
            "raw_response": "guesser_raw_response",
            "guess_hex": "guesser_guess_hex_after",
            "guess_lab_l": "guesser_guess_lab_l_after",
            "guess_lab_a": "guesser_guess_lab_a_after",
            "guess_lab_b": "guesser_guess_lab_b_after",
            "guess_hsv_h": "guesser_guess_hsv_h_after",
            "guess_hsv_s": "guesser_guess_hsv_s_after",
            "guess_hsv_v": "guesser_guess_hsv_v_after",
            "parse_ok": "guesser_parse_ok",
            "error_lab": "error_lab_after",
        }
    )

    # Structured teacher fields from feedback table if present (avoid duplicate teacher_type)
    extra_fb_cols = [
        c
        for c in revision.columns
        if c
        in (
            "constraint_axis",
            "constraint_direction",
            "constraint_sign",
            "delta",
            "normalized_delta",
            "target_value",
            "guess_value",
            "all_constraints_json",
            "teacher_raw_output",
            "teacher_parse_ok",
            "teacher_correctness",
        )
    ]
    for c in extra_fb_cols:
        if c in out_cols:
            continue
        if c in revision.columns:
            out_cols.append(c)

    existing = [c for c in out_cols if c in revision.columns]
    table = revision[existing].copy()

    if args.include_initial:
        init = traj[traj["turn"] == 0].copy()
        init = init.rename(
            columns={
                "prompt": "guesser_prompt",
                "raw_response": "guesser_raw_response",
                "guess_hex": "guesser_guess_hex_after",
                "guess_lab_l": "guesser_guess_lab_l_after",
                "guess_lab_a": "guesser_guess_lab_a_after",
                "guess_lab_b": "guesser_guess_lab_b_after",
                "guess_hsv_h": "guesser_guess_hsv_h_after",
                "guess_hsv_s": "guesser_guess_hsv_s_after",
                "guess_hsv_v": "guesser_guess_hsv_v_after",
                "parse_ok": "guesser_parse_ok",
                "error_lab": "error_lab_after",
            }
        )
        init["teacher_feedback_turn"] = pd.NA
        _before_cols = [
            "guesser_guess_hex_before",
            "guesser_guess_lab_l_before",
            "guesser_guess_lab_a_before",
            "guesser_guess_lab_b_before",
            "guesser_guess_hsv_h_before",
            "guesser_guess_hsv_s_before",
            "guesser_guess_hsv_v_before",
        ]
        for c in _before_cols:
            init[c] = pd.NA
        for c in [
            "teacher_feedback_text",
            "feedback_prev_axis",
            "feedback_prev_direction",
            "feedback_prev_sign",
            "feedback_prev_delta",
        ]:
            init[c] = pd.NA
        init_tbl = init[[c for c in existing if c in init.columns]].copy()
        for c in existing:
            if c not in init_tbl.columns:
                init_tbl[c] = pd.NA
        init_tbl = init_tbl[existing]
        table = pd.concat([init_tbl, table], ignore_index=True)

    fmt: str
    if args.format is not None:
        fmt = args.format
    elif args.out is not None and args.out.suffix.lower() == ".csv":
        fmt = "csv"
    else:
        fmt = "parquet"

    out_path = args.out
    if out_path is None:
        out_dir = run_dir / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = ".csv" if fmt == "csv" else ".parquet"
        out_path = out_dir / f"teacher_guesser_interactions{ext}"
    else:
        out_path = out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.format is None and out_path.suffix.lower() == ".csv":
            fmt = "csv"
        elif args.format is None and out_path.suffix.lower() in (".parquet", ".pq"):
            fmt = "parquet"

    if fmt == "csv":
        table.to_csv(
            out_path,
            index=False,
            encoding="utf-8",
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
            float_format="%.6g",
        )
    else:
        table.to_parquet(out_path, index=False)
    logger.info("Wrote %d rows to %s (%s)", len(table), out_path, fmt.upper())


if __name__ == "__main__":
    main()
