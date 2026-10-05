"""Color conversion utilities for the ColorRef experiment pipeline.

All conversions use sRGB with D65 white point for LAB.
Primary distance metric is Euclidean ΔE in CIELAB (ΔE76).
"""

from __future__ import annotations

import math
import re


# ---------------------------------------------------------------------------
# Hex ↔ RGB
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def normalize_hex(value: str) -> str | None:
    """Return lowercase #rrggbb if valid; otherwise None."""
    if not isinstance(value, str):
        return None
    m = _HEX_RE.match(value.strip())
    if m is None:
        return None
    return "#" + m.group(1).lower()


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #rrggbb to integer RGB tuple.

    Raises ValueError for invalid input.
    """
    norm = normalize_hex(hex_color)
    if norm is None:
        raise ValueError(f"Invalid hex color: {hex_color!r}")
    h = norm.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert integer RGB tuple to #rrggbb."""
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# RGB ↔ LAB  (D65 white point, sRGB gamma)
# ---------------------------------------------------------------------------

# D65 reference white in XYZ
_D65_X = 95.047
_D65_Y = 100.000
_D65_Z = 108.883


def _srgb_to_linear(c: float) -> float:
    """Inverse sRGB gamma (channel in [0, 1])."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    """sRGB gamma (channel in [0, 1])."""
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _f_lab(t: float) -> float:
    delta = 6.0 / 29.0
    if t > delta**3:
        return t ** (1.0 / 3.0)
    return t / (3 * delta**2) + 4.0 / 29.0


def _f_lab_inv(t: float) -> float:
    delta = 6.0 / 29.0
    if t > delta:
        return t**3
    return 3 * delta**2 * (t - 4.0 / 29.0)


def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert sRGB 0-255 to CIELAB using D65 white point."""
    rl = _srgb_to_linear(r / 255.0)
    gl = _srgb_to_linear(g / 255.0)
    bl = _srgb_to_linear(b / 255.0)

    # Linear sRGB → XYZ (D65)
    x = (0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl) * 100.0
    y = (0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl) * 100.0
    z = (0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl) * 100.0

    fx = _f_lab(x / _D65_X)
    fy = _f_lab(y / _D65_Y)
    fz = _f_lab(z / _D65_Z)

    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return L, a, b_val


def lab_to_rgb(l: float, a: float, b: float) -> tuple[int, int, int]:
    """Convert CIELAB to clipped sRGB 0-255."""
    fy = (l + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    x = _f_lab_inv(fx) * _D65_X
    y = _f_lab_inv(fy) * _D65_Y
    z = _f_lab_inv(fz) * _D65_Z

    x /= 100.0
    y /= 100.0
    z /= 100.0

    # XYZ → linear sRGB
    rl =  3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    gl = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl =  0.0556434 * x - 0.2040259 * y + 1.0572252 * z

    def to_uint8(c: float) -> int:
        c = _linear_to_srgb(max(0.0, min(1.0, c)))
        return int(round(max(0.0, min(255.0, c * 255.0))))

    return to_uint8(rl), to_uint8(gl), to_uint8(bl)


# ---------------------------------------------------------------------------
# RGB → HSV
# ---------------------------------------------------------------------------

def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to HSV: H in [0, 360), S/V in [0, 1]."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    # Value
    v = cmax

    # Saturation
    s = 0.0 if cmax == 0.0 else delta / cmax

    # Hue
    if delta == 0.0:
        h = 0.0
    elif cmax == rf:
        h = 60.0 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        h = 60.0 * (((bf - rf) / delta) + 2)
    else:
        h = 60.0 * (((rf - gf) / delta) + 4)

    if h < 0:
        h += 360.0

    return h, s, v


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------

def color_distance_lab(
    c1: tuple[float, float, float],
    c2: tuple[float, float, float],
) -> float:
    """Euclidean LAB distance (ΔE76). Primary v1 distance metric."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
