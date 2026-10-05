"""
Stage 3: compute component scores and assign regime labels.

Input  : data/processed/colornames_v2.parquet  (canonical + v2 parse fields)
Output : data/processed/colornames_taxonomy.parquet  (adds all scores + labels)
         reports/taxonomy_summary.md

Usage:
    uv run scripts/build_taxonomy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.taxonomy.scores import compute_all_scores
from src.taxonomy.regime_labeler import assign_regimes, REGIMES


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = Path(__file__).parent.parent
    in_path  = root / "data/colornames_v2.parquet"
    out_path = root / "data/colornames_taxonomy.parquet"
    rep_path = root / "reports/taxonomy_summary.md"

    print(f"Loading {in_path}")
    df = pd.read_parquet(in_path)
    print(f"  {len(df):,} rows")

    # ---- Component scores
    print("Computing component scores...")
    scores = compute_all_scores(df)
    for col in scores.columns:
        df[col] = scores[col]

    # ---- Regime labels
    print("Assigning regime labels...")
    labels, conf = assign_regimes(df)
    df["regime_label"]      = labels
    df["regime_confidence"] = conf.round(4)

    # ---- Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"Saved → {out_path}  ({len(df):,} rows, {len(df.columns)} columns)")

    # ---- Console summary
    total = len(df)
    print("\n--- Regime distribution ---")
    for regime in REGIMES:
        n = (df["regime_label"] == regime).sum()
        bar = "█" * int(40 * n / total)
        print(f"  {regime:<28} {n:>8,}  {100*n/total:5.1f}%  {bar}")

    print("\n--- Score distributions (mean ± std) ---")
    for col in ["explicitness_score", "prototype_score", "rarity_score", "abstraction_score"]:
        print(f"  {col:<28} {df[col].mean():.3f} ± {df[col].std():.3f}")

    print("\n--- Regime confidence (mean per regime) ---")
    for regime in REGIMES:
        sub = df[df["regime_label"] == regime]["regime_confidence"]
        print(f"  {regime:<28} {sub.mean():.3f}")

    # ---- Report
    write_report(df, rep_path)
    print(f"\nReport saved → {rep_path}")


def write_report(df: pd.DataFrame, path: Path):
    total = len(df)
    lines = [
        "# Taxonomy summary (Stage 3)",
        "",
        f"Total examples: {total:,}",
        "",
        "## Regime distribution",
        "",
        f"{'Regime':<28} {'Count':>8}  {'%':>6}  {'Mean conf':>10}",
        "-" * 60,
    ]
    for regime in REGIMES:
        sub = df[df["regime_label"] == regime]
        n   = len(sub)
        c   = sub["regime_confidence"].mean() if n > 0 else 0.0
        lines.append(f"{regime:<28} {n:>8,}  {100*n/total:5.1f}%  {c:>10.3f}")

    lines += [
        "",
        "## Component score distributions",
        "",
        f"{'Score':<28} {'Mean':>6}  {'Std':>6}  {'Min':>6}  {'Max':>6}",
        "-" * 58,
    ]
    for col in ["explicitness_score", "prototype_score", "rarity_score", "abstraction_score"]:
        lines.append(
            f"{col:<28} {df[col].mean():6.3f}  {df[col].std():6.3f}"
            f"  {df[col].min():6.3f}  {df[col].max():6.3f}"
        )

    lines += ["", "## Per-regime score means", ""]
    score_cols = ["explicitness_score", "prototype_score", "rarity_score", "abstraction_score"]
    header = f"{'Regime':<28} " + "  ".join(f"{c[:8]:>8}" for c in score_cols)
    lines.append(header)
    lines.append("-" * (28 + 12 * len(score_cols)))
    for regime in REGIMES:
        sub = df[df["regime_label"] == regime]
        row = f"{regime:<28} "
        row += "  ".join(f"{sub[c].mean():8.3f}" for c in score_cols)
        lines.append(row)

    lines += [
        "",
        "## Sample names per regime (top 10 by regime confidence)",
        "",
    ]
    for regime in REGIMES:
        sub = df[df["regime_label"] == regime].nlargest(10, "regime_confidence")
        lines.append(f"### {regime}")
        lines.append("")
        for _, row in sub.iterrows():
            lines.append(
                f"  - `{row['raw_name']}`  "
                f"(conf={row['regime_confidence']:.2f}, "
                f"cat={row['parse_category']}, "
                f"head={row['parsed_head']})"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
