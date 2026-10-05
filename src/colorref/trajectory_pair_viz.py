"""Side-by-side or overlaid oracle vs LLM teacher trajectory visualization.

Default **overlay** layout: one a*–b* panel (with optional chromaticity background),
narrow **L*** strip (oracle vs LLM lightness per turn), and **stacked** full-width
feedback rows — similar spacing to ``plot_lab_trajectory``.

``panel_layout="split"`` restores two separate a*–b* panels (legacy).

Consistent visual encoding (spec §4.7):
  solid star        – target color
  dashed white ring – guess nodes (fill = model hex)
  bold turn index   – centered on each node
  blue / orange     – oracle vs LLM revision arrows (overlay)
  green check (✓)  – LLM rail directional verdict
  red cross  (✗)   – LLM rail wrong direction
  grey dashed arrow – ideal direction to target
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib import gridspec

from colorref.trajectory_viz import (
    TrajectoryCase,
    _attach_l_strip,
    _draw_ab_background,
    _draw_feedback_rail,
    _FEEDBACK_FIG_MARGINS,
    _FEEDBACK_RAIL_HSPACE,
    _FEEDBACK_ROW_RATIO,
    load_trajectory_case,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "figure.dpi": 150,
})

_PALETTE_TURNS = ["#5C6BC0", "#26A69A", "#FFA726", "#EF5350", "#AB47BC", "#78909C", "#26C6DA"]
_TARGET_FILL = "#FFD700"
_TARGET_EDGE = "#1a1a1a"
_IDEAL_ARROW_COLOR = "#9e9e9e"
_CHECK_COLOR = "#43a047"
_CROSS_COLOR = "#e53935"
_NODE_EDGE = "white"
_PATH_COLOR = "#333333"
_SAVE_PAD_INCHES = 0.05
_TEXT_BOX_PROPS = dict(
    boxstyle="round,pad=0.25",
    facecolor="white",
    edgecolor="#cccccc",
    alpha=0.88,
    linewidth=0.8,
)
_ORACLE_PATH = "#1565c0"
_LLM_PATH = "#e65100"
_OVERLAP_AB_EPS = 2.5


# ---------------------------------------------------------------------------
# Axis limits helpers
# ---------------------------------------------------------------------------

def _axis_limits(
    cases: list[TrajectoryCase],
    pad: float = 8.0,
) -> tuple[float, float, float, float]:
    """Compute shared a* / b* axis limits across all given cases."""
    all_a: list[float] = []
    all_b: list[float] = []
    for c in cases:
        all_a.append(c.target_lab[1])
        all_b.append(c.target_lab[2])
        for t in c.turns:
            all_a.append(t["lab"][1])
            all_b.append(t["lab"][2])
    if not all_a:
        return -80, 80, -80, 80
    return (
        min(all_a) - pad, max(all_a) + pad,
        min(all_b) - pad, max(all_b) + pad,
    )


def _hex_mpl(h: str) -> str:
    h = h.strip()
    return h if h.startswith("#") else f"#{h}"


def _turn_ab_dist(t0: dict[str, Any], t1: dict[str, Any]) -> float:
    return float(
        np.hypot(
            float(t0["lab"][1]) - float(t1["lab"][1]),
            float(t0["lab"][2]) - float(t1["lab"][2]),
        )
    )


def _draw_indexed_guess_node(
    ax: plt.Axes,
    turn: dict[str, Any],
    idx: int,
    *,
    zbase: int,
    radius: float = 5.0,
) -> None:
    """Filled circle at guess LAB (a*, b*), bold turn index centered."""
    a, b = float(turn["lab"][1]), float(turn["lab"][2])
    hx = _hex_mpl(str(turn["hex"]))
    L = float(turn["lab"][0])
    circ = plt.Circle(
        (a, b),
        radius,
        facecolor=hx,
        edgecolor=_NODE_EDGE,
        linewidth=1.85,
        linestyle=(0, (4, 2.5)),
        zorder=zbase,
    )
    ax.add_patch(circ)
    txt_color = "white" if L < 55 else "black"
    if txt_color == "white":
        peff = [pe.withStroke(linewidth=2.2, foreground="#00000055")]
    else:
        peff = [pe.withStroke(linewidth=1.6, foreground="#ffffff88")]
    ax.text(
        a, b, str(idx),
        ha="center", va="center",
        fontsize=10, fontweight="bold", color=txt_color,
        zorder=zbase + 1,
        path_effects=peff,
    )


def _draw_pair_lightness_strip(
    ax_l: Any,
    oracle_case: TrajectoryCase,
    llm_case: TrajectoryCase,
) -> None:
    """Vertical L* panel: paired horizontal bars per turn (oracle vs LLM)."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    L_tgt = float(oracle_case.target_lab[0])
    n = max(len(oracle_case.turns), len(llm_case.turns))
    if n == 0:
        ax_l.set_visible(False)
        return

    dy = 0.22
    bar_h = 0.30
    for i in range(n):
        if i < len(oracle_case.turns):
            Lo = float(oracle_case.turns[i]["lab"][0])
            ax_l.barh(
                i - dy, Lo, height=bar_h, left=0.0,
                color=_ORACLE_PATH, edgecolor="white", linewidth=0.6,
                alpha=0.92, zorder=2,
            )
        if i < len(llm_case.turns):
            Ll = float(llm_case.turns[i]["lab"][0])
            ax_l.barh(
                i + dy, Ll, height=bar_h, left=0.0,
                color=_LLM_PATH, edgecolor="white", linewidth=0.6,
                alpha=0.92, zorder=3,
            )

    ax_l.axvline(L_tgt, color=_TARGET_EDGE, linestyle="--", linewidth=1.45, zorder=4)
    ax_l.set_xlabel("L*", fontsize=8)
    ax_l.set_ylabel("Turn", fontsize=8, labelpad=5)
    ax_l.yaxis.set_label_position("left")
    ax_l.set_title("Lightness", fontsize=8, pad=2)
    ax_l.set_xlim(0, 100)
    turns_idx = list(range(n))
    ax_l.set_yticks(turns_idx)
    ax_l.invert_yaxis()
    t_lo, t_hi = min(turns_idx), max(turns_idx)
    ax_l.set_ylim(t_hi + 0.5, t_lo - 0.5)
    ax_l.tick_params(axis="y", labelsize=8, pad=2)
    ax_l.grid(True, axis="x", linestyle="--", linewidth=0.35, alpha=0.35)

    leg = [
        Patch(facecolor=_ORACLE_PATH, edgecolor="white", linewidth=0.5, label="Oracle L*"),
        Patch(facecolor=_LLM_PATH, edgecolor="white", linewidth=0.5, label="LLM L*"),
        Line2D([0, 1], [0, 0], color=_TARGET_EDGE, linestyle="--", linewidth=1.5, label="Target L*"),
    ]
    ax_l.legend(handles=leg, fontsize=6, loc="lower right", framealpha=0.94, borderpad=0.25)


