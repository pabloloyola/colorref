"""Tests for src/colorref/bins.py."""

import pandas as pd
import pytest

from colorref.bins import hue_bin, lightness_bin, saturation_bin, value_bin, add_bins


class TestHueBin:
    def test_grayscale_low_saturation(self):
        assert hue_bin(0.0, 0.05) == "grayscale"
        assert hue_bin(180.0, 0.09) == "grayscale"

    def test_red_near_zero(self):
        assert hue_bin(5.0, 0.8) == "red"

    def test_red_near_360(self):
        assert hue_bin(350.0, 0.8) == "red"

    def test_orange(self):
        assert hue_bin(30.0, 0.8) == "orange"

    def test_yellow(self):
        assert hue_bin(60.0, 0.8) == "yellow"

    def test_green(self):
        assert hue_bin(120.0, 0.8) == "green"

    def test_cyan(self):
        assert hue_bin(180.0, 0.8) == "cyan"

    def test_blue(self):
        assert hue_bin(220.0, 0.8) == "blue"

    def test_purple(self):
        assert hue_bin(270.0, 0.8) == "purple"

    def test_magenta(self):
        assert hue_bin(310.0, 0.8) == "magenta"


class TestLightnessBin:
    def test_dark(self):
        assert lightness_bin(0.0) == "dark"
        assert lightness_bin(34.9) == "dark"

    def test_medium(self):
        assert lightness_bin(35.0) == "medium"
        assert lightness_bin(69.9) == "medium"

    def test_light(self):
        assert lightness_bin(70.0) == "light"
        assert lightness_bin(100.0) == "light"


class TestSaturationBin:
    def test_low(self):
        assert saturation_bin(0.0) == "low"
        assert saturation_bin(0.32) == "low"

    def test_medium(self):
        assert saturation_bin(0.33) == "medium"
        assert saturation_bin(0.65) == "medium"

    def test_high(self):
        assert saturation_bin(0.66) == "high"
        assert saturation_bin(1.0) == "high"


class TestValueBin:
    def test_low(self):
        assert value_bin(0.0) == "low"
        assert value_bin(0.32) == "low"

    def test_medium(self):
        assert value_bin(0.33) == "medium"
        assert value_bin(0.65) == "medium"

    def test_high(self):
        assert value_bin(0.66) == "high"
        assert value_bin(1.0) == "high"


class TestAddBins:
    def _make_df(self):
        return pd.DataFrame({
            "hsv_h": [0.0, 120.0, 240.0, 30.0],
            "hsv_s": [0.9, 0.9, 0.9, 0.05],
            "hsv_v": [1.0, 0.5, 0.2, 0.8],
            "lab_l": [20.0, 50.0, 80.0, 65.0],
        })

    def test_columns_added(self):
        df = add_bins(self._make_df())
        for col in ("hue_bin", "lightness_bin", "saturation_bin", "value_bin"):
            assert col in df.columns

    def test_no_mutation(self):
        original = self._make_df()
        result = add_bins(original)
        assert "hue_bin" not in original.columns
        assert "hue_bin" in result.columns

    def test_missing_column_raises(self):
        df = self._make_df().drop(columns=["lab_l"])
        with pytest.raises(ValueError, match="missing columns"):
            add_bins(df)

    def test_grayscale_row(self):
        df = add_bins(self._make_df())
        assert df.iloc[3]["hue_bin"] == "grayscale"

    def test_red_row(self):
        df = add_bins(self._make_df())
        assert df.iloc[0]["hue_bin"] == "red"

    def test_lightness_values(self):
        df = add_bins(self._make_df())
        assert df.iloc[0]["lightness_bin"] == "dark"
        assert df.iloc[1]["lightness_bin"] == "medium"
        assert df.iloc[2]["lightness_bin"] == "light"
