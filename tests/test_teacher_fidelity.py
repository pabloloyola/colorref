"""CPU-only acceptance tests; simulated teachers are not scientific results."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from colorref.interface_study import (
    REGIMES,
    build_tasks,
    color_from_hex,
    next_prompt,
    score_record,
)
from colorref.teacher_fidelity import (
    CONDITIONS,
    analyze,
    build_plan,
    canonical,
    candidates,
    score,
)
from colorref.quantifier_study import plan_digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_interface_study as interface_runner  # noqa: E402
import run_shared_start_study as shared_runner  # noqa: E402
import run_teacher_fidelity_study as runner  # noqa: E402


def make_parent(tmp_path, quota=3):
    cfg = yaml.safe_load(
        (ROOT / "configs/experiments/interface_study_a100_40gb.yaml").read_text()
    )
    cfg["study"]["examples_per_regime"] = quota
    cfg["output"]["run_root"] = str(tmp_path / "interface")
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
            "raw_name": f"unique description {i} {j}",
            "hex": "#{:02x}{:02x}{:02x}".format(
                120 + i * 8 + j, 60 + j * 2, 30 + i * 10
            ),
            "regime_label": r,
        }
        for i, r in enumerate(REGIMES)
        for j in range(quota)
    ]
    directory = interface_runner.create_run(cfg, templates, examples, Path("fixture"))
    metadata = interface_runner.load_plan(directory)[2]
    for task in build_tasks(cfg, examples):
        if task["variant"] != "hex":
            continue
        i, j = map(int, task["example"]["example_id"].split("_"))
        guess = "#{:02x}{:02x}{:02x}".format(20 + i * 4 + j, 120 + i * 5, 160 - j * 5)
        prompt, feedback = next_prompt(task, [], cfg, templates)
        record = score_record(task, [], prompt, feedback, guess)
        interface_runner.write_json(
            interface_runner.checkpoint_path(directory, task),
            {
                "run_id": metadata["run_id"],
                "condition_id": task["condition_id"],
                "records": [record],
            },
        )
    cfg, plan = shared_runner.prepare_parent(directory, output_root=tmp_path / "shared")
    return shared_runner.create_run(cfg, plan)


@pytest.fixture
def prepared(tmp_path):
    parent = make_parent(tmp_path)
    cfg, plan, snapshot = runner.prepare_parent(
        parent, output_root=tmp_path / "teacher"
    )
    return parent, cfg, plan, snapshot


class Client:
    def __init__(self, blank_at=None, fail_at=None, revision="fixture_revision"):
        self.calls = 0
        self.blank_at, self.fail_at = blank_at, fail_at
        self._model_and_tokenizer = (
            SimpleNamespace(config=SimpleNamespace(_commit_hash=revision)),
            None,
        )

    def generate(self, prompt, **kwargs):
        self.calls += 1
        assert kwargs == {"max_tokens": 80, "temperature": 0.0}
        if self.calls == self.fail_at:
            return SimpleNamespace(error="offline")
        blocks = re.findall(r'\[\s*\{\s*"direction".*?\]', prompt, re.S)
        directions = [c["direction"] for c in json.loads(blocks[-1])]
        return SimpleNamespace(
            text="" if self.calls == self.blank_at else canonical(directions),
            error=None,
            model_name="mock",
            provider="mock",
            latency_s=0,
            raw={"generated_tokens": 14, "prompt_tokens": 123, "finish_reason": "eos"},
        )


def test_plan_matches_states_directions_and_demonstration_split(prepared):
    _, cfg, plan, snapshot = prepared
    assert build_plan(cfg, snapshot, plan["templates"]) == plan
    assert len(plan["demonstrations"]) == 4
    assert len(plan["evaluation"]) == 8
    assert len(plan["tasks"]) == 64
    demo_ids = {d["example_id"] for d in plan["demonstrations"]}
    groups = {}
    for task in plan["tasks"]:
        assert task["example_id"] not in demo_ids
        assert task["clause_budget"] >= task["constraint_count"]
        assert task["required"] == candidates(task["example"], cfg)[: task["bandwidth"]]
        groups.setdefault(task["case_id"], []).append(task)
        if task["condition"].endswith("_4"):
            assert set(task["demonstration_ids"]) == demo_ids
            assert "Worked examples:" in task["prompt"]
        else:
            assert task["demonstration_ids"] == []
            assert "Worked examples:" not in task["prompt"]
    for group in groups.values():
        assert {t["condition"] for t in group} == set(CONDITIONS)
        assert all(
            t["required"] == group[0]["required"]
            and t["example"] == group[0]["example"]
            for t in group
        )
    natural = next(t for t in plan["tasks"] if t["condition"] == "natural_0")
    assert (
        "paraphrase only" in natural["prompt"]
        and "warmer or cooler" in natural["prompt"]
    )
    restricted = next(t for t in plan["tasks"] if t["condition"] == "restricted_0")
    assert "Do not add, omit, reverse, or substitute" in restricted["prompt"]
    assert cfg["model"]["model_name"] == snapshot["config"]["model"]["model_name"]
    assert cfg["model"]["max_tokens"] == 80


def audit_task(prepared):
    task = copy.deepcopy(prepared[2]["tasks"][0])
    task["required"] = [
        {"direction": "lighter", "axis": "lab_l"},
        {"direction": "more red", "axis": "lab_a"},
    ]
    task["all_candidates"] = [
        *task["required"],
        {"direction": "more blue", "axis": "lab_b"},
    ]
    task["clause_budget"] = 3
    return task


def test_scoring_synonyms_negation_broad_terms_unknowns_and_numeric_leak(prepared):
    task = audit_task(prepared)
    good = score(task, "Make it brighter and redder.")["metrics"]
    assert good["certified_preservation"] and not good["canonical_compliant"]
    negated = score(task, "Do not make it lighter and more red.")["metrics"]
    assert negated["keyword_set_equal"] and not negated["certified_preservation"]
    assert "negation_or_scope" in negated["audit_flags"]
    scoped = score(task, "Make it lighter and less more red.")["metrics"]
    assert scoped["keyword_set_equal"] and not scoped["certified_preservation"]
    assert "unresolved_comparative_scope" in scoped["audit_flags"]
    for text in (
        "Make it warmer.",
        "Make it lighter and more red with banana.",
        "Make it lighter and more red by 10.",
    ):
        metrics = score(task, text)["metrics"]
        assert metrics["audit_flags"] and not metrics["certified_preservation"]
    metrics = score(task, "Make it darker and more red and more blue.")["metrics"]
    assert metrics["reversals"] == ["darker"]
    assert metrics["additions"] == ["darker", "more blue"]
    assert metrics["omissions"] == ["lighter"]
    assert metrics["recognized_geometric_precision"] == pytest.approx(2 / 3)
    assert score(task, "Make it lighter, darker, and more red.")["metrics"][
        "contradictory_axes"
    ] == ["lab_l"]


def test_scoring_duplicate_mentions_empty_output_and_word_boundaries(prepared):
    task = audit_task(prepared)
    metrics = score(task, "Make it lighter, lighter, and more red.")["metrics"]
    assert metrics["duplicate_mentions"] == 1 and not metrics["certified_preservation"]
    assert not metrics["canonical_compliant"]
    metrics = score(task, "")["metrics"]
    assert not metrics["nonempty"] and metrics["recognized_geometric_precision"] is None
    assert score(task, "Make it more reddish.")["metrics"]["detected_directions"] == []
    assert score(task, "Make it lighter and more red.")["metrics"][
        "canonical_compliant"
    ]


def test_resume_one_model_and_preserve_parent_primary_and_checkpoints(
    prepared, monkeypatch
):
    parent, cfg, plan, snapshot = prepared
    original_parent = {p: p.read_bytes() for p in parent.rglob("*") if p.is_file()}
    directory = runner.create_run(cfg, plan, snapshot)
    clients = []

    def build(_):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setattr("colorref.llm_clients.build_client", build)
    result = runner.execute(directory, limit=8)
    assert result["completed"] == 8 and result["common_quartets"] == 2
    assert len(clients) == 1 and clients[0].calls == 8
    saved = {p: p.read_bytes() for p in directory.glob("raw_outputs/responses/*.json")}
    result = runner.execute(directory)
    assert len(clients) == 2 and clients[1].calls == len(plan["tasks"]) - 8
    assert all(r["certified"] == r["planned"] for r in result["completion"])
    assert result["oracle_canonical_certified"]
    assert all(p.read_bytes() == data for p, data in saved.items())
    assert all(p.read_bytes() == data for p, data in original_parent.items())
    original = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    monkeypatch.setattr(
        "colorref.llm_clients.build_client",
        lambda _: pytest.fail("CPU/completed run must not load model"),
    )
    assert runner.execute(directory, report_only=True) == result
    assert runner.execute(directory) == result
    assert all(p.read_bytes() == data for p, data in original.items())
    assert all(e["difference"] == 0 for e in result["effects"])


def test_backend_failure_stays_pending_and_blank_feedback_is_completed(
    prepared, monkeypatch
):
    _, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    monkeypatch.setattr(
        "colorref.llm_clients.build_client", lambda _: Client(blank_at=2, fail_at=3)
    )
    with pytest.raises(RuntimeError, match="pending"):
        runner.execute(directory)
    result = json.loads((directory / "metrics/teacher_analysis.json").read_text())
    assert result["completed"] == 2
    rows = runner.load_rows(directory, plan, runner.load_plan(directory)[2])
    assert sum(not r["metrics"]["nonempty"] for r in rows.values()) == 1
    blank = next(
        p
        for p in directory.glob("raw_outputs/responses/*.json")
        if not json.loads(p.read_text())["raw_response"]
    )
    before = blank.read_bytes()
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: Client())
    result = runner.execute(directory)
    assert result["completed"] == len(plan["tasks"]) and blank.read_bytes() == before


def test_tamper_unknown_files_and_model_revision_guards(prepared, monkeypatch):
    _, cfg, plan, snapshot = prepared
    directory = runner.create_run(cfg, plan, snapshot)
    monkeypatch.setattr("colorref.llm_clients.build_client", lambda _: Client())
    runner.execute(directory, limit=1)
    monkeypatch.setattr(
        "colorref.llm_clients.build_client", lambda _: Client(revision="changed")
    )
    with pytest.raises(ValueError, match="Model revision changed"):
        runner.execute(directory)
    path = runner.checkpoint_path(directory, plan["tasks"][0])
    original = path.read_bytes()
    bad = json.loads(original)
    bad["metrics"]["certified_preservation"] = False
    runner.write_json(path, bad)
    with pytest.raises(ValueError, match="frozen task/score"):
        runner.execute(directory, report_only=True)
    path.write_bytes(original)
    unknown = directory / "raw_outputs/responses/unknown.json"
    unknown.write_text("{}")
    with pytest.raises(ValueError, match="Unknown"):
        runner.execute(directory, report_only=True)
    unknown.unlink()
    bad = json.loads((directory / "inputs/plan.json").read_text())
    bad["tasks"][0]["clause_budget"] = 0
    runner.write_json(directory / "inputs/plan.json", bad)
    with pytest.raises(ValueError, match="integrity"):
        runner.load_plan(directory)


def test_snapshot_independence_and_cli_dry_run_production_counts(
    tmp_path, monkeypatch, capsys
):
    parent = make_parent(tmp_path, quota=16)
    monkeypatch.setattr(
        "colorref.llm_clients.build_client",
        lambda _: pytest.fail("Dry-run cannot load model"),
    )
    monkeypatch.setattr(
        sys, "argv", ["runner", "--parent-run", str(parent), "--dry-run"]
    )
    runner.main()
    result = json.loads(capsys.readouterr().out)
    assert result["evaluation_examples"] == 60 and result["generations"] == 480
    assert len(result["demonstration_ids"]) == 4 and result["exclusions"] == []
    assert result["clause_budget_covers_supplied_directions"]
    cfg, plan, snapshot = runner.prepare_parent(parent)
    cfg["output"]["run_root"] = str(tmp_path / "independent")
    plan = build_plan(cfg, snapshot, plan["templates"])
    directory = runner.create_run(cfg, plan, snapshot)
    parent.rename(parent.with_name(parent.name + "_moved"))
    assert runner.execute(directory, report_only=True)["completed"] == 0


def test_empty_report_and_available_pair_cluster_denominators(prepared):
    _, cfg, plan, _ = prepared
    result = analyze(cfg, plan, {})
    assert result["common_quartets"] == 0 and result["diagnostics"] == []
    assert all(r["pending"] == r["planned"] for r in result["completion"])
    assert all(e["difference"] is None for e in result["effects"])
    rows = {t["condition_id"]: score(t, t["oracle_feedback"]) for t in plan["tasks"]}
    missing = next(t for t in plan["tasks"] if t["condition"] == "restricted_4")
    del rows[missing["condition_id"]]
    result = analyze(cfg, plan, rows)
    assert result["common_quartets"] == len(plan["tasks"]) // 4 - 1
    available = next(
        e
        for e in result["effects"]
        if e["cohort"] == "available_pairs"
        and e["left"] == "natural_0"
        and e["right"] == "natural_4"
    )
    common = next(
        e
        for e in result["effects"]
        if e["cohort"] == "common_quartets"
        and e["left"] == "natural_0"
        and e["right"] == "natural_4"
    )
    assert available["cases"] == 16 and common["cases"] == 15
    assert available["examples"] == common["examples"] == 8
    assert available["interval"] == [0.0, 0.0]
    json.dumps(result, allow_nan=False)


def test_cluster_effect_keeps_both_bandwidths_with_each_example(prepared):
    _, cfg, plan, _ = prepared
    bad_ids = {
        next(e["example_id"] for e in plan["evaluation"] if e["regime_label"] == r)
        for r in REGIMES
    }
    rows = {
        t["condition_id"]: score(
            t,
            ""
            if t["condition"] == "natural_0" and t["example_id"] in bad_ids
            else t["oracle_feedback"],
        )
        for t in plan["tasks"]
    }
    result = analyze(cfg, plan, rows)
    effect = next(
        e
        for e in result["effects"]
        if e["cohort"] == "common_quartets"
        and e["left"] == "natural_0"
        and e["right"] == "natural_4"
    )
    assert effect["examples"] == 8 and effect["cases"] == 16
    assert effect["difference"] == 0.5
    assert effect["interval"][0] < 0.5 < effect["interval"][1]
    assert effect["interval"][1] - effect["interval"][0] > 0.5


@pytest.mark.parametrize(
    "kind", ["description_overlap", "state_overlap", "empty_oracle"]
)
def test_input_only_exclusions_and_declared_configuration(prepared, kind):
    _, cfg, plan, snapshot = prepared
    snapshot = copy.deepcopy(snapshot)
    demo = plan["demonstrations"][0]
    chosen = next(
        e for e in plan["evaluation"] if e["regime_label"] == demo["regime_label"]
    )
    changed = next(
        e
        for e in snapshot["plan"]["examples"]
        if e["example_id"] == chosen["example_id"]
    )
    if kind == "description_overlap":
        changed["raw_name"] = demo["raw_name"]
    elif kind == "state_overlap":
        changed["hex"] = demo["hex"]
        changed["shared_start_hex"] = demo["shared_start_hex"]
        changed["shared_start_state"] = color_from_hex(demo["shared_start_hex"])
    else:
        changed["hex"] = changed["shared_start_hex"]
    snapshot["plan"]["tasks"] = build_tasks(
        snapshot["config"], snapshot["plan"]["examples"]
    )
    snapshot["metadata"]["plan_sha256"] = plan_digest([snapshot["plan"]])
    rebuilt = build_plan(cfg, snapshot, plan["templates"])
    assert len(rebuilt["evaluation"]) == 7
    assert any(e["example_id"] == chosen["example_id"] for e in rebuilt["exclusions"])
    altered = copy.deepcopy(cfg)
    altered["study"]["bandwidths"] = [1]
    with pytest.raises(ValueError, match="declared protocol"):
        build_plan(altered, snapshot, plan["templates"])
