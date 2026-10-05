"""Plotting utilities for the ColorRef experiment pipeline.

Generates the paper-facing figures from run metrics tables.
All functions accept DataFrames and write PNG (and PDF when possible)
to a given output directory.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_PALETTE = [
    "#2196F3", "#FF5722", "#4CAF50", "#9C27B0",
    "#FF9800", "#00BCD4", "#E91E63", "#607D8B",
]
_REGIME_ORDER = [
    "explicit_grounded",
    "prototype_mediated",
    "compound_associative",
    "abstract_idiosyncratic",
]
_REGIME_LABELS = {
    "explicit_grounded": "Explicit",
    "prototype_mediated": "Prototype",
    "compound_associative": "Compound",
    "abstract_idiosyncratic": "Abstract",
}


def _save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{stem}.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    try:
        fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)


def _regime_color(regime: str) -> str:
    idx = _REGIME_ORDER.index(regime) if regime in _REGIME_ORDER else 0
    return _PALETTE[idx % len(_PALETTE)]


# ---------------------------------------------------------------------------
# 1. Error by turn
# ---------------------------------------------------------------------------

def plot_error_by_turn(
    traj_df: pd.DataFrame,
    out_dir: Path,
    *,
    group_col: str = "regime_label",
    stem: str = "error_by_turn",
    title: str | None = None,
) -> None:
    """Mean LAB error per turn, grouped by regime or teacher_type."""
    fig, ax = plt.subplots(figsize=(7, 4.5))

    groups = traj_df[group_col].dropna().unique()
    order = _REGIME_ORDER if group_col == "regime_label" else sorted(groups)

    for i, grp in enumerate(order):
        sub = traj_df[traj_df[group_col] == grp]
        means = sub.groupby("turn")["error_lab"].mean()
        sems = sub.groupby("turn")["error_lab"].sem()
        turns = means.index.tolist()
        color = _PALETTE[i % len(_PALETTE)]
        label = _REGIME_LABELS.get(grp, grp)
        ax.plot(turns, means.values, marker="o", color=color, label=label, linewidth=2)
        ax.fill_between(
            turns,
            means.values - sems.values,
            means.values + sems.values,
            color=color, alpha=0.15,
        )

    ax.set_xlabel("Turn", fontsize=11)
    ax.set_ylabel("Mean LAB error (ΔE₇₆)", fontsize=11)
    ax.set_title(title or f"Error by turn — by {group_col}", fontsize=12)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 2. Initial vs final error by regime (grouped bar)
# ---------------------------------------------------------------------------

def plot_initial_vs_final_error(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "error_by_regime",
    title: str | None = None,
) -> None:
    """Grouped bar: initial and final LAB error per regime."""
    regimes = [r for r in _REGIME_ORDER if r in per_example_df["regime_label"].values]
    if not regimes:
        regimes = sorted(per_example_df["regime_label"].dropna().unique())

    init_means = [per_example_df[per_example_df["regime_label"] == r]["initial_error_lab"].mean() for r in regimes]
    init_sems  = [per_example_df[per_example_df["regime_label"] == r]["initial_error_lab"].sem()  for r in regimes]
    fin_means  = [per_example_df[per_example_df["regime_label"] == r]["final_error_lab"].mean()   for r in regimes]
    fin_sems   = [per_example_df[per_example_df["regime_label"] == r]["final_error_lab"].sem()    for r in regimes]

    x = np.arange(len(regimes))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars1 = ax.bar(x - w / 2, init_means, w, yerr=init_sems, capsize=4,
                   color=_PALETTE[0], alpha=0.85, label="Initial ΔE")
    bars2 = ax.bar(x + w / 2, fin_means,  w, yerr=fin_sems,  capsize=4,
                   color=_PALETTE[2], alpha=0.85, label="Final ΔE")

    ax.set_xticks(x)
    ax.set_xticklabels([_REGIME_LABELS.get(r, r) for r in regimes], fontsize=10)
    ax.set_ylabel("Mean LAB error (ΔE₇₆)", fontsize=11)
    ax.set_title(title or "Initial vs final error by regime", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 3. Relative improvement by regime (bar + error bar)
# ---------------------------------------------------------------------------

def plot_relative_improvement_by_regime(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "improvement_by_regime",
    title: str | None = None,
) -> None:
    regimes = [r for r in _REGIME_ORDER if r in per_example_df["regime_label"].values]
    if not regimes:
        regimes = sorted(per_example_df["regime_label"].dropna().unique())

    means = [per_example_df[per_example_df["regime_label"] == r]["relative_improvement"].mean() for r in regimes]
    sems  = [per_example_df[per_example_df["regime_label"] == r]["relative_improvement"].sem()  for r in regimes]

    colors = [_regime_color(r) for r in regimes]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(len(regimes)), means, yerr=sems, capsize=4,
           color=colors, alpha=0.85, width=0.55)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xticks(range(len(regimes)))
    ax.set_xticklabels([_REGIME_LABELS.get(r, r) for r in regimes], fontsize=10)
    ax.set_ylabel("Mean relative improvement", fontsize=11)
    ax.set_title(title or "Relative improvement by regime", fontsize=12)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 4. Constraint satisfaction by regime
# ---------------------------------------------------------------------------

def plot_constraint_satisfaction(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "constraint_satisfaction",
    title: str | None = None,
) -> None:
    col = "mean_constraint_satisfaction"
    if col not in per_example_df.columns:
        return

    sub = per_example_df.dropna(subset=[col])
    if sub.empty:
        return

    regimes = [r for r in _REGIME_ORDER if r in sub["regime_label"].values]
    if not regimes:
        regimes = sorted(sub["regime_label"].dropna().unique())

    means = [sub[sub["regime_label"] == r][col].mean() for r in regimes]
    sems  = [sub[sub["regime_label"] == r][col].sem()  for r in regimes]

    colors = [_regime_color(r) for r in regimes]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(len(regimes)), means, yerr=sems, capsize=4,
           color=colors, alpha=0.85, width=0.55)
    ax.axhline(0.5, color="gray", linewidth=0.8, linestyle="--", label="chance")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(range(len(regimes)))
    ax.set_xticklabels([_REGIME_LABELS.get(r, r) for r in regimes], fontsize=10)
    ax.set_ylabel("Constraint satisfaction rate", fontsize=11)
    ax.set_title(title or "Constraint satisfaction by regime", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 5. Directional alignment by regime
# ---------------------------------------------------------------------------

def plot_directional_alignment(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "directional_alignment",
    title: str | None = None,
) -> None:
    col = "mean_directional_alignment"
    if col not in per_example_df.columns:
        return

    sub = per_example_df.dropna(subset=[col])
    if sub.empty:
        return

    regimes = [r for r in _REGIME_ORDER if r in sub["regime_label"].values]
    if not regimes:
        regimes = sorted(sub["regime_label"].dropna().unique())

    means = [sub[sub["regime_label"] == r][col].mean() for r in regimes]
    sems  = [sub[sub["regime_label"] == r][col].sem()  for r in regimes]

    colors = [_regime_color(r) for r in regimes]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(len(regimes)), means, yerr=sems, capsize=4,
           color=colors, alpha=0.85, width=0.55)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylim(-0.2, 1.05)
    ax.set_xticks(range(len(regimes)))
    ax.set_xticklabels([_REGIME_LABELS.get(r, r) for r in regimes], fontsize=10)
    ax.set_ylabel("Mean directional alignment", fontsize=11)
    ax.set_title(title or "Directional alignment by regime", fontsize=12)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 6. Final error vs abstraction score (scatter + binned line)
# ---------------------------------------------------------------------------

def plot_error_vs_abstraction(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "error_vs_abstraction",
    title: str | None = None,
    n_bins: int = 10,
) -> None:
    sub = per_example_df.dropna(subset=["abstraction_score", "final_error_lab"])
    if sub.empty:
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(
        sub["abstraction_score"], sub["final_error_lab"],
        alpha=0.25, s=10, color=_PALETTE[0], label="examples",
    )

    # Binned averages
    sub = sub.copy()
    sub["abs_bin"] = pd.cut(sub["abstraction_score"], bins=n_bins)
    binned = sub.groupby("abs_bin", observed=True)["final_error_lab"].agg(["mean", "sem", "count"])
    bin_centers = [iv.mid for iv in binned.index]
    ax.plot(bin_centers, binned["mean"].values, color=_PALETTE[2],
            linewidth=2, marker="o", markersize=5, label=f"binned mean (n={n_bins})")
    ax.fill_between(
        bin_centers,
        binned["mean"] - binned["sem"],
        binned["mean"] + binned["sem"],
        color=_PALETTE[2], alpha=0.2,
    )

    ax.set_xlabel("Abstraction score", fontsize=11)
    ax.set_ylabel("Final LAB error (ΔE₇₆)", fontsize=11)
    ax.set_title(title or "Final error vs abstraction score", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# 7. Parse failure rate by model (or by run)
# ---------------------------------------------------------------------------

def plot_parse_failure_rate(
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    stem: str = "parse_failure_rate",
    title: str | None = None,
) -> None:
    if "model_alias" not in per_example_df.columns:
        return

    groups = per_example_df.groupby("model_alias")
    rates = {}
    for alias, grp in groups:
        total_turns = grp["num_valid_turns"].sum() + grp["parse_failure_count"].sum()
        failures = grp["parse_failure_count"].sum()
        rates[alias] = failures / max(total_turns, 1)

    if not rates:
        return

    names = list(rates.keys())
    vals = [rates[n] for n in names]

    fig, ax = plt.subplots(figsize=(max(5, len(names) * 1.5), 4))
    ax.bar(range(len(names)), vals, color=_PALETTE[3], alpha=0.85, width=0.5)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Parse failure rate", fontsize=11)
    ax.set_title(title or "Parse failure rate by model", fontsize=12)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# Multi-run comparison: error by turn, grouped by run label
# ---------------------------------------------------------------------------

def plot_error_by_turn_multi(
    runs: list[tuple[str, pd.DataFrame]],
    out_dir: Path,
    *,
    stem: str = "error_by_turn_multi",
    title: str | None = None,
) -> None:
    """Error by turn for multiple runs (each run = one line)."""
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for i, (label, traj_df) in enumerate(runs):
        sub = traj_df.dropna(subset=["error_lab"])
        means = sub.groupby("turn")["error_lab"].mean()
        sems  = sub.groupby("turn")["error_lab"].sem()
        turns = means.index.tolist()
        color = _PALETTE[i % len(_PALETTE)]
        ax.plot(turns, means.values, marker="o", color=color, label=label, linewidth=2)
        ax.fill_between(turns, means - sems, means + sems, color=color, alpha=0.15)

    ax.set_xlabel("Turn", fontsize=11)
    ax.set_ylabel("Mean LAB error (ΔE₇₆)", fontsize=11)
    ax.set_title(title or "Error by turn — teacher comparison", fontsize=12)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


def plot_relative_improvement_multi(
    runs: list[tuple[str, pd.DataFrame]],
    out_dir: Path,
    *,
    stem: str = "improvement_multi",
    title: str | None = None,
) -> None:
    """Relative improvement by regime for multiple runs."""
    regimes = _REGIME_ORDER
    n_runs = len(runs)
    n_reg = len(regimes)
    w = 0.8 / n_runs
    x = np.arange(n_reg)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, (label, df) in enumerate(runs):
        means = []
        sems = []
        for r in regimes:
            sub = df[df["regime_label"] == r]["relative_improvement"].dropna()
            means.append(sub.mean() if len(sub) else 0.0)
            sems.append(sub.sem() if len(sub) > 1 else 0.0)
        offset = (i - n_runs / 2 + 0.5) * w
        ax.bar(x + offset, means, w, yerr=sems, capsize=3,
               color=_PALETTE[i % len(_PALETTE)], alpha=0.85, label=label)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([_REGIME_LABELS.get(r, r) for r in regimes], fontsize=10)
    ax.set_ylabel("Mean relative improvement", fontsize=11)
    ax.set_title(title or "Relative improvement by regime — teacher comparison", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


# ---------------------------------------------------------------------------
# All-in-one: generate all standard plots for a single run
# ---------------------------------------------------------------------------

def generate_all_plots(
    traj_df: pd.DataFrame,
    per_example_df: pd.DataFrame,
    out_dir: Path,
    *,
    run_label: str = "",
) -> list[Path]:
    """Generate all standard per-run figures. Returns list of written paths."""
    out_dir = Path(out_dir)
    written: list[Path] = []

    def _written(stem: str) -> None:
        written.append(out_dir / f"{stem}.png")

    plot_error_by_turn(traj_df, out_dir, group_col="regime_label",
                       stem="error_by_turn_regime",
                       title=f"Error by turn by regime{' — ' + run_label if run_label else ''}")
    _written("error_by_turn_regime")

    plot_initial_vs_final_error(per_example_df, out_dir,
                                stem="error_by_regime",
                                title=f"Initial vs final error{' — ' + run_label if run_label else ''}")
    _written("error_by_regime")

    plot_relative_improvement_by_regime(per_example_df, out_dir,
                                        stem="improvement_by_regime",
                                        title=f"Relative improvement{' — ' + run_label if run_label else ''}")
    _written("improvement_by_regime")

    plot_constraint_satisfaction(per_example_df, out_dir,
                                 stem="constraint_satisfaction",
                                 title=f"Constraint satisfaction{' — ' + run_label if run_label else ''}")
    _written("constraint_satisfaction")

    plot_directional_alignment(per_example_df, out_dir,
                               stem="directional_alignment",
                               title=f"Directional alignment{' — ' + run_label if run_label else ''}")
    _written("directional_alignment")

    plot_error_vs_abstraction(per_example_df, out_dir,
                              stem="error_vs_abstraction",
                              title=f"Final error vs abstraction score{' — ' + run_label if run_label else ''}")
    _written("error_vs_abstraction")

    plot_parse_failure_rate(per_example_df, out_dir,
                            stem="parse_failure_rate",
                            title=f"Parse failure rate{' — ' + run_label if run_label else ''}")
    _written("parse_failure_rate")

    return [p for p in written if p.exists()]
