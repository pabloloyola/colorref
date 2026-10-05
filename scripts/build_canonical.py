"""
Build the canonical processed dataset (Stage 1).

Reads  data/raw/colornames_en.parquet
Writes data/processed/colornames_canonical.parquet

Adds:
  - example_id          sequential int (stable sort by raw_name)
  - normalized_name     lowercase, collapsed whitespace
  - rgb_r/g/b           renamed from r/g/b
  - char_len            character length of raw_name
  - word_len            whitespace-token count of normalized_name
  - tokenizer_name      model tokenizer used
  - token_count         number of subword tokens
  - token_ids           list[int] of token ids (stored as parquet list column)

Placeholder null columns for later stages:
  - parser_version, parse_category, parse_confidence,
    parsed_head, parsed_modifiers, candidate_prototype_terms,
    abstractness_score, prototype_score, rarity_score,
    regime_label, regime_confidence

Usage:
    uv run scripts/build_canonical.py [--tokenizer bert-base-uncased] [--batch 1024]
"""

import argparse
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from transformers import AutoTokenizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"\s+", " ", n)
    return n


def tokenize_batch(texts: list[str], tokenizer, max_length: int = 64):
    enc = tokenizer(
        texts,
        add_special_tokens=False,
        truncation=True,
        max_length=max_length,
        padding=False,
    )
    return enc["input_ids"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Build canonical dataset (Stage 1).")
    p.add_argument("--input",     type=Path, default=Path("data/colornames_en.parquet"))
    p.add_argument("--out",       type=Path, default=Path("data/colornames_canonical.parquet"))
    p.add_argument("--tokenizer", type=str,  default="bert-base-uncased")
    p.add_argument("--batch",     type=int,  default=2048,
                   help="Tokenizer batch size")
    return p.parse_args()


def main():
    args = parse_args()

    print(f"Loading {args.input}")
    df = pd.read_parquet(args.input)
    print(f"  {len(df):,} rows, columns: {list(df.columns)}")

    # ------------------------------------------------------------------ ids
    # Sort by name for stable, reproducible IDs across runs
    df = df.sort_values("name").reset_index(drop=True)
    df.insert(0, "example_id", df.index.astype("int32"))

    # ------------------------------------------ rename / derive base fields
    df.rename(columns={"name": "raw_name", "r": "rgb_r", "g": "rgb_g", "b": "rgb_b"},
              inplace=True)
    df["normalized_name"] = df["raw_name"].map(normalize)
    df["char_len"] = df["raw_name"].str.len().astype("int16")
    df["word_len"] = df["normalized_name"].str.split().str.len().astype("int16")

    # --------------------------------------------------- tokenizer
    print(f"Loading tokenizer: {args.tokenizer}")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    df["tokenizer_name"] = args.tokenizer

    all_ids = []
    names = df["normalized_name"].tolist()
    for start in tqdm(range(0, len(names), args.batch), desc="Tokenizing"):
        batch = names[start : start + args.batch]
        all_ids.extend(tokenize_batch(batch, tokenizer))

    df["token_count"] = pd.array([len(ids) for ids in all_ids], dtype="int16")
    df["token_ids"]   = all_ids   # list[int] per row — stored as parquet list column

    # -------------------------------------- placeholder columns (later stages)
    for col in [
        "parser_version", "parse_category", "parsed_head", "parsed_modifiers",
        "candidate_prototype_terms", "regime_label",
    ]:
        df[col] = pd.NA

    for col in [
        "parse_confidence", "abstractness_score", "prototype_score",
        "rarity_score", "regime_confidence",
    ]:
        df[col] = pd.NA

    # -------------------------------------------------------- column ordering
    ordered = [
        "example_id", "raw_name", "normalized_name", "hex",
        "rgb_r", "rgb_g", "rgb_b",
        "lab_l", "lab_a", "lab_b",
        "hsv_h", "hsv_s", "hsv_v",
        "score", "char_len", "word_len",
        "tokenizer_name", "token_count", "token_ids",
        "parser_version", "parse_category", "parse_confidence",
        "parsed_head", "parsed_modifiers", "candidate_prototype_terms",
        "abstractness_score", "prototype_score", "rarity_score",
        "regime_label", "regime_confidence",
    ]
    df = df[ordered]

    # -------------------------------------------------------- save
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"\nSaved → {args.out}  ({len(df):,} rows, {len(df.columns)} columns)")

    # -------------------------------------------------------- summary
    print("\n--- Dataset summary ---")
    print(f"  Total entries     : {len(df):,}")
    print(f"  Unique names      : {df['raw_name'].nunique():,}")
    print(f"  Char len  mean/max: {df['char_len'].mean():.1f} / {df['char_len'].max()}")
    print(f"  Word len  mean/max: {df['word_len'].mean():.1f} / {df['word_len'].max()}")
    print(f"  Token cnt mean/max: {df['token_count'].mean():.1f} / {df['token_count'].max()}")
    print(f"  Score     mean    : {df['score'].mean():.3f}")
    print(f"  Score     min/max : {df['score'].min():.2f} / {df['score'].max():.2f}")
    print(f"\n  Lab L  range: [{df['lab_l'].min():.1f}, {df['lab_l'].max():.1f}]")
    print(f"  Lab a  range: [{df['lab_a'].min():.1f}, {df['lab_a'].max():.1f}]")
    print(f"  Lab b  range: [{df['lab_b'].min():.1f}, {df['lab_b'].max():.1f}]")


if __name__ == "__main__":
    main()
