"""Run/resume matched one-revision reception of original teacher feedback."""

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
from colorref.quantifier_study import plan_digest  # noqa: E402
from colorref.shared_start_study import generation_diagnostics  # noqa: E402
from colorref.teacher_receiver import (  # noqa: E402
    ARMS,
    analyze,
    build_plan,
    report,
    score,
    study_config,
)
from run_interface_study import run_lock, write_json  # noqa: E402
import run_teacher_fidelity_study as teacher  # noqa: E402

logger = logging.getLogger(__name__)


def prepare_parent(parent, name="teacher_receiver_a100_40gb", output_root=None):
    with run_lock(parent):
        cfg, plan, metadata = teacher.load_plan(parent)
        rows = teacher.load_rows(parent, plan, metadata)
        snapshot = {
            "config": cfg,
            "plan": plan,
            "metadata": metadata,
            "parent_snapshot": json.loads(
                (parent / "inputs/parent_snapshot.json").read_text()
            ),
            "rows": rows,
        }
        cfg = study_config(snapshot, name, output_root)
        plan = build_plan(cfg, snapshot)
    return cfg, plan, snapshot


def create_run(cfg, plan, snapshot):
    if build_plan(cfg, snapshot) != plan:
        raise ValueError("Receiver plan failed reproduction")
    identifier = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        + "_"
        + cfg["experiment_name"]
    )
    directory = Path(cfg["output"]["run_root"]) / identifier
    directory.mkdir(parents=True, exist_ok=False)
    for folder in ("inputs", "raw_outputs/responses", "reports", "metrics"):
        (directory / folder).mkdir(parents=True)
    (directory / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    write_json(directory / "inputs/plan.json", plan)
    write_json(directory / "inputs/parent_snapshot.json", snapshot)
    write_json(
        directory / "metadata.json",
        {
            "schema_version": 1,
            "study_kind": "matched_teacher_receiver",
            "run_id": identifier,
            "config_sha256": plan_digest([cfg]),
            "plan_sha256": plan_digest([plan]),
            "parent_snapshot_sha256": plan_digest([snapshot]),
            "required_model_revision": snapshot["metadata"].get(
                "resolved_model_revision"
            ),
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
        or metadata.get("study_kind") != "matched_teacher_receiver"
        or metadata["config_sha256"] != plan_digest([cfg])
        or metadata["plan_sha256"] != plan_digest([plan])
        or metadata["parent_snapshot_sha256"] != plan_digest([snapshot])
        or metadata["required_model_revision"]
        != snapshot["metadata"].get("resolved_model_revision")
        or build_plan(cfg, snapshot) != plan
    ):
        raise ValueError("Frozen receiver inputs failed integrity validation")
    return cfg, plan, metadata


def checkpoint_path(directory, task):
    return directory / "raw_outputs/responses" / f"{task['slot']:04d}.json"


def load_rows(directory, cfg, plan, metadata):
    known = {checkpoint_path(directory, task) for task in plan["tasks"]}
    if set((directory / "raw_outputs/responses").glob("*.json")) - known:
        raise ValueError("Unknown receiver response checkpoint")
    rows = {}
    for task in plan["tasks"]:
        path = checkpoint_path(directory, task)
        if not path.exists():
            continue
        row = json.loads(path.read_text())
        expected = score(task, row["record"]["raw_response"], cfg)
        if row["run_id"] != metadata["run_id"] or any(
            row.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("Receiver checkpoint differs from frozen task/score")
        rows[task["condition_id"]] = row
    return rows


def write_reports(directory, cfg, plan, rows):
    result = analyze(cfg, plan, rows)
    write_json(directory / "metrics/receiver_analysis.json", result)
    (directory / "reports/receiver_summary.md").write_text(
        report(result, cfg, plan, directory.name)
    )
    return result


def execute(directory, limit=None, report_only=False):
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("Limit must be a positive number of new responses")
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        rows = load_rows(directory, cfg, plan, metadata)
        if report_only or len(rows) == len(plan["tasks"]):
            return write_reports(directory, cfg, plan, rows)
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        metadata["invocations"].append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "limit": limit,
                "git_revision": revision.stdout.strip()
                if revision.returncode == 0
                else None,
            }
        )
        write_json(directory / "metadata.json", metadata)
        client, calls = None, 0
        try:
            for task in plan["tasks"]:
                if task["condition_id"] in rows:
                    continue
                if limit is not None and calls >= limit:
                    break
                if client is None:
                    from colorref.llm_clients import build_client

                    client = build_client(cfg["model"])
                    model = getattr(client, "_model_and_tokenizer", (None, None))[0]
                    resolved = getattr(
                        getattr(model, "config", None), "_commit_hash", None
                    )
                    previous = metadata["required_model_revision"] or metadata.get(
                        "resolved_model_revision"
                    )
                    if previous is not None and resolved != previous:
                        raise ValueError(
                            "Model revision changed; resume with the original snapshot"
                        )
                    if resolved is not None:
                        metadata["resolved_model_revision"] = resolved
                        metadata["invocations"][-1]["resolved_model_revision"] = (
                            resolved
                        )
                        write_json(directory / "metadata.json", metadata)
                try:
                    response = client.generate(
                        task["prompt"],
                        max_tokens=cfg["model"]["max_tokens"],
                        temperature=cfg["model"]["temperature"],
                    )
                    if getattr(response, "error", None):
                        raise RuntimeError(str(response.error))
                    if not isinstance(response.text, str):
                        raise RuntimeError("Backend returned a non-string response")
                except Exception as error:
                    write_json(
                        directory / "raw_outputs/last_execution_error.json",
                        {
                            "condition_id": task["condition_id"],
                            "error": str(error),
                            "at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    raise RuntimeError(
                        "Backend error: unfinished receiver response remains pending for resume"
                    ) from error
                raw = getattr(response, "raw", None) or {}
                row = {
                    **score(task, response.text, cfg),
                    "run_id": metadata["run_id"],
                    "model_name": getattr(response, "model_name", None),
                    "provider": getattr(response, "provider", None),
                    "latency_s": getattr(response, "latency_s", None),
                    "generation": generation_diagnostics(response),
                    "prompt_tokens": raw.get(
                        "prompt_tokens", (raw.get("usage") or {}).get("prompt_tokens")
                    ),
                }
                write_json(checkpoint_path(directory, task), row)
                rows[task["condition_id"]] = row
                calls += 1
                if calls % 20 == 0:
                    logger.info(
                        "Saved %d new revisions (%d/%d total)",
                        calls,
                        len(rows),
                        len(plan["tasks"]),
                    )
        finally:
            write_reports(directory, cfg, plan, rows)
        return analyze(cfg, plan, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--parent-run", type=Path)
    source.add_argument("--resume", type=Path)
    source.add_argument("--report-only", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--experiment-name", default="teacher_receiver_a100_40gb")
    args = parser.parse_args()
    if (args.dry_run or args.output_root is not None) and args.parent_run is None:
        parser.error("--dry-run and --output-root require --parent-run")
    if args.limit is not None and (args.limit <= 0 or args.report_only is not None):
        parser.error("--limit must be positive and cannot accompany --report-only")
    if not args.experiment_name or not all(
        c.isalnum() or c in "_-" for c in args.experiment_name
    ):
        parser.error(
            "Experiment name must contain only letters, digits, underscores and hyphens"
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
                        "model": cfg["model"],
                        "examples": len({t["example_id"] for t in plan["tasks"]}),
                        "cases": len(plan["tasks"]) // len(ARMS),
                        "generations": len(plan["tasks"]),
                        "arms": list(ARMS),
                        "output_interface": "hex",
                        "revisions_per_case": 1,
                        "teacher_text_unchanged": True,
                        "semantic_label_selection": False,
                        "empty_teacher_messages": sum(
                            t["teacher_empty"] for t in plan["tasks"]
                        ),
                        "teacher_target_hex_mentions": sum(
                            t["teacher_mentions_target_hex"] for t in plan["tasks"]
                        ),
                    },
                    indent=2,
                )
            )
            return
        directory = create_run(cfg, plan, snapshot)
    else:
        directory = args.resume or args.report_only
    logger.info("Receiver run directory: %s", directory)
    result = execute(directory, args.limit, args.report_only is not None)
    logger.info(
        "Completed %d/%d; report: %s",
        result["completed"],
        result["planned"],
        directory / "reports/receiver_summary.md",
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    main()
