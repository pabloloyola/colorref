"""Run/resume fresh-start sequential transfer of a frozen magnitude controller."""

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
from colorref.magnitude_control import score  # noqa: E402
from colorref.magnitude_transfer import (  # noqa: E402
    build_plan,
    next_revision,
    transfer_config,
    validate_records,
)
from colorref.magnitude_transfer_reports import analyze, report  # noqa: E402
from colorref.quantifier_study import plan_digest  # noqa: E402
from colorref.shared_start_study import generation_diagnostics  # noqa: E402
from run_magnitude_control import (  # noqa: E402
    load_controller,
    load_plan as load_parent_plan,
    load_rows,
    run_lock,
    write_json,
)

logger = logging.getLogger(__name__)


def prepare_parent(parent_dir, name="magnitude_transfer_a100_40gb", output_root=None):
    with run_lock(parent_dir):
        cfg, plan, metadata = load_parent_plan(parent_dir)
        calibration = load_rows(parent_dir, plan["calibration_tasks"], metadata)
        if not (parent_dir / "inputs/controller.json").is_file():
            raise ValueError(
                "Parent has no frozen controller; complete calibration first"
            )
        bundle = load_controller(parent_dir, cfg, plan, calibration)
        if bundle is None:
            raise ValueError("Complete parent calibration before transfer")
        evaluation = load_rows(parent_dir, bundle["evaluation_tasks"], metadata)
        snapshot = {
            "config": cfg,
            "plan": plan,
            "metadata": metadata,
            "calibration": calibration,
            "controller": bundle,
            "evaluation_completed": len(evaluation),
            "evaluation_outputs_sha256": plan_digest(
                [
                    evaluation[t["condition_id"]]
                    for t in bundle["evaluation_tasks"]
                    if t["condition_id"] in evaluation
                ]
            ),
            "source_directory": str(parent_dir),
        }
        cfg = transfer_config(snapshot, name, output_root)
        plan = build_plan(cfg, snapshot)
    return cfg, plan, snapshot


