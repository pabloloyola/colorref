"""Audit LLM teacher feedback for directional correctness.

For each feedback message produced by an LLM teacher, detect the axis/sign
constraint implied by the text, compare it to the ground-truth target-minus-guess
direction, and report correctness statistics.

Usage:
    uv run python scripts/audit_llm_teacher_feedback.py \
        --run_dir runs/<llm_teacher_run>

    uv run python scripts/audit_llm_teacher_feedback.py \
        --run_dir runs/<llm_teacher_run> \
        --out_dir reports/audits/llm_teacher
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.teachers import detect_constraints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_EPSILON = 1e-8

# Map axis + sign → which trajectory column determines correctness
# correct when sign * (target_val - guess_val) > 0
_AXIS_TARGET_COL: dict[str, str] = {
    "lab_l": "true_lab_l",
    "lab_a": "true_lab_a",
    "lab_b": "true_lab_b",
    "hsv_s": "true_hsv_s",
}
_AXIS_GUESS_COL: dict[str, str] = {
    "lab_l": "guess_lab_l",
    "lab_a": "guess_lab_a",
    "lab_b": "guess_lab_b",
    "hsv_s": "guess_hsv_s",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit LLM teacher feedback directional correctness.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run_dir", required=True, help="Path to a completed run directory")
    p.add_argument(
        "--out_dir",
        default=None,
        help="Output directory for audit CSV (defaults to <run_dir>/reports/)",
    )
    return p.parse_args()


def load_data(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load feedback.parquet and trajectories.parquet."""
    fb_path   = run_dir / "games" / "feedback.parquet"
    traj_path = run_dir / "games" / "trajectories.parquet"

    if not fb_path.exists():
        raise FileNotFoundError(f"feedback.parquet not found in {run_dir}/games/")
    if not traj_path.exists():
        raise FileNotFoundError(f"trajectories.parquet not found in {run_dir}/games/")

    fb_df   = pd.read_parquet(fb_path)
    traj_df = pd.read_parquet(traj_path)
    return fb_df, traj_df


def audit_feedback_row(
    fb_row: pd.Series,
    traj_df: pd.DataFrame,
) -> dict:
    """Audit one feedback row against trajectory data."""
    example_id  = fb_row["example_id"]
    turn        = int(fb_row["turn"])
    feedback_text = str(fb_row.get("feedback_text", ""))

    detected = detect_constraints(feedback_text)

    # Look up trajectory row for the turn AFTER this feedback (turn+1)
    next_turn = traj_df[
        (traj_df["example_id"] == example_id) & (traj_df["turn"] == turn)
    ]
    # Look up the current-turn row (before feedback) to get guess values
    cur_turn = traj_df[
        (traj_df["example_id"] == example_id) & (traj_df["turn"] == turn)
    ]

    results = []
    for c in detected:
        axis = c["axis"]
        sign = c["sign"]
        t_col = _AXIS_TARGET_COL.get(axis)
        g_col = _AXIS_GUESS_COL.get(axis)

        correct = None
        target_val = None
        guess_val  = None
        delta      = None

        if t_col and g_col and len(cur_turn) > 0:
            row = cur_turn.iloc[0]
            target_val = row.get(t_col)
            guess_val  = row.get(g_col)
            if pd.notna(target_val) and pd.notna(guess_val):
                delta = float(target_val) - float(guess_val)
                # Correct if sign matches direction of (target - guess)
                correct = bool(sign * delta > 0)

        results.append({
            "example_id":             example_id,
            "turn":                   turn,
            "feedback_text":          feedback_text,
            "detected_axis":          axis,
            "detected_sign":          sign,
            "detected_direction":     c["direction"],
            "detected_keyword":       c["keyword"],
            "target_value":           target_val,
            "guess_value":            guess_val,
            "delta":                  delta,
            "teacher_constraint_correct": correct,
        })

    if not detected:
        results.append({
            "example_id":             example_id,
            "turn":                   turn,
            "feedback_text":          feedback_text,
            "detected_axis":          None,
            "detected_sign":          None,
            "detected_direction":     None,
            "detected_keyword":       None,
            "target_value":           None,
            "guess_value":            None,
            "delta":                  None,
            "teacher_constraint_correct": None,
        })

    return results


def write_summary(audit_df: pd.DataFrame, out_dir: Path) -> None:
    if audit_df.empty or "detected_axis" not in audit_df.columns:
        path = out_dir / "llm_teacher_audit_summary.md"
        path.write_text("# LLM Teacher Audit Summary\n\nNo feedback rows to audit.\n", encoding="utf-8")
        logger.info("Summary written to %s", path)
        return

    n_total  = len(audit_df)
    detected = audit_df["detected_axis"].notna()
    n_det    = detected.sum()
    det_rate = n_det / max(n_total, 1)

    correct_rows = audit_df[detected & audit_df["teacher_constraint_correct"].notna()]
    n_correct = correct_rows["teacher_constraint_correct"].sum()
    correctness_rate = n_correct / max(len(correct_rows), 1)

    lines = [
        "# LLM Teacher Audit Summary", "",
        f"- Total feedback messages:    {n_total}",
        f"- Constraint detected:        {n_det} ({det_rate:.1%})",
        f"- Constraints evaluable:      {len(correct_rows)}",
        f"- Correct direction:          {int(n_correct)} ({correctness_rate:.1%})",
        "",
        "## Correctness by axis", "",
        "| Axis | N | Correct | Rate |",
        "|---|---:|---:|---:|",
    ]
    for axis, grp in audit_df[detected].groupby("detected_axis"):
        ev = grp[grp["teacher_constraint_correct"].notna()]
        nc = ev["teacher_constraint_correct"].sum()
        rate = nc / max(len(ev), 1)
        lines.append(f"| {axis} | {len(ev)} | {int(nc)} | {rate:.1%} |")
    lines.append("")

    path = out_dir / "llm_teacher_audit_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Summary written to %s", path)


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir) if args.out_dir else run_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Auditing run: %s", run_dir.name)
    fb_df, traj_df = load_data(run_dir)

    # Filter to LLM-teacher rows (variant-specific type names, not literal "llm_teacher")
    if "teacher_type" in fb_df.columns:
        fb_df = fb_df[fb_df["teacher_type"].astype(str).str.startswith("llm_teacher")]
    logger.info("LLM teacher feedback rows: %d", len(fb_df))

    if fb_df.empty:
        logger.warning("No LLM teacher feedback rows found in %s", run_dir.name)
        audit_path = out_dir / "llm_teacher_audit.csv"
        pd.DataFrame(columns=[
            "example_id", "turn", "feedback_text", "detected_axis", "detected_sign",
            "detected_direction", "detected_keyword", "target_value", "guess_value",
            "delta", "teacher_constraint_correct",
        ]).to_csv(audit_path, index=False)
        logger.info("Wrote empty audit to %s", audit_path)
        return

    all_rows: list[dict] = []
    for _, fb_row in fb_df.iterrows():
        rows = audit_feedback_row(fb_row, traj_df)
        all_rows.extend(rows)

    audit_df = pd.DataFrame(all_rows)
    audit_path = out_dir / "llm_teacher_audit.csv"
    audit_df.to_csv(audit_path, index=False)
    logger.info("Audit saved to %s (%d rows)", audit_path, len(audit_df))

    write_summary(audit_df, out_dir)
    logger.info("Done.")


if __name__ == "__main__":
    main()
