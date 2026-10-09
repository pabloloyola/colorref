"""Run/resume single-axis calibration then matched held-out magnitude evaluation."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from run_interface_study import run_lock, write_json  # noqa: E402
from colorref.magnitude_control import build_plan, evaluation_arms, evaluation_tasks, fit_mapping, score  # noqa: E402
from colorref.magnitude_reports import analyze, report  # noqa: E402
from colorref.quantifier_study import plan_digest  # noqa: E402
from colorref.shared_start_study import generation_diagnostics  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def create_run(cfg, plan, config_path):
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        + "_"
        + cfg["experiment_name"]
    )
    directory = Path(cfg["output"]["run_root"]) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    for folder in (
        "inputs",
        "raw_outputs/calibration",
        "raw_outputs/evaluation",
        "reports",
        "metrics",
    ):
        (directory / folder).mkdir(parents=True)
    (directory / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    write_json(directory / "inputs/plan.json", plan)
    write_json(
        directory / "metadata.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "config_path": str(config_path),
            "plan_sha256": plan_digest([plan]),
            "config_sha256": plan_digest([cfg]),
            "invocations": [],
        },
    )
    return directory


def load_plan(directory):
    cfg = yaml.safe_load((directory / "config.yaml").read_text())
    plan = json.loads((directory / "inputs/plan.json").read_text())
    metadata = json.loads((directory / "metadata.json").read_text())
    if (
        metadata["schema_version"] != 1
        or metadata["config_sha256"] != plan_digest([cfg])
        or metadata["plan_sha256"] != plan_digest([plan])
        or build_plan(cfg, plan["template"]) != plan
    ):
        raise ValueError("Frozen magnitude plan/config failed validation")
    return cfg, plan, metadata


def checkpoint_path(directory, task):
    # IDs are generated internally; SHA filenames avoid colons/unsafe paths.
    return (
        directory
        / "raw_outputs"
        / task["phase"]
        / (plan_digest([task])[0:32] + ".json")
    )


def load_rows(directory, tasks, metadata):
    phase = tasks[0]["phase"] if tasks else "evaluation"
    known = {
        checkpoint_path(directory, t)
        for t in tasks
        if t.get("status", "generate") == "generate"
    }
    if set((directory / "raw_outputs" / phase).glob("*.json")) - known:
        raise ValueError("Unknown magnitude checkpoint")
    rows = {}
    for task in tasks:
        path = checkpoint_path(directory, task)
        if not path.exists():
            continue
        row = json.loads(path.read_text())
        if row.get("run_id") != metadata["run_id"]:
            raise ValueError("Checkpoint belongs to another run")
        expected = score(task, row["raw_response"])
        if any(row.get(k) != v for k, v in expected.items()):
            raise ValueError("Checkpoint does not match frozen task/score")
        rows[task["condition_id"]] = row
    return rows


def controller_bundle(cfg, plan, calibration):
    mapping = fit_mapping(cfg, plan, calibration)
    return {
        "mapping": mapping,
        "evaluation_tasks": evaluation_tasks(cfg, plan, mapping),
    }


def load_controller(directory, cfg, plan, calibration, allow_create=False):
    path = directory / "inputs/controller.json"
    complete = len(calibration) == len(plan["calibration_tasks"])
    if not complete:
        if path.exists() or list((directory / "raw_outputs/evaluation").glob("*.json")):
            raise ValueError("Evaluation artifacts exist before complete calibration")
        return None
    bundle = controller_bundle(cfg, plan, calibration)
    if path.exists():
        if json.loads(path.read_text()) != bundle:
            raise ValueError("Frozen controller differs from calibration outputs")
    elif allow_create:
        write_json(path, bundle)
    elif list((directory / "raw_outputs/evaluation").glob("*.json")):
        raise ValueError("Evaluation checkpoints have no frozen controller")
    return bundle


def run_tasks(client, cfg, tasks, directory, metadata, rows, limit=None):
    calls = 0
    for task in tasks:
        if task.get("status", "generate") != "generate" or task["condition_id"] in rows:
            continue
        if limit is not None and calls >= limit:
            break
        response = client.generate(
            task["prompt"],
            max_tokens=cfg["model"]["max_tokens"],
            temperature=cfg["model"]["temperature"],
        )
        if getattr(response, "error", None):
            write_json(
                directory / "raw_outputs/last_execution_error.json",
                {
                    "condition_id": task["condition_id"],
                    "error": str(response.error),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            raise RuntimeError("Backend error: condition remains pending for resume")
        raw = getattr(response, "raw", None) or {}
        row = {
            **score(task, response.text),
            "run_id": metadata["run_id"],
            "model_name": response.model_name,
            "provider": response.provider,
            "latency_s": response.latency_s,
            "generation": generation_diagnostics(response),
            "prompt_tokens": raw.get(
                "prompt_tokens", (raw.get("usage") or {}).get("prompt_tokens")
            ),
        }
        write_json(checkpoint_path(directory, task), row)
        rows[task["condition_id"]] = row
        calls += 1
        if calls % 12 == 0:
            logger.info(
                "Saved %s %d/%d responses", task["phase"], len(rows), len(tasks)
            )
    return calls


def write_reports(directory, cfg, plan, calibration, bundle, evaluation):
    result = analyze(
        cfg,
        plan,
        calibration,
        bundle["mapping"] if bundle else None,
        bundle["evaluation_tasks"] if bundle else [],
        evaluation,
    )
    write_json(directory / "metrics/magnitude_analysis.json", result)
    (directory / "reports/magnitude_summary.md").write_text(
        report(result, directory.name)
    )
    return result


def execute(directory, phase="all", limit=None, report_only=False):
    """A single client per invocation; incomplete calibration cannot start evaluation."""
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        calibration = load_rows(directory, plan["calibration_tasks"], metadata)
        bundle = load_controller(directory, cfg, plan, calibration)
        evaluation = load_rows(
            directory, bundle["evaluation_tasks"] if bundle else [], metadata
        )
        if report_only:
            return write_reports(directory, cfg, plan, calibration, bundle, evaluation)
        if phase == "evaluation" and bundle is None:
            raise ValueError("Finish calibration before evaluation")
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
                "phase": phase,
                "limit": limit,
            }
        )
        write_json(directory / "metadata.json", metadata)
        client = None

        def get_client():
            nonlocal client
            if client is None:
                from colorref.llm_clients import build_client

                client = build_client(cfg["model"])
                model = getattr(client, "_model_and_tokenizer", (None, None))[0]
                resolved = getattr(getattr(model, "config", None), "_commit_hash", None)
                previous = metadata.get("resolved_model_revision")
                if previous is not None and resolved != previous:
                    raise ValueError(
                        "Model revision changed since calibration; keep the original model snapshot"
                    )
                if resolved is not None:
                    metadata["resolved_model_revision"] = resolved
                    metadata["invocations"][-1]["resolved_model_revision"] = resolved
                    write_json(directory / "metadata.json", metadata)
            return client

        try:
            used = 0
            if phase in ("calibration", "all") and len(calibration) < len(
                plan["calibration_tasks"]
            ):
                used = run_tasks(
                    get_client(),
                    cfg,
                    plan["calibration_tasks"],
                    directory,
                    metadata,
                    calibration,
                    limit,
                )
            bundle = load_controller(
                directory, cfg, plan, calibration, allow_create=True
            )
            if phase in ("evaluation", "all") and bundle is not None:
                tasks = bundle["evaluation_tasks"]
                if (limit is None or used < limit) and any(
                    t["status"] == "generate" and t["condition_id"] not in evaluation
                    for t in tasks
                ):
                    run_tasks(
                        get_client(),
                        cfg,
                        tasks,
                        directory,
                        metadata,
                        evaluation,
                        None if limit is None else limit - used,
                    )
        finally:
            write_reports(directory, cfg, plan, calibration, bundle, evaluation)
    logger.info("Summary: %s/reports/magnitude_summary.md", directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--resume", type=Path)
    source.add_argument("--report-only", type=Path)
    parser.add_argument(
        "--phase", choices=("calibration", "evaluation", "all"), default="all"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        help="New response cap, preserving the full plan for resume",
    )
    args = parser.parse_args()
    if args.limit is not None and (args.limit <= 0 or args.report_only is not None):
        parser.error("--limit must be positive and cannot be used with --report-only")
    if args.dry_run and args.config is None:
        parser.error("--dry-run requires --config")
    if args.config is not None:
        cfg = yaml.safe_load(args.config.read_text())
        path = Path(cfg["study"]["template_path"])
        template = path.read_text() if path.is_absolute() else (ROOT / path).read_text()
        plan = build_plan(cfg, template)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "calibration_colors": len(plan["splits"]["calibration"]),
                        "evaluation_colors": len(plan["splits"]["evaluation"]),
                        "calibration_calls": len(plan["calibration_tasks"]),
                        "held_out_cases": len(plan["evaluation_cases"]),
                        "arms": list(evaluation_arms(cfg)),
                        "primary_comparison": ["unfitted", "calibrated"] if "unfitted_cutpoints" in cfg["study"] else ["bare", "calibrated"],
                        "maximum_evaluation_calls": len(evaluation_arms(cfg))
                        * sum(
                            not c["initially_converged"]
                            for c in plan["evaluation_cases"]
                        ),
                        "feasibility_exclusions": len(plan["feasibility_exclusions"]),
                        "targets_frozen_before_calibration": True,
                        "model": cfg["model"],
                    },
                    indent=2,
                )
            )
            return
        directory = create_run(cfg, plan, args.config)
    else:
        directory = args.resume or args.report_only
    logger.info("Run directory: %s", directory)
    execute(directory, args.phase, args.limit, args.report_only is not None)


if __name__ == "__main__":
    main()
