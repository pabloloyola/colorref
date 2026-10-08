"""Prepare Mistral replication on the confirmation's unchanged frozen stimuli."""
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
from run_magnitude_control import load_plan

MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
REVISION = "c170c708c41dac9275d15a8fff4eca08d52bab71"


def prepare_config(parent_cfg, parent_plan, parent_meta):
    if (parent_cfg["model"]["model_name"] != "Qwen/Qwen3-14B"
            or len(parent_plan["splits"]["calibration"]) != 32
            or len(parent_plan["splits"]["evaluation"]) != 128
            or set(evaluation_arms(parent_cfg)) != {"bare", "unfitted", "calibrated", "numeric"}):
        raise ValueError("Parent must be the Qwen 32/128 four-arm confirmation")
    cfg = copy.deepcopy(parent_cfg)
    cfg["experiment_name"] = "magnitude_replication_128_mistral7b_a100_40gb"
    cfg["model"].update(
        alias="mistral7b_magnitude_replication_128", model_name=MODEL,
        revision=REVISION, provider="hf_transformers", device_map="auto",
        torch_dtype="bfloat16", temperature=0.0, max_tokens=64,
        enable_thinking=False,
    )
    cfg["replication_sources"] = {
        "parent_run_id": parent_meta["run_id"],
        "parent_plan_sha256": parent_meta["plan_sha256"],
        "parent_config_sha256": parent_meta["config_sha256"],
        "selection_uses_outputs": False,
        "mapping": "fit independently from this model's calibration responses",
    }
    if build_plan(cfg, parent_plan["template"]) != parent_plan:
        raise ValueError("Replication changed the frozen stimuli or task order")
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-run", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/confirmatory/magnitude_128_mistral")
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Output exists; preserve the prepared protocol")
    cfg, plan, metadata = load_plan(args.parent_run)
    cfg = prepare_config(cfg, plan, metadata)
    path = Path(cfg["study"]["template_path"])
    if (path if path.is_absolute() else ROOT / path).read_text() != plan["template"]:
        parser.error("Prompt template differs from the frozen parent")
    summary = {
        "model": cfg["model"], "parent_run_id": metadata["run_id"],
        "same_frozen_plan": True, "calibration_calls": len(plan["calibration_tasks"]),
        "held_out_cases": len(plan["evaluation_cases"]),
        "evaluation_colors": len(plan["splits"]["evaluation"]),
        "arms": list(evaluation_arms(cfg)),
        "maximum_evaluation_calls": len(evaluation_arms(cfg)) * sum(not c["initially_converged"] for c in plan["evaluation_cases"]),
        "primary_comparison": "calibrated minus unfitted displayed target error",
        "config_path": str(args.out_dir / "config.yaml"),
        "parent_plan_file_sha256": hashlib.sha256((args.parent_run / "inputs/plan.json").read_bytes()).hexdigest(),
    }
    args.out_dir.mkdir(parents=True, exist_ok=False)
    (args.out_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (args.out_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
