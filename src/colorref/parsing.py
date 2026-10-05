"""LLM output parsing for the ColorRef experiment pipeline.

Extracts hex color codes from raw model text with robust fallbacks.
"""

from __future__ import annotations

import re

from colorref.colors import normalize_hex


# Matches #RRGGBB (anchored to word boundary or start/end)
_HEX_HASH_RE = re.compile(r"#([0-9a-fA-F]{6})\b")

# Bare six-character hex: must be surrounded by non-hex chars (word boundary)
_HEX_BARE_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{6})(?![0-9a-fA-F])")


def extract_hex(text: str) -> tuple[str | None, dict]:
    """Extract the first valid #RRGGBB or RRGGBB-style hex code.

    Returns (normalized_hex_or_None, metadata_dict).

    Metadata keys:
        parse_ok      – bool
        num_candidates – int (number of candidate hex strings found)
        candidates    – list[str] of all candidates (normalized)
        reason        – str | None (failure reason when parse_ok is False)
    """
    if not isinstance(text, str):
        return None, {
            "parse_ok": False,
            "num_candidates": 0,
            "candidates": [],
            "reason": "input is not a string",
        }

    # 1. Prefer explicit #RRGGBB matches
    hash_matches = _HEX_HASH_RE.findall(text)
    candidates: list[str] = [f"#{m.lower()}" for m in hash_matches]

    # 2. If none, look for isolated bare six-char hex
    if not candidates:
        bare_matches = _HEX_BARE_RE.findall(text)
        for m in bare_matches:
            norm = normalize_hex(m)
            if norm is not None:
                candidates.append(norm)

    if not candidates:
        return None, {
            "parse_ok": False,
            "num_candidates": 0,
            "candidates": [],
            "reason": "no hex code found",
        }

    chosen = candidates[0]
    return chosen, {
        "parse_ok": True,
        "num_candidates": len(candidates),
        "candidates": candidates,
        "reason": None,
    }
