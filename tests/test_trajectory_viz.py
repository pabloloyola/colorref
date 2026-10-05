"""Tests for LAB trajectory visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from colorref.trajectory_viz import load_trajectory_case, plot_lab_trajectory, plot_paper_showcase


def test_load_and_plot_single_trajectory(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    run_dir = root / "runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000"
    if not run_dir.exists():
        return
    case = load_trajectory_case(run_dir, raw_name_contains="anchored")
    out = tmp_path / "traj.png"
    plot_lab_trajectory(case, out, show_l_strip=True)
    assert out.exists()
    assert out.stat().st_size > 5000


def test_plot_paper_showcase_smoke(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    if not (root / "runs").exists():
        return
    paths = plot_paper_showcase(tmp_path / "showcase")
    assert len(paths) >= 1
    assert paths[0].exists()
