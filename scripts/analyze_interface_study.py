"""Analyze saved matched reference-game trajectories without model loading."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.interface_analysis import analyze, write_analysis  # noqa: E402
from run_interface_study import load_checkpoints, load_plan, run_lock  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    if args.resamples < 100 or args.seed < 0:
        parser.error("--resamples must be at least 100 and --seed must be nonnegative")
    with run_lock(args.run):
        cfg, plan, metadata = load_plan(args.run)
        checkpoints = load_checkpoints(args.run, cfg, plan, metadata)
        result = analyze(cfg, plan["tasks"], checkpoints, args.resamples, args.seed)
        write_analysis(result, args.run)
    print(f"Analysis: {args.run / 'reports/interface_analysis.md'}")


if __name__ == "__main__":
    main()
