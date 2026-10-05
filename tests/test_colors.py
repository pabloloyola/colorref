"""Tests for src/colorref/colors.py."""

import math
import pytest

from colorref.colors import (
    normalize_hex,
    hex_to_rgb,
    rgb_to_hex,
    rgb_to_lab,
    lab_to_rgb,
    rgb_to_hsv,
    color_distance_lab,
)


# ---------------------------------------------------------------------------
# normalize_hex
# ---------------------------------------------------------------------------

class TestNormalizeHex:
    def test_valid_with_hash(self):
        assert normalize_hex("#FF0000") == "#ff0000"

    def test_valid_without_hash(self):
        assert normalize_hex("aabbcc") == "#aabbcc"

    def test_lowercase_passthrough(self):
        assert normalize_hex("#aabbcc") == "#aabbcc"

    def test_mixed_case(self):
        assert normalize_hex("#AbCdEf") == "#abcdef"

    def test_invalid_too_short(self):
        assert normalize_hex("#fff") is None

    def test_invalid_three_char(self):
        assert normalize_hex("fff") is None

    def test_invalid_non_hex(self):
        assert normalize_hex("#gghhii") is None

    def test_invalid_non_string(self):
        assert normalize_hex(123) is None  # type: ignore[arg-type]

    def test_whitespace_stripped(self):
        assert normalize_hex("  #ff0000  ") == "#ff0000"


# ---------------------------------------------------------------------------
# hex_to_rgb
# ---------------------------------------------------------------------------

class TestHexToRgb:
    def test_red(self):
        assert hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            hex_to_rgb("nothex")


# ---------------------------------------------------------------------------
# rgb_to_hex
# ---------------------------------------------------------------------------

class TestRgbToHex:
    def test_round_trip(self):
        for r, g, b in [(0, 0, 0), (255, 255, 255), (128, 64, 192)]:
            assert hex_to_rgb(rgb_to_hex(r, g, b)) == (r, g, b)

    def test_format(self):
        assert rgb_to_hex(255, 0, 0) == "#ff0000"


# ---------------------------------------------------------------------------
# rgb_to_lab — sanity checks for known colors
# ---------------------------------------------------------------------------

class TestRgbToLab:
    def _approx(self, got, expected, tol=2.0):
        for g, e in zip(got, expected):
            assert abs(g - e) < tol, f"got {got}, expected {expected}"

    def test_black(self):
        L, a, b = rgb_to_lab(0, 0, 0)
        assert abs(L) < 1.0
        assert abs(a) < 1.0
        assert abs(b) < 1.0

    def test_white(self):
        L, a, b = rgb_to_lab(255, 255, 255)
        assert abs(L - 100.0) < 1.0
        assert abs(a) < 2.0
        assert abs(b) < 2.0

    def test_red(self):
        # sRGB red → LAB ≈ (53.2, 80.1, 67.2)
        L, a, b = rgb_to_lab(255, 0, 0)
        assert 50 < L < 57
        assert a > 70
        assert b > 55

    def test_green(self):
        # sRGB lime green → LAB ≈ (87.7, -86.2, 83.2)
        L, a, b = rgb_to_lab(0, 255, 0)
        assert 85 < L < 92
        assert a < -80
        assert b > 75

    def test_blue(self):
        # sRGB blue → LAB ≈ (32.3, 79.2, -107.9)
        L, a, b = rgb_to_lab(0, 0, 255)
        assert 28 < L < 38
        assert a > 60
        assert b < -100


# ---------------------------------------------------------------------------
# lab_to_rgb — clipping behavior
# ---------------------------------------------------------------------------

class TestLabToRgb:
    def test_black_round_trip(self):
        lab = rgb_to_lab(0, 0, 0)
        r, g, b = lab_to_rgb(*lab)
        assert (r, g, b) == (0, 0, 0)

    def test_white_round_trip(self):
        lab = rgb_to_lab(255, 255, 255)
        r, g, b = lab_to_rgb(*lab)
        assert (r, g, b) == (255, 255, 255)

    def test_mid_color_round_trip(self):
        for rgb in [(128, 64, 200), (10, 200, 100), (200, 50, 50)]:
            lab = rgb_to_lab(*rgb)
            got = lab_to_rgb(*lab)
            for g, e in zip(got, rgb):
                assert abs(g - e) <= 2, f"round-trip failed: {rgb} → {lab} → {got}"

    def test_out_of_gamut_clips(self):
        # Extreme LAB values outside sRGB gamut must return valid 0-255 values
        r, g, b = lab_to_rgb(50, 150, 150)
        for v in (r, g, b):
            assert 0 <= v <= 255


# ---------------------------------------------------------------------------
# rgb_to_hsv
# ---------------------------------------------------------------------------

class TestRgbToHsv:
    def test_red_hue(self):
        h, s, v = rgb_to_hsv(255, 0, 0)
        assert abs(h - 0.0) < 1.0
        assert abs(s - 1.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_green_hue(self):
        h, s, v = rgb_to_hsv(0, 255, 0)
        assert abs(h - 120.0) < 1.0

    def test_blue_hue(self):
        h, s, v = rgb_to_hsv(0, 0, 255)
        assert abs(h - 240.0) < 1.0

    def test_white_saturation(self):
        h, s, v = rgb_to_hsv(255, 255, 255)
        assert abs(s) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_black_value(self):
        h, s, v = rgb_to_hsv(0, 0, 0)
        assert abs(v) < 0.01

    def test_hue_in_range(self):
        for r, g, b in [(255, 128, 0), (0, 128, 255), (128, 0, 255)]:
            h, s, v = rgb_to_hsv(r, g, b)
            assert 0.0 <= h < 360.0
            assert 0.0 <= s <= 1.0
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# color_distance_lab
# ---------------------------------------------------------------------------

class TestColorDistanceLab:
    def test_same_color(self):
        c = (50.0, 10.0, -20.0)
        assert color_distance_lab(c, c) == 0.0

    def test_known_distance(self):
        c1 = (0.0, 0.0, 0.0)
        c2 = (3.0, 4.0, 0.0)
        assert abs(color_distance_lab(c1, c2) - 5.0) < 1e-9

    def test_black_white(self):
        black = rgb_to_lab(0, 0, 0)
        white = rgb_to_lab(255, 255, 255)
        d = color_distance_lab(black, white)
        assert d > 90.0  # L goes from ~0 to ~100
