"""One-shot color prediction experiment.

For each example in the subset, renders a prompt, calls the model,
parses the hex guess, computes LAB error, and saves all outputs.

Usage:
    uv run python scripts/run_oneshot.py --config configs/experiments/oneshot_debug.yaml
    uv run python scripts/run_oneshot.py --config configs/experiments/oneshot_debug.yaml --limit 20
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

from colorref.colors import hex_to_rgb, rgb_to_lab, rgb_to_hsv, color_distance_lab
from colorref.llm_clients import build_client, LLMResponse
from colorref.parsing import extract_hex
from colorref.prompts import load_template, render_oneshot

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
        description="Run one-shot color prediction experiment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", required=True, help="Path to experiment YAML config")
    p.add_argument("--limit", type=int, default=None, help="Process at most N examples (overrides config)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Run ID and directory setup
# ---------------------------------------------------------------------------

def make_run_id(cfg: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = cfg["experiment_name"]
    alias = cfg["model"]["alias"]
    subset = Path(cfg["input"]["subset_path"]).stem
    return f"{ts}_{name}_{alias}_{subset}"


def setup_run_dir(run_root: str, run_id: str) -> dict[str, Path]:
    base = Path(run_root) / run_id
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


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

def load_completed_ids(jsonl_path: Path) -> set[int]:
    """Return set of example_ids already in the JSONL file."""
    if not jsonl_path.exists():
        return set()
    done: set[int] = set()
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
                done.add(int(rec["example_id"]))
            except Exception:
                pass
    return done


# ---------------------------------------------------------------------------
# Per-example processing
# ---------------------------------------------------------------------------

def process_example(
    row: pd.Series,
    template: str,
    client,
    cfg: dict,
    run_id: str,
) -> tuple[dict, dict]:
    """Return (raw_record, result_record) for one example."""
    example_id = int(row["example_id"])
    raw_name = str(row["raw_name"])

    prompt = render_oneshot(template, raw_name=raw_name)

    resp: LLMResponse = client.generate(
        prompt,
        max_tokens=cfg["model"]["max_tokens"],
        temperature=cfg["model"]["temperature"],
    )

    # --- parse ---
    guess_hex, parse_meta = extract_hex(resp.text)

    # --- convert guess to color spaces ---
    guess_lab = (None, None, None)
    guess_hsv = (None, None, None)
    guess_rgb = (None, None, None)
    if guess_hex:
        try:
            guess_rgb = hex_to_rgb(guess_hex)
            guess_lab = rgb_to_lab(*guess_rgb)
            guess_hsv = rgb_to_hsv(*guess_rgb)
        except Exception:
            guess_hex = None
            parse_meta["parse_ok"] = False
            parse_meta["reason"] = "conversion_failed"

    # --- error ---
    true_lab = (float(row["lab_l"]), float(row["lab_a"]), float(row["lab_b"]))
    error_lab = None
    if guess_hex and all(v is not None for v in guess_lab):
        error_lab = color_distance_lab(true_lab, guess_lab)

    # --- raw record (JSONL) ---
    raw_record = {
        "example_id": example_id,
        "turn": 0,
        "phase": "oneshot",
        "prompt": prompt,
        "raw_response": resp.text,
        "model_alias": cfg["model"]["alias"],
        "model_name": cfg["model"]["model_name"],
        "provider": cfg["model"]["provider"],
        "latency_s": resp.latency_s,
        "error": resp.error,
    }

    # --- result record (parquet row) ---
    result = {
        "run_id": run_id,
        "example_id": example_id,
        "raw_name": raw_name,
        "hex": str(row["hex"]),
        "true_lab_l": true_lab[0],
        "true_lab_a": true_lab[1],
        "true_lab_b": true_lab[2],
        "model_alias": cfg["model"]["alias"],
        "prompt_version": cfg["prompt"]["template_path"],
        "raw_response": resp.text,
        "guess_hex": guess_hex,
        "parse_ok": parse_meta["parse_ok"],
        "parse_reason": parse_meta.get("reason"),
        "guess_rgb_r": guess_rgb[0],
        "guess_rgb_g": guess_rgb[1],
        "guess_rgb_b": guess_rgb[2],
        "guess_lab_l": guess_lab[0],
        "guess_lab_a": guess_lab[1],
        "guess_lab_b": guess_lab[2],
        "guess_hsv_h": guess_hsv[0],
        "guess_hsv_s": guess_hsv[1],
        "guess_hsv_v": guess_hsv[2],
        "error_lab": error_lab,
        "regime_label": str(row.get("regime_label", "")),
        "abstraction_score": float(row["abstraction_score"]) if pd.notna(row.get("abstraction_score")) else None,
        "explicitness_score": float(row["explicitness_score"]) if pd.notna(row.get("explicitness_score")) else None,
        "prototype_score": float(row["prototype_score"]) if pd.notna(row.get("prototype_score")) else None,
        "rarity_score": float(row["rarity_score"]) if pd.notna(row.get("rarity_score")) else None,
        "hue_bin": str(row.get("hue_bin", "")),
        "lightness_bin": str(row.get("lightness_bin", "")),
        "saturation_bin": str(row.get("saturation_bin", "")),
        "value_bin": str(row.get("value_bin", "")),
    }

    return raw_record, result


def _write_prompt_audit(df: pd.DataFrame, template: str, reports_dir: Path, n: int = 20) -> None:
    """Save up to n rendered prompts for manual inspection (spec §23.2)."""
    lines = ["# Prompt audit (first 20 examples)\n"]
    for i, (_, row) in enumerate(df.head(n).iterrows()):
        raw_name = str(row["raw_name"])
        lines.append(f"## Example {i+1}: example_id={row['example_id']}")
        lines.append(f"**raw_name:** {raw_name}\n```")
        lines.append(render_oneshot(template, raw_name=raw_name))
        lines.append("```\n")
    (reports_dir / "prompt_audit.txt").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Prompt audit written to %s/prompt_audit.txt", reports_dir)


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def write_summary(
    results: list[dict],
    cfg: dict,
    run_id: str,
    reports_dir: Path,
) -> None:
    df = pd.DataFrame(results)
    n = len(df)
    n_ok = df["parse_ok"].sum()
    errors = df["error_lab"].dropna()

    lines = [
        f"# Run summary: {run_id}",
        "",
        "## Metadata",
        f"- Experiment: `{cfg['experiment_name']}`",
        f"- Model: `{cfg['model']['alias']}` (`{cfg['model']['model_name']}`)",
        f"- Subset: `{cfg['input']['subset_path']}`",
        f"- Total examples: {n}",
        "",
        "## Parse success",
        f"- Parsed OK: {n_ok} / {n} ({100 * n_ok / max(n, 1):.1f}%)",
        "",
        "## LAB error (parsed examples only)",
        f"- Mean ΔE: {errors.mean():.2f}" if len(errors) else "- No valid guesses",
        f"- Median ΔE: {errors.median():.2f}" if len(errors) else "",
        f"- Min ΔE: {errors.min():.2f}" if len(errors) else "",
        f"- Max ΔE: {errors.max():.2f}" if len(errors) else "",
        "",
    ]

    if "regime_label" in df.columns:
        lines += ["## Error by regime", ""]
        lines += ["| Regime | N | Mean ΔE | Median ΔE | Parse rate |"]
        lines += ["|---|---:|---:|---:|---:|"]
        for regime, grp in df.groupby("regime_label"):
            grp_errors = grp["error_lab"].dropna()
            parse_rate = grp["parse_ok"].mean() * 100
            lines.append(
                f"| {regime} | {len(grp)} | "
                f"{grp_errors.mean():.2f} | {grp_errors.median():.2f} | {parse_rate:.1f}% |"
            )
        lines.append("")

    (reports_dir / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Summary written to %s/run_summary.md", reports_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text())

    # CLI override
    if args.limit is not None:
        cfg["execution"]["limit"] = args.limit

    # --- run directory ---
    run_id = make_run_id(cfg)
    run_root = cfg.get("output", {}).get("run_root", "runs")
    dirs = setup_run_dir(run_root, run_id)
    logger.info("Run ID: %s", run_id)

    # --- save config and metadata ---
    (dirs["base"] / "config.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    metadata = {
        "run_id": run_id,
        "experiment_name": cfg["experiment_name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(cfg_path),
        "seed": cfg.get("seed", 13),
        "model": cfg["model"],
    }
    (dirs["base"] / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    # --- load subset ---
    subset_path = cfg["input"]["subset_path"]
    df = pd.read_parquet(subset_path)
    logger.info("Loaded subset: %d rows from %s", len(df), subset_path)

    # --- copy subset to inputs/ ---
    subset_dest = dirs["inputs"] / "subset.parquet"
    df.to_parquet(subset_dest, index=False)

    # --- resume support ---
    jsonl_path = dirs["raw_outputs"] / "responses.jsonl"
    completed_ids = set()
    if cfg["execution"].get("resume", True):
        completed_ids = load_completed_ids(jsonl_path)
        if completed_ids:
            logger.info("Resuming: %d examples already done", len(completed_ids))

    # --- apply limit ---
    limit = cfg["execution"].get("limit")
    rows = [row for _, row in df.iterrows() if int(row["example_id"]) not in completed_ids]
    if limit:
        rows = rows[:limit]
    logger.info("Examples to process: %d", len(rows))

    # --- load template ---
    template = load_template(cfg["prompt"]["template_path"])

    # --- prompt audit ---
    _write_prompt_audit(df, template, dirs["reports"])

    # --- build client ---
    logger.info("Building LLM client…")
    client = build_client(cfg["model"])

    # --- process ---
    results: list[dict] = []
    sleep_s = cfg["execution"].get("sleep_s", 0.0)

    with jsonl_path.open("a") as jsonl_file:
        for i, row in enumerate(rows):
            example_id = int(row["example_id"])
            raw_record, result = process_example(row, template, client, cfg, run_id)

            # write JSONL immediately (crash-safe)
            jsonl_file.write(json.dumps(raw_record) + "\n")
            jsonl_file.flush()

            results.append(result)

            if (i + 1) % 20 == 0 or (i + 1) == len(rows):
                n_ok = sum(1 for r in results if r["parse_ok"])
                errors = [r["error_lab"] for r in results if r["error_lab"] is not None]
                mean_err = sum(errors) / len(errors) if errors else float("nan")
                logger.info(
                    "[%d/%d] id=%d parse_ok=%s ΔE=%.1f  (running mean ΔE=%.2f, parse=%.0f%%)",
                    i + 1, len(rows), example_id,
                    result["parse_ok"],
                    result["error_lab"] if result["error_lab"] is not None else float("nan"),
                    mean_err,
                    100 * n_ok / (i + 1),
                )

            if sleep_s > 0:
                time.sleep(sleep_s)

    # --- save prediction table ---
    pred_df = pd.DataFrame(results)
    pred_path = dirs["games"] / "oneshot_predictions.parquet"
    pred_df.to_parquet(pred_path, index=False)
    logger.info("Predictions saved to %s", pred_path)

    # --- save per-example metrics ---
    metrics_df = pred_df[["run_id", "example_id", "raw_name", "hex", "model_alias",
                           "parse_ok", "error_lab", "regime_label",
                           "abstraction_score", "hue_bin", "lightness_bin",
                           "saturation_bin", "value_bin"]].copy()
    metrics_path = dirs["metrics"] / "per_example.parquet"
    metrics_df.to_parquet(metrics_path, index=False)

    # --- write summary ---
    write_summary(results, cfg, run_id, dirs["reports"])

    logger.info("Done. Run directory: %s", dirs["base"])


if __name__ == "__main__":
    main()
