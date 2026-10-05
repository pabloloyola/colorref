"""Aggregate feedback bandwidth ablation runs into a comparison report.

Usage:
    uv run python scripts/compare_bandwidth.py \
        --run_dirs runs/<axis_c1> runs/<axis_c2> ... \
        --out_dir reports/comparisons/feedback_bandwidth
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.comparison_reports import polish_comparison  # noqa: E402
from evaluate_games import evaluate_multi_run, evaluate_single_run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare feedback bandwidth experiment runs.")
    p.add_argument("--run_dirs", type=Path, nargs="+", required=True)
    p.add_argument(
        "--out_dir",
        type=Path,
        default=Path("reports/comparisons/feedback_bandwidth"),
    )
    p.add_argument(
        "--recompute",
        action="store_true",
        help="Recompute per-run metrics before aggregating",
    )
    p.add_argument(
        "--skip_polish",
        action="store_true",
        help="Skip figures, geometry, and combined_report.md",
    )
    p.add_argument(
        "--kind",
        default="bandwidth",
        choices=["bandwidth", "final_main_4000"],
        help="Comparison type for polish step",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [Path(d) for d in args.run_dirs]

    if args.recompute:
        for rd in run_dirs:
            logger.info("Recomputing %s", rd.name)
            evaluate_single_run(rd)

    evaluate_multi_run(run_dirs, args.out_dir)
    logger.info("Bandwidth comparison written to %s", args.out_dir)

    if not args.skip_polish:
        polish_comparison(args.kind, args.out_dir, run_dirs)
        logger.info("Polished figures and report in %s", args.out_dir)


if __name__ == "__main__":
    main()