def _stamp_feedback_row_label(ax: Any, label: str) -> None:
    ax.text(
        0.01, 0.88, label,
        transform=ax.transAxes,
        fontsize=7.5, fontweight="bold", color="#424242",
        ha="left", va="top",
    )


def _draw_combined_ab_panel(
    ax: Any,
    oracle_case: TrajectoryCase,
    llm_case: TrajectoryCase,
    *,
    a_lim: tuple[float, float],
    b_lim: tuple[float, float],
    show_ideal_arrow: bool = True,
    show_background: bool = True,
) -> None:
    """Single a*–b* axes: both trajectories, numbered guess-colored nodes (paper style)."""
    from matplotlib.lines import Line2D

    tgt_a, tgt_b = oracle_case.target_lab[1], oracle_case.target_lab[2]
    L_bg = oracle_case.target_lab[0]

    ax.set_xlim(*a_lim)
    ax.set_ylim(*b_lim)
    ax.set_aspect("equal", adjustable="box")
    if show_background:
        _draw_ab_background(ax, L_bg, a_lim, b_lim)
    ax.set_xlabel("a* (green ← → red)", fontsize=9)
    ax.set_ylabel("b* (blue ← → yellow)", fontsize=9)
    ax.grid(True, color="white", linewidth=0.45, alpha=0.4, zorder=1)

    if show_ideal_arrow and oracle_case.turns:
        ia = float(oracle_case.turns[0]["lab"][1])
        ib = float(oracle_case.turns[0]["lab"][2])
        ax.annotate(
            "",
            xy=(tgt_a, tgt_b),
            xytext=(ia, ib),
            arrowprops=dict(
                arrowstyle="-|>",
                color=_IDEAL_ARROW_COLOR,
                lw=1.05,
                linestyle="dashed",
                mutation_scale=9,
                shrinkA=4,
                shrinkB=6,
            ),
            zorder=2,
        )

    def _curved_arrows(case: TrajectoryCase, color: str, ls: str | tuple, z: int) -> None:
        for i in range(len(case.turns) - 1):
            t0, t1 = case.turns[i], case.turns[i + 1]
            p0 = (float(t0["lab"][1]), float(t0["lab"][2]))
            p1 = (float(t1["lab"][1]), float(t1["lab"][2]))
            arr = FancyArrowPatch(
                p0,
                p1,
                arrowstyle="-|>",
                mutation_scale=12,
                linewidth=1.45,
                color=color,
                linestyle=ls,
                zorder=z,
                connectionstyle="arc3,rad=0.12",
                shrinkA=8,
                shrinkB=8,
            )
            ax.add_patch(arr)

    _curved_arrows(oracle_case, _ORACLE_PATH, "solid", z=3)
    _curved_arrows(llm_case, _LLM_PATH, (0, (4, 2)), z=4)

    n_o = len(oracle_case.turns)
    n_l = len(llm_case.turns)
    n_max = max(n_o, n_l)
    for i in range(n_max):
        o_t = oracle_case.turns[i] if i < n_o else None
        l_t = llm_case.turns[i] if i < n_l else None
        if o_t is not None and l_t is not None and _turn_ab_dist(o_t, l_t) < _OVERLAP_AB_EPS:
            _draw_indexed_guess_node(ax, o_t, i, zbase=8)
        else:
            if o_t is not None:
                _draw_indexed_guess_node(ax, o_t, i, zbase=5)
            if l_t is not None:
                _draw_indexed_guess_node(ax, l_t, i, zbase=7)

    tgt_hex = _hex_mpl(oracle_case.target_hex)
    target_circ = Circle(
        (tgt_a, tgt_b),
        radius=4.5,
        facecolor=tgt_hex,
        edgecolor="white",
        linewidth=2.4,
        linestyle="solid",
        zorder=10,
    )
    ax.add_patch(target_circ)

    leg_handles = [
        Line2D([0], [0], color=_ORACLE_PATH, lw=2.4, linestyle="solid", label="Oracle path"),
        Line2D([0], [0], color=_LLM_PATH, lw=2.4, linestyle=(0, (4, 2)), label="LLM path"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#888888", markersize=9,
              markeredgecolor="white", markeredgewidth=1.2, linestyle="None", label="Guess (dashed ring)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=tgt_hex, markersize=9,
              markeredgecolor="white", markeredgewidth=2.0, linestyle="None", label="Target (solid ring)"),
    ]
    ax.legend(
        handles=leg_handles,
        loc="upper right",
        fontsize=7,
        framealpha=0.96,
        borderpad=0.35,
        labelspacing=0.35,
    )

    ax.set_title(
        f'"{oracle_case.raw_name}"',
        fontsize=11,
        fontweight="bold",
        pad=6,
        color="#1a1a1a",
    )


