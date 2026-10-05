"""Evaluate completed runs and write full metrics tables.

Recomputes metrics from raw trajectory fields so they are independent of any
runtime calculations. Writes per-turn, per-example, and aggregate CSVs.

Usage — single run:
    uv run python scripts/evaluate_games.py \
        --run_dir runs/20260515_174732_feedback_minimal_debug_qwen3_8b_minimal_oracle_debug_400

Usage — multi-run comparison:
    uv run python scripts/evaluate_games.py \
        --run_dirs runs/run_a runs/run_b runs/run_c \
        --out_dir reports/comparisons/minimal_vs_axis
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.metrics import directional_alignment
from colorref.example_summary import summarize_example_from_tables
from colorref.stats import bootstrap_grouped_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_EPSILON = 1e-8


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _dedupe_trajectory(traj_df: pd.DataFrame) -> pd.DataFrame:
    """Keep the last record per (example_id, turn) when resume appended duplicates."""
    if traj_df.empty or "example_id" not in traj_df.columns or "turn" not in traj_df.columns:
        return traj_df
    sort_cols = ["example_id", "turn"]
    if "created_at" in traj_df.columns:
        sort_cols.append("created_at")
    out = traj_df.sort_values(sort_cols).drop_duplicates(
        subset=["example_id", "turn"], keep="last"
    )
    n_dup = len(traj_df) - len(out)
    if n_dup > 0:
        logger.warning("Dropped %d duplicate trajectory rows after resume", n_dup)
    return out.reset_index(drop=True)


def _dedupe_feedback(fb_df: pd.DataFrame) -> pd.DataFrame:
    if fb_df.empty or "example_id" not in fb_df.columns or "turn" not in fb_df.columns:
        return fb_df
    sort_cols = ["example_id", "turn"]
    if "created_at" in fb_df.columns:
        sort_cols.append("created_at")
    out = fb_df.sort_values(sort_cols).drop_duplicates(
        subset=["example_id", "turn"], keep="last"
    )
    n_dup = len(fb_df) - len(out)
    if n_dup > 0:
        logger.warning("Dropped %d duplicate feedback rows after resume", n_dup)
    return out.reset_index(drop=True)


def load_run(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load trajectories.parquet (or oneshot_predictions.parquet), feedback.parquet, metadata.json."""
    traj_path    = run_dir / "games" / "trajectories.parquet"
    oneshot_path = run_dir / "games" / "oneshot_predictions.parquet"
    fb_path      = run_dir / "games" / "feedback.parquet"
    meta_path    = run_dir / "metadata.json"

    if traj_path.exists():
        traj_df = pd.read_parquet(traj_path)
        traj_df = _dedupe_trajectory(traj_df)
    elif oneshot_path.exists():
        # Adapt one-shot predictions to trajectory format (single turn=0, no feedback)
        pred_df = pd.read_parquet(oneshot_path)
        traj_df = pred_df.rename(columns={
            "true_lab_l": "true_lab_l",
            "true_lab_a": "true_lab_a",
            "true_lab_b": "true_lab_b",
        }).copy()
        traj_df["turn"]  = 0
        traj_df["phase"] = "oneshot"
        for col in ["feedback_prev_text", "feedback_prev_axis", "feedback_prev_direction",
                    "feedback_prev_sign", "feedback_prev_delta", "teacher_type",
                    "true_hsv_h", "true_hsv_s", "true_hsv_v", "true_hex"]:
            if col not in traj_df.columns:
                traj_df[col] = None
        if "hex" in traj_df.columns and "true_hex" not in traj_df.columns:
            traj_df["true_hex"] = traj_df["hex"]
        logger.info("Loaded one-shot predictions as single-turn trajectories")
    else:
        raise FileNotFoundError(
            f"Neither trajectories.parquet nor oneshot_predictions.parquet found in {run_dir}/games/"
        )

    fb_df    = pd.read_parquet(fb_path) if fb_path.exists() else pd.DataFrame()
    if not fb_df.empty:
        fb_df = _dedupe_feedback(fb_df)
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    logger.info("Loaded %d turn records from %s", len(traj_df), run_dir.name)
    return traj_df, fb_df, metadata


