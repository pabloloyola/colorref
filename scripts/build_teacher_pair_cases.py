"""Build a curated selected_cases.csv for oracle vs LLM teacher pair visualization.

Usage:
    uv run python scripts/build_teacher_pair_cases.py \\
        --oracle_runs "runs/*template_llm_vocab_debug*" \\
        --llm_runs "runs/*llm_teacher*_debug*" \\
        --out reports/comparisons/teacher_pair_visualization/selected_cases.csv

    # Explicit run dirs:
    uv run python scripts/build_teacher_pair_cases.py \\
        --oracle_runs runs/20260517_214025_feedback_template_llm_vocab_debug_qwen3_14b_template_oracle_llm_vocab_debug_400 \\
        --llm_runs runs/20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_llm_teacher_hex_only_debug_400 \\
                   runs/20260517_211314_feedback_llm_lab_aware_debug_qwen3_14b_llm_teacher_lab_aware_debug_400 \\
        --out reports/comparisons/teacher_pair_visualization/selected_cases.csv
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.pairing import build_pair_case_table, select_top_cases

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
        description="Build selected_cases.csv for oracle vs LLM teacher pairs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--oracle_runs", nargs="+", required=True,
        help="Oracle run dirs (glob patterns or explicit paths)",
    )
    p.add_argument(
        "--llm_runs", nargs="+", required=True,
        help="LLM teacher run dirs (glob patterns or explicit paths)",
    )
    p.add_argument(
        "--out",
        default="reports/comparisons/teacher_pair_visualization/selected_cases.csv",
        help="Output path for selected_cases.csv",
    )
    p.add_argument(
        "--all_cases",
        default="reports/comparisons/teacher_pair_visualization/all_cases.parquet",
        help="Output path for the full (unfiltered) case table",
    )
    p.add_argument(
        "--n_per_type", type=int, default=8,
        help="Max selected cases per case type",
    )
    p.add_argument(
        "--also_top", type=int, default=15,
        help="Always include top-N by selection score",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_paths(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to existing run directories."""
    result = []
    for pat in patterns:
        matches = sorted(glob.glob(pat))
        if matches:
            result.extend(Path(m) for m in matches if Path(m).is_dir())
        else:
            p = Path(pat)
            if p.is_dir():
                result.append(p)
            else:
                logger.warning("Pattern matched nothing: %s", pat)
    return sorted(set(result))


def _has_games(run_dir: Path) -> bool:
    return (run_dir / "games" / "trajectories.parquet").exists()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    oracle_dirs = [d for d in _expand_paths(args.oracle_runs) if _has_games(d)]
    llm_dirs = [d for d in _expand_paths(args.llm_runs) if _has_games(d)]

    logger.info("Oracle runs found: %d", len(oracle_dirs))
    for d in oracle_dirs:
        logger.info("  %s", d.name)
    logger.info("LLM runs found: %d", len(llm_dirs))
    for d in llm_dirs:
        logger.info("  %s", d.name)

    if not oracle_dirs:
        logger.error("No oracle runs found — check --oracle_runs patterns")
        sys.exit(1)
    if not llm_dirs:
        logger.error("No LLM runs found — check --llm_runs patterns")
        sys.exit(1)

    all_tables: list[pd.DataFrame] = []

    for oracle_dir in oracle_dirs:
        for llm_dir in llm_dirs:
            logger.info("Pairing: %s  vs  %s", oracle_dir.name, llm_dir.name)
            try:
                df = build_pair_case_table(oracle_dir, llm_dir)
                logger.info("  → %d paired examples", len(df))
                all_tables.append(df)
            except Exception as exc:
                logger.warning("  Skipping pair (%s): %s", llm_dir.name, exc)

    if not all_tables:
        logger.error("No paired cases found.")
        sys.exit(1)

    combined = pd.concat(all_tables, ignore_index=True)
    combined = (
        combined
        .sort_values("selection_score", ascending=False)
        .reset_index(drop=True)
    )

    # Save full table
    out_all = Path(args.all_cases)
    out_all.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_all, index=False)
    logger.info("Saved full case table: %s  (%d rows)", out_all, len(combined))

    # Save selected subset (CSV for easy inspection)
    selected = select_top_cases(combined, n_per_type=args.n_per_type, also_top_score=args.also_top)
    out_selected = Path(args.out)
    out_selected.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(out_selected, index=False)
    logger.info("Saved selected cases: %s  (%d rows)", out_selected, len(selected))

    # Quick summary
    print(f"\n{'='*60}")
    print(f"Selected cases: {len(selected)}")
    print(f"Case type breakdown:")
    for ct, cnt in selected["case_type"].value_counts().items():
        print(f"  {ct}: {cnt}")
    print(f"\nTop 10 by selection score:")
    cols_show = ["example_id", "raw_name", "oracle_final_error", "llm_final_error",
                 "llm_precision", "case_type", "selection_score"]
    print(selected[cols_show].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
