"""Acceptance checks for traceable, read-only plotting of current run checkpoints."""

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from colorref.interface_study import REGIMES, build_tasks, next_prompt, score_record
from colorref.quantifier_study import plan_digest
from colorref.saved_trajectory_figures import load_saved_trajectories, select_illustrations


def fixture(root):
    cfg = {
        "seed": 113,
        "study": {"design": "grounding_replication", "examples_per_regime": 1,
                  "variants": [{"id": "hex", "output_space": "hex"}]},
        "execution": {"max_turns": 3, "convergence_delta_e": 5},
        "teacher": {"type": "axis_oracle", "max_feedback_constraints": 3,
                    "min_delta": {"lab_l": 2, "lab_a": 3, "lab_b": 3, "hsv_s": 0.05}},
        "model": {"model_name": "TEST FIXTURE", "temperature": 0,
                  "enable_thinking": False, "max_tokens": 64},
    }
    templates = {"hex": {
        "initial": "Description: {raw_name}. Answer #RRGGBB.",
        "revision": "Description: {raw_name}. Previous: {previous_guess}. Feedback: {feedback}.",
    }}
    examples = [{"example_id": str(i), "raw_name": f"TEST FIXTURE {i}",
                 "hex": "#35734c", "regime_label": regime} for i, regime in enumerate(REGIMES)]
    tasks = build_tasks(cfg, examples)
    plan = {"templates": templates, "examples": examples, "tasks": tasks}
    metadata = {"schema_version": 1, "run_id": "TEST_RUN", "model": cfg["model"],
                "plan_sha256": plan_digest([plan]), "config_sha256": plan_digest([cfg])}
    (root / "inputs").mkdir()
    (root / "raw_outputs/games").mkdir(parents=True)
    (root / "inputs/plan.json").write_text(json.dumps(plan))
    (root / "metadata.json").write_text(json.dumps(metadata))
    (root / "config.yaml").write_text(yaml.safe_dump(cfg))
    for task in tasks:
        records = []
        for text in ("#5b8ec7", "#4c866e", "#3c795a", "#35734c"):
            prompt, feedback = next_prompt(task, records, cfg, templates)
            records.append(score_record(task, records, prompt, feedback, text))
        path = root / "raw_outputs/games" / f"{task['slot']:04d}.json"
        path.write_text(json.dumps({"run_id": "TEST_RUN", "condition_id": task["condition_id"],
                                    "records": records}))
    return cfg, templates, tasks


class SavedTrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cfg, self.templates, self.tasks = fixture(self.root)
        self.path = self.root / "raw_outputs/games/0000.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_real_feedback_response_and_sources_without_writing_run(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        cases, manifest = load_saved_trajectories(self.root)
        self.assertEqual(len(cases), 4)
        self.assertEqual(cases[0]["records"][0]["feedback"], None)
        self.assertEqual(cases[0]["records"][1]["feedback"],
                         json.loads(self.path.read_text())["records"][1]["feedback"])
        self.assertEqual(cases[0]["records"][1]["raw_response"], "#4c866e")
        self.assertIn("raw_outputs/games/0000.json", cases[0]["source_sha256"])
        self.assertEqual(len(manifest["statuses"]), 4)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_rejects_changed_feedback_and_color_even_with_valid_source_hashes(self):
        saved = json.loads(self.path.read_text())
        original = self.path.read_text()
        saved["records"][1]["feedback"]["text"] = "Invented correction"
        self.path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "Checkpoint does not match"):
            load_saved_trajectories(self.root)
        saved = json.loads(original)
        saved["records"][1]["displayed_state"]["lab"][1] += 1
        self.path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "Checkpoint does not match"):
            load_saved_trajectories(self.root)

    def test_rejects_changed_plan_and_cross_run_checkpoint(self):
        saved = json.loads(self.path.read_text())
        saved["run_id"] = "OTHER_RUN"
        self.path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "another run"):
            load_saved_trajectories(self.root)
        plan_path = self.root / "inputs/plan.json"
        plan = json.loads(plan_path.read_text())
        plan["examples"][0]["raw_name"] = "Changed description"
        plan_path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "integrity"):
            load_saved_trajectories(self.root)

    def test_pending_failed_and_missing_games_remain_visible_not_imputed(self):
        saved = json.loads(self.path.read_text())
        saved["records"] = saved["records"][:1]
        self.path.write_text(json.dumps(saved))
        failure_path = self.root / "raw_outputs/games/0001.json"
        task = self.tasks[1]
        prompt, feedback = next_prompt(task, [], self.cfg, self.templates)
        failure_path.write_text(json.dumps({"run_id": "TEST_RUN", "condition_id": task["condition_id"],
            "records": [score_record(task, [], prompt, feedback, "No color output")]}))
        (self.root / "raw_outputs/games/0002.json").unlink()
        cases, manifest = load_saved_trajectories(self.root)
        self.assertEqual(len(cases), 1)
        self.assertCountEqual([x["status"] for x in manifest["statuses"]],
                              ["pending", "parse_failure", "missing", "full_parsed"])

    def test_selection_balances_regimes_without_success_ranking_and_is_stable(self):
        cases, _ = load_saved_trajectories(self.root)
        chosen = select_illustrations(cases, n=4)
        self.assertEqual(chosen, select_illustrations(list(reversed(cases)), n=4))
        self.assertEqual([x["task"]["example"]["regime_label"] for x in chosen], list(REGIMES))
        self.assertEqual(len(select_illustrations(cases, example_id="0")), 1)
        with self.assertRaisesRegex(ValueError, "no unique"):
            select_illustrations(cases, example_id="absent")


if __name__ == "__main__":
    unittest.main()
