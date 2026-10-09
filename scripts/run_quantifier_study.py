"""Run the matched 888-call study with one model load and durable checkpoints.

Examples:
    uv run python scripts/run_quantifier_study.py --config configs/experiments/quantifier_study_a100_40gb.yaml --dry-run
    uv run python scripts/run_quantifier_study.py --config configs/experiments/quantifier_study_a100_40gb.yaml
    uv run python scripts/run_quantifier_study.py --resume runs/YOUR_RUN
    uv run python scripts/run_quantifier_study.py --report-only runs/YOUR_RUN
"""

from __future__ import annotations

import argparse
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

from colorref.prompts import load_template  # noqa: E402
from colorref.quantifier_study import (  # noqa: E402
    build_conditions,
    plan_digest,
    score_prediction,
)
from colorref.quantifier_study_reports import write_study_reports  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run or reanalyze the matched quantifier study."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument(
        "--resume",
        type=Path,
        help="Use the saved plan and generate only unfinished conditions",
    )
    source.add_argument(
        "--report-only", type=Path, help="Reanalyze saved trials without model loading"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the plan without model loading or file creation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Generate at most N new responses this invocation; retain the full plan for resume",
    )
    args = parser.parse_args()
    if args.dry_run and args.config is None:
        parser.error("--dry-run requires --config")
    if args.report_only is not None and args.limit is not None:
        parser.error("--limit cannot be used with --report-only")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    return args


def _git_revision():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def create_run(
    cfg: dict, templates: dict, conditions: list[dict], config_path: Path
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{cfg['experiment_name']}"
    run_dir = Path(cfg.get("output", {}).get("run_root", "runs")) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ("inputs", "raw_outputs", "metrics", "reports"):
        (run_dir / name).mkdir()
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )
    _write_json(run_dir / "inputs" / "prompts.json", templates)
    _write_json(run_dir / "inputs" / "conditions.json", conditions)
    _write_json(
        run_dir / "metadata.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config_path": str(config_path),
            "model": cfg["model"],
            "interface": {
                "output_space": "lab",
                "evaluation_space": "lab",
                "projection": "clipped_srgb_from_lab",
            },
            "seed_for_condition_order": cfg.get("seed", 13),
            "planned_conditions": len(conditions),
            "planned_pairs": len(conditions) // 2,
            "plan_sha256": plan_digest(conditions),
            "config_sha256": plan_digest([cfg]),
            "invocations": [],
        },
    )
    return run_dir


def load_plan(run_dir: Path):
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    conditions = json.loads(
        (run_dir / "inputs" / "conditions.json").read_text(encoding="utf-8")
    )
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata["schema_version"] != 1 or metadata["plan_sha256"] != plan_digest(
        conditions
    ):
        raise ValueError("Saved condition plan failed integrity validation")
    if metadata["config_sha256"] != plan_digest([cfg]):
        raise ValueError("Saved configuration failed integrity validation")
    templates = json.loads(
        (run_dir / "inputs" / "prompts.json").read_text(encoding="utf-8")
    )
    if build_conditions(cfg, templates) != conditions:
        raise ValueError(
            "Saved configuration or prompt snapshot no longer matches the plan"
        )
    return cfg, conditions, metadata


def read_trial_records(
    path: Path,
    conditions: list[dict],
    *,
    repair_trailing: bool = False,
    expected_run_id: str | None = None,
) -> list[dict]:
    """Reject duplicate/foreign trials; optionally repair only an interrupted final line."""
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    rows = []
    offset = 0
    known = {item["condition_id"]: item for item in conditions}
    seen = set()
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            interrupted_tail = index == len(lines) - 1 and not line.endswith(b"\n")
            if repair_trailing and interrupted_tail:
                with path.open("r+b") as stream:
                    stream.truncate(offset)
                    stream.flush()
                    os.fsync(stream.fileno())
                logger.warning(
                    "Removed interrupted trailing record; completed trials retained"
                )
                break
            raise ValueError(
                "Invalid saved response record; only an unterminated final line may be repaired"
            ) from None
        condition_id = row.get("condition_id")
        if condition_id not in known or condition_id in seen:
            raise ValueError(f"Unknown or duplicate saved condition: {condition_id}")
        if any(row.get(key) != value for key, value in known[condition_id].items()):
            raise ValueError(
                f"Saved trial does not match its frozen condition: {condition_id}"
            )
        if not isinstance(row.get("parse_ok"), bool):
            raise TypeError(f"Missing parse status: {condition_id}")
        if expected_run_id is not None and row.get("run_id") != expected_run_id:
            raise ValueError("Saved trial belongs to a different run")
        seen.add(condition_id)
        rows.append(row)
        offset += len(line)
    if (
        repair_trailing
        and rows
        and path.stat().st_size
        and not path.read_bytes().endswith(b"\n")
    ):
        with path.open("ab") as stream:
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    return rows


