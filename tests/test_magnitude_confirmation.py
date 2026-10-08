"""CPU acceptance checks for the unfitted comparator and larger frozen study."""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from colorref.magnitude_control import ARMS, build_plan, evaluation_arms, evaluation_tasks, fit_mapping, score, unfitted_phrase, validate_config
from colorref.magnitude_reports import analyze, report
from colorref.quantifiers import DIRECTION_SPECS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_magnitude_confirmation as preparation
import run_magnitude_control as runner


def inputs(directory):
    cfg = yaml.safe_load((ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml").read_text())
    cfg["output"]["run_root"] = str(directory)
    cfg["study"].update(calibration_colors=2, evaluation_colors=3, unfitted_cutpoints=[9, 18])
    cfg["analysis"]["resamples"] = 100
    template = (ROOT / cfg["study"]["template_path"]).read_text()
    return cfg, build_plan(cfg, template)


def answer(task):
    lab = [round(x, 6) for x in task["start"]["lab"]]
    if task.get("expected_numeric_lab") is not None:
        lab = task["expected_numeric_lab"]
    else:
        d = DIRECTION_SPECS[task["direction"]]
        wording = task.get("selected_wording", task.get("wording"))
        lab[d.index] += d.sign * {"baseline": 20, "a_little": 5, "somewhat": 10, "much": 30}[wording]
    return "LAB({:.6f}, {:.6f}, {:.6f})".format(*lab)


def calibration(plan):
    return {t["condition_id"]: score(t, answer(t)) for t in plan["calibration_tasks"]}


class ConfirmationTests(unittest.TestCase):
    def test_fixed_rule_boundaries_and_validation(self):
        self.assertEqual([unfitted_phrase(x, [9, 18]) for x in (6, 8.999, 9, 12, 17.999, 18, 24)], ["a_little", "a_little", "somewhat", "somewhat", "somewhat", "much", "much"])
        cfg, _ = inputs("runs")
        for cuts in ([18, 9], [9], [0, 18], [True, 18], [float('nan'), 18]):
            cfg["study"]["unfitted_cutpoints"] = cuts
            with self.assertRaises(ValueError):
                validate_config(cfg)

    def test_unfitted_messages_independent_of_fitted_map(self):
        cfg, plan = inputs("runs")
        mapping = fit_mapping(cfg, plan, calibration(plan))
        a = evaluation_tasks(cfg, plan, mapping)
        other = copy.deepcopy(mapping)
        for rows in other["table"].values():
            for row in rows:
                row["usable"] = False
        b = evaluation_tasks(cfg, plan, other)
        self.assertEqual([t for t in a if t["arm"] == "unfitted"], [t for t in b if t["arm"] == "unfitted"])
        self.assertEqual(set(t["arm"] for t in a), {"bare", "unfitted", "calibrated", "numeric"})
        self.assertEqual(a, evaluation_tasks(cfg, plan, mapping))
        self.assertTrue(all(t["status"] == "unavailable_calibration" for t in b if t["arm"] == "calibrated"))

    def test_legacy_defaults_stay_three_arm(self):
        cfg, _ = inputs("runs")
        cfg["study"].pop("unfitted_cutpoints")
        plan = build_plan(cfg, (ROOT / cfg["study"]["template_path"]).read_text())
        tasks = evaluation_tasks(cfg, plan, fit_mapping(cfg, plan, calibration(plan)))
        self.assertEqual(evaluation_arms(cfg), ARMS)
        self.assertEqual([t["arm"] for t in tasks[:3]], list(ARMS))

    def test_report_primary_clusters_and_missing_fourth_arm(self):
        cfg, plan = inputs("runs")
        cal = calibration(plan)
        mapping = fit_mapping(cfg, plan, cal)
        tasks = evaluation_tasks(cfg, plan, mapping)
        rows = {t["condition_id"]: score(t, answer(t)) for t in tasks if t["status"] == "generate"}
        result = analyze(cfg, plan, cal, mapping, tasks, rows)
        self.assertEqual(result["common_starting_colors"], 3)
        self.assertEqual(result["common_quartets"], len(plan["evaluation_cases"]))
        primary = next(r for r in result["effects"] if r["cohort"] == "common_quartets" and r["left"] == "unfitted" and r["right"] == "calibrated")
        self.assertEqual(primary["starting_colors"], 3)
        self.assertIn("unfitted → calibrated", report(result, "fixture"))
        removed = next(t for t in tasks if t["arm"] == "unfitted")
        del rows[removed["condition_id"]]
        result = analyze(cfg, plan, cal, mapping, tasks, rows)
        self.assertEqual(result["common_quartets"], len(plan["evaluation_cases"])-1)
        self.assertEqual(next(r for r in result["evaluation"] if r["arm"] == "unfitted")["pending"], 1)

    def test_preparation_excludes_all_prior_colors_and_increases_clusters(self):
        cfg, plan = inputs("runs")
        cfg["study"].pop("unfitted_cutpoints")
        transfer = {"starts": [{"state": {"hex": "#35969a"}}]}
        new = preparation.prepare_config(cfg, plan, transfer)
        frozen = build_plan(new, plan["template"])
        self.assertEqual(len(frozen["splits"]["calibration"]), 32)
        self.assertEqual(len(frozen["splits"]["evaluation"]), 128)
        self.assertEqual(len(frozen["calibration_tasks"]), 768)
        prior = {c["state"]["hex"] for split in plan["splits"].values() for c in split} | {"#35969a"}
        new_colors = {c["state"]["hex"] for split in frozen["splits"].values() for c in split}
        self.assertFalse(prior & new_colors)
        self.assertEqual(new["study"]["unfitted_cutpoints"], [9, 18])

    def test_resumable_four_arm_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, plan = inputs(folder)
            directory = runner.create_run(cfg, plan, Path("fixture.yaml"))
            class Client:
                calls = 0
                def generate(self, prompt, **kwargs):
                    self.calls += 1
                    lab = list(map(float, re.search(r"Current color.*LAB\(([^)]+)\)", prompt)[1].split(",")))
                    instruction = re.search(r"Instruction: ([^\n]+)", prompt)[1]
                    numeric = re.match(r"(Increase|Decrease) the ([Lab]) coordinate by exactly ([\d.]+)", instruction)
                    if numeric:
                        lab[("L", "a", "b").index(numeric[2])] += (1 if numeric[1] == "Increase" else -1) * float(numeric[3])
                    else:
                        d = next(d for d in DIRECTION_SPECS.values() if instruction.endswith(d.phrase + "."))
                        lab[d.index] += d.sign * (5 if "a little" in instruction else 10 if "somewhat" in instruction else 30 if "much" in instruction else 20)
                    return SimpleNamespace(text="LAB({:.6f}, {:.6f}, {:.6f})".format(*lab), error=None, raw={}, latency_s=1, model_name="fixture", provider="mock")
            client = Client()
            with patch("colorref.llm_clients.build_client", return_value=client):
                runner.execute(directory, limit=3)
                runner.execute(directory)
            result = json.loads((directory / "metrics/magnitude_analysis.json").read_text())
            self.assertEqual(result["calibration_completed"], len(plan["calibration_tasks"]))
            self.assertEqual(result["common_quartets"], len(plan["evaluation_cases"]))
            calls = client.calls
            with patch("colorref.llm_clients.build_client", side_effect=AssertionError("Completed run must not load a model")):
                runner.execute(directory)
            self.assertEqual(calls, client.calls)


if __name__ == "__main__":
    unittest.main()
