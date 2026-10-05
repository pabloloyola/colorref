"""In-context learning (ICL) context retrieval and prompt rendering.

Supports three retrieval modes (spec §3.4):
  - random        : uniform sample from context pool
  - regime_matched: sample from same regime_label
  - text_similar  : TF-IDF nearest-neighbor retrieval

Contexts are stored as Parquet files with one row per target example
and k context columns (context_0 ... context_{k-1}), each as a JSON string.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context pool helpers
# ---------------------------------------------------------------------------

def build_context_pool(
    taxonomy_path: Path | str,
    eval_subset_path: Path | str | None = None,
) -> pd.DataFrame:
    """Load taxonomy and exclude eval subset example_ids.

    Returns a DataFrame of candidate context examples.
    """
    pool = pd.read_parquet(taxonomy_path)
    if eval_subset_path is not None:
        eval_df = pd.read_parquet(eval_subset_path)
        eval_ids = set(eval_df["example_id"].tolist())
        pool = pool[~pool["example_id"].isin(eval_ids)]
        logger.info("Context pool size after exclusion: %d", len(pool))
    return pool.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Random retrieval (spec §3.4.1)
# ---------------------------------------------------------------------------

def retrieve_random(
    pool: pd.DataFrame,
    k: int,
    seed_offset: int,
    global_seed: int = 13,
    stratify_by_regime: bool = True,
) -> list[dict]:
    """Sample k examples uniformly from pool.

    Seed is deterministic: global_seed + example_id (via seed_offset).
    """
    rng = np.random.default_rng(global_seed + seed_offset)
    if len(pool) < k:
        return pool.to_dict("records")
    if stratify_by_regime and "regime_label" in pool.columns:
        regimes = pool["regime_label"].unique()
        per_regime = max(1, k // len(regimes))
        parts = []
        for regime in regimes:
            sub = pool[pool["regime_label"] == regime]
            n = min(per_regime, len(sub))
            idx = rng.choice(len(sub), size=n, replace=False)
            parts.append(sub.iloc[idx])
        combined = pd.concat(parts).sample(frac=1, random_state=int(global_seed + seed_offset))
        return combined.head(k).to_dict("records")
    idx = rng.choice(len(pool), size=k, replace=False)
    return pool.iloc[idx].to_dict("records")


# ---------------------------------------------------------------------------
# Regime-matched retrieval (spec §3.4.2)
# ---------------------------------------------------------------------------

def retrieve_regime_matched(
    pool: pd.DataFrame,
    k: int,
    target_regime: str,
    seed_offset: int,
    global_seed: int = 13,
) -> list[dict]:
    """Sample k examples from the same regime_label.

    Falls back to random if insufficient examples in regime.
    """
    rng = np.random.default_rng(global_seed + seed_offset)
    regime_pool = pool[pool.get("regime_label", pd.Series()) == target_regime] if "regime_label" in pool.columns else pd.DataFrame()

    if len(regime_pool) >= k:
        idx = rng.choice(len(regime_pool), size=k, replace=False)
        return regime_pool.iloc[idx].to_dict("records")

    # Fallback: random
    logger.debug("Regime %s has < %d examples, falling back to random.", target_regime, k)
    return retrieve_random(pool, k, seed_offset, global_seed, stratify_by_regime=False)


# ---------------------------------------------------------------------------
# Text-similar retrieval (spec §3.4.3)
# ---------------------------------------------------------------------------

def build_tfidf_index(pool: pd.DataFrame, text_col: str = "raw_name") -> Any:
    """Build a TF-IDF index over pool[text_col].

    Returns (vectorizer, matrix).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = pool[text_col].fillna("").tolist()
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=50_000,
        lowercase=True,
    )
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def retrieve_text_similar(
    pool: pd.DataFrame,
    k: int,
    query_text: str,
    query_id: int,
    vectorizer: Any,
    matrix: Any,
) -> list[dict]:
    """Retrieve k nearest neighbors by TF-IDF similarity, excluding query_id."""
    from sklearn.metrics.pairwise import cosine_similarity

    query_vec = vectorizer.transform([query_text])
    sims = cosine_similarity(query_vec, matrix).flatten()

    # Exclude query_id if in pool
    if "example_id" in pool.columns:
        pool_ids = pool["example_id"].values
        for i, pid in enumerate(pool_ids):
            if pid == query_id:
                sims[i] = -1.0

    top_k_idx = np.argsort(sims)[::-1][:k]
    return pool.iloc[top_k_idx].to_dict("records")


