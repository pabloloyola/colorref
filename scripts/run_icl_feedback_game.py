"""Run ICL-augmented feedback game (initial prompt has k in-context examples).

Wraps run_feedback_game.py infrastructure, injecting ICL context into
the initial guess prompt only (initial_only_icl = True by spec default).

Usage:
    uv run python scripts/run_icl_feedback_game.py \\
        --subset data/eval_subsets/main_1000.parquet \\
        --contexts data/icl_contexts/main_1000_random_k4.parquet \\
        --teacher axis_oracle \\
        --max_constraints 3 \\
        --k 4 --mode random

    # Or from YAML (set ``execution.accumulate_feedback: true`` to show all prior
    # teacher utterances in each revision prompt):
    uv run python scripts/run_icl_feedback_game.py \\
        --configs configs/experiments/icl_feedback_axis_c3_*.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.colors import color_distance_lab, hex_to_rgb, rgb_to_lab
from colorref.games import GameResult, _example_summary, _feedback_record, _parse_and_convert, _turn_record, format_revision_feedback_text
from colorref.icl import render_icl_examples, render_icl_initial_prompt
from colorref.llm_clients import build_client
from colorref.metrics import is_converged
from colorref.parsing import extract_hex
from colorref.prompts import load_template, render_oneshot, render_revision
from colorref.teachers import build_teacher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ICL-augmented game runner
# ---------------------------------------------------------------------------

def run_icl_game_for_example(
    example: dict,
    run_id: str,
    initial_template_icl: str,
    revision_template: str,
    icl_examples_text: str,
    guesser,
    teacher,
    model_alias: str,
    teacher_type: str,
    prompt_version: str,
    k_shot: int,
    retrieval_mode: str,
    max_turns: int = 3,
    convergence_delta_e: float = 5.0,
    max_tokens: int = 64,
    temperature: float = 0.0,
    stop_on_parse_failure: bool = False,
    accumulate_feedback: bool = False,
) -> GameResult:
    """Like run_game_for_example but injects ICL examples into turn 0."""
    from colorref.games import _color_dict_from_row

    result = GameResult()
    target = _color_dict_from_row(example)

    # Turn 0: ICL-augmented initial guess
    prompt0 = render_icl_initial_prompt(
        initial_template_icl,
        raw_name=example["raw_name"],
        icl_examples_text=icl_examples_text,
    )
    resp0 = guesser.generate(prompt0, max_tokens=max_tokens, temperature=temperature)
    guess = _parse_and_convert(resp0.text)
    error0 = (
        color_distance_lab(target["lab"], guess["lab"])
        if guess["parse_ok"] and guess["lab"] else None
    )

    result.turn_records.append(_turn_record(
        run_id, example, target, turn=0, phase="initial_guess",
        prompt=prompt0, raw_response=resp0.text, guess=guess,
        error_lab=error0, feedback_prev=None,
        model_alias=model_alias, teacher_type=teacher_type,
        prompt_version=prompt_version,
    ))

    if not guess["parse_ok"] or (error0 is not None and is_converged(error0, convergence_delta_e)):
        result.summary = _example_summary(
            run_id, example, target, result.turn_records, result.feedback_records,
            model_alias, teacher_type, max_turns, convergence_delta_e,
        )
        return result

    current_guess = guess
    feedback_text_history: list[str] = []
    for turn in range(max_turns):
        feedback = teacher.give_feedback(target, current_guess, example, turn)
        result.feedback_records.append(_feedback_record(run_id, example["example_id"], turn, feedback))
        feedback_text_history.append(feedback.text)
        feedback_for_prompt = format_revision_feedback_text(
            feedback_text_history, accumulate=accumulate_feedback
        )

        # Standard revision prompt (no ICL repetition by default)
        revision_prompt = render_revision(
            revision_template,
            raw_name=example["raw_name"],
            previous_guess_hex=current_guess["hex"] or "#000000",
            feedback=feedback_for_prompt,
        )
        resp = guesser.generate(revision_prompt, max_tokens=max_tokens, temperature=temperature)
        next_guess = _parse_and_convert(resp.text)
        next_error = (
            color_distance_lab(target["lab"], next_guess["lab"])
            if next_guess["parse_ok"] and next_guess["lab"] else None
        )

        result.turn_records.append(_turn_record(
            run_id, example, target, turn=turn + 1, phase="revision",
            prompt=revision_prompt, raw_response=resp.text, guess=next_guess,
            error_lab=next_error, feedback_prev=feedback,
            model_alias=model_alias, teacher_type=teacher_type,
            prompt_version=prompt_version,
        ))

        if not next_guess["parse_ok"]:
            if stop_on_parse_failure:
                break
            break

        current_guess = next_guess
        if next_error is not None and is_converged(next_error, convergence_delta_e):
            break

    result.summary = _example_summary(
        run_id, example, target, result.turn_records, result.feedback_records,
        model_alias, teacher_type, max_turns, convergence_delta_e,
    )
    return result


# ---------------------------------------------------------------------------
# Run one config
# ---------------------------------------------------------------------------

def run_icl_feedback_config(
    subset: pd.DataFrame,
    contexts_df: pd.DataFrame,
    client,
    teacher,
    model_alias: str,
    teacher_type: str,
    k: int,
    mode: str,
    exp_name: str,
    runs_root: Path,
    initial_template_path: str = "configs/prompts/feedback_initial_icl.txt",
    revision_template_path: str = "configs/prompts/feedback_revision.txt",
    max_turns: int = 3,
    convergence_delta_e: float = 5.0,
    max_tokens: int = 64,
    temperature: float = 0.0,
    accumulate_feedback: bool = False,
) -> Path:
    initial_template = load_template(initial_template_path)
    revision_template = load_template(revision_template_path)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"{ts}_{exp_name}_{model_alias}_{teacher_type}_icl_{mode}_k{k}_main_1000"
    run_dir = runs_root / run_id
    for sub in ["games", "metrics", "reports", "inputs"]:
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    ctx_by_id = {}
    for _, row in contexts_df.iterrows():
        eid = int(row["example_id"])
        ctx_by_id[eid] = row

    all_turns = []
    all_feedback = []
    all_summaries = []

    for _, row in subset.iterrows():
        example = row.to_dict()
        eid = int(example["example_id"])

        # Build ICL text
        ctx_row = ctx_by_id.get(eid)
        icl_text = ""
        if ctx_row is not None:
            try:
                ctx_list = json.loads(str(ctx_row.get("contexts_json", "[]")))
                icl_text = render_icl_examples(ctx_list, k=k)
            except Exception:
                pass

        result = run_icl_game_for_example(
            example=example,
            run_id=run_id,
            initial_template_icl=initial_template,
            revision_template=revision_template,
            icl_examples_text=icl_text,
            guesser=client,
            teacher=teacher,
            model_alias=model_alias,
            teacher_type=teacher_type,
            prompt_version=initial_template_path,
            k_shot=k,
            retrieval_mode=mode,
            max_turns=max_turns,
            convergence_delta_e=convergence_delta_e,
            max_tokens=max_tokens,
            temperature=temperature,
            accumulate_feedback=accumulate_feedback,
        )

        all_turns.extend(result.turn_records)
        all_feedback.extend(result.feedback_records)
        sm = dict(result.summary)
        sm["k_shot"] = k
        sm["retrieval_mode"] = mode
        if ctx_row is not None:
            for diag_col in ["context_mean_lab_distance_to_target", "context_same_regime_rate"]:
                sm[diag_col] = ctx_row.get(diag_col)
        all_summaries.append(sm)

    if all_turns:
        pd.DataFrame(all_turns).to_parquet(run_dir / "games" / "trajectories.parquet", index=False)
    if all_feedback:
        pd.DataFrame(all_feedback).to_parquet(run_dir / "games" / "feedback.parquet", index=False)
    if all_summaries:
        pd.DataFrame(all_summaries).to_parquet(run_dir / "games" / "example_summaries.parquet", index=False)

    logger.info("Run complete: %s", run_id)
    return run_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run ICL-augmented feedback game.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--configs", nargs="+", default=None)
    p.add_argument("--subset", default="data/eval_subsets/main_1000.parquet")
    p.add_argument("--contexts", default=None)
    p.add_argument("--teacher", default="axis_oracle")
    p.add_argument("--max_constraints", type=int, default=3)
    p.add_argument("--model", default="Qwen/Qwen3-14B")
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--ks", type=int, nargs="+", default=None,
                   help="Run multiple k values in one process (model loaded once)")
    p.add_argument("--mode", default="random")
    p.add_argument("--modes", nargs="+", default=None,
                   help="Run multiple modes in one process (model loaded once)")
    p.add_argument("--max_turns", type=int, default=3)
    p.add_argument(
        "--accumulate-feedback",
        action="store_true",
        help="Include all prior teacher utterances in each revision prompt "
        "(direct CLI mode). With --configs, use execution.accumulate_feedback in YAML.",
    )
    p.add_argument("--runs_root", default="runs")
    p.add_argument("--dry_run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root)

    if args.configs:
        import glob as _glob
        for pat in args.configs:
            for cp in sorted(_glob.glob(pat)):
                with open(cp) as f:
                    cfg = yaml.safe_load(f)
                icl_cfg = cfg.get("icl", {})
                k = int(icl_cfg.get("k_shot", args.k))
                mode = str(icl_cfg.get("retrieval_mode", args.mode))
                contexts_path = Path(icl_cfg.get(
                    "contexts_path",
                    f"data/icl_contexts/{Path(cfg['input']['subset_path']).stem}_{mode}_k{k}.parquet"
                ))
                subset = pd.read_parquet(cfg["input"]["subset_path"])
                contexts_df = pd.read_parquet(contexts_path) if contexts_path.exists() else pd.DataFrame()
                teacher = build_teacher({
                    "type": cfg["teacher"]["type"],
                    "max_feedback_constraints": cfg["teacher"].get("max_feedback_constraints", 3),
                })
                if args.dry_run:
                    logger.info("[DRY RUN] %s k=%d mode=%s", cp, k, mode)
                    continue
                client = build_client(cfg["model"])
                run_icl_feedback_config(
                    subset, contexts_df, client, teacher,
                    model_alias=cfg["model"]["alias"],
                    teacher_type=cfg["teacher"]["type"],
                    k=k, mode=mode,
                    exp_name=cfg["experiment_name"],
                    runs_root=runs_root,
                    initial_template_path=icl_cfg.get("initial_template_path", "configs/prompts/feedback_initial_icl.txt"),
                    revision_template_path=icl_cfg.get("revision_template_path", "configs/prompts/feedback_revision.txt"),
                    max_turns=cfg["execution"].get("max_turns", 3),
                    max_tokens=cfg["model"].get("max_tokens", 64),
                    temperature=cfg["model"].get("temperature", 0.0),
                    accumulate_feedback=bool(
                        cfg.get("execution", {}).get("accumulate_feedback", False)
                    ),
                )
        return

    # Direct CLI mode — supports multi-mode/multi-k sweeps with one model load
    modes_to_run = args.modes if args.modes else [args.mode]
    ks_to_run = args.ks if args.ks else [args.k]
    conditions = [(m, k) for m in modes_to_run for k in ks_to_run]

    teacher = build_teacher({
        "type": args.teacher,
        "max_feedback_constraints": args.max_constraints,
    })

    if args.dry_run:
        for m, k in conditions:
            logger.info("[DRY RUN] teacher=%s mode=%s k=%d", args.teacher, m, k)
        return

    subset = pd.read_parquet(args.subset)
    model_cfg = {
        "provider": "hf_transformers",
        "model_name": args.model,
        "alias": "qwen3_14b",
        "hf_home": "/rit-as-pvc/pablo/hf",
        "device_map": "auto",
        "torch_dtype": "bfloat16",
        "enable_thinking": False,
        "temperature": 0.0,
        "max_tokens": 64,
    }
    logger.info("Loading model once for %d conditions…", len(conditions))
    client = build_client(model_cfg)

    for mode, k in conditions:
        contexts_path = Path(args.contexts) if args.contexts else Path(
            f"data/icl_contexts/{Path(args.subset).stem}_{mode}_k{k}.parquet"
        )
        contexts_df = pd.read_parquet(contexts_path) if contexts_path.exists() else pd.DataFrame()
        if contexts_df.empty:
            logger.warning("No contexts file found at %s", contexts_path)
        logger.info("Running condition: teacher=%s mode=%s k=%d", args.teacher, mode, k)
        run_icl_feedback_config(
            subset, contexts_df, client, teacher,
            model_alias="qwen3_14b",
            teacher_type=args.teacher,
            k=k, mode=mode,
            exp_name=f"icl_feedback_{args.teacher}_k{k}_{mode}",
            runs_root=runs_root,
            max_turns=args.max_turns,
            accumulate_feedback=args.accumulate_feedback,
        )


if __name__ == "__main__":
    main()
