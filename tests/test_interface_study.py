"""CPU acceptance tests for comparable states, fixed rounds, and turn-level resume."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml
from colorref.interface_study import (
    REGIMES,
    build_tasks,
    color_from_hex,
    next_prompt,
    parse_response,
    score_record,
    select_examples,
    validate_checkpoint,
    validate_config,
)
from colorref.interface_study_reports import write_reports

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "interface_runner", ROOT / "scripts/run_interface_study.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def inputs():
    cfg = yaml.safe_load(
        (ROOT / "configs/experiments/interface_study_a100_40gb.yaml").read_text()
    )
    cfg["study"]["examples_per_regime"] = 1
    templates = {
        v["id"]: {
            phase: (ROOT / v[f"{phase}_template_path"]).read_text()
            for phase in ("initial", "revision")
        }
        for v in cfg["study"]["variants"]
    }
    examples = [
        {
            "example_id": str(i),
            "raw_name": "gray",
            "hex": "#808080",
            "regime_label": regime,
        }
        for i, regime in enumerate(REGIMES)
    ]
    return cfg, templates, examples


class Client:
    def __init__(self, fail_after=None, invalid=False):
        self.calls = []
        self.fail_after = fail_after
        self.invalid = invalid

    def generate(self, prompt, **kwargs):
        if self.fail_after is not None and len(self.calls) == self.fail_after:
            return SimpleNamespace(error="simulated backend failure")
        self.calls.append(prompt)
        text = (
            "invalid response"
            if self.invalid
            else ("#808080" if "#RRGGBB" in prompt else "LAB(50, 0, 0)")
        )
        return SimpleNamespace(
            text=text, error=None, model_name="fixture", provider="mock", latency_s=0
        )


def test_selection_is_stable_balanced_and_rejects_shortfalls():
    frame = pd.DataFrame(
        [
            {
                "example_id": i * 10 + j,
                "raw_name": "gray",
                "hex": "#808080",
                "regime_label": regime,
            }
            for i, regime in enumerate(REGIMES)
            for j in range(3)
        ]
    )
    selected = select_examples(frame, 2, 13)
    assert selected == select_examples(frame.sample(frac=1, random_state=9), 2, 13)
    assert len(selected) == 8
    with pytest.raises(ValueError, match="need 4"):
        select_examples(frame, 4, 13)
    with pytest.raises(ValueError, match="unique"):
        select_examples(pd.concat([frame, frame.iloc[:1]]), 2, 13)


def test_plain_lab_has_no_axis_semantics_and_legend_is_the_only_change():
    cfg, templates, _ = inputs()
    validate_config(cfg, templates)
    for phase in ("initial", "revision"):
        plain, legend = (
            templates["lab_plain"][phase],
            templates["lab_axis_legend"][phase],
        )
        assert "increasing a" not in plain
        assert "increasing a makes it more red" in legend
        line = next(
            x
            for x in legend.splitlines(keepends=True)
            if x.startswith("CIELAB axis directions:")
        )
        assert legend.replace(line + "\n", "") == plain


def test_projection_controls_oracle_and_revision_state():
    cfg, templates, examples = inputs()
    task = next(t for t in build_tasks(cfg, examples) if t["variant"] == "lab_plain")
    prompt, _ = next_prompt(task, [], cfg, templates)
    record = score_record(task, [], prompt, None, "LAB(50, 0, 127)")
    assert record["projection_delta_e"] > 50
    revision, feedback = next_prompt(task, [record], cfg, templates)
    state = record["displayed_state"]
    assert "LAB({:.6f}, {:.6f}, {:.6f})".format(*state["lab"]) in revision
    for constraint in feedback["metadata"]["all_constraints"]:
        key, index = {
            "lab_l": ("lab", 0),
            "lab_a": ("lab", 1),
            "lab_b": ("lab", 2),
            "hsv_s": ("hsv", 1),
        }[constraint["axis"]]
        assert constraint["guess_value"] == state[key][index]
    hex_parsed = parse_response(state["hex"], "hex")
    assert hex_parsed["displayed_state"] == state
    assert hex_parsed["projection_delta_e"] == 0


def test_partial_game_resume_preserves_every_completed_turn(tmp_path, monkeypatch):
    cfg, templates, examples = inputs()
    cfg["output"]["run_root"] = str(tmp_path)
    run_dir = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, plan, metadata = runner.load_plan(run_dir)
    checkpoints = {}
    first = Client()
    assert (
        runner.run_pending(first, cfg, plan, metadata, run_dir, checkpoints, limit=5)
        == 5
    )
    reloaded = runner.load_checkpoints(run_dir, cfg, plan, metadata)
    assert sum(len(x) for x in reloaded.values()) == 5
    second = Client()
    assert runner.run_pending(second, cfg, plan, metadata, run_dir, reloaded) == 43
    assert len(first.calls) + len(second.calls) == 48
    # Initial HEX gray is already exact; all three revisions still run.
    assert all(len(x) == 4 for x in reloaded.values())
    full = runner.load_checkpoints(run_dir, cfg, plan, metadata)
    write_reports(cfg, plan["tasks"], full, run_dir)
    summary = (run_dir / "reports/interface_summary.md").read_text()
    assert "Completed games: 12 / 12" in summary
    assert "Matched triplets with all 4 responses parsed: 4 / 4" in summary
    assert len((run_dir / "metrics/paired_deltas.csv").read_text().splitlines()) == 13

    # Completed resume/report-only must not try to load inference modules.
    def forbidden(*args, **kwargs):
        raise AssertionError("Inference path called for a completed run")

    from unittest.mock import patch

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=forbidden)
    )
    with patch.object(sys, "argv", ["runner", "--resume", str(run_dir)]):
        runner.main()
    with patch.object(sys, "argv", ["runner", "--report-only", str(run_dir)]):
        runner.main()


def test_backend_failure_leaves_only_unfinished_turn_pending(tmp_path):
    cfg, templates, examples = inputs()
    cfg["output"]["run_root"] = str(tmp_path)
    run_dir = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, plan, metadata = runner.load_plan(run_dir)
    with pytest.raises(RuntimeError, match="remains pending"):
        runner.run_pending(Client(fail_after=2), cfg, plan, metadata, run_dir, {})
    saved = runner.load_checkpoints(run_dir, cfg, plan, metadata)
    assert sum(len(x) for x in saved.values()) == 2
    assert runner.run_pending(Client(), cfg, plan, metadata, run_dir, saved) == 46


def test_parse_failures_complete_games_and_do_not_enter_paired_means(tmp_path):
    cfg, templates, examples = inputs()
    cfg["output"]["run_root"] = str(tmp_path)
    run_dir = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, plan, metadata = runner.load_plan(run_dir)
    saved = {}
    assert (
        runner.run_pending(
            Client(invalid=True), cfg, plan, metadata, run_dir, saved, limit=1
        )
        == 1
    )
    assert runner.run_pending(Client(), cfg, plan, metadata, run_dir, saved) == 44
    assert runner.run_pending(Client(), cfg, plan, metadata, run_dir, saved) == 0
    write_reports(cfg, plan["tasks"], saved, run_dir)
    report = (run_dir / "reports/interface_summary.md").read_text()
    assert "Parse failures: 1" in report
    assert "Completed matched triplets: 4 / 4" in report
    assert "Matched triplets with all 4 responses parsed: 3 / 4" in report


def test_checkpoint_and_snapshot_mismatches_are_rejected(tmp_path):
    cfg, templates, examples = inputs()
    cfg["output"]["run_root"] = str(tmp_path)
    run_dir = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, plan, metadata = runner.load_plan(run_dir)
    checkpoints = {}
    runner.run_pending(Client(), cfg, plan, metadata, run_dir, checkpoints, limit=1)
    task = plan["tasks"][0]
    records = copy.deepcopy(checkpoints[task["slot"]])
    records[0]["projected_error_delta_e"] = 999
    with pytest.raises(ValueError, match="Checkpoint does not match"):
        validate_checkpoint(task, records, cfg, templates)
    path = run_dir / "inputs/plan.json"
    altered = json.loads(path.read_text())
    altered["templates"]["hex"]["initial"] += " altered"
    path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="integrity"):
        runner.load_plan(run_dir)


def test_native_and_projected_errors_are_distinct():
    cfg, templates, examples = inputs()
    task = next(t for t in build_tasks(cfg, examples) if t["variant"] == "lab_plain")
    native_target = color_from_hex(task["example"]["hex"])["lab"]
    record = score_record(task, [], "fixture", None, "LAB(50, 0, 127)")
    assert record["native_error_delta_e"] != record["projected_error_delta_e"]
    assert native_target != record["native_lab"]


def test_full_768_call_plan_runs_with_one_model_load_per_invocation(
    tmp_path, monkeypatch, capsys
):
    cfg, _, _ = inputs()
    cfg["study"]["examples_per_regime"] = 16
    cfg["output"]["run_root"] = str(tmp_path / "runs")
    frame = pd.DataFrame(
        [
            {
                "example_id": i * 100 + j,
                "raw_name": "gray",
                "hex": "#808080",
                "regime_label": regime,
            }
            for i, regime in enumerate(REGIMES)
            for j in range(20)
        ]
    )
    subset = tmp_path / "subset.parquet"
    frame.to_parquet(subset, index=False)
    cfg["input"]["subset_path"] = str(subset)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(cfg))
    clients = []

    def build_client(_):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=build_client)
    )
    monkeypatch.setattr(
        sys, "argv", ["runner", "--config", str(config_path), "--dry-run"]
    )
    runner.main()
    assert json.loads(capsys.readouterr().out)["maximum_generations"] == 768
    assert not clients and not (tmp_path / "runs").exists()
    monkeypatch.setattr(
        sys, "argv", ["runner", "--config", str(config_path), "--limit", "8"]
    )
    runner.main()
    run_dir = next((tmp_path / "runs").iterdir())
    assert len(clients) == 1 and len(clients[0].calls) == 8
    # Frozen selection and prompt snapshots must suffice after the live dataset disappears.
    subset.unlink()
    monkeypatch.setattr(sys, "argv", ["runner", "--resume", str(run_dir)])
    runner.main()
    assert len(clients) == 2 and len(clients[1].calls) == 760
    report = (run_dir / "reports/interface_summary.md").read_text()
    assert "Completed games: 192 / 192" in report
    assert "Matched triplets with all 4 responses parsed: 64 / 64" in report
    monkeypatch.setattr(sys, "argv", ["runner", "--report-only", str(run_dir)])
    runner.main()
    assert len(clients) == 2
