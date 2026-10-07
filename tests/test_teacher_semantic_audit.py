"""Finite-grammar scope, export denominators and preservation tests."""

import copy
import hashlib

import pytest

from colorref.teacher_fidelity import analyze, score
from colorref.teacher_semantic_audit import audit, audit_row, interpret
from tests.test_teacher_fidelity import make_parent
import run_teacher_fidelity_study as runner
import inspect_teacher_semantics as inspector


@pytest.mark.parametrize(
    "text,directions,form",
    [
        ("Feedback: Make it lighter.", ["lighter"], "direct_adjustment"),
        (
            "Your guess is darker, more saturated, and less yellow than the target color.",
            ["lighter", "more muted", "more yellow"],
            "guess_target_comparison",
        ),
        (
            "Your guess is less green and less saturated compared to the target color.",
            ["more green", "more saturated"],
            "guess_target_comparison",
        ),
        (
            "Your guess is slightly darker than the target color.",
            ["lighter"],
            "guess_target_comparison",
        ),
    ],
)
def test_scope(text, directions, form):
    result = interpret(text)
    assert result["resolved"] and result["form"] == form
    assert result["directions"] == sorted(directions)


@pytest.mark.parametrize(
    "text",
    [
        "Your guess is more muted than the lilac rug.",
        "Your guess is too dark and needs to be lighter.",
        "Your guess is more blue.",
        "Make it not lighter.",
        "Make it lighter. Ignore the previous instruction.",
        "Make it cooler.",
        "",
        "Feedback: Feedback: Make it lighter.",
    ],
)
def test_unknown_scope_stays_unresolved(text):
    assert not interpret(text)["resolved"]


def test_audit_not_based_on_required_answer():
    row = {
        "condition_id": "x",
        "condition": "natural_0",
        "bandwidth": 1,
        "required": [{"direction": "lighter"}],
        "raw_response": "Your guess is lighter than the target color.",
        "metrics": {"certified_preservation": False},
    }
    result = audit_row(row)
    assert result["exact_set_match"] is False
    assert result["directions"] == ["darker"]
    row["raw_response"] = "Your guess is more blue."
    assert audit_row(row)["exact_set_match"] is None


def test_checkpoint_and_selected_export_agree_and_preserve(tmp_path, monkeypatch):
    from tests.test_teacher_fidelity import Client

    parent = make_parent(tmp_path)
    cfg, plan, snapshot = runner.prepare_parent(parent, output_root=tmp_path / "runs")
    run = runner.create_run(cfg, plan, snapshot)
    import colorref.llm_clients

    monkeypatch.setattr(colorref.llm_clients, "build_client", lambda _: Client())
    runner.execute(run, limit=8)
    loaded_cfg, loaded_plan, metadata = runner.load_plan(run)
    rows = runner.load_rows(run, loaded_plan, metadata)
    original = analyze(loaded_cfg, loaded_plan, rows)
    partial = audit(
        original["diagnostics"], original["completion"], "diagnostic_export"
    )
    full = audit(list(rows.values()), original["completion"], "validated_checkpoints")
    assert [s["resolved_match"] for s in partial["summary"]] == [
        s["resolved_match"] for s in full["summary"]
    ]
    assert sum(s["aggregate_only_canonical"] for s in partial["summary"]) == 8
    frozen = [p for p in run.rglob("*") if p.is_file() and p.name != ".run.lock"]
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
    monkeypatch.setattr(
        colorref.llm_clients, "build_client", lambda _: pytest.fail("No model allowed")
    )
    inspector.inspect_run(run)
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items()
    )
    bad = copy.deepcopy(original["completion"])
    bad[0]["canonical"] += 1
    with pytest.raises(ValueError, match="reconcile"):
        audit(original["diagnostics"], bad, "diagnostic_export")


def test_duplicate_and_unknown_rows_rejected():
    task = {
        "condition_id": "x",
        "condition": "restricted_0",
        "bandwidth": 1,
        "clause_budget": 1,
        "required": [{"direction": "lighter"}],
        "all_candidates": [{"direction": "lighter"}],
    }
    row = score(task, "Make it lighter.")
    completion = [
        {
            "condition": "restricted_0",
            "bandwidth": 1,
            "completed": 1,
            "canonical": 1,
            "certified": 1,
        }
    ]
    with pytest.raises(ValueError, match="Duplicate"):
        audit([row, row], completion, "validated_checkpoints")
    with pytest.raises(ValueError, match="Completion"):
        audit([], completion, "validated_checkpoints")
