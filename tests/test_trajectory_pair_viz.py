"""Tests for oracle vs LLM paired trajectory figures (feedback rail layout)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from colorref.trajectory_pair_viz import plot_pair_figure
from colorref.trajectory_viz import TrajectoryCase, _transition_feedbacks


def _case(
    *,
    eid: int,
    raw: str,
    feedback_turn0: str,
    n_turns: int = 2,
) -> TrajectoryCase:
    target_lab = (70.0, 5.0, 30.0)
    turns: list[dict] = [
        {"turn": 0, "hex": "#ff0000", "lab": (50.0, 40.0, -30.0), "error_lab": 55.0},
        {"turn": 1, "hex": "#44aa44", "lab": (58.0, 15.0, 10.0), "error_lab": 22.0},
    ]
    feedback = [{"turn": 0, "text": feedback_turn0}]
    if n_turns > 2:
        turns.append({"turn": 2, "hex": "#00cc44", "lab": (65.0, 8.0, 28.0), "error_lab": 8.0})
        feedback.append({"turn": 1, "text": "Second round: adjust chroma slightly warmer."})
    return TrajectoryCase(
        example_id=eid,
        raw_name=raw,
        target_hex="#00dd44",
        target_lab=target_lab,
        turns=turns,
        feedback=feedback,
        condition="synthetic",
        regime_label="explicit_grounded",
    )


def _first_ax_text_block_containing(fig: plt.Figure, needle: str) -> str:
    for ax in fig.axes:
        s = "\n".join(t.get_text() for t in ax.texts)
        if needle in s:
            return s
    return ""


def _main_ab_axes(fig: plt.Figure):
    for ax in fig.axes:
        xl = ax.get_xlabel() or ""
        if "a*" in xl and "green" in xl:
            return ax
    return fig.axes[0]


def _rail_text_join(fig: plt.Figure, rail_ax_index: int) -> str:
    ax = fig.axes[rail_ax_index]
    return "\n".join(t.get_text() for t in ax.texts)


def test_plot_pair_overlay_rail_four_axes_and_full_llm_text() -> None:
    long_llm = (
        "ZZUNIQUEFEEDBACKMARKER_ZZ Your guess is much cooler and more blue than the target color, "
        "and should move substantially warmer along the red-green axis."
    )
    oracle = _case(eid=1, raw="demo", feedback_turn0="Move toward a brighter shade.")
    llm = _case(eid=2, raw="demo", feedback_turn0=long_llm)
    fig = plot_pair_figure(oracle, llm, None, feedback_layout="rail", panel_layout="overlay")
    try:
        assert len(fig.axes) == 4
        oracle_rail = _first_ax_text_block_containing(fig, "brighter")
        llm_rail = _first_ax_text_block_containing(fig, "ZZUNIQUEFEEDBACKMARKER_ZZ")
        assert "0 → 1" in oracle_rail
        assert "brighter" in oracle_rail
        assert "ZZUNIQUEFEEDBACKMARKER_ZZ" in llm_rail
        assert "more blue" in llm_rail and "than the target" in llm_rail
        assert len(llm_rail) > 70
        main = _main_ab_axes(fig)
        assert main.get_legend() is not None
        leg_txt = " ".join(t.get_text() for t in main.get_legend().get_texts())
        assert "Oracle path" in leg_txt and "LLM path" in leg_txt
    finally:
        plt.close(fig)


def test_plot_pair_split_rail_four_axes() -> None:
    oracle = _case(eid=1, raw="demo", feedback_turn0="Oracle fb.")
    llm = _case(eid=2, raw="demo", feedback_turn0="LLM fb longer text for wrap.")
    fig = plot_pair_figure(oracle, llm, None, feedback_layout="rail", panel_layout="split")
    try:
        assert len(fig.axes) == 4
        assert _rail_text_join(fig, 2)
        assert _rail_text_join(fig, 3)
    finally:
        plt.close(fig)


def test_plot_pair_inline_two_axes() -> None:
    oracle = _case(eid=1, raw="x", feedback_turn0="Short oracle hint.")
    llm = _case(eid=2, raw="x", feedback_turn0="Another short line.")
    fig = plot_pair_figure(
        oracle, llm, None,
        feedback_layout="inline",
        panel_layout="split",
    )
    try:
        assert len(fig.axes) == 2
    finally:
        plt.close(fig)


def test_transition_feedbacks_matches_turns_minus_one() -> None:
    c = _case(eid=1, raw="x", feedback_turn0="fb", n_turns=3)
    segs = [s for s in _transition_feedbacks(c) if s[2]]
    assert len(segs) == 2
    assert {s[0] for s in segs} == {0, 1}


def test_plot_pair_rail_with_llm_feedback_parquet_smoke(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    oracle_dir = root / (
        "runs/20260517_214025_feedback_template_llm_vocab_debug_qwen3_14b_"
        "template_oracle_llm_vocab_debug_400"
    )
    llm_dir = root / (
        "runs/20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_"
        "llm_teacher_hex_only_debug_400"
    )
    if not oracle_dir.is_dir() or not llm_dir.is_dir():
        return
    from colorref.pairing import load_run_data
    from colorref.trajectory_viz import load_trajectory_case

    eid = 440394
    oracle_case = load_trajectory_case(
        oracle_dir, example_id=eid, condition="oracle",
    )
    llm_case = load_trajectory_case(
        llm_dir, example_id=eid, condition="llm",
    )
    _, llm_fb, _ = load_run_data(llm_dir)
    out = tmp_path / "pair_rail.png"
    fig = plot_pair_figure(
        oracle_case, llm_case, llm_fb,
        out_path=out,
        feedback_layout="rail",
    )
    try:
        assert out.exists()
        assert out.stat().st_size > 8000
        assert len(fig.axes) == 4
        n_feedback_cards = sum(
            1 for ax in fig.axes for t in ax.texts if "0 → 1" in t.get_text()
        )
        assert n_feedback_cards >= 2
    finally:
        plt.close(fig)


def test_draw_feedback_rail_per_turn_colors() -> None:
    from colorref.trajectory_viz import _draw_feedback_rail

    c = _case(eid=1, raw="x", feedback_turn0="First.", n_turns=3)
    c.feedback[1] = {"turn": 1, "text": "Second."}
    fig = plt.figure(figsize=(4, 2))
    ax_rail = fig.add_axes([0.05, 0.15, 0.9, 0.7])
    verdict = {0: True, 1: False}
    try:
        _draw_feedback_rail(
            ax_rail, c, per_turn_correct=verdict,
            check_color="#00ff00", cross_color="#ff0000",
        )
        texts = [t.get_text() for t in ax_rail.texts]
        joined = " ".join(texts)
        assert "✓" in joined and "✗" in joined
    finally:
        plt.close(fig)
