"""Run one-shot ICL baseline (no feedback, with k in-context examples).

Extends run_oneshot.py to inject ICL examples into the initial prompt.

Usage:
    uv run python scripts/run_icl_oneshot.py \\
        --configs configs/experiments/icl_oneshot_*.yaml

    # Or run single condition directly:
    uv run python scripts/run_icl_oneshot.py \\
        --subset data/eval_subsets/main_1000.parquet \\
        --contexts data/icl_contexts/main_1000_random_k4.parquet \\
        --model Qwen/Qwen3-14B \\
        --k 4 --mode random
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

from colorref.icl import render_icl_examples, render_icl_initial_prompt
from colorref.llm_clients import build_client
from colorref.parsing import extract_hex
from colorref.colors import hex_to_rgb, rgb_to_lab, color_distance_lab
from colorref.prompts import load_template

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
        description="Run one-shot ICL baseline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--configs", nargs="+", default=None,
                   help="YAML experiment configs")
    p.add_argument("--subset", default="data/eval_subsets/main_1000.parquet")
    p.add_argument("--contexts", default=None,
                   help="Prebuilt contexts parquet (data/icl_contexts/*.parquet)")
    p.add_argument("--model", default="Qwen/Qwen3-14B")
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--ks", type=int, nargs="+", default=None,
                   help="Run multiple k values in one process (model loaded once)")
    p.add_argument("--mode", default="random",
                   choices=["random", "regime_matched", "text_similar"])
    p.add_argument("--modes", nargs="+", default=None,
                   choices=["random", "regime_matched", "text_similar"],
                   help="Run multiple modes in one process (model loaded once)")
    p.add_argument("--runs_root", default="runs")
    p.add_argument("--configs_dir", default="configs/experiments")
    p.add_argument("--dry_run", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Run one ICL oneshot condition
# ---------------------------------------------------------------------------

def run_icl_oneshot(
    subset: pd.DataFrame,
    contexts_df: pd.DataFrame,
    client,
    model_alias: str,
    k: int,
    mode: str,
    exp_name: str,
    runs_root: Path,
    template_path: str = "configs/prompts/oneshot_hex_icl.txt",
    max_tokens: int = 64,
    temperature: float = 0.0,
) -> Path:
    template = load_template(template_path)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"{ts}_{exp_name}_{model_alias}_icl_oneshot_{mode}_k{k}_main_1000"
    run_dir = runs_root / run_id
    (run_dir / "games").mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics").mkdir(exist_ok=True)
    (run_dir / "reports").mkdir(exist_ok=True)

    # Build context lookup
    ctx_by_id = {}
    for _, row in contexts_df.iterrows():
        eid = int(row["example_id"])
        ctx_by_id[eid] = row

    records = []
    for _, row in subset.iterrows():
        eid = int(row["example_id"])
        raw_name = str(row["raw_name"])
        true_hex = str(row["hex"])
        true_lab = (float(row["lab_l"]), float(row["lab_a"]), float(row["lab_b"]))

        # Get ICL examples for this example
        ctx_row = ctx_by_id.get(eid)
        icl_text = ""
        if ctx_row is not None:
            try:
                ctx_list = json.loads(str(ctx_row.get("contexts_json", "[]")))
                icl_text = render_icl_examples(ctx_list, k=k)
            except Exception:
                pass

        prompt = render_icl_initial_prompt(template, raw_name=raw_name, icl_examples_text=icl_text)

        if not icl_text:
            # Fall back to zero-shot if no context available
            from colorref.prompts import render_oneshot
            zs_template = load_template("configs/prompts/feedback_initial.txt")
            prompt = render_oneshot(zs_template, raw_name=raw_name)

        resp = client.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        guess_hex, _ = extract_hex(resp.text)
        error = None
        guess_lab = None
        if guess_hex:
            try:
                rgb = hex_to_rgb(guess_hex)
                guess_lab = rgb_to_lab(*rgb)
                error = color_distance_lab(true_lab, guess_lab)
            except Exception:
                pass

        # Context diagnostics from stored row
        ctx_diag = {}
        if ctx_row is not None:
            for diag_col in ["context_mean_lab_distance_to_target", "context_min_lab_distance_to_target",
                             "context_same_regime_rate", "context_same_hue_bin_rate"]:
                ctx_diag[diag_col] = ctx_row.get(diag_col)

        records.append({
            "run_id": run_id,
            "example_id": eid,
            "raw_name": raw_name,
            "true_hex": true_hex,
            "guess_hex": guess_hex or "",
            "error_lab": error,
            "parse_ok": guess_hex is not None,
            "k_shot": k,
            "retrieval_mode": mode,
            "model_alias": model_alias,
            "regime_label": row.get("regime_label", ""),
            **ctx_diag,
        })

    df = pd.DataFrame(records)
    df.to_parquet(run_dir / "games" / "icl_oneshot_predictions.parquet", index=False)

    # Aggregate summary
    summary = {
        "run_id": run_id,
        "k_shot": k,
        "retrieval_mode": mode,
        "n": len(df),
        "mean_error": float(df["error_lab"].mean()) if df["error_lab"].notna().any() else float("nan"),
        "parse_rate": float(df["parse_ok"].mean()),
    }
    pd.DataFrame([summary]).to_csv(run_dir / "metrics" / "icl_summary.csv", index=False)
    logger.info("Run %s: mean ΔE=%.2f", run_id, summary["mean_error"])
    return run_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root)

    if args.configs:
        import glob as _glob
        config_paths = []
        for pat in args.configs:
            for m in _glob.glob(pat):
                config_paths.append(Path(m))
    else:
        config_paths = []

    if config_paths:
        for cp in config_paths:
            with open(cp) as f:
                cfg = yaml.safe_load(f)
            logger.info("Running config: %s", cp.name)
            icl_cfg = cfg.get("icl", {})
            k = int(icl_cfg.get("k_shot", args.k))
            mode = str(icl_cfg.get("retrieval_mode", args.mode))
            contexts_path = Path(icl_cfg.get("contexts_path",
                f"data/icl_contexts/{Path(cfg['input']['subset_path']).stem}_{mode}_k{k}.parquet"))

            subset = pd.read_parquet(cfg["input"]["subset_path"])
            contexts_df = pd.read_parquet(contexts_path) if contexts_path.exists() else pd.DataFrame()
            client = build_client(cfg["model"])

            if args.dry_run:
                logger.info("[DRY RUN] %s  k=%d  mode=%s", cp.name, k, mode)
                continue

            run_icl_oneshot(
                subset, contexts_df, client,
                model_alias=cfg["model"]["alias"],
                k=k, mode=mode,
                exp_name=cfg["experiment_name"],
                runs_root=runs_root,
                template_path=icl_cfg.get("template_path", "configs/prompts/oneshot_hex_icl.txt"),
                max_tokens=cfg["model"].get("max_tokens", 64),
                temperature=cfg["model"].get("temperature", 0.0),
            )
    else:
        # Direct mode from CLI args — supports multi-mode/multi-k sweeps with one model load
        modes_to_run = args.modes if args.modes else [args.mode]
        ks_to_run = args.ks if args.ks else [args.k]
        conditions = [(m, k) for m in modes_to_run for k in ks_to_run]

        if args.dry_run:
            for m, k in conditions:
                logger.info("[DRY RUN] mode=%s k=%d", m, k)
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
                logger.warning("No contexts file found at %s — running zero-shot fallback", contexts_path)
            logger.info("Running condition: mode=%s k=%d", mode, k)
            run_icl_oneshot(
                subset, contexts_df, client,
                model_alias="qwen3_14b",
                k=k, mode=mode,
                exp_name=f"icl_oneshot_{mode}_k{k}",
                runs_root=runs_root,
            )


if __name__ == "__main__":
    main()
