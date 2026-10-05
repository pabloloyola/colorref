"""Aggregate and compare information-budget ablation runs.

Usage:
    uv run python scripts/compare_information_budget.py \\
        --run_dirs runs/*budget_axis* \\
        --out_dir reports/comparisons/information_budget
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.budget import BUDGET_CONDITIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "figure.dpi": 150,
})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare information-budget ablation runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run_dirs", nargs="+", required=True)
    p.add_argument("--out_dir", default="reports/comparisons/information_budget")
    p.add_argument("--figures_dir", default=None)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_run_dirs(patterns: list[str]) -> list[Path]:
    result = []
    for pat in patterns:
        matches = sorted(glob.glob(pat))
        for m in matches:
            p = Path(m)
            if p.is_dir() and (p / "games" / "trajectories.parquet").exists():
                result.append(p)
        if not matches:
            p = Path(pat)
            if p.is_dir() and (p / "games" / "trajectories.parquet").exists():
                result.append(p)
    return sorted(set(result))


def _load_run_meta(run_dir: Path) -> dict:
    config_path = run_dir / "config.yaml"
    meta: dict = {"run_id": run_dir.name}
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        teacher_cfg = cfg.get("teacher", {})
        exec_cfg = cfg.get("execution", {})
        meta.update({
            "experiment_name": cfg.get("experiment_name", run_dir.name),
            "budget_condition": teacher_cfg.get("budget_condition", "unknown"),
            "total_budget": teacher_cfg.get("total_constraint_budget", None),
            "max_c_per_turn": teacher_cfg.get("max_feedback_constraints", None),
            "max_turns": exec_cfg.get("max_turns", None),
        })
    return meta


def _load_per_example(run_dir: Path, meta: dict) -> pd.DataFrame:
    """Load per-example data, prioritizing pre-computed budget metrics."""
    bm_path = run_dir / "metrics" / "budget_metrics.parquet"
    es_path = run_dir / "games" / "example_summaries.parquet"

    if bm_path.exists():
        bm = pd.read_parquet(bm_path)
    else:
        bm = pd.DataFrame()

    if es_path.exists():
        es = pd.read_parquet(es_path)
    else:
        # Build from trajectories
        traj = pd.read_parquet(run_dir / "games" / "trajectories.parquet")
        es = _summarize_from_traj(traj)

    if not bm.empty and not es.empty:
        merged = es.merge(bm, on="example_id", how="outer", suffixes=("", "_bm"))
        # Prefer budget metrics columns when available
        for col in bm.columns:
            if col != "example_id" and col in merged:
                pass
        df = merged
    elif not bm.empty:
        df = bm
    else:
        df = es

    for k, v in meta.items():
        if k not in df.columns:
            df[k] = v

    return df


def _summarize_from_traj(traj: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for eid, group in traj.groupby("example_id"):
        group = group.sort_values("turn")
        errors = group["error_lab"].dropna().values
        if len(errors) == 0:
            continue
        rows.append({
            "example_id": eid,
            "initial_error_lab": float(errors[0]),
            "final_error_lab": float(errors[-1]),
            "best_error_lab": float(errors.min()),
            "regime_label": str(group.iloc[0].get("regime_label", "")),
            "raw_name": str(group.iloc[0].get("raw_name", "")),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

_CONDITION_ORDER = [
    "one_turn_c1", "one_turn_c2", "one_turn_c3",
    "two_turn_c1", "two_turn_c2",
    "three_turn_c1", "three_turn_c2", "three_turn_c3",
]

_MATCHED_PAIRS = [
    ("one_turn_c3", "three_turn_c1", "budget=3"),
    ("one_turn_c2", "two_turn_c1",   "budget=2"),
]


def _condition_label(cond: str) -> str:
    info = BUDGET_CONDITIONS.get(cond, {})
    r = info.get("rounds", "?")
    c = info.get("max_c_per_turn", "?")
    b = info.get("total_budget", "?")
    return f"{cond}\n(r={r},c={c},B={b})"


def _save_fig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = Path(args.figures_dir) if args.figures_dir else out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = _expand_run_dirs(args.run_dirs)
    logger.info("Found %d valid run dirs:", len(run_dirs))
    for rd in run_dirs:
        logger.info("  %s", rd.name)

    if not run_dirs:
        logger.error("No valid run dirs found.")
        sys.exit(1)

    all_per_ex: list[pd.DataFrame] = []
    all_per_turn: list[pd.DataFrame] = []

    for run_dir in run_dirs:
        meta = _load_run_meta(run_dir)
        per_ex = _load_per_example(run_dir, meta)
        all_per_ex.append(per_ex)

        traj_path = run_dir / "games" / "trajectories.parquet"
        traj = pd.read_parquet(traj_path)
        traj["budget_condition"] = meta.get("budget_condition", "unknown")
        traj["total_budget"] = meta.get("total_budget")
        traj["max_turns"] = meta.get("max_turns")
        all_per_turn.append(traj)

    combined_pe = pd.concat(all_per_ex, ignore_index=True)
    combined_traj = pd.concat(all_per_turn, ignore_index=True)

    combined_pe.to_parquet(out_dir / "combined_per_example.parquet", index=False)
    combined_traj.to_parquet(out_dir / "combined_per_turn.parquet", index=False)

    # ----------------------------------------------------------------
    # Aggregates
    # ----------------------------------------------------------------
    grp_cols = ["budget_condition", "total_budget", "max_turns"]
    grp_cols_present = [c for c in grp_cols if c in combined_pe.columns]

    agg_cols = {}
    if "initial_error_lab" in combined_pe.columns:
        agg_cols["mean_initial_error"] = ("initial_error_lab", "mean")
    if "final_error_lab" in combined_pe.columns:
        agg_cols["mean_final_error"] = ("final_error_lab", "mean")
    if "best_error_lab" in combined_pe.columns:
        agg_cols["mean_best_error"] = ("best_error_lab", "mean")
    if "improvement_per_constraint" in combined_pe.columns:
        agg_cols["mean_imp_per_constraint"] = ("improvement_per_constraint", "mean")
    agg_cols["n"] = ("example_id" if "example_id" in combined_pe.columns else grp_cols_present[0], "count")

    if grp_cols_present and agg_cols:
        agg = combined_pe.groupby(grp_cols_present).agg(**agg_cols).reset_index()
        agg.to_csv(out_dir / "aggregate_by_budget_condition.csv", index=False)
        logger.info("aggregate_by_budget_condition.csv")

    # By total budget
    if "total_budget" in combined_pe.columns:
        agg_by_budget = combined_pe.groupby("total_budget").agg(
            mean_final_error=("final_error_lab", "mean") if "final_error_lab" in combined_pe.columns else ("example_id", "count"),
        ).reset_index()
        agg_by_budget.to_csv(out_dir / "aggregate_by_total_budget.csv", index=False)

    # By rounds (max_turns)
    if "max_turns" in combined_pe.columns and "final_error_lab" in combined_pe.columns:
        agg_by_rounds = combined_pe.groupby("max_turns").agg(
            mean_final_error=("final_error_lab", "mean"),
        ).reset_index()
        agg_by_rounds.to_csv(out_dir / "aggregate_by_rounds.csv", index=False)

    # Regime × budget
    if "regime_label" in combined_pe.columns and "budget_condition" in combined_pe.columns:
        if "final_error_lab" in combined_pe.columns:
            agg_regime = combined_pe.groupby(["regime_label", "budget_condition"]).agg(
                mean_final_error=("final_error_lab", "mean"),
            ).reset_index()
            agg_regime.to_csv(out_dir / "aggregate_by_regime_budget.csv", index=False)

    # ----------------------------------------------------------------
    # Figures
    # ----------------------------------------------------------------
    if "budget_condition" in combined_pe.columns and "final_error_lab" in combined_pe.columns:
        present_conditions = [c for c in _CONDITION_ORDER if c in combined_pe["budget_condition"].values]
        sub = combined_pe[combined_pe["budget_condition"].isin(present_conditions)]

        # 1. Final error by total budget
        if "total_budget" in sub.columns:
            fig, ax = plt.subplots(figsize=(7, 4))
            for mt, grp in sub.groupby("max_turns"):
                by_budget = grp.groupby("total_budget")["final_error_lab"].mean().reset_index()
                ax.plot(by_budget["total_budget"], by_budget["final_error_lab"],
                        "o-", label=f"{int(mt)} rounds", ms=6, linewidth=1.8)
            ax.set_xlabel("Total constraint budget")
            ax.set_ylabel("Mean final ΔE (LAB)")
            ax.set_title("Final error by total constraint budget")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            _save_fig(fig, figures_dir / "final_error_by_total_budget.png")

        # 2. Final error by rounds and constraints per turn
        if "max_turns" in sub.columns and "max_c_per_turn" in sub.columns:
            fig, ax = plt.subplots(figsize=(8, 4))
            cmap = plt.cm.viridis
            cvals = {v: cmap(i/3) for i, v in enumerate([1, 2, 3])}
            for c_val, grp in sub.groupby("max_c_per_turn"):
                by_rounds = grp.groupby("max_turns")["final_error_lab"].mean().reset_index()
                color = cvals.get(int(c_val), "gray")
                ax.plot(by_rounds["max_turns"], by_rounds["final_error_lab"],
                        "o-", color=color, label=f"c/turn={int(c_val)}", ms=6, linewidth=1.8)
            ax.set_xlabel("Number of feedback rounds")
            ax.set_ylabel("Mean final ΔE (LAB)")
            ax.set_title("Final error by rounds × constraints/turn")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            _save_fig(fig, figures_dir / "final_error_by_rounds_and_constraints.png")

        # 3. Improvement per constraint
        if "improvement_per_constraint" in sub.columns:
            fig, ax = plt.subplots(figsize=(8, 4))
            by_cond = sub.groupby("budget_condition")["improvement_per_constraint"].mean()
            by_cond = by_cond.reindex([c for c in present_conditions if c in by_cond.index])
            xs = range(len(by_cond))
            ax.bar(xs, by_cond.values, color="#5C6BC0", edgecolor="white")
            ax.set_xticks(list(xs))
            ax.set_xticklabels([_condition_label(c) for c in by_cond.index], fontsize=7, rotation=15)
            ax.set_ylabel("ΔE improvement per constraint")
            ax.set_title("Efficiency: improvement per constraint issued")
            ax.grid(True, alpha=0.3, axis="y")
            fig.tight_layout()
            _save_fig(fig, figures_dir / "improvement_per_constraint.png")

        # 4. Matched-budget comparison: one_turn_c3 vs three_turn_c1
        for cond_a, cond_b, label in _MATCHED_PAIRS:
            if cond_a not in sub["budget_condition"].values or cond_b not in sub["budget_condition"].values:
                continue
            pair = sub[sub["budget_condition"].isin([cond_a, cond_b])]
            fig, ax = plt.subplots(figsize=(5, 4))
            means = pair.groupby("budget_condition")["final_error_lab"].mean()
            colors = {"one_turn_c3": "#EF5350", "three_turn_c1": "#26A69A",
                      "one_turn_c2": "#FFA726", "two_turn_c1": "#5C6BC0"}
            for cond in [cond_a, cond_b]:
                if cond in means:
                    ax.bar(cond, means[cond], color=colors.get(cond, "gray"), edgecolor="white",
                           label=f"{cond} (ΔE={means[cond]:.1f})")
            ax.set_ylabel("Mean final ΔE (LAB)")
            ax.set_title(f"Matched budget ({label}): iterative vs single-turn")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3, axis="y")
            fig.tight_layout()
            fname = f"{cond_a}_vs_{cond_b}.png"
            _save_fig(fig, figures_dir / fname)
            logger.info("Saved %s", fname)

    # ----------------------------------------------------------------
    # Combined report
    # ----------------------------------------------------------------
    lines = [
        "# Information Budget Ablation — Combined Report",
        "",
        f"**Runs**: {len(run_dirs)}",
        "",
        "## Budget Conditions",
        "",
        "| Condition | Rounds | Max c/turn | Total budget |",
        "|---|---|---|---|",
    ]
    for cond, info in BUDGET_CONDITIONS.items():
        lines.append(f"| {cond} | {info['rounds']} | {info['max_c_per_turn']} | {info['total_budget']} |")

    lines += [
        "",
        "## Aggregate Results",
        "",
    ]
    if "budget_condition" in combined_pe.columns and "final_error_lab" in combined_pe.columns:
        by_cond = combined_pe.groupby("budget_condition")["final_error_lab"].agg(["mean", "std", "count"])
        lines.append("| Condition | Mean final ΔE | Std | n |")
        lines.append("|---|---|---|---|")
        for cond, row in by_cond.iterrows():
            lines.append(f"| {cond} | {row['mean']:.2f} | {row['std']:.2f} | {int(row['count'])} |")

    lines += [
        "",
        "## Paper-Facing Questions",
        "",
        "1. **With total budget=3: one_turn_c3 vs three_turn_c1?**",
        "   → See `one_turn_c3_vs_three_turn_c1.png` and aggregate_by_budget_condition.csv",
        "",
        "2. **Does iterative feedback help because it conditions later feedback?**",
        "   → Compare matched-budget pairs (one-turn vs multi-turn same total budget)",
        "",
        "3. **High-bandwidth single-turn vs multi-turn?**",
        "   → Compare one_turn_c3 (B=3) vs three_turn_c1 (B=3)",
        "",
        "4. **Marginal improvement per constraint?**",
        "   → See improvement_per_constraint.png",
        "",
        "## Figures",
        "",
        "- `figures/final_error_by_total_budget.png`",
        "- `figures/final_error_by_rounds_and_constraints.png`",
        "- `figures/improvement_per_constraint.png`",
        "- `figures/one_turn_c3_vs_three_turn_c1.png`",
        "- `figures/one_turn_c2_vs_two_turn_c1.png`",
    ]

    (out_dir / "combined_report.md").write_text("\n".join(lines))
    logger.info("Written combined_report.md")
    print(f"\nDone. Results in {out_dir}")


if __name__ == "__main__":
    main()