# ---------------------------------------------------------------------------
# Per-panel drawing
# ---------------------------------------------------------------------------

def _draw_panel(
    ax: plt.Axes,
    case: TrajectoryCase,
    *,
    precision_info: dict[str, Any] | None = None,
    a_lim: tuple[float, float] | None = None,
    b_lim: tuple[float, float] | None = None,
    show_ideal_arrow: bool = True,
    panel_label: str = "",
    is_oracle: bool = True,
    show_inline_feedback: bool = True,
) -> None:
    """Draw one trajectory panel on ax.

    precision_info (optional): dict with keys per_turn_correct (list[bool | None])
    show_inline_feedback — mid-path truncated feedback boxes (legacy); off when
        using the bottom feedback rail only.
    """
    tgt_a, tgt_b = case.target_lab[1], case.target_lab[2]

    if a_lim:
        ax.set_xlim(*a_lim)
    if b_lim:
        ax.set_ylim(*b_lim)

    ax.set_xlabel("a* (green–red)", fontsize=8)
    ax.set_ylabel("b* (blue–yellow)", fontsize=8)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.45, zorder=0)
    ax.set_aspect("equal", adjustable="datalim")

    # ---- ideal grey dashed arrow from initial guess → target ----
    if show_ideal_arrow and case.turns:
        init_a, init_b = case.turns[0]["lab"][1], case.turns[0]["lab"][2]
        ax.annotate(
            "",
            xy=(tgt_a, tgt_b),
            xytext=(init_a, init_b),
            arrowprops=dict(
                arrowstyle="-|>",
                color=_IDEAL_ARROW_COLOR,
                lw=1.0,
                linestyle="dashed",
                mutation_scale=8,
                shrinkA=4,
                shrinkB=6,
            ),
            zorder=1,
        )

    # ---- trajectory arrows ----
    for i in range(len(case.turns) - 1):
        t0, t1 = case.turns[i], case.turns[i + 1]
        a0, b0 = t0["lab"][1], t0["lab"][2]
        a1, b1 = t1["lab"][1], t1["lab"][2]
        color = _PALETTE_TURNS[min(i, len(_PALETTE_TURNS) - 1)]
        ax.annotate(
            "",
            xy=(a1, b1), xytext=(a0, b0),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=1.5,
                mutation_scale=10,
                shrinkA=5,
                shrinkB=5,
            ),
            zorder=3,
        )

    # ---- guess nodes ----
    for idx, t in enumerate(case.turns):
        a, b = t["lab"][1], t["lab"][2]
        hex_c = _hex_mpl(t["hex"])
        radius = 5.0
        circle = plt.Circle(
            (a, b), radius,
            facecolor=hex_c,
            edgecolor=_NODE_EDGE,
            linewidth=1.5,
            linestyle=(0, (4, 3)),
            zorder=4,
        )
        ax.add_patch(circle)
        err_str = f"ΔE={t['error_lab']:.1f}" if t.get("error_lab") is not None else ""
        offset_b = -7.5 if b > tgt_b else 7.5
        ax.text(
            a, b + offset_b, err_str,
            ha="center", va="center",
            fontsize=6.5, color="#333333", zorder=6,
        )

    # ---- target marker (star) ----
    tgt_hex = _hex_mpl(case.target_hex)
    ax.scatter(
        [tgt_a], [tgt_b],
        s=160, marker="*",
        facecolor=tgt_hex,
        edgecolors=_TARGET_EDGE,
        linewidths=1.4,
        zorder=5,
        label="Target",
    )

    # ---- optional mid-path feedback (truncated) ----
    if show_inline_feedback:
        fb_by_turn = {f["turn"]: f["text"] for f in case.feedback}
        per_turn_correct = (precision_info or {}).get("per_turn_correct", {})

        for i in range(len(case.turns) - 1):
            t0, t1 = case.turns[i], case.turns[i + 1]
            text = fb_by_turn.get(t0["turn"], "")
            if not text:
                continue

            mid_a = (t0["lab"][1] + t1["lab"][1]) / 2
            mid_b = (t0["lab"][2] + t1["lab"][2]) / 2

            correct = per_turn_correct.get(t0["turn"])
            if not is_oracle and correct is not None:
                indicator = " ✓" if correct else " ✗"
                ind_color = _CHECK_COLOR if correct else _CROSS_COLOR
            else:
                indicator = ""
                ind_color = "#333333"

            words = text.strip().split()
            max_w = 28
            lines: list[str] = []
            cur: list[str] = []
            n = 0
            for w in words:
                if n + len(w) + 1 > max_w and cur:
                    lines.append(" ".join(cur))
                    cur, n = [w], len(w)
                else:
                    cur.append(w)
                    n += len(w) + (1 if n else 0)
            if cur:
                lines.append(" ".join(cur))
            short_text = "\n".join(lines[:2])

            text_color = ind_color if indicator else "#333333"
            ax.text(
                mid_a, mid_b,
                short_text + indicator,
                ha="center", va="center",
                fontsize=6.0, color=text_color,
                bbox=_TEXT_BOX_PROPS,
                zorder=7,
            )

    # ---- title ----
    title_str = f'"{case.raw_name}" — {panel_label}\n[{case.regime_label}]'
    ax.set_title(title_str, fontsize=9, pad=5)


