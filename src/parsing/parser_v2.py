"""
Parser v2: extends v1 with prototype-term heads and suffix normalization.

New over v1
-----------
- prototype_terms lexicon: object/material/nature terms that can serve as heads
  when no basic color head is present (e.g. "mustard", "sky", "ocean")
- -ish suffix normalization: "greenish" → head "green"
- Plural stripping: "blues" → head "blue"
- candidate_prototype_terms: all prototype terms found anywhere in the name
  (populated even when a basic head exists, used downstream for taxonomy)

Additional categories (over v1)
--------------------------------
  prototype_head           single prototype term (no basic color head)
  modifier_prototype       modifier(s) + prototype head
  compound_prototype       prototype head but with unrecognized prefix words
"""

from __future__ import annotations

from .parser_v1 import ColorNameParserV1, ParseResult


# ---------------------------------------------------------------------------
# Parser v2
# ---------------------------------------------------------------------------

class ColorNameParserV2(ColorNameParserV1):
    VERSION = "v2"

    def __init__(
        self,
        heads: set[str],
        modifiers: set[str],
        prototype_terms: set[str],
        ish_exceptions: dict[str, str],
        plural_strip: bool = True,
        plural_min_len: int = 4,
    ):
        super().__init__(heads=heads, modifiers=modifiers)
        self.prototype_terms = prototype_terms
        self.ish_exceptions  = ish_exceptions
        self.plural_strip    = plural_strip
        self.plural_min_len  = plural_min_len

        # Build fast ish lookup from known heads + prototype terms
        self._ish_lookup: dict[str, str] = dict(ish_exceptions)
        for term in heads | prototype_terms:
            # "green" -> "greenish"
            candidate = term + "ish"
            if candidate not in self._ish_lookup:
                self._ish_lookup[candidate] = term
            # "blue" -> "blueish" (keep "e"), also "bluish" (drop "e")
            if term.endswith("e"):
                self._ish_lookup[term[:-1] + "ish"] = term

    # ---------------------------------------------------------------- public

    def parse(self, name: str) -> ParseResult:
        norm  = self._normalize(name)
        words = norm.split()

        if not words:
            return ParseResult(norm, words, None, [], [], [], "empty", 0.0, self.VERSION)

        # Normalize each word with suffix rules before lookup
        norm_words = [self._normalize_word(w) for w in words]
        # Build word→normalised mapping for display (keep original where unchanged)
        display_words = [
            nw if nw != w else w
            for w, nw in zip(words, norm_words)
        ]

        # Detect prototype terms in the full (un-normalized) word list
        proto_found = [w for w in norm_words if w in self.prototype_terms]

        # 1. Try basic color head first (rightmost)
        head, head_idx = self._find_head(norm_words)

        if head is not None:
            # Basic head found — same logic as v1, just with normalized words
            prefix_words = norm_words[:head_idx]
            known_mods   = [w for w in prefix_words if w in self.modifiers]
            non_mod      = [w for w in prefix_words if w not in self.modifiers]
            category     = self._categorize(head, norm_words, known_mods, non_mod)
            confidence   = self._score(category, non_mod)

        else:
            # 2. No basic head — look for prototype head (rightmost)
            proto_head, proto_idx = self._find_prototype_head(norm_words)

            if proto_head is not None:
                head = proto_head
                prefix_words = norm_words[:proto_idx]
                known_mods   = [w for w in prefix_words if w in self.modifiers]
                non_mod      = [w for w in prefix_words if w not in self.modifiers]
                category, confidence = self._categorize_prototype(
                    norm_words, known_mods, non_mod
                )
            else:
                # Still no head after expansion
                head       = None
                known_mods = []
                non_mod    = words  # all unrecognized
                category   = "no_head"
                confidence = 0.1

        return ParseResult(
            name_norm=norm,
            words=display_words,
            head=head,
            modifiers=known_mods,
            non_mod_prefixes=non_mod,
            candidate_prototype_terms=proto_found,
            category=category,
            confidence=confidence,
            parser_version=self.VERSION,
        )

    # --------------------------------------------------------------- private

    def _normalize_word(self, word: str) -> str:
        """Apply suffix normalization to a single word."""
        # 1. Explicit ish exceptions / ish lookup
        if word in self._ish_lookup:
            return self._ish_lookup[word]
        # 2. Plural stripping
        if (
            self.plural_strip
            and word.endswith("s")
            and len(word) >= self.plural_min_len
        ):
            stem = word[:-1]
            if stem in self.heads or stem in self.prototype_terms:
                return stem
        return word

    def _find_prototype_head(self, words: list[str]) -> tuple[str | None, int | None]:
        for i in range(len(words) - 1, -1, -1):
            if words[i] in self.prototype_terms:
                return words[i], i
        return None, None

    @staticmethod
    def _categorize_prototype(
        words: list[str],
        known_mods: list[str],
        non_mod: list[str],
    ) -> tuple[str, float]:
        if len(words) == 1:
            return "prototype_head", 0.85
        if not non_mod and len(known_mods) >= 1:
            return "modifier_prototype", 0.75
        return "compound_prototype", max(0.25, 0.6 - 0.1 * len(non_mod))
