"""CPU-only acceptance tests; simulated outputs are not model evidence."""

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from colorref.teacher_receiver import ARMS, analyze, build_plan, paired, score
from colorref.teacher_fidelity import score as teacher_score
from tests.test_teacher_fidelity import Client, make_parent

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_teacher_fidelity_study as teacher  # noqa: E402
import run_teacher_receiver_study as runner  # noqa: E402


class Guesser:
    def __init__(self, blank_at=None, fail_at=None, revision="fixture_revision"):
        self.calls = 0
        self.blank_at, self.fail_at = blank_at, fail_at
        self._model_and_tokenizer = (
            SimpleNamespace(config=SimpleNamespace(_commit_hash=revision)),
            None,
        )

    def generate(self, prompt, **kwargs):
        self.calls += 1
        assert kwargs == {"max_tokens": 64, "temperature": 0.0}
        if self.calls == self.fail_at:
            return SimpleNamespace(error="offline")
        return SimpleNamespace(
            text="" if self.calls == self.blank_at else "#808080",
            error=None,
            model_name="mock",
            provider="mock",
            latency_s=0,
            raw={"generated_tokens": 4, "prompt_tokens": 100, "finish_reason": "eos"},
        )


def prepare(tmp_path, monkeypatch, quota=3):
    import colorref.llm_clients

    parent = make_parent(tmp_path, quota)
    cfg, plan, snapshot = teacher.prepare_parent(
        parent, output_root=tmp_path / "teacher"
    )
    teacher_run = teacher.create_run(cfg, plan, snapshot)
    monkeypatch.setattr(colorref.llm_clients, "build_client", lambda _: Client())
    teacher.execute(teacher_run)
    cfg, plan, snapshot = runner.prepare_parent(
        teacher_run, output_root=tmp_path / "receiver"
    )
    return teacher_run, cfg, plan, snapshot


def test_matched_tasks_original_feedback_and_no_hidden_target(tmp_path, monkeypatch):
    _, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    assert len(plan["tasks"]) == 80
    assert build_plan(cfg, snapshot) == plan
    assert cfg["model"]["max_tokens"] == 64
    for case in {t["case_id"] for t in plan["tasks"]}:
        tasks = [t for t in plan["tasks"] if t["case_id"] == case]
        assert {t["arm"] for t in tasks} == set(ARMS)
        assert all(
            t["example"] == tasks[0]["example"]
            and t["required"] == tasks[0]["required"]
            for t in tasks
        )
        oracle_text = next(
            t["oracle_feedback"]
            for t in snapshot["plan"]["tasks"]
            if t["case_id"] == case
        )
        for task in tasks:
            expected = (
                snapshot["rows"][task["teacher_condition_id"]]["raw_response"]
                if task["teacher_condition_id"]
                else oracle_text
            )
            assert task["feedback_text"] == expected
            assert task["feedback_text"] in task["prompt"]
            assert task["example"]["hex"] not in task["prompt"]
            assert "oracle_constraints" not in task["prompt"]
    first = plan["tasks"][:10]
    assert len({t["example_id"] for t in first}) == 1
    assert {t["bandwidth"] for t in first} == {1, 3}


def test_require_complete_teacher_but_keep_empty_text(tmp_path, monkeypatch):
    _, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    bad = copy.deepcopy(snapshot)
    bad["rows"].pop(next(iter(bad["rows"])))
    with pytest.raises(ValueError, match="every planned"):
        build_plan(cfg, bad)
    task = snapshot["plan"]["tasks"][0]
    for text in (
        "",
        "Feedback: Your guess is darker than the target color.",
        "The target is " + task["example"]["hex"],
    ):
        modified = copy.deepcopy(snapshot)
        old = modified["rows"][task["condition_id"]]
        modified["rows"][task["condition_id"]] = {**old, **teacher_score(task, text)}
        frozen = build_plan(cfg, modified)
        chosen = [
            t
            for t in frozen["tasks"]
            if t["teacher_condition_id"] == task["condition_id"]
        ][0]
        assert chosen["feedback_text"] == text and text in chosen["prompt"]
        assert chosen["teacher_empty"] == (not text.strip())
        assert chosen["teacher_mentions_target_hex"] == (task["example"]["hex"] in text)
        assert len(frozen["tasks"]) == len(plan["tasks"])


def test_resume_cpu_reports_and_parent_preservation(tmp_path, monkeypatch):
    import colorref.llm_clients

    parent, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    hashes = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in parent.rglob("*")
        if p.is_file()
    }
    run = runner.create_run(cfg, plan, snapshot)
    clients = []

    def factory(_):
        client = Guesser()
        clients.append(client)
        return client

    monkeypatch.setattr(colorref.llm_clients, "build_client", factory)
    result = runner.execute(run, limit=10)
    assert result["completed"] == 10 and result["common_cases"] == 2
    prefix = {p: p.read_bytes() for p in (run / "raw_outputs/responses").glob("*.json")}
    result = runner.execute(run)
    assert result["completed"] == 80 and result["common_cases"] == 16
    assert [c.calls for c in clients] == [10, 70]
    assert all(p.read_bytes() == data for p, data in prefix.items())
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items()
    )
    frozen = {
        p: p.read_bytes()
        for p in run.rglob("*")
        if p.is_file() and p.parent.name not in {"metrics", "reports"}
    }
    monkeypatch.setattr(
        colorref.llm_clients, "build_client", lambda _: pytest.fail("No model allowed")
    )
    assert runner.execute(run, report_only=True) == result
    assert runner.execute(run) == result
    assert all(p.read_bytes() == data for p, data in frozen.items())
    parent.rename(parent.with_name("moved_parent"))
    assert runner.load_plan(run)[1] == plan


