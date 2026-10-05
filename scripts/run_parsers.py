"""
Stage 2: run parser v1 and parser v2 on the canonical dataset.

Outputs
-------
  data/processed/colornames_v1.parquet      canonical + v1 parse fields
  data/processed/colornames_v2.parquet      canonical + v2 parse fields
  data/audits/parser_v1_audit.csv           200 samples per major category
  data/audits/parser_v2_audit.csv           200 samples per major category
  reports/parser_comparison.md             coverage + migration table

Usage:
    uv run scripts/run_parsers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml
from tqdm import tqdm

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsing.parser_v1 import ColorNameParserV1
from src.parsing.parser_v2 import ColorNameParserV2


# ---------------------------------------------------------------------------
# Load configs
# ---------------------------------------------------------------------------

def load_lexicons(lexicons_path: Path, proto_path: Path, suffix_path: Path):
    with open(lexicons_path) as f:
        lex = yaml.safe_load(f)
    with open(proto_path) as f:
        proto = yaml.safe_load(f)
    with open(suffix_path) as f:
        suffix = yaml.safe_load(f)

    heads     = set(lex["heads"])
    modifiers = set(lex["modifiers"])
    prototype_terms = set(proto["prototype_terms"])
    ish_exceptions  = suffix.get("ish_exceptions", {})
    plural_strip    = suffix.get("plural_strip", True)
    plural_min_len  = suffix.get("plural_min_len", 4)

    return heads, modifiers, prototype_terms, ish_exceptions, plural_strip, plural_min_len


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def run_parser(parser, df: pd.DataFrame, desc: str) -> pd.DataFrame:
    records = []
    for row in tqdm(df.itertuples(), total=len(df), desc=desc):
        r = parser.parse(row.raw_name)
        records.append({
            "example_id":               row.example_id,
            "parser_version":           r.parser_version,
            "parse_category":           r.category,
            "parse_confidence":         r.confidence,
            "parsed_head":              r.head,
            "parsed_modifiers":         "|".join(r.modifiers),
            "candidate_prototype_terms": "|".join(r.candidate_prototype_terms),
        })
    return pd.DataFrame(records)


def merge_parse_results(canonical: pd.DataFrame, parse_df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [
        "parser_version", "parse_category", "parse_confidence",
        "parsed_head", "parsed_modifiers", "candidate_prototype_terms",
    ]
    base = canonical.drop(columns=[c for c in drop_cols if c in canonical.columns])
    return base.merge(parse_df, on="example_id", how="left")


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

AUDIT_COLS = [
    "example_id", "raw_name", "parse_category", "parse_confidence",
    "parsed_head", "parsed_modifiers", "candidate_prototype_terms",
]

def save_audit(df: pd.DataFrame, path: Path, n_per_cat: int = 200):
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for cat, grp in df.groupby("parse_category"):
        sample = grp.sample(min(n_per_cat, len(grp)), random_state=42)
        chunks.append(sample[AUDIT_COLS])
    audit = pd.concat(chunks).sort_values(["parse_category", "parse_confidence"])
    audit.to_csv(path, index=False)
    print(f"  Audit saved → {path}  ({len(audit):,} rows)")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def category_table(df: pd.DataFrame, label: str) -> str:
    total = len(df)
    counts = df["parse_category"].value_counts().sort_index()
    lines = [f"### {label}", "", f"Total: {total:,}", ""]
    lines.append(f"{'Category':<28} {'Count':>8}  {'%':>6}")
    lines.append("-" * 48)
    for cat, n in counts.items():
        lines.append(f"{cat:<28} {n:>8,}  {100*n/total:5.1f}%")
    lines.append("")
    return "\n".join(lines)


def migration_table(v1: pd.DataFrame, v2: pd.DataFrame) -> str:
    m = v1[["example_id", "parse_category"]].merge(
        v2[["example_id", "parse_category"]],
        on="example_id",
        suffixes=("_v1", "_v2"),
    )
    pivot = (
        m.groupby(["parse_category_v1", "parse_category_v2"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    lines = ["### Migration table (v1 → v2)", "", f"{'v1 category':<28} {'v2 category':<28} {'count':>8}"]
    lines.append("-" * 68)
    for _, row in pivot.iterrows():
        lines.append(f"{row['parse_category_v1']:<28} {row['parse_category_v2']:<28} {row['count']:>8,}")
    lines.append("")

    # Summary: how much did no_head shrink?
    no_head_v1 = (m["parse_category_v1"] == "no_head").sum()
    no_head_v2 = (m["parse_category_v2"] == "no_head").sum()
    rescued = no_head_v1 - no_head_v2
    lines += [
        f"no_head in v1 : {no_head_v1:,}",
        f"no_head in v2 : {no_head_v2:,}",
        f"Rescued by v2 : {rescued:,}  ({100*rescued/max(no_head_v1,1):.1f}% of v1 no_head)",
        "",
    ]
    return "\n".join(lines)


def coverage_line(df: pd.DataFrame, label: str) -> str:
    total = len(df)
    interpretable = df["parse_category"].isin(
        ["head_only", "modifier_head", "multi_modifier",
         "prototype_head", "modifier_prototype"]
    ).sum()
    return f"{label:<10}: {interpretable:,} / {total:,} interpretable  ({100*interpretable/total:.1f}%)"


def write_report(v1_df, v2_df, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Parser comparison report (v1 vs v2)",
        "",
        "## Coverage",
        "",
        coverage_line(v1_df, "Parser v1"),
        coverage_line(v2_df, "Parser v2"),
        "",
        "## Category distributions",
        "",
        category_table(v1_df, "Parser v1"),
        category_table(v2_df, "Parser v2"),
        migration_table(v1_df, v2_df),
    ]
    out_path.write_text("\n".join(lines))
    print(f"  Report saved → {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = Path(__file__).parent.parent

    canonical_path  = root / "data/colornames_canonical.parquet"
    lexicons_path   = root / "configs/lexicons.yaml"
    proto_path      = root / "configs/prototype_terms.yaml"
    suffix_path     = root / "configs/suffix_rules.yaml"
    out_v1          = root / "data/colornames_v1.parquet"
    out_v2          = root / "data/colornames_v2.parquet"
    audit_v1        = root / "data/audits/parser_v1_audit.csv"
    audit_v2        = root / "data/audits/parser_v2_audit.csv"
    report_path     = root / "reports/parser_comparison.md"

    print("Loading canonical dataset...")
    canonical = pd.read_parquet(canonical_path)
    print(f"  {len(canonical):,} rows")

    print("Loading lexicons...")
    heads, modifiers, prototype_terms, ish_exceptions, plural_strip, plural_min_len = \
        load_lexicons(lexicons_path, proto_path, suffix_path)
    print(f"  heads={len(heads)}  modifiers={len(modifiers)}  prototypes={len(prototype_terms)}")

    # ---- Parser v1
    parser_v1 = ColorNameParserV1(heads=heads, modifiers=modifiers)
    parse_v1  = run_parser(parser_v1, canonical, "Parser v1")
    merged_v1 = merge_parse_results(canonical, parse_v1)
    merged_v1.to_parquet(out_v1, index=False)
    print(f"  Saved → {out_v1}")
    save_audit(merged_v1, audit_v1)

    # ---- Parser v2
    parser_v2 = ColorNameParserV2(
        heads=heads,
        modifiers=modifiers,
        prototype_terms=prototype_terms,
        ish_exceptions=ish_exceptions,
        plural_strip=plural_strip,
        plural_min_len=plural_min_len,
    )
    parse_v2  = run_parser(parser_v2, canonical, "Parser v2")
    merged_v2 = merge_parse_results(canonical, parse_v2)
    merged_v2.to_parquet(out_v2, index=False)
    print(f"  Saved → {out_v2}")
    save_audit(merged_v2, audit_v2)

    # ---- Report
    write_report(merged_v1, merged_v2, report_path)

    # ---- Quick console summary
    print("\n--- Quick summary ---")
    for label, df in [("v1", merged_v1), ("v2", merged_v2)]:
        print(f"\n  [{label}] category distribution:")
        total = len(df)
        for cat, n in df["parse_category"].value_counts().items():
            print(f"    {cat:<28} {n:>8,}  {100*n/total:5.1f}%")


if __name__ == "__main__":
    main()
