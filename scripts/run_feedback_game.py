"""Feedback game experiment runner.

For each example, runs the multi-turn guess → feedback → revise loop
and saves complete trajectory, feedback, per-example summary, and raw JSONL.

Set ``execution.accumulate_feedback: true`` in the YAML to include all prior
teacher utterances in each revision prompt (numbered); default is latest only.

Usage:
    uv run python scripts/run_feedback_game.py \
        --config configs/experiments/feedback_minimal_debug.yaml

    uv run python scripts/run_feedback_game.py \
        --config configs/experiments/feedback_minimal_debug.yaml --limit 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.games import run_game_for_example
from colorref.llm_clients import build_client
from colorref.prompts import load_template
from colorref.teachers import build_teacher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run a multi-turn feedback game experiment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", required=True, help="Path to experiment YAML config")
    p.add_argument("--limit", type=int, default=None, help="Process at most N examples")
    p.add_argument(
        "--run_id",
        default=None,
        help="Resume into an existing run directory instead of creating a new one",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Run ID / directory helpers (same pattern as run_oneshot.py)
# ---------------------------------------------------------------------------

def make_run_id(cfg: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = cfg["experiment_name"]
    alias = cfg["model"]["alias"]
    teacher = cfg["teacher"]["type"]
    subset = Path(cfg["input"]["subset_path"]).stem
    return f"{ts}_{name}_{alias}_{teacher}_{subset}"


def setup_run_dir(run_root: str, run_id: str) -> dict[str, Path]:
    base = Path(run_root) / run_id
    dirs = {
        "base": base,
        "raw_outputs": base / "raw_outputs",
        "games": base / "games",
        "metrics": base / "metrics",
        "reports": base / "reports",
        "inputs": base / "inputs",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def load_completed_ids(jsonl_path: Path) -> set[int]:
    if not jsonl_path.exists():
        return set()
    done: set[int] = set()
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("turn") == 0:
                    done.add(int(rec["example_id"]))
            except Exception:
                pass
    return done


# ---------------------------------------------------------------------------
# Progress summary
# ---------------------------------------------------------------------------

def _log_progress(
    i: int,
    total: int,
    summary: dict,
) -> None:
    ie = summary.get("initial_error_lab")
    fe = summary.get("final_error_lab")
    rel = summary.get("relative_improvement")
    sat = summary.get("mean_constraint_satisfaction")
    logger.info(
        "[%d/%d] id=%-8s  init_ΔE=%5.1f  final_ΔE=%5.1f  rel_imp=%+.2f  csat=%s",
        i + 1, total,
        summary.get("example_id", "?"),
        ie if ie is not None else float("nan"),
        fe if fe is not None else float("nan"),
        rel if rel is not None else float("nan"),
        f"{sat:.2f}" if sat is not None else "n/a",
    )


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def write_summary(
    summaries: list[dict],
    turn_records: list[dict],
    cfg: dict,
    run_id: str,
    reports_dir: Path,
) -> None:
    df = pd.DataFrame(summaries)
    n = len(df)
    n_conv = df["converged"].sum()
    mean_ie = df["initial_error_lab"].mean()
    mean_fe = df["final_error_lab"].mean()
    mean_rel = df["relative_improvement"].mean()
    mean_sat = df["mean_constraint_satisfaction"].dropna().mean()
    mean_align = df["mean_directional_alignment"].dropna().mean()
    parse_failures = df["parse_failure_count"].sum()

    lines = [
        f"# Run summary: {run_id}", "",
        "## Metadata",
        f"- Experiment: `{cfg['experiment_name']}`",
        f"- Model: `{cfg['model']['alias']}` (`{cfg['model']['model_name']}`)",
        f"- Teacher: `{cfg['teacher']['type']}`",
        f"- Max turns: {cfg['execution']['max_turns']}",
        f"- Subset: `{cfg['input']['subset_path']}`",
        f"- Total examples: {n}", "",
        "## Overall metrics",
        f"- Converged: {n_conv} / {n} ({100 * n_conv / max(n, 1):.1f}%)",
        f"- Parse failures: {int(parse_failures)}",
        f"- Mean initial ΔE: {mean_ie:.2f}",
        f"- Mean final ΔE: {mean_fe:.2f}",
        f"- Mean relative improvement: {mean_rel:.3f}",
        f"- Mean constraint satisfaction: {mean_sat:.3f}" if not pd.isna(mean_sat) else "- Mean constraint satisfaction: n/a",
        f"- Mean directional alignment: {mean_align:.3f}" if not pd.isna(mean_align) else "- Mean directional alignment: n/a",
        "",
    ]

    if "regime_label" in df.columns:
        lines += ["## Metrics by regime", ""]
        lines += ["| Regime | N | Init ΔE | Final ΔE | Rel imp | C-sat | Dir align |"]
        lines += ["|---|---:|---:|---:|---:|---:|---:|"]
        for regime, grp in df.groupby("regime_label"):
            csat = grp["mean_constraint_satisfaction"].dropna().mean()
            align = grp["mean_directional_alignment"].dropna().mean()
            lines.append(
                f"| {regime} | {len(grp)} "
                f"| {grp['initial_error_lab'].mean():.2f} "
                f"| {grp['final_error_lab'].mean():.2f} "
                f"| {grp['relative_improvement'].mean():.3f} "
                f"| {csat:.3f} "
                f"| {align:.3f} |"
            )
        lines.append("")

    # Qualitative examples: top 5 improvers and top 5 worst
    if len(df) >= 5:
        lines += ["## Top 5 largest improvements", ""]
        top = df.nlargest(5, "absolute_improvement")
        for _, row in top.iterrows():
            lines.append(f"- [{int(row.example_id)}] \"{row.raw_name}\" "
                         f"ΔE: {row.initial_error_lab:.1f} → {row.final_error_lab:.1f} "
                         f"(+{row.absolute_improvement:.1f})")
        lines.append("")

        lines += ["## Top 5 largest regressions", ""]
        worst = df.nsmallest(5, "absolute_improvement")
        for _, row in worst.iterrows():
            lines.append(f"- [{int(row.example_id)}] \"{row.raw_name}\" "
                         f"ΔE: {row.initial_error_lab:.1f} → {row.final_error_lab:.1f} "
                         f"({row.absolute_improvement:.1f})")
        lines.append("")

    (reports_dir / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Summary written to %s/run_summary.md", reports_dir)


def _write_prompt_audit(
    df: pd.DataFrame,
    initial_template: str,
    revision_template: str,
    reports_dir: Path,
    n: int = 20,
) -> None:
    """Save up to n rendered example prompts for manual inspection (spec §23.2)."""
    from colorref.prompts import render_oneshot, render_revision
    lines = ["# Prompt audit (first 20 examples)\n"]
    for i, (_, row) in enumerate(df.head(n).iterrows()):
        raw_name = str(row["raw_name"])
        lines.append(f"## Example {i+1}: example_id={row['example_id']}")
        lines.append(f"**raw_name:** {raw_name}\n")
        lines.append("**Initial prompt:**\n```")
        lines.append(render_oneshot(initial_template, raw_name=raw_name))
        lines.append("```\n")
        lines.append("**Revision prompt (placeholder feedback):**\n```")
        lines.append(render_revision(revision_template, raw_name=raw_name,
                                     previous_guess_hex="#aabbcc",
                                     feedback="Make it darker."))
        lines.append("```\n")
    (reports_dir / "prompt_audit.txt").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Prompt audit written to %s/prompt_audit.txt", reports_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text())

    if args.limit is not None:
        cfg["execution"]["limit"] = args.limit

    run_root = cfg.get("output", {}).get("run_root", "runs")
    if args.run_id:
        run_id = args.run_id
        logger.info("Resuming existing run: %s", run_id)
    else:
        run_id = make_run_id(cfg)
    dirs = setup_run_dir(run_root, run_id)
    logger.info("Run ID: %s", run_id)

    # save config + metadata
    (dirs["base"] / "config.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    metadata = {
        "run_id": run_id,
        "experiment_name": cfg["experiment_name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(cfg_path),
        "seed": cfg.get("seed", 13),
        "model": cfg["model"],
        "teacher": cfg["teacher"],
        "execution": cfg["execution"],
    }
    (dirs["base"] / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # load subset
    subset_path = cfg["input"]["subset_path"]
    df = pd.read_parquet(subset_path)
    logger.info("Loaded subset: %d rows from %s", len(df), subset_path)
    df.to_parquet(dirs["inputs"] / "subset.parquet", index=False)

    # resume
    jsonl_path = dirs["raw_outputs"] / "responses.jsonl"
    completed_ids: set[int] = set()
    if cfg["execution"].get("resume", True):
        completed_ids = load_completed_ids(jsonl_path)
        if completed_ids:
            logger.info("Resuming: %d examples already done", len(completed_ids))

    rows = [row.to_dict() for _, row in df.iterrows()
            if int(row["example_id"]) not in completed_ids]

    limit = cfg["execution"].get("limit")
    if limit:
        rows = rows[:limit]
    logger.info("Examples to process: %d", len(rows))

    # templates
    initial_template = load_template(cfg["prompt"]["initial_template_path"])
    revision_template = load_template(cfg["prompt"]["revision_template_path"])

    # --- prompt audit: save 20 rendered prompts ---
    _write_prompt_audit(df, initial_template, revision_template, dirs["reports"])

    # client and teacher
    logger.info("Building LLM client…")
    guesser = build_client(cfg["model"])
    teacher_cfg = cfg["teacher"]
    teacher_type = teacher_cfg.get("type", "minimal_oracle")
    if teacher_type == "llm_teacher":
        # Reuse the guesser if the teacher model matches; avoids loading two copies
        t_model_cfg = teacher_cfg.get("model", {})
        same_model = (
            t_model_cfg.get("model_name") == cfg["model"].get("model_name")
            and t_model_cfg.get("provider") == cfg["model"].get("provider")
        )
        teacher_client = guesser if same_model else None
        if same_model:
            logger.info("LLM teacher: sharing guesser model instance")
        else:
            logger.info("LLM teacher: building separate teacher client")
        teacher = build_teacher(teacher_cfg, teacher_client=teacher_client)
    else:
        teacher = build_teacher(teacher_cfg)
    logger.info("Teacher: %s", teacher_type)

    exec_cfg = cfg["execution"]
    max_turns = exec_cfg.get("max_turns", 3)
    convergence_delta_e = exec_cfg.get("convergence_delta_e", 5.0)
    stop_on_parse_failure = exec_cfg.get("stop_on_parse_failure", False)
    sleep_s = exec_cfg.get("sleep_s", 0.0)
    accumulate_feedback = bool(exec_cfg.get("accumulate_feedback", False))
    if accumulate_feedback:
        logger.info("Revision prompts will include accumulated feedback (all prior rounds).")

    all_turn_records: list[dict] = []
    all_feedback_records: list[dict] = []
    all_summaries: list[dict] = []

    with jsonl_path.open("a") as jsonl_file:
        for i, example in enumerate(rows):
            game = run_game_for_example(
                example=example,
                run_id=run_id,
                initial_template=initial_template,
                revision_template=revision_template,
                guesser=guesser,
                teacher=teacher,
                model_alias=cfg["model"]["alias"],
                teacher_type=cfg["teacher"]["type"],
                prompt_version=cfg["prompt"]["initial_template_path"],
                max_turns=max_turns,
                convergence_delta_e=convergence_delta_e,
                max_tokens=cfg["model"]["max_tokens"],
                temperature=cfg["model"]["temperature"],
                stop_on_parse_failure=stop_on_parse_failure,
                accumulate_feedback=accumulate_feedback,
            )

            # write all turn records to JSONL (crash-safe)
            for rec in game.turn_records:
                jsonl_file.write(json.dumps(rec, default=str) + "\n")
            jsonl_file.flush()

            all_turn_records.extend(game.turn_records)
            all_feedback_records.extend(game.feedback_records)
            all_summaries.append(game.summary)

            if (i + 1) % 10 == 0 or (i + 1) == len(rows):
                _log_progress(i, len(rows), game.summary)

            if sleep_s > 0:
                time.sleep(sleep_s)

    # --- save trajectories ---
    # When resuming, in-memory all_turn_records only contains NEW examples.
    # Always rebuild the complete trajectory from the JSONL so resumed runs
    # produce a correct full parquet.
    import json as _json
    all_jsonl_records: list[dict] = []
    with jsonl_path.open() as _f:
        for _line in _f:
            try:
                all_jsonl_records.append(_json.loads(_line))
            except Exception:
                pass
    traj_df = pd.DataFrame(all_jsonl_records)
    traj_df.to_parquet(dirs["games"] / "trajectories.parquet", index=False)
    logger.info("Trajectories saved (%d turn records, %d examples)",
                len(traj_df), traj_df["example_id"].nunique() if len(traj_df) else 0)

    # --- save feedback table ---
    # Reconstruct feedback from trajectory JSONL (feedback fields are embedded in turn records)
    fb_rows = []
    for rec in all_jsonl_records:
        if rec.get("turn", 0) > 0 and rec.get("feedback_prev_text") is not None:
            fb_rows.append({
                "run_id":              rec.get("run_id"),
                "example_id":         rec.get("example_id"),
                "turn":               rec.get("turn", 0) - 1,  # feedback was given after turn-1
                "teacher_type":       rec.get("teacher_type"),
                "feedback_text":      rec.get("feedback_prev_text"),
                "constraint_axis":    rec.get("feedback_prev_axis"),
                "constraint_direction": rec.get("feedback_prev_direction"),
                "constraint_sign":    rec.get("feedback_prev_sign"),
                "delta":              rec.get("feedback_prev_delta"),
                "created_at":         rec.get("created_at"),
            })
    # Supplement with richer in-session feedback records (contain full metadata)
    in_session_fb = pd.DataFrame(all_feedback_records)
    if len(fb_rows) > 0 and len(in_session_fb) > 0:
        # Use JSONL-derived rows for any previously-completed examples, supplement with in-session
        in_session_ids = set(in_session_fb["example_id"].unique()) if "example_id" in in_session_fb.columns else set()
        prev_fb = [r for r in fb_rows if r["example_id"] not in in_session_ids]
        fb_df = pd.concat([pd.DataFrame(prev_fb), in_session_fb], ignore_index=True)
    elif len(in_session_fb) > 0:
        fb_df = in_session_fb
    else:
        fb_df = pd.DataFrame(fb_rows)
    fb_df.to_parquet(dirs["games"] / "feedback.parquet", index=False)

    # --- save per-example summary ---
    # If we resumed, in-session summaries only cover new examples.
    # Rebuild all-example summaries by aggregating from the full trajectory DataFrame.
    if completed_ids:
        # Compute per-example summary from full traj_df for all examples
        def _summarize_from_traj(traj: pd.DataFrame) -> list[dict]:
            rows = []
            for eid, grp in traj.groupby("example_id"):
                grp_sorted = grp.sort_values("turn")
                turn0 = grp_sorted[grp_sorted["turn"] == 0]
                last  = grp_sorted.iloc[-1]
                ie = turn0["error_lab"].iloc[0] if len(turn0) and pd.notna(turn0["error_lab"].iloc[0]) else None
                fe = last["error_lab"] if pd.notna(last["error_lab"]) else ie
                ai = (ie - fe) if (ie is not None and fe is not None) else None
                ri = ai / (ie + 1e-8) if (ai is not None and ie) else 0.0
                rows.append({
                    "run_id":              last.get("run_id"),
                    "example_id":          eid,
                    "raw_name":            last.get("raw_name"),
                    "true_hex":            last.get("true_hex"),
                    "model_alias":         last.get("model_alias"),
                    "teacher_type":        last.get("teacher_type"),
                    "num_valid_turns":     len(grp_sorted),
                    "initial_error_lab":   ie,
                    "final_error_lab":     fe,
                    "absolute_improvement": ai,
                    "relative_improvement": ri,
                    "converged":           bool(fe is not None and fe < convergence_delta_e),
                    "parse_failure_count": int((~grp_sorted["parse_ok"].astype(bool)).sum()),
                    "regime_label":        last.get("regime_label"),
                    "abstraction_score":   last.get("abstraction_score"),
                    "explicitness_score":  last.get("explicitness_score"),
                    "prototype_score":     last.get("prototype_score"),
                    "rarity_score":        last.get("rarity_score"),
                    "hue_bin":             last.get("hue_bin"),
                    "lightness_bin":       last.get("lightness_bin"),
                    "saturation_bin":      last.get("saturation_bin"),
                    "value_bin":           last.get("value_bin"),
                    # Fields computed during game (only available for in-session examples)
                    "mean_constraint_satisfaction": None,
                    "mean_directional_alignment":   None,
                    "best_error_lab":               None,
                    "best_turn":                    None,
                    "trajectory_path_length":       None,
                    "trajectory_efficiency":        None,
                })
            return rows
        # Merge: use richer in-session summaries for new examples, traj-derived for old
        in_session_ids = {s["example_id"] for s in all_summaries}
        prev_rows = _summarize_from_traj(traj_df[~traj_df["example_id"].isin(in_session_ids)])
        merged_summaries = prev_rows + all_summaries
    else:
        merged_summaries = all_summaries

    summary_df = pd.DataFrame(merged_summaries)
    summary_df.to_parquet(dirs["metrics"] / "per_example.parquet", index=False)

    # --- aggregate CSVs ---
    if "regime_label" in summary_df.columns:
        agg = summary_df.groupby("regime_label").agg(
            n=("example_id", "count"),
            mean_initial_error=("initial_error_lab", "mean"),
            mean_final_error=("final_error_lab", "mean"),
            mean_relative_improvement=("relative_improvement", "mean"),
            convergence_rate=("converged", "mean"),
            mean_constraint_satisfaction=("mean_constraint_satisfaction", "mean"),
            mean_directional_alignment=("mean_directional_alignment", "mean"),
        ).reset_index()
        agg.to_csv(dirs["metrics"] / "aggregate_by_regime.csv", index=False)

    # --- write summary markdown ---
    write_summary(merged_summaries, all_jsonl_records, cfg, run_id, dirs["reports"])
    logger.info("Done. Run directory: %s", dirs["base"])


if __name__ == "__main__":
    main()
