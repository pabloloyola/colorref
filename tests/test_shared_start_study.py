"""CPU acceptance tests for frozen parent starts, matched feedback and cohorts."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from colorref.interface_study import REGIMES, build_tasks, next_prompt, score_record
from colorref.llm_clients import _hf_generation_diagnostics
from colorref.shared_start_reports import summarize, write_reports
from colorref.shared_start_study import (
    freeze_inputs,
    generation_diagnostics,
    revision_prompt,
    supplied_start,
    validate_checkpoint,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "shared_runner", ROOT / "scripts/run_shared_start_study.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
import run_interface_study as parent_runner  # noqa: E402


def parent_inputs(tmp_path, quota=1, start_hex="#404040"):
    cfg = yaml.safe_load(
        (ROOT / "configs/experiments/interface_study_a100_40gb.yaml").read_text()
    )
    cfg["study"]["examples_per_regime"] = quota
    cfg["output"]["run_root"] = str(tmp_path / "parent")
    templates = {
        v["id"]: {
            phase: (ROOT / v[f"{phase}_template_path"]).read_text()
            for phase in ("initial", "revision")
        }
        for v in cfg["study"]["variants"]
    }
    examples = [
        {
            "example_id": f"{i}_{j}",
            "raw_name": "gray",
            "hex": "#808080",
            "regime_label": regime,
        }
        for i, regime in enumerate(REGIMES)
        for j in range(quota)
    ]
    directory = parent_runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
    cfg, _plan, metadata = parent_runner.load_plan(directory)
    # Production parent runs already contain their lock file.
    with parent_runner.run_lock(directory):
        pass
    for task in build_tasks(cfg, examples):
        # A parsed HEX start is sufficient; other interfaces' failures cannot
        # select the membership of the shared-start experiment.
        if task["variant"] == "hex":
            prompt, feedback = next_prompt(task, [], cfg, templates)
            record = score_record(task, [], prompt, feedback, start_hex)
            parent_runner.write_json(
                parent_runner.checkpoint_path(directory, task),
                {
                    "run_id": metadata["run_id"],
                    "condition_id": task["condition_id"],
                    "records": [record],
                },
            )
        elif task["variant"] == "lab_axis_legend":
            prompt, feedback = next_prompt(task, [], cfg, templates)
            record = score_record(task, [], prompt, feedback, "invalid")
            parent_runner.write_json(
                parent_runner.checkpoint_path(directory, task),
                {
                    "run_id": metadata["run_id"],
                    "condition_id": task["condition_id"],
                    "records": [record],
                },
            )
    return directory


def inputs(tmp_path, quota=1):
    parent = parent_inputs(tmp_path, quota)
    cfg, plan = runner.prepare_parent(parent, output_root=tmp_path / "shared")
    directory = runner.create_run(cfg, plan)
    cfg, plan, metadata = runner.load_plan(directory)
    return parent, directory, cfg, plan, metadata


class Client:
    def __init__(self, invalid_at=None, backend_at=None):
        self.calls = []
        self.invalid_at = invalid_at
        self.backend_at = backend_at

    def generate(self, prompt, **kwargs):
        if len(self.calls) == self.backend_at:
            return SimpleNamespace(error="simulated backend failure")
        invalid = len(self.calls) == self.invalid_at
        self.calls.append(prompt)
        return SimpleNamespace(
            text="invalid"
            if invalid
            else "#808080"
            if "#RRGGBB" in prompt
            else "LAB(50, 0, 0)",
            error=None,
            model_name="fixture",
            provider="mock",
            latency_s=0,
            raw={
                "generated_tokens": 9,
                "finish_reason": "stop",
                "finish_reason_source": "test_backend",
            },
        )


def test_starts_feedback_and_model_settings_match_and_parent_is_unchanged(tmp_path):
    parent = parent_inputs(tmp_path)
    before = {
        str(p.relative_to(parent)): p.read_bytes()
        for p in parent.rglob("*")
        if p.is_file()
    }
    cfg, plan = runner.prepare_parent(parent)
    original_cfg, original_plan, _ = parent_runner.load_plan(parent)
    assert cfg["model"] == original_cfg["model"]
    assert cfg["teacher"] == original_cfg["teacher"]
    assert cfg["execution"] == original_cfg["execution"]
    assert plan["templates"] == original_plan["templates"]
    assert len(plan["examples"]) == 4  # Includes all parent legend failures.
    for identifier in {t["example"]["example_id"] for t in plan["tasks"]}:
        tasks = [t for t in plan["tasks"] if t["example"]["example_id"] == identifier]
        starts = [supplied_start(t) for t in tasks]
        assert starts[0] == starts[1] == starts[2]
        feedback = [revision_prompt(t, [], cfg, plan["templates"])[1] for t in tasks]
        assert feedback[0] == feedback[1] == feedback[2]
        assert (
            starts[0]["record_kind"] == "supplied_start"
            and starts[0]["raw_response"] is None
        )
        lab_prompt = revision_prompt(
            next(t for t in tasks if t["variant"] == "lab_plain"),
            [],
            cfg,
            plan["templates"],
        )[0]
        assert (
            "LAB({:.6f}, {:.6f}, {:.6f})".format(*starts[0]["displayed_state"]["lab"])
            in lab_prompt
        )
    after = {
        str(p.relative_to(parent)): p.read_bytes()
        for p in parent.rglob("*")
        if p.is_file()
    }
    assert before == after


def test_missing_parent_hex_and_tampered_parent_checkpoint_are_rejected(tmp_path):
    parent = parent_inputs(tmp_path)
    cfg, plan, meta = parent_runner.load_plan(parent)
    saved = parent_runner.load_checkpoints(parent, cfg, plan, meta)
    hex_task = next(t for t in plan["tasks"] if t["variant"] == "hex")
    missing = copy.deepcopy(saved)
    missing.pop(hex_task["slot"])
    with pytest.raises(ValueError, match="Missing parsed parent HEX"):
        freeze_inputs(cfg, plan, meta, missing)
    path = parent_runner.checkpoint_path(parent, hex_task)
    payload = json.loads(path.read_text())
    payload["records"][0]["projected_error_delta_e"] = 999
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Checkpoint does not match"):
        runner.prepare_parent(parent)


def test_turn_resume_backend_errors_and_snapshot_integrity(tmp_path):
    _, directory, cfg, plan, meta = inputs(tmp_path)
    saved = {}
    with pytest.raises(RuntimeError, match="remains pending"):
        runner.run_pending(Client(backend_at=2), cfg, plan, meta, directory, saved)
    saved = runner.load_checkpoints(directory, cfg, plan, meta)
    assert sum(map(len, saved.values())) == 2
    first = plan["tasks"][0]
    assert saved[first["slot"]][0]["turn"] == 1
    assert runner.run_pending(Client(), cfg, plan, meta, directory, saved) == 34
    assert runner.run_pending(Client(), cfg, plan, meta, directory, saved) == 0
    records = copy.deepcopy(saved[first["slot"]])
    records[0]["feedback"]["text"] += " changed"
    with pytest.raises(ValueError, match="Checkpoint does not match"):
        validate_checkpoint(first, records, cfg, plan["templates"])
    path = directory / "inputs/plan.json"
    altered = json.loads(path.read_text())
    altered["examples"][0]["shared_start_hex"] = "#ff0000"
    path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="integrity"):
        runner.load_plan(directory)


@pytest.mark.parametrize(
    "invalid_at,first_n,full_n,responses", [(0, 3, 3, 34), (1, 4, 3, 35)]
)
def test_first_and_late_failures_have_separate_cohorts(
    tmp_path, invalid_at, first_n, full_n, responses
):
    _, directory, cfg, plan, meta = inputs(tmp_path)
    saved = {}
    assert (
        runner.run_pending(
            Client(invalid_at=invalid_at), cfg, plan, meta, directory, saved
        )
        == responses
    )
    result = write_reports(cfg, plan, saved, directory, resamples=100)
    assert len(result["common_first_ids"]) == first_n
    assert len(result["common_final_ids"]) == full_n
    assert result["completed_games"] == 12
    assert len(result["parse_failures"]) == 1
    assert result["parse_failures"][0]["generation"]["generated_tokens"] == 9
    assert sum(r["first_parsed"] for r in result["games"]) == (
        11 if invalid_at == 0 else 12
    )
    assert all(
        r["record_kind"] == "generated_revision"
        for records in saved.values()
        for r in records
    )
    for effect in result["effects"]:
        a, b = effect["error_delta"], effect["gain_delta"]
        assert a["mean"] == pytest.approx(-b["mean"])
        assert a["low"] == pytest.approx(-b["high"])
        assert a["high"] == pytest.approx(-b["low"])


def test_empty_cohort_and_no_constraint_drift_are_defined(tmp_path):
    _, directory, cfg, plan, meta = inputs(tmp_path)
    empty = write_reports(cfg, plan, {}, directory, resamples=100)
    assert not empty["common_first_ids"]
    assert all(r["error_delta"]["mean"] is None for r in empty["effects"])
    # Use the target as an explicitly assigned state; still perform fixed rounds.
    for e in plan["examples"]:
        e["shared_start_hex"] = e["hex"]
        from colorref.interface_study import color_from_hex

        e["shared_start_state"] = color_from_hex(e["hex"])
    plan["tasks"] = build_tasks(cfg, plan["examples"])
    saved = {}
    runner.run_pending(Client(), cfg, plan, meta, directory, saved)
    result = summarize(cfg, plan, saved, resamples=100)
    assert all(
        r["initially_converged"] and r["no_first_constraint"] for r in result["games"]
    )
    assert all(
        r["first_satisfaction"] is None and r["first_alignment"] is None
        for r in result["games"]
    )
    assert len(result["projection"]) == 36  # No assigned start contributes.


def test_full_576_plan_one_load_resume_and_report_without_parent(
    tmp_path, monkeypatch, capsys
):
    import shutil

    parent = parent_inputs(tmp_path, quota=16)
    clients = []

    def build_client(_):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=build_client)
    )
    command = [
        "runner",
        "--parent-run",
        str(parent),
        "--output-root",
        str(tmp_path / "shared"),
        "--resamples",
        "100",
    ]
    monkeypatch.setattr(sys, "argv", [*command, "--dry-run"])
    runner.main()
    preview = json.loads(capsys.readouterr().out)
    assert preview["maximum_generations"] == 576
    assert not clients and not (tmp_path / "shared").exists()
    monkeypatch.setattr(sys, "argv", [*command, "--limit", "8"])
    runner.main()
    directory = next((tmp_path / "shared").iterdir())
    assert len(clients) == 1 and len(clients[0].calls) == 8
    shutil.rmtree(parent)  # Frozen starts/prompts suffice; no dataset or parent needed.
    monkeypatch.setattr(
        sys, "argv", ["runner", "--resume", str(directory), "--resamples", "100"]
    )
    runner.main()
    assert len(clients) == 2 and len(clients[1].calls) == 568
    report = (directory / "reports/shared_start_summary.md").read_text()
    assert "Generated responses: 576 / 576" in report
    assert "Common first-revision examples: 64 / 64" in report
    monkeypatch.setattr(
        sys, "argv", ["runner", "--report-only", str(directory), "--resamples", "100"]
    )
    runner.main()
    monkeypatch.setattr(
        sys, "argv", ["runner", "--resume", str(directory), "--resamples", "100"]
    )
    runner.main()
    assert len(clients) == 2


def test_backend_diagnostics_distinguish_eos_limit_and_missing():
    assert _hf_generation_diagnostics([11, 99], [98, 99], 2) == {
        "generated_tokens": 2,
        "eos_reached": True,
        "token_limit_reached": True,
        "finish_reason": "eos",
        "finish_reason_source": "observed_output_tokens",
    }
    assert _hf_generation_diagnostics([11, 12], 99, 2)["finish_reason"] == "length"
    assert _hf_generation_diagnostics([11], None, 2)["finish_reason"] is None
    assert generation_diagnostics(SimpleNamespace(raw=None))["finish_reason"] is None
    result = generation_diagnostics(
        SimpleNamespace(
            raw={
                "choices": [{"finish_reason": "length"}],
                "usage": {"completion_tokens": 64},
            }
        )
    )
    assert (
        result["generated_tokens"] == 64
        and result["finish_reason_source"] == "backend_reported"
    )


def test_hf_client_preserves_generation_settings_and_returns_observed_diagnostics(
    monkeypatch,
):
    from contextlib import nullcontext

    from colorref.llm_clients import HFTransformersClient

    class Inputs(dict):
        input_ids = SimpleNamespace(shape=(1, 2))

        def to(self, device):
            assert device == "cpu"
            return self

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert messages == [{"role": "user", "content": "fixture"}]
            assert kwargs["enable_thinking"] is False
            return "formatted fixture"

        def __call__(self, text, **kwargs):
            assert text == ["formatted fixture"]
            return Inputs()

        def decode(self, tokens, **kwargs):
            assert tokens == [11, 12, 99]
            assert kwargs["skip_special_tokens"] is True
            return "  LAB(50, 0, 0)  "

    class Model:
        device = "cpu"
        generation_config = SimpleNamespace(eos_token_id=[98, 99])

        def generate(self, **kwargs):
            assert kwargs == {"max_new_tokens": 64, "do_sample": False}
            return [[3, 4, 11, 12, 99]]

    client = HFTransformersClient.__new__(HFTransformersClient)
    client.model_name = "fixture"
    client.enable_thinking = False
    client._model_and_tokenizer = (Model(), Tokenizer())
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=nullcontext))
    response = client.generate("fixture", max_tokens=64, temperature=0)
    assert response.error is None and response.text == "LAB(50, 0, 0)"
    assert response.raw["generated_tokens"] == 3
    assert response.raw["finish_reason"] == "eos"
    assert response.raw["token_limit_reached"] is False


def test_case_inspection_empty_selection_and_unknown_id(tmp_path):
    from inspect_shared_start_cases import inspect

    _, directory, _, _, _ = inputs(tmp_path)
    assert inspect(directory)["case_count"] == 0
    with pytest.raises(ValueError, match="Unknown example ID"):
        inspect(directory, "nonexistent")


def test_case_inspection_retains_raw_failures_and_does_not_rewrite_outputs(
    tmp_path, monkeypatch
):
    from inspect_shared_start_cases import inspect

    parent = parent_inputs(tmp_path, start_hex="#808080")
    cfg, plan = runner.prepare_parent(parent, output_root=tmp_path / "shared")
    directory = runner.create_run(cfg, plan)
    cfg, plan, metadata = runner.load_plan(directory)
    saved = {}
    runner.run_pending(Client(invalid_at=1), cfg, plan, metadata, directory, saved)
    with runner.run_lock(directory):
        pass
    before = {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }

    def forbidden(_):
        raise AssertionError("Case inspection must not load a model")

    monkeypatch.setitem(
        sys.modules, "colorref.llm_clients", SimpleNamespace(build_client=forbidden)
    )
    result = inspect(directory)
    assert result["case_count"] == 4
    assert all(
        c["initially_converged"] and c["starting_error"] == 0 for c in result["cases"]
    )
    assert all(len(c["trajectories"]) == 3 for c in result["cases"])
    trajectories = [t for c in result["cases"] for t in c["trajectories"]]
    assert sum(len(t["revisions"]) for t in trajectories) == 35
    failed = [r for t in trajectories for r in t["revisions"] if not r["parse_ok"]]
    assert len(failed) == 1 and failed[0]["raw_response"] == "invalid"
    assert failed[0]["projected_error"] is None
    identifier = result["cases"][0]["example_id"]
    assert inspect(directory, identifier)["case_count"] == 1
    after = {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }
    assert before == after
