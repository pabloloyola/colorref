"""Aggregate LLM teacher decomposition runs and polish outputs.

Usage:
    uv run python scripts/compare_llm_teachers.py \\
        --run_dirs runs/<llm_hex> runs/<llm_lab> runs/<llm_oracle_assisted> runs/<template_matched> \\
        --out_dir reports/comparisons/llm_teacher_decomposition
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

_DEFAULT_RUNS = [
    "runs/20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_llm_teacher_hex_only_debug_400",
    "runs/20260517_211314_feedback_llm_lab_aware_debug_qwen3_14b_llm_teacher_lab_aware_debug_400",
    "runs/20260517_214016_feedback_llm_oracle_assisted_debug_qwen3_14b_llm_teacher_oracle_assisted_debug_400",
    "runs/20260517_214025_feedback_template_llm_vocab_debug_qwen3_14b_template_oracle_llm_vocab_debug_400",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare LLM teacher decomposition runs.")
    p.add_argument("--run_dirs", type=Path, nargs="*", default=None)
    p.add_argument(
        "--out_dir",
        type=Path,
        default=Path("reports/comparisons/llm_teacher_decomposition"),
    )
    p.add_argument("--recompute", action="store_true")
    p.add_argument("--skip_polish", action="store_true")
    p.add_argument("--subsample_geometry", type=int, default=500)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [Path(d) for d in (args.run_dirs or _DEFAULT_RUNS)]
    run_dirs = [d for d in run_dirs if d.exists()]
    if not run_dirs:
        raise SystemExit("No valid run directories.")

    if args.recompute:
        for rd in run_dirs:
            logger.info("Recomputing %s", rd.name)
            evaluate_single_run(rd)

    evaluate_multi_run(run_dirs, args.out_dir)
    logger.info("LLM teacher comparison tables written to %s", args.out_dir)

    if not args.skip_polish:
        polish_comparison(
            "llm",
            args.out_dir,
            run_dirs,
            subsample_geometry=args.subsample_geometry,
        )
        logger.info("Figures and combined_report.md written to %s", args.out_dir)


if __name__ == "__main__":
    main()
