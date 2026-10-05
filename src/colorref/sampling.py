"""Evaluation subset construction for the ColorRef experiment pipeline.

Builds balanced evaluation subsets from the full taxonomy parquet,
stratified by regime_label with an optional color-bin balancing pass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import pandas as pd

from colorref.bins import add_bins

logger = logging.getLogger(__name__)

# Columns that must be present in the input dataset (spec §1.1)
REQUIRED_COLUMNS: list[str] = [
    "example_id", "raw_name", "normalized_name",
    "hex", "rgb_r", "rgb_g", "rgb_b",
    "lab_l", "lab_a", "lab_b",
    "hsv_h", "hsv_s", "hsv_v",
    "score", "char_len", "word_len", "token_count",
    "parse_category", "parse_confidence",
    "parsed_head", "parsed_modifiers", "candidate_prototype_terms",
    "explicitness_score", "prototype_score", "rarity_score",
    "abstraction_score", "regime_label", "regime_confidence",
]

VALID_REGIMES: list[str] = [
    "explicit_grounded",
    "prototype_mediated",
    "compound_associative",
    "abstract_idiosyncratic",
]


# ---------------------------------------------------------------------------
# Dataset loading and validation
# ---------------------------------------------------------------------------

def load_and_validate(path: str | Path) -> pd.DataFrame:
    """Load the taxonomy parquet and fail early if required columns are missing."""
    df = pd.read_parquet(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Input dataset is missing required columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )
    logger.info("Loaded %d rows from %s", len(df), path)
    return df


# ---------------------------------------------------------------------------
# Regime-balanced sampling
# ---------------------------------------------------------------------------

def sample_balanced_by_regime(
    df: pd.DataFrame,
    n: int,
    seed: int,
    min_score: float = 0.0,
    min_regime_confidence: float = 0.0,
    regimes: list[str] | None = None,
) -> pd.DataFrame:
    """Sample n rows stratified equally across regime_label.

    Parameters
    ----------
    df:
        Full (or pre-filtered) taxonomy DataFrame.
    n:
        Total number of rows to sample.
    seed:
        Fixed random seed for reproducibility.
    min_score:
        Drop rows below this quality score before sampling.
    min_regime_confidence:
        Drop rows below this regime confidence before sampling.
    regimes:
        Regime labels to use. Defaults to VALID_REGIMES.

    Returns
    -------
    Shuffled DataFrame of exactly n rows (or fewer if the data is too sparse).
    """
    regimes = regimes or VALID_REGIMES
    n_regimes = len(regimes)

    # --- filter ---
    pool = df.copy()
    if min_score > 0:
        pool = pool[pool["score"] >= min_score]
    if min_regime_confidence > 0:
        pool = pool[pool["regime_confidence"] >= min_regime_confidence]
    pool = pool[pool["regime_label"].isin(regimes)]
    pool = pool.sort_values("example_id").reset_index(drop=True)

    # --- per-regime quota ---
    # Distribute remainder to regimes sorted alphabetically
    base = n // n_regimes
    remainder = n % n_regimes
    sorted_regimes = sorted(regimes)
    quota: dict[str, int] = {r: base for r in regimes}
    for i in range(remainder):
        quota[sorted_regimes[i]] += 1

    # --- sample each regime ---
    parts: list[pd.DataFrame] = []
    for regime, q in quota.items():
        regime_pool = pool[pool["regime_label"] == regime]
        if len(regime_pool) < q:
            logger.warning(
                "Regime %r has only %d rows but quota is %d; taking all.",
                regime, len(regime_pool), q,
            )
            q = len(regime_pool)
        sampled = regime_pool.sample(n=q, random_state=seed, replace=False)
        parts.append(sampled)
        logger.info("  %s: sampled %d / %d", regime, q, len(regime_pool))

    result = pd.concat(parts, ignore_index=True)
    result = result.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    logger.info("Total sampled: %d", len(result))
    return result


# ---------------------------------------------------------------------------
# Color-bin balancing (optional)
# ---------------------------------------------------------------------------

def sample_balanced_by_regime_and_bins(
    df: pd.DataFrame,
    n: int,
    seed: int,
    min_score: float = 0.0,
    min_regime_confidence: float = 0.0,
    stratify_cols: Sequence[str] = ("regime_label", "hue_bin", "lightness_bin", "saturation_bin"),
) -> pd.DataFrame:
    """Attempt approximate balance across regime and color bins.

    Falls back to regime-only sampling per regime when bins are too sparse.
    """
    regimes = VALID_REGIMES
    n_regimes = len(regimes)
    base = n // n_regimes
    remainder = n % n_regimes
    sorted_regimes = sorted(regimes)
    quota: dict[str, int] = {r: base for r in regimes}
    for i in range(remainder):
        quota[sorted_regimes[i]] += 1

    pool = df.copy()
    if min_score > 0:
        pool = pool[pool["score"] >= min_score]
    if min_regime_confidence > 0:
        pool = pool[pool["regime_confidence"] >= min_regime_confidence]
    pool = pool[pool["regime_label"].isin(regimes)]
    pool = pool.sort_values("example_id").reset_index(drop=True)

    bin_cols = [c for c in stratify_cols if c != "regime_label"]

    parts: list[pd.DataFrame] = []
    for regime, q in quota.items():
        regime_pool = pool[pool["regime_label"] == regime]
        try:
            sampled = _bin_stratified_sample(regime_pool, q, seed, bin_cols)
        except Exception as exc:
            logger.warning(
                "Bin-balanced sampling failed for %r (%s); falling back to uniform.", regime, exc
            )
            sampled = regime_pool.sample(n=min(q, len(regime_pool)), random_state=seed)
        parts.append(sampled)
        logger.info("  %s: sampled %d / %d (bin-balanced)", regime, len(sampled), len(regime_pool))

    result = pd.concat(parts, ignore_index=True)
    result = result.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return result


def _bin_stratified_sample(
    df: pd.DataFrame,
    n: int,
    seed: int,
    bin_cols: Sequence[str],
) -> pd.DataFrame:
    """Sample approximately n rows with roughly equal representation across bin groups."""
    groups = df.groupby(list(bin_cols), observed=True)
    n_groups = groups.ngroups
    if n_groups == 0 or n == 0:
        return df.sample(n=min(n, len(df)), random_state=seed)

    per_group = max(1, n // n_groups)
    parts: list[pd.DataFrame] = []
    for _, grp in groups:
        take = min(per_group, len(grp))
        parts.append(grp.sample(n=take, random_state=seed))

    result = pd.concat(parts, ignore_index=True)
    if len(result) < n and len(df) > len(result):
        # top-up from the remainder
        used_ids = set(result["example_id"])
        rest = df[~df["example_id"].isin(used_ids)]
        need = min(n - len(result), len(rest))
        if need > 0:
            result = pd.concat(
                [result, rest.sample(n=need, random_state=seed)], ignore_index=True
            )
    elif len(result) > n:
        result = result.sample(n=n, random_state=seed)

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def build_summary_markdown(
    df: pd.DataFrame,
    subset_name: str,
    seed: int,
    source_path: str | Path,
) -> str:
    """Generate a human-readable markdown summary of a subset."""
    lines: list[str] = []
    lines.append(f"# Subset summary: {subset_name}\n")
    lines.append(f"- **Source:** `{source_path}`")
    lines.append(f"- **Seed:** {seed}")
    lines.append(f"- **Total rows:** {len(df)}\n")

    lines.append("## Counts by regime\n")
    regime_counts = df["regime_label"].value_counts().sort_index()
    lines.append("| Regime | Count |")
    lines.append("|---|---:|")
    for regime, count in regime_counts.items():
        lines.append(f"| {regime} | {count} |")
    lines.append("")

    if "hue_bin" in df.columns:
        lines.append("## Counts by hue bin\n")
        hue_counts = df["hue_bin"].value_counts().sort_index()
        lines.append("| Hue bin | Count |")
        lines.append("|---|---:|")
        for hue, count in hue_counts.items():
            lines.append(f"| {hue} | {count} |")
        lines.append("")

    if "lightness_bin" in df.columns:
        lines.append("## Counts by lightness bin\n")
        light_counts = df["lightness_bin"].value_counts().sort_index()
        lines.append("| Lightness bin | Count |")
        lines.append("|---|---:|")
        for lb, count in light_counts.items():
            lines.append(f"| {lb} | {count} |")
        lines.append("")

    if "saturation_bin" in df.columns:
        lines.append("## Counts by saturation bin\n")
        sat_counts = df["saturation_bin"].value_counts().sort_index()
        lines.append("| Saturation bin | Count |")
        lines.append("|---|---:|")
        for sb, count in sat_counts.items():
            lines.append(f"| {sb} | {count} |")
        lines.append("")

    lines.append("## Score statistics\n")
    lines.append(f"- Mean score: {df['score'].mean():.4f}")
    lines.append(f"- Median score: {df['score'].median():.4f}")
    if "abstraction_score" in df.columns:
        lines.append(f"- Mean abstraction score: {df['abstraction_score'].mean():.4f}")
        lines.append(f"- Median abstraction score: {df['abstraction_score'].median():.4f}")
    lines.append("")

    lines.append("## First 20 sampled examples\n")
    lines.append("| example_id | raw_name | hex | regime_label |")
    lines.append("|---:|---|---|---|")
    for _, row in df.head(20).iterrows():
        name = str(row["raw_name"]).replace("|", "\\|")
        lines.append(f"| {row['example_id']} | {name} | `{row['hex']}` | {row['regime_label']} |")
    lines.append("")

    return "\n".join(lines)
