"""Run/resume the shared-start control using a validated saved interface study."""

from __future__ import annotations

import argparse
import copy
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.quantifier_study import plan_digest  # noqa: E402
from colorref.shared_start_reports import write_reports  # noqa: E402
from colorref.shared_start_study import (  # noqa: E402
    freeze_inputs,
    generation_diagnostics,
    is_complete,
    revision_prompt,
    revision_record,
    validate_checkpoint,
    validate_plan,
)
from run_interface_study import (  # noqa: E402
    checkpoint_path,
    load_checkpoints as load_parent_checkpoints,
    load_plan as load_parent_plan,
    run_lock,
    write_json,
)

logger = logging.getLogger(__name__)


def prepare_parent(
    parent_dir, name="shared_start_interface_study_a100_40gb", output_root=None
):
    with run_lock(parent_dir):
        parent_cfg, parent_plan, parent_metadata = load_parent_plan(parent_dir)
        checkpoints = load_parent_checkpoints(
            parent_dir, parent_cfg, parent_plan, parent_metadata
        )
        cfg = copy.deepcopy(parent_cfg)
        cfg["experiment_name"] = name
        cfg["input"] = {
            "parent_run": str(parent_dir),
            "start_policy": "parent_hex_turn_0_displayed_state",
        }
        if output_root is not None:
            cfg["output"]["run_root"] = str(output_root)
        plan = freeze_inputs(cfg, parent_plan, parent_metadata, checkpoints)
    return cfg, plan


def create_run(cfg, plan):
    validate_plan(cfg, plan)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        + "_"
        + cfg["experiment_name"]
    )
    run_dir = Path(cfg.get("output", {}).get("run_root", "runs")) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for folder in ("inputs", "raw_outputs/games", "reports", "metrics"):
        (run_dir / folder).mkdir(parents=True)
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )
    write_json(run_dir / "inputs/plan.json", plan)
    write_json(
        run_dir / "metadata.json",
        {
            "schema_version": 1,
            "study_kind": "shared_start_interface",
            "run_id": run_id,
            "plan_sha256": plan_digest([plan]),
            "config_sha256": plan_digest([cfg]),
            "parent": plan["parent"],
            "state_space": "clipped_rounded_uint8_srgb",
            "primary_evaluation": "projected_lab_first_revision",
            "fixed_feedback_rounds": cfg["execution"]["max_turns"],
            "invocations": [],
        },
    )
    return run_dir


def load_plan(run_dir):
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "inputs/plan.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    if (
        metadata.get("study_kind") != "shared_start_interface"
        or metadata["schema_version"] != 1
        or metadata["plan_sha256"] != plan_digest([plan])
        or metadata["config_sha256"] != plan_digest([cfg])
        or metadata["parent"] != plan["parent"]
    ):
        raise ValueError("Frozen shared-start study failed integrity validation")
    validate_plan(cfg, plan)
    return cfg, plan, metadata


def load_checkpoints(run_dir, cfg, plan, metadata):
    known = {checkpoint_path(run_dir, t) for t in plan["tasks"]}
    if set((run_dir / "raw_outputs/games").glob("*.json")) - known:
        raise ValueError("Checkpoint folder contains an unknown shared-start game")
    result = {}
    for task in plan["tasks"]:
        path = checkpoint_path(run_dir, task)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload["run_id"] != metadata["run_id"]
            or payload["condition_id"] != task["condition_id"]
        ):
            raise ValueError(
                "Checkpoint belongs to a different shared-start run/condition"
            )
        validate_checkpoint(task, payload["records"], cfg, plan["templates"])
        result[task["slot"]] = payload["records"]
    return result


