"""Generate oracle vs LLM teacher paired trajectory figures.

Usage:
    # Plot all cases in selected_cases.csv:
    uv run python scripts/plot_teacher_pair_trajectories.py \\
        --cases reports/comparisons/teacher_pair_visualization/selected_cases.csv \\
        --out_dir reports/comparisons/teacher_pair_visualization/figures

    # Plot a specific example (default: one combined a*b* panel + feedback rails):
    uv run python scripts/plot_teacher_pair_trajectories.py \\
        --cases reports/comparisons/teacher_pair_visualization/selected_cases.csv \\
        --case_id 305159 \\
        --out_dir reports/comparisons/teacher_pair_visualization/figures \\
        --feedback_layout rail \\
        --panel_layout overlay

    # Two separate a*b* panels (legacy):
    #   --panel_layout split

    # Legacy mid-path labels only (split layout):
    #   --feedback_layout inline --panel_layout split

    # Also generate a grid of the top N pairs:
    uv run python scripts/plot_teacher_pair_trajectories.py \\
        --cases reports/comparisons/teacher_pair_visualization/selected_cases.csv \\
        --out_dir reports/comparisons/teacher_pair_visualization/figures \\
        --grid_n 6
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.pairing import load_run_data
from colorref.trajectory_pair_viz import plot_pair_figure, plot_pair_grid
from colorref.trajectory_viz import load_trajectory_case

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
        description="Plot oracle vs LLM teacher paired trajectory figures.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--cases", required=True,
        help="Path to selected_cases.csv (from build_teacher_pair_cases.py)",
    )
    p.add_argument(
        "--out_dir",
        default="reports/comparisons/teacher_pair_visualization/figures",
        help="Output directory for figures",
    )
    p.add_argument(
        "--case_id", type=int, default=None,
        help="Only plot this example_id (optional)",
    )
    p.add_argument(
        "--grid_n", type=int, default=6,
        help="Number of pairs to include in the grid figure (0 to skip)",
    )
    p.add_argument(
        "--runs_root", default="runs",
        help="Root directory containing run directories",
    )
    p.add_argument(
        "--report", action="store_true",
        help="Write a markdown summary report alongside the figures",
    )
    p.add_argument(
        "--feedback_layout",
        choices=["rail", "inline", "both"],
        default="rail",
        help="How to show per-step teacher text (see trajectory_pair_viz.plot_pair_figure)",
    )
    p.add_argument(
        "--panel_layout",
        choices=["overlay", "split"],
        default="overlay",
        help="overlay = one shared a*b* plot + rails; split = two a*b* panels (legacy)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def _load_pair(
    row: pd.Series,
    runs_root: Path,
) -> tuple | None:
    """Load (oracle_case, llm_case, llm_fb_df) for one selected row."""
    eid = int(row["example_id"])

    oracle_run_dir = runs_root / str(row["oracle_run_id"])
    llm_run_dir = runs_root / str(row["llm_run_id"])

    if not oracle_run_dir.is_dir():
        logger.warning("Oracle run dir missing: %s", oracle_run_dir)
        return None
    if not llm_run_dir.is_dir():
        logger.warning("LLM run dir missing: %s", llm_run_dir)
        return None

    try:
        oracle_case = load_trajectory_case(
            oracle_run_dir, example_id=eid,
            condition=str(row.get("oracle_teacher_type", "oracle")),
        )
        llm_case = load_trajectory_case(
            llm_run_dir, example_id=eid,
            condition=str(row.get("llm_teacher_type", "llm_teacher")),
        )
    except Exception as exc:
        logger.warning("Could not load pair for example %d: %s", eid, exc)
        return None

    # LLM feedback df for correctness annotation
    try:
        _, llm_fb_df, _ = load_run_data(llm_run_dir)
    except Exception:
        llm_fb_df = None

    return oracle_case, llm_case, llm_fb_df


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _write_report(
    cases_df: pd.DataFrame,
    figure_paths: dict[int, Path],
    out_dir: Path,
) -> None:
    report_path = out_dir.parent / "combined_report.md"
    lines = [
        "# Oracle vs LLM Teacher Paired Visualization",
        "",
        "## Selection Criteria",
        "",
        "Cases are selected using five criteria (spec §4.4):",
        "- **Case 1**: LLM teacher failure (final ΔE > 25) while oracle succeeds (final ΔE < 10)",
        "- **Case 2**: Same (or close) initial guess, divergent final trajectories",
        "- **Case 3**: LLM feedback with < 40% directional precision (wrong-direction errors)",
        "- **Case 5**: LLM overcorrection — initial ΔE < 10, final ΔE > initial + 20",
        "",
        f"**Total selected cases**: {len(cases_df)}",
        "",
        "## Case Type Breakdown",
        "",
    ]

    for ct, cnt in cases_df["case_type"].value_counts().items():
        lines.append(f"- `{ct}`: {cnt}")

    lines += [
        "",
        "## Top 10 Cases by Selection Score",
        "",
        "| # | example_id | raw_name | oracle ΔE_f | LLM ΔE_f | LLM prec | case_type |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, row in cases_df.head(10).iterrows():
        o_f = f"{row['oracle_final_error']:.1f}" if pd.notna(row.get("oracle_final_error")) else "—"
        l_f = f"{row['llm_final_error']:.1f}" if pd.notna(row.get("llm_final_error")) else "—"
        prec = f"{row['llm_precision']:.2f}" if pd.notna(row.get("llm_precision")) else "—"
        lines.append(
            f"| {i+1} | {int(row['example_id'])} | {row['raw_name']} "
            f"| {o_f} | {l_f} | {prec} | {row['case_type']} |"
        )

    lines += ["", "## Qualitative Figures", ""]
    for eid, fp in figure_paths.items():
        rel = fp.relative_to(out_dir.parent) if fp.is_relative_to(out_dir.parent) else fp
        row = cases_df[cases_df["example_id"] == eid]
        if not row.empty:
            raw_name = row.iloc[0]["raw_name"]
            lines.append(f"### {raw_name} (id={eid})")
            lines.append(f"![pair figure]({rel})")
            lines.append("")

    lines += [
        "## Recommended Paper Caption",
        "",
        "**Figure X**: *Oracle vs LLM in one CIELAB a\\*–b\\* panel (chromaticity background), with a "
        "narrow lightness strip (paired L* bars per turn: oracle vs LLM) and two full-width feedback rows "
        "(oracle, then LLM) in the style of single-trajectory paper figures. Numbered nodes use the guess "
        "hex; target is a solid white ring. Curved blue vs dashed-orange arrows separate the two "
        "teacher-driven paths. LLM row cards show ✓/✗ when directions are parseable.*",
        "",
    ]

    report_path.write_text("\n".join(lines))
    logger.info("Written report: %s", report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        logger.error("Cases file not found: %s", cases_path)
        sys.exit(1)

    cases_df = pd.read_csv(cases_path)
    logger.info("Loaded %d selected cases", len(cases_df))

    if args.case_id is not None:
        cases_df = cases_df[cases_df["example_id"] == args.case_id]
        if cases_df.empty:
            logger.error("example_id %d not found in cases file", args.case_id)
            sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs_root)

    figure_paths: dict[int, Path] = {}
    pairs_loaded: list[tuple] = []

    for _, row in cases_df.iterrows():
        eid = int(row["example_id"])
        result = _load_pair(row, runs_root)
        if result is None:
            continue

        oracle_case, llm_case, llm_fb_df = result
        pairs_loaded.append((oracle_case, llm_case))

        # Determine output name
        safe_name = _safe_name(str(row["raw_name"]))
        oracle_tt = _safe_name(str(row.get("oracle_teacher_type", "oracle")))
        llm_tt = _safe_name(str(row.get("llm_teacher_type", "llm")))
        fname = f"pair_{eid}_{safe_name}_{oracle_tt}_vs_{llm_tt}.png"
        out_path = out_dir / fname

        oracle_label = str(row.get("oracle_teacher_type", "Oracle"))
        llm_label = str(row.get("llm_teacher_type", "LLM Teacher"))

        try:
            import matplotlib.pyplot as plt
            fig = plot_pair_figure(
                oracle_case, llm_case, llm_fb_df,
                out_path=out_path,
                oracle_panel_label=oracle_label,
                llm_panel_label=llm_label,
                feedback_layout=args.feedback_layout,
                panel_layout=args.panel_layout,
            )
            plt.close(fig)
            figure_paths[eid] = out_path
            logger.info("  Saved: %s", fname)
        except Exception as exc:
            logger.warning("  Failed for example %d: %s", eid, exc)

    logger.info("Generated %d pair figures", len(figure_paths))

    # Grid figure
    if args.grid_n > 0 and pairs_loaded:
        import matplotlib.pyplot as plt
        grid_pairs = pairs_loaded[: args.grid_n]
        grid_path = out_dir / "oracle_vs_llm_teacher_pair_grid.png"
        try:
            fig = plot_pair_grid(grid_pairs, out_path=grid_path, cols=1)
            plt.close(fig)
            logger.info("Saved grid figure: %s", grid_path)
        except Exception as exc:
            logger.warning("Grid figure failed: %s", exc)

    # Markdown report
    if args.report:
        _write_report(cases_df, figure_paths, out_dir)

    print(f"\nDone. Generated {len(figure_paths)} figures in {out_dir}")


if __name__ == "__main__":
    main()
