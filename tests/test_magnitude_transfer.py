"""Sequential stopping, frozen-controller transfer, strict resume and CPU audits."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from colorref.magnitude_control import build_plan as parent_plan, score
from colorref.magnitude_transfer import (
    build_plan,
    endpoint,
    next_revision,
    validate_records,
)
from colorref.magnitude_transfer_reports import analyze
from colorref.quantifiers import DIRECTION_SPECS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_magnitude_control as parent_runner  # noqa: E402
import run_magnitude_transfer as runner  # noqa: E402


def answer(prompt):
    lab = list(
        map(float, re.search(r"Current color.*LAB\(([^)]+)\)", prompt)[1].split(","))
    )
    instruction = re.search(r"Instruction: ([^\n]+)", prompt)[1]
    numeric = re.match(
        r"(Increase|Decrease) the ([Lab]) coordinate by exactly ([\d.]+)", instruction
    )
    if numeric:
        lab[("L", "a", "b").index(numeric[2])] += (
            1 if numeric[1] == "Increase" else -1
        ) * float(numeric[3])
    else:
        d = next(
            d for d in DIRECTION_SPECS.values() if instruction.endswith(d.phrase + ".")
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
        min(hi, max(lo, v))
        for v, (lo, hi) in zip(lab, [(0, 100), (-128, 127), (-128, 127)])
    ]
    return "LAB({:.6f}, {:.6f}, {:.6f})".format(*lab)


class Client:
    def __init__(self, bad_at=None, fail_at=None, revision="snapshot"):
        self.calls = 0
        self.bad_at, self.fail_at = bad_at, fail_at
        self._model_and_tokenizer = (
            SimpleNamespace(config=SimpleNamespace(_commit_hash=revision)),
            None,
        )

    def generate(self, prompt, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            text="bad" if self.calls == self.bad_at else answer(prompt),
            error="offline" if self.calls == self.fail_at else None,
            raw={"prompt_tokens": 99, "generated_tokens": 20},
            model_name="simulation",
            provider="mock",
            latency_s=0,
        )


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    cfg = yaml.safe_load(
        (
            ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml"
        ).read_text()
    )
    cfg["output"]["run_root"] = str(tmp_path)
    cfg["study"]["calibration_colors"] = 2
    cfg["study"]["evaluation_colors"] = 3
    cfg["analysis"]["resamples"] = 100
    plan = parent_plan(cfg, (ROOT / cfg["study"]["template_path"]).read_text())
    parent = parent_runner.create_run(cfg, plan, Path("fixture"))
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: Client())
    parent_runner.execute(parent)
    cfg, plan, snapshot = runner.prepare_parent(parent)
    return parent, cfg, plan, snapshot


def row(game, records, cfg, plan, raw=None, run_id="fixture"):
    reason, task = next_revision(game, records, cfg, plan)
    assert reason is None
    return {
        **score(task, raw if raw is not None else answer(task["prompt"])),
        "run_id": run_id,
    }


def test_fresh_selection_counts_target_free_prompts_and_mapping(prepared):
    parent, cfg, plan, snapshot = prepared
    assert build_plan(cfg, snapshot) == plan
    starts = {c["state"]["hex"] for c in plan["starts"]}
    old = {
        c["state"]["hex"]
        for split in snapshot["plan"]["splits"].values()
        for c in split
    }
    assert len(starts) == 12 and starts.isdisjoint(
        old | set(snapshot["plan"]["excluded_hex"])
    )
    assert len(plan["evaluation_cases"]) + len(plan["feasibility_exclusions"]) == 216
    assert len(plan["games"]) == 3 * len(plan["evaluation_cases"])
    assert plan["mapping"] == snapshot["controller"]["mapping"]
    before = copy.deepcopy(plan["mapping"])
    for game in plan["games"]:
        reason, task = next_revision(game, [], cfg, plan)
        if task:
            assert "Target:" not in task["prompt"]
            assert task["constraint_count"] == 1
    assert plan["mapping"] == before
    assert plan["required_model_revision"] == "snapshot"


def test_parent_requires_complete_evaluation_and_original_controller(prepared):
    parent, cfg, plan, snapshot = prepared
    bad = copy.deepcopy(snapshot)
    bad["evaluation_completed"] -= 1
    with pytest.raises(ValueError, match="Complete the parent"):
        build_plan(cfg, bad)
    bad = copy.deepcopy(snapshot)
    bad["controller"]["mapping"]["table"]["lighter"][1]["displayed_median_step"] += 1
    with pytest.raises(ValueError, match="controller"):
        build_plan(cfg, bad)
    changed = copy.deepcopy(cfg)
    changed["seed"] += 1
    with pytest.raises(ValueError, match="declared protocol"):
        build_plan(changed, snapshot)


def test_threshold_including_assigned_start_never_generates(prepared):
    _, cfg, plan, _ = prepared
    game = copy.deepcopy(plan["games"][0])
    game["target"] = copy.deepcopy(game["start"])
    reason, task = next_revision(game, [], cfg, plan)
    assert reason == "threshold_stop" and task is None
    result = endpoint(game, [], cfg, plan)
    assert result["valid"] and result["zero_call_stop"] and result["calls"] == 0
    assert result["error"] == 0 and result["converged"]


def test_sign_reversal_uses_original_axis_and_dynamic_numeric_residual(prepared):
    _, cfg, plan, _ = prepared
    game = next(
        g
        for g in plan["games"]
        if g["direction"] == "lighter" and g["arm"] == "numeric"
    )
    previous = {"parse_ok": True, "displayed_state": copy.deepcopy(game["target"])}
    previous["displayed_state"]["lab"][0] += 12
    reason, task = next_revision(game, [previous], cfg, plan)
    assert reason is None and task["direction"] == "darker"
    assert task["original_direction"] == "lighter" and task["turn"] == 2
    assert "Decrease the L coordinate" in task["instruction"]
    assert task["expected_numeric_lab"][0] == round(game["target"]["lab"][0], 6)
    assert task["start"] == previous["displayed_state"]


def test_off_axis_resolution_stops_without_repair(prepared):
    _, cfg, plan, _ = prepared
    game = copy.deepcopy(plan["games"][0])
    state = copy.deepcopy(game["target"])
    axis = DIRECTION_SPECS[game["direction"]].index
    state["lab"][(axis + 1) % 3] += 15
    records = [{"parse_ok": True, "displayed_state": state}]
    reason, task = next_revision(game, records, cfg, plan)
    assert reason == "off_axis_residual" and task is None
    result = endpoint(game, records, cfg, plan)
    assert (
        result["valid"]
        and not result["converged"]
        and result["error"] == pytest.approx(15)
    )


def test_unavailable_reverse_mapping_is_explicit(prepared):
    _, cfg, plan, _ = prepared
    game = next(
        g
        for g in plan["games"]
        if g["direction"] == "lighter" and g["arm"] == "calibrated"
    )
    plan = copy.deepcopy(plan)
    for r in plan["mapping"]["table"]["darker"]:
        r["usable"] = False
    previous = {"parse_ok": True, "displayed_state": copy.deepcopy(game["target"])}
    previous["displayed_state"]["lab"][0] += 12
    assert next_revision(game, [previous], cfg, plan)[0] == "unavailable_calibration"
    assert not endpoint(game, [previous], cfg, plan)["valid"]
    assert endpoint(game, [previous], cfg, plan, 1)["valid"]
    assert not endpoint(game, [previous], cfg, plan, 3)["valid"]


def test_cap_and_no_extra_revisions_after_terminal(prepared):
    _, cfg, plan, _ = prepared
    game = plan["games"][0]
    records = []
    unchanged = "LAB({:.6f}, {:.6f}, {:.6f})".format(*game["start"]["lab"])
    for _ in range(5):
        records.append(row(game, records, cfg, plan, unchanged))
    assert next_revision(game, records, cfg, plan)[0] == "budget_exhausted"
    validate_records(game, records, cfg, plan, "fixture")
    with pytest.raises(ValueError, match="continues after"):
        validate_records(game, [*records, records[-1]], cfg, plan, "fixture")


def test_later_failure_preserves_budget_one_and_never_imputes_final(prepared):
    _, cfg, plan, _ = prepared
    game = next(
        g for g in plan["games"] if g["arm"] == "bare" and g["requested_distance"] == 24
    )
    raw = "LAB({:.6f}, {:.6f}, {:.6f})".format(*game["start"]["lab"])
    first = row(game, [], cfg, plan, raw)
    second = row(game, [first], cfg, plan, "invalid")
    records = [first, second]
    assert endpoint(game, records, cfg, plan, 1)["valid"]
    assert not endpoint(game, records, cfg, plan, 3)["valid"]
    final = endpoint(game, records, cfg, plan)
    assert final["status"] == "parse_failure" and final["error"] is None


def test_resume_one_load_and_cpu_reports_preserve_inputs(prepared, monkeypatch):
    parent, cfg, plan, snapshot = prepared
    parent_bytes = {p: p.read_bytes() for p in parent.rglob("*") if p.is_file()}
    directory = runner.create_run(cfg, plan, snapshot)
    clients = []

    def build(_):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setattr("colorref.llm_clients.build_client", build)
    runner.execute(directory, limit=7)
    assert len(clients) == 1 and clients[0].calls == 7
    original = {p: p.read_bytes() for p in directory.glob("raw_outputs/games/*.json")}
    result = runner.execute(directory)
    assert len(clients) == 2
    assert result["generated"] == 7 + clients[1].calls
    assert result["common_triplets"] == len(plan["evaluation_cases"])
    assert all(r["statuses"].get("pending", 0) == 0 for r in result["completion"])
    assert len(plan["games"]) * 5 >= result["generated"]
    assert all(p.read_bytes() == data for p, data in parent_bytes.items())
    # An early partially saved game grows on resume; complete saved prefixes are never regenerated.
    for p, data in original.items():
        before = json.loads(data)["records"]
        assert json.loads(p.read_text())["records"][: len(before)] == before
    frozen = {
        p: p.read_bytes()
        for p in [
            directory / "config.yaml",
            *directory.glob("inputs/*.json"),
            *directory.glob("raw_outputs/games/*.json"),
        ]
    }
    monkeypatch.setattr(
        "colorref.llm_clients.build_client",
        lambda _: pytest.fail("CPU/completed runs cannot load model"),
    )
    assert runner.execute(directory, report_only=True) == result
    assert runner.execute(directory) == result
    assert all(p.read_bytes() == data for p, data in frozen.items())
    assert result["numeric_execution"]["max"] < 0.01
    assert all(p["common_triplets"] == result["targets"] for p in result["prefixes"])


def test_backend_pending_and_parse_failure_terminal(prepared, monkeypatch):
    _, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    client = Client(bad_at=1, fail_at=3)
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    with pytest.raises(RuntimeError, match="pending for resume"):
        runner.execute(directory)
    result = json.loads((directory / "metrics/transfer_analysis.json").read_text())
    assert result["generated"] == 2 and len(result["failures"]) == 1
    assert result["endpoints"][0]["error"] is None
    assert (directory / "raw_outputs/last_execution_error.json").exists()
    failed_path = runner.checkpoint_path(directory, plan["games"][0])
    before = failed_path.read_bytes()
    client = Client()
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    result = runner.execute(directory)
    assert result["common_triplets"] == result["targets"] - 1
    pair = next(
        e
        for e in result["effects"]
        if e["cohort"] == "available_pairs"
        and e["right"] == "numeric"
        and e["measure"] == "error"
    )
    assert (
        pair["cases"] == result["targets"] - 1
    )  # Failed bare arm invalidates both pairs.
    assert failed_path.read_bytes() == before


def test_model_revision_mismatch_prevents_inference(prepared, monkeypatch):
    _, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    client = Client(revision="different")
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    with pytest.raises(ValueError, match="Model revision changed"):
        runner.execute(directory)
    assert client.calls == 0 and not list(directory.glob("raw_outputs/games/*.json"))


def test_frozen_tampering_unknown_files_and_replayed_score_rejected(
    prepared, monkeypatch
):
    _, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: Client())
    runner.execute(directory, limit=1)
    p = runner.checkpoint_path(directory, plan["games"][0])
    saved = p.read_text()
    bad = json.loads(saved)
    bad["records"][0]["metrics"]["gain"] += 1
    runner.write_json(p, bad)
    with pytest.raises(ValueError, match="frozen task/score"):
        runner.execute(directory, report_only=True)
    p.write_text(saved)
    extra = directory / "raw_outputs/games/unknown.json"
    extra.write_text("{}")
    with pytest.raises(ValueError, match="Unknown"):
        runner.execute(directory, report_only=True)
    extra.unlink()
    p = directory / "inputs/parent_snapshot.json"
    saved = p.read_text()
    bad = json.loads(saved)
    bad["controller"]["mapping"]["table"]["lighter"][1]["displayed_median_step"] += 1
    runner.write_json(p, bad)
    with pytest.raises(ValueError, match="integrity"):
        runner.load_plan(directory)


def test_cluster_counts_missing_numeric_and_numeric_tail(prepared):
    _, cfg, plan, _ = prepared
    checkpoints = {}
    for game in plan["games"]:
        records = []
        while next_revision(game, records, cfg, plan)[0] is None:
            records.append(row(game, records, cfg, plan))
        checkpoints[game["condition_id"]] = records
    numeric_game = next(g for g in plan["games"] if g["arm"] == "numeric")
    first = row(numeric_game, [], cfg, plan, "bad")
    checkpoints[numeric_game["condition_id"]] = [first]
    result = analyze(cfg, plan, checkpoints)
    assert result["common_triplets"] == result["targets"] - 1
    pair = next(
        e
        for e in result["effects"]
        if e["cohort"] == "available_pairs"
        and e["right"] == "calibrated"
        and e["measure"] == "error"
    )
    assert pair["cases"] == result["targets"] and pair["starting_colors"] == 12
    assert sum(s["n"] for s in result["per_start"]) == result["common_triplets"]
    # Deliberately large but strictly parsed numeric execution miss is retained.
    numeric_game = next(
        g
        for g in plan["games"]
        if g["arm"] == "numeric" and g["direction"] == "more_red"
    )
    first = row(numeric_game, [], cfg, plan, "LAB(50, 70, 0)")
    checkpoints[numeric_game["condition_id"]] = [first]
    result = analyze(cfg, plan, checkpoints)
    assert result["numeric_execution"]["above_1"] >= 1
    assert any(
        r["condition_id"] == first["condition_id"] for r in result["numeric_misses"]
    )


def test_empty_report_pending_denominators_no_nan(prepared):
    _, cfg, plan, _ = prepared
    result = analyze(cfg, plan, {})
    assert result["common_triplets"] == 0 and result["generated"] == 0
    assert all(
        r["statuses"]["pending"] == len(plan["evaluation_cases"])
        for r in result["completion"]
    )
    json.dumps(result, allow_nan=False)


def test_cli_dry_run_full_parent_never_loads_model(tmp_path, monkeypatch, capsys):
    cfg = yaml.safe_load(
        (
            ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml"
        ).read_text()
    )
    cfg["output"]["run_root"] = str(tmp_path)
    cfg["analysis"]["resamples"] = 100
    plan = parent_plan(cfg, (ROOT / cfg["study"]["template_path"]).read_text())
    parent = parent_runner.create_run(cfg, plan, Path("fixture"))
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: Client())
    parent_runner.execute(parent)
    original = {p: p.read_bytes() for p in parent.rglob("*") if p.is_file()}
    monkeypatch.setattr(
        "colorref.llm_clients.build_client",
        lambda _: pytest.fail("dry run cannot load model"),
    )
    output_root = tmp_path / "dry_run_should_not_create"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_magnitude_transfer.py",
            "--parent-run",
            str(parent),
            "--output-root",
            str(output_root),
            "--dry-run",
        ],
    )
    runner.main()
    result = json.loads(capsys.readouterr().out)
    assert result["fresh_starts"] == 12
    assert (
        result["feasible_targets"],
        result["feasibility_exclusions"],
        result["games"],
        result["maximum_generations"],
    ) == (200, 16, 600, 3000)
    assert result["feasible_targets"] + result["feasibility_exclusions"] == 216
    assert result["games"] == result["feasible_targets"] * 3
    assert result["maximum_generations"] == result["games"] * 5
    assert result["new_calibration_generations"] == 0
    assert result["required_model_revision"] == "snapshot"
    assert not output_root.exists()
    assert all(p.read_bytes() == data for p, data in original.items())


def test_snapshot_allows_resume_when_parent_is_moved(prepared, monkeypatch):
    parent, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    parent.rename(parent.with_name(parent.name + "_moved"))
    client = Client()
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: client)
    runner.execute(directory, limit=2)
    assert client.calls == 2
    monkeypatch.setattr(
        "colorref.llm_clients.build_client",
        lambda _: pytest.fail("report only cannot load model"),
    )
    monkeypatch.setattr(
        sys, "argv", ["run_magnitude_transfer.py", "--report-only", str(directory)]
    )
    runner.main()
    result = json.loads((directory / "metrics/transfer_analysis.json").read_text())
    assert result["generated"] == 2
