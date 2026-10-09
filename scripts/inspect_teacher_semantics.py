"""CPU-only supplementary meaning audit; preserves all original reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.teacher_fidelity import analyze  # noqa: E402
from colorref.teacher_semantic_audit import audit, report  # noqa: E402
from run_teacher_fidelity_study import load_plan, load_rows  # noqa: E402
from run_interface_study import run_lock, write_json  # noqa: E402


def inspect_run(directory):
    with run_lock(directory):
        cfg, plan, metadata = load_plan(directory)
        rows = load_rows(directory, plan, metadata)
        original = analyze(cfg, plan, rows)
        result = audit(
            list(rows.values()), original["completion"], "validated_checkpoints"
        )
        write_json(directory / "metrics/teacher_semantic_audit.json", result)
        (directory / "reports/teacher_semantic_audit.md").write_text(report(result))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", type=Path)
    source.add_argument(
        "--analysis", type=Path, help="Original selected-diagnostics JSON export"
    )
    parser.add_argument("--out-dir", type=Path, help="Required with --analysis only")
    args = parser.parse_args()
    if args.run:
        if args.out_dir:
            parser.error("--out-dir applies only to --analysis")
        result = inspect_run(args.run)
    else:
        if args.out_dir is None:
            parser.error("--analysis requires --out-dir")
        payload = json.loads(args.analysis.read_text())
        result = audit(
            payload["diagnostics"], payload["completion"], "diagnostic_export"
        )
        args.out_dir.mkdir(parents=True, exist_ok=True)
        destination = args.out_dir / "teacher_semantic_audit.json"
        if destination.resolve() == args.analysis.resolve():
            parser.error("Audit destination must differ from input")
        write_json(destination, result)
        (args.out_dir / "teacher_semantic_audit.md").write_text(report(result))
    print(report(result))


if __name__ == "__main__":
    main()