# ---------------------------------------------------------------------------
# Build precision_info per-turn for LLM teacher
# ---------------------------------------------------------------------------

def _compute_per_turn_correctness(
    case: TrajectoryCase,
    fb_df: pd.DataFrame,
) -> dict[str, Any]:
    """Return per_turn_correct dict (turn → bool | None) for one example."""
    from colorref.teachers import _compute_candidate_deltas, detect_constraints, _MIN_DELTA

    fb_sub = fb_df[fb_df["example_id"] == case.example_id] if not fb_df.empty else pd.DataFrame()
    per_turn_correct: dict[int, bool | None] = {}

    turns_by_idx = {t["turn"]: t for t in case.turns}

    for _, fb_row in fb_sub.iterrows():
        turn = int(fb_row["turn"])
        text = str(fb_row.get("feedback_text", ""))
        detected = detect_constraints(text)
        if not detected:
            per_turn_correct[turn] = None
            continue

        t_info = turns_by_idx.get(turn)
        if t_info is None:
            per_turn_correct[turn] = None
            continue

        lab = t_info["lab"]
        tgt_lab = case.target_lab
        # We don't have HSV here so approximate with lab-only candidates
        # (hsv_s axis may be skipped)
        target_cd = {"lab": tgt_lab, "hsv": (0.0, 0.5, 0.5)}
        guess_cd = {"lab": lab, "hsv": (0.0, 0.5, 0.5)}
        try:
            oracle_cands = _compute_candidate_deltas(target_cd, guess_cd, _MIN_DELTA)
        except Exception:
            per_turn_correct[turn] = None
            continue

        oracle_by_axis = {c["axis"]: c["sign"] for c in oracle_cands}
        any_correct = any(
            d["axis"] in oracle_by_axis and oracle_by_axis[d["axis"]] == d["sign"]
            for d in detected
        )
        per_turn_correct[turn] = any_correct

    return {"per_turn_correct": per_turn_correct}


