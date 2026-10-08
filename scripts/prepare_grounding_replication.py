"""Freeze 1,000 balanced descriptions outside the original debug subset; no inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.interface_study import select_examples


def choose(frame, excluded, per_regime=250, seed=113):
    if "example_id" not in excluded.columns:
        raise ValueError("Exclusion subset needs example_id")
    ids = set(excluded["example_id"].astype(str))
    pool = frame.loc[~frame["example_id"].astype(str).isin(ids)].copy()
    examples = select_examples(pool, per_regime, seed)
    assert not ids.intersection(x["example_id"] for x in examples)
    return pd.DataFrame(examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/colornames_taxonomy.parquet")
    parser.add_argument("--exclude", type=Path, default=ROOT / "data/eval_subsets/debug_400.parquet")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/confirmatory/grounding_1000")
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Output directory already exists; preserve the frozen subset")
    source, excluded = pd.read_parquet(args.input), pd.read_parquet(args.exclude)
    selected = choose(source, excluded)
    manifest = {"seed": 113, "examples": len(selected), "examples_per_regime": 250,
                "regime_counts": selected["regime_label"].value_counts().to_dict(),
                "excluded_ids": sorted(excluded["example_id"].astype(str).unique()),
                "input": str(args.input), "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
                "exclude": str(args.exclude), "exclude_sha256": hashlib.sha256(args.exclude.read_bytes()).hexdigest(),
                "selected_ids": selected["example_id"].tolist(),
                "sampling": "equal-regime sample; not corpus-frequency weights"}
    args.out_dir.mkdir(parents=True, exist_ok=False)
    selected.to_parquet(args.out_dir / "examples.parquet", index=False)
    manifest["subset_sha256"] = hashlib.sha256((args.out_dir / "examples.parquet").read_bytes()).hexdigest()
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k not in {"selected_ids", "excluded_ids"}}, indent=2))


if __name__ == "__main__":
    main()
