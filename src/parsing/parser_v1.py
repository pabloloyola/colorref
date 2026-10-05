"""
Parser v1: modifier + head decomposition of English color names.

Structural categories
---------------------
  head_only         single word that is a known color head
  modifier_head     exactly 1 known modifier + 1 known head (last word)
  multi_modifier    2+ known modifiers + 1 known head (last word)
  compound_head     known head but >=1 non-modifier word precedes it
  no_head           no word matches the head lexicon
  empty             name normalizes to empty string

Confidence
----------
  head_only / modifier_head  → 1.0
  multi_modifier             → 0.9
  compound_head              → 0.8 - 0.15 * n_unknown  (floor 0.3)
  no_head                    → 0.1
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    name_norm: str
    words: list[str]
    head: Optional[str]
    modifiers: list[str]
    non_mod_prefixes: list[str]
    candidate_prototype_terms: list[str]   # empty in v1, populated in v2
    category: str
    confidence: float
    parser_version: str = "v1"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ColorNameParserV1:
    VERSION = "v1"

    def __init__(self, heads: set[str], modifiers: set[str]):
        self.heads = heads
        self.modifiers = modifiers

    # ---------------------------------------------------------------- public

    def parse(self, name: str) -> ParseResult:
        norm = self._normalize(name)
        words = norm.split()

        if not words:
            return ParseResult(norm, words, None, [], [], [], "empty", 0.0, self.VERSION)

        head, head_idx = self._find_head(words)
        prefix_words = words[:head_idx] if head_idx is not None else words

        known_mods = [w for w in prefix_words if w in self.modifiers]
        non_mod    = [w for w in prefix_words if w not in self.modifiers]

        category   = self._categorize(head, words, known_mods, non_mod)
        confidence = self._score(category, non_mod)

        return ParseResult(
            name_norm=norm,
            words=words,
            head=head,
            modifiers=known_mods,
            non_mod_prefixes=non_mod,
            candidate_prototype_terms=[],
            category=category,
            confidence=confidence,
            parser_version=self.VERSION,
        )

    # --------------------------------------------------------------- private

    @staticmethod
    def _normalize(name: str) -> str:
        n = name.lower().strip()
        n = re.sub(r"['\"\-]", " ", n)
        n = re.sub(r"[^a-z\s]", "", n)
        n = re.sub(r"\s+", " ", n).strip()
        return n

    def _find_head(self, words: list[str]) -> tuple[Optional[str], Optional[int]]:
        for i in range(len(words) - 1, -1, -1):
            if words[i] in self.heads:
                return words[i], i
        return None, None

    @staticmethod
    def _categorize(head, words, known_mods, non_mod) -> str:
        if head is None:
            return "no_head"
        if len(words) == 1:
            return "head_only"
        if not non_mod and len(known_mods) == 1:
            return "modifier_head"
        if not non_mod and len(known_mods) >= 2:
            return "multi_modifier"
        return "compound_head"

    @staticmethod
    def _score(category: str, non_mod: list[str]) -> float:
        if category in ("head_only", "modifier_head"):
            return 1.0
        if category == "multi_modifier":
            return 0.9
        if category == "compound_head":
            return max(0.3, 0.8 - 0.15 * len(non_mod))
        return 0.1  # no_head / empty
