"""Detailed run summary report (spec §19).

Produces a rich markdown report for a completed run including qualitative
examples, top improvements/failures, and per-regime metrics tables.

Usage:
    uv run python scripts/summarize_runs.py \
        --run_dir runs/20260516_121822_feedback_minimal_main_qwen3_14b_minimal_oracle_main_1000

    uv run python scripts/summarize_runs.py \
        --run_dirs runs/run_a runs/run_b \
        --out_dir reports/summaries
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
        description="Write a detailed run summary markdown (spec §19).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--run_dir",  help="Single run directory")
    grp.add_argument("--run_dirs", nargs="+", help="Multiple run directories")
    p.add_argument("--out_dir", default=None,
                   help="Output directory (default: <run_dir>/reports/)")
    p.add_argument("--top_n",    type=int, default=20, help="Examples in top/bottom tables")
    p.add_argument("--random_n", type=int, default=10, help="Random qualitative examples")
    p.add_argument("--seed",     type=int, default=13)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_run_data(run_dir: Path) -> dict:
    """Load all available data from a run directory."""
    data: dict = {"run_dir": run_dir, "run_id": run_dir.name}

    meta_path = run_dir / "metadata.json"
    data["metadata"] = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    cfg_path = run_dir / "config.yaml"
    data["config"] = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}

    # Trajectories (prefer per-example summary for speed)
    per_ex_path = run_dir / "metrics" / "per_example.parquet"
    traj_path   = run_dir / "games"   / "trajectories.parquet"
    fb_path     = run_dir / "games"   / "feedback.parquet"

    data["per_example"] = pd.read_parquet(per_ex_path) if per_ex_path.exists() else pd.DataFrame()
    data["trajectories"] = pd.read_parquet(traj_path)  if traj_path.exists()   else pd.DataFrame()
    data["feedback"]     = pd.read_parquet(fb_path)    if fb_path.exists()      else pd.DataFrame()

    # Subset info
    subset_path = run_dir / "inputs" / "subset.parquet"
    data["subset"] = pd.read_parquet(subset_path) if subset_path.exists() else pd.DataFrame()

    return data


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _s(text: str) -> list[str]:
    return [text, ""]


def section_metadata(data: dict) -> list[str]:
    meta = data["metadata"]
    cfg  = data["config"]
    lines = ["## 1. Run metadata", ""]
    lines += [f"- **Run ID:** `{data['run_id']}`"]
    if meta.get("created_at"):
        lines += [f"- **Created:** {meta['created_at']}"]
    if meta.get("experiment_name"):
        lines += [f"- **Experiment:** `{meta['experiment_name']}`"]
    if meta.get("seed") is not None:
        lines += [f"- **Seed:** {meta['seed']}"]
    return lines + [""]


def section_config(data: dict) -> list[str]:
    cfg = data["config"]
    if not cfg:
        return []
    lines = ["## 2. Config summary", "", "```yaml"]
    lines += yaml.dump(cfg, default_flow_style=False).splitlines()
    lines += ["```", ""]
    return lines


def section_subset(data: dict) -> list[str]:
    sub = data["subset"]
    if sub.empty:
        return []
    lines = ["## 3. Dataset subset", ""]
    lines += [f"- **Total examples:** {len(sub)}"]
    if "regime_label" in sub.columns:
        lines += ["", "| Regime | N |", "|---|---:|"]
        for r, n in sub["regime_label"].value_counts().sort_index().items():
            lines += [f"| {r} | {n} |"]
    lines += [""]
    return lines


def section_model(data: dict) -> list[str]:
    cfg = data["config"]
    mdl = cfg.get("model", {})
    if not mdl:
        return []
    lines = ["## 4. Model settings", ""]
    for k, v in mdl.items():
        lines += [f"- **{k}:** `{v}`"]
    return lines + [""]


def section_teacher(data: dict) -> list[str]:
    cfg = data["config"]
    tch = cfg.get("teacher", {})
    if not tch:
        return []
    lines = ["## 5. Teacher settings", ""]
    for k, v in tch.items():
        lines += [f"- **{k}:** `{v}`"]
    return lines + [""]


def section_parse_rate(data: dict) -> list[str]:
    df = data["per_example"]
    if df.empty or "parse_failure_count" not in df.columns:
        return []
    total = len(df)
    fails = int(df["parse_failure_count"].sum())
    rate  = 1.0 - fails / max(total, 1)
    lines = ["## 6. Parse success rate", ""]
    lines += [
        f"- **Total examples:** {total}",
        f"- **Total parse failures:** {fails}",
        f"- **Parse success rate:** {rate:.1%}",
    ]
    return lines + [""]


def section_overall_metrics(data: dict) -> list[str]:
    df = data["per_example"]
    if df.empty:
        return []
    lines = ["## 7. Overall metrics", ""]

    def _fmt(col: str) -> str:
        return f"{df[col].mean():.3f}" if col in df.columns else "n/a"

    n_conv = int(df["converged"].sum()) if "converged" in df.columns else 0
    lines += [
        f"- **N:** {len(df)}",
        f"- **Converged:** {n_conv} ({100*n_conv/max(len(df),1):.1f}%)",
        f"- **Mean initial ΔE:** {_fmt('initial_error_lab')}",
        f"- **Mean final ΔE:** {_fmt('final_error_lab')}",
        f"- **Mean relative improvement:** {_fmt('relative_improvement')}",
        f"- **Mean constraint satisfaction:** {_fmt('mean_constraint_satisfaction')}",
        f"- **Mean directional alignment:** {_fmt('mean_directional_alignment')}",
    ]
    return lines + [""]


def section_by_regime(data: dict) -> list[str]:
    df = data["per_example"]
    if df.empty or "regime_label" not in df.columns:
        return []
    lines = ["## 8. Metrics by regime", ""]
    lines += ["| Regime | N | Init ΔE | Final ΔE | Rel imp | C-sat | Dir align |"]
    lines += ["|---|---:|---:|---:|---:|---:|---:|"]
    for regime, g in df.groupby("regime_label"):
        cs    = g["mean_constraint_satisfaction"].mean() if "mean_constraint_satisfaction" in g else float("nan")
        da    = g["mean_directional_alignment"].mean()   if "mean_directional_alignment"   in g else float("nan")
        ie    = g["initial_error_lab"].mean()            if "initial_error_lab" in g            else float("nan")
        fe    = g["final_error_lab"].mean()              if "final_error_lab"   in g            else float("nan")
        ri    = g["relative_improvement"].mean()         if "relative_improvement" in g         else float("nan")
        lines += [f"| {regime} | {len(g)} | {ie:.2f} | {fe:.2f} | {ri:+.3f} | "
                  f"{'n/a' if pd.isna(cs) else f'{cs:.3f}'} | "
                  f"{'n/a' if pd.isna(da) else f'{da:.3f}'} |"]
    return lines + [""]


def section_by_abstraction_quartile(data: dict) -> list[str]:
    df = data["per_example"]
    if df.empty or "abstraction_score" not in df.columns:
        return []
    df = df.copy()
    df["abst_q"] = pd.qcut(df["abstraction_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
    lines = ["## 9. Metrics by abstraction quartile", ""]
    lines += ["| Quartile | N | Mean final ΔE | Rel imp |"]
    lines += ["|---|---:|---:|---:|"]
    for q, g in df.groupby("abst_q", observed=True):
        fe = g["final_error_lab"].mean() if "final_error_lab" in g else float("nan")
        ri = g["relative_improvement"].mean() if "relative_improvement" in g else float("nan")
        lines += [f"| {q} | {len(g)} | {fe:.2f} | {ri:+.3f} |"]
    return lines + [""]


def section_by_color_bin(data: dict) -> list[str]:
    df = data["per_example"]
    if df.empty or "hue_bin" not in df.columns:
        return []
    lines = ["## 10. Metrics by color bin", ""]

    for bin_col, title in [("hue_bin", "Hue"), ("lightness_bin", "Lightness"), ("saturation_bin", "Saturation")]:
        if bin_col not in df.columns:
            continue
        lines += [f"### {title} bins", ""]
        lines += ["| Bin | N | Mean final ΔE | Rel imp |"]
        lines += ["|---|---:|---:|---:|"]
        for b, g in df.groupby(bin_col):
            fe = g["final_error_lab"].mean() if "final_error_lab" in g else float("nan")
            ri = g["relative_improvement"].mean() if "relative_improvement" in g else float("nan")
            lines += [f"| {b} | {len(g)} | {fe:.2f} | {ri:+.3f} |"]
        lines += [""]
    return lines


def section_top_n(data: dict, top_n: int) -> list[str]:
    df = data["per_example"]
    if df.empty or "absolute_improvement" not in df.columns:
        return []
    lines = [f"## 11. Top {top_n} largest improvements", ""]
    for _, row in df.nlargest(top_n, "absolute_improvement").iterrows():
        name = str(row.get("raw_name", "?")).replace("|", "\\|")
        ie = row.get("initial_error_lab", float("nan"))
        fe = row.get("final_error_lab",   float("nan"))
        ai = row.get("absolute_improvement", float("nan"))
        lines += [f"- [{int(row['example_id'])}] \"{name}\" — ΔE: {ie:.1f} → {fe:.1f} (+{ai:.1f})"]
    lines += [""]

    lines += [f"## 12. Top {top_n} largest failures / regressions", ""]
    for _, row in df.nsmallest(top_n, "absolute_improvement").iterrows():
        name = str(row.get("raw_name", "?")).replace("|", "\\|")
        ie = row.get("initial_error_lab", float("nan"))
        fe = row.get("final_error_lab",   float("nan"))
        ai = row.get("absolute_improvement", float("nan"))
        lines += [f"- [{int(row['example_id'])}] \"{name}\" — ΔE: {ie:.1f} → {fe:.1f} ({ai:.1f})"]
    lines += [""]
    return lines


def section_qualitative(data: dict, n: int, seed: int) -> list[str]:
    traj = data["trajectories"]
    fb   = data["feedback"]
    per_ex = data["per_example"]

    if traj.empty:
        return []

    # Pick examples: mix of good, bad, random
    example_ids = traj["example_id"].unique().tolist()
    rng = random.Random(seed)
    sample_ids = rng.sample(example_ids, min(n, len(example_ids)))

    lines = [f"## 13. Qualitative examples ({len(sample_ids)} random)", ""]

    for eid in sample_ids:
        ex_traj = traj[traj["example_id"] == eid].sort_values("turn")
        ex_fb   = fb[fb["example_id"] == eid].sort_values("turn") if not fb.empty else pd.DataFrame()
        ex_meta = per_ex[per_ex["example_id"] == eid].iloc[0] if not per_ex.empty and eid in per_ex["example_id"].values else None

        row0 = ex_traj.iloc[0]
        name = str(row0.get("raw_name", "?"))
        true_hex = str(row0.get("true_hex", "?"))
        regime = str(row0.get("regime_label", "?"))

        lines += [
            f"### Example {eid}: \"{name}\"",
            f"- **Target:** `{true_hex}`  |  **Regime:** {regime}",
        ]
        if ex_meta is not None and pd.notna(ex_meta.get("initial_error_lab")):
            ie = ex_meta["initial_error_lab"]
            fe = ex_meta.get("final_error_lab", ie)
            ri = ex_meta.get("relative_improvement", 0.0)
            lines += [f"- **ΔE:** {ie:.1f} → {fe:.1f}  |  **Rel imp:** {ri:+.3f}"]
        lines += [""]

        for _, turn_row in ex_traj.iterrows():
            t = int(turn_row["turn"])
            g_hex = str(turn_row.get("guess_hex", "?"))
            err   = turn_row.get("error_lab")
            err_s = f"ΔE={err:.1f}" if pd.notna(err) else "ΔE=?"
            lines += [f"- **Turn {t} guess:** `{g_hex}` ({err_s})"]

            # Feedback given after this turn
            if not ex_fb.empty:
                fb_row = ex_fb[ex_fb["turn"] == t]
                if len(fb_row) > 0:
                    fb_text = str(fb_row.iloc[0].get("feedback_text", ""))
                    if fb_text:
                        lines += [f"  - *Feedback:* {fb_text}"]

        lines += [""]

    return lines


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

def build_report(data: dict, top_n: int, random_n: int, seed: int) -> str:
    run_id = data["run_id"]
    sections = [
        [f"# Run summary: {run_id}", ""],
        section_metadata(data),
        section_config(data),
        section_subset(data),
        section_model(data),
        section_teacher(data),
        section_parse_rate(data),
        section_overall_metrics(data),
        section_by_regime(data),
        section_by_abstraction_quartile(data),
        section_by_color_bin(data),
        section_top_n(data, top_n),
        section_qualitative(data, random_n, seed),
    ]
    lines: list[str] = []
    for sec in sections:
        lines.extend(sec)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    run_dirs = [Path(args.run_dir)] if args.run_dir else [Path(d) for d in args.run_dirs]

    for run_dir in run_dirs:
        logger.info("Summarizing %s …", run_dir.name)
        data = load_run_data(run_dir)

        out_dir = Path(args.out_dir) if args.out_dir else run_dir / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)

        report = build_report(data, top_n=args.top_n, random_n=args.random_n, seed=args.seed)
        out_path = out_dir / "run_summary_full.md"
        out_path.write_text(report, encoding="utf-8")
        logger.info("Written: %s", out_path)


if __name__ == "__main__":
    main()
