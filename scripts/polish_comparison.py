"""Generate figures, geometry alignment, and combined_report.md for a comparison dir.

Usage:
    uv run python scripts/polish_comparison.py --kind bandwidth \\
        --out_dir reports/comparisons/feedback_bandwidth \\
        --run_dirs runs/*axis_c1* runs/*axis_c2* ...

    uv run python scripts/polish_comparison.py --kind final_main_4000 \\
        --out_dir reports/comparisons/final_main_4000 \\
        --run_dirs runs/*main_4000* runs/*_4000_*
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.comparison_reports import ComparisonKind, polish_comparison  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DEFAULT_RUNS: dict[str, list[str]] = {
    "bandwidth": [
        "runs/20260517_171411_feedback_axis_c1_main_qwen3_14b_axis_oracle_main_1000",
        "runs/20260517_172906_feedback_axis_c2_main_qwen3_14b_axis_oracle_main_1000",
        "runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000",
        "runs/20260517_201037_feedback_template_c1_main_qwen3_14b_template_oracle_main_1000",
        "runs/20260517_174337_feedback_template_c2_main_qwen3_14b_template_oracle_main_1000",
        "runs/20260517_175800_feedback_template_c3_main_qwen3_14b_template_oracle_main_1000",
        "runs/20260516_121822_feedback_minimal_main_qwen3_14b_minimal_oracle_main_1000",
    ],
    "llm": [
        "runs/20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_llm_teacher_hex_only_debug_400",
        "runs/20260517_211314_feedback_llm_lab_aware_debug_qwen3_14b_llm_teacher_lab_aware_debug_400",
        "runs/20260517_214016_feedback_llm_oracle_assisted_debug_qwen3_14b_llm_teacher_oracle_assisted_debug_400",
        "runs/20260517_214025_feedback_template_llm_vocab_debug_qwen3_14b_template_oracle_llm_vocab_debug_400",
    ],
    "model": [
        "runs/20260516_143421_oneshot_main_qwen3_14b_main_1000",
        "runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000",
        "runs/20260517_201037_feedback_template_c1_main_qwen3_14b_template_oracle_main_1000",
        "runs/20260518_010348_oneshot_main_qwen3_8b_qwen3_8b_main_1000",
        "runs/20260518_010350_feedback_axis_c3_main_qwen3_8b_qwen3_8b_axis_oracle_main_1000",
        "runs/20260518_012037_feedback_template_c1_main_qwen3_8b_qwen3_8b_template_oracle_main_1000",
    ],
    "final_main_4000": [
        "runs/20260518_014252_oneshot_main_4000_qwen3_14b_main_4000",
        "runs/20260518_014303_feedback_axis_c3_main_4000_qwen3_14b_axis_oracle_main_4000",
        "runs/20260518_024819_feedback_minimal_c1_main_4000_qwen3_14b_minimal_oracle_main_4000",
        "runs/20260518_024823_feedback_template_c3_main_4000_qwen3_14b_template_oracle_main_4000",
        "runs/20260518_034542_feedback_template_llm_vocab_main_4000_qwen3_14b_template_oracle_llm_vocab_main_4000",
    ],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Polish a comparison directory with figures and report.")
    p.add_argument(
        "--kind",
        required=True,
        choices=list(_DEFAULT_RUNS.keys()),
        help="Comparison type",
    )
    p.add_argument("--out_dir", type=Path, required=True)
    p.add_argument("--run_dirs", type=Path, nargs="*", default=None)
    p.add_argument("--subsample_geometry", type=int, default=500)
    p.add_argument("--skip_geometry", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [Path(d) for d in (args.run_dirs or _DEFAULT_RUNS[args.kind])]
    missing = [d for d in run_dirs if not d.exists()]
    if missing:
        for d in missing:
            logger.warning("Run dir not found, skipping: %s", d)
        run_dirs = [d for d in run_dirs if d.exists()]
    if not run_dirs:
        raise SystemExit("No valid run directories.")

    logger.info("Polishing %s (%d runs) → %s", args.kind, len(run_dirs), args.out_dir)
    polish_comparison(
        args.kind,
        args.out_dir,
        run_dirs,
        subsample_geometry=args.subsample_geometry,
        skip_geometry=args.skip_geometry,
    )
    logger.info("Done. See %s/combined_report.md and figures/", args.out_dir)


if __name__ == "__main__":
    main()
