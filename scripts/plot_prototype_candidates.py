#!/usr/bin/env python3
"""Generate many single-game trajectory prototypes for intro figure selection.

Usage:
    uv run python scripts/plot_prototype_candidates.py
    uv run python scripts/plot_prototype_candidates.py --n 60 --strategy stratified
    uv run python scripts/plot_prototype_candidates.py --run runs/<run_id> --out reports/figures/prototype_candidates
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.trajectory_viz import plot_prototype_candidates  # noqa: E402


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default_run = root / "runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000"

    p = argparse.ArgumentParser(description="Batch-generate prototype trajectory figures.")
    p.add_argument("--run", type=Path, default=default_run, help="Run directory with games/*.parquet")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("reports/figures/prototype_candidates"),
        help="Output directory for PNG gallery",
    )
    p.add_argument("--n", type=int, default=48, help="Number of figures to generate")
    p.add_argument(
        "--strategy",
        choices=("curated", "random", "stratified"),
        default="curated",
        help="curated=top intro scores; stratified=per regime; random=sample",
    )
    p.add_argument("--seed", type=int, default=0, help="RNG seed for --strategy random")
    p.add_argument("--min-turns", type=int, default=4, help="Require at least this many turns")
    p.add_argument(
        "--node-color",
        choices=("hex", "chromaticity"),
        default="hex",
        help="Guess node fill: hex=actual model color; chromaticity=match a*b* background at target L*",
    )
    args = p.parse_args()

    if not args.run.exists():
        raise SystemExit(f"Run not found: {args.run}")

    paths = plot_prototype_candidates(
        args.run,
        args.out,
        n=args.n,
        strategy=args.strategy,
        min_turns=args.min_turns,
        seed=args.seed,
        node_color_mode=args.node_color,
    )
    pngs = [p for p in paths if p.suffix == ".png"]
    print(f"Wrote {len(pngs)} prototypes to {args.out.resolve()}")
    print(f"  Gallery: {(args.out / 'index.html').resolve()}")
    print(f"  Scores:  {(args.out / 'candidates.csv').resolve()}")


if __name__ == "__main__":
    main()
