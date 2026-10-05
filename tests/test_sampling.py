"""Tests for src/colorref/sampling.py."""

from __future__ import annotations

import math
import pandas as pd
import pytest

from colorref.sampling import (
    load_and_validate,
    sample_balanced_by_regime,
    sample_balanced_by_regime_and_bins,
    build_summary_markdown,
    REQUIRED_COLUMNS,
    VALID_REGIMES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(n_per_regime: int = 100, seed: int = 0) -> pd.DataFrame:
    """Build a minimal synthetic taxonomy DataFrame for testing."""
    import numpy as np
    rng = np.random.default_rng(seed)
    rows = []
    for i, regime in enumerate(VALID_REGIMES):
        for j in range(n_per_regime):
            eid = i * n_per_regime + j
            rows.append({
                "example_id":          eid,
                "raw_name":            f"color_{eid}",
                "normalized_name":     f"color_{eid}",
                "hex":                 "#aabbcc",
                "rgb_r": 170, "rgb_g": 187, "rgb_b": 204,
                "lab_l": float(rng.uniform(10, 90)),
                "lab_a": float(rng.uniform(-50, 50)),
                "lab_b": float(rng.uniform(-50, 50)),
                "hsv_h": float(rng.uniform(0, 360)),
                "hsv_s": float(rng.uniform(0, 1)),
                "hsv_v": float(rng.uniform(0, 1)),
                "score": float(rng.uniform(0.5, 1.0)),
                "char_len":            10,
                "word_len":            2,
                "token_count":         3,
                "parse_category":      "simple",
                "parse_confidence":    0.9,
                "parsed_head":         "color",
                "parsed_modifiers":    "[]",
                "candidate_prototype_terms": "[]",
                "explicitness_score":  float(rng.uniform(0, 1)),
                "prototype_score":     float(rng.uniform(0, 1)),
                "rarity_score":        float(rng.uniform(0, 1)),
                "abstraction_score":   float(rng.uniform(0, 1)),
                "regime_label":        regime,
                "regime_confidence":   float(rng.uniform(0.6, 1.0)),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# load_and_validate
# ---------------------------------------------------------------------------

class TestLoadAndValidate:
    def test_missing_column_raises(self, tmp_path):
        df = _make_df(10)
        df = df.drop(columns=["regime_label"])
        p = tmp_path / "bad.parquet"
        df.to_parquet(p)
        with pytest.raises(ValueError, match="regime_label"):
            load_and_validate(p)

    def test_valid_df_loads(self, tmp_path):
        df = _make_df(10)
        p = tmp_path / "good.parquet"
        df.to_parquet(p)
        result = load_and_validate(p)
        assert len(result) == len(df)


# ---------------------------------------------------------------------------
# sample_balanced_by_regime
# ---------------------------------------------------------------------------

class TestSampleBalancedByRegime:
    def setup_method(self):
        self.df = _make_df(n_per_regime=100)

    def test_total_size_exact(self):
        result = sample_balanced_by_regime(self.df, n=400, seed=13)
        assert len(result) == 400

    def test_equal_regime_counts(self):
        result = sample_balanced_by_regime(self.df, n=400, seed=13)
        counts = result["regime_label"].value_counts()
        assert all(counts == 100)

    def test_remainder_distributed(self):
        # Use a large pool so no regime hits its cap
        big_df = _make_df(n_per_regime=300)
        # 401 / 4 = 100 rem 1 → one regime gets 101
        result = sample_balanced_by_regime(big_df, n=401, seed=13)
        assert len(result) == 401
        counts = result["regime_label"].value_counts()
        assert counts.max() == 101
        assert counts.min() == 100

    def test_different_seeds_give_different_samples(self):
        r1 = sample_balanced_by_regime(self.df, n=40, seed=1)
        r2 = sample_balanced_by_regime(self.df, n=40, seed=2)
        assert not r1["example_id"].equals(r2["example_id"])

    def test_same_seed_is_reproducible(self):
        r1 = sample_balanced_by_regime(self.df, n=40, seed=13)
        r2 = sample_balanced_by_regime(self.df, n=40, seed=13)
        assert list(r1["example_id"]) == list(r2["example_id"])

    def test_no_duplicates(self):
        result = sample_balanced_by_regime(self.df, n=400, seed=13)
        assert result["example_id"].nunique() == 400

    def test_min_score_filter(self):
        result = sample_balanced_by_regime(self.df, n=40, seed=13, min_score=0.9)
        # All remaining rows should have score >= 0.9
        assert (result["score"] >= 0.9).all()

    def test_sparse_regime_falls_back(self):
        # Give one regime only 5 rows
        small_df = self.df.copy()
        mask = small_df["regime_label"] == VALID_REGIMES[0]
        small_df = pd.concat([
            small_df[~mask],
            small_df[mask].head(5),
        ])
        # Should not raise, just take all 5 from that regime
        result = sample_balanced_by_regime(small_df, n=400, seed=13)
        assert len(result) > 0

    def test_all_regimes_present(self):
        result = sample_balanced_by_regime(self.df, n=400, seed=13)
        assert set(result["regime_label"].unique()) == set(VALID_REGIMES)


# ---------------------------------------------------------------------------
# sample_balanced_by_regime_and_bins
# ---------------------------------------------------------------------------

class TestSampleBalancedByRegimeAndBins:
    def setup_method(self):
        from colorref.bins import add_bins
        self.df = add_bins(_make_df(n_per_regime=200))

    def test_returns_correct_size(self):
        result = sample_balanced_by_regime_and_bins(self.df, n=400, seed=13)
        assert len(result) == 400

    def test_no_duplicates(self):
        result = sample_balanced_by_regime_and_bins(self.df, n=200, seed=13)
        assert result["example_id"].nunique() == 200

    def test_all_regimes_present(self):
        result = sample_balanced_by_regime_and_bins(self.df, n=400, seed=13)
        assert set(result["regime_label"].unique()) == set(VALID_REGIMES)


# ---------------------------------------------------------------------------
# build_summary_markdown
# ---------------------------------------------------------------------------

class TestBuildSummaryMarkdown:
    def setup_method(self):
        from colorref.bins import add_bins
        self.df = add_bins(_make_df(n_per_regime=25))

    def test_contains_subset_name(self):
        md = build_summary_markdown(self.df, "test_subset", seed=13, source_path="data/test.parquet")
        assert "test_subset" in md

    def test_contains_total_rows(self):
        md = build_summary_markdown(self.df, "test_subset", seed=13, source_path="data/test.parquet")
        assert str(len(self.df)) in md

    def test_contains_regime_table(self):
        md = build_summary_markdown(self.df, "test_subset", seed=13, source_path="data/test.parquet")
        for regime in VALID_REGIMES:
            assert regime in md

    def test_contains_first_20_examples(self):
        md = build_summary_markdown(self.df, "test_subset", seed=13, source_path="data/test.parquet")
        assert "First 20" in md

    def test_returns_string(self):
        md = build_summary_markdown(self.df, "test_subset", seed=13, source_path="data/test.parquet")
        assert isinstance(md, str)
        assert len(md) > 0
