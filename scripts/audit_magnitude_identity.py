"""Audit frozen four-arm policies and saved responses with zero inference."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from colorref.magnitude_identity import analyze, report
from colorref.magnitude_control import evaluation_arms
from run_magnitude_control import load_plan, load_rows, load_controller, run_lock, write_json


def execute(directory):
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        if 'unfitted' not in evaluation_arms(cfg):
            raise ValueError('Requires four-arm magnitude confirmation')
        calibration = load_rows(directory, plan['calibration_tasks'], metadata)
        bundle = load_controller(directory, cfg, plan, calibration)
        if bundle is None:
            raise ValueError('Frozen controller not yet available')
        tasks = bundle['evaluation_tasks']
        rows = load_rows(directory, tasks, metadata)
        result = analyze(tasks, rows)
        write_json(directory / 'metrics/magnitude_identity.json', result)
        path = directory / 'reports/magnitude_identity.md'
        path.write_text(report(result, directory.name))
        return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    print(execute(parser.parse_args().run))
