"""
Component scores for regime taxonomy (Stage 3).

Scores are all in [0, 1].

explicitness_score
    How directly the name uses a canonical color head with recognised modifiers.
    High → modifier_head / multi_modifier. Low → no_head.

prototype_score
    How strongly a prototype / object / material term anchors the name.
    High → prototype_head / modifier_prototype.

rarity_score
    How unusual the words are relative to the full corpus.
    Computed from corpus-internal word frequency percentile.

abstraction_score
    Derived: how much of the name lacks any strong anchor.
    = 1 - (0.6 * explicitness + 0.4 * prototype)
"""

from __future__ import annotations

import math
from collections import Counter

import pandas as pd


# ---------------------------------------------------------------------------
# Explicitness
# ---------------------------------------------------------------------------

_EXPLICIT_CATS = {"modifier_head", "multi_modifier", "head_only"}
_PROTO_CATS    = {"prototype_head", "modifier_prototype"}


def compute_explicitness(df: pd.DataFrame) -> pd.Series:
    cat  = df["parse_category"]
    conf = df["parse_confidence"].fillna(0.0)

    scores = pd.Series(0.0, index=df.index)
    scores[cat.isin(_EXPLICIT_CATS)]                               = 1.0
    scores[(cat == "compound_head") & (conf >= 0.7)]               = conf[(cat == "compound_head") & (conf >= 0.7)]
    scores[(cat == "compound_head") & (conf < 0.7)]                = conf[(cat == "compound_head") & (conf < 0.7)] * 0.8
    scores[cat.isin(_PROTO_CATS)]                                  = 0.35
    scores[cat == "compound_prototype"]                            = 0.20
    # no_head stays 0.0
    return scores.clip(0.0, 1.0)


# ---------------------------------------------------------------------------
# Prototype score
# ---------------------------------------------------------------------------

def compute_prototype(df: pd.DataFrame) -> pd.Series:
    cat        = df["parse_category"]
    proto_col  = df["candidate_prototype_terms"].fillna("")
    n_proto    = proto_col.str.split("|").apply(lambda x: sum(1 for t in x if t))

    scores = pd.Series(0.05, index=df.index)
    scores[cat == "prototype_head"]                    = 0.95
    scores[cat == "modifier_prototype"]                = 0.85
    scores[cat == "compound_prototype"]                = 0.65
    # basic head present but prototype terms also found
    has_proto  = n_proto > 0
    basic_cats = cat.isin(_EXPLICIT_CATS | {"compound_head"})
    scores[basic_cats & has_proto] = (0.35 + 0.10 * n_proto[basic_cats & has_proto].clip(upper=2))
    return scores.clip(0.0, 1.0)


# ---------------------------------------------------------------------------
# Rarity score
# ---------------------------------------------------------------------------

def compute_rarity(df: pd.DataFrame) -> pd.Series:
    """
    Rarity = mean inverse-frequency-percentile of the words in the name.

    Steps:
      1. Count each word across all normalized names.
      2. Rank words by frequency (low rank = rare).
      3. For each name, compute mean percentile rank of its words.
         A word that never appeared elsewhere scores 1.0;
         the most common word scores 0.0.
    """
    all_words: list[str] = []
    for name in df["normalized_name"]:
        all_words.extend(str(name).split())

    freq = Counter(all_words)
    total_unique = len(freq)
    if total_unique == 0:
        return pd.Series(0.5, index=df.index)

    # map word → rarity in [0,1]: hapax legomena → ~1.0, most common → ~0.0
    max_count = max(freq.values())
    # log-scaled rarity: rarity(w) = 1 - log(count(w)+1) / log(max_count+1)
    log_max = math.log(max_count + 1)
    rarity_map: dict[str, float] = {
        w: 1.0 - math.log(c + 1) / log_max for w, c in freq.items()
    }

    scores = []
    for name in df["normalized_name"]:
        words = str(name).split()
        if not words:
            scores.append(0.5)
        else:
            scores.append(sum(rarity_map.get(w, 1.0) for w in words) / len(words))

    return pd.Series(scores, index=df.index).clip(0.0, 1.0)


# ---------------------------------------------------------------------------
# Abstraction score (derived)
# ---------------------------------------------------------------------------

def compute_abstraction(
    explicitness: pd.Series,
    prototype: pd.Series,
) -> pd.Series:
    return (1.0 - (0.6 * explicitness + 0.4 * prototype)).clip(0.0, 1.0)


# ---------------------------------------------------------------------------
# Convenience: compute all four at once
# ---------------------------------------------------------------------------

def compute_all_scores(df: pd.DataFrame) -> pd.DataFrame:
    expl  = compute_explicitness(df)
    proto = compute_prototype(df)
    rarity = compute_rarity(df)
    abst  = compute_abstraction(expl, proto)
    return pd.DataFrame({
        "explicitness_score": expl,
        "prototype_score":    proto,
        "rarity_score":       rarity,
        "abstraction_score":  abst,
    }, index=df.index)
