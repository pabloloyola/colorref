"""CPU-only replay of target-threshold stopping on saved shared-start games."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.stopping_replay import analyze, write_reports  # noqa: E402
from run_shared_start_study import (  # noqa: E402
    load_checkpoints,
    load_plan,
    run_lock,
)


def run_analysis(run_dir, threshold=None, resamples=5000, seed=13):
    with run_lock(run_dir):
        cfg, plan, metadata = load_plan(run_dir)
        saved = load_checkpoints(run_dir, cfg, plan, metadata)
        result = analyze(cfg, plan, saved, threshold, resamples, seed)
        write_reports(result, run_dir)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument(
        "--threshold",
        type=float,
        help="Optional sensitivity override; default is the frozen convergence threshold",
    )
    parser.add_argument("--resamples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    if args.threshold is not None and (
        not math.isfinite(args.threshold) or args.threshold <= 0
    ):
        parser.error("--threshold must be positive and finite")
    if args.resamples < 100:
        parser.error("--resamples must be at least 100")
    result = run_analysis(args.run, args.threshold, args.resamples, args.seed)
    print(
        f"Common fully parsed examples: {result['common_examples']} / {result['planned_examples']}"
    )
    print(f"Summary: {args.run / 'reports/stopping_replay_summary.md'}")


if __name__ == "__main__":
    main()
