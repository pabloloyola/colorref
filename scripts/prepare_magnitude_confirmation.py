"""Freeze a 32-calibration/128-held-out four-arm protocol outside prior stimuli."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.magnitude_control import build_plan, evaluation_arms
from run_magnitude_control import load_plan as load_pilot
from run_magnitude_transfer import load_plan as load_transfer


def prepare_config(pilot_cfg, pilot_plan, transfer_plan):
    cfg = copy.deepcopy(pilot_cfg)
    cfg["experiment_name"] = "magnitude_confirmation_128_a100_40gb"
    cfg["seed"] = 211
    cfg["model"]["alias"] = "qwen3_14b_magnitude_confirmation_128"
    cfg["model"]["revision"] = "40c069824f4251a91eefaf281ebe4c544efd3e18"
    cfg["study"].update(calibration_colors=32, evaluation_colors=128, unfitted_cutpoints=[9, 18])
    excluded = set(pilot_plan["excluded_hex"])
    excluded.update(c["state"]["hex"] for split in pilot_plan["splits"].values() for c in split)
    excluded.update(c["state"]["hex"] for c in transfer_plan["starts"])
    cfg["study"]["exclude_hex"] = sorted(excluded)
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-run", type=Path, required=True)
    parser.add_argument("--transfer-run", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/confirmatory/magnitude_128")
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Output directory exists; preserve the frozen protocol")
    pilot_cfg, pilot_plan, pilot_meta = load_pilot(args.pilot_run)
    _, transfer_plan, _ = load_transfer(args.transfer_run)
    if transfer_plan["parent_run_id"] != pilot_meta["run_id"]:
        parser.error("Transfer stimuli come from a different pilot parent")
    if pilot_cfg["model"]["model_name"] != "Qwen/Qwen3-14B":
        parser.error("This confirmation protocol is specified for Qwen3-14B")
    cfg = prepare_config(pilot_cfg, pilot_plan, transfer_plan)
    cfg["preparation_sources"] = {
        "pilot_run_id": pilot_meta["run_id"],
        "pilot_plan_sha256": hashlib.sha256((args.pilot_run / "inputs/plan.json").read_bytes()).hexdigest(),
        "transfer_plan_sha256": hashlib.sha256((args.transfer_run / "inputs/plan.json").read_bytes()).hexdigest(),
        "pilot_resolved_revision": pilot_meta.get("resolved_model_revision"),
        "selection_uses_outputs": False,
    }
    template_path = Path(cfg["study"]["template_path"])
    template = (template_path if template_path.is_absolute() else ROOT / template_path).read_text()
    plan = build_plan(cfg, template)
    summary = {
        "seed": cfg["seed"], "calibration_colors": 32, "evaluation_colors": 128,
        "calibration_calls": len(plan["calibration_tasks"]),
        "held_out_cases": len(plan["evaluation_cases"]),
        "held_out_colors_with_feasible_cases": len({c["base_id"] for c in plan["evaluation_cases"]}),
        "arms": list(evaluation_arms(cfg)), "unfitted_cutpoints": [9, 18],
        "maximum_evaluation_calls": len(evaluation_arms(cfg)) * sum(not c["initially_converged"] for c in plan["evaluation_cases"]),
        "feasibility_exclusions": len(plan["feasibility_exclusions"]),
        "excluded_prior_colors": len(plan["excluded_hex"]),
        "primary_comparison": "calibrated minus unfitted displayed target error",
        "config_path": str(args.out_dir / "config.yaml"),
        "sources": cfg["preparation_sources"],
    }
    args.out_dir.mkdir(parents=True, exist_ok=False)
    (args.out_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (args.out_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
