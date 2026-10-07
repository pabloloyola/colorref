"""Inspect saved shared-start trajectories, defaulting to initially close cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.shared_start_study import supplied_start  # noqa: E402
from run_shared_start_study import (  # noqa: E402
    load_checkpoints,
    load_plan,
    run_lock,
)


def inspect(run_dir, example_id=None):
    """Validate frozen inputs/checkpoints and return observations without inference."""
    with run_lock(run_dir):
        cfg, plan, metadata = load_plan(run_dir)
        saved = load_checkpoints(run_dir, cfg, plan, metadata)
        threshold = cfg["execution"]["convergence_delta_e"]
        known_ids = {e["example_id"] for e in plan["examples"]}
        if example_id is not None and example_id not in known_ids:
            raise ValueError(f"Unknown example ID: {example_id}")
        cases = {}
        for task in plan["tasks"]:
            start = supplied_start(task)
            example = task["example"]
            identifier = example["example_id"]
            if example_id is None and start["projected_error_delta_e"] > threshold:
                continue
            if example_id is not None and identifier != example_id:
                continue
            case = cases.setdefault(
                identifier,
                {
                    "example_id": identifier,
                    "description": example["raw_name"],
                    "regime": example["regime_label"],
                    "target_hex": example["hex"],
                    "supplied_start": start["displayed_state"],
                    "starting_error": start["projected_error_delta_e"],
                    "initially_converged": start["projected_error_delta_e"]
                    <= threshold,
                    "trajectories": [],
                },
            )
            records = saved.get(task["slot"], [])
            case["trajectories"].append(
                {
                    "condition_id": task["condition_id"],
                    "first_prompt": records[0]["prompt"] if records else None,
                    "errors_by_turn": [
                        start["projected_error_delta_e"],
                        *[r["projected_error_delta_e"] for r in records],
                    ],
                    "revisions": [
                        {
                            "turn": r["turn"],
                            "feedback": r["feedback"]["text"],
                            "constraints": r["feedback"]["metadata"].get(
                                "all_constraints", []
                            ),
                            "raw_response": r["raw_response"],
                            "parse_ok": r["parse_ok"],
                            "native_lab": r["native_lab"],
                            "displayed_state": r["displayed_state"],
                            "projected_error": r["projected_error_delta_e"],
                            "constraint_satisfaction": r["constraint_satisfaction"],
                            "directional_alignment": r["directional_alignment"],
                            "generation": r.get("generation"),
                        }
                        for r in records
                    ],
                }
            )
        return {
            "run_id": metadata["run_id"],
            "convergence_threshold": threshold,
            "selection": "initially_converged" if example_id is None else "example_id",
            "case_count": len(cases),
            "cases": [cases[i] for i in sorted(cases)],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument(
        "--example-id",
        help="Inspect a specific frozen example instead of initially close starts",
    )
    args = parser.parse_args()
    print(json.dumps(inspect(args.run, args.example_id), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
