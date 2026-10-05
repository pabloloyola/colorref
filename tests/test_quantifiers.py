"""Tests for quantifier calibration specifications and metrics."""

from colorref.prompts import render_quantifier_calibration
from colorref.quantifiers import (
    make_instruction,
    measure_update,
    pairwise_monotonicity,
)


def test_instruction_phrasing() -> None:
    assert make_instruction("baseline", "more_blue") == "Make it more blue."
    assert make_instruction("a_little", "more_blue") == "Make it a little more blue."
    assert make_instruction("somewhat", "lighter") == "Make it somewhat lighter."
    assert make_instruction("much", "darker") == "Make it much darker."


def test_measure_update_uses_requested_sign() -> None:
    metrics = measure_update((50.0, 0.0, 0.0), (60.0, 2.0, 3.0), "more_blue")
    assert metrics["requested_signed_step"] == -3.0
    assert metrics["update_l"] == 10.0
    assert metrics["off_axis_drift"] == 10.198039027185569
    assert metrics["direction_followed"] == 0.0

    metrics = measure_update((50.0, 0.0, 0.0), (60.0, 2.0, -3.0), "more_blue")
    assert metrics["requested_signed_step"] == 3.0
    assert metrics["direction_followed"] == 1.0


def test_monotonicity_counts_ordered_pairs() -> None:
    rows = [
        {"base_id": "x", "direction": "lighter", "quantifier": "a_little", "quantifier_rank": 1, "parse_ok": True, "requested_signed_step": 1.0},
        {"base_id": "x", "direction": "lighter", "quantifier": "somewhat", "quantifier_rank": 2, "parse_ok": True, "requested_signed_step": 2.0},
        {"base_id": "x", "direction": "lighter", "quantifier": "much", "quantifier_rank": 3, "parse_ok": True, "requested_signed_step": 2.0},
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 3
    assert result["monotonicity_ordered_pairs"] == 3
    assert result["monotonicity_rate"] == 1.0


def test_monotonicity_ignores_parse_failures() -> None:
    rows = [
        {"base_id": "x", "direction": "lighter", "quantifier": "a_little", "quantifier_rank": 1, "parse_ok": True, "requested_signed_step": 1.0},
        {"base_id": "x", "direction": "lighter", "quantifier": "somewhat", "quantifier_rank": 2, "parse_ok": False, "requested_signed_step": None},
        {"base_id": "x", "direction": "lighter", "quantifier": "much", "quantifier_rank": 3, "parse_ok": True, "requested_signed_step": 0.5},
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 1
    assert result["monotonicity_ordered_pairs"] == 0
    assert result["monotonicity_rate"] == 0.0


def test_prompt_renderer() -> None:
    rendered = render_quantifier_calibration(
        "Current: {base_lab}; Instruction: {instruction}",
        "LAB(50.00, 0.00, 0.00)",
        "Make it a little lighter.",
    )
    assert rendered == (
        "Current: LAB(50.00, 0.00, 0.00); "
        "Instruction: Make it a little lighter."
    )

def test_archived_baseline_is_not_an_ordinal_quantifier() -> None:
    rows = [
        {"base_id": "x", "direction": "lighter", "quantifier": name,
         "quantifier_rank": rank, "parse_ok": True, "requested_signed_step": step}
        for name, rank, step in [
            ("baseline", 0, 50.0), ("a_little", 1, 5.0),
            ("somewhat", 2, 5.0), ("much", 3, 10.0),
        ]
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 3
    assert result["monotonicity_rate"] == 1.0
    assert result["monotonicity_strict_pairs"] == 2
    assert result["monotonicity_tied_pairs"] == 1
    assert result["strict_monotonicity_rate"] == 2 / 3


def test_monotonicity_keeps_starting_colors_separate() -> None:
    rows = [
        {"base_id": base, "direction": "lighter", "quantifier": name,
         "parse_ok": True, "requested_signed_step": step}
        for base, name, step in [
            ("x", "a_little", 10.0), ("x", "much", 5.0),
            ("y", "a_little", 1.0), ("y", "much", 3.0),
        ]
    ]
    result = pairwise_monotonicity(rows)
    assert result["monotonicity_comparisons"] == 2
    assert result["monotonicity_ordered_pairs"] == 1


def test_saved_report_runs_without_model_loading(tmp_path, monkeypatch) -> None:
    import importlib.util
    import json
    import sys
    from pathlib import Path

    import yaml

    script = Path(__file__).resolve().parents[1] / "scripts" / "run_quantifier_calibration.py"
    spec = importlib.util.spec_from_file_location("quantifier_runner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "colorref.llm_clients", None)
    monkeypatch.setitem(sys.modules, "colorref.games", None)

    (tmp_path / "raw_outputs").mkdir()
    (tmp_path / "reports").mkdir()
    cfg = {"model": {"alias": "test", "model_name": "test", "provider": "test"},
           "calibration": {"quantifiers": ["baseline", "a_little", "somewhat", "much"]}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    rows = [
        {"run_id": "saved", "base_id": "x", "direction": "lighter",
         "quantifier": name, "quantifier_rank": rank, "parse_ok": True,
         "requested_signed_step": step, "direction_followed": float(step > 0),
         "off_axis_drift": 0.0, "raw_response": "LAB(50, 0, 0)",
         "lab_projection_delta_e": 0.0}
        for name, rank, step in [
            ("baseline", 0, 20.0), ("a_little", 1, 0.0),
            ("somewhat", 2, 0.0), ("much", 3, -1.0),
        ]
    ]
    (tmp_path / "raw_outputs" / "responses.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    monkeypatch.setattr(sys, "argv", ["runner", "--report-only", str(tmp_path)])
    module.main()
    report = (tmp_path / "reports" / "quantifier_summary.md").read_text()
    assert "Ordered pairs: 1 / 3" in report
    assert "Strictly increasing pairs: 0 / 3" in report
    assert "Tied pairs: 1" in report
    assert "Zero-step N | Wrong-direction N" in report
    assert "| lighter | much | 1 | -1.000 | 0 | 1 |" in report
    assert "## Steps by starting color and direction" in report
