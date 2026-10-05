"""Build ICL context files for all eval examples.

Usage:
    uv run python scripts/build_icl_contexts.py \\
        --input data/colornames_taxonomy.parquet \\
        --eval_subset data/eval_subsets/main_1000.parquet \\
        --out_dir data/icl_contexts \\
        --k_values 2 4 8 \\
        --modes random regime_matched text_similar \\
        --seed 13
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.icl import build_context_pool, build_contexts_for_subset, build_tfidf_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build ICL context files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", default="data/colornames_taxonomy.parquet")
    p.add_argument("--eval_subset", default="data/eval_subsets/main_1000.parquet")
    p.add_argument("--out_dir", default="data/icl_contexts")
    p.add_argument("--k_values", type=int, nargs="+", default=[2, 4, 8])
    p.add_argument("--modes", nargs="+",
                   default=["random", "regime_matched", "text_similar"])
    p.add_argument("--seed", type=int, default=13)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading taxonomy: %s", args.input)
    pool = build_context_pool(args.input, args.eval_subset)
    eval_df = pd.read_parquet(args.eval_subset)
    logger.info("Eval subset: %d examples", len(eval_df))

    # Pre-build TF-IDF index once (reused across k values)
    tfidf_index = None
    if "text_similar" in args.modes:
        logger.info("Building TF-IDF index on pool of %d items...", len(pool))
        tfidf_index = build_tfidf_index(pool)

    subset_stem = Path(args.eval_subset).stem

    for mode in args.modes:
        for k in args.k_values:
            logger.info("Building contexts: mode=%s k=%d", mode, k)
            df = build_contexts_for_subset(
                eval_df, pool, k=k, mode=mode,
                global_seed=args.seed,
                tfidf_index=tfidf_index if mode == "text_similar" else None,
            )
            out_path = out_dir / f"{subset_stem}_{mode}_k{k}.parquet"
            df.to_parquet(out_path, index=False)
            logger.info("Saved: %s (%d rows)", out_path, len(df))

    logger.info("Done.")


if __name__ == "__main__":
    main()
