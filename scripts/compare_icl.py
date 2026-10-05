"""Aggregate and compare ICL calibration results.

Usage:
    uv run python scripts/compare_icl.py \\
        --run_dirs runs/*icl* \\
        --out_dir reports/comparisons/icl_calibration
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "figure.dpi": 150})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare ICL calibration runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run_dirs", nargs="+", required=True)
    p.add_argument("--out_dir", default="reports/comparisons/icl_calibration")
    p.add_argument("--figures_dir", default=None)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_run_dirs(patterns: list[str]) -> list[Path]:
    result = []
    for pat in patterns:
        for m in sorted(glob.glob(pat)):
            p = Path(m)
            if p.is_dir():
                games = p / "games"
                if (games / "icl_oneshot_predictions.parquet").exists() or \
                   (games / "trajectories.parquet").exists() or \
                   (games / "example_summaries.parquet").exists():
                    result.append(p)
    return sorted(set(result))


def _load_predictions(run_dir: Path) -> pd.DataFrame | None:
    # ICL one-shot
    os_path = run_dir / "games" / "icl_oneshot_predictions.parquet"
    if os_path.exists():
        return pd.read_parquet(os_path)
    # ICL feedback via example_summaries
    es_path = run_dir / "games" / "example_summaries.parquet"
    if es_path.exists():
        return pd.read_parquet(es_path)
    return None


def _load_run_meta(run_dir: Path) -> dict:
    import yaml
    meta = {"run_id": run_dir.name}
    cp = run_dir / "config.yaml"
    if cp.exists():
        with open(cp) as f:
            cfg = yaml.safe_load(f)
        icl_cfg = cfg.get("icl", {})
        meta.update({
            "experiment_type": "feedback" if "icl_feedback" in run_dir.name else "oneshot",
            "k_shot": icl_cfg.get("k_shot", 0),
            "retrieval_mode": icl_cfg.get("retrieval_mode", "unknown"),
        })
    else:
        # Infer from run_id
        name = run_dir.name
        if "k0" in name or "_k0_" in name:
            meta["k_shot"] = 0
        elif "_k4_" in name:
            meta["k_shot"] = 4
        elif "_k2_" in name:
            meta["k_shot"] = 2
        elif "_k8_" in name:
            meta["k_shot"] = 8
        for mode in ["random", "text_similar", "regime_matched"]:
            if mode in name:
                meta["retrieval_mode"] = mode
                break
        meta["experiment_type"] = "feedback" if "feedback" in name else "oneshot"
    return meta


def _save_fig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = Path(args.figures_dir) if args.figures_dir else out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = _expand_run_dirs(args.run_dirs)
    logger.info("Found %d ICL run dirs", len(run_dirs))

    if not run_dirs:
        logger.error("No valid ICL run dirs found.")
        sys.exit(1)

    all_preds: list[pd.DataFrame] = []

    for run_dir in run_dirs:
        meta = _load_run_meta(run_dir)
        preds = _load_predictions(run_dir)
        if preds is None:
            continue
        for k, v in meta.items():
            if k not in preds.columns:
                preds[k] = v
        all_preds.append(preds)

    if not all_preds:
        logger.error("No prediction data found.")
        sys.exit(1)

    combined = pd.concat(all_preds, ignore_index=True)
    combined.to_parquet(out_dir / "combined_per_example.parquet", index=False)

    # ----------------------------------------------------------------
    # Aggregates
    # ----------------------------------------------------------------
    error_col = "error_lab" if "error_lab" in combined.columns else "final_error_lab"
    init_col = "initial_error_lab" if "initial_error_lab" in combined.columns else None

    if "k_shot" in combined.columns and error_col in combined.columns:
        agg_k = combined.groupby("k_shot")[error_col].agg(["mean", "std", "count"]).reset_index()
        agg_k.columns = ["k_shot", "mean_error", "std_error", "n"]
        agg_k.to_csv(out_dir / "aggregate_by_k_shot.csv", index=False)

    if "retrieval_mode" in combined.columns and error_col in combined.columns:
        agg_mode = combined.groupby("retrieval_mode")[error_col].agg(["mean", "std", "count"]).reset_index()
        agg_mode.to_csv(out_dir / "aggregate_by_retrieval_mode.csv", index=False)

    if all(c in combined.columns for c in ["k_shot", "retrieval_mode"]):
        agg_cond = combined.groupby(["k_shot", "retrieval_mode", "experiment_type"])[error_col].agg(
            ["mean", "std", "count"]
        ).reset_index()
        agg_cond.to_csv(out_dir / "aggregate_by_condition.csv", index=False)

    if "regime_label" in combined.columns:
        agg_regime = combined.groupby(["regime_label", "k_shot"])[error_col].mean().reset_index()
        agg_regime.to_csv(out_dir / "aggregate_by_regime.csv", index=False)

    # ----------------------------------------------------------------
    # Figures
    # ----------------------------------------------------------------
    if "k_shot" in combined.columns and error_col in combined.columns:
        # Initial and final error by k (oneshot vs feedback)
        for exp_type in combined.get("experiment_type", pd.Series(["oneshot"])).unique():
            sub = combined[combined.get("experiment_type", "oneshot") == exp_type] \
                if "experiment_type" in combined.columns else combined
            by_k = sub.groupby("k_shot")[error_col].mean()

            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(by_k.index, by_k.values, "o-", color="#5C6BC0", linewidth=1.8, ms=6)
            ax.set_xlabel("k-shot (number of in-context examples)")
            ax.set_ylabel("Mean ΔE (LAB)")
            ax.set_title(f"ICL {exp_type}: error by k")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            _save_fig(fig, figures_dir / f"icl_{exp_type}_error_by_k.png")

        # Random vs text-similar
        if "retrieval_mode" in combined.columns:
            for mode in ["random", "text_similar"]:
                if mode not in combined["retrieval_mode"].values:
                    continue
            fig, ax = plt.subplots(figsize=(7, 4))
            for mode, grp in combined.groupby("retrieval_mode"):
                by_k = grp.groupby("k_shot")[error_col].mean()
                ax.plot(by_k.index, by_k.values, "o-", label=mode, linewidth=1.8, ms=5)
            ax.set_xlabel("k-shot")
            ax.set_ylabel("Mean ΔE")
            ax.set_title("ICL: error by retrieval mode")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            _save_fig(fig, figures_dir / "icl_random_vs_textsimilar.png")

    # ----------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------
    lines = [
        "# ICL Calibration — Combined Report",
        "",
        f"**Runs**: {len(run_dirs)}",
        "",
        "## Aggregate by k_shot",
        "",
    ]
    agg_k_path = out_dir / "aggregate_by_k_shot.csv"
    if agg_k_path.exists():
        agg_k_df = pd.read_csv(agg_k_path)
        lines.append("| k_shot | mean ΔE | std | n |")
        lines.append("|---|---|---|---|")
        for _, row in agg_k_df.iterrows():
            lines.append(f"| {int(row['k_shot'])} | {row['mean_error']:.2f} | {row.get('std_error',0):.2f} | {int(row['n'])} |")

    lines += [
        "",
        "## Paper-Facing Questions",
        "",
        "1. **Does ICL improve the initial guess?**",
        "   → Compare k=0 vs k>0 in aggregate_by_k_shot.csv (oneshot experiment)",
        "",
        "2. **Does ICL still help after oracle feedback?**",
        "   → Compare feedback runs at k=0 vs k>0",
        "",
        "3. **Does similar-example retrieval outperform random?**",
        "   → See aggregate_by_retrieval_mode.csv and icl_random_vs_textsimilar.png",
        "",
        "## Figures",
        "",
        "- `figures/icl_oneshot_error_by_k.png`",
        "- `figures/icl_feedback_error_by_k.png`",
        "- `figures/icl_random_vs_textsimilar.png`",
    ]

    (out_dir / "combined_report.md").write_text("\n".join(lines))
    logger.info("Written combined_report.md")
    print(f"\nDone. Results in {out_dir}")


if __name__ == "__main__":
    main()
