"""Generate the figures missing from the initial comparison runs.

Missing figures to produce:
  convergence:  regime_error_by_turn_long.png + aggregate_by_regime_turn.csv
  icl:          icl_relative_improvement_by_k.png
                icl_by_regime.png
                icl_feedback_vs_oneshot.png
  budget:       regime_by_budget_condition.png
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
    "axes.labelsize": 9,
    "figure.dpi": 150,
})

ROOT = Path(__file__).resolve().parents[1]
CONV_DIR  = ROOT / "reports/comparisons/convergence_sweep"
ICL_DIR   = ROOT / "reports/comparisons/icl_calibration"
BUDGET_DIR = ROOT / "reports/comparisons/information_budget"
DATA_PATH = ROOT / "data/eval_subsets/main_1000.parquet"


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    logger.info("Saved %s", path.name)


# ---------------------------------------------------------------------------
# A. Convergence — regime breakdown
# ---------------------------------------------------------------------------

def make_convergence_regime_figure() -> None:
    pe = pd.read_parquet(CONV_DIR / "combined_per_example.parquet")

    if "regime_label" not in pe.columns:
        if DATA_PATH.exists():
            ref = pd.read_parquet(DATA_PATH)[["example_id", "regime_label"]]
            pe = pe.merge(ref, on="example_id", how="left")
        else:
            logger.warning("No regime_label in convergence data and data path not found — skipping")
            return

    if "regime_label" not in pe.columns or pe["regime_label"].isna().all():
        logger.warning("regime_label still missing after join — skipping convergence regime figure")
        return

    # aggregate_by_regime_turn.csv
    agg = (
        pe.groupby(["max_turns", "regime_label"])
        .agg(
            mean_final_error=("final_error", "mean"),
            mean_best_error=("best_error", "mean"),
            n=("example_id", "count"),
        )
        .reset_index()
    )
    out_csv = CONV_DIR / "aggregate_by_regime_turn.csv"
    agg.to_csv(out_csv, index=False)
    logger.info("Written %s", out_csv.name)

    # Figure: lines per regime, x=max_turns
    regimes = sorted(pe["regime_label"].dropna().unique())
    max_turns_list = sorted(pe["max_turns"].unique())
    cmap = plt.cm.tab10
    colors = {r: cmap(i / max(len(regimes) - 1, 1)) for i, r in enumerate(regimes)}

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for regime in regimes:
        sub = agg[agg["regime_label"] == regime].sort_values("max_turns")
        ax.plot(sub["max_turns"], sub["mean_final_error"], "o-",
                color=colors[regime], label=regime, linewidth=1.6, ms=5)
    ax.set_xlabel("max_turns")
    ax.set_ylabel("Mean final ΔE (LAB)")
    ax.set_title("Convergence sweep: final error by regime and max_turns")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save(fig, CONV_DIR / "figures/regime_error_by_turn_long.png")


# ---------------------------------------------------------------------------
# B. ICL — three missing figures
# ---------------------------------------------------------------------------

def make_icl_figures() -> None:
    pe = pd.read_parquet(ICL_DIR / "combined_per_example.parquet")

    error_col = "error_lab" if "error_lab" in pe.columns else "final_error_lab"
    init_col = "initial_error_lab" if "initial_error_lab" in pe.columns else None
    rel_col = "relative_improvement" if "relative_improvement" in pe.columns else None

    figs_dir = ICL_DIR / "figures"
    figs_dir.mkdir(exist_ok=True)

    # ---- 1. Relative improvement by k (oneshot and feedback side-by-side) ----
    if rel_col and "k_shot" in pe.columns and "experiment_type" in pe.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        for exp_type, marker in [("oneshot", "o--"), ("feedback", "s-")]:
            sub = pe[pe["experiment_type"] == exp_type]
            if sub.empty:
                continue
            by_k = sub.groupby("k_shot")[rel_col].mean()
            ax.plot(by_k.index, by_k.values * 100, marker,
                    label=exp_type, linewidth=1.8, ms=6)
        ax.axhline(0, color="gray", linewidth=0.8, linestyle=":")
        ax.set_xlabel("k-shot (number of in-context examples)")
        ax.set_ylabel("Mean relative improvement (%)")
        ax.set_title("ICL: relative improvement by k-shot")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        _save(fig, figs_dir / "icl_relative_improvement_by_k.png")

    # ---- 2. Error by regime and k ----
    if "regime_label" in pe.columns and "k_shot" in pe.columns:
        regimes = sorted(pe["regime_label"].dropna().unique())
        cmap = plt.cm.tab10
        colors = {r: cmap(i / max(len(regimes) - 1, 1)) for i, r in enumerate(regimes)}

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        for ax, exp_type in zip(axes, ["oneshot", "feedback"]):
            sub = pe[pe["experiment_type"] == exp_type] if "experiment_type" in pe.columns else pe
            for regime in regimes:
                rsub = sub[sub["regime_label"] == regime]
                if rsub.empty:
                    continue
                by_k = rsub.groupby("k_shot")[error_col].mean()
                ax.plot(by_k.index, by_k.values, "o-",
                        color=colors[regime], label=regime, linewidth=1.5, ms=5)
            ax.set_xlabel("k-shot")
            ax.set_ylabel("Mean ΔE (LAB)")
            ax.set_title(f"ICL {exp_type}: error by regime and k")
            ax.legend(fontsize=6, ncol=2)
            ax.grid(True, alpha=0.3)
        fig.tight_layout()
        _save(fig, figs_dir / "icl_by_regime.png")

    # ---- 3. Feedback vs oneshot comparison (k-shot on x-axis) ----
    if "experiment_type" in pe.columns and "k_shot" in pe.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        for exp_type, color, marker in [
            ("oneshot",  "#EF5350", "o--"),
            ("feedback", "#26A69A", "s-"),
        ]:
            sub = pe[pe["experiment_type"] == exp_type]
            if sub.empty:
                continue
            by_k = sub.groupby("k_shot")[error_col].mean()
            ax.plot(by_k.index, by_k.values, marker,
                    color=color, label=exp_type, linewidth=1.8, ms=6)
        ax.set_xlabel("k-shot")
        ax.set_ylabel("Mean ΔE (LAB)")
        ax.set_title("ICL: one-shot vs feedback game — error by k")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        _save(fig, figs_dir / "icl_feedback_vs_oneshot.png")


# ---------------------------------------------------------------------------
# C. Budget — regime breakdown
# ---------------------------------------------------------------------------

def make_budget_regime_figure() -> None:
    pe = pd.read_parquet(BUDGET_DIR / "combined_per_example.parquet")

    if "regime_label" not in pe.columns or "budget_condition" not in pe.columns:
        logger.warning("Missing required columns — skipping budget regime figure")
        return

    _CONDITION_ORDER = [
        "one_turn_c1", "one_turn_c2", "one_turn_c3",
        "two_turn_c1", "two_turn_c2",
        "three_turn_c1", "three_turn_c3",
    ]
    present = [c for c in _CONDITION_ORDER if c in pe["budget_condition"].values]
    sub = pe[pe["budget_condition"].isin(present)]

    regimes = sorted(sub["regime_label"].dropna().unique())
    cmap = plt.cm.tab10
    colors = {r: cmap(i / max(len(regimes) - 1, 1)) for i, r in enumerate(regimes)}

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = np.arange(len(present))
    width = 0.8 / max(len(regimes), 1)

    for i, regime in enumerate(regimes):
        rsub = sub[sub["regime_label"] == regime]
        means = [
            rsub[rsub["budget_condition"] == c]["final_error_lab"].mean()
            for c in present
        ]
        offset = (i - len(regimes) / 2 + 0.5) * width
        ax.bar(x + offset, means, width, label=regime,
               color=colors[regime], edgecolor="white", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(present, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Mean final ΔE (LAB)")
    ax.set_title("Information budget: final error by regime and condition")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    _save(fig, BUDGET_DIR / "figures/regime_by_budget_condition.png")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== Convergence: regime breakdown ===")
    make_convergence_regime_figure()

    logger.info("=== ICL: missing figures ===")
    make_icl_figures()

    logger.info("=== Budget: regime breakdown ===")
    make_budget_regime_figure()

    logger.info("All missing figures generated.")


if __name__ == "__main__":
    main()