def run_pending(client, cfg, plan, metadata, run_dir, checkpoints, limit=None):
    calls = 0
    for task in plan["tasks"]:
        records = checkpoints.setdefault(task["slot"], [])
        while not is_complete(records, cfg["execution"]["max_turns"]):
            if limit is not None and calls >= limit:
                return calls
            prompt, feedback = revision_prompt(task, records, cfg, plan["templates"])
            response = client.generate(
                prompt,
                max_tokens=cfg["model"]["max_tokens"],
                temperature=cfg["model"]["temperature"],
            )
            if getattr(response, "error", None):
                write_json(
                    run_dir / "raw_outputs/last_execution_error.json",
                    {
                        "condition_id": task["condition_id"],
                        "turn": len(records) + 1,
                        "error": str(response.error),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise RuntimeError(
                    f"Model execution failed; unfinished revision remains pending: {response.error}"
                )
            row = revision_record(task, records, prompt, feedback, response.text)
            row.update(
                {
                    "model_name": response.model_name,
                    "provider": response.provider,
                    "latency_s": response.latency_s,
                    "generation": generation_diagnostics(response),
                }
            )
            write_json(
                checkpoint_path(run_dir, task),
                {
                    "run_id": metadata["run_id"],
                    "condition_id": task["condition_id"],
                    "records": [*records, row],
                },
            )
            records.append(row)
            calls += 1
            if calls % 20 == 0:
                logger.info(
                    "Saved %d new revisions; %s turn %d",
                    calls,
                    task["condition_id"],
                    row["turn"],
                )
    return calls


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--parent-run", type=Path)
    source.add_argument("--resume", type=Path)
    source.add_argument("--report-only", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--experiment-name", default="shared_start_interface_study_a100_40gb"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit", type=int, help="Maximum new revisions; resume retains the whole plan"
    )
    parser.add_argument("--resamples", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=13)
    args = parser.parse_args()
    if (args.dry_run or args.output_root is not None) and args.parent_run is None:
        parser.error("--dry-run and --output-root require --parent-run")
    if args.limit is not None and (args.limit <= 0 or args.report_only is not None):
        parser.error("--limit must be positive and cannot be used with --report-only")
    if args.resamples < 100:
        parser.error("--resamples must be at least 100")
    if not args.experiment_name or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in args.experiment_name
    ):
        parser.error("--experiment-name must be a safe nonempty identifier")
    return args


def main():
    args = parse_args()
    if args.parent_run is not None:
        cfg, plan = prepare_parent(
            args.parent_run, args.experiment_name, args.output_root
        )
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "parent_run_id": plan["parent"]["run_id"],
                        "examples": len(plan["examples"]),
                        "games": len(plan["tasks"]),
                        "maximum_generations": len(plan["tasks"])
                        * cfg["execution"]["max_turns"],
                        "first_feedback_matched": True,
                        "assigned_starts_are_generations": False,
                        "model": cfg["model"],
                        "example_ids": [e["example_id"] for e in plan["examples"]],
                    },
                    indent=2,
                )
            )
            return
        run_dir = create_run(cfg, plan)
    else:
        run_dir = args.resume if args.resume is not None else args.report_only
    logger.info("Run directory: %s", run_dir)
    with run_lock(run_dir):
        cfg, plan, metadata = load_plan(run_dir)
        checkpoints = load_checkpoints(run_dir, cfg, plan, metadata)
        if args.report_only is not None:
            write_reports(
                cfg, plan, checkpoints, run_dir, args.resamples, args.bootstrap_seed
            )
            return
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        metadata["invocations"].append(
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "git_revision": revision.stdout.strip()
                if revision.returncode == 0
                else None,
                "saved_responses_at_start": sum(len(r) for r in checkpoints.values()),
                "resumed": args.resume is not None,
                "limit": args.limit,
            }
        )
        write_json(run_dir / "metadata.json", metadata)
        try:
            if any(
                not is_complete(
                    checkpoints.get(t["slot"], []), cfg["execution"]["max_turns"]
                )
                for t in plan["tasks"]
            ):
                from colorref.llm_clients import build_client

                client = build_client(cfg["model"])
                run_pending(
                    client, cfg, plan, metadata, run_dir, checkpoints, args.limit
                )
        finally:
            write_reports(
                cfg, plan, checkpoints, run_dir, args.resamples, args.bootstrap_seed
            )
        logger.info("Summary: %s/reports/shared_start_summary.md", run_dir)


if __name__ == "__main__":
    main()