def create_run(cfg, plan, snapshot):
    if build_plan(cfg, snapshot) != plan:
        raise ValueError("Transfer plan failed reproduction")
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        + "_"
        + cfg["experiment_name"]
    )
    directory = Path(cfg["output"]["run_root"]) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    for folder in ("inputs", "raw_outputs/games", "reports", "metrics"):
        (directory / folder).mkdir(parents=True)
    (directory / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    write_json(directory / "inputs/plan.json", plan)
    write_json(directory / "inputs/parent_snapshot.json", snapshot)
    write_json(
        directory / "metadata.json",
        {
            "schema_version": 1,
            "study_kind": "sequential_magnitude_transfer",
            "run_id": run_id,
            "config_sha256": plan_digest([cfg]),
            "plan_sha256": plan_digest([plan]),
            "parent_snapshot_sha256": plan_digest([snapshot]),
            "required_model_revision": plan["required_model_revision"],
            "invocations": [],
        },
    )
    return directory


def load_plan(directory):
    cfg = yaml.safe_load((directory / "config.yaml").read_text())
    plan = json.loads((directory / "inputs/plan.json").read_text())
    snapshot = json.loads((directory / "inputs/parent_snapshot.json").read_text())
    metadata = json.loads((directory / "metadata.json").read_text())
    if (
        metadata.get("schema_version") != 1
        or metadata.get("study_kind") != "sequential_magnitude_transfer"
        or metadata["config_sha256"] != plan_digest([cfg])
        or metadata["plan_sha256"] != plan_digest([plan])
        or metadata["parent_snapshot_sha256"] != plan_digest([snapshot])
        or metadata["required_model_revision"] != plan["required_model_revision"]
        or build_plan(cfg, snapshot) != plan
    ):
        raise ValueError("Frozen transfer inputs failed integrity validation")
    return cfg, plan, metadata


def checkpoint_path(directory, game):
    return directory / "raw_outputs/games" / f"{game['slot']:04d}.json"


def load_checkpoints(directory, cfg, plan, metadata):
    known = {checkpoint_path(directory, g) for g in plan["games"]}
    if set((directory / "raw_outputs/games").glob("*.json")) - known:
        raise ValueError("Unknown transfer game checkpoint")
    result = {}
    for game in plan["games"]:
        path = checkpoint_path(directory, game)
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        if (
            payload["run_id"] != metadata["run_id"]
            or payload["condition_id"] != game["condition_id"]
        ):
            raise ValueError("Transfer checkpoint belongs to another run/game")
        validate_records(game, payload["records"], cfg, plan, metadata["run_id"])
        result[game["condition_id"]] = payload["records"]
    return result


def write_reports(directory, cfg, plan, checkpoints):
    result = analyze(cfg, plan, checkpoints)
    write_json(directory / "metrics/transfer_analysis.json", result)
    (directory / "reports/transfer_summary.md").write_text(
        report(result, directory.name)
    )
    return result


def execute(directory, limit=None, report_only=False):
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("Limit must be a positive number of new revisions")
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        checkpoints = load_checkpoints(directory, cfg, plan, metadata)
        if report_only:
            return write_reports(directory, cfg, plan, checkpoints)
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
                "limit": limit,
                "git_revision": revision.stdout.strip()
                if revision.returncode == 0
                else None,
            }
        )
        write_json(directory / "metadata.json", metadata)
        client = None
        calls = 0
        try:
            for game in plan["games"]:
                if limit is not None and calls >= limit:
                    break
                records = checkpoints.setdefault(game["condition_id"], [])
                while True:
                    reason, task = next_revision(game, records, cfg, plan)
                    if reason is not None:
                        break
                    if limit is not None and calls >= limit:
                        break
                    if client is None:
                        from colorref.llm_clients import build_client

                        client = build_client(cfg["model"])
                        model = getattr(client, "_model_and_tokenizer", (None, None))[0]
                        resolved = getattr(
                            getattr(model, "config", None), "_commit_hash", None
                        )
                        previous = plan["required_model_revision"] or metadata.get(
                            "resolved_model_revision"
                        )
                        if previous is not None and resolved != previous:
                            raise ValueError(
                                "Model revision changed; use the original calibration snapshot"
                            )
                        if resolved is not None:
                            metadata["resolved_model_revision"] = resolved
                            metadata["invocations"][-1]["resolved_model_revision"] = (
                                resolved
                            )
                            write_json(directory / "metadata.json", metadata)
                    response = client.generate(
                        task["prompt"],
                        max_tokens=cfg["model"]["max_tokens"],
                        temperature=cfg["model"]["temperature"],
                    )
                    if getattr(response, "error", None):
                        write_json(
                            directory / "raw_outputs/last_execution_error.json",
                            {
                                "condition_id": game["condition_id"],
                                "turn": task["turn"],
                                "error": str(response.error),
                                "at": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                        raise RuntimeError(
                            "Backend error: unfinished transfer revision remains pending for resume"
                        )
                    raw = getattr(response, "raw", None) or {}
                    row = {
                        **score(task, response.text),
                        "run_id": metadata["run_id"],
                        "model_name": response.model_name,
                        "provider": response.provider,
                        "latency_s": response.latency_s,
                        "generation": generation_diagnostics(response),
                        "prompt_tokens": raw.get(
                            "prompt_tokens",
                            (raw.get("usage") or {}).get("prompt_tokens"),
                        ),
                    }
                    write_json(
                        checkpoint_path(directory, game),
                        {
                            "run_id": metadata["run_id"],
                            "condition_id": game["condition_id"],
                            "records": [*records, row],
                        },
                    )
                    records.append(row)
                    calls += 1
                    if calls % 12 == 0:
                        logger.info(
                            "Saved %d new revisions; %s revision %d",
                            calls,
                            game["condition_id"],
                            task["turn"],
                        )
        finally:
            result = write_reports(directory, cfg, plan, checkpoints)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--parent-run", type=Path)
    source.add_argument("--resume", type=Path)
    source.add_argument("--report-only", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--experiment-name", default="magnitude_transfer_a100_40gb")
    parser.add_argument(
        "--limit", type=int, help="New revisions this invocation; full plan retained"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if (args.output_root is not None or args.dry_run) and args.parent_run is None:
        parser.error("--output-root and --dry-run require --parent-run")
    if args.limit is not None and (
        args.limit <= 0 or args.report_only is not None or args.dry_run
    ):
        parser.error(
            "--limit must be positive; unavailable with --report-only or --dry-run"
        )
    if args.parent_run is not None:
        cfg, plan, snapshot = prepare_parent(
            args.parent_run, args.experiment_name, args.output_root
        )
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "parent_run_id": plan["parent_run_id"],
                        "fresh_starts": len(plan["starts"]),
                        "feasible_targets": len(plan["evaluation_cases"]),
                        "feasibility_exclusions": len(plan["feasibility_exclusions"]),
                        "games": len(plan["games"]),
                        "max_revisions": cfg["execution"]["max_revisions"],
                        "maximum_generations": len(plan["games"])
                        * cfg["execution"]["max_revisions"],
                        "new_calibration_generations": 0,
                        "required_model_revision": plan["required_model_revision"],
                        "model": cfg["model"],
                        "fresh_start_hex": [s["state"]["hex"] for s in plan["starts"]],
                    },
                    indent=2,
                )
            )
            return
        directory = create_run(cfg, plan, snapshot)
        print(f"Run directory: {directory}", flush=True)
    else:
        directory = args.resume or args.report_only
    execute(directory, args.limit, args.report_only is not None)
    print(f"Summary: {directory}/reports/transfer_summary.md", flush=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    main()
