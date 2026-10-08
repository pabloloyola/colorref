"""Run, resume, or reanalyze paired HEX/plain-LAB/legend-LAB reference games."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.interface_study import (  # noqa: E402
    build_tasks,
    is_complete,
    next_prompt,
    score_record,
    select_examples,
    validate_checkpoint,
    validate_config,
)
from colorref.interface_study_reports import write_reports  # noqa: E402
from colorref.quantifier_study import plan_digest  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextlib.contextmanager
def run_lock(run_dir):
    with (run_dir / "run.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another process is using this run; wait for it to finish"
            ) from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def create_run(cfg, templates, examples, config_path):
    tasks = build_tasks(cfg, examples)
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
    plan = {"templates": templates, "examples": examples, "tasks": tasks}
    write_json(run_dir / "inputs" / "plan.json", plan)
    write_json(
        run_dir / "metadata.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "config_path": str(config_path),
            "plan_sha256": plan_digest([plan]),
            "config_sha256": plan_digest([cfg]),
            "model": cfg["model"],
            "teacher": cfg["teacher"],
            "input_artifact": {
                "path": cfg["input"]["subset_path"],
                "sha256": hashlib.sha256((ROOT / cfg["input"]["subset_path"]).read_bytes()).hexdigest(),
            } if (ROOT / cfg["input"]["subset_path"]).is_file() else None,
            "state_space": "clipped_rounded_uint8_srgb",
            "primary_evaluation": "projected_lab",
            "fixed_feedback_rounds": cfg["execution"]["max_turns"],
            "invocations": [],
        },
    )
    return run_dir


def load_plan(run_dir):
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "inputs" / "plan.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    if (
        metadata["schema_version"] != 1
        or metadata["plan_sha256"] != plan_digest([plan])
        or metadata["config_sha256"] != plan_digest([cfg])
    ):
        raise ValueError(
            "Frozen study plan or configuration failed integrity validation"
        )
    validate_config(cfg, plan["templates"])
    if build_tasks(cfg, plan["examples"]) != plan["tasks"]:
        raise ValueError("Frozen example selection does not match the task plan")
    return cfg, plan, metadata


def checkpoint_path(run_dir, task):
    return run_dir / "raw_outputs" / "games" / f"{task['slot']:04d}.json"


def load_checkpoints(run_dir, cfg, plan, metadata):
    known_paths = {checkpoint_path(run_dir, t) for t in plan["tasks"]}
    if set((run_dir / "raw_outputs" / "games").glob("*.json")) - known_paths:
        raise ValueError("Checkpoint folder contains an unknown game")
    checkpoints = {}
    for task in plan["tasks"]:
        path = checkpoint_path(run_dir, task)
        if not path.exists():
            continue
        saved = json.loads(path.read_text(encoding="utf-8"))
        if (
            saved["run_id"] != metadata["run_id"]
            or saved["condition_id"] != task["condition_id"]
        ):
            raise ValueError("Checkpoint belongs to a different run or condition")
        records = saved["records"]
        validate_checkpoint(task, records, cfg, plan["templates"])
        checkpoints[task["slot"]] = records
    return checkpoints


def run_pending(client, cfg, plan, metadata, run_dir, checkpoints, limit=None):
    calls = 0
    for task in plan["tasks"]:
        records = checkpoints.setdefault(task["slot"], [])
        while not is_complete(records, cfg["execution"]["max_turns"]):
            if limit is not None and calls >= limit:
                return calls
            prompt, feedback = next_prompt(task, records, cfg, plan["templates"])
            response = client.generate(
                prompt,
                max_tokens=cfg["model"]["max_tokens"],
                temperature=cfg["model"]["temperature"],
            )
            if getattr(response, "error", None):
                write_json(
                    run_dir / "raw_outputs" / "last_execution_error.json",
                    {
                        "condition_id": task["condition_id"],
                        "turn": len(records),
                        "error": str(response.error),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise RuntimeError(
                    f"Model execution failed; unfinished turn remains pending: {response.error}"
                )
            row = score_record(task, records, prompt, feedback, response.text)
            row.update(
                {
                    "model_name": response.model_name,
                    "provider": response.provider,
                    "latency_s": response.latency_s,
                }
            )
            updated = [*records, row]
            write_json(
                checkpoint_path(run_dir, task),
                {
                    "run_id": metadata["run_id"],
                    "condition_id": task["condition_id"],
                    "records": updated,
                },
            )
            records.append(row)
            calls += 1
            if calls % 20 == 0:
                logger.info(
                    "Saved %d new responses; current %s turn %d",
                    calls,
                    task["condition_id"],
                    row["turn"],
                )
    return calls


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--resume", type=Path)
    source.add_argument("--report-only", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum new generations; resume retains the full plan",
    )
    args = parser.parse_args()
    if args.dry_run and args.config is None:
        parser.error("--dry-run requires --config")
    if args.limit is not None and (args.limit <= 0 or args.report_only is not None):
        parser.error("--limit must be positive and cannot be used for report-only")
    return args


def main():
    args = parse_args()
    if args.config is not None:
        import pandas as pd

        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        templates = {
            v["id"]: {
                phase: (ROOT / v[f"{phase}_template_path"]).read_text(encoding="utf-8")
                for phase in ("initial", "revision")
            }
            for v in cfg["study"]["variants"]
        }
        validate_config(cfg, templates)
        examples = select_examples(
            pd.read_parquet(ROOT / cfg["input"]["subset_path"]),
            cfg["study"]["examples_per_regime"],
            cfg["seed"],
        )
        tasks = build_tasks(cfg, examples)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "examples": len(examples),
                        "study_design": cfg["study"].get("design", "interface_comparison"),
                        "examples_per_regime": cfg["study"]["examples_per_regime"],
                        "games": len(tasks),
                        "maximum_generations": len(tasks)
                        * (cfg["execution"]["max_turns"] + 1),
                        "state_space": "clipped_rounded_uint8_srgb",
                        "primary_evaluation": "projected_lab",
                        "example_ids": [x["example_id"] for x in examples],
                    },
                    indent=2,
                )
            )
            return
        run_dir = create_run(cfg, templates, examples, args.config)
    else:
        run_dir = args.resume if args.resume is not None else args.report_only
    logger.info("Run directory: %s", run_dir)
    with run_lock(run_dir):
        cfg, plan, metadata = load_plan(run_dir)
        checkpoints = load_checkpoints(run_dir, cfg, plan, metadata)
        if args.report_only is not None:
            write_reports(cfg, plan["tasks"], checkpoints, run_dir)
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
                "saved_responses_at_start": sum(len(x) for x in checkpoints.values()),
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
            write_reports(cfg, plan["tasks"], checkpoints, run_dir)
        report_name = "grounding_summary.md" if cfg["study"].get("design") == "grounding_replication" else "interface_summary.md"
        logger.info("Summary: %s/reports/%s", run_dir, report_name)


if __name__ == "__main__":
    main()
