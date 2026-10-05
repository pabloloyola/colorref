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
    required_run_names = (
        "20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000",
        "20260517_171411_feedback_axis_c1_main_qwen3_14b_axis_oracle_main_1000",
        "20260517_172906_feedback_axis_c2_main_qwen3_14b_axis_oracle_main_1000",
        "20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_llm_teacher_hex_only_debug_400",
    )
    required_trajectories = [
        root / "runs" / run_name / "games" / "trajectories.parquet"
        for run_name in required_run_names
    ]
    if not all(path.is_file() for path in required_trajectories):
        return
    paths = plot_paper_showcase(tmp_path / "showcase")
    assert len(paths) >= 1
    assert paths[0].exists()
