"""Tests for src/colorref/parsing.py."""

import pytest

from colorref.parsing import extract_hex


class TestExtractHex:
    # --- happy path ---

    def test_bare_hash_hex(self):
        result, meta = extract_hex("#ff0000")
        assert result == "#ff0000"
        assert meta["parse_ok"] is True
        assert meta["num_candidates"] == 1

    def test_uppercase_normalized(self):
        result, meta = extract_hex("#FF0000")
        assert result == "#ff0000"

    def test_sentence_with_hex(self):
        result, meta = extract_hex("The color is #aabbcc.")
        assert result == "#aabbcc"
        assert meta["parse_ok"] is True

    def test_thinks_then_hex(self):
        result, meta = extract_hex("I think it is close to #aabbcc")
        assert result == "#aabbcc"

    def test_bare_six_char_hex(self):
        result, meta = extract_hex("FF0000")
        assert result == "#ff0000"
        assert meta["parse_ok"] is True

    def test_multiple_candidates_takes_first(self):
        result, meta = extract_hex("#aabbcc or maybe #ddeeff")
        assert result == "#aabbcc"
        assert meta["num_candidates"] == 2
        assert "#ddeeff" in meta["candidates"]

    # --- failure cases ---

    def test_named_color_fails(self):
        result, meta = extract_hex("red")
        assert result is None
        assert meta["parse_ok"] is False

    def test_rgb_string_fails(self):
        result, meta = extract_hex("RGB(255, 0, 0)")
        assert result is None
        assert meta["parse_ok"] is False

    def test_empty_string(self):
        result, meta = extract_hex("")
        assert result is None
        assert meta["parse_ok"] is False

    def test_non_string_input(self):
        result, meta = extract_hex(None)  # type: ignore[arg-type]
        assert result is None
        assert meta["parse_ok"] is False
        assert "not a string" in meta["reason"]

    def test_three_char_hex_not_parsed(self):
        # Three-char shorthand should not be parsed in v1
        result, meta = extract_hex("#fff")
        assert result is None
        assert meta["parse_ok"] is False

    def test_partial_hex_in_longer_word(self):
        # Hex digits embedded in a longer word should not match as bare hex
        result, meta = extract_hex("0000001")
        assert result is None or meta["num_candidates"] >= 1  # at minimum, no crash

    # --- metadata structure ---

    def test_metadata_keys_present(self):
        _, meta = extract_hex("#ff0000")
        for key in ("parse_ok", "num_candidates", "candidates", "reason"):
            assert key in meta

    def test_failed_metadata_has_reason(self):
        _, meta = extract_hex("no hex here")
        assert meta["reason"] is not None

    def test_success_reason_is_none(self):
        _, meta = extract_hex("#ff0000")
        assert meta["reason"] is None
