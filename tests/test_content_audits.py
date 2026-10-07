"""Read-only content audit checks; fixture data are not scientific findings."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_target_multiplicity as audit  # noqa: E402
import inspect_teacher_receiver as messages  # noqa: E402


class TargetInventoryTests(unittest.TestCase):
    def test_duplicates_normalization_and_exact_multicolor_are_distinct(self):
        frame = pd.DataFrame({
            "raw_name": ["Blue", "Blue", " blue  ", "sunset", "sunset", None, "bad"],
            "hex": ["#0000FF", "0000ff", "#00ff00", "#ff0000", "#00ff00", "#000000", "invalid"],
            "score": [0.75, 0.8, 0.75, 0.9, 0.5, None, float("inf")],
        })
        result = audit.inventory(frame)
        self.assertEqual(result["valid_name_color_rows"], 5)
        self.assertEqual(result["duplicate_exact_name_color_rows_beyond_first"], 1)
        self.assertEqual(result["groupings"]["raw"]["multiple_color_groups"], 1)
        self.assertEqual(result["groupings"]["normalized"]["multiple_color_groups"], 2)
        details = {r["normalized_name"]: r for r in result["multiple_target_groups"]}
        self.assertFalse(details["blue"]["has_exact_raw_name_with_multiple_colors"])
        self.assertTrue(details["sunset"]["has_exact_raw_name_with_multiple_colors"])
        self.assertEqual(result["score_boundary"]["score_equal_0_75"], 2)
        self.assertEqual(result["score_boundary"]["score_at_least_0_75"], 4)
        self.assertEqual(result["score_boundary"]["score_greater_than_0_75"], 2)
        collapsed = audit.inventory(frame.drop(index=1))
        self.assertEqual(details["blue"]["unique_color_rms_delta_e_to_centroid"], collapsed["multiple_target_groups"][0]["unique_color_rms_delta_e_to_centroid"])

    def test_evaluation_overwrites_and_fields_are_inventory_not_agreement(self):
        result = audit.evaluation_inventory([
            {"description": "blue", "score": 0.75, "language_match": True},
            {"description": "blue", "score": 0.9},
            {"description": "Blue", "score": 0.75},
        ])
        self.assertEqual(result["duplicate_description_rows_beyond_first"], 1)
        self.assertEqual(result["repeated_descriptions_with_distinct_scores"], 1)
        self.assertIn("language_match", result["field_names"])
        with self.assertRaises(ValueError):
            audit.evaluation_inventory([{"score": 0.5}])

    def test_cli_preserves_input_and_refuses_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "source.json", root / "report.json"
            original = json.dumps({"English": [{"name": "blue", "color": "#0000ff"}]}).encode()
            source.write_bytes(original)
            cmd = [sys.executable, str(ROOT / "scripts/audit_target_multiplicity.py"), "--input", str(source), "--output", str(output)]
            subprocess.run(cmd, check=True, capture_output=True)
            self.assertEqual(source.read_bytes(), original)
            saved = output.read_bytes()
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), saved)
            cmd[-1] = str(source)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(source.read_bytes(), original)

    def test_empty_or_invalid_data_and_missing_schema(self):
        for frame in [pd.DataFrame(columns=["name", "color"]), pd.DataFrame({"name": [None], "color": ["bad"]})]:
            result = audit.inventory(frame)
            self.assertEqual(result["multiple_target_groups"], [])
            self.assertEqual(result["valid_name_color_rows"], 0)
        with self.assertRaises(ValueError):
            audit.inventory(pd.DataFrame({"name": ["blue"]}))


class MessageExportTests(unittest.TestCase):
    def test_same_set_changed_pairs_exported_even_without_valid_endpoint(self):
        row = {
            "arm": "restricted_0", "tags": ["lexical_set_equal", "different_feedback"],
            "condition_id": "changed_same_set", "paired_parsed": False,
            "error_difference": None, "teacher_feedback": "Make it bluer and lighter.",
            "oracle_feedback": "Make it lighter and bluer.",
            "arm_raw_response": None, "oracle_raw_response": "#808080",
        }
        identical = {**row, "condition_id": "identical_not_exported", "tags": ["lexical_set_equal", "identical_feedback"]}
        other = {**row, "condition_id": "natural_not_exported", "arm": "natural_0"}
        result = {"summary": [], "pairs": [row, identical, other]}
        before = copy.deepcopy(result)
        text = messages.report(result)
        self.assertIn("### changed_same_set", text)
        self.assertIn("teacher-minus-oracle error: n/a", text)
        self.assertIn("Teacher-arm response: None", text)
        self.assertNotIn("### identical_not_exported", text)
        self.assertNotIn("### natural_not_exported", text)
        self.assertEqual(result, before)


if __name__ == "__main__":
    unittest.main()