# ---------------------------------------------------------------------------
# Per-turn metrics recomputation
# ---------------------------------------------------------------------------

def compute_per_turn(traj_df: pd.DataFrame) -> pd.DataFrame:
    """Add derived per-turn columns: per_turn_delta_e, directional_alignment."""
    df = traj_df.copy()

    # Per-turn delta E: improvement from this turn to next (within same example)
    df = df.sort_values(["example_id", "turn"]).reset_index(drop=True)

    delta_e = []
    dir_align = []

    for _, grp in df.groupby("example_id"):
        grp = grp.sort_values("turn")
        errors = grp["error_lab"].tolist()
        labs_l = grp["guess_lab_l"].tolist()
        labs_a = grp["guess_lab_a"].tolist()
        labs_b = grp["guess_lab_b"].tolist()
        true_l = grp["true_lab_l"].tolist()
        true_a = grp["true_lab_a"].tolist()
        true_b = grp["true_lab_b"].tolist()

        for i, (_, row) in enumerate(grp.iterrows()):
            # delta_e: E_t - E_{t+1} (positive = improvement)
            if i + 1 < len(errors) and errors[i] is not None and errors[i + 1] is not None:
                delta_e.append(errors[i] - errors[i + 1])
            else:
                delta_e.append(None)

            # directional alignment with next turn
            if (i + 1 < len(labs_l)
                    and all(v is not None for v in [labs_l[i], labs_a[i], labs_b[i],
                                                     labs_l[i+1], labs_a[i+1], labs_b[i+1]])):
                tgt = (true_l[i], true_a[i], true_b[i])
                cur = (labs_l[i], labs_a[i], labs_b[i])
                nxt = (labs_l[i+1], labs_a[i+1], labs_b[i+1])
                dir_align.append(directional_alignment(tgt, cur, nxt))
            else:
                dir_align.append(None)

    df["per_turn_delta_e"] = delta_e
    df["per_turn_directional_alignment"] = dir_align
    return df


# ---------------------------------------------------------------------------
# Per-example metrics recomputation
# ---------------------------------------------------------------------------

