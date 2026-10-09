"""CPU acceptance tests for matching, exact controls, and safe resume."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from colorref.quantifier_study import build_conditions, score_prediction

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_quantifier_study.py"
spec = importlib.util.spec_from_file_location("study_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@contextlib.contextmanager
def inference_modules(values):
    # Restore only the replaced keys; patch.dict(sys.modules) would also unload
    # NumPy/PyArrow modules imported by report export inside the context.
    missing = object()
    previous = {key: sys.modules.get(key, missing) for key in values}
    sys.modules.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


def config_and_templates():
    cfg = yaml.safe_load(
        (ROOT / "configs/experiments/quantifier_study_a100_40gb.yaml").read_text()
    )
    templates = {
        item["id"]: (ROOT / item["template_path"]).read_text()
        for item in cfg["study"]["prompt_variants"]
    }
    return cfg, templates


def fixture_parser(text, *, output_space):
    assert output_space == "lab"
    match = re.fullmatch(r"LAB\(([^)]+)\)", text)
    if not match:
        return {
            "parse_ok": False,
            "parse_reason": "fixture_parse_failure",
            "hex": None,
            "lab": None,
        }
    return {
        "parse_ok": True,
        "parse_reason": None,
        "hex": "#808080",
        "lab": tuple(float(x) for x in match.group(1).split(",")),
    }


class FixtureClient:
    """Known responses test plumbing, not model performance."""

    def __init__(self, conditions, fail_after=None):
        self.by_prompt = {condition["prompt"]: condition for condition in conditions}
        self.calls = []
        self.fail_after = fail_after

    def generate(self, prompt, **kwargs):
        if self.fail_after is not None and len(self.calls) == self.fail_after:
            return SimpleNamespace(error="simulated execution interruption")
        self.calls.append(prompt)
        condition = self.by_prompt[prompt]
        if (
            condition["prompt_variant"] == "plain"
            and condition["base_id"] == "neutral_low"
            and condition["quantifier"] == "a_little"
            and condition["direction"] == "lighter"
        ):
            text = "intentionally malformed fixture response"
        else:
            lab = list(condition["expected_lab"] or condition["base_lab"])
            if condition["condition_kind"] == "wording":
                from colorref.quantifiers import DIRECTION_SPECS

                direction = DIRECTION_SPECS[condition["direction"]]
                step = {"baseline": 20, "a_little": 5, "somewhat": 10, "much": 30}[
                    condition["quantifier"]
                ]
                lab[direction.index] += direction.sign * step
            text = f"LAB({lab[0]}, {lab[1]}, {lab[2]})"
        return SimpleNamespace(
            text=text,
            model_name="fixture",
            provider="fixture",
            latency_s=0.0,
            error=None,
        )


class MatchedStudyTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.templates = config_and_templates()
        self.conditions = build_conditions(self.cfg, self.templates)

    def test_plan_matches_every_instruction_and_counts_controls(self):
        self.assertEqual(len(self.conditions), 888)
        self.assertEqual(len({x["condition_id"] for x in self.conditions}), 888)
        self.assertEqual(
            Counter(x["condition_kind"] for x in self.conditions),
            {"wording": 576, "numeric": 288, "no_change": 24},
        )
        for left, right in zip(self.conditions[::2], self.conditions[1::2]):
            self.assertEqual(left["pair_key"], right["pair_key"])
            self.assertNotEqual(left["prompt_variant"], right["prompt_variant"])
            self.assertEqual(left["instruction"], right["instruction"])
            self.assertEqual(left["expected_lab"], right["expected_lab"])
            self.assertEqual(left["base_lab"], right["base_lab"])
        self.assertEqual(self.conditions, build_conditions(self.cfg, self.templates))
        altered = copy.deepcopy(self.cfg)
        altered["seed"] += 1
        self.assertNotEqual(
            [x["condition_id"] for x in self.conditions],
            [x["condition_id"] for x in build_conditions(altered, self.templates)],
        )

    def test_numeric_controls_have_exact_signed_targets_and_no_change_is_separate(self):
        for condition in self.conditions:
            if condition["expected_lab"] is not None:
                scored = score_prediction(condition, tuple(condition["expected_lab"]))
                self.assertEqual(scored["control_error_delta_e"], 0)
                self.assertEqual(scored["control_exact_within_0_01"], 1)
                self.assertEqual(scored["control_within_1"], 1)
                self.assertEqual(scored["projected_control_error_delta_e"], 0)
                if condition["condition_kind"] == "numeric":
                    self.assertEqual(scored["numeric_step_ratio"], 1)
                else:
                    self.assertEqual(scored["native_movement_norm"], 0)
                    self.assertEqual(scored["projected_movement_norm"], 0)
                    self.assertNotIn("direction_followed", scored)

    def test_wrong_sign_and_no_change_drift_are_not_successes(self):
        numeric = next(
            x
            for x in self.conditions
            if x["condition_kind"] == "numeric"
            and x["direction"] == "more_blue"
            and x["requested_numeric_step"] == 5
        )
        base = numeric["base_lab"]
        scored = score_prediction(numeric, (base[0], base[1], base[2] + 5))
        self.assertEqual(scored["numeric_step_ratio"], -1)
        self.assertEqual(scored["direction_followed"], 0)
        self.assertEqual(scored["control_error_delta_e"], 10)
        noop = next(x for x in self.conditions if x["condition_kind"] == "no_change")
        base = noop["base_lab"]
        scored = score_prediction(noop, (base[0] + 5, base[1], base[2]))
        self.assertEqual(scored["control_error_delta_e"], 5)
        self.assertEqual(scored["control_within_1"], 0)

    def test_unsafe_anchors_or_control_targets_are_rejected(self):
        altered = copy.deepcopy(self.cfg)
        altered["study"]["base_colors"][0]["lab"] = [50, 0, 127]
        with self.assertRaisesRegex(ValueError, "projection error"):
            build_conditions(altered, self.templates)
        altered = copy.deepcopy(self.cfg)
        altered["study"]["numeric_steps"] = [5, 100]
        with self.assertRaises(ValueError):
            build_conditions(altered, self.templates)

    def test_saved_model_or_prompt_changes_cannot_silently_mix_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = copy.deepcopy(self.cfg)
            cfg["output"]["run_root"] = directory
            run_dir = runner.create_run(
                cfg, self.templates, self.conditions, Path("fixture.yaml")
            )
            runner.load_plan(run_dir)
            path = run_dir / "config.yaml"
            altered = copy.deepcopy(cfg)
            altered["model"]["model_name"] = "a-different-model"
            path.write_text(yaml.safe_dump(altered))
            with self.assertRaisesRegex(ValueError, "configuration"):
                runner.load_plan(run_dir)
            path.write_text(yaml.safe_dump(cfg))
            templates = dict(self.templates)
            templates["plain"] += " changed"
            (run_dir / "inputs/prompts.json").write_text(json.dumps(templates))
            with self.assertRaisesRegex(ValueError, "snapshot"):
                runner.load_plan(run_dir)

    def test_execution_error_preserves_progress_and_does_not_complete_failed_call(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = copy.deepcopy(self.cfg)
            cfg["output"]["run_root"] = directory
            run_dir = runner.create_run(
                cfg, self.templates, self.conditions, Path("fixture.yaml")
            )
            rows = []
            client = FixtureClient(self.conditions, fail_after=5)
            with self.assertRaisesRegex(RuntimeError, "remains pending"):
                runner.run_pending(
                    client,
                    fixture_parser,
                    cfg,
                    self.conditions,
                    run_dir,
                    run_dir.name,
                    rows,
                )
            restored = runner.read_trial_records(
                run_dir / "raw_outputs/responses.jsonl", self.conditions
            )
            self.assertEqual(len(restored), 5)
            self.assertEqual(
                len(runner.pending_conditions(self.conditions, restored)), 883
            )

    def test_resume_repairs_only_unterminated_tail_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = copy.deepcopy(self.cfg)
            cfg["output"]["run_root"] = directory
            run_dir = runner.create_run(
                cfg, self.templates, self.conditions, Path("fixture.yaml")
            )
            rows = []
            runner.run_pending(
                FixtureClient(self.conditions),
                fixture_parser,
                cfg,
                self.conditions[:2],
                run_dir,
                run_dir.name,
                rows,
            )
            path = run_dir / "raw_outputs/responses.jsonl"
            original = path.read_bytes()
            path.write_bytes(original + b'{"interrupted":')
            with self.assertRaises(ValueError):
                runner.read_trial_records(path, self.conditions)
            self.assertEqual(
                len(
                    runner.read_trial_records(
                        path, self.conditions, repair_trailing=True
                    )
                ),
                2,
            )
            self.assertEqual(path.read_bytes(), original)
            # A complete final JSON object without its newline must not be discarded.
            path.write_bytes(original.rstrip(b"\n"))
            self.assertEqual(
                len(
                    runner.read_trial_records(
                        path, self.conditions, repair_trailing=True
                    )
                ),
                2,
            )
            self.assertTrue(path.read_bytes().endswith(b"\n"))
            path.write_bytes(original + original.splitlines(keepends=True)[0])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                runner.read_trial_records(path, self.conditions, repair_trailing=True)
            path.write_bytes(original + b'{"broken":\n')
            with self.assertRaises(ValueError):
                runner.read_trial_records(path, self.conditions, repair_trailing=True)

    def test_full_cli_loads_once_per_invocation_resumes_and_reports_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = copy.deepcopy(self.cfg)
            cfg["output"]["run_root"] = str(Path(directory) / "runs")
            config_path = Path(directory) / "config.yaml"
            config_path.write_text(yaml.safe_dump(cfg))
            clients = []

            def factory(_cfg):
                client = FixtureClient(self.conditions)
                clients.append(client)
                return client

            modules = {
                "colorref.games": SimpleNamespace(_parse_and_convert=fixture_parser),
                "colorref.llm_clients": SimpleNamespace(build_client=factory),
            }
            with inference_modules(modules), patch.object(runner.logger, "info"):
                with patch(
                    "sys.argv", ["runner", "--config", str(config_path), "--limit", "8"]
                ):
                    runner.main()
                self.assertEqual(len(clients), 1)
                self.assertEqual(len(clients[0].calls), 8)
                run_dir = next(Path(cfg["output"]["run_root"]).iterdir())
                with patch("sys.argv", ["runner", "--resume", str(run_dir)]):
                    runner.main()
                self.assertEqual(len(clients), 2)
                self.assertEqual(len(clients[1].calls), 880)
            raw = runner.read_trial_records(
                run_dir / "raw_outputs/responses.jsonl", self.conditions
            )
            self.assertEqual(len(raw), 888)
            self.assertEqual(sum(not x["parse_ok"] for x in raw), 1)
            report = (run_dir / "reports/study_summary.md").read_text()
            self.assertIn("Completed: 888 / 888", report)
            self.assertIn("Matched completed pairs: 444 / 444", report)
            self.assertIn("| a_little | 72 | 71 |", report)
            self.assertIn(
                "| numeric_5 | 72 | 72 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 |",
                report,
            )
            self.assertTrue((run_dir / "metrics/study_trials.parquet").exists())
            self.assertTrue((run_dir / "metrics/paired_trials.csv").exists())
            with (
                inference_modules(
                    {"colorref.games": None, "colorref.llm_clients": None}
                ),
                patch.object(runner.logger, "info"),
            ):
                with patch("sys.argv", ["runner", "--report-only", str(run_dir)]):
                    runner.main()
                with patch("sys.argv", ["runner", "--resume", str(run_dir)]):
                    runner.main()
            self.assertEqual(len(clients), 2)

    def test_dry_run_requires_no_inference_modules_and_creates_no_run(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = copy.deepcopy(self.cfg)
            cfg["output"]["run_root"] = str(Path(directory) / "must-not-exist")
            config_path = Path(directory) / "config.yaml"
            config_path.write_text(yaml.safe_dump(cfg))
            output = io.StringIO()
            with inference_modules(
                {"colorref.games": None, "colorref.llm_clients": None}
            ):
                with (
                    patch(
                        "sys.argv",
                        ["runner", "--config", str(config_path), "--dry-run"],
                    ),
                    contextlib.redirect_stdout(output),
                ):
                    runner.main()
            self.assertEqual(json.loads(output.getvalue())["conditions"], 888)
            self.assertFalse(Path(cfg["output"]["run_root"]).exists())


if __name__ == "__main__":
    unittest.main()
