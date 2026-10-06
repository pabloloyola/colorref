"""Print exact prompts and responses for failed saved numeric/no-change controls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.colors import color_distance_lab  # noqa: E402
from colorref.parsing import extract_lab  # noqa: E402
from run_quantifier_study import load_plan, read_trial_records  # noqa: E402


def control_misses(rows, threshold=0.01):
    """Reparse raw outputs; stored aggregate means do not identify the miss."""
    misses = []
    for row in rows:
        if row["condition_kind"] not in {"numeric", "no_change"}:
            continue
        actual, meta = extract_lab(row["raw_response"])
        if bool(actual is not None) != row["parse_ok"]:
            raise ValueError(
                "Saved parse status disagrees with the raw control response"
            )
        if actual is not None and any(
            abs(x - row[f"guess_lab_{axis}"]) > 1e-8
            for x, axis in zip(actual, ("l", "a", "b"))
        ):
            raise ValueError("Saved coordinates disagree with the raw control response")
        expected = row["expected_lab"]
        error = color_distance_lab(actual, expected) if actual is not None else None
        if error is None or error > threshold:
            misses.append(
                {
                    "condition_id": row["condition_id"],
                    "prompt_variant": row["prompt_variant"],
                    "base_id": row["base_id"],
                    "direction": row["direction"],
                    "condition_name": row["condition_name"],
                    "base_lab": row["base_lab"],
                    "expected_lab": expected,
                    "actual_lab": list(actual) if actual is not None else None,
                    "coordinate_residual": [a - e for a, e in zip(actual, expected)]
                    if actual is not None
                    else None,
                    "control_error_delta_e": error,
                    "parse_reason": meta["reason"],
                    "prompt": row["prompt"],
                    "raw_response": row["raw_response"],
                }
            )
    return misses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    _, conditions, metadata = load_plan(args.run)
    rows = read_trial_records(
        args.run / "raw_outputs" / "responses.jsonl",
        conditions,
        expected_run_id=metadata["run_id"],
    )
    controls = [
        row for row in rows if row["condition_kind"] in {"numeric", "no_change"}
    ]
    misses = control_misses(rows)
    print(
        json.dumps(
            {
                "completed_controls": len(controls),
                "misses_over_0_01_delta_e": len(misses),
                "misses": misses,
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
