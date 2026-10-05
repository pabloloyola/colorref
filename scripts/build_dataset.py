"""
Build the master English color-names dataset.

Usage:
    uv run scripts/build_dataset.py --raw_dir <path_to_raw_colornames_folder>

Inputs (inside raw_dir):
    dataset_colornames_source.json   -- {language: [{name, color (hex)}]}
    colornames_evaluations.json      -- [{description, score, language_match, ...}]

Output:
    data/colornames_en.parquet
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Color conversion (pure numpy, no extra deps)
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#").strip()
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """sRGB (0-255) -> CIELAB (D65 illuminant)."""
    rgb = np.array([r, g, b], dtype=float) / 255.0
    # sRGB gamma expansion
    mask = rgb > 0.04045
    rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
    rgb[~mask] /= 12.92
    # Linear RGB -> XYZ (D65)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = M @ rgb
    # Normalise by D65 white point
    xyz /= np.array([0.95047, 1.00000, 1.08883])
    # XYZ -> Lab
    eps = 0.008856
    mask = xyz > eps
    xyz[mask] = xyz[mask] ** (1.0 / 3.0)
    xyz[~mask] = 7.787 * xyz[~mask] + 16.0 / 116.0
    L = 116.0 * xyz[1] - 16.0
    a = 500.0 * (xyz[0] - xyz[1])
    b_val = 200.0 * (xyz[1] - xyz[2])
    return float(L), float(a), float(b_val)


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """sRGB (0-255) -> HSV (H in [0,360), S and V in [0,1])."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin
    # Hue
    if delta == 0:
        h = 0.0
    elif cmax == rf:
        h = 60.0 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        h = 60.0 * (((bf - rf) / delta) + 2)
    else:
        h = 60.0 * (((rf - gf) / delta) + 4)
    s = 0.0 if cmax == 0 else delta / cmax
    v = cmax
    return float(h), float(s), float(v)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Build master English color-names dataset.")
    p.add_argument(
        "--raw_dir",
        type=Path,
        required=True,
        help="Folder containing dataset_colornames_source.json and colornames_evaluations.json",
    )
    p.add_argument(
        "--out_dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Output directory (default: data/ next to this script's parent)",
    )
    p.add_argument(
        "--score_threshold",
        type=float,
        default=0.75,
        help="Minimum LLM quality score to keep (default: 0.75)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    source_path = args.raw_dir / "dataset_colornames_source.json"
    evals_path = args.raw_dir / "colornames_evaluations.json"

    for p in (source_path, evals_path):
        if not p.exists():
            raise FileNotFoundError(f"Expected file not found: {p}")

    print(f"Loading source: {source_path}")
    with open(source_path) as f:
        source = json.load(f)

    print(f"Loading evaluations: {evals_path}")
    with open(evals_path) as f:
        evals = json.load(f)

    en_entries = source.get("English", [])
    print(f"English source entries: {len(en_entries):,}")
    print(f"Evaluation entries: {len(evals):,}")

    # Build eval lookup by description (name-based join — index alignment is unreliable)
    eval_by_name = {e["description"]: e for e in evals}

    rows = []
    n_no_eval = 0
    n_low_score = 0
    n_bad_hex = 0

    for entry in tqdm(en_entries, desc="Processing"):
        name = entry["name"]
        hex_code = entry["color"]

        ev = eval_by_name.get(name)
        if ev is None:
            n_no_eval += 1
            continue
        if ev["score"] < args.score_threshold:
            n_low_score += 1
            continue

        rgb = hex_to_rgb(hex_code)
        if rgb is None:
            n_bad_hex += 1
            continue

        r, g, b = rgb
        L, a_val, b_val = rgb_to_lab(r, g, b)
        h, s, v = rgb_to_hsv(r, g, b)

        rows.append({
            "name": name,
            "hex": hex_code.lower(),
            "r": r,
            "g": g,
            "b": b,
            "lab_l": round(L, 4),
            "lab_a": round(a_val, 4),
            "lab_b": round(b_val, 4),
            "hsv_h": round(h, 4),
            "hsv_s": round(s, 4),
            "hsv_v": round(v, 4),
            "score": ev["score"],
        })

    print(f"\nDropped — no eval match : {n_no_eval:,}")
    print(f"Dropped — score < {args.score_threshold} : {n_low_score:,}")
    print(f"Dropped — bad hex       : {n_bad_hex:,}")
    print(f"Kept                    : {len(rows):,}")

    df = pd.DataFrame(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "colornames_en.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nSaved to {out_path}")
    print(df.describe().to_string())


if __name__ == "__main__":
    main()
