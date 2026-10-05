"""Build balanced evaluation subsets from the full taxonomy parquet.

Usage:
    uv run python scripts/build_eval_subsets.py \
        --input data/colornames_taxonomy.parquet \
        --out_dir data/eval_subsets \
        --seed 13 \
        --sizes 400 1000 4000 \
        --balance_regime \
        --add_bins
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Make src/ importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.bins import add_bins
from colorref.sampling import (
    load_and_validate,
    sample_balanced_by_regime,
    sample_balanced_by_regime_and_bins,
    build_summary_markdown,
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
        description="Build balanced evaluation subsets for ColorRef experiments.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", required=True, help="Path to colornames_taxonomy.parquet")
    p.add_argument("--out_dir", required=True, help="Output directory for subsets")
    p.add_argument("--seed", type=int, default=13, help="Random seed")
    p.add_argument(
        "--sizes", type=int, nargs="+", default=[400, 1000, 4000],
        help="Subset sizes to generate",
    )
    p.add_argument(
        "--balance_regime", action="store_true",
        help="Sample equal counts from each regime_label (default strategy)",
    )
    p.add_argument(
        "--balance_color_bins", action="store_true",
        help="Also attempt approximate balance across color bins within each regime",
    )
    p.add_argument(
        "--add_bins", action="store_true",
        help="Add hue_bin, lightness_bin, saturation_bin, value_bin columns",
    )
    p.add_argument(
        "--min_score", type=float, default=0.0,
        help="Minimum quality score; 0 keeps all rows",
    )
    p.add_argument(
        "--min_regime_confidence", type=float, default=0.0,
        help="Minimum regime confidence",
    )
    p.add_argument(
        "--stratify_cols", nargs="+",
        default=["regime_label", "hue_bin", "lightness_bin", "saturation_bin"],
        help="Columns used for bin stratification (only with --balance_color_bins)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

_SIZE_NAMES: dict[int, str] = {
    400: "debug_400",
    1000: "main_1000",
    4000: "main_4000",
    8000: "main_8000",
}


def subset_name(size: int) -> str:
    return _SIZE_NAMES.get(size, f"subset_{size}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- load & validate ---
    df = load_and_validate(args.input)

    # --- optionally add bins now (needed for bin-balancing) ---
    if args.add_bins or args.balance_color_bins:
        logger.info("Adding color bins to dataset…")
        df = add_bins(df)

    # --- build each subset ---
    for size in args.sizes:
        name = subset_name(size)
        logger.info("=== Building %s (n=%d) ===", name, size)

        if args.balance_color_bins:
            subset = sample_balanced_by_regime_and_bins(
                df,
                n=size,
                seed=args.seed,
                min_score=args.min_score,
                min_regime_confidence=args.min_regime_confidence,
                stratify_cols=args.stratify_cols,
            )
        else:
            subset = sample_balanced_by_regime(
                df,
                n=size,
                seed=args.seed,
                min_score=args.min_score,
                min_regime_confidence=args.min_regime_confidence,
            )

        # Add bin columns if not already present
        if args.add_bins and "hue_bin" not in subset.columns:
            subset = add_bins(subset)

        # Attach metadata columns required by spec §7.3
        subset = subset.copy()
        subset["subset_name"] = name
        subset["sample_seed"] = args.seed

        # --- save parquet ---
        parquet_path = out_dir / f"{name}.parquet"
        subset.to_parquet(parquet_path, index=False)
        logger.info("Saved %s (%d rows) → %s", name, len(subset), parquet_path)

        # --- save summary markdown ---
        md = build_summary_markdown(subset, name, args.seed, args.input)
        md_path = out_dir / f"{name}_summary.md"
        md_path.write_text(md, encoding="utf-8")
        logger.info("Saved summary → %s", md_path)

        # --- quick sanity print ---
        regime_counts = subset["regime_label"].value_counts().sort_index()
        logger.info("Regime distribution:\n%s", regime_counts.to_string())

    logger.info("Done. Subsets written to %s", out_dir)


if __name__ == "__main__":
    main()
