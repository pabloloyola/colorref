"""Validate saved magnitude results and write CPU-only exploratory breakdowns."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.magnitude_analysis import analyze, report  # noqa: E402
from run_magnitude_control import (  # noqa: E402
    load_controller,
    load_plan,
    load_rows,
    run_lock,
    write_json,
)


def run_analysis(directory):
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        calibration = load_rows(directory, plan["calibration_tasks"], metadata)
        bundle = load_controller(directory, cfg, plan, calibration)
        evaluation = load_rows(
            directory, bundle["evaluation_tasks"] if bundle else [], metadata
        )
        result = analyze(cfg, plan, bundle, evaluation)
        write_json(directory / "metrics/magnitude_breakdown.json", result)
        (directory / "reports/magnitude_breakdown.md").write_text(
            report(result, directory.name)
        )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run_analysis(args.run)
    print(f"CPU audit: {args.run}/reports/magnitude_breakdown.md")


if __name__ == "__main__":
    main()
