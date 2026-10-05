"""Run a convergence sweep over multiple max_turns settings.

Launches run_feedback_game.py for each config and writes
per-example convergence metrics augmented with stopping.py statistics.

Usage:
    # Run from pre-built YAML configs:
    uv run python scripts/run_convergence_sweep.py \\
        --configs configs/experiments/convergence_axis_c3_t*.yaml

    # Generate and run configs directly:
    uv run python scripts/run_convergence_sweep.py \\
        --teacher axis_oracle \\
        --max_constraints 3 \\
        --turns 1 2 3 5 7 10 \\
        --subset data/eval_subsets/main_1000.parquet \\
        --model Qwen/Qwen3-14B
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run convergence sweep and compute stopping metrics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--configs", nargs="+", default=None,
                   help="Explicit YAML config paths (glob or list). "
                        "If omitted, configs are generated from --teacher/--turns etc.")
    p.add_argument("--teacher", default="axis_oracle")
    p.add_argument("--max_constraints", type=int, default=3)
    p.add_argument("--turns", type=int, nargs="+", default=[1, 2, 3, 5, 7, 10])
    p.add_argument("--subset", default="data/eval_subsets/main_1000.parquet")
    p.add_argument("--model", default="Qwen/Qwen3-14B")
    p.add_argument("--runs_root", default="runs")
    p.add_argument("--configs_dir", default="configs/experiments")
    p.add_argument("--dry_run", action="store_true",
                   help="Print commands without running them")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_run_dir(run_root: Path, experiment_name: str) -> Path | None:
    """Find the most recent matching run directory."""
    matches = sorted(run_root.glob(f"*_{experiment_name}_*"))
    # Also look for pattern where experiment name appears after timestamp
    matches += sorted(run_root.glob(f"*{experiment_name}*"))
    # Filter to those with trajectories
    valid = [m for m in set(matches) if (m / "games" / "trajectories.parquet").exists()]
    if not valid:
        return None
    return sorted(valid)[-1]


def _run_experiment(config_path: Path, dry_run: bool = False) -> int:
    cmd = ["uv", "run", "python", "scripts/run_feedback_game.py",
           "--config", str(config_path)]
    logger.info("Running: %s", " ".join(cmd))
    if dry_run:
        return 0
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _compute_and_save_convergence_metrics(
    run_dir: Path,
    max_turns: int,
) -> None:
    """Augment a run with stopping.py convergence metrics."""
    traj_path = run_dir / "games" / "trajectories.parquet"
    if not traj_path.exists():
        logger.warning("No trajectories.parquet in %s", run_dir)
        return

    traj = pd.read_parquet(traj_path)
    metrics_dir = run_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    # Per-example convergence
    per_ex = compute_all_per_example(traj)
    per_ex["max_turns"] = max_turns
    per_ex["run_id"] = run_dir.name
    out_pe = metrics_dir / "convergence_per_example.parquet"
    per_ex.to_parquet(out_pe, index=False)
    logger.info("Saved %s", out_pe)

    # Turn curves
    turn_curve = compute_turn_curves(traj)
    turn_curve["max_turns"] = max_turns
    out_tc = metrics_dir / "convergence_by_turn.csv"
    turn_curve.to_csv(out_tc, index=False)
    logger.info("Saved %s", out_tc)

    # Convergence rate
    conv_rate = compute_convergence_rate_curve(traj)
    conv_rate["max_turns"] = max_turns
    out_cr = metrics_dir / "convergence_rate_by_turn.csv"
    conv_rate.to_csv(out_cr, index=False)

    # Plateau
    plateau = find_plateau_turn(turn_curve)

    # Summary report
    report_dir = run_dir / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "convergence_summary.md"

    lines = [
        f"# Convergence Summary: {run_dir.name}",
        "",
        f"**max_turns**: {max_turns}",
        f"**n_examples**: {len(per_ex)}",
        "",
        "## Aggregate Statistics",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| mean initial error | {per_ex['initial_error'].mean():.2f} |",
        f"| mean final error | {per_ex['final_error'].mean():.2f} |",
        f"| mean best error | {per_ex['best_error'].mean():.2f} |",
        f"| mean final-best gap | {per_ex['final_best_gap'].mean():.2f} |",
        f"| regression rate (final > initial) | {per_ex['regressed'].mean():.3f} |",
        f"| mean turn regressions | {per_ex['turn_regressions'].mean():.2f} |",
        f"| plateau turn (ΔE < 1.0 over 2 turns) | {plateau} |",
        "",
        "## Turn Curve",
        "",
    ]
    if not turn_curve.empty:
        lines.append("| turn | mean_error | mean_best_error | marginal_gain | regression_rate |")
        lines.append("|---|---|---|---|---|")
        for _, row in turn_curve.iterrows():
            mg = f"{row['marginal_gain']:.2f}" if pd.notna(row["marginal_gain"]) else "—"
            rr = f"{row['regression_rate']:.3f}" if pd.notna(row["regression_rate"]) else "—"
            lines.append(
                f"| {int(row['turn'])} | {row['mean_error']:.2f} | {row['mean_best_error']:.2f} | {mg} | {rr} |"
            )

    report_path.write_text("\n".join(lines))
    logger.info("Saved %s", report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Resolve config paths
    if args.configs:
        import glob
        config_paths: list[Path] = []
        for pat in args.configs:
            matches = sorted(glob.glob(pat))
            if matches:
                config_paths.extend(Path(m) for m in matches)
            else:
                p = Path(pat)
                if p.exists():
                    config_paths.append(p)
                else:
                    logger.warning("Config not found: %s", pat)
    else:
        # Build config names from parameters
        subset_stem = Path(args.subset).stem
        model_alias = "qwen3_14b"
        configs_dir = Path(args.configs_dir)
        config_paths = []
        for t in args.turns:
            name = f"convergence_{args.teacher}_c{args.max_constraints}_t{t}_{subset_stem}_{model_alias}"
            # Map legacy stem names
            if "main_1000" in subset_stem:
                name = f"convergence_axis_c{args.max_constraints}_t{t}_main_{model_alias}"
            cp = configs_dir / f"{name}.yaml"
            if not cp.exists():
                logger.warning("Config missing: %s", cp)
                continue
            config_paths.append(cp)

    if not config_paths:
        logger.error("No config paths found.")
        sys.exit(1)

    logger.info("Will run %d configs:", len(config_paths))
    for cp in config_paths:
        logger.info("  %s", cp.name)

    runs_root = Path(args.runs_root)

    for config_path in config_paths:
        # Load config to get experiment_name and max_turns
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        exp_name = cfg["experiment_name"]
        max_turns = cfg["execution"]["max_turns"]

        logger.info("=" * 60)
        logger.info("Config: %s  (max_turns=%d)", config_path.name, max_turns)

        # Run the experiment
        rc = _run_experiment(config_path, dry_run=args.dry_run)
        if rc != 0:
            logger.error("Experiment failed with rc=%d", rc)
            continue

        # Find the resulting run directory
        run_dir = _find_run_dir(runs_root, exp_name)
        if run_dir is None:
            logger.warning("Could not find run dir for %s", exp_name)
            continue

        logger.info("Run dir: %s", run_dir)

        # Compute and save convergence metrics
        _compute_and_save_convergence_metrics(run_dir, max_turns)

    logger.info("Convergence sweep complete.")


if __name__ == "__main__":
    main()
