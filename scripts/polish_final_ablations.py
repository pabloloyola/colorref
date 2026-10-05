"""Generate the final ablations summary report combining all four experiments.

Usage:
    uv run python scripts/polish_final_ablations.py \\
        --convergence_dir reports/comparisons/convergence_sweep \\
        --icl_dir reports/comparisons/icl_calibration \\
        --pair_dir reports/comparisons/teacher_pair_visualization \\
        --budget_dir reports/comparisons/information_budget \\
        --out_dir reports/comparisons/final_ablations_summary
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

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
        description="Combine all ablation results into a final summary report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--convergence_dir", default="reports/comparisons/convergence_sweep")
    p.add_argument("--icl_dir", default="reports/comparisons/icl_calibration")
    p.add_argument("--pair_dir", default="reports/comparisons/teacher_pair_visualization")
    p.add_argument("--budget_dir", default="reports/comparisons/information_budget")
    p.add_argument("--out_dir", default="reports/comparisons/final_ablations_summary")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return f"*(file not found: {path})*"


def _section_exists(d: Path, filename: str) -> bool:
    return (d / filename).exists()


def _load_csv_summary(path: Path, n: int = 5) -> str:
    if not path.exists():
        return f"*(not found: {path})*"
    try:
        df = pd.read_csv(path)
        return df.head(n).to_markdown(index=False)
    except Exception as e:
        return f"*(error reading {path}: {e})*"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_CLASSIFICATION = {
    # Convergence
    "figures/error_by_turn_long.png": "main_paper",
    "figures/best_error_by_turn_long.png": "main_paper",
    "figures/convergence_rate_by_turn.png": "appendix",
    "figures/final_vs_best_gap_by_turn.png": "appendix",
    "figures/regression_rate_by_turn.png": "appendix",
    "aggregate_by_max_turns.csv": "main_paper",
    # Teacher pairs
    "figures/oracle_vs_llm_teacher_pair_grid.png": "main_paper",
    "selected_cases.csv": "appendix",
    # Information budget
    "figures/one_turn_c3_vs_three_turn_c1.png": "main_paper",
    "figures/final_error_by_total_budget.png": "appendix",
    "figures/improvement_per_constraint.png": "appendix",
    "aggregate_by_budget_condition.csv": "main_paper",
    # ICL
    "figures/icl_oneshot_error_by_k.png": "appendix",
    "figures/icl_random_vs_textsimilar.png": "appendix",
    "aggregate_by_k_shot.csv": "appendix",
}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(args: argparse.Namespace, out_dir: Path) -> str:
    conv_dir = Path(args.convergence_dir)
    icl_dir = Path(args.icl_dir)
    pair_dir = Path(args.pair_dir)
    budget_dir = Path(args.budget_dir)

    lines = [
        "# Final Ablations Summary",
        "",
        "This report consolidates four ablation experiments for the ColorRef EMNLP paper:",
        "",
        "| Experiment | Status |",
        "|---|---|",
        f"| A. Convergence sweep | {'✓ Complete' if _section_exists(conv_dir, 'combined_report.md') else '⏳ Pending'} |",
        f"| B. ICL calibration | {'✓ Complete' if _section_exists(icl_dir, 'combined_report.md') else '⏳ Pending'} |",
        f"| C. Oracle vs LLM teacher pairs | {'✓ Complete' if _section_exists(pair_dir, 'combined_report.md') else '⏳ Pending'} |",
        f"| D. Information budget | {'✓ Complete' if _section_exists(budget_dir, 'combined_report.md') else '⏳ Pending'} |",
        "",
        "---",
        "",
        "## A. Convergence and Longer Games",
        "",
        "**Question**: Does performance plateau after 3 feedback rounds?",
        "",
    ]

    conv_agg = conv_dir / "aggregate_by_max_turns.csv"
    if conv_agg.exists():
        lines.append("### Results by max_turns")
        lines.append("")
        lines.append(_load_csv_summary(conv_agg, n=8))
        lines.append("")

    lines += [
        "### Key Figures",
        "- `convergence_sweep/figures/error_by_turn_long.png` → **main_paper**",
        "- `convergence_sweep/figures/best_error_by_turn_long.png` → **main_paper**",
        "- `convergence_sweep/figures/regression_rate_by_turn.png` → **appendix**",
        "",
        "---",
        "",
        "## B. In-Context Learning Calibration",
        "",
        "**Question**: Do in-context examples improve the initial color prior, or does feedback already provide localization?",
        "",
    ]

    icl_agg = icl_dir / "aggregate_by_k_shot.csv"
    if icl_agg.exists():
        lines.append("### Results by k_shot")
        lines.append("")
        lines.append(_load_csv_summary(icl_agg, n=6))
        lines.append("")

    lines += [
        "### Key Figures",
        "- `icl_calibration/figures/icl_oneshot_error_by_k.png` → **appendix**",
        "- `icl_calibration/figures/icl_random_vs_textsimilar.png` → **appendix**",
        "",
        "---",
        "",
        "## C. Oracle vs LLM Teacher Paired Examples",
        "",
        "**Question**: Is the oracle/LLM gap semantically and geometrically visible in trajectories?",
        "",
    ]

    pair_cases = pair_dir / "selected_cases.csv"
    if pair_cases.exists():
        df = pd.read_csv(pair_cases)
        lines.append(f"**Selected cases**: {len(df)}")
        lines.append("")
        lines.append("### Case Type Breakdown")
        lines.append("")
        for ct, cnt in df["case_type"].value_counts().head(6).items():
            lines.append(f"- `{ct}`: {cnt}")
        lines.append("")
        lines.append("### Top 5 by Selection Score")
        lines.append("")
        show = df[["example_id", "raw_name", "oracle_final_error", "llm_final_error", "llm_precision", "case_type"]].head(5)
        lines.append("| example_id | raw_name | oracle ΔE_f | LLM ΔE_f | LLM prec | case_type |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in show.iterrows():
            lines.append(
                f"| {int(r['example_id'])} | {r['raw_name']} "
                f"| {r['oracle_final_error']:.1f} | {r['llm_final_error']:.1f} "
                f"| {r['llm_precision']:.2f} | {r['case_type']} |"
            )
        lines.append("")

    figures_dir = pair_dir / "figures"
    pair_figs = sorted(figures_dir.glob("pair_*.png")) if figures_dir.exists() else []
    lines += [
        "### Key Figures",
        f"- `teacher_pair_visualization/figures/oracle_vs_llm_teacher_pair_grid.png` → **main_paper**",
        f"- {len(pair_figs)} individual pair figures → **appendix**",
        "",
        "---",
        "",
        "## D. Information Budget",
        "",
        "**Question**: Does iterative feedback matter beyond total constraint count?",
        "",
    ]

    budget_agg = budget_dir / "aggregate_by_budget_condition.csv"
    if budget_agg.exists():
        lines.append("### Results by budget condition")
        lines.append("")
        lines.append(_load_csv_summary(budget_agg, n=10))
        lines.append("")

    lines += [
        "### Key Figures",
        "- `information_budget/figures/one_turn_c3_vs_three_turn_c1.png` → **main_paper**",
        "- `information_budget/figures/improvement_per_constraint.png` → **appendix**",
        "",
        "---",
        "",
        "## Recommended Paper Integration",
        "",
        "| Artifact | Experiment | Recommended placement |",
        "|---|---|---|",
    ]
    for artifact, placement in _CLASSIFICATION.items():
        exp = (
            "Convergence" if "error_by_turn" in artifact or "convergence" in artifact or "regression" in artifact or "max_turns" in artifact
            else "ICL" if "icl" in artifact
            else "Teacher Pairs" if "pair" in artifact or "selected_cases" in artifact
            else "Info Budget" if "budget" in artifact or "three_turn" in artifact or "one_turn" in artifact or "constraint" in artifact
            else "—"
        )
        lines.append(f"| `{artifact}` | {exp} | **{placement}** |")

    lines += [
        "",
        "---",
        "",
        "## Discussion Recommendations",
        "",
        "- **Convergence**: Use turn curves to motivate the 3-turn default. If marginal_gain drops below 1 ΔE at turn 3→5, cite this as justification.",
        "- **ICL**: If k=4 gives minimal improvement over k=0 after oracle feedback, argue that interactive correction dominates prior calibration.",
        "- **Teacher pairs**: Use the paired trajectory figure (main paper) to visually explain *why* LLM teachers fail — wrong-direction feedback in CIELAB space.",
        "- **Budget**: If one_turn_c3 underperforms three_turn_c1 (same total budget=3), argue that iterative conditioning matters.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_text = build_report(args, out_dir)
    report_path = out_dir / "final_ablations_report.md"
    report_path.write_text(report_text)
    logger.info("Written: %s", report_path)
    print(f"\nFinal ablations report: {report_path}")


if __name__ == "__main__":
    main()
