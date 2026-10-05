"""Behavioral geometry comparison across runs.

Computes trajectory structure vs. true-color structure alignment using
Spearman correlation and kernel alignment metrics (spec §17).

Usage — single run:
    uv run python scripts/compare_geometries.py \
        --run_dir runs/20260516_121822_feedback_minimal_main_qwen3_14b_minimal_oracle_main_1000

Usage — compare multiple runs:
    uv run python scripts/compare_geometries.py \
        --run_dirs runs/run_minimal runs/run_axis runs/run_template \
        --out_dir reports/comparisons/geometry
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.geometry import compute_geometry_alignment, alignment_summary_df

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
        description="Compute behavioral geometry alignment for completed runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--run_dir",  help="Single run directory")
    grp.add_argument("--run_dirs", nargs="+", help="Multiple run directories")
    p.add_argument("--out_dir", default=None,
                   help="Output directory (default: <run_dir>/metrics/ for single, required for multi)")
    p.add_argument("--max_turns", type=int, default=4,
                   help="Number of turns to include (0..max_turns-1)")
    p.add_argument("--subsample", type=int, default=500,
                   help="Max examples to use (for speed). 0 = use all.")
    p.add_argument("--seed", type=int, default=13)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Per-run analysis
# ---------------------------------------------------------------------------

def analyze_run(run_dir: Path, max_turns: int, subsample: int, seed: int) -> pd.DataFrame:
    traj_path = run_dir / "games" / "trajectories.parquet"
    if not traj_path.exists():
        raise FileNotFoundError(f"trajectories.parquet not found in {run_dir}/games/")

    traj_df = pd.read_parquet(traj_path)
    logger.info("Loaded %d rows from %s", len(traj_df), run_dir.name)

    results = compute_geometry_alignment(
        traj_df,
        max_turns=max_turns,
        subsample=subsample if subsample > 0 else None,
        seed=seed,
    )
    summary = alignment_summary_df(results)
    summary["run_id"] = run_dir.name
    return summary, results


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_alignment_bars(
    df: pd.DataFrame,
    out_dir: Path,
    metric: str = "spearman_rho",
    title: str = "Trajectory alignment with true LAB color space",
) -> None:
    runs  = df["run_id"].unique()
    reprs = ["initial_guess", "final_guess", "traj_state", "traj_update"]
    labels = {"initial_guess": "Initial\nguess", "final_guess": "Final\nguess",
               "traj_state": "State\ntraj.", "traj_update": "Update\ntraj."}

    fig, ax = plt.subplots(figsize=(max(6, 2 * len(reprs)), 4))
    x = np.arange(len(reprs))
    width = 0.8 / max(len(runs), 1)

    for i, run in enumerate(runs):
        sub = df[df["run_id"] == run].set_index("representation")
        vals = [sub.loc[r, metric] if r in sub.index else float("nan") for r in reprs]
        offset = (i - len(runs) / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width * 0.9, label=run.split("_")[3] if "_" in run else run)

    ax.set_xticks(x)
    ax.set_xticklabels([labels[r] for r in reprs])
    ax.set_ylabel("Spearman ρ" if metric == "spearman_rho" else "Kernel alignment")
    ax.set_title(title)
    ax.axhline(0, color="black", linewidth=0.5)
    if len(runs) > 1:
        ax.legend(fontsize=7, loc="upper left")
    ax.set_ylim(-0.1, 1.0)

    for fmt in ("png", "pdf"):
        fig.savefig(out_dir / f"geometry_alignment_bars.{fmt}", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("  geometry_alignment_bars.png")


def plot_distance_heatmap(D: np.ndarray, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(D, aspect="auto", cmap="viridis")
    plt.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(title)
    ax.set_xlabel("Example index")
    ax.set_ylabel("Example index")
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    run_dirs = [Path(args.run_dir)] if args.run_dir else [Path(d) for d in args.run_dirs]

    # Determine output directory
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif len(run_dirs) == 1:
        out_dir = run_dirs[0] / "metrics"
    else:
        raise ValueError("--out_dir is required when multiple --run_dirs are provided.")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_summaries: list[pd.DataFrame] = []

    for run_dir in run_dirs:
        logger.info("Analyzing %s …", run_dir.name)
        try:
            summary, results = analyze_run(run_dir, args.max_turns, args.subsample, args.seed)
        except FileNotFoundError as e:
            logger.warning("Skipping %s: %s", run_dir.name, e)
            continue

        # Save per-run CSV
        per_run_out = run_dir / "metrics" if len(run_dirs) > 1 else out_dir
        per_run_out.mkdir(parents=True, exist_ok=True)
        csv_path = per_run_out / "geometry_alignment.csv"
        summary.to_csv(csv_path, index=False)
        logger.info("  Saved %s", csv_path)

        # Heatmaps for single-run mode
        if len(run_dirs) == 1:
            for name, D in [
                ("true_lab",      results["D_true_lab"]),
                ("initial_guess", results["D_initial_guess"]),
                ("final_guess",   results["D_final_guess"]),
                ("traj_state",    results["D_traj_state"]),
                ("traj_update",   results["D_traj_update"]),
            ]:
                plot_distance_heatmap(
                    D[:50, :50],  # show first 50x50 for readability
                    title=f"Distance matrix: {name}",
                    out_path=out_dir / f"geometry_heatmap_{name}.png",
                )
            logger.info("  geometry_heatmap_*.png")

        all_summaries.append(summary)

    if all_summaries:
        combined = pd.concat(all_summaries, ignore_index=True)
        combined.to_csv(out_dir / "geometry_alignment_all.csv", index=False)

        # Print summary table
        pivot = combined.pivot_table(
            index="representation", columns="run_id",
            values="spearman_rho", aggfunc="first"
        )
        logger.info("\nSpearman ρ (true LAB vs. representation):\n%s", pivot.to_string())

        plot_alignment_bars(combined, out_dir)
        logger.info("Done. Outputs in %s", out_dir)


if __name__ == "__main__":
    main()
