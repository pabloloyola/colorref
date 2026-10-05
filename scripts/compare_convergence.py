"""Aggregate and compare convergence sweep runs across max_turns settings.

Usage:
    uv run python scripts/compare_convergence.py \\
        --run_dirs runs/*convergence_axis_c3* \\
        --out_dir reports/comparisons/convergence_sweep

    # Also include the existing t=3 run:
    uv run python scripts/compare_convergence.py \\
        --run_dirs runs/*convergence_axis* runs/*feedback_axis_c3_main_qwen3* \\
        --out_dir reports/comparisons/convergence_sweep
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.stopping import (
    compute_all_per_example,
    compute_convergence_rate_curve,
    compute_turn_curves,
    find_plateau_turn,
)

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
_CMAP = plt.cm.viridis  # noqa: E501


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare convergence sweep runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run_dirs", nargs="+", required=True,
                   help="Run directories or glob patterns")
    p.add_argument("--out_dir",
                   default="reports/comparisons/convergence_sweep")
    p.add_argument("--figures_dir", default=None,
                   help="Figures output dir (defaults to out_dir/figures)")
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


def _infer_max_turns(run_dir: Path, traj: pd.DataFrame) -> int:
    """Try to infer max_turns from config or trajectory."""
    config_path = run_dir / "config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        try:
            return int(cfg["execution"]["max_turns"])
        except (KeyError, TypeError):
            pass
    return int(traj["turn"].max())


def _load_run(run_dir: Path) -> tuple[pd.DataFrame, int] | None:
    """Load trajectories and infer max_turns."""
    traj_path = run_dir / "games" / "trajectories.parquet"
    if not traj_path.exists():
        return None
    traj = pd.read_parquet(traj_path)
    mt = _infer_max_turns(run_dir, traj)
    return traj, mt


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _color_for_turns(max_turns_list: list[int]) -> dict[int, str]:
    sorted_t = sorted(set(max_turns_list))
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(sorted_t)))
    return {t: f"#{int(c[0]*255):02x}{int(c[1]*255):02x}{int(c[2]*255):02x}" for t, c in zip(sorted_t, colors)}


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
    logger.info("Found %d valid run dirs", len(run_dirs))
    for rd in run_dirs:
        logger.info("  %s", rd.name)

    if not run_dirs:
        logger.error("No valid run dirs found.")
        sys.exit(1)

    # Load all runs
    all_per_ex: list[pd.DataFrame] = []
    all_turn_curves: list[pd.DataFrame] = []
    all_conv_rates: list[pd.DataFrame] = []
    run_meta: list[dict] = []

    for run_dir in run_dirs:
        result = _load_run(run_dir)
        if result is None:
            continue
        traj, mt = result
        logger.info("  max_turns=%d  |  %s", mt, run_dir.name)

        # Check if pre-computed metrics exist
        pe_path = run_dir / "metrics" / "convergence_per_example.parquet"
        tc_path = run_dir / "metrics" / "convergence_by_turn.csv"
        cr_path = run_dir / "metrics" / "convergence_rate_by_turn.csv"

        if pe_path.exists():
            pe = pd.read_parquet(pe_path)
        else:
            pe = compute_all_per_example(traj)
            pe["max_turns"] = mt
            pe["run_id"] = run_dir.name

        if tc_path.exists():
            tc = pd.read_csv(tc_path)
        else:
            tc = compute_turn_curves(traj)
            tc["max_turns"] = mt

        if cr_path.exists():
            cr = pd.read_csv(cr_path)
        else:
            cr = compute_convergence_rate_curve(traj)
            cr["max_turns"] = mt

        pe["max_turns"] = mt
        pe["run_id"] = run_dir.name
        tc["max_turns"] = mt
        cr["max_turns"] = mt

        all_per_ex.append(pe)
        all_turn_curves.append(tc)
        all_conv_rates.append(cr)
        run_meta.append({"run_id": run_dir.name, "max_turns": mt})

    if not all_per_ex:
        logger.error("No data loaded.")
        sys.exit(1)

    combined_pe = pd.concat(all_per_ex, ignore_index=True)
    combined_tc = pd.concat(all_turn_curves, ignore_index=True)
    combined_cr = pd.concat(all_conv_rates, ignore_index=True)

    # Save combined data
    combined_pe.to_parquet(out_dir / "combined_per_example.parquet", index=False)
    combined_tc.to_parquet(out_dir / "combined_per_turn.parquet", index=False)
    logger.info("Saved combined data.")

    # ----------------------------------------------------------------
    # Aggregate by max_turns
    # ----------------------------------------------------------------
    agg_by_max_turns = (
        combined_pe
        .groupby("max_turns")
        .agg(
            mean_initial_error=("initial_error", "mean"),
            mean_final_error=("final_error", "mean"),
            mean_best_error=("best_error", "mean"),
            mean_final_best_gap=("final_best_gap", "mean"),
            regression_rate=("regressed", "mean"),
            mean_turn_regressions=("turn_regressions", "mean"),
            n=("example_id", "count"),
        )
        .reset_index()
        .sort_values("max_turns")
    )
    agg_by_max_turns.to_csv(out_dir / "aggregate_by_max_turns.csv", index=False)
    logger.info("aggregate_by_max_turns.csv")

    # ----------------------------------------------------------------
    # Aggregate by turn (across all runs)
    # ----------------------------------------------------------------
    agg_by_turn = (
        combined_tc
        .groupby(["max_turns", "turn"])
        .agg(
            mean_error=("mean_error", "mean"),
            mean_best_error=("mean_best_error", "mean"),
            marginal_gain=("marginal_gain", "mean"),
            regression_rate=("regression_rate", "mean"),
        )
        .reset_index()
        .sort_values(["max_turns", "turn"])
    )
    agg_by_turn.to_csv(out_dir / "aggregate_by_turn.csv", index=False)
    logger.info("aggregate_by_turn.csv")

    # ----------------------------------------------------------------
    # Regime × turn breakdown
    # ----------------------------------------------------------------
    if "regime_label" in combined_pe.columns:
        agg_regime_turn = (
            combined_pe
            .groupby(["max_turns", "regime_label"])
            .agg(
                mean_final_error=("final_error", "mean"),
                mean_best_error=("best_error", "mean"),
            )
            .reset_index()
        )
        agg_regime_turn.to_csv(out_dir / "aggregate_by_regime_turn.csv", index=False)

    # ----------------------------------------------------------------
    # Figures
    # ----------------------------------------------------------------
    max_turns_list = sorted(combined_pe["max_turns"].unique())
    color_map = _color_for_turns(max_turns_list)

    # 1. Error by turn (each max_turns = one line, turns up to its max)
    fig, ax = plt.subplots(figsize=(7, 4))
    for mt, group in agg_by_turn.groupby("max_turns"):
        group = group.sort_values("turn")
        ax.plot(group["turn"], group["mean_error"], "o-",
                color=color_map[mt], label=f"max_turns={mt}", linewidth=1.8, ms=5)
    ax.set_xlabel("Feedback turn")
    ax.set_ylabel("Mean ΔE (LAB)")
    ax.set_title("Error by turn — convergence sweep")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = figures_dir / "error_by_turn_long.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(p.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    logger.info("Saved %s", p)

    # 2. Best-so-far error by turn
    fig, ax = plt.subplots(figsize=(7, 4))
    for mt, group in agg_by_turn.groupby("max_turns"):
        group = group.sort_values("turn")
        ax.plot(group["turn"], group["mean_best_error"], "s--",
                color=color_map[mt], label=f"max_turns={mt}", linewidth=1.8, ms=5)
    ax.set_xlabel("Feedback turn")
    ax.set_ylabel("Mean best-so-far ΔE (LAB)")
    ax.set_title("Best-so-far error by turn — convergence sweep")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = figures_dir / "best_error_by_turn_long.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(p.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)

    # 3. Convergence rate by turn
    fig, ax = plt.subplots(figsize=(7, 4))
    for mt, group in combined_cr.groupby("max_turns"):
        group = group.sort_values("turn")
        ax.plot(group["turn"], group["convergence_rate"], "o-",
                color=color_map[mt], label=f"max_turns={mt}", linewidth=1.8, ms=5)
    ax.set_xlabel("Feedback turn")
    ax.set_ylabel("Fraction converged (ΔE < 5)")
    ax.set_title("Convergence rate by turn")
    ax.set_ylim(0, 1.0)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = figures_dir / "convergence_rate_by_turn.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(p.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)

    # 4. Final vs best gap by max_turns
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = agg_by_max_turns["max_turns"]
    ax.bar(xs, agg_by_max_turns["mean_final_best_gap"],
           color=[color_map[t] for t in xs], edgecolor="white")
    ax.set_xlabel("max_turns")
    ax.set_ylabel("Mean final-best gap (ΔE)")
    ax.set_title("Final vs best-so-far gap by max_turns")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    p = figures_dir / "final_vs_best_gap_by_turn.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # 5. Regression rate by max_turns
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(xs, agg_by_max_turns["regression_rate"],
           color=[color_map[t] for t in xs], edgecolor="white")
    ax.set_xlabel("max_turns")
    ax.set_ylabel("Regression rate (final > initial)")
    ax.set_title("Regression rate by max_turns")
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    p = figures_dir / "regression_rate_by_turn.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figures.")

    # ----------------------------------------------------------------
    # Combined report
    # ----------------------------------------------------------------
    plateau_info: dict[int, int | None] = {}
    for mt, group in combined_tc.groupby("max_turns"):
        plateau_info[mt] = find_plateau_turn(group)

    lines = [
        "# Convergence Sweep Combined Report",
        "",
        f"**Runs compared**: {len(run_dirs)}",
        f"**max_turns values**: {max_turns_list}",
        "",
        "## Aggregate by max_turns",
        "",
        "| max_turns | mean ΔE_init | mean ΔE_final | mean ΔE_best | mean gap | regression% | plateau_turn |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in agg_by_max_turns.iterrows():
        mt = int(row["max_turns"])
        pt = plateau_info.get(mt, "—")
        lines.append(
            f"| {mt} | {row['mean_initial_error']:.2f} | {row['mean_final_error']:.2f} "
            f"| {row['mean_best_error']:.2f} | {row['mean_final_best_gap']:.2f} "
            f"| {row['regression_rate']*100:.1f}% | {pt} |"
        )

    lines += [
        "",
        "## Paper-Facing Questions",
        "",
        "1. **Does final error keep decreasing after 3 turns?**",
        "   → See `aggregate_by_max_turns.csv`, compare mean_final_error at t=3 vs t=5, t=7, t=10.",
        "",
        "2. **Does best-so-far error keep decreasing after 3 turns?**",
        "   → See `aggregate_by_turn.csv`, mean_best_error column.",
        "",
        "3. **Does convergence rate increase meaningfully after 3 turns?**",
        "   → See `convergence_rate_by_turn.png`.",
        "",
        "4. **Do longer games introduce more regressions?**",
        "   → See regression_rate column above and `regression_rate_by_turn.png`.",
        "",
        "5. **Is 3 turns a reasonable compute/quality tradeoff?**",
        "   → Compare marginal_gain from t=3→5 vs t=1→3 in aggregate_by_turn.csv.",
        "",
        "## Figures",
        "",
        "- `figures/error_by_turn_long.png`",
        "- `figures/best_error_by_turn_long.png`",
        "- `figures/convergence_rate_by_turn.png`",
        "- `figures/final_vs_best_gap_by_turn.png`",
        "- `figures/regression_rate_by_turn.png`",
    ]

    (out_dir / "combined_report.md").write_text("\n".join(lines))
    logger.info("Written: %s", out_dir / "combined_report.md")
    print(f"\nDone. Results in {out_dir}")


if __name__ == "__main__":
    main()
