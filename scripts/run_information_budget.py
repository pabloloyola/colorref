"""Run information-budget ablation experiments.

Runs feedback games with BudgetedTeacher for multiple budget conditions.
Reuses run_feedback_game.py infrastructure but wraps the teacher with
the budget-aware wrapper.

Usage:
    uv run python scripts/run_information_budget.py \\
        --subset data/eval_subsets/main_1000.parquet \\
        --model Qwen/Qwen3-14B \\
        --conditions one_turn_c3 three_turn_c1 three_turn_c3 one_turn_c1 one_turn_c2 two_turn_c1 two_turn_c2

    # Run from pre-built YAML configs:
    uv run python scripts/run_information_budget.py \\
        --configs configs/experiments/budget_axis_*.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.budget import BUDGET_CONDITIONS, BudgetedTeacher, _count_issued_constraints
from colorref.games import run_game_for_example
from colorref.llm_clients import build_client
from colorref.prompts import load_template
from colorref.teachers import build_teacher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run information-budget ablation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--configs", nargs="+", default=None,
                   help="Explicit YAML config paths to run")
    p.add_argument("--conditions", nargs="+", default=None,
                   help=f"Budget condition names. Choices: {list(BUDGET_CONDITIONS)}")
    p.add_argument("--subset", default="data/eval_subsets/main_1000.parquet")
    p.add_argument("--model", default="Qwen/Qwen3-14B")
    p.add_argument("--runs_root", default="runs")
    p.add_argument("--configs_dir", default="configs/experiments")
    p.add_argument("--dry_run", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_id(exp_name: str, model_alias: str, teacher_type: str, subset_stem: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{exp_name}_{model_alias}_{teacher_type}_{subset_stem}"


def _setup_run_dir(run_root: Path, run_id: str) -> dict[str, Path]:
    base = run_root / run_id
    dirs = {
        "base": base,
        "raw_outputs": base / "raw_outputs",
        "games": base / "games",
        "metrics": base / "metrics",
        "reports": base / "reports",
        "inputs": base / "inputs",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def _load_completed_ids(jsonl_path: Path) -> set[int]:
    if not jsonl_path.exists():
        return set()
    done: set[int] = set()
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("turn") == 0:
                    done.add(int(rec["example_id"]))
            except Exception:
                pass
    return done


def _resolve_configs(args: argparse.Namespace) -> list[Path]:
    import glob
    if args.configs:
        paths = []
        for pat in args.configs:
            matches = sorted(glob.glob(pat))
            if matches:
                paths.extend(Path(m) for m in matches)
            else:
                p = Path(pat)
                if p.exists():
                    paths.append(p)
        return paths

    if args.conditions:
        configs_dir = Path(args.configs_dir)
        paths = []
        for cond in args.conditions:
            if cond not in BUDGET_CONDITIONS:
                logger.warning("Unknown condition: %s", cond)
                continue
            info = BUDGET_CONDITIONS[cond]
            r, c, b = info["rounds"], info["max_c_per_turn"], info["total_budget"]
            fname = f"budget_axis_rounds{r}_c{c}_budget{b}_main_qwen3_14b.yaml"
            cp = configs_dir / fname
            if not cp.exists():
                logger.warning("Config not found: %s", cp)
                continue
            paths.append(cp)
        return paths

    logger.error("Provide --configs or --conditions")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Run one budget condition config
# ---------------------------------------------------------------------------

def run_budget_config(cfg: dict, config_path: Path, runs_root: Path) -> Path | None:
    """Run one budget condition. Returns the run directory."""
    exp_name = cfg["experiment_name"]
    model_cfg = cfg["model"]
    teacher_cfg = cfg["teacher"]
    execution = cfg["execution"]
    prompt_cfg = cfg["prompt"]
    subset_path = Path(cfg["input"]["subset_path"])

    model_alias = model_cfg["alias"]
    teacher_type = teacher_cfg["type"]
    subset_stem = subset_path.stem

    budget = teacher_cfg.get("total_constraint_budget", None)
    budget_condition = teacher_cfg.get("budget_condition", "unknown")
    max_c_per_turn = teacher_cfg.get("max_feedback_constraints", 3)
    max_turns = execution["max_turns"]
    stop_when_exhausted = teacher_cfg.get("stop_when_budget_exhausted", True)

    run_id = _make_run_id(exp_name, model_alias, teacher_type, subset_stem)
    dirs = _setup_run_dir(runs_root, run_id)
    logger.info("Run ID: %s", run_id)

    # Save config
    import shutil
    shutil.copy(config_path, dirs["base"] / "config.yaml")

    # Load subset
    subset = pd.read_parquet(subset_path)
    limit = execution.get("limit")
    if limit:
        subset = subset.head(int(limit))
    logger.info("Loaded %d examples", len(subset))

    # Build model
    logger.info("Building LLM client...")
    client = build_client(model_cfg)

    # Build budgeted teacher
    base_teacher = build_teacher({
        "type": teacher_type,
        "max_feedback_constraints": max_c_per_turn,
        "min_delta": teacher_cfg.get("min_delta"),
    })
    teacher = BudgetedTeacher(base_teacher, total_constraint_budget=budget,
                              max_constraints_per_turn=max_c_per_turn)

    # Load templates
    initial_template = load_template(prompt_cfg["initial_template_path"])
    revision_template = load_template(prompt_cfg["revision_template_path"])

    # Resume
    jsonl_path = dirs["raw_outputs"] / "responses.jsonl"
    completed = _load_completed_ids(jsonl_path) if execution.get("resume") else set()
    logger.info("Already completed: %d", len(completed))

    all_turns: list[dict] = []
    all_feedback: list[dict] = []
    all_summaries: list[dict] = []
    budget_metrics: list[dict] = []

    n_total = len(subset)
    n_done = 0
    log_every = 10

    for _, row in subset.iterrows():
        example = row.to_dict()
        eid = int(example["example_id"])

        if eid in completed:
            n_done += 1
            continue

        # Reset budget for this example
        teacher.reset(eid)

        result = run_game_for_example(
            example=example,
            run_id=run_id,
            initial_template=initial_template,
            revision_template=revision_template,
            guesser=client,
            teacher=teacher,
            model_alias=model_alias,
            teacher_type=f"budgeted_{teacher_type}_{budget_condition}",
            prompt_version=prompt_cfg["initial_template_path"],
            max_turns=max_turns,
            convergence_delta_e=execution.get("convergence_delta_e", 5.0),
            max_tokens=model_cfg.get("max_tokens", 64),
            temperature=model_cfg.get("temperature", 0.0),
            stop_on_parse_failure=execution.get("stop_on_parse_failure", False),
            accumulate_feedback=bool(execution.get("accumulate_feedback", False)),
        )

        # Append records
        all_turns.extend(result.turn_records)
        all_feedback.extend(result.feedback_records)
        all_summaries.append(result.summary)

        # Compute budget-specific metrics
        total_issued = teacher._constraints_used(eid)
        rounds_issued = len([f for f in result.feedback_records
                             if f.get("run_id") == run_id or True])
        init_e = result.summary.get("initial_error_lab")
        final_e = result.summary.get("final_error_lab")
        imp_per_c = (
            (init_e - final_e) / total_issued
            if total_issued > 0 and init_e and final_e else None
        )
        imp_per_round = (
            (init_e - final_e) / max(rounds_issued, 1)
            if init_e and final_e else None
        )
        budget_metrics.append({
            "example_id": eid,
            "run_id": run_id,
            "budget_condition": budget_condition,
            "total_budget": budget,
            "max_turns": max_turns,
            "max_c_per_turn": max_c_per_turn,
            "total_constraints_issued": total_issued,
            "mean_constraints_per_round": total_issued / max(rounds_issued, 1),
            "constraints_remaining": max(0, (budget or 0) - total_issued),
            "budget_exhausted": total_issued >= (budget or float("inf")),
            "rounds_until_budget_exhausted": rounds_issued,
            "improvement_per_constraint": imp_per_c,
            "improvement_per_feedback_round": imp_per_round,
        })

        # Write to JSONL for resume support
        with jsonl_path.open("a") as f:
            for rec in result.turn_records:
                f.write(json.dumps(rec, default=str) + "\n")

        n_done += 1
        if n_done % log_every == 0:
            init_e = result.summary.get("initial_error_lab") or 0
            final_e = result.summary.get("final_error_lab") or 0
            ri = (init_e - final_e) / init_e if init_e > 0 else 0
            logger.info(
                "[%d/%d] id=%-8d  init_ΔE=%5.1f  final_ΔE=%5.1f  rel_imp=%+.2f  budget_used=%d",
                n_done, n_total, eid, init_e, final_e, ri, total_issued,
            )

    # Save all artifacts
    if all_turns:
        pd.DataFrame(all_turns).to_parquet(dirs["games"] / "trajectories.parquet", index=False)
    if all_feedback:
        pd.DataFrame(all_feedback).to_parquet(dirs["games"] / "feedback.parquet", index=False)
    if all_summaries:
        pd.DataFrame(all_summaries).to_parquet(dirs["games"] / "example_summaries.parquet", index=False)
    if budget_metrics:
        bm_df = pd.DataFrame(budget_metrics)
        bm_df.to_parquet(dirs["metrics"] / "budget_metrics.parquet", index=False)

    logger.info("Run complete: %s", run_id)
    return dirs["base"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    config_paths = _resolve_configs(args)

    if not config_paths:
        logger.error("No configs to run.")
        sys.exit(1)

    logger.info("Will run %d configs:", len(config_paths))
    for cp in config_paths:
        logger.info("  %s", cp.name)

    runs_root = Path(args.runs_root)

    for config_path in config_paths:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        logger.info("=" * 60)
        logger.info("Config: %s", config_path.name)

        if args.dry_run:
            logger.info("[DRY RUN] Would run: %s", cfg["experiment_name"])
            continue

        try:
            run_dir = run_budget_config(cfg, config_path, runs_root)
            logger.info("Completed: %s", run_dir)
        except Exception as exc:
            logger.exception("Failed config %s: %s", config_path.name, exc)


if __name__ == "__main__":
    main()
