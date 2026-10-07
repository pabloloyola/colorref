"""Frozen splits, controller independence, CPU lifecycle and cluster uncertainty."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from colorref.colors import color_distance_lab
from colorref.magnitude_control import (
    ARMS,
    build_plan,
    choose_phrase,
    evaluation_tasks,
    fit_mapping,
    score,
)
from colorref.magnitude_reports import analyze, cluster_effect
from colorref.quantifiers import DIRECTION_SPECS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "magnitude_runner", ROOT / "scripts/run_magnitude_control.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def inputs(tmp_path):
    cfg = yaml.safe_load(
        (
            ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml"
        ).read_text()
    )
    cfg["output"]["run_root"] = str(tmp_path)
    cfg["study"]["calibration_colors"] = 2
    cfg["study"]["evaluation_colors"] = 3
    cfg["analysis"]["resamples"] = 200
    template = (ROOT / cfg["study"]["template_path"]).read_text()
    return cfg, build_plan(cfg, template)


def answer(text):
    match = re.search(r"Current color.*LAB\(([^)]+)\)", text)
    lab = list(map(float, match.group(1).split(",")))
    instruction = re.search(r"Instruction: ([^\n]+)", text).group(1)
    numeric = re.match(
        r"(Increase|Decrease) the ([Lab]) coordinate by exactly ([\d.]+)", instruction
    )
    if numeric:
        index = ("L", "a", "b").index(numeric[2])
        lab[index] += (1 if numeric[1] == "Increase" else -1) * float(numeric[3])
    else:
        d = next(
            x for x in DIRECTION_SPECS.values() if instruction.endswith(x.phrase + ".")
        )
        step = (
            5
            if "a little" in instruction
            else 10
            if "somewhat" in instruction
            else 30
            if "much" in instruction
            else 20
        )
        lab[d.index] += d.sign * step
    lab = [
        min(high, max(low, value))
        for value, (low, high) in zip(lab, [(0, 100), (-128, 127), (-128, 127)])
    ]
    return "LAB({:.6f}, {:.6f}, {:.6f})".format(*lab)


def calibrate(plan):
    return {
        t["condition_id"]: score(t, answer(t["prompt"]))
        for t in plan["calibration_tasks"]
    }


class Client:
    def __init__(self, fail_at=None, bad_at=None):
        self.calls = 0
        self.fail_at, self.bad_at = fail_at, bad_at

    def generate(self, prompt, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            text="not a color" if self.calls == self.bad_at else answer(prompt),
            error="unavailable" if self.calls == self.fail_at else None,
            raw={"prompt_tokens": 99, "generated_tokens": 20},
            latency_s=0,
            model_name="cpu_simulation",
            provider="mock",
        )


def test_splits_feasibility_and_prompts_frozen_before_outputs(tmp_path):
    cfg, plan = inputs(tmp_path)
    assert build_plan(cfg, plan["template"]) == plan
    cal = {x["state"]["hex"] for x in plan["splits"]["calibration"]}
    eva = {x["state"]["hex"] for x in plan["splits"]["evaluation"]}
    assert cal.isdisjoint(eva) and (cal | eva).isdisjoint(plan["excluded_hex"])
    assert len(plan["calibration_tasks"]) == 48
    assert len(plan["evaluation_cases"]) + len(plan["feasibility_exclusions"]) == 54
    for case in plan["evaluation_cases"]:
        assert case["target_projection_delta_e"] <= 1
        assert case["axis_residual"] > 0
        assert case["starting_error_delta_e"] == color_distance_lab(
            case["start"]["lab"], case["target"]["lab"]
        )
    changed = copy.deepcopy(cfg)
    changed["seed"] += 1
    assert build_plan(changed, plan["template"])["splits"] != plan["splits"]


def test_positive_median_includes_zero_wrong_sign_and_failures(tmp_path):
    cfg, plan = inputs(tmp_path)
    rows = calibrate(plan)
    for task in plan["calibration_tasks"]:
        if task["direction"] == "lighter" and task["wording"] != "baseline":
            if task["base_id"].endswith("00"):
                rows[task["condition_id"]] = score(task, "bad")
            else:
                state = task["start"]["lab"].copy()
                state[0] -= 3
                rows[task["condition_id"]] = score(
                    task, "LAB({}, {}, {})".format(*state)
                )
    mapping = fit_mapping(cfg, plan, rows)
    assert choose_phrase(mapping, "lighter", 6) is None
    assert any(
        r["parsed"] == 1 and r["nonpositive"] == 1 for r in mapping["table"]["lighter"]
    )
    tasks = evaluation_tasks(cfg, plan, mapping)
    assert all(
        t["status"] == "unavailable_calibration"
        for t in tasks
        if t["direction"] == "lighter" and t["arm"] == "calibrated"
    )
    with pytest.raises(ValueError, match="Complete calibration"):
        fit_mapping(cfg, plan, {})


def test_ties_favor_smaller_median_then_fixed_wording_order():
    mapping = {
        "table": {
            "lighter": [
                {"wording": q, "displayed_median_step": s, "usable": True}
                for q, s in [("a_little", 5), ("somewhat", 10), ("much", 10)]
            ]
        }
    }
    assert choose_phrase(mapping, "lighter", 7.5)["wording"] == "a_little"
    assert choose_phrase(mapping, "lighter", 10)["wording"] == "somewhat"


def test_numeric_target_uses_prompted_start_and_displayed_axis(tmp_path):
    cfg, plan = inputs(tmp_path)
    mapping = fit_mapping(cfg, plan, calibrate(plan))
    tasks = evaluation_tasks(cfg, plan, mapping)
    groups = {}
    for task in tasks:
        groups.setdefault(task["case_id"], []).append(task)
        if task["arm"] == "numeric":
            row = score(task, answer(task["prompt"]))
            assert row["metrics"]["numeric_native_execution_error"] < 1e-6
            assert row["metrics"]["numeric_display_execution_error"] == 0
            assert task["holds_other_coordinates"]
        assert "Target:" not in (task["prompt"] or "")
    for rows in groups.values():
        assert len(rows) == 3 and all(
            r["start"] == rows[0]["start"] and r["target"] == rows[0]["target"]
            for r in rows
        )


def test_geometry_and_projection_do_not_filter_responses(tmp_path):
    cfg, plan = inputs(tmp_path)
    tasks = evaluation_tasks(cfg, plan, fit_mapping(cfg, plan, calibrate(plan)))
    task = next(t for t in tasks if t["arm"] == "bare" and t["direction"] == "more_red")
    row = score(task, "LAB(50, 120, 0)")
    assert row["parse_ok"] and row["projection_delta_e"] > 1
    m = row["metrics"]
    assert m["projected_target_error"] ** 2 == pytest.approx(
        task["starting_error_delta_e"] ** 2
        + m["displayed_movement_norm"] ** 2
        - 2
        * task["starting_error_delta_e"]
        * m["displayed_movement_norm"]
        * m["alignment"]
    )
    assert score(task, "LAB(50, 999, 0)")["metrics"] is None


def test_cluster_bootstrap_resamples_starts_not_cases():
    one = cluster_effect([0] * 20 + [100] * 20, ["a"] * 20 + ["b"] * 20, 2000, 13)
    assert one["starting_colors"] == 2 and one["cases"] == 40 and one["mean"] == 50
    assert one["low"] == 0 and one["high"] == 100
    assert cluster_effect([3, 4], ["a", "a"])["low"] is None
    assert cluster_effect([], [])["mean"] is None
    uneven = cluster_effect([0, 0, 0, 100], ["a", "a", "a", "b"], 2000, 13)
    assert uneven["mean"] == 25  # pooled case weights, not a mean of means
    with pytest.raises(ValueError):
        cluster_effect([np.nan], ["a"])


def test_resume_stages_load_one_client_and_cpu_reanalysis_no_inference(
    tmp_path, monkeypatch
):
    cfg, plan = inputs(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture.yaml"))
    clients = []

    def build(_):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setattr("colorref.llm_clients.build_client", build)
    runner.execute(directory, "calibration", limit=8)
    assert clients[0].calls == 8 and not (directory / "inputs/controller.json").exists()
    with pytest.raises(ValueError, match="Finish calibration"):
        runner.execute(directory, "evaluation")
    runner.execute(directory, "calibration")
    assert clients[1].calls == 40
    bundle = json.loads((directory / "inputs/controller.json").read_text())
    assert len(list((directory / "raw_outputs/evaluation").glob("*.json"))) == 0
    runner.execute(directory, "evaluation", limit=5)
    assert clients[2].calls == 5
    runner.execute(directory, "all")
    expected = sum(t["status"] == "generate" for t in bundle["evaluation_tasks"])
    assert clients[3].calls == expected - 5
    original = {
        p: p.read_bytes()
        for p in [
            directory / "inputs/plan.json",
            directory / "inputs/controller.json",
            *directory.glob("raw_outputs/*/*.json"),
        ]
    }

    def forbidden(_):
        raise AssertionError("No model for completed runs or CPU reports")

    monkeypatch.setattr("colorref.llm_clients.build_client", forbidden)
    runner.execute(directory, report_only=True)
    runner.execute(directory)
    assert all(p.read_bytes() == data for p, data in original.items())
    result = json.loads((directory / "metrics/magnitude_analysis.json").read_text())
    assert result["common_triplets"] == len(plan["evaluation_cases"])
    assert result["effects"][0]["starting_colors"] <= 3
    assert len(result["coverage"]) == 18


def test_all_phase_one_client_limit_across_stage_boundary(tmp_path, monkeypatch):
    cfg, plan = inputs(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture"))
    client = Client()
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    runner.execute(directory, limit=50)
    assert client.calls == 50
    assert len(list((directory / "raw_outputs/calibration").glob("*.json"))) == 48
    assert len(list((directory / "raw_outputs/evaluation").glob("*.json"))) == 2


def test_backend_failures_pending_parse_failures_complete(tmp_path, monkeypatch):
    cfg, plan = inputs(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture"))
    client = Client(fail_at=3, bad_at=2)
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    with pytest.raises(RuntimeError, match="remains pending"):
        runner.execute(directory, "calibration")
    assert len(list((directory / "raw_outputs/calibration").glob("*.json"))) == 2
    assert (directory / "reports/magnitude_summary.md").exists()
    client = Client()
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    runner.execute(directory, "calibration")
    assert client.calls == 46
    result = json.loads((directory / "metrics/magnitude_analysis.json").read_text())
    assert result["calibration_parsed"] == 47


def test_tampering_unknown_files_and_controller_rejected(tmp_path):
    cfg, plan = inputs(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture"))
    cfg2, plan2, meta = runner.load_plan(directory)
    task = plan["calibration_tasks"][0]
    path = runner.checkpoint_path(directory, task)
    row = {**score(task, answer(task["prompt"])), "run_id": meta["run_id"]}
    row["metrics"]["displayed_requested_signed_step"] += 1
    runner.write_json(path, row)
    with pytest.raises(ValueError, match="Checkpoint"):
        runner.load_rows(directory, plan["calibration_tasks"], meta)
    path.unlink()
    (directory / "raw_outputs/calibration/unknown.json").write_text("{}")
    with pytest.raises(ValueError, match="Unknown"):
        runner.load_rows(directory, plan["calibration_tasks"], meta)
    (directory / "raw_outputs/calibration/unknown.json").unlink()
    bundle = runner.controller_bundle(cfg, plan, calibrate(plan))
    bundle["mapping"]["table"]["lighter"][1]["displayed_median_step"] += 1
    runner.write_json(directory / "inputs/controller.json", bundle)
    with pytest.raises(ValueError, match="controller differs"):
        runner.load_controller(directory, cfg, plan, calibrate(plan))


def test_evaluation_failures_change_explicit_cohorts_not_mapping(tmp_path):
    cfg, plan = inputs(tmp_path)
    calibration = calibrate(plan)
    mapping = fit_mapping(cfg, plan, calibration)
    original = copy.deepcopy(mapping)
    tasks = evaluation_tasks(cfg, plan, mapping)
    rows = {t["condition_id"]: score(t, answer(t["prompt"])) for t in tasks}
    bad = next(t for t in tasks if t["arm"] == "numeric")
    rows[bad["condition_id"]] = score(bad, "failed")
    result = analyze(cfg, plan, calibration, mapping, tasks, rows)
    assert result["common_triplets"] == len(plan["evaluation_cases"]) - 1
    effects = {(r["cohort"], r["right"]): r for r in result["effects"]}
    assert effects[("available_pairs", "calibrated")]["cases"] == len(
        plan["evaluation_cases"]
    )
    assert fit_mapping(cfg, plan, calibration) == original
    assert result["evaluation"][2]["parse_failures"] == 1


def test_initial_threshold_skips_generation_for_all_arms(tmp_path):
    cfg, plan = inputs(tmp_path)
    mapping = fit_mapping(cfg, plan, calibrate(plan))
    plan["evaluation_cases"][0]["initially_converged"] = True
    tasks = evaluation_tasks(cfg, plan, mapping)
    stops = [t for t in tasks if t["status"] == "assigned_threshold_stop"]
    assert len(stops) == 3 and all(t["prompt"] is None for t in stops)
    assert {t["arm"] for t in stops} == set(ARMS)


@pytest.mark.parametrize(
    "key,value",
    [
        ("target_steps", [5]),
        ("target_steps", [6, 6]),
        ("convergence_delta_e", float("nan")),
        ("rgb_channel_range", [0, 256]),
        ("calibration_colors", 0),
    ],
)
def test_invalid_config_rejected(tmp_path, key, value):
    cfg, plan = inputs(tmp_path)
    cfg["study"][key] = value
    with pytest.raises(ValueError):
        build_plan(cfg, plan["template"])


def test_full_frozen_pilot_counts_and_single_load(tmp_path, monkeypatch):
    cfg = yaml.safe_load(
        (
            ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml"
        ).read_text()
    )
    cfg["output"]["run_root"] = str(tmp_path)
    cfg["analysis"]["resamples"] = 100
    plan = build_plan(cfg, (ROOT / cfg["study"]["template_path"]).read_text())
    assert len(plan["calibration_tasks"]) == 288
    assert len(plan["evaluation_cases"]) == 196
    assert len(plan["feasibility_exclusions"]) == 20
    directory = runner.create_run(cfg, plan, Path("fixture"))
    client = Client()
    builds = []

    def build(_):
        builds.append(True)
        return client

    monkeypatch.setattr("colorref.llm_clients.build_client", build)
    runner.execute(directory)
    assert len(builds) == 1 and client.calls == 876
    result = json.loads((directory / "metrics/magnitude_analysis.json").read_text())
    assert result["calibration_completed"] == 288
    assert result["common_triplets"] == 196
    assert all(r["pending"] == 0 for r in result["evaluation"])


def test_resolved_model_revision_cannot_change_between_stages(tmp_path, monkeypatch):
    cfg, plan = inputs(tmp_path)
    directory = runner.create_run(cfg, plan, Path("fixture"))
    client = Client()
    client._model_and_tokenizer = (
        SimpleNamespace(config=SimpleNamespace(_commit_hash="first")),
        None,
    )
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    runner.execute(directory, "calibration")
    client._model_and_tokenizer[0].config._commit_hash = "changed"
    with pytest.raises(ValueError, match="Model revision changed"):
        runner.execute(directory, "evaluation")
    assert not list((directory / "raw_outputs/evaluation").glob("*.json"))
