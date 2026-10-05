"""Bootstrap confidence intervals for aggregate experiment metrics."""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import pandas as pd


def bootstrap_mean_ci(
    values: Sequence[float],
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 13,
) -> tuple[float | None, float | None, float | None]:
    """Return (mean, lower, upper) for a percentile bootstrap CI of the mean."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None, None, None

    mean = float(np.mean(arr))
    if arr.size == 1:
        return mean, mean, mean

    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot, dtype=float)
    n = arr.size
    for i in range(n_boot):
        sample = arr[rng.integers(0, n, size=n)]
        boots[i] = float(np.mean(sample))

    alpha = (1.0 - ci) / 2.0
    low, high = np.quantile(boots, [alpha, 1.0 - alpha])
    return mean, float(low), float(high)


def bootstrap_grouped_metrics(
    df: pd.DataFrame,
    group_cols: list[str] | str,
    metric_cols: list[str],
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 13,
) -> pd.DataFrame:
    """Grouped means and percentile bootstrap CIs for selected metric columns."""
    if isinstance(group_cols, str):
        group_cols = [group_cols]

    rows: list[dict] = []
    grouped = df.groupby(group_cols, dropna=False)
    for group_key, grp in grouped:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        row = dict(zip(group_cols, group_key))
        row["n"] = len(grp)

        for col in metric_cols:
            if col not in grp.columns:
                continue
            values = grp[col].dropna().tolist()
            mean, low, high = bootstrap_mean_ci(values, n_boot=n_boot, ci=ci, seed=seed)
            row[f"mean_{col}"] = mean
            pct = int(ci * 100)
            row[f"ci{pct}_low_{col}"] = low
            row[f"ci{pct}_high_{col}"] = high

        rows.append(row)

    return pd.DataFrame(rows)


def add_bootstrap_ci_columns(
    aggregate_df: pd.DataFrame,
    per_example_df: pd.DataFrame,
    group_col: str,
    metric_cols: list[str],
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 13,
) -> pd.DataFrame:
    """Merge bootstrap CI columns onto an existing aggregate table."""
    ci_df = bootstrap_grouped_metrics(
        per_example_df,
        group_cols=group_col,
        metric_cols=metric_cols,
        n_boot=n_boot,
        ci=ci,
        seed=seed,
    )
    if group_col not in aggregate_df.columns:
        return aggregate_df
    merged = aggregate_df.merge(ci_df, on=group_col, how="left", suffixes=("", "_boot"))
    return merged