def compute_per_example(
    traj_df: pd.DataFrame,
    fb_df: pd.DataFrame,
    convergence_delta_e: float = 5.0,
    max_turns_configured: int = 3,
) -> pd.DataFrame:
    """Recompute per-example summary from trajectory and feedback tables."""
    rows = []
    for eid in traj_df["example_id"].unique():
        sub = traj_df[traj_df["example_id"] == eid]
        ex_fb = fb_df[fb_df["example_id"] == eid] if not fb_df.empty else pd.DataFrame()
        rows.append(
            summarize_example_from_tables(
                sub,
                ex_fb,
                max_turns_configured=max_turns_configured,
                convergence_delta_e=convergence_delta_e,
            )
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

_AGG_COLS = {
    "n":                         ("example_id", "count"),
    "parse_success_rate":        ("parse_failure_count", lambda s: 1 - s.sum() / max(s.count(), 1)),
    "mean_initial_error":        ("initial_error_lab", "mean"),
    "median_initial_error":      ("initial_error_lab", "median"),
    "se_initial_error":          ("initial_error_lab", "sem"),
    "mean_final_error":          ("final_error_lab", "mean"),
    "median_final_error":        ("final_error_lab", "median"),
    "se_final_error":            ("final_error_lab", "sem"),
    "mean_absolute_improvement": ("absolute_improvement", "mean"),
    "mean_relative_improvement": ("relative_improvement", "mean"),
    "se_relative_improvement":   ("relative_improvement", "sem"),
    "mean_best_error":           ("best_error_lab", "mean"),
    "convergence_rate":          ("converged", "mean"),
    "mean_feedback_rounds_issued": ("num_feedback_rounds_issued", "mean"),
    "mean_revision_attempts":    ("num_revision_attempts", "mean"),
    "mean_states":               ("num_states", "mean"),
    "mean_converged_at_round":   (
        "converged_at_round",
        lambda s: s,  # placeholder; handled in _aggregate
    ),
    "mean_directional_alignment":    ("mean_directional_alignment", "mean"),
    "mean_constraint_satisfaction":  ("mean_constraint_satisfaction", "mean"),
    "se_constraint_satisfaction":    ("mean_constraint_satisfaction", "sem"),
    "mean_trajectory_efficiency":    ("trajectory_efficiency", "mean"),
    "mean_constraints_issued":   ("mean_constraints_issued", "mean"),
}

_BOOTSTRAP_METRICS = [
    "initial_error_lab",
    "final_error_lab",
    "absolute_improvement",
    "relative_improvement",
    "mean_constraint_satisfaction",
    "mean_directional_alignment",
    "trajectory_efficiency",
]

_CI_RENAME = {
    "initial_error_lab": "initial_error",
    "final_error_lab": "final_error",
    "absolute_improvement": "absolute_improvement",
    "relative_improvement": "relative_improvement",
    "mean_constraint_satisfaction": "constraint_satisfaction",
    "mean_directional_alignment": "directional_alignment",
    "trajectory_efficiency": "trajectory_efficiency",
}


def _rename_ci_columns(ci_df: pd.DataFrame) -> pd.DataFrame:
    out = ci_df.copy()
    for old, new in _CI_RENAME.items():
        for prefix in ("mean_", "ci95_low_", "ci95_high_"):
            old_col = f"{prefix}{old}"
            new_col = f"{prefix}{new}"
            if old_col in out.columns:
                out = out.rename(columns={old_col: new_col})
    return out


def _aggregate(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for val, grp in df.groupby(group_col):
        row: dict = {group_col: val}
        for out_col, (src_col, fn) in _AGG_COLS.items():
            if src_col not in grp.columns:
                row[out_col] = None
                continue
            series = grp[src_col].dropna()
            if out_col == "mean_converged_at_round":
                conv = grp[grp["converged"] == True]["converged_at_round"].dropna()
                row[out_col] = float(conv.mean()) if len(conv) else None
            elif callable(fn):
                row[out_col] = fn(grp[src_col]) if len(series) else None
            elif fn == "count":
                row[out_col] = len(grp)
            else:
                row[out_col] = getattr(series, fn)() if len(series) else None
        rows.append(row)
    return pd.DataFrame(rows)


def write_bootstrap_cis(
    per_example_df: pd.DataFrame,
    metrics_dir: Path,
    seed: int = 13,
) -> None:
    """Write bootstrap CI aggregate tables for paper-facing metrics."""
    ci_specs = {
        "aggregate_by_teacher_ci": "teacher_type",
        "aggregate_by_regime_ci": "regime_label",
    }
    for stem, col in ci_specs.items():
        if col not in per_example_df.columns:
            continue
        ci_df = bootstrap_grouped_metrics(
            per_example_df,
            group_cols=col,
            metric_cols=_BOOTSTRAP_METRICS,
            seed=seed,
        )
        ci_df = _rename_ci_columns(ci_df)
        ci_df.to_csv(metrics_dir / f"{stem}.csv", index=False)
        logger.info("  Wrote %s.csv (%d rows)", stem, len(ci_df))

    if {"regime_label", "teacher_type"}.issubset(per_example_df.columns):
        ci_rt = bootstrap_grouped_metrics(
            per_example_df,
            group_cols=["regime_label", "teacher_type"],
            metric_cols=_BOOTSTRAP_METRICS,
            seed=seed,
        )
        ci_rt = _rename_ci_columns(ci_rt)
        ci_rt.to_csv(metrics_dir / "aggregate_by_regime_teacher_ci.csv", index=False)
        logger.info("  Wrote aggregate_by_regime_teacher_ci.csv (%d rows)", len(ci_rt))


def write_aggregates(per_example_df: pd.DataFrame, metrics_dir: Path, seed: int = 13) -> None:
    groupings = {
        "aggregate_by_regime":               "regime_label",
        "aggregate_by_teacher":              "teacher_type",
        "aggregate_by_model":                "model_alias",
        "aggregate_by_hue_bin":              "hue_bin",
        "aggregate_by_lightness_bin":        "lightness_bin",
        "aggregate_by_saturation_bin":       "saturation_bin",
    }
    for stem, col in groupings.items():
        if col in per_example_df.columns:
            agg = _aggregate(per_example_df, col)
            agg.to_csv(metrics_dir / f"{stem}.csv", index=False)
            logger.info("  Wrote %s.csv (%d rows)", stem, len(agg))

    write_bootstrap_cis(per_example_df, metrics_dir, seed=seed)

    # abstraction quartile
    if "abstraction_score" in per_example_df.columns:
        df2 = per_example_df.copy()
        df2["abstraction_quartile"] = pd.qcut(
            df2["abstraction_score"].dropna(), q=4,
            labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop",
        )
        agg = _aggregate(df2.dropna(subset=["abstraction_quartile"]), "abstraction_quartile")
        agg.to_csv(metrics_dir / "aggregate_by_abstraction_quartile.csv", index=False)
        logger.info("  Wrote aggregate_by_abstraction_quartile.csv")

    # regime × teacher
    if "regime_label" in per_example_df.columns and "teacher_type" in per_example_df.columns:
        rows = []
        for (reg, teach), grp in per_example_df.groupby(["regime_label", "teacher_type"]):
            row: dict = {"regime_label": reg, "teacher_type": teach}
            for out_col, (src_col, fn) in _AGG_COLS.items():
                if src_col not in grp.columns:
                    row[out_col] = None
                    continue
                series = grp[src_col].dropna()
                if out_col == "mean_converged_at_round":
                    conv = grp[grp["converged"] == True]["converged_at_round"].dropna()
                    row[out_col] = float(conv.mean()) if len(conv) else None
                elif callable(fn):
                    row[out_col] = fn(grp[src_col]) if len(series) else None
                elif fn == "count":
                    row[out_col] = len(grp)
                else:
                    row[out_col] = getattr(series, fn)() if len(series) else None
            rows.append(row)
        if rows:
            pd.DataFrame(rows).to_csv(metrics_dir / "aggregate_by_regime_teacher.csv", index=False)
            logger.info("  Wrote aggregate_by_regime_teacher.csv")


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def write_summary_md(
    per_example_df: pd.DataFrame,
    traj_df: pd.DataFrame,
    run_dir: Path,
    run_id: str,
    metadata: dict,
    convergence_delta_e: float,
) -> None:
    n = len(per_example_df)
    n_conv = int(per_example_df["converged"].sum())
    mean_ie   = per_example_df["initial_error_lab"].mean()
    mean_fe   = per_example_df["final_error_lab"].mean()
    mean_rel  = per_example_df["relative_improvement"].mean()
    mean_csat = per_example_df["mean_constraint_satisfaction"].dropna().mean()
    mean_da   = per_example_df["mean_directional_alignment"].dropna().mean()
    mean_fb   = per_example_df["num_feedback_rounds_issued"].mean() if "num_feedback_rounds_issued" in per_example_df.columns else None
    parse_fail = int(per_example_df["parse_failure_count"].sum())

    model_alias = metadata.get("model", {}).get("alias", "?")
    model_name  = metadata.get("model", {}).get("model_name", "?")
    teacher     = metadata.get("teacher", {}).get("type", "?")
    max_turns   = metadata.get("execution", {}).get("max_turns", "?")
    subset_path = metadata.get("config", {})  # may not be in metadata

    lines = [
        f"# Evaluation summary: {run_id}", "",
        "## Metadata",
        f"- Run ID: `{run_id}`",
        f"- Model: `{model_alias}` (`{model_name}`)",
        f"- Teacher: `{teacher}`",
        f"- Max turns: {max_turns}",
        f"- Convergence threshold: ΔE < {convergence_delta_e}",
        "",
        "## Overall metrics",
        f"- Examples: {n}",
        f"- Converged: {n_conv} / {n} ({100 * n_conv / max(n, 1):.1f}%)",
        f"- Parse failures (all turns): {parse_fail}",
        f"- Mean initial ΔE: {mean_ie:.2f}",
        f"- Mean final ΔE: {mean_fe:.2f}",
        f"- Mean relative improvement: {mean_rel:.3f}",
        f"- Mean constraint satisfaction: {mean_csat:.3f}" if pd.notna(mean_csat) else "- Mean constraint satisfaction: n/a",
        f"- Mean directional alignment: {mean_da:.3f}" if pd.notna(mean_da) else "- Mean directional alignment: n/a",
        f"- Mean feedback rounds issued: {mean_fb:.2f}" if mean_fb is not None and pd.notna(mean_fb) else "- Mean feedback rounds issued: n/a",
        "",
    ]

    if "regime_label" in per_example_df.columns:
        lines += ["## Metrics by regime", ""]
        lines += ["| Regime | N | Init ΔE | Final ΔE | Rel imp | C-sat | Dir align |"]
        lines += ["|---|---:|---:|---:|---:|---:|---:|"]
        for regime, grp in per_example_df.groupby("regime_label"):
            csat  = grp["mean_constraint_satisfaction"].dropna().mean()
            align = grp["mean_directional_alignment"].dropna().mean()
            csat_str  = f"{csat:.3f}"  if pd.notna(csat)  else "n/a"
            align_str = f"{align:.3f}" if pd.notna(align) else "n/a"
            lines.append(
                f"| {regime} | {len(grp)} "
                f"| {grp['initial_error_lab'].mean():.2f} "
                f"| {grp['final_error_lab'].mean():.2f} "
                f"| {grp['relative_improvement'].mean():.3f} "
                f"| {csat_str} "
                f"| {align_str} |"
            )
        lines.append("")

    if "hue_bin" in per_example_df.columns:
        lines += ["## Metrics by hue bin", ""]
        lines += ["| Hue bin | N | Init ΔE | Final ΔE | Rel imp |"]
        lines += ["|---|---:|---:|---:|---:|"]
        for hbin, grp in per_example_df.groupby("hue_bin"):
            lines.append(
                f"| {hbin} | {len(grp)} "
                f"| {grp['initial_error_lab'].mean():.2f} "
                f"| {grp['final_error_lab'].mean():.2f} "
                f"| {grp['relative_improvement'].mean():.3f} |"
            )
        lines.append("")

    # Top improvements / regressions
    if len(per_example_df) >= 5:
        lines += ["## Top 10 largest improvements", ""]
        top = per_example_df.nlargest(10, "absolute_improvement")
        for _, row in top.iterrows():
            lines.append(f"- [{int(row.example_id)}] \"{row.raw_name}\" "
                         f"ΔE: {row.initial_error_lab:.1f} → {row.final_error_lab:.1f} "
                         f"(+{row.absolute_improvement:.1f})")
        lines.append("")
        lines += ["## Top 10 largest regressions", ""]
        worst = per_example_df.nsmallest(10, "absolute_improvement")
        for _, row in worst.iterrows():
            lines.append(f"- [{int(row.example_id)}] \"{row.raw_name}\" "
                         f"ΔE: {row.initial_error_lab:.1f} → {row.final_error_lab:.1f} "
                         f"({row.absolute_improvement:.1f})")
        lines.append("")

    # Random qualitative examples
    import random
    random.seed(42)
    sample = per_example_df.sample(min(5, len(per_example_df)), random_state=42)
    lines += ["## Qualitative examples (random sample)", ""]
    for _, row in sample.iterrows():
        sub_traj = traj_df[traj_df["example_id"] == row.example_id].sort_values("turn")
        lines.append(f"**[{int(row.example_id)}] \"{row.raw_name}\"**  ")
        lines.append(f"Target: `{row.true_hex}` | Regime: {row.regime_label}  ")
        for _, tr in sub_traj.iterrows():
            err_str = f"{tr['error_lab']:.1f}" if tr["error_lab"] is not None else "?"
            if tr["turn"] == 0:
                lines.append(f"- Turn 0 guess: `{tr['guess_hex']}` (ΔE={err_str})")
            else:
                lines.append(f"  - Feedback: _{tr['feedback_prev_text']}_")
                lines.append(f"- Turn {int(tr['turn'])} guess: `{tr['guess_hex']}` (ΔE={err_str})")
        lines.append(f"Initial ΔE={row.initial_error_lab:.1f}, Final ΔE={row.final_error_lab:.1f}, "
                     f"Rel imp={row.relative_improvement:.3f}")
        lines.append("")

    out_path = run_dir / "reports" / "eval_summary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Evaluation summary written to %s", out_path)


# ---------------------------------------------------------------------------
# Malformed outputs CSV
# ---------------------------------------------------------------------------

def write_malformed_outputs(traj_df: pd.DataFrame, reports_dir: Path) -> None:
    cols = ["example_id", "turn", "raw_response", "parse_reason"]
    for optional in ["prompt"]:
        if optional in traj_df.columns:
            cols.insert(2, optional)
    bad = traj_df[traj_df["parse_ok"] == False][cols].copy()
    if not bad.empty:
        bad.to_csv(reports_dir / "malformed_outputs.csv", index=False)
        logger.info("Malformed outputs: %d rows", len(bad))


# ---------------------------------------------------------------------------
# Single-run evaluation
# ---------------------------------------------------------------------------

def evaluate_single_run(run_dir: Path, convergence_delta_e: float = 5.0) -> dict:
    """Evaluate one run directory. Returns dict with DataFrames."""
    run_dir = Path(run_dir)
    run_id = run_dir.name

    traj_df, fb_df, metadata = load_run(run_dir)

    metrics_dir  = run_dir / "metrics"
    reports_dir  = run_dir / "reports"
    metrics_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    # Recompute convergence threshold from metadata if available
    exec_cfg = metadata.get("execution", {})
    conv_de = exec_cfg.get("convergence_delta_e", convergence_delta_e)
    max_turns_cfg = int(exec_cfg.get("max_turns", 3))
    seed = int(metadata.get("seed", 13))

    logger.info("Computing per-turn metrics…")
    per_turn_df = compute_per_turn(traj_df)
    per_turn_df.to_parquet(metrics_dir / "per_turn.parquet", index=False)

    logger.info("Computing per-example metrics…")
    per_example_df = compute_per_example(
        traj_df,
        fb_df,
        convergence_delta_e=conv_de,
        max_turns_configured=max_turns_cfg,
    )
    per_example_df.to_parquet(metrics_dir / "per_example.parquet", index=False)

    logger.info("Writing aggregate CSVs…")
    write_aggregates(per_example_df, metrics_dir, seed=seed)

    logger.info("Writing eval summary markdown…")
    write_summary_md(per_example_df, traj_df, run_dir, run_id, metadata, conv_de)

    logger.info("Writing malformed outputs report…")
    write_malformed_outputs(traj_df, reports_dir)

    logger.info("Done evaluating %s", run_id)
    return {
        "run_id":         run_id,
        "traj_df":        per_turn_df,
        "per_example_df": per_example_df,
    }


# ---------------------------------------------------------------------------
# Multi-run comparison
# ---------------------------------------------------------------------------

def evaluate_multi_run(run_dirs: list[Path], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_per_example = []
    all_traj = []

    for rd in run_dirs:
        result = evaluate_single_run(rd)
        pe = result["per_example_df"]
        pe["run_id"] = rd.name
        all_per_example.append(pe)
        traj = result["traj_df"]
        traj["run_id"] = rd.name
        all_traj.append(traj)

    combined_pe   = pd.concat(all_per_example, ignore_index=True)
    combined_traj = pd.concat(all_traj, ignore_index=True)

    combined_pe.to_parquet(out_dir / "combined_per_example.parquet", index=False)
    combined_traj.to_parquet(out_dir / "combined_per_turn.parquet", index=False)

    # Aggregate across all runs
    write_aggregates(combined_pe, out_dir)

    logger.info("Multi-run evaluation written to %s", out_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate one or more completed run directories.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--run_dir", type=Path,
                       help="Single run directory to evaluate")
    group.add_argument("--run_dirs", type=Path, nargs="+",
                       help="Multiple run directories for comparison")
    p.add_argument("--out_dir", type=Path, default=None,
                   help="Output directory for multi-run comparison (default: reports/comparisons/<timestamp>)")
    p.add_argument("--convergence_delta_e", type=float, default=5.0,
                   help="ΔE threshold for convergence")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.run_dir:
        evaluate_single_run(args.run_dir, convergence_delta_e=args.convergence_delta_e)
    else:
        from datetime import datetime, timezone
        out_dir = args.out_dir or Path("reports/comparisons") / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        evaluate_multi_run(args.run_dirs, out_dir)


if __name__ == "__main__":
    main()
