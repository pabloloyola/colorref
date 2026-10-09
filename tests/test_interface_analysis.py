"""Paired bootstrap units, failure selection, and inference-free saved-run analysis."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from colorref.interface_analysis import analyze, paired_bootstrap, write_analysis
from colorref.interface_study import next_prompt, score_record
from colorref.interface_study_reports import write_reports

ROOT = Path(__file__).resolve().parents[1]


def script(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def saved_run(tmp_path, monkeypatch, fail_legend=False, all_invalid=False):
    runner = script("run_interface_study", monkeypatch)
    cfg = yaml.safe_load(
        (ROOT / "configs/experiments/interface_study_a100_40gb.yaml").read_text()
    )
    cfg["study"]["examples_per_regime"] = 1
    cfg["output"]["run_root"] = str(tmp_path)
    templates = {
        v["id"]: {
            p: (ROOT / v[f"{p}_template_path"]).read_text()
            for p in ("initial", "revision")
        }
        for v in cfg["study"]["variants"]
    }
    regimes = (
        "explicit_grounded",
        "prototype_mediated",
        "compound_associative",
        "abstract_idiosyncratic",
    )
    examples = [
        {
            "example_id": str(i),
            "raw_name": f"gray {i}",
            "hex": "#808080",
            "regime_label": r,
        }
        for i, r in enumerate(regimes)
    ]
    run = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, plan, metadata = runner.load_plan(run)

    class Client:
        def generate(self, prompt, **kwargs):
            failed = all_invalid or (
                fail_legend
                and '"gray 0"' in prompt
                and "CIELAB axis directions" in prompt
            )
            text = (
                "LAB(50, 0 + 10, -10"
                if failed
                else ("#808080" if "#RRGGBB" in prompt else "LAB(50, 0, 0)")
            )
            return SimpleNamespace(
                text=text,
                error=None,
                model_name="fixture",
                provider="mock",
                latency_s=0,
            )

    checkpoints = {}
    runner.run_pending(Client(), cfg, plan, metadata, run, checkpoints)
    write_reports(cfg, plan["tasks"], checkpoints, run)
    return cfg, plan, checkpoints, run


def test_pairing_preserves_covariance_instead_of_resampling_interfaces_separately():
    # Absolute interface errors vary enormously, but their paired difference is constant.
    left = np.array([1, 50, 1000, 4], dtype=float)
    right = left + 2
    regimes = ["explicit_grounded"] * 4
    effect = paired_bootstrap((right - left).reshape(-1, 1), regimes, resamples=100)
    assert effect == [{"n": 4, "mean": 2.0, "low": 2.0, "high": 2.0}]


def test_stratification_preserves_observed_counts_and_pooled_weighting():
    values = [[1], [1], [1], [100]]
    regimes = ["explicit_grounded"] * 3 + ["abstract_idiosyncratic"]
    estimate = paired_bootstrap(values, regimes, resamples=100)[0]
    assert estimate["mean"] == 25.75
    assert estimate["low"] == estimate["high"] == 25.75
    assert paired_bootstrap(values, regimes, 100, 5) == paired_bootstrap(
        values, regimes, 100, 5
    )
    varied = [[0], [10], [20], [30]]
    first = paired_bootstrap(varied, ["explicit_grounded"] * 4, 500, 13)
    assert first == paired_bootstrap(varied, ["explicit_grounded"] * 4, 500, 13)
    assert first[0]["low"] < first[0]["high"]
    with pytest.raises(ValueError, match="finite"):
        paired_bootstrap([[float("nan")]], ["explicit_grounded"], 100)
    assert paired_bootstrap([[3]], ["explicit_grounded"], 100)[0]["low"] is None


def test_failed_triplet_is_excluded_but_other_available_pairs_are_retained(
    tmp_path, monkeypatch
):
    cfg, plan, checkpoints, run = saved_run(tmp_path, monkeypatch, fail_legend=True)
    result = analyze(cfg, plan["tasks"], checkpoints, resamples=100)
    assert result["common_examples"] == 3
    assert all(row["projected_error"]["n"] == 3 for row in result["curves"])
    effect = next(
        x
        for x in result["paired_effects"]
        if x["left"] == "hex"
        and x["right"] == "lab_plain"
        and x["cohort"] == "available_pairs"
    )
    assert effect["n"] == 4
    assert len(result["parse_failures"]) == 1
    assert result["parse_failures"][0]["arithmetic_text"]
    assert len(result["curves"]) == 12
    write_analysis(result, run)
    assert (
        "truncation cannot be confirmed"
        in (run / "reports/interface_analysis.md").read_text()
    )


def test_overshoot_diagnostics_distinguish_lost_close_guesses_from_stationary_states(
    tmp_path, monkeypatch
):
    cfg, plan, checkpoints, _ = saved_run(tmp_path, monkeypatch)
    task = next(x for x in plan["tasks"] if x["variant"] == "hex")
    records = checkpoints[task["slot"]]
    # A valid displayed trajectory: initially exact, then progressively lighter.
    replacement = []
    for text in ("#808080", "#909090", "#b0b0b0", "#e0e0e0"):
        prompt, feedback = next_prompt(task, replacement, cfg, plan["templates"])
        replacement.append(score_record(task, replacement, prompt, feedback, text))
    records[:] = replacement
    result = analyze(cfg, plan["tasks"], checkpoints, resamples=100)
    control = next(x for x in result["control_diagnostics"] if x["variant"] == "hex")
    assert control["initially_converged_then_lost_n"] == 1
    assert control["worsened_n"] == 1
    assert control["zero_movement_revisions_n"] == 9
    assert (
        result["largest_overshoots"][0]["final_best_gap"]
        == replacement[-1]["projected_error_delta_e"]
    )
    assert result["largest_overshoots"][0]["first_best_turn"] == 0


def test_no_complete_common_cases_produces_explicit_missing_estimates(
    tmp_path, monkeypatch
):
    cfg, plan, checkpoints, run = saved_run(tmp_path, monkeypatch, all_invalid=True)
    result = analyze(cfg, plan["tasks"], checkpoints, resamples=100)
    assert result["common_examples"] == 0
    assert all(x["projected_error"]["mean"] is None for x in result["curves"])
    assert all(x["n"] == 0 for x in result["paired_effects"])
    assert len(result["parse_failures"]) == 12
    write_analysis(result, run)


def test_cli_uses_saved_run_only_and_preserves_original_files(tmp_path, monkeypatch):
    _, _, _, run = saved_run(tmp_path, monkeypatch)
    analyzer = script("analyze_interface_study", monkeypatch)
    originals = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("Model loading attempted for CPU reanalysis")

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=forbidden)
    )
    monkeypatch.setattr(
        sys, "argv", ["analysis", "--run", str(run), "--resamples", "100"]
    )
    analyzer.main()
    assert (run / "reports/interface_analysis.md").exists()
    assert (run / "metrics/interface_analysis.json").exists()
    assert all(p.read_bytes() == content for p, content in originals.items())
