"""CPU-only recorded-name inventory; not human agreement or semantic scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from colorref.colors import hex_to_rgb, normalize_hex, rgb_to_lab  # noqa: E402


def inventory(frame):
    name_col = next((c for c in ("raw_name", "name") if c in frame), None)
    color_col = next((c for c in ("hex", "color") if c in frame), None)
    if name_col is None or color_col is None:
        raise ValueError("Expected raw_name/name and hex/color columns")
    names_ok = frame[name_col].map(lambda x: isinstance(x, str) and bool(x.strip()))
    colors = frame[color_col].map(normalize_hex)
    valid = names_ok & colors.notna()
    data = pd.DataFrame({"raw": frame.loc[valid, name_col], "hex": colors[valid]})
    data["normalized"] = data["raw"].map(lambda x: " ".join(x.lower().split()))
    result = {
        "rows": len(frame), "valid_name_color_rows": len(data),
        "invalid_name_rows": int((~names_ok).sum()),
        "invalid_color_rows": int(colors.isna().sum()),
        "duplicate_exact_name_color_rows_beyond_first": int(data.duplicated(["raw", "hex"]).sum()),
        "groupings": {},
        "limits": [
            "Repeated targets measure recorded multiplicity, not human agreement.",
            "Normalization uses lowercasing and collapsed whitespace, not punctuation removal.",
            "Dispersion weights unique HEX colors equally, not votes or duplicate rows.",
            "Centroid dispersion is descriptive, not a semantic truth target.",
            "Source files are read only; invalid rows are counted separately.",
        ],
    }
    multiple_names = set()
    for key in ("raw", "normalized"):
        groups = data.groupby(key, sort=True).agg(rows=("hex", "size"), unique_colors=("hex", "nunique"), raw_forms=("raw", "nunique"))
        multiple = groups["unique_colors"] > 1
        if key == "normalized":
            multiple_names = set(groups.index[multiple])
        result["groupings"][key] = {
            "distinct_names": len(groups),
            "repeated_name_groups": int((groups["rows"] > 1).sum()),
            "multiple_color_groups": int(multiple.sum()),
            "rows_in_multiple_color_groups": int(groups.loc[multiple, "rows"].sum()),
            "groups_with_multiple_raw_forms": int((groups["raw_forms"] > 1).sum()),
        }
    raw_colors = data.groupby("raw")["hex"].nunique()
    details = []
    for name, group in data[data["normalized"].isin(multiple_names)].groupby("normalized", sort=True):
        unique = sorted(group["hex"].unique())
        if len(unique) < 2:
            continue
        labs = np.array([rgb_to_lab(*hex_to_rgb(h)) for h in unique])
        forms = sorted(group["raw"].unique())
        details.append({
            "normalized_name": name, "raw_forms": forms, "rows": len(group),
            "unique_colors": len(unique),
            "has_exact_raw_name_with_multiple_colors": bool((raw_colors.loc[forms] > 1).any()),
            "unique_color_rms_delta_e_to_centroid": float(np.sqrt(np.mean(np.sum((labs - labs.mean(axis=0)) ** 2, axis=1)))),
            "recorded_hex_colors": unique,
        })
    result["multiple_target_groups"] = details
    if "score" in frame:
        score = pd.to_numeric(frame["score"], errors="coerce")
        finite = score.notna() & np.isfinite(score)
        result["score_boundary"] = {
            "finite_score_rows": int(finite.sum()),
            "score_equal_0_75": int((score[finite] == 0.75).sum()),
            "score_at_least_0_75": int((score[finite] >= 0.75).sum()),
            "score_greater_than_0_75": int((score[finite] > 0.75).sum()),
            "interpretation": "Quality scores are not target-agreement judgments.",
        }
    if "regime_label" in frame:
        result["rows_by_regime"] = {str(k): int(v) for k, v in frame["regime_label"].value_counts(dropna=False).items()}
    return result


def evaluation_inventory(entries):
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("description"), str) for e in entries):
        raise ValueError("Expected evaluation list with string description fields")
    names = pd.Series([e["description"] for e in entries], dtype="object")
    counts = names.value_counts()
    repeated = {n for n, count in counts.items() if count > 1}
    scores = {}
    for row in entries:
        if row["description"] in repeated:
            scores.setdefault(row["description"], set()).add(json.dumps(row.get("score"), sort_keys=True))
    return {
        "rows": len(entries), "distinct_exact_descriptions": len(counts),
        "repeated_exact_description_groups": len(repeated),
        "duplicate_description_rows_beyond_first": int(names.duplicated().sum()),
        "repeated_descriptions_with_distinct_scores": sum(len(v) > 1 for v in scores.values()),
        "field_names": sorted({k for e in entries for k in e}),
        "interpretation": "Fields require review; this inventory does not certify agreement data.",
    }


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--evaluations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.input] + ([args.evaluations] if args.evaluations else [])
    if args.output.resolve() in {p.resolve() for p in inputs}:
        parser.error("Output must differ from every input")
    if args.output.exists():
        parser.error("Output already exists; choose a new report path")
    if args.input.suffix == ".parquet":
        frame = pd.read_parquet(args.input)
    elif args.input.suffix == ".json":
        source = json.loads(args.input.read_text())
        if not isinstance(source, dict) or not isinstance(source.get("English"), list):
            raise ValueError("Expected source JSON with an English list")
        frame = pd.DataFrame(source["English"], columns=["name", "color"]) if not source["English"] else pd.DataFrame(source["English"])
    else:
        parser.error("Input must be .parquet or raw source .json")
    result = inventory(frame)
    result["input"] = {"path": str(args.input), "sha256": digest(args.input)}
    if args.evaluations:
        result["evaluations"] = evaluation_inventory(json.loads(args.evaluations.read_text()))
        result["evaluations"]["input"] = {"path": str(args.evaluations), "sha256": digest(args.evaluations)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "multiple_target_groups"}, indent=2))
    print(f"Detailed groups saved to {args.output}")


if __name__ == "__main__":
    main()
