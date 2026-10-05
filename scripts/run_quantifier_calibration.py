"""Calibrate how a model operationalizes graded color instructions.

This experiment isolates quantifier semantics from color-name grounding. The
model receives a known CIELAB state and an instruction such as "a little more
blue", then returns the updated CIELAB state. We measure signed movement along
the requested axis, orthogonal drift, direction following, and monotonicity
across quantifier levels.

Usage:
    uv run python scripts/run_quantifier_calibration.py
        --config configs/experiments/quantifier_calibration_a100_40gb_pilot.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.prompts import load_template, render_quantifier_calibration
from colorref.quantifiers import (
    DIRECTION_SPECS,
    QUANTIFIER_SPECS,
    make_instruction,
    measure_update,
    pairwise_monotonicity,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate quantifier-to-LAB movement semantics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", help="YAML calibration config")
    source.add_argument("--report-only", type=Path, help="Reanalyze a saved run without loading the model")
    parser.add_argument("--limit", type=int, default=None, help="Run at most N conditions")
    return parser.parse_args()


def make_run_id(cfg: dict) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{cfg['experiment_name']}_{cfg['model']['alias']}"


def setup_run_dir(run_root: str, run_id: str) -> dict[str, Path]:
    base = Path(run_root) / run_id
    dirs = {
        "base": base,
        "raw_outputs": base / "raw_outputs",
        "metrics": base / "metrics",
        "reports": base / "reports",
        "inputs": base / "inputs",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def _format_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def write_summary(
    rows: list[dict],
    cfg: dict,
    run_id: str,
    reports_dir: Path,
) -> None:
    frame = pd.DataFrame(rows)
    parsed = frame[frame["parse_ok"].astype(bool)]
    monotonicity = pairwise_monotonicity(rows)

    lines = [
        f"# Quantifier calibration: {run_id}",
        "",
        "## Metadata",
        f"- Model: {cfg['model']['alias']} ({cfg['model']['model_name']} via {cfg['model']['provider']})",
        "- Output interface: lab",
        "- Evaluation space: lab",
        f"- Conditions: {len(frame)}",
        f"- Parsed: {len(parsed)} / {len(frame)} ({100 * len(parsed) / max(len(frame), 1):.1f}%)",
        "",
        "## Movement by quantifier",
        "",
        "| Quantifier | N | Mean signed step | Median signed step | Direction-follow rate | Off-axis drift |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    quantifier_names = cfg["calibration"]["quantifiers"]
    for name in quantifier_names:
        subset = parsed[parsed["quantifier"] == name]
        lines.append(
            f"| {name} | {len(subset)} "
            f"| {_format_number(subset['requested_signed_step'].mean() if len(subset) else None)} "
            f"| {_format_number(subset['requested_signed_step'].median() if len(subset) else None)} "
            f"| {_format_number(subset['direction_followed'].mean() if len(subset) else None)} "
            f"| {_format_number(subset['off_axis_drift'].mean() if len(subset) else None)} |"
        )

    lines += [
        "",
        "## Quantifier monotonicity",
        "",
        f"- Ordered pairs: {monotonicity['monotonicity_ordered_pairs']} / {monotonicity['monotonicity_comparisons']}",
        f"- Nondecreasing rate (includes ties): {_format_number(monotonicity['monotonicity_rate'])}",
        f"- Strictly increasing pairs: {monotonicity['monotonicity_strict_pairs']} / {monotonicity['monotonicity_comparisons']}",
        f"- Strictly increasing rate: {_format_number(monotonicity['strict_monotonicity_rate'])}",
        f"- Tied pairs: {monotonicity['monotonicity_tied_pairs']}",
        "",
        "Only a_little < somewhat < much enter the ordinal comparison.",
        "The unmodified baseline is a separate comparison condition with no rank.",
        "Nondecreasing pairs include equal movements; strict pairs require an increase.",
        "Neither score alone guarantees movement in the requested direction.",
        "",
    ]

    lines += [
        "## Steps by starting color and direction",
        "",
        "| Base | Direction | " + " | ".join(quantifier_names) + " |",
        "|---|---|" + "---:|" * len(quantifier_names),
    ]
    for (base_id, direction), subset in parsed.groupby(["base_id", "direction"], sort=False):
        steps = [
            _format_number(subset.loc[subset["quantifier"] == name, "requested_signed_step"].mean())
            for name in quantifier_names
        ]
        lines.append(f"| {base_id} | {direction} | " + " | ".join(steps) + " |")
    lines += [
        "",
        "Values are signed requested-axis steps; positive follows the instruction.",
        "",
        "## Movement by direction",
        "",
        "| Direction | Quantifier | N | Mean signed step | Zero-step N | Wrong-direction N | Mean off-axis drift |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for (direction, name), subset in parsed.groupby(["direction", "quantifier"], sort=False):
        steps = subset["requested_signed_step"]
        lines.append(
            f"| {direction} | {name} | {len(subset)} | {_format_number(steps.mean())}"
            f" | {int((steps == 0).sum())} | {int((steps < 0).sum())}"
            f" | {_format_number(subset['off_axis_drift'].mean())} |"
        )
    failed = parsed.loc[parsed["requested_signed_step"] <= 0]
    lines += [
        "",
        "## Nonpositive requested-axis updates",
        "",
        "| Base | Direction | Quantifier | Signed step | Off-axis drift | Raw response |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in failed.to_dict("records"):
        response = str(row.get("raw_response", "")).replace("|", r"\|").replace("\n", " ")
        lines.append(
            f"| {row['base_id']} | {row['direction']} | {row['quantifier']}"
            f" | {_format_number(row['requested_signed_step'])}"
            f" | {_format_number(row['off_axis_drift'])} | {response} |"
        )
    if failed.empty:
        lines.append("| None | | | | | |")
    lines += [
        "",
        "## LAB-to-sRGB projection diagnostic",
        "",
    ]
    projection = pd.to_numeric(parsed.get("lab_projection_delta_e", pd.Series(dtype=float)), errors="coerce").dropna()
    lines += [
        f"- Mean projection ΔE: {_format_number(projection.mean())}",
        f"- States with projection ΔE > 1: {int((projection > 1).sum())} / {len(projection)}",
        "",
    ]

    (reports_dir / "quantifier_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    logger.info("Summary written to %s/quantifier_summary.md", reports_dir)


def main() -> None:
    args = parse_args()
    if args.report_only is not None:
        if args.limit is not None:
            raise ValueError("--limit applies only to inference runs")
        run_dir = args.report_only
        cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
        with (run_dir / "raw_outputs" / "responses.jsonl").open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        if not rows:
            raise ValueError("Saved run has no trial responses")
        write_summary(rows, cfg, rows[0]["run_id"], run_dir / "reports")
        return

    # Import the inference stack only when generating new responses.
    from colorref.games import _parse_and_convert, format_lab_triplet
    from colorref.llm_clients import build_client
    from colorref.run_metadata import interface_identity, model_identity

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    calibration_cfg = cfg["calibration"]
    if args.limit is not None:
        calibration_cfg["limit"] = args.limit

    run_id = make_run_id(cfg)
    dirs = setup_run_dir(cfg.get("output", {}).get("run_root", "runs"), run_id)
    logger.info("Run ID: %s", run_id)

    model_meta = model_identity(cfg["model"])
    interface_meta = interface_identity(cfg)
    metadata = {
        "run_id": run_id,
        "experiment_name": cfg["experiment_name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(cfg_path),
        "seed": cfg.get("seed", 13),
        "model": cfg["model"],
        "guesser_identity": model_meta,
        "interface": interface_meta,
        "calibration": calibration_cfg,
    }
    (dirs["base"] / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8",
    )
    (dirs["base"] / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    template = load_template(cfg["prompt"]["template_path"])
    bases = calibration_cfg["base_colors"]
    directions = calibration_cfg["directions"]
    quantifiers = calibration_cfg["quantifiers"]
    for direction in directions:
        if direction not in DIRECTION_SPECS:
            raise ValueError(f"Unknown direction in config: {direction}")
    for quantifier in quantifiers:
        if quantifier not in QUANTIFIER_SPECS:
            raise ValueError(f"Unknown quantifier in config: {quantifier}")

    conditions = list(product(bases, directions, quantifiers))
    limit = calibration_cfg.get("limit")
    if limit is not None:
        conditions = conditions[: int(limit)]
    logger.info("Conditions to process: %d", len(conditions))

    audit_lines = ["# Quantifier calibration prompt audit", ""]
    for base, direction, quantifier in conditions[: min(12, len(conditions))]:
        base_lab = tuple(float(value) for value in base["lab"])
        instruction = make_instruction(quantifier, direction)
        audit_lines += [
            f"## {base['id']} / {direction} / {quantifier}",
            "PROMPT:",
            render_quantifier_calibration(
                template,
                base_lab=format_lab_triplet(base_lab),
                instruction=instruction,
            ),
            "",
        ]
    (dirs["reports"] / "prompt_audit.txt").write_text(
        "\n".join(audit_lines),
        encoding="utf-8",
    )

    logger.info("Building LLM client…")
    client = build_client(cfg["model"])
    rows: list[dict] = []
    jsonl_path = dirs["raw_outputs"] / "responses.jsonl"

    with jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        for index, (base, direction, quantifier) in enumerate(conditions, start=1):
            base_lab = tuple(float(value) for value in base["lab"])
            instruction = make_instruction(quantifier, direction)
            prompt = render_quantifier_calibration(
                template,
                base_lab=format_lab_triplet(base_lab),
                instruction=instruction,
            )
            response = client.generate(
                prompt,
                max_tokens=cfg["model"]["max_tokens"],
                temperature=cfg["model"]["temperature"],
            )
            parsed = _parse_and_convert(response.text, output_space="lab")
            row = {
                "run_id": run_id,
                "condition_index": index,
                "base_id": base["id"],
                "base_lab_l": base_lab[0],
                "base_lab_a": base_lab[1],
                "base_lab_b": base_lab[2],
                "direction": direction,
                "direction_phrase": DIRECTION_SPECS[direction].phrase,
                "quantifier": quantifier,
                "quantifier_rank": QUANTIFIER_SPECS[quantifier].rank,
                "instruction": instruction,
                "prompt": prompt,
                "raw_response": response.text,
                "model_alias": cfg["model"]["alias"],
                "model_name": response.model_name,
                "provider": response.provider,
                "latency_s": response.latency_s,
                "parse_ok": parsed["parse_ok"],
                "parse_reason": parsed["parse_reason"],
                "guess_hex": parsed["hex"],
                "guess_lab_l": parsed["lab"][0] if parsed["lab"] else None,
                "guess_lab_a": parsed["lab"][1] if parsed["lab"] else None,
                "guess_lab_b": parsed["lab"][2] if parsed["lab"] else None,
                "lab_projection_delta_e": parsed.get("lab_projection_delta_e"),
            }
            if parsed["parse_ok"]:
                predicted_lab = tuple(float(value) for value in parsed["lab"])
                row.update(measure_update(base_lab, predicted_lab, direction))
            else:
                row.update({
                    "update_l": None,
                    "update_a": None,
                    "update_b": None,
                    "requested_signed_step": None,
                    "requested_abs_step": None,
                    "off_axis_drift": None,
                    "movement_norm": None,
                    "direction_followed": None,
                })

            jsonl_file.write(json.dumps(row, default=str) + "\n")
            jsonl_file.flush()
            rows.append(row)

            if index % 10 == 0 or index == len(conditions):
                logger.info(
                    "[%d/%d] %s / %s / %s parse_ok=%s signed_step=%s",
                    index,
                    len(conditions),
                    base["id"],
                    direction,
                    quantifier,
                    parsed["parse_ok"],
                    _format_number(row["requested_signed_step"]),
                )

    pd.DataFrame(rows).to_parquet(
        dirs["metrics"] / "quantifier_trials.parquet",
        index=False,
    )
    write_summary(rows, cfg, run_id, dirs["reports"])
    logger.info("Done. Run directory: %s", dirs["base"])


if __name__ == "__main__":
    main()
