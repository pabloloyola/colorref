"""Recompute metrics for completed runs without rerunning LLM inference.

Usage:
    uv run python scripts/recompute_metrics.py --run_dir runs/<run_id> --overwrite
    uv run python scripts/recompute_metrics.py --run_dirs runs/a runs/b --overwrite
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root / "scripts"))

from evaluate_games import evaluate_single_run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Recompute metrics for completed runs.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--run_dir", type=Path)
    group.add_argument("--run_dirs", type=Path, nargs="+")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite metrics/ and reports/eval_summary.md (default: true)",
    )
    p.add_argument("--convergence_delta_e", type=float, default=5.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [args.run_dir] if args.run_dir else list(args.run_dirs)

    for run_dir in run_dirs:
        logger.info("Recomputing metrics for %s", run_dir.name)
        evaluate_single_run(run_dir, convergence_delta_e=args.convergence_delta_e)
        logger.info("Done: %s", run_dir.name)


if __name__ == "__main__":
    main()
