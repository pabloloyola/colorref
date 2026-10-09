"""CPU checks for fresh selection, strict designs, saved-state reporting and resume."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import yaml
from colorref.interface_study import REGIMES, build_tasks, validate_config
from colorref.interface_study_reports import write_reports

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_grounding_replication as preparation
import run_interface_study as runner


def inputs():
    cfg = yaml.safe_load((ROOT / "configs/experiments/grounding_1000_a100_40gb.yaml").read_text())
    cfg["study"]["examples_per_regime"] = 1
    cfg["analysis"]["resamples"] = 100
    templates = {"hex": {p: (ROOT / cfg["study"]["variants"][0][f"{p}_template_path"]).read_text() for p in ("initial", "revision")}}
    examples = [{"example_id": str(i), "raw_name": "gray", "hex": "#808080", "regime_label": r} for i, r in enumerate(REGIMES)]
    return cfg, templates, examples


class GroundingTests(unittest.TestCase):
    def test_fresh_selection_stable_and_excludes_debug_ids(self):
        frame = pd.DataFrame([dict(example_id=str(i*10+j), raw_name="gray", hex="#808080", regime_label=r) for i, r in enumerate(REGIMES) for j in range(4)])
        excluded = frame.iloc[::4]
        a = preparation.choose(frame, excluded, 2, 113)
        b = preparation.choose(frame.sample(frac=1, random_state=7), excluded, 2, 113)
        self.assertEqual(a.to_dict("records"), b.to_dict("records"))
        self.assertFalse(set(a.example_id) & set(excluded.example_id))
        self.assertEqual(len(a), 8)
        with self.assertRaises(ValueError):
            preparation.choose(frame, excluded, 4, 113)

    def test_explicit_design_and_hex_only_tasks(self):
        cfg, templates, examples = inputs()
        validate_config(cfg, templates)
        self.assertEqual(len(build_tasks(cfg, examples)), 4)
        self.assertEqual({t["variant"] for t in build_tasks(cfg, examples)}, {"hex"})
        cfg["study"].pop("design")
        with self.assertRaises(ValueError):
            validate_config(cfg, templates)

    def test_frozen_run_resume_and_completion_report(self):
        cfg, templates, examples = inputs()
        class Client:
            calls = 0
            def generate(self, *args, **kwargs):
                self.calls += 1
                return SimpleNamespace(text="#808080", error=None, model_name="fixture", provider="mock", latency_s=1.25)
        with tempfile.TemporaryDirectory() as folder:
            cfg["output"]["run_root"] = folder
            directory = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
            frozen, plan, metadata = runner.load_plan(directory)
            saved = runner.load_checkpoints(directory, frozen, plan, metadata)
            client = Client()
            self.assertEqual(runner.run_pending(client, frozen, plan, metadata, directory, saved, 2), 2)
            write_reports(frozen, plan["tasks"], saved, directory)
            partial = json.loads((directory / "metrics/grounding_analysis.json").read_text())
            self.assertEqual(partial["full_parsed"], 0)
            saved = runner.load_checkpoints(directory, frozen, plan, metadata)
            self.assertEqual(runner.run_pending(client, frozen, plan, metadata, directory, saved), 14)
            self.assertEqual(client.calls, 16)
            write_reports(frozen, plan["tasks"], saved, directory)
            final = json.loads((directory / "metrics/grounding_analysis.json").read_text())
            self.assertEqual(final["full_parsed"], 4)
            self.assertEqual(final["estimates"]["gain"]["mean"], 0)
            self.assertEqual(final["mean_generation_latency_s"], 1.25)
            self.assertFalse((directory / "reports/interface_summary.md").exists())

    def test_failed_output_is_not_imputed(self):
        cfg, templates, examples = inputs()
        class Client:
            def generate(self, *args, **kwargs):
                return SimpleNamespace(text="invalid", error=None, model_name="fixture", provider="mock", latency_s=1)
        with tempfile.TemporaryDirectory() as folder:
            cfg["output"]["run_root"] = folder
            d = runner.create_run(cfg, templates, examples, Path("fixture.yaml"))
            frozen, plan, meta = runner.load_plan(d)
            saved = {}
            runner.run_pending(Client(), frozen, plan, meta, d, saved)
            write_reports(frozen, plan["tasks"], saved, d)
            result = json.loads((d / "metrics/grounding_analysis.json").read_text())
            self.assertEqual(result["completed"], 4)
            self.assertEqual(result["parse_failures"], 4)
            self.assertEqual(result["full_parsed"], 0)
            self.assertEqual(result["estimates"], {})

    def test_model_revision_is_forwarded(self):
        from colorref.llm_clients import build_client
        cfg, _, _ = inputs()
        with patch("colorref.llm_clients.HFTransformersClient") as constructor:
            build_client(cfg["model"])
            self.assertEqual(constructor.call_args.kwargs["revision"], cfg["model"]["revision"])


if __name__ == "__main__":
    unittest.main()
