"""Four-arm subgroup audits retain clusters and exclude failed fourth outputs."""
import unittest
from tests.test_magnitude_confirmation import inputs, calibration, answer
from colorref.magnitude_control import evaluation_tasks, fit_mapping, score
from colorref.magnitude_analysis import analyze, report
from colorref.magnitude_reports import analyze as primary


class FourArmAuditTests(unittest.TestCase):
    def test_cohort_effect_partition_and_failure_sensitivity(self):
        cfg, plan = inputs('runs')
        cal = calibration(plan)
        mapping = fit_mapping(cfg, plan, cal)
        tasks = evaluation_tasks(cfg, plan, mapping)
        bundle = {'mapping': mapping, 'evaluation_tasks': tasks}
        rows = {t['condition_id']: score(t, answer(t)) for t in tasks if t['status'] == 'generate'}
        result = analyze(cfg, plan, bundle, rows)
        reference = primary(cfg, plan, cal, mapping, tasks, rows)
        effect = reference['effects'][0]
        self.assertEqual(result['global']['common_cases'], reference['common_quartets'])
        for key in ('mean', 'low', 'high', 'cases', 'starting_colors'):
            self.assertEqual(result['global']['primary_effect'][key], effect[key])
        self.assertEqual(result['comparison_left'], 'unfitted')
        for grouping in ('by_direction', 'by_distance', 'by_direction_distance', 'by_start'):
            parts = result[grouping]
            n = result['global']['common_cases']
            self.assertEqual(sum(p['common_cases'] for p in parts), n)
            pooled = sum(p['primary_effect']['mean'] * p['common_cases'] for p in parts if p['common_cases']) / n
            self.assertAlmostEqual(pooled, effect['mean'])
        self.assertIn('Calibrated minus unfitted', report(result, 'fixture'))
        failed = next(t for t in tasks if t['arm'] == 'numeric')
        rows[failed['condition_id']] = score(failed, 'bad')
        result = analyze(cfg, plan, bundle, rows)
        self.assertEqual(result['global']['common_cases'], n-1)
        self.assertEqual(result['available_pair']['cases'], n)
        self.assertEqual(result['global']['arms']['numeric']['parsed'], n-1)

    def test_pending_four_arm_report(self):
        cfg, plan = inputs('runs')
        result = analyze(cfg, plan, None, {})
        self.assertEqual(result['global']['common_cases'], 0)
        self.assertEqual(set(result['global']['arms']), {'bare', 'unfitted', 'calibrated', 'numeric'})
        self.assertIn('Common parsed quartets: 0', report(result, 'pending'))
