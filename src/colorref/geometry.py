"""Behavioral geometry analysis for ColorRef trajectories.

Computes pairwise distance matrices over true LAB colors and model
trajectory representations, then measures alignment via Spearman
correlation and optional kernel alignment.

Spec §17.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Distance matrices
# ---------------------------------------------------------------------------

def pairwise_lab_distances(lab_array: np.ndarray) -> np.ndarray:
    """Return symmetric NxN Euclidean distance matrix for Nx3 LAB array."""
    return squareform(pdist(lab_array, metric="euclidean"))


def upper_triangle(matrix: np.ndarray) -> np.ndarray:
    """Return the upper-triangle values (excluding diagonal) as a 1-D array."""
    idx = np.triu_indices(matrix.shape[0], k=1)
    return matrix[idx]


# ---------------------------------------------------------------------------
# Trajectory representations
# ---------------------------------------------------------------------------

def build_state_trajectory_matrix(
    traj_df: pd.DataFrame,
    example_ids: Sequence[int],
    max_turns: int,
) -> np.ndarray:
    """Build an N × (max_turns * 3) matrix of LAB state trajectories.

    Missing turns are padded with the final valid guess for that example.
    Examples with no valid guesses are filled with zeros.
    """
    rows = []
    for eid in example_ids:
        ex = traj_df[traj_df["example_id"] == eid].sort_values("turn")
        vec = []
        last_valid = np.zeros(3)
        for t in range(max_turns):
            turn_row = ex[ex["turn"] == t]
            if len(turn_row) > 0:
                r = turn_row.iloc[0]
                if pd.notna(r.get("guess_lab_l")) and pd.notna(r.get("guess_lab_a")) and pd.notna(r.get("guess_lab_b")):
                    last_valid = np.array([r["guess_lab_l"], r["guess_lab_a"], r["guess_lab_b"]])
            vec.extend(last_valid.tolist())
        rows.append(vec)
    return np.array(rows, dtype=float)


def build_update_trajectory_matrix(
    traj_df: pd.DataFrame,
    example_ids: Sequence[int],
    max_turns: int,
) -> np.ndarray:
    """Build an N × ((max_turns-1) * 3) matrix of LAB update vectors.

    update[t] = guess[t+1] - guess[t]. Missing entries padded with zeros.
    """
    rows = []
    for eid in example_ids:
        ex = traj_df[traj_df["example_id"] == eid].sort_values("turn")
        guesses: dict[int, np.ndarray] = {}
        for _, r in ex.iterrows():
            t = int(r["turn"])
            if pd.notna(r.get("guess_lab_l")) and pd.notna(r.get("guess_lab_a")) and pd.notna(r.get("guess_lab_b")):
                guesses[t] = np.array([r["guess_lab_l"], r["guess_lab_a"], r["guess_lab_b"]])

        vec = []
        for t in range(max_turns - 1):
            if t in guesses and (t + 1) in guesses:
                update = guesses[t + 1] - guesses[t]
            else:
                update = np.zeros(3)
            vec.extend(update.tolist())
        rows.append(vec)
    return np.array(rows, dtype=float)


# ---------------------------------------------------------------------------
# Spearman alignment
# ---------------------------------------------------------------------------

def spearman_alignment(d1: np.ndarray, d2: np.ndarray) -> tuple[float, float]:
    """Spearman correlation between upper triangles of two distance matrices.

    Returns (rho, p_value).
    """
    u1 = upper_triangle(d1)
    u2 = upper_triangle(d2)
    valid = np.isfinite(u1) & np.isfinite(u2)
    if valid.sum() < 3:
        return float("nan"), float("nan")
    rho, pval = spearmanr(u1[valid], u2[valid])
    return float(rho), float(pval)


# ---------------------------------------------------------------------------
# RBF kernel alignment (optional)
# ---------------------------------------------------------------------------

def _rbf_kernel(dist_matrix: np.ndarray, sigma: float | None = None) -> np.ndarray:
    """Convert distance matrix to RBF kernel using median heuristic for sigma."""
    u = upper_triangle(dist_matrix)
    u = u[np.isfinite(u) & (u > 0)]
    if sigma is None:
        sigma = float(np.median(u)) if len(u) > 0 else 1.0
    if sigma < 1e-12:
        sigma = 1.0
    return np.exp(-(dist_matrix ** 2) / (2 * sigma ** 2))


def _center_kernel(K: np.ndarray) -> np.ndarray:
    n = K.shape[0]
    ones = np.ones((n, n)) / n
    return K - ones @ K - K @ ones + ones @ K @ ones


def kernel_alignment(d1: np.ndarray, d2: np.ndarray) -> float:
    """Normalized kernel alignment (Frobenius inner product of centered RBF kernels)."""
    K1 = _center_kernel(_rbf_kernel(d1))
    K2 = _center_kernel(_rbf_kernel(d2))
    num   = np.sum(K1 * K2)
    denom = np.sqrt(np.sum(K1 * K1) * np.sum(K2 * K2))
    if denom < 1e-12:
        return float("nan")
    return float(num / denom)


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

def compute_geometry_alignment(
    traj_df: pd.DataFrame,
    max_turns: int = 3,
    subsample: int | None = None,
    seed: int = 13,
) -> dict:
    """Compute all geometry alignment metrics for a completed run.

    Parameters
    ----------
    traj_df:
        Full trajectories DataFrame (from trajectories.parquet).
    max_turns:
        Number of turns to consider (including turn 0).
    subsample:
        If set, randomly subsample this many examples (for speed).
    seed:
        Random seed for subsampling.

    Returns
    -------
    dict with keys:
        example_ids, D_true_lab, D_initial_guess, D_final_guess,
        D_traj_state, D_traj_update,
        spearman_true_vs_initial, spearman_true_vs_final,
        spearman_true_vs_state, spearman_true_vs_update,
        kernel_true_vs_initial, kernel_true_vs_final,
        kernel_true_vs_state, kernel_true_vs_update,
        n_examples
    """
    # Get examples that have turn 0 (initial guess)
    valid_ids = sorted(
        traj_df[traj_df["turn"] == 0]["example_id"].unique().tolist()
    )

    if subsample and len(valid_ids) > subsample:
        rng = np.random.default_rng(seed)
        valid_ids = list(rng.choice(valid_ids, size=subsample, replace=False))
        valid_ids = sorted(valid_ids)

    logger.info("Computing geometry for %d examples (max_turns=%d)", len(valid_ids), max_turns)
    n = len(valid_ids)

    # True LAB colors
    true_lab = []
    for eid in valid_ids:
        r = traj_df[traj_df["example_id"] == eid].iloc[0]
        true_lab.append([r["true_lab_l"], r["true_lab_a"], r["true_lab_b"]])
    true_lab = np.array(true_lab, dtype=float)

    # Initial guesses (turn 0)
    init_lab = []
    for eid in valid_ids:
        r = traj_df[(traj_df["example_id"] == eid) & (traj_df["turn"] == 0)].iloc[0]
        if pd.notna(r.get("guess_lab_l")):
            init_lab.append([r["guess_lab_l"], r["guess_lab_a"], r["guess_lab_b"]])
        else:
            init_lab.append([float("nan")] * 3)
    init_lab = np.array(init_lab, dtype=float)

    # Final guesses (last valid turn)
    final_lab = []
    for eid in valid_ids:
        ex = traj_df[traj_df["example_id"] == eid].sort_values("turn")
        last = None
        for _, row in ex.iterrows():
            if pd.notna(row.get("guess_lab_l")):
                last = [row["guess_lab_l"], row["guess_lab_a"], row["guess_lab_b"]]
        final_lab.append(last if last else [float("nan")] * 3)
    final_lab = np.array(final_lab, dtype=float)

    # Trajectory matrices
    state_mat  = build_state_trajectory_matrix(traj_df, valid_ids, max_turns)
    update_mat = build_update_trajectory_matrix(traj_df, valid_ids, max_turns)

    # Distance matrices
    D_true    = pairwise_lab_distances(true_lab)
    D_initial = pairwise_lab_distances(init_lab)
    D_final   = pairwise_lab_distances(final_lab)
    D_state   = squareform(pdist(state_mat,  metric="euclidean"))
    D_update  = squareform(pdist(update_mat, metric="euclidean"))

    # Spearman correlations
    rho_init,   p_init   = spearman_alignment(D_true, D_initial)
    rho_final,  p_final  = spearman_alignment(D_true, D_final)
    rho_state,  p_state  = spearman_alignment(D_true, D_state)
    rho_update, p_update = spearman_alignment(D_true, D_update)

    logger.info(
        "Spearman ρ: init=%.3f  final=%.3f  state=%.3f  update=%.3f",
        rho_init, rho_final, rho_state, rho_update,
    )

    # Kernel alignment
    ka_init   = kernel_alignment(D_true, D_initial)
    ka_final  = kernel_alignment(D_true, D_final)
    ka_state  = kernel_alignment(D_true, D_state)
    ka_update = kernel_alignment(D_true, D_update)

    return {
        "n_examples":               n,
        "max_turns":                max_turns,
        "D_true_lab":               D_true,
        "D_initial_guess":          D_initial,
        "D_final_guess":            D_final,
        "D_traj_state":             D_state,
        "D_traj_update":            D_update,
        "spearman_true_vs_initial": rho_init,
        "spearman_p_initial":       p_init,
        "spearman_true_vs_final":   rho_final,
        "spearman_p_final":         p_final,
        "spearman_true_vs_state":   rho_state,
        "spearman_p_state":         p_state,
        "spearman_true_vs_update":  rho_update,
        "spearman_p_update":        p_update,
        "kernel_true_vs_initial":   ka_init,
        "kernel_true_vs_final":     ka_final,
        "kernel_true_vs_state":     ka_state,
        "kernel_true_vs_update":    ka_update,
    }


def alignment_summary_df(results: dict) -> pd.DataFrame:
    """Convert compute_geometry_alignment results to a tidy DataFrame."""
    rows = []
    for label, rho_key, p_key, ka_key in [
        ("initial_guess", "spearman_true_vs_initial", "spearman_p_initial",  "kernel_true_vs_initial"),
        ("final_guess",   "spearman_true_vs_final",   "spearman_p_final",    "kernel_true_vs_final"),
        ("traj_state",    "spearman_true_vs_state",   "spearman_p_state",    "kernel_true_vs_state"),
        ("traj_update",   "spearman_true_vs_update",  "spearman_p_update",   "kernel_true_vs_update"),
    ]:
        rows.append({
            "representation":      label,
            "spearman_rho":        results[rho_key],
            "spearman_p":          results[p_key],
            "kernel_alignment":    results[ka_key],
            "n_examples":          results["n_examples"],
        })
    return pd.DataFrame(rows)
