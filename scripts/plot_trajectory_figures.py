#!/usr/bin/env python3
"""Generate paper-ready LAB trajectory visualizations.

Usage:
    uv run python scripts/plot_trajectory_figures.py
    uv run python scripts/plot_trajectory_figures.py --out reports/figures/trajectory_showcase
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.trajectory_viz import plot_paper_showcase  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Plot ColorRef LAB trajectory figures.")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("reports/figures/trajectory_showcase"),
        help="Output directory for PNG/PDF figures",
    )
    args = p.parse_args()
    paths = plot_paper_showcase(args.out)
    print(f"Wrote {len(paths)} figures to {args.out.resolve()}:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