def test_parse_failures_cohorts_and_backend_pending(tmp_path, monkeypatch):
    import colorref.llm_clients

    _, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    run = runner.create_run(cfg, plan, snapshot)
    monkeypatch.setattr(
        colorref.llm_clients, "build_client", lambda _: Guesser(blank_at=1, fail_at=2)
    )
    with pytest.raises(RuntimeError, match="pending"):
        runner.execute(run)
    assert len(list((run / "raw_outputs/responses").glob("*.json"))) == 1
    first = runner.checkpoint_path(run, plan["tasks"][0]).read_bytes()
    monkeypatch.setattr(colorref.llm_clients, "build_client", lambda _: Guesser())
    result = runner.execute(run)
    assert result["completed"] == 80 and result["common_cases"] == 15
    assert (
        len(result["failures"]) == 1
        and sum(s["failed"] for s in result["completion"]) == 1
    )
    assert runner.checkpoint_path(run, plan["tasks"][0]).read_bytes() == first
    bad_arm = plan["tasks"][0]["arm"]
    unaffected = [
        e
        for e in result["effects"]
        if e["cohort"] == "available_pairs" and bad_arm not in (e["left"], e["right"])
    ]
    assert unaffected and all(e["cases"] == 16 for e in unaffected)
    assert all(
        e["cases"] == 15 for e in result["effects"] if e["cohort"] == "common_quintets"
    )


def test_integrity_unknown_checkpoint_and_revision_guard(tmp_path, monkeypatch):
    import colorref.llm_clients

    _, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    run = runner.create_run(cfg, plan, snapshot)
    monkeypatch.setattr(
        colorref.llm_clients, "build_client", lambda _: Guesser(revision="different")
    )
    with pytest.raises(ValueError, match="revision changed"):
        runner.execute(run)
    assert not list((run / "raw_outputs/responses").glob("*.json"))
    monkeypatch.setattr(colorref.llm_clients, "build_client", lambda _: Guesser())
    runner.execute(run, limit=1)
    path = runner.checkpoint_path(run, plan["tasks"][0])
    original = path.read_text()
    row = json.loads(original)
    row["metrics"]["error"] += 1
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="checkpoint differs"):
        runner.execute(run, report_only=True)
    path.write_text(original)
    (run / "raw_outputs/responses/9999.json").write_text("{}")
    with pytest.raises(ValueError, match="Unknown"):
        runner.execute(run, report_only=True)


def test_whole_example_clusters_and_undefined_alignment(tmp_path, monkeypatch):
    _, cfg, plan, snapshot = prepare(tmp_path, monkeypatch)
    rows = {
        t["condition_id"]: score(t, t["example"]["shared_start_hex"], cfg)
        for t in plan["tasks"]
    }
    assert all(
        r["metrics"]["gain"] == 0 and r["metrics"]["alignment"] is None
        for r in rows.values()
    )
    for task in plan["tasks"]:
        if task["arm"] == "oracle":
            rows[task["condition_id"]]["metrics"]["error"] += (
                int(task["example_id"].split("_")[-1]) % 2
            )
    effect = paired(plan["tasks"], rows, "natural_0", "oracle", cfg)
    assert effect["cases"] == 16 and effect["examples"] == 8
    assert effect["interval"] is not None
    result = analyze(cfg, plan, {})
    assert result["common_cases"] == 0
    assert all(s["error"] is None for s in result["primary"])
    one = [
        t for t in plan["tasks"] if t["example_id"] == plan["tasks"][0]["example_id"]
    ]
    assert paired(one, rows, "natural_0", "oracle", cfg)["interval"] is None


def test_production_shape_and_dry_run_no_receiver_model(tmp_path, monkeypatch, capsys):
    import colorref.llm_clients

    parent, cfg, plan, snapshot = prepare(tmp_path, monkeypatch, quota=16)
    assert len(plan["tasks"]) == 600
    assert len({t["example_id"] for t in plan["tasks"]}) == 60
    monkeypatch.setattr(
        colorref.llm_clients,
        "build_client",
        lambda _: pytest.fail("Dry run must not load model"),
    )
    monkeypatch.setattr(
        sys, "argv", ["runner", "--parent-run", str(parent), "--dry-run"]
    )
    runner.main()
    output = json.loads(capsys.readouterr().out)
    assert output["generations"] == 600 and output["cases"] == 120
    assert output["teacher_text_unchanged"] and not output["semantic_label_selection"]
