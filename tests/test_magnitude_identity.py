"""Identity counts distinguish policy equality, output equality and missing arms."""
import copy
import unittest
import sys
import tempfile
from pathlib import Path
from tests.test_magnitude_confirmation import inputs, calibration, answer
from colorref.magnitude_control import evaluation_tasks, fit_mapping, score
from colorref.magnitude_identity import analyze, report
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_magnitude_identity as audit
import run_magnitude_control as runner


class IdentityTests(unittest.TestCase):
    def fixture(self):
        cfg, plan = inputs('runs')
        tasks = evaluation_tasks(cfg, plan, fit_mapping(cfg, plan, calibration(plan)))
        rows = {t['condition_id']: score(t, answer(t)) for t in tasks if t['status'] == 'generate'}
        return tasks, rows

    def test_partitions_and_prompt_equal_outputs(self):
        tasks, rows = self.fixture()
        before = copy.deepcopy((tasks, rows))
        result = analyze(tasks, rows)
        n = len(tasks)//4
        self.assertEqual(result['all_pairs']['both_parsed'], n)
        self.assertEqual(sum(r['planned_pairs'] for r in result['by_direction_distance']), n)
        self.assertEqual(sum(r['planned_pairs'] for r in result['by_prompt_identity']), n)
        self.assertEqual(result['all_pairs']['identical_prompt_different_native_lab'], 0)
        self.assertIn('Phrase transitions', report(result, 'fixture'))
        self.assertEqual((tasks, rows), before)

    def test_failure_cohorts_and_identical_prompt_mismatch(self):
        tasks, rows = self.fixture()
        result = analyze(tasks, rows)
        same = next(p for p in result['pairs'] if p['same_prompt'])
        cal = next(t for t in tasks if t['case_id'] == same['case_id'] and t['arm'] == 'calibrated')
        rows[cal['condition_id']] = score(cal, 'LAB(40,0,0)')
        self.assertGreater(analyze(tasks, rows)['all_pairs']['identical_prompt_different_native_lab'], 0)
        numeric = next(t for t in tasks if t['arm'] == 'numeric')
        rows[numeric['condition_id']] = score(numeric, 'bad')
        result = analyze(tasks, rows)
        self.assertEqual(result['all_pairs']['common_quartets'], len(tasks)//4-1)
        self.assertEqual(result['all_pairs']['both_parsed'], len(tasks)//4)
        rows.pop(cal['condition_id'])
        self.assertEqual(analyze(tasks, rows)['all_pairs']['both_completed'], len(tasks)//4-1)

    def test_reject_legacy_and_empty_partial(self):
        tasks, rows = self.fixture()
        with self.assertRaises(ValueError):
            analyze([t for t in tasks if t['arm'] != 'unfitted'], rows)
        result = analyze(tasks, {})
        self.assertEqual(result['all_pairs']['both_parsed'], 0)
        self.assertIsNone(result['all_pairs']['mean_error_delta'])
        report(result, 'pending')

    def test_cpu_saved_run_preserves_source_files(self):
        with tempfile.TemporaryDirectory() as root:
            cfg, plan = inputs(root)
            directory = runner.create_run(cfg, plan, Path('fixture'))
            cfg, plan, metadata = runner.load_plan(directory)
            cal = calibration(plan)
            for task in plan['calibration_tasks']:
                row = {**cal[task['condition_id']], 'run_id': metadata['run_id']}
                cal[task['condition_id']] = row
                runner.write_json(runner.checkpoint_path(directory, task), row)
            bundle = runner.load_controller(directory, cfg, plan, cal, allow_create=True)
            for task in bundle['evaluation_tasks']:
                if task['status'] == 'generate':
                    runner.write_json(runner.checkpoint_path(directory, task), {**score(task, answer(task)), 'run_id': metadata['run_id']})
            before = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            path = audit.execute(directory)
            self.assertTrue(path.exists())
            self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))