# ---------------------------------------------------------------------------
# Public: plot one pair
# ---------------------------------------------------------------------------

def plot_pair_figure(
    oracle_case: TrajectoryCase,
    llm_case: TrajectoryCase,
    llm_fb_df: pd.DataFrame | None = None,
    *,
    out_path: Path | str | None = None,
    figsize: tuple[float, float] | None = None,
    show_ideal_arrow: bool = True,
    oracle_panel_label: str = "Oracle",
    llm_panel_label: str = "LLM Teacher",
    feedback_layout: Literal["rail", "inline", "both"] = "rail",
    rail_wrap_len: int = 34,
    panel_layout: Literal["split", "overlay"] = "overlay",
    show_ab_background: bool = True,
) -> plt.Figure:
    """Oracle vs LLM trajectory figure for one example.

    ``panel_layout``:
      ``overlay`` (default) — one shared a*–b* plot: both paths with numbered,
      guess-colored nodes (oracle = solid blue arrows, LLM = dashed orange).
      ``split`` — two separate a*–b* panels (legacy).

    ``feedback_layout``:
      ``rail`` (default) — full per-step feedback cards under the plot(s).
      ``inline`` — mid-path labels (truncated); ignored on ``overlay`` (too busy).
      ``both`` — rail plus inline (split layout only).

    Returns the Figure object. If out_path is given, saves PNG + PDF.
    """
    a_min, a_max, b_min, b_max = _axis_limits(
        [oracle_case, llm_case], pad=10.0
    )

    precision_info = None
    if llm_fb_df is not None:
        precision_info = _compute_per_turn_correctness(llm_case, llm_fb_df)

    use_rail = feedback_layout in ("rail", "both")
    show_inline = feedback_layout in ("inline", "both")
    if panel_layout == "overlay":
        show_inline = False

    if figsize is None:
        if panel_layout == "overlay":
            figsize = (6.35 + 0.85, 5.75 + 0.55 + 0.55) if use_rail else (9.0, 5.4)
        else:
            figsize = (12.0, 6.85) if use_rail else (12.0, 5.5)

    if use_rail:
        fig = plt.figure(figsize=figsize)
        if panel_layout == "overlay":
            h_rail = _FEEDBACK_ROW_RATIO * 0.9
            gs = fig.add_gridspec(
                3, 1,
                height_ratios=[5.0, h_rail, h_rail],
                hspace=_FEEDBACK_RAIL_HSPACE * 0.82,
                **_FEEDBACK_FIG_MARGINS,
            )
            ax_main = fig.add_subplot(gs[0, 0])
            ax_l = _attach_l_strip(ax_main)
            ax_fb_o = fig.add_subplot(gs[1, 0])
            ax_fb_l = fig.add_subplot(gs[2, 0])
            _draw_combined_ab_panel(
                ax_main, oracle_case, llm_case,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                show_background=show_ab_background,
            )
            _draw_pair_lightness_strip(ax_l, oracle_case, llm_case)
        else:
            gs = gridspec.GridSpec(
                2, 2,
                figure=fig,
                height_ratios=[4.65, 1.12],
                hspace=0.26,
                wspace=0.28,
                left=0.07,
                right=0.98,
                top=0.90,
                bottom=0.07,
            )
            ax0 = fig.add_subplot(gs[0, 0])
            ax1 = fig.add_subplot(gs[0, 1])
            ax_fb_o = fig.add_subplot(gs[1, 0])
            ax_fb_l = fig.add_subplot(gs[1, 1])
            _draw_panel(
                ax0, oracle_case,
                precision_info=None,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                panel_label=oracle_panel_label,
                is_oracle=True,
                show_inline_feedback=show_inline,
            )
            _draw_panel(
                ax1, llm_case,
                precision_info=precision_info,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                panel_label=llm_panel_label,
                is_oracle=False,
                show_inline_feedback=show_inline,
            )
    else:
        if panel_layout == "overlay":
            fig, ax_main = plt.subplots(1, 1, figsize=figsize)
            ax_l = _attach_l_strip(ax_main)
            ax_fb_o = ax_fb_l = None
            _draw_combined_ab_panel(
                ax_main, oracle_case, llm_case,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                show_background=show_ab_background,
            )
            _draw_pair_lightness_strip(ax_l, oracle_case, llm_case)
        else:
            fig, axes = plt.subplots(1, 2, figsize=figsize)
            fig.subplots_adjust(wspace=0.30)
            ax_fb_o = ax_fb_l = None
            _draw_panel(
                axes[0], oracle_case,
                precision_info=None,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                panel_label=oracle_panel_label,
                is_oracle=True,
                show_inline_feedback=show_inline,
            )
            _draw_panel(
                axes[1], llm_case,
                precision_info=precision_info,
                a_lim=(a_min, a_max), b_lim=(b_min, b_max),
                show_ideal_arrow=show_ideal_arrow,
                panel_label=llm_panel_label,
                is_oracle=False,
                show_inline_feedback=show_inline,
            )

    if use_rail and ax_fb_o is not None and ax_fb_l is not None:
        _draw_feedback_rail(ax_fb_o, oracle_case, wrap_len=rail_wrap_len)
        _stamp_feedback_row_label(ax_fb_o, f"{oracle_panel_label} — per-step feedback")
        llm_verdict = (precision_info or {}).get("per_turn_correct") if precision_info else None
        _draw_feedback_rail(
            ax_fb_l,
            llm_case,
            wrap_len=rail_wrap_len,
            per_turn_correct=llm_verdict,
            check_color=_CHECK_COLOR,
            cross_color=_CROSS_COLOR,
        )
        _stamp_feedback_row_label(ax_fb_l, f"{llm_panel_label} — per-step feedback")

    supt_parts = [f'"{oracle_case.raw_name}"']
    if oracle_case.regime_label:
        supt_parts.append(oracle_case.regime_label)
    supt_parts.append(f"target {oracle_case.target_hex}")
    fig.suptitle("  |  ".join(supt_parts), fontsize=9.5, y=0.985)

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
        try:
            fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
        except Exception:
            pass
        logger.info("Saved pair figure: %s", out_path)

    return fig


