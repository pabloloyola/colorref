"""Saved-output budget/equivalence audit; no scientific model-performance tests."""

import copy
import hashlib
import sys
from pathlib import Path

import pytest

from colorref.teacher_fidelity import canonical, score as teacher_score
from colorref.teacher_receiver import build_plan, score
from tests.test_teacher_receiver import prepare

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import inspect_teacher_receiver as inspector  # noqa: E402
import run_teacher_receiver_study as runner  # noqa: E402


def make_run(tmp_path, monkeypatch):
    _, cfg, _, snapshot = prepare(tmp_path, monkeypatch)
    snapshot = copy.deepcopy(snapshot)
    task = next(t for t in snapshot["plan"]["tasks"] if t["condition"] == "restricted_0" and t["bandwidth"] == 1 and len(t["all_candidates"]) > 1)
    required = [c["direction"] for c in task["required"]]
    extra = next(c["direction"] for c in task["all_candidates"] if c["direction"] not in required)
    old = snapshot["rows"][task["condition_id"]]
    snapshot["rows"][task["condition_id"]] = {**old, **teacher_score(task, canonical(required + [extra]))}
    plan = build_plan(cfg, snapshot)
    run = runner.create_run(cfg, plan, snapshot)
    metadata = runner.load_plan(run)[2]
    rows = {}
    for t in plan["tasks"]:
        text = t["example"]["hex"] if t["condition_id"] == task["condition_id"] else "#808080"
        row = {**score(t, text, cfg), "run_id": metadata["run_id"], "generation": {"generated_tokens": 4}, "prompt_tokens": 100}
        rows[t["condition_id"]] = row
        runner.write_json(runner.checkpoint_path(run, t), row)
    runner.write_reports(run, cfg, plan, rows)
    return run, cfg, plan, rows, snapshot, task["condition_id"]


def test_budget_partition_equivalence_and_primary_preservation(tmp_path, monkeypatch):
    import colorref.llm_clients
    run, cfg, plan, rows, snapshot, changed = make_run(tmp_path, monkeypatch)
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob("*") if p.is_file()}
    monkeypatch.setattr(colorref.llm_clients, "build_client", lambda _: pytest.fail("No inference allowed"))
    result = inspector.inspect_run(run)
    restricted = {s["group"]: s for s in result["summary"] if s["arm"] == "restricted_0"}
    assert restricted["lexical_additions"]["planned"] == 1
    assert restricted["additions_all_threshold_valid"]["planned"] == 1
    assert restricted["additions_not_all_threshold_valid"]["planned"] == 0
    assert restricted["identical_feedback"]["paired"] == 15
    assert restricted["different_feedback"]["paired"] == 1
    assert restricted["lexical_additions"]["mean_difference"] < 0
    assert restricted["all"]["summed_difference"] == restricted["lexical_additions"]["summed_difference"]
    assert all(s["identical_prompt_different_color"] == 0 for s in result["summary"])
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items())


def test_pending_and_invalid_pairs_have_no_imputed_effect(tmp_path, monkeypatch):
    _, cfg, plan, rows, snapshot, changed = make_run(tmp_path, monkeypatch)
    incomplete = copy.deepcopy(rows)
    incomplete.pop(changed)
    result = inspector.inspect(cfg, plan, incomplete, snapshot)
    pair = next(r for r in result["pairs"] if r["condition_id"] == changed)
    assert not pair["paired_parsed"] and pair["error_difference"] is None
    assert pair["arm_raw_response"] is None
    selected = next(s for s in result["summary"] if s["arm"] == "restricted_0" and s["group"] == "lexical_additions")
    assert selected["planned"] == 1 and selected["paired"] == 0
    assert selected["mean_difference"] is None and selected["summed_difference"] is None
    task = next(t for t in plan["tasks"] if t["condition_id"] == changed)
    incomplete[changed] = score(task, "not a color", cfg)
    failed = inspector.inspect(cfg, plan, incomplete, snapshot)
    assert next(r for r in failed["pairs"] if r["condition_id"] == changed)["error_difference"] is None
