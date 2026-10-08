"""Verify a model change cannot change frozen stimuli or reuse fitted outputs."""
import copy
import sys
import unittest
from pathlib import Path
import yaml
from colorref.magnitude_control import build_plan

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_magnitude_replication import prepare_config, MODEL, REVISION


class ReplicationTests(unittest.TestCase):
    def test_exact_stimulus_identity_and_independent_model(self):
        cfg = yaml.safe_load((ROOT / "configs/experiments/magnitude_control_a100_40gb_pilot.yaml").read_text())
        cfg["study"].update(calibration_colors=32, evaluation_colors=128, unfitted_cutpoints=[9, 18])
        template = (ROOT / cfg["study"]["template_path"]).read_text()
        plan = build_plan(cfg, template)
        before = copy.deepcopy(cfg)
        result = prepare_config(cfg, plan, {"run_id": "fixture", "plan_sha256": "p", "config_sha256": "c"})
        self.assertEqual(cfg, before)
        self.assertEqual(build_plan(result, template), plan)
        self.assertEqual(result["model"]["model_name"], MODEL)
        self.assertEqual(result["model"]["revision"], REVISION)
        self.assertFalse(result["replication_sources"]["selection_uses_outputs"])
        altered = copy.deepcopy(plan)
        altered["evaluation_cases"].reverse()
        with self.assertRaisesRegex(ValueError, "frozen stimuli"):
            prepare_config(cfg, altered, {"run_id": "fixture", "plan_sha256": "p", "config_sha256": "c"})


if __name__ == "__main__":
    unittest.main()
