"""Tests for bootstrap CI utilities."""

import pytest

from colorref.stats import bootstrap_mean_ci, bootstrap_grouped_metrics
import pandas as pd


class TestBootstrapMeanCi:
    def test_returns_interval(self):
        values = [10.0, 12.0, 11.0, 13.0, 9.0]
        mean, low, high = bootstrap_mean_ci(values, n_boot=500, seed=13)
        assert mean == pytest.approx(11.0)
        assert low <= mean <= high

    def test_empty(self):
        assert bootstrap_mean_ci([]) == (None, None, None)


class TestBootstrapGrouped:
    def test_grouped_columns(self):
        df = pd.DataFrame({
            "teacher_type": ["a", "a", "b", "b"],
            "final_error_lab": [10.0, 12.0, 20.0, 22.0],
        })
        out = bootstrap_grouped_metrics(
            df, group_cols="teacher_type", metric_cols=["final_error_lab"], n_boot=200, seed=1
        )
        assert len(out) == 2
        assert "mean_final_error_lab" in out.columns
