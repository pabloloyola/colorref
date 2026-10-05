"""
Regime labeler: assigns one of 4 regimes to each color name.

Regimes
-------
  explicit_grounded      Direct basic color head + recognised modifiers.
                         Prototypical: "dark green", "pale sky blue"

  prototype_mediated     Object / material / nature anchor, no basic color head
                         required. Prototypical: "mustard yellow", "ocean blue",
                         "blueberry", "deep forest"

  compound_associative   Multiple words with *some* anchor but not fully parsed.
                         Prototypical: "garden's darkest night", "summer storm grey"

  abstract_idiosyncratic No recoverable anchor. Affective / idiosyncratic.
                         Prototypical: "abandoned hope", "whisper of tuesday"

Decision logic (applied in order, first match wins)
----------------------------------------------------
  1. explicit_grounded   if category in {modifier_head, multi_modifier, head_only}
                         OR (compound_head AND explicitness >= 0.65)
  2. prototype_mediated  if category in {prototype_head, modifier_prototype}
                         OR (compound_prototype AND prototype >= 0.55)
                         OR (compound_head AND prototype >= 0.40 AND explicitness < 0.65)
  3. compound_associative if category in {compound_head, compound_prototype}
                          AND abstraction < 0.70
  4. abstract_idiosyncratic  everything else

Regime confidence
-----------------
  Score derived from the margin between the winning signal and alternatives.
  Ranges in [0.3, 1.0].
"""

from __future__ import annotations

import pandas as pd


REGIMES = [
    "explicit_grounded",
    "prototype_mediated",
    "compound_associative",
    "abstract_idiosyncratic",
]

_EXPLICIT_CATS = {"modifier_head", "multi_modifier", "head_only"}
_PROTO_CATS    = {"prototype_head", "modifier_prototype"}
_COMPOUND_CATS = {"compound_head", "compound_prototype"}


def assign_regimes(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    Returns (regime_label, regime_confidence) Series aligned to df.index.

    df must contain:
      parse_category, explicitness_score, prototype_score, abstraction_score
    """
    cat   = df["parse_category"]
    expl  = df["explicitness_score"]
    proto = df["prototype_score"]
    abst  = df["abstraction_score"]

    labels     = pd.Series("abstract_idiosyncratic", index=df.index, dtype="object")
    confidence = pd.Series(0.5, index=df.index)

    # ---- Rule 4 baseline (already set above) ----

    # ---- Rule 3: compound_associative ----
    r3 = cat.isin(_COMPOUND_CATS) & (abst < 0.70)
    labels[r3]     = "compound_associative"
    confidence[r3] = (0.70 - abst[r3]).clip(0.30, 0.70) + 0.30

    # ---- Rule 2: prototype_mediated ----
    r2 = (
        cat.isin(_PROTO_CATS)
        | (cat == "compound_prototype") & (proto >= 0.55)
        | cat.isin(_COMPOUND_CATS) & (proto >= 0.40) & (expl < 0.65)
    )
    labels[r2]     = "prototype_mediated"
    confidence[r2] = proto[r2].clip(0.50, 0.95)

    # ---- Rule 1: explicit_grounded (highest priority, applied last) ----
    r1 = cat.isin(_EXPLICIT_CATS) | (cat == "compound_head") & (expl >= 0.65)
    labels[r1]     = "explicit_grounded"
    confidence[r1] = expl[r1].clip(0.65, 1.00)

    return labels, confidence.clip(0.30, 1.00)