# ---------------------------------------------------------------------------
# Public: plot grid of top cases
# ---------------------------------------------------------------------------

def plot_pair_grid(
    pairs: list[tuple[TrajectoryCase, TrajectoryCase]],
    *,
    out_path: Path | str | None = None,
    cols: int = 2,
    cell_size: tuple[float, float] = (11.0, 5.0),
    oracle_label: str = "Oracle",
    llm_label: str = "LLM Teacher",
) -> plt.Figure:
    """Grid of multiple pair figures (each pair = 2 subplots on a row)."""
    n = len(pairs)
    rows = (n + cols - 1) // cols
    fig_w = cell_size[0] * cols
    fig_h = cell_size[1] * rows

    fig, axes_grid = plt.subplots(
        rows * 1, cols * 2,
        figsize=(fig_w, fig_h),
        squeeze=False,
    )
    fig.subplots_adjust(hspace=0.5, wspace=0.35)

    # Flatten into pairs of axes
    ax_pairs: list[tuple[plt.Axes, plt.Axes]] = []
    for r in range(rows):
        for c in range(cols):
            ax_pairs.append((axes_grid[r, c * 2], axes_grid[r, c * 2 + 1]))

    # Fill in pairs
    for i, (oracle_case, llm_case) in enumerate(pairs):
        if i >= len(ax_pairs):
            break
        ax_o, ax_l = ax_pairs[i]
        a_min, a_max, b_min, b_max = _axis_limits([oracle_case, llm_case], pad=8.0)
        _draw_panel(
            ax_o, oracle_case,
            a_lim=(a_min, a_max), b_lim=(b_min, b_max),
            panel_label=oracle_label, is_oracle=True,
        )
        _draw_panel(
            ax_l, llm_case,
            a_lim=(a_min, a_max), b_lim=(b_min, b_max),
            panel_label=llm_label, is_oracle=False,
        )

    # Hide unused axes
    for i in range(len(pairs), len(ax_pairs)):
        ax_pairs[i][0].set_visible(False)
        ax_pairs[i][1].set_visible(False)

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
        try:
            fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
        except Exception:
            pass
        logger.info("Saved pair grid: %s", out_path)

    return fig
