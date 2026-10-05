"""Regenerate reports/paper_handoff_emnlp_v1.md from current comparison outputs.

Usage:
    uv run python scripts/generate_paper_handoff.py
    uv run python scripts/generate_paper_handoff.py --out reports/paper_handoff_emnlp_v1.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from colorref.comparison_reports import condition_label_from_run_id  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "paper_handoff_emnlp_v1.md"
TEMPLATE_HEADER = """# ColorRef — EMNLP paper handoff (auto-generated core stats)

**Generated:** {ts}  
**Note:** This section is auto-appended with fresh numbers. Merge into the full handoff or use standalone.

---

## Auto-generated tables

"""


def _cond_table(parquet: Path) -> pd.DataFrame:
    pe = pd.read_parquet(parquet)
    pe["condition"] = pe["run_id"].map(condition_label_from_run_id)
    return (
        pe.groupby("condition")
        .agg(
            n=("example_id", "count"),
            init=("initial_error_lab", "mean"),
            final=("final_error_lab", "mean"),
            rel=("relative_improvement", "mean"),
            csat=("mean_constraint_satisfaction", "mean"),
            dalign=("mean_directional_alignment", "mean"),
            conv=("converged", "mean"),
        )
        .round(3)
    )


def _md_table(df: pd.DataFrame, title: str) -> str:
    lines = [f"### {title}", ""]
    # Simple markdown table without tabulate dependency
    if isinstance(df.index, pd.MultiIndex):
        cols = list(df.index.names) + list(df.columns)
        lines.append("| " + " | ".join(str(c) for c in cols) + " |")
        lines.append("| " + " | ".join("---" for _ in cols) + " |")
        for idx, row in df.iterrows():
            if isinstance(idx, tuple):
                key = list(idx)
            else:
                key = [idx]
            vals = [f"{v:.3f}" if isinstance(v, float) else str(v) for v in row.values]
            lines.append("| " + " | ".join(str(x) for x in key + vals) + " |")
    else:
        lines.append("| " + " | ".join([df.index.name or ""] + list(df.columns)) + " |")
        lines.append("| " + " | ".join(["---"] * (len(df.columns) + 1)) + " |")
        for idx, row in df.iterrows():
            vals = [f"{v:.3f}" if isinstance(v, float) else str(v) for v in row.values]
            lines.append("| " + " | ".join([str(idx)] + vals) + " |")
    lines.append("")
    return "\n".join(lines)


def build_stats_section() -> str:
    parts = [TEMPLATE_HEADER.format(ts=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))]

    bw = ROOT / "reports/comparisons/feedback_bandwidth/combined_per_example.parquet"
    if bw.exists():
        parts.append(_md_table(_cond_table(bw), "Bandwidth (main_1000)"))

    fin = ROOT / "reports/comparisons/final_main_4000/combined_per_example.parquet"
    if fin.exists():
        parts.append(_md_table(_cond_table(fin), "Scale-up (main_4000)"))

    pe = fin if fin.exists() else None
    if pe and pe.exists():
        df = pd.read_parquet(pe)
        df["condition"] = df["run_id"].map(condition_label_from_run_id)
        sub = df[df["condition"] == "axis_c3"]
        regime = (
            sub.groupby("regime_label")
            .agg(
                n=("example_id", "count"),
                init=("initial_error_lab", "mean"),
                final=("final_error_lab", "mean"),
                rel=("relative_improvement", "mean"),
            )
            .round(2)
        )
        parts.append(_md_table(regime, "Regime breakdown — axis_c3 (main_4000)"))

    model_pe = ROOT / "reports/comparisons/model_comparison/combined_per_example.parquet"
    if model_pe.exists():
        df = pd.read_parquet(model_pe)
        df["condition"] = df["run_id"].map(condition_label_from_run_id)
        pivot = (
            df.groupby(["model_alias", "condition"])
            .agg(final=("final_error_lab", "mean"), rel=("relative_improvement", "mean"))
            .round(2)
        )
        parts.append(_md_table(pivot, "Model comparison (main_1000)"))

    audit = ROOT / "reports/comparisons/llm_teacher_decomposition/teacher_feedback_audit_summary.csv"
    if audit.exists():
        parts.append(_md_table(pd.read_csv(audit), "LLM teacher audit summary"))

    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate or update paper handoff markdown.")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--stats-only",
        action="store_true",
        help="Write only auto-generated stats (separate file)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_stats_section()

    if args.stats_only:
        out = args.out.parent / (args.out.stem + "_stats.md")
        out.write_text(stats, encoding="utf-8")
        print(f"Wrote {out}")
        return

    base = args.out
    if base.exists():
        text = base.read_text(encoding="utf-8")
        start, end = "<!-- AUTO_STATS_START -->", "<!-- AUTO_STATS_END -->"
        if start in text:
            pre = text.split(start)[0].rstrip()
            text = pre + "\n\n" + start + "\n" + stats.split("---\n\n", 1)[-1] + end + "\n"
        else:
            text = text.rstrip() + f"\n\n{start}\n" + stats.split("---\n\n", 1)[-1] + end + "\n"
        base.write_text(text, encoding="utf-8")
        print(f"Updated {base} (refreshed auto-stats section)")
    else:
        base.write_text(stats, encoding="utf-8")
        print(f"Wrote {base} (stats only — copy full handoff template if missing)")


if __name__ == "__main__":
    main()
