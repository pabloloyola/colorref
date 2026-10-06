"""Numeric anomalies must be identified from saved raw responses, not mean ratios."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from colorref.quantifier_study import score_prediction

ROOT = Path(__file__).resolve().parents[1]


def inspector(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "control_inspector", ROOT / "scripts/inspect_quantifier_controls.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(actual):
    condition = {
        "condition_id": "axis_legend:neutral_mid:numeric:lighter:numeric_10",
        "prompt_variant": "axis_legend",
        "base_id": "neutral_mid",
        "condition_kind": "numeric",
        "condition_name": "numeric_10",
        "direction": "lighter",
        "base_lab": [50, 0, 0],
        "expected_lab": [60, 0, 0],
        "requested_numeric_step": 10,
        "prompt": "Increase L by exactly 10 units. Leave a and b unchanged.",
    }
    return {
        **condition,
        **score_prediction(condition, actual),
        "parse_ok": True,
        "raw_response": "LAB({}, {}, {})".format(*actual),
    }


def test_single_numeric_miss_shows_actual_residual_and_original_prompt(monkeypatch):
    module = inspector(monkeypatch)
    missed = row((70, 0, 0))
    misses = module.control_misses([row((60, 0, 0)), missed])
    assert len(misses) == 1
    assert misses[0]["expected_lab"] == [60, 0, 0]
    assert misses[0]["actual_lab"] == [70, 0, 0]
    assert misses[0]["coordinate_residual"] == [10, 0, 0]
    assert misses[0]["prompt"] == missed["prompt"]
    assert misses[0]["raw_response"] == "LAB(70, 0, 0)"


def test_raw_output_and_saved_coordinates_must_agree(monkeypatch):
    module = inspector(monkeypatch)
    saved = row((70, 0, 0))
    saved["raw_response"] = "LAB(60, 0, 0)"
    with pytest.raises(ValueError, match="coordinates disagree"):
        module.control_misses([saved])
    saved["raw_response"] = "unparseable"
    with pytest.raises(ValueError, match="parse status disagrees"):
        module.control_misses([saved])
    saved["parse_ok"] = False
    assert module.control_misses([saved])[0]["actual_lab"] is None
