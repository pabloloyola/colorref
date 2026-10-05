"""Generate figures for one or more completed run directories.

Usage — single run:
    uv run python scripts/plot_results.py \
        --run_dir runs/20260515_174732_feedback_minimal_debug_qwen3_8b_minimal_oracle_debug_400

Usage — multi-run comparison:
    uv run python scripts/plot_results.py \
        --run_dirs runs/run_minimal runs/run_axis runs/run_template \
        --out_dir reports/comparisons/teacher_variants
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.plotting import (
    generate_all_plots,
    plot_error_by_turn_multi,
    plot_relative_improvement_multi,
    plot_error_by_turn,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_run_data(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load per_turn and per_example parquets from a run directory."""
    metrics_dir = run_dir / "metrics"

    per_turn_path    = metrics_dir / "per_turn.parquet"
    per_example_path = metrics_dir / "per_example.parquet"

    if not per_example_path.exists():
        raise FileNotFoundError(
            f"per_example.parquet not found in {metrics_dir}. "
            "Run evaluate_games.py first."
        )

    per_example_df = pd.read_parquet(per_example_path)

    if per_turn_path.exists():
        per_turn_df = pd.read_parquet(per_turn_path)
    else:
        # Fall back to raw trajectories
        traj_path = run_dir / "games" / "trajectories.parquet"
        if traj_path.exists():
            per_turn_df = pd.read_parquet(traj_path)
            logger.warning("per_turn.parquet not found; using raw trajectories")
        else:
            per_turn_df = pd.DataFrame()
            logger.warning("No trajectory data found for %s", run_dir.name)

    return per_turn_df, per_example_df


def _run_label(run_dir: Path) -> str:
    """Short human-readable label from run directory name."""
    parts = run_dir.name.split("_")
    # Format: YYYYMMDD_HHMMSS_<exp>_<model>_<teacher>_<subset>
    # Try to extract teacher type from name
    if len(parts) >= 5:
        # Look for known teacher types
        for part in parts:
            if part in ("minimal", "axis", "template", "llm"):
                return part + "_oracle"
        # Fall back to experiment name
        return "_".join(parts[2:4]) if len(parts) >= 4 else run_dir.name
    return run_dir.name


# ---------------------------------------------------------------------------
# Single-run plots
# ---------------------------------------------------------------------------

def plot_single_run(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    run_id  = run_dir.name
    figures_dir = run_dir / "figures"

    logger.info("Loading data from %s…", run_id)
    per_turn_df, per_example_df = _load_run_data(run_dir)

    if per_turn_df.empty:
        logger.warning("No turn data — skipping trajectory plots")
    if per_example_df.empty:
        logger.warning("No per-example data — nothing to plot")
        return

    logger.info("Generating figures in %s…", figures_dir)
    written = generate_all_plots(
        traj_df=per_turn_df,
        per_example_df=per_example_df,
        out_dir=figures_dir,
        run_label=run_id,
    )
    logger.info("Written %d figure(s):", len(written))
    for p in written:
        logger.info("  %s", p.name)


# ---------------------------------------------------------------------------
# Multi-run comparison plots
# ---------------------------------------------------------------------------

def plot_multi_run(run_dirs: list[Path], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    runs_traj:       list[tuple[str, pd.DataFrame]] = []
    runs_per_example: list[tuple[str, pd.DataFrame]] = []

    for rd in run_dirs:
        label = _run_label(rd)
        try:
            per_turn_df, per_example_df = _load_run_data(rd)
        except FileNotFoundError as e:
            logger.error("Skipping %s: %s", rd.name, e)
            continue
        runs_traj.append((label, per_turn_df))
        runs_per_example.append((label, per_example_df))

    if not runs_traj:
        logger.error("No valid runs found")
        return

    logger.info("Generating comparison figures in %s…", out_dir)

    # Error by turn (all runs on one plot)
    plot_error_by_turn_multi(
        runs_traj, out_dir,
        stem="error_by_turn_comparison",
        title="Error by turn — teacher comparison",
    )
    logger.info("  error_by_turn_comparison.png")

    # Relative improvement by regime (grouped bars)
    all_pe = pd.concat(
        [df.assign(run_label=label) for label, df in runs_per_example],
        ignore_index=True,
    )
    from colorref.plotting import plot_relative_improvement_multi
    plot_relative_improvement_multi(
        runs_per_example, out_dir,
        stem="improvement_comparison",
        title="Relative improvement by regime — teacher comparison",
    )
    logger.info("  improvement_comparison.png")

    # Per-run error-by-turn by regime
    for label, traj_df in runs_traj:
        if not traj_df.empty and "regime_label" in traj_df.columns:
            plot_error_by_turn(
                traj_df, out_dir,
                group_col="regime_label",
                stem=f"error_by_turn_regime_{label}",
                title=f"Error by turn by regime — {label}",
            )
            logger.info("  error_by_turn_regime_%s.png", label)

    # Save combined per_example
    all_pe.to_parquet(out_dir / "combined_per_example.parquet", index=False)
    logger.info("Combined per_example saved.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate figures for one or more completed runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--run_dir", type=Path,
                       help="Single run directory")
    group.add_argument("--run_dirs", type=Path, nargs="+",
                       help="Multiple run directories for comparison")
    p.add_argument("--out_dir", type=Path, default=None,
                   help="Output directory for multi-run plots (default: reports/comparisons/<timestamp>)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.run_dir:
        plot_single_run(args.run_dir)
    else:
        from datetime import datetime, timezone
        out_dir = args.out_dir or Path("reports/comparisons") / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        plot_multi_run(args.run_dirs, out_dir)


if __name__ == "__main__":
    main()