# ---------------------------------------------------------------------------
# Context diagnostics
# ---------------------------------------------------------------------------

def compute_context_diagnostics(
    contexts: list[dict],
    target_hex: str,
    target_lab: tuple[float, float, float] | None,
    target_regime: str | None,
    target_hue_bin: str | None,
    target_text: str,
) -> dict[str, float]:
    """Compute context quality diagnostics for spec §3.7."""
    from colorref.colors import color_distance_lab

    lab_dists = []
    same_regime = 0
    same_hue_bin = 0

    for ctx in contexts:
        ctx_lab = _ctx_lab(ctx)
        if ctx_lab and target_lab:
            try:
                lab_dists.append(color_distance_lab(target_lab, ctx_lab))
            except Exception:
                pass

        if target_regime and ctx.get("regime_label") == target_regime:
            same_regime += 1
        if target_hue_bin and ctx.get("hue_bin") == target_hue_bin:
            same_hue_bin += 1

    n = max(len(contexts), 1)
    return {
        "context_mean_lab_distance_to_target": float(np.mean(lab_dists)) if lab_dists else float("nan"),
        "context_min_lab_distance_to_target": float(np.min(lab_dists)) if lab_dists else float("nan"),
        "context_same_regime_rate": same_regime / n,
        "context_same_hue_bin_rate": same_hue_bin / n,
        "context_text_similarity_mean": float("nan"),  # placeholder; set by caller if available
    }


def _ctx_lab(ctx: dict) -> tuple[float, float, float] | None:
    try:
        return (float(ctx["lab_l"]), float(ctx["lab_a"]), float(ctx["lab_b"]))
    except (KeyError, TypeError, ValueError):
        pass
    try:
        hex_c = str(ctx.get("hex", "")).lstrip("#")
        if len(hex_c) == 6:
            r, g, b = int(hex_c[:2], 16), int(hex_c[2:4], 16), int(hex_c[4:], 16)
            from colorref.colors import rgb_to_lab
            return rgb_to_lab(r, g, b)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# ICL prompt rendering
# ---------------------------------------------------------------------------

def render_icl_examples(examples: list[dict], k: int | None = None) -> str:
    """Render k context examples as a numbered list (spec §3.5.1 format)."""
    out = []
    for i, ex in enumerate(examples[:k] if k else examples, start=1):
        raw = str(ex.get("raw_name", ex.get("name", "")))
        hex_c = str(ex.get("hex", "")).strip()
        if not hex_c.startswith("#"):
            hex_c = f"#{hex_c}"
        out.append(f'{i}. Description: "{raw}" -> Hex: {hex_c}')
    return "\n".join(out)


def render_icl_initial_prompt(
    template: str,
    raw_name: str,
    icl_examples_text: str,
) -> str:
    """Insert ICL examples block into the initial prompt template."""
    return (
        template
        .replace("{icl_examples}", icl_examples_text)
        .replace("{raw_name}", raw_name)
    )


# ---------------------------------------------------------------------------
# Build / save context files
# ---------------------------------------------------------------------------

def build_contexts_for_subset(
    eval_subset: pd.DataFrame,
    pool: pd.DataFrame,
    k: int,
    mode: str,
    global_seed: int = 13,
    tfidf_index: tuple | None = None,
) -> pd.DataFrame:
    """Build context retrieval for all eval examples.

    Returns a DataFrame with columns: example_id, raw_name, contexts_json (list of k dicts).
    """
    if mode == "text_similar" and tfidf_index is None:
        logger.info("Building TF-IDF index...")
        tfidf_index = build_tfidf_index(pool)

    # Pre-build regime groups for fast lookup
    regime_groups: dict[str, pd.DataFrame] = {}
    if mode == "regime_matched" and "regime_label" in pool.columns:
        for regime, grp in pool.groupby("regime_label"):
            regime_groups[str(regime)] = grp.reset_index(drop=True)

    pool_array = pool.reset_index(drop=True)

    # For text_similar, batch all queries at once
    if mode == "text_similar":
        return _build_text_similar_batch(
            eval_subset, pool_array, k, tfidf_index, global_seed
        )

    rows = []
    for _, row in eval_subset.iterrows():
        eid = int(row["example_id"])
        raw_name = str(row.get("raw_name", ""))
        regime = str(row.get("regime_label", ""))
        target_lab = None
        try:
            target_lab = (float(row["lab_l"]), float(row["lab_a"]), float(row["lab_b"]))
        except Exception:
            pass

        if mode == "random":
            contexts = _retrieve_random_fast(pool_array, k, seed=global_seed + eid)
        elif mode == "regime_matched":
            contexts = _retrieve_regime_fast(pool_array, regime_groups, k, regime,
                                              seed=global_seed + eid)
        else:
            raise ValueError(f"Unknown retrieval mode: {mode!r}")

        diag = compute_context_diagnostics(
            contexts,
            target_hex=str(row.get("hex", "")),
            target_lab=target_lab,
            target_regime=regime,
            target_hue_bin=str(row.get("hue_bin", "")),
            target_text=raw_name,
        )

        rows.append({
            "example_id": eid,
            "raw_name": raw_name,
            "k_shot": k,
            "retrieval_mode": mode,
            "contexts_json": json.dumps([
                {"raw_name": c.get("raw_name", ""), "hex": c.get("hex", "")}
                for c in contexts
            ]),
            **diag,
        })

    return pd.DataFrame(rows)


