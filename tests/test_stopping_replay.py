"""Check first-hit stopping, valid prefixes, matching, and original preservation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from colorref.interface_study import REGIMES, VARIANTS
from colorref.stopping_replay import analyze, replay

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from replay_shared_start_stopping import run_analysis  # noqa: E402
from test_shared_start_study import Client, inputs, runner  # noqa: E402


def records(errors):
    return [{"parse_ok": x is not None, "projected_error_delta_e": x} for x in errors]


def start(error):
    return {"projected_error_delta_e": error}


def test_stops_at_initial_state_without_consulting_later_failure():
    assert replay(start(2.38), records([49.4, None]), 3, 5) == {
        "status": "threshold",
        "turn": 0,
        "error": 2.38,
    }


def test_first_hit_is_not_best_state_and_last_turn_saves_no_calls():
    assert replay(start(20), records([4, 1, 12]), 3, 5) == {
        "status": "threshold",
        "turn": 1,
        "error": 4,
    }
    assert replay(start(20), records([8, 6, 5]), 3, 5)["turn"] == 3
    assert replay(start(20), records([8, 7, 6]), 3, 5) == {
        "status": "budget_exhausted",
        "turn": 3,
        "error": 6,
    }


def test_prefix_completion_failure_and_pending_are_distinct():
    assert replay(start(20), records([4, None]), 3, 5)["error"] == 4
    assert replay(start(20), records([4]), 3, 5)["status"] == "threshold"
    assert replay(start(20), records([8, None]), 3, 5)["status"] == "parse_failure"
    assert replay(start(20), records([8]), 3, 5)["status"] == "pending"
    assert replay(start(20), [], 3, 5)["error"] is None


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf")])
def test_invalid_thresholds_are_rejected(threshold):
    with pytest.raises(ValueError, match="positive and finite"):
        replay(start(2), [], 3, threshold)


def analysis_fixture():
    cfg = {"execution": {"max_turns": 3, "convergence_delta_e": 5}}
    tasks = []
    saved = {}
    paths = {"hex": [4, 1, 12], "lab_plain": [8, 6, 5], "lab_axis_legend": [8, 7, 6]}
    for i, regime in enumerate(REGIMES):
        for v in VARIANTS:
            task = {
                "slot": len(tasks),
                "condition_id": f"{v}:{i}",
                "variant": v,
                "example": {
                    "example_id": str(i),
                    "raw_name": "gray",
                    "regime_label": regime,
                    "hex": "#808080",
                    "shared_start_hex": "#404040",
                },
            }
            tasks.append(task)
            saved[task["slot"]] = records(paths[v])
    return cfg, {"tasks": tasks}, saved


def test_exact_counts_paired_differences_and_fixed_cohort_are_preserved():
    cfg, plan, saved = analysis_fixture()
    result = analyze(cfg, plan, saved, resamples=100)
    assert result["common_examples"] == 4
    rows = {r["variant"]: r for r in result["summaries"]}
    assert rows["hex"]["mean_fixed_error"] == 12
    assert rows["hex"]["mean_stop_error"] == 4  # Not the future minimum 1.
    assert rows["hex"]["fixed_calls"] == 12
    assert rows["hex"]["stop_calls"] == 4
    assert rows["hex"]["saved_calls"] == 8
    assert rows["hex"]["converged_then_lost_n"] == 4
    assert rows["lab_plain"]["saved_calls"] == 0
    assert rows["lab_axis_legend"]["mean_stop_error"] == 6
    within = result["within_interface_effects"][0]
    assert within["error_delta"]["mean"] == -8
    assert within["calls_delta"]["mean"] == -2
    assert within["convergence_rate_delta"]["mean"] == 1
    assert len(result["lost_convergence_cases"]) == 4


def test_early_stopping_can_preserve_a_worse_still_converged_error():
    cfg, plan, saved = analysis_fixture()
    for t in plan["tasks"]:
        saved[t["slot"]] = records([4, 2, 1])
    result = analyze(cfg, plan, saved, resamples=100)
    assert all(
        r["error_delta"]["mean"] == 3 for r in result["within_interface_effects"]
    )


def test_later_failure_does_not_inflate_common_policy_accuracy():
    cfg, plan, saved = analysis_fixture()
    saved[0] = records([4, None])
    result = analyze(cfg, plan, saved, resamples=100)
    assert result["common_examples"] == 3
    assert result["games"][0]["stop_status"] == "threshold"
    assert result["games"][0]["stop_error"] == 4
    assert result["available_outcome_counts"][0]["threshold_stops"] == 4
    assert result["available_outcome_counts"][0]["fixed_full"] == 3


def test_empty_cohort_and_explicit_threshold_override():
    cfg, plan, _ = analysis_fixture()
    result = analyze(cfg, plan, {}, threshold=10, resamples=100)
    assert result["threshold_source"] == "explicit_analysis_override"
    assert result["common_examples"] == 0
    assert all(
        r["error_delta"]["mean"] is None for r in result["within_interface_effects"]
    )
    assert all(r["pending"] == 4 for r in result["available_outcome_counts"])


def test_cpu_reanalysis_preserves_inputs_and_original_reports(tmp_path, monkeypatch):
    _, directory, cfg, plan, meta = inputs(tmp_path)
    saved = {}
    runner.run_pending(Client(), cfg, plan, meta, directory, saved)
    original = directory / "reports/shared_start_summary.md"
    original.write_text("unchanged original summary\n")
    with runner.run_lock(directory):
        pass
    before = {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }

    def forbidden(_):
        raise AssertionError("Replay must not load a model")

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=forbidden)
    )
    result = run_analysis(directory, resamples=100)
    assert result["common_examples"] == 4
    assert all((directory / p).read_bytes() == data for p, data in before.items())
    report = (directory / "reports/stopping_replay_summary.md").read_text()
    assert "target-known benchmark" in report
    assert "Primary common fully parsed examples: 4 / 4" in report
    assert (
        json.loads((directory / "metrics/stopping_replay.json").read_text())[
            "threshold_source"
        ]
        == "frozen_config"
    )