def pending_conditions(conditions, completed, limit=None):
    seen = {row["condition_id"] for row in completed}
    pending = [
        condition for condition in conditions if condition["condition_id"] not in seen
    ]
    return pending if limit is None else pending[:limit]


def run_pending(client, parser, cfg, pending, run_dir, run_id, completed):
    """Checkpoint every completed response, including genuine parse failures."""
    path = run_dir / "raw_outputs" / "responses.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        for index, condition in enumerate(pending, start=1):
            response = client.generate(
                condition["prompt"],
                max_tokens=cfg["model"]["max_tokens"],
                temperature=cfg["model"]["temperature"],
            )
            error = getattr(response, "error", None)
            if error:
                with (run_dir / "raw_outputs" / "execution_errors.jsonl").open(
                    "a", encoding="utf-8"
                ) as errors:
                    errors.write(
                        json.dumps(
                            {
                                "condition_id": condition["condition_id"],
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "error": str(error),
                            }
                        )
                        + "\n"
                    )
                raise RuntimeError(
                    f"Model execution failed; condition remains pending for resume: {error}"
                )
            parsed = parser(response.text, output_space="lab")
            row = {
                **condition,
                "run_id": run_id,
                "model_name": response.model_name,
                "provider": response.provider,
                "latency_s": response.latency_s,
                "raw_response": response.text,
                "parse_ok": parsed["parse_ok"],
                "parse_reason": parsed["parse_reason"],
                "guess_hex": parsed["hex"],
            }
            if parsed["parse_ok"]:
                row.update(
                    score_prediction(
                        condition, tuple(float(value) for value in parsed["lab"])
                    )
                )
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            completed.append(row)
            if index % 20 == 0 or index == len(pending):
                logger.info(
                    "[%d/%d this invocation] total completed=%d",
                    index,
                    len(pending),
                    len(completed),
                )


def export_reports(rows, conditions, cfg, run_dir):
    write_study_reports(rows, conditions, cfg, run_dir)
    if rows:
        import pandas as pd

        pd.DataFrame(rows).to_parquet(
            run_dir / "metrics" / "study_trials.parquet", index=False
        )
    logger.info("Report: %s/reports/study_summary.md", run_dir)


def main():
    args = parse_args()
    if args.config is not None:
        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        templates = {}
        for variant in cfg["study"]["prompt_variants"]:
            path = Path(variant["template_path"])
            templates[variant["id"]] = load_template(
                path if path.is_absolute() else ROOT / path
            )
        conditions = build_conditions(cfg, templates)
        if args.dry_run:
            counts = {
                kind: sum(x["condition_kind"] == kind for x in conditions)
                for kind in ("wording", "numeric", "no_change")
            }
            print(
                json.dumps(
                    {
                        "conditions": len(conditions),
                        "matched_pairs": len(conditions) // 2,
                        "prompt_variants": list(templates),
                        "counts": counts,
                        "plan_sha256": plan_digest(conditions),
                    },
                    indent=2,
                )
            )
            return
        run_dir = create_run(cfg, templates, conditions, args.config)
        cfg, conditions, metadata = load_plan(run_dir)
    else:
        run_dir = args.resume if args.resume is not None else args.report_only
        cfg, conditions, metadata = load_plan(run_dir)
    logger.info("Run directory: %s", run_dir)
    rows = read_trial_records(
        run_dir / "raw_outputs" / "responses.jsonl",
        conditions,
        repair_trailing=args.resume is not None,
        expected_run_id=metadata["run_id"],
    )
    if args.report_only is not None:
        export_reports(rows, conditions, cfg, run_dir)
        return
    pending = pending_conditions(conditions, rows, args.limit)
    logger.info(
        "Planned=%d completed=%d pending this invocation=%d",
        len(conditions),
        len(rows),
        len(pending),
    )
    metadata["invocations"].append(
        {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "git_revision": _git_revision(),
            "completed_at_start": len(rows),
            "requested_new_responses": len(pending),
            "resumed": args.resume is not None,
        }
    )
    _write_json(run_dir / "metadata.json", metadata)
    try:
        if pending:
            # Model and parser imports are not needed for planning or reanalysis.
            from colorref.games import _parse_and_convert
            from colorref.llm_clients import build_client

            client = build_client(cfg["model"])
            run_pending(
                client,
                _parse_and_convert,
                cfg,
                pending,
                run_dir,
                metadata["run_id"],
                rows,
            )
    finally:
        export_reports(rows, conditions, cfg, run_dir)
    logger.info(
        "Completed %d/%d. Run directory: %s", len(rows), len(conditions), run_dir
    )


if __name__ == "__main__":
    main()