def _build_text_similar_batch(
    eval_subset: pd.DataFrame,
    pool: pd.DataFrame,
    k: int,
    tfidf_index: tuple,
    global_seed: int = 13,
) -> pd.DataFrame:
    """Batch cosine similarity for all eval queries at once (fast path)."""
    from sklearn.metrics.pairwise import cosine_similarity as _cossim

    vec, mat = tfidf_index
    pool_ids = pool["example_id"].values if "example_id" in pool.columns else np.arange(len(pool))

    # Vectorize all query texts at once
    query_texts = eval_subset["raw_name"].fillna("").tolist()
    query_vecs = vec.transform(query_texts)  # (n_eval, n_features)

    # Compute all similarities at once: (n_eval, n_pool)
    logger.info("Computing batch cosine similarity: %d queries × %d pool items...",
                len(query_texts), len(pool))
    sim_matrix = _cossim(query_vecs, mat)  # dense (n_eval, n_pool)
    logger.info("Done.")

    rows = []
    for i, (_, row) in enumerate(eval_subset.iterrows()):
        eid = int(row["example_id"])
        sims = sim_matrix[i].copy()

        # Exclude self
        mask = pool_ids == eid
        sims[mask] = -1.0

        top_k_idx = np.argsort(sims)[::-1][:k]
        contexts = pool.iloc[top_k_idx].to_dict("records")

        target_lab = None
        try:
            target_lab = (float(row["lab_l"]), float(row["lab_a"]), float(row["lab_b"]))
        except Exception:
            pass

        diag = compute_context_diagnostics(
            contexts,
            target_hex=str(row.get("hex", "")),
            target_lab=target_lab,
            target_regime=str(row.get("regime_label", "")),
            target_hue_bin=str(row.get("hue_bin", "")),
            target_text=str(row.get("raw_name", "")),
        )
        diag["context_text_similarity_mean"] = float(np.mean(sims[top_k_idx]))

        rows.append({
            "example_id": eid,
            "raw_name": str(row.get("raw_name", "")),
            "k_shot": k,
            "retrieval_mode": "text_similar",
            "contexts_json": json.dumps([
                {"raw_name": c.get("raw_name", ""), "hex": c.get("hex", "")}
                for c in contexts
            ]),
            **diag,
        })

    return pd.DataFrame(rows)


def _retrieve_random_fast(
    pool: pd.DataFrame,
    k: int,
    seed: int,
) -> list[dict]:
    """Fast random sampling — avoid per-row re-grouping."""
    rng = np.random.default_rng(seed)
    n = len(pool)
    if n <= k:
        return pool.to_dict("records")
    idx = rng.choice(n, size=k, replace=False)
    return pool.iloc[idx].to_dict("records")


def _retrieve_regime_fast(
    pool: pd.DataFrame,
    regime_groups: dict[str, pd.DataFrame],
    k: int,
    target_regime: str,
    seed: int,
) -> list[dict]:
    """Fast regime-matched retrieval using pre-built groups."""
    rng = np.random.default_rng(seed)
    grp = regime_groups.get(target_regime)
    if grp is not None and len(grp) >= k:
        idx = rng.choice(len(grp), size=k, replace=False)
        return grp.iloc[idx].to_dict("records")
    # Fallback to random
    return _retrieve_random_fast(pool, k, seed)
