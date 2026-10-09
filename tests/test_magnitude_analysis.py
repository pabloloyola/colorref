"""Check paired subgroup weights, numeric tails and read-only CPU analysis."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from colorref.magnitude_analysis import analyze, numeric_audit, report
from colorref.magnitude_control import evaluation_tasks, fit_mapping, score
from colorref.magnitude_reports import analyze as primary_analyze
from tests.test_magnitude_control import answer, calibrate, inputs, runner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_magnitude_control import run_analysis  # noqa: E402


def data(tmp_path):
    cfg, plan = inputs(tmp_path)
    calibration = calibrate(plan)
    mapping = fit_mapping(cfg, plan, calibration)
    tasks = evaluation_tasks(cfg, plan, mapping)
    bundle = {"mapping": mapping, "evaluation_tasks": tasks}
    rows = {
        t["condition_id"]: score(t, answer(t["prompt"]))
        for t in tasks
        if t["status"] == "generate"
    }
    return cfg, plan, calibration, bundle, rows


def test_primary_mean_and_cluster_interval_preserved(tmp_path):
    cfg, plan, calibration, bundle, rows = data(tmp_path)
    result = analyze(cfg, plan, bundle, rows)
    primary = primary_analyze(
        cfg, plan, calibration, bundle["mapping"], bundle["evaluation_tasks"], rows
    )
    overall = result["global"]
    assert overall["common_cases"] == primary["common_triplets"]
    for key in ("cases", "starting_colors", "mean", "low", "high"):
        assert overall["calibrated_minus_bare"][key] == pytest.approx(
            primary["effects"][0][key]
        )
    assert (
        overall["wins"] + overall["ties"] + overall["losses"] == overall["common_cases"]
    )
    assert overall["common_starting_colors"] <= cfg["study"]["evaluation_colors"]


def test_partitions_weights_and_leave_one_color_out(tmp_path):
    cfg, plan, _, bundle, rows = data(tmp_path)
    result = analyze(cfg, plan, bundle, rows)
    total = result["global"]["common_cases"]
    overall = result["global"]["calibrated_minus_bare"]["mean"]
    for key in ("by_direction", "by_distance", "by_direction_distance", "by_start"):
        assert sum(r["planned_cases"] for r in result[key]) == len(
            plan["evaluation_cases"]
        )
        assert sum(r["common_cases"] for r in result[key]) == total
        pooled = (
            sum(
                r["calibrated_minus_bare"]["mean"] * r["common_cases"]
                for r in result[key]
                if r["common_cases"]
            )
            / total
        )
        assert pooled == pytest.approx(overall)
    assert len(result["by_direction_distance"]) == 18
    assert len(result["leave_one_start_out"]) == 3
    for omission in result["leave_one_start_out"]:
        own = next(
            r for r in result["by_start"] if r["base_id"] == omission["omitted_base_id"]
        )
        assert omission["remaining_cases"] == total - own["common_cases"]
        expected = (
            overall * total - own["calibrated_minus_bare"]["mean"] * own["common_cases"]
        ) / omission["remaining_cases"]
        assert omission["mean_error_delta"] == pytest.approx(expected)


def test_failed_numeric_keeps_available_natural_pair(tmp_path):
    cfg, plan, _, bundle, rows = data(tmp_path)
    task = next(t for t in bundle["evaluation_tasks"] if t["arm"] == "numeric")
    rows[task["condition_id"]] = score(task, "bad")
    result = analyze(cfg, plan, bundle, rows)
    assert result["global"]["common_cases"] == len(plan["evaluation_cases"]) - 1
    assert result["available_pair"]["cases"] == len(plan["evaluation_cases"])
    assert result["numeric"]["parse_failures"] == 1
    assert (
        sum(r["arms"]["numeric"]["parsed"] for r in result["by_direction"])
        == len(plan["evaluation_cases"]) - 1
    )


def test_numeric_tail_counts_preserve_raw_miss():
    tasks, rows = [], {}
    for index, error in enumerate((0.0, 0.005, 0.5, 39.0)):
        key = str(index)
        tasks.append({"condition_id": key, "arm": "numeric", "status": "generate"})
        rows[key] = {
            "condition_id": key,
            "parse_ok": True,
            "base_id": "test",
            "direction": "more_red",
            "requested_distance": 6,
            "start": {"lab": [69.245395932, -43.698223054, 10.326235732]},
            "expected_numeric_lab": [69.245396, -37.939764, 10.326236],
            "native_lab": [69.245396, -37.939764 + error, 10.326236],
            "metrics": {
                "numeric_native_execution_error": error,
                "numeric_display_execution_error": error,
                "projected_target_error": error,
            },
            "projection_delta_e": 0.1,
            "prompt": "exact request",
            "raw_response": "raw retained",
            "generation": {"finish_reason": "eos", "generated_tokens": 34},
        }
    result = numeric_audit(tasks, rows)
    assert result["exact_within_0_01"] == 2
    assert result["within_1"] == 3 and result["over_1"] == 1
    assert result["native_error_distribution"]["mean"] == pytest.approx(39.505 / 4)
    assert result["native_error_distribution"]["median"] == pytest.approx(0.2525)
    assert result["misses"][0]["requested_axis_residual"] == pytest.approx(39)
    assert result["misses"][0]["other_coordinate_residual_norm"] == 0
    assert result["misses"][0]["raw_response"] == "raw retained"
    assert result["largest_error_share_of_total"] == pytest.approx(39 / 39.505)


def test_empty_partial_and_single_start_denominators(tmp_path):
    cfg, plan, _, bundle, rows = data(tmp_path)
    empty = analyze(cfg, plan, None, {})
    assert empty["global"]["common_cases"] == 0
    assert empty["global"]["calibrated_minus_bare"]["mean"] is None
    assert empty["numeric"]["native_error_distribution"]["max"] is None
    report(empty, "empty")
    pending = analyze(cfg, plan, bundle, {})
    assert pending["global"]["arms"]["bare"]["pending"] == len(plan["evaluation_cases"])
    base = bundle["evaluation_tasks"][0]["base_id"]
    partial = analyze(
        cfg, plan, bundle, {k: r for k, r in rows.items() if r["base_id"] == base}
    )
    assert partial["global"]["common_starting_colors"] == 1
    assert partial["global"]["calibrated_minus_bare"]["low"] is None
    assert partial["leave_one_start_out"][0]["mean_error_delta"] is None


def test_phrase_diagnostics_do_not_refit_mapping(tmp_path):
    cfg, plan, _, bundle, rows = data(tmp_path)
    untouched = copy.deepcopy(bundle)
    result = analyze(cfg, plan, bundle, rows)
    matched = [r for r in rows.values() if r["arm"] == "calibrated"]
    expected = sum(
        abs(r["calibrated_median"] - r["axis_residual"]) for r in matched
    ) / len(matched)
    assert result["global"]["calibrated_median_target_gap"]["mean"] == pytest.approx(
        expected
    )
    assert bundle == untouched


def test_cpu_integration_preserves_primary_and_validates_raw(tmp_path, monkeypatch):
    cfg, plan, calibration, _, _ = data(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture"))
    cfg, plan, metadata = runner.load_plan(directory)
    for task in plan["calibration_tasks"]:
        row = {**calibration[task["condition_id"]], "run_id": metadata["run_id"]}
        calibration[task["condition_id"]] = row
        runner.write_json(runner.checkpoint_path(directory, task), row)
    bundle = runner.load_controller(
        directory, cfg, plan, calibration, allow_create=True
    )
    rows = {}
    for task in bundle["evaluation_tasks"]:
        if task["status"] == "generate":
            row = {**score(task, answer(task["prompt"])), "run_id": metadata["run_id"]}
            rows[task["condition_id"]] = row
            runner.write_json(runner.checkpoint_path(directory, task), row)
    runner.write_reports(directory, cfg, plan, calibration, bundle, rows)
    paths = [
        directory / "config.yaml",
        directory / "metadata.json",
        *directory.glob("inputs/*.json"),
        *directory.glob("raw_outputs/*/*.json"),
        directory / "reports/magnitude_summary.md",
        directory / "metrics/magnitude_analysis.json",
    ]
    before = {p: p.read_bytes() for p in paths}

    def forbidden(_):
        raise AssertionError("CPU audit cannot load a model")

    monkeypatch.setattr("colorref.llm_clients.build_client", forbidden)
    result = run_analysis(directory)
    assert result["global"]["common_cases"] == len(plan["evaluation_cases"])
    assert all(p.read_bytes() == content for p, content in before.items())
    assert (directory / "reports/magnitude_breakdown.md").exists()
    assert json.loads((directory / "metrics/magnitude_breakdown.json").read_text())[
        "global"
    ]["common_cases"] == len(plan["evaluation_cases"])
    task = bundle["evaluation_tasks"][0]
    path = runner.checkpoint_path(directory, task)
    bad = json.loads(path.read_text())
    bad["metrics"]["projected_target_error"] += 1
    runner.write_json(path, bad)
    with pytest.raises(ValueError, match="Checkpoint"):
        run_analysis(directory)
