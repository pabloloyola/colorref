"""Color binning utilities for the ColorRef experiment pipeline.

Adds hue_bin, lightness_bin, saturation_bin, and value_bin columns
to a pandas DataFrame that already contains HSV and LAB coordinates.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Individual bin functions (operate on scalar values)
# ---------------------------------------------------------------------------

def hue_bin(hsv_h: float, hsv_s: float) -> str:
    """Return a hue category name.

    Uses 'grayscale' when HSV saturation < 0.10 (hue is unstable there).
    """
    if hsv_s < 0.10:
        return "grayscale"
    h = hsv_h % 360.0
    if h < 15 or h >= 345:
        return "red"
    if h < 45:
        return "orange"
    if h < 75:
        return "yellow"
    if h < 165:
        return "green"
    if h < 195:
        return "cyan"
    if h < 255:
        return "blue"
    if h < 285:
        return "purple"
    return "magenta"


def lightness_bin(lab_l: float) -> str:
    """Bin LAB L into dark / medium / light."""
    if lab_l < 35:
        return "dark"
    if lab_l < 70:
        return "medium"
    return "light"


def saturation_bin(hsv_s: float) -> str:
    """Bin HSV saturation into low / medium / high."""
    if hsv_s < 0.33:
        return "low"
    if hsv_s < 0.66:
        return "medium"
    return "high"


def value_bin(hsv_v: float) -> str:
    """Bin HSV value into low / medium / high."""
    if hsv_v < 0.33:
        return "low"
    if hsv_v < 0.66:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# DataFrame-level helper
# ---------------------------------------------------------------------------

def add_bins(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with hue_bin, lightness_bin, saturation_bin, value_bin added.

    Expects columns: hsv_h, hsv_s, hsv_v, lab_l.
    """
    required = {"hsv_h", "hsv_s", "hsv_v", "lab_l"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"add_bins: missing columns {sorted(missing)}")

    df = df.copy()
    df["hue_bin"] = [
        hue_bin(h, s) for h, s in zip(df["hsv_h"], df["hsv_s"])
    ]
    df["lightness_bin"] = df["lab_l"].map(lightness_bin)
    df["saturation_bin"] = df["hsv_s"].map(saturation_bin)
    df["value_bin"] = df["hsv_v"].map(value_bin)
    return df
