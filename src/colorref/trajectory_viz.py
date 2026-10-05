"""LAB-space trajectory visualizations for ColorRef paper figures.

Plots guess paths in CIELAB (a*, b* plane with optional L inset), with
color-filled nodes, feedback-labeled arrows, and target marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.legend_handler import HandlerBase
from matplotlib.patches import Circle, FancyArrowPatch
from colorref.colors import lab_to_rgb

# Paper style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "figure.dpi": 150,
})

_PALETTE_TURNS = ["#5C6BC0", "#26A69A", "#FFA726", "#EF5350"]
_PATH_COLOR = "#1a1a1a"
_TARGET_COLOR = "#FFD700"
_TARGET_EDGE = "#1a1a1a"
_SAVE_PAD_INCHES = 0.05
_TIGHT_FIG_MARGINS = dict(left=0.08, right=0.96, top=0.92, bottom=0.10)
_FEEDBACK_FIG_MARGINS = dict(left=0.11, right=0.97, top=0.90, bottom=0.14)
_FEEDBACK_ROW_RATIO = 0.62
_FEEDBACK_RAIL_HSPACE = 0.34
_L_STRIP_SIZE = "20%"
_L_STRIP_PAD = 0.58
_L_BAR_COLOR = "#6B7B8C"


@dataclass
class TrajectoryCase:
    """One game instance ready for plotting."""

    example_id: int
    raw_name: str
    target_hex: str
    target_lab: tuple[float, float, float]
    turns: list[dict[str, Any]]  # turn, hex, lab, error_lab
    feedback: list[dict[str, Any]]  # turn, text
    condition: str = ""
    regime_label: str = ""


def _lab_from_row(row: pd.Series, prefix: str = "guess") -> tuple[float, float, float]:
    if prefix == "true":
        return float(row["true_lab_l"]), float(row["true_lab_a"]), float(row["true_lab_b"])
    return float(row["guess_lab_l"]), float(row["guess_lab_a"]), float(row["guess_lab_b"])


def load_trajectory_case(
    run_dir: Path | str,
    example_id: int | None = None,
    *,
    raw_name_contains: str | None = None,
    condition: str = "",
) -> TrajectoryCase:
    """Load one example from a run directory."""
    run_dir = Path(run_dir)
    traj = pd.read_parquet(run_dir / "games" / "trajectories.parquet")
    fb_path = run_dir / "games" / "feedback.parquet"
    feedback_df = pd.read_parquet(fb_path) if fb_path.exists() else pd.DataFrame()

    if example_id is None:
        if raw_name_contains is None:
            raise ValueError("Provide example_id or raw_name_contains")
        mask = traj["raw_name"].str.contains(raw_name_contains, case=False, na=False)
        example_id = int(traj.loc[mask, "example_id"].iloc[0])

    sub = traj[traj["example_id"] == example_id].sort_values("turn")
    if sub.empty:
        raise ValueError(f"example_id {example_id} not in {run_dir}")

    row0 = sub.iloc[0]
    target_lab = _lab_from_row(row0, "true")
    target_hex = str(row0["true_hex"])
    if not target_hex.startswith("#"):
        target_hex = f"#{target_hex}"

    turns = []
    for _, r in sub.iterrows():
        lab = _lab_from_row(r, "guess")
        hx = str(r["guess_hex"])
        if not hx.startswith("#"):
            hx = f"#{hx}"
        turns.append({
            "turn": int(r["turn"]),
            "hex": hx,
            "lab": lab,
            "error_lab": float(r["error_lab"]),
        })

    feedback = []
    if not feedback_df.empty:
        fsub = feedback_df[feedback_df["example_id"] == example_id].sort_values("turn")
        for _, r in fsub.iterrows():
            feedback.append({"turn": int(r["turn"]), "text": str(r["feedback_text"])})

    return TrajectoryCase(
        example_id=int(example_id),
        raw_name=str(row0["raw_name"]),
        target_hex=target_hex,
        target_lab=target_lab,
        turns=turns,
        feedback=feedback,
        condition=condition,
        regime_label=str(row0.get("regime_label", "")),
    )


def _save_trajectory_figure(fig: plt.Figure, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
    try:
        fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=_SAVE_PAD_INCHES)
    except Exception:
        pass
    plt.close(fig)
    return path


def _hex_mpl(hex_color: str) -> str:
    h = hex_color.strip()
    return h if h.startswith("#") else f"#{h}"


def _guess_node_mpl_color(
    case: TrajectoryCase,
    turn: dict[str, Any],
    *,
    node_color_mode: str = "hex",
) -> str:
    """Node fill on the a*b* plot.

    hex — actual guess sRGB from the model (default).
    chromaticity — color at (a*, b*) on the background slice (target L*).
    """
    if node_color_mode == "hex":
        return _hex_mpl(turn["hex"])
    if node_color_mode == "chromaticity":
        L_fix, a, b = case.target_lab[0], turn["lab"][1], turn["lab"][2]
        r, g, bch = lab_to_rgb(L_fix, a, b)
        return f"#{int(r):02x}{int(g):02x}{int(bch):02x}"
    raise ValueError(f"node_color_mode must be 'hex' or 'chromaticity', got {node_color_mode!r}")


def _wrap_feedback(text: str, max_len: int = 42) -> str:
    text = text.strip().rstrip(".")
    if len(text) <= max_len:
        return text
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    n = 0
    for w in words:
        if n + len(w) + 1 > max_len and cur:
            lines.append(" ".join(cur))
            cur, n = [w], len(w)
        else:
            cur.append(w)
            n += len(w) + (1 if n else 0)
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines[:3])


def _feedback_by_turn(case: TrajectoryCase) -> dict[int, str]:
    return {f["turn"]: f["text"] for f in case.feedback}


def _transition_feedbacks(case: TrajectoryCase) -> list[tuple[int, int, str, str]]:
    """Per-segment feedback: (turn_from, turn_to, text, arrow_color)."""
    fb_by_turn = _feedback_by_turn(case)
    out: list[tuple[int, int, str, str]] = []
    for i in range(len(case.turns) - 1):
        t0, t1 = case.turns[i], case.turns[i + 1]
        color = _PALETTE_TURNS[min(i, len(_PALETTE_TURNS) - 1)]
        out.append((t0["turn"], t1["turn"], fb_by_turn.get(t0["turn"], ""), color))
    return out


@dataclass(frozen=True)
class _LegendCircleHandle:
    """Proxy handle for circular legend swatches with optional dashed ring."""

    facecolor: str
    linewidth: float = 2.0
    linestyle: str | tuple = "solid"


class _HandlerLegendCircle(HandlerBase):
    """Filled circle + white ring (dashed or solid) for legend."""

    def create_artists(
        self,
        legend: Any,
        orig_handle: _LegendCircleHandle,
        xdescent: float,
        ydescent: float,
        width: float,
        height: float,
        fontsize: float,
        trans: Any,
    ) -> list[Circle]:
        r = 0.36 * min(width, height)
        cx = 0.5 * width - xdescent
        cy = 0.5 * height - ydescent
        fill = Circle(
            (cx, cy),
            r,
            facecolor=orig_handle.facecolor,
            edgecolor="none",
            transform=trans,
            zorder=1,
        )
        ring = Circle(
            (cx, cy),
            r,
            facecolor="none",
            edgecolor="white",
            linewidth=orig_handle.linewidth,
            transform=trans,
            zorder=2,
        )
        if orig_handle.linestyle == "solid":
            ring.set_linestyle("solid")
        else:
            # Fine dashes — thick strokes collapse to a few chunky arcs at legend size.
            ring.set_linestyle((0, (1.1, 0.85)))
        return [fill, ring]


def _border_style_legend_elems(case: TrajectoryCase) -> tuple[list[_LegendCircleHandle], list[str]]:
    """Legend swatches for guess (dashed white ring) vs target (solid white ring)."""
    guess = _LegendCircleHandle(
        facecolor="#888888",
        linewidth=1.15,
        linestyle=(0, (4, 2.5)),
    )
    target = _LegendCircleHandle(
        facecolor=_hex_mpl(case.target_hex),
        linewidth=1.4,
        linestyle="solid",
    )
    return [guess, target], ["Guess (dashed border)", "Target (solid border)"]


def _draw_lightness_strip(ax_l: plt.Axes, case: TrajectoryCase, *, horizontal: bool = True) -> None:
    """L* per turn — horizontal bars under the main plot by default."""
    turns_idx = [t["turn"] for t in case.turns]
    L_vals = [t["lab"][0] for t in case.turns]
    L_tgt = case.target_lab[0]

    if horizontal:
        ax_l.bar(turns_idx, L_vals, color=_L_BAR_COLOR, edgecolor="white", width=0.65)
        ax_l.axhline(L_tgt, color=_TARGET_EDGE, linestyle="--", linewidth=1.5, label="Target L*")
        ax_l.set_xlabel("Turn")
        ax_l.set_ylabel("L*")
        ax_l.set_title("Lightness", fontsize=8, pad=3)
        ax_l.set_xlim(min(turns_idx) - 0.5, max(turns_idx) + 0.5)
        ax_l.set_xticks(turns_idx)
        ax_l.set_ylim(0, 100)
        ax_l.legend(fontsize=6, loc="upper right", framealpha=0.92, borderpad=0.3)
    else:
        ax_l.barh(turns_idx, L_vals, color=_L_BAR_COLOR, edgecolor="white", height=0.65)
        ax_l.axvline(L_tgt, color=_TARGET_EDGE, linestyle="--", linewidth=1.5, label="Target L*")
        ax_l.set_xlabel("L*", fontsize=8)
        ax_l.set_ylabel("Turn", fontsize=8, labelpad=6)
        ax_l.yaxis.set_label_position("left")
        ax_l.set_title("Lightness", fontsize=8, pad=2)
        ax_l.set_xlim(0, 100)
        ax_l.invert_yaxis()
        ax_l.set_yticks(turns_idx)
        ax_l.tick_params(axis="y", labelsize=8, pad=2, left=True, labelleft=True, labelright=False)
        t_lo, t_hi = min(turns_idx), max(turns_idx)
        ax_l.set_ylim(t_hi + 0.5, t_lo - 0.5)
        ax_l.legend(fontsize=6, loc="lower right", framealpha=0.92, borderpad=0.3)


def _attach_l_strip(ax_main: plt.Axes) -> plt.Axes:
    """Narrow L* panel attached to the main axes (same height, no manual repositioning)."""
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    divider = make_axes_locatable(ax_main)
    return divider.append_axes("right", size=_L_STRIP_SIZE, pad=_L_STRIP_PAD)


def _feedback_rail_text(t0: int, t1: int, fb: str, *, max_len: int) -> str:
    """Compact one- or two-line feedback string for the bottom rail."""
    fb = fb.strip()
    one_line = f"{t0} → {t1}: {fb}"
    if len(one_line) <= max_len:
        return one_line
    return f"{t0} → {t1}:\n{_wrap_feedback(fb, max_len)}"


_FB_BBOX = dict(
    boxstyle="round,pad=0.10",
    facecolor="white",
    edgecolor="#cccccc",
    alpha=0.95,
    linewidth=0.8,
)


def _draw_feedback_rail(
    ax_fb: plt.Axes,
    case: TrajectoryCase,
    *,
    wrap_len: int = 38,
    per_turn_correct: dict[int, bool | None] | None = None,
    check_color: str = "#2e7d32",
    cross_color: str = "#c62828",
    base_color: str = "#222222",
) -> None:
    """Compact feedback row below the main + L* panels.

    When ``per_turn_correct`` is set (typical for LLM-teacher rails), each card
    for feedback turn ``t0`` appends a directional ✓/✗ and uses matching text color.
    """
    segs = [(t0, t1, fb, color) for t0, t1, fb, color in _transition_feedbacks(case) if fb]
    if not segs:
        ax_fb.set_visible(False)
        return

    n = len(segs)
    fb_font = 7.0
    per_col = max(28, min(wrap_len, int(54 / n)))
    texts: list[str] = []
    colors: list[str] = []
    edge_colors: list[str] = []
    for t0, t1, fb, color in segs:
        body = _feedback_rail_text(t0, t1, fb, max_len=per_col)
        if per_turn_correct is None:
            texts.append(body)
            colors.append(base_color)
            edge_colors.append("#cccccc")
            continue
        verdict = per_turn_correct.get(t0)
        if verdict is True:
            texts.append(body + " ✓")
            colors.append(check_color)
            edge_colors.append(check_color)
        elif verdict is False:
            texts.append(body + " ✗")
            colors.append(cross_color)
            edge_colors.append(cross_color)
        else:
            texts.append(body)
            colors.append(base_color)
            edge_colors.append("#cccccc")

    ax_fb.set_axis_off()
    # Pack boxes as a centered group rather than spreading across the full row.
    box_w = min(0.285, 0.92 / n)
    gap = 0.010
    total_w = n * box_w + (n - 1) * gap
    x0 = 0.5 - total_w / 2
    for i, text in enumerate(texts):
        x = x0 + i * (box_w + gap) + box_w / 2
        bbox = {**_FB_BBOX, "edgecolor": edge_colors[i]}
        ax_fb.text(
            x,
            0.5,
            text,
            ha="center",
            va="center",
            fontsize=fb_font,
            color=colors[i],
            transform=ax_fb.transAxes,
            bbox=bbox,
            linespacing=1.05,
            clip_on=False,
        )


def _annotate_feedback_leaders(
    ax: plt.Axes,
    case: TrajectoryCase,
    *,
    wrap_len: int = 32,
) -> None:
    """Place feedback outside the path with thin leader lines to each segment."""
    labs = [t["lab"] for t in case.turns]
    ab = np.array([[l[1], l[2]] for l in labs])
    centroid = ab.mean(axis=0)
    a_lim = ax.get_xlim()
    b_lim = ax.get_ylim()
    span = max(a_lim[1] - a_lim[0], b_lim[1] - b_lim[0])

    for i, (t0, t1, fb, color) in enumerate(_transition_feedbacks(case)):
        if not fb:
            continue
        p0 = (case.turns[i]["lab"][1], case.turns[i]["lab"][2])
        p1 = (case.turns[i + 1]["lab"][1], case.turns[i + 1]["lab"][2])
        mid = np.array([(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2])
        outward = mid - centroid
        norm = float(np.linalg.norm(outward))
        if norm < 1e-6:
            outward = np.array([1.0, 0.3])
            norm = float(np.linalg.norm(outward))
        outward /= norm
        label_xy = mid + outward * (0.22 * span)
        ax.annotate(
            _wrap_feedback(fb, wrap_len),
            xy=mid,
            xytext=label_xy,
            fontsize=7,
            ha="center",
            va="center",
            color="#111111",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor=color,
                alpha=0.94,
                linewidth=0.9,
            ),
            arrowprops=dict(
                arrowstyle="-",
                color=color,
                lw=0.9,
                shrinkA=4,
                shrinkB=6,
                connectionstyle="arc3,rad=0.08",
            ),
            zorder=6,
            linespacing=1.1,
        )


def _draw_ab_background(
    ax: plt.Axes,
    L_fix: float,
    a_lim: tuple[float, float],
    b_lim: tuple[float, float],
    resolution: int = 72,
    alpha: float = 0.92,
) -> None:
    """Soft chromaticity field at fixed L (makes LAB plane intuitive)."""
    a = np.linspace(a_lim[0], a_lim[1], resolution)
    b = np.linspace(b_lim[0], b_lim[1], resolution)
    aa, bb = np.meshgrid(a, b)
    rgb = np.zeros((resolution, resolution, 3), dtype=float)
    for j in range(resolution):
        for i in range(resolution):
            r, g, bch = lab_to_rgb(L_fix, float(aa[j, i]), float(bb[j, i]))
            rgb[j, i] = (r / 255.0, g / 255.0, bch / 255.0)
    ax.imshow(
        rgb,
        extent=[a_lim[0], a_lim[1], b_lim[0], b_lim[1]],
        origin="lower",
        aspect="auto",
        alpha=alpha,
        zorder=0,
        interpolation="bilinear",
    )


def _draw_convergence_disk(
    ax: plt.Axes,
    target_ab: tuple[float, float],
    target_lab: tuple[float, float, float],
    delta_e: float = 5.0,
    **kwargs: Any,
) -> None:
    """Approximate ΔE < 5 region as a circle in a*b* (slice at target L)."""
    # In LAB, sphere of radius delta_e; project to ab as circle radius ~ delta_e
    circ = Circle(
        target_ab,
        radius=delta_e,
        fill=True,
        facecolor="white",
        edgecolor="#2e7d32",
        linewidth=1.2,
        linestyle="--",
        alpha=0.35,
        zorder=1,
        **kwargs,
    )
    ax.add_patch(circ)


def _ab_span(case: TrajectoryCase) -> float:
    labs = [t["lab"] for t in case.turns]
    ab = np.array([[l[1], l[2]] for l in labs])
    target_ab = np.array([case.target_lab[1], case.target_lab[2]])
    all_pts = np.vstack([ab, target_ab.reshape(1, 2)])
    return float(max(all_pts[:, 0].max() - all_pts[:, 0].min(), all_pts[:, 1].max() - all_pts[:, 1].min()))


def plot_lightness_failure_trajectory(
    case: TrajectoryCase,
    out_path: Path | str | None = None,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (7.5, 5.2),
) -> plt.Figure:
    """For near-neutral guesses: show wrong movement in L* (feedback vs actual)."""
    fig, axes = plt.subplots(1, 2, figsize=figsize, gridspec_kw={"width_ratios": [1.4, 1]})

    ax_l, ax_ab = axes[0], axes[1]
    fb_by_turn = {f["turn"]: f["text"] for f in case.feedback}
    L_tgt = case.target_lab[0]

    turns = [t["turn"] for t in case.turns]
    L_vals = [t["lab"][0] for t in case.turns]
    errors = [t["error_lab"] for t in case.turns]

    for i in range(len(case.turns) - 1):
        t0, t1 = case.turns[i], case.turns[i + 1]
        ax_l.annotate(
            "",
            xy=(t1["turn"], t1["lab"][0]),
            xytext=(t0["turn"], t0["lab"][0]),
            arrowprops=dict(arrowstyle="-|>", color=_PALETTE_TURNS[i], lw=2.5),
        )
        fb = fb_by_turn.get(t0["turn"], "")
        if fb:
            ax_l.text(
                (t0["turn"] + t1["turn"]) / 2,
                (t0["lab"][0] + t1["lab"][0]) / 2 + 4,
                _wrap_feedback(fb, 38),
                fontsize=7.5,
                ha="center",
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor=_PALETTE_TURNS[i], alpha=0.95),
            )

    for i, t in enumerate(case.turns):
        ax_l.scatter(
            t["turn"],
            t["lab"][0],
            s=180 + 40 * (3 - i),
            c=_hex_mpl(t["hex"]),
            edgecolors="white",
            linewidths=2,
            zorder=5,
            label=f"Turn {t['turn']}",
        )
        ax_l.text(t["turn"], t["lab"][0] - 5, f"{t['turn']}", ha="center", fontsize=9, fontweight="bold", color="#333")

    ax_l.axhline(L_tgt, color=_TARGET_EDGE, linestyle="--", linewidth=2, label=f"Target L*={L_tgt:.0f}")
    ax_l.set_xlabel("Turn")
    ax_l.set_ylabel("L* (lightness)")
    ax_l.set_title("Lightness drifts wrong despite feedback", fontsize=10, fontweight="bold")
    ax_l.set_xticks(turns)
    ax_l.set_ylim(-2, max(max(L_vals), L_tgt) + 12)
    ax_l.grid(True, alpha=0.3)

    # Chromaticity inset: zoomed a*b*
    ab_tgt = (case.target_lab[1], case.target_lab[2])
    for t in case.turns:
        ax_ab.scatter(
            t["lab"][1],
            t["lab"][2],
            s=120,
            c=_hex_mpl(t["hex"]),
            edgecolors="white",
            linewidths=1.5,
        )
    ax_ab.scatter([ab_tgt[0]], [ab_tgt[1]], s=200, marker="*", c=_TARGET_COLOR, edgecolors="k")
    pad = 8
    ax_ab.set_xlim(ab_tgt[0] - pad, ab_tgt[0] + pad)
    ax_ab.set_ylim(ab_tgt[1] - pad, ab_tgt[1] + pad)
    ax_ab.set_xlabel("a*")
    ax_ab.set_ylabel("b*")
    ax_ab.set_title("Near-neutral chroma\n(zoomed)", fontsize=9)
    ax_ab.set_aspect("equal")
    ax_ab.grid(True, alpha=0.3)

    init_de, final_de = errors[0], errors[-1]
    fig.suptitle(
        title or f'"{case.raw_name}" — {case.condition}',
        fontsize=11,
        fontweight="bold",
        y=1.02,
    )
    fig.text(
        0.5,
        0.01,
        f"ΔE: {init_de:.1f} → {final_de:.1f}  ·  Teacher says darker; L* increases",
        ha="center",
        fontsize=9,
        style="italic",
        color="#b71c1c",
    )

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        try:
            fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
        except Exception:
            pass
        plt.close(fig)
    return fig


def plot_lab_trajectory_3d(
    case: TrajectoryCase,
    out_path: Path | str | None = None,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (7.5, 6.5),
    elev: float = 22,
    azim: float = -58,
) -> plt.Figure:
    """3D LAB path with color nodes and feedback labels (hero figure)."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")

    Ls = [t["lab"][0] for t in case.turns]
    As = [t["lab"][1] for t in case.turns]
    Bs = [t["lab"][2] for t in case.turns]
    for i in range(len(case.turns) - 1):
        ax.plot(
            [As[i], As[i + 1]],
            [Bs[i], Bs[i + 1]],
            [Ls[i], Ls[i + 1]],
            color=_PALETTE_TURNS[i],
            linewidth=2.5,
            alpha=0.9,
        )

    for i, t in enumerate(case.turns):
        ax.scatter(
            t["lab"][1],
            t["lab"][2],
            t["lab"][0],
            s=90 + 30 * (3 - i),
            c=_hex_mpl(t["hex"]),
            edgecolors="white",
            linewidths=1.2,
            depthshade=False,
            zorder=5,
        )
        ax.text(t["lab"][1], t["lab"][2], t["lab"][0] + 3, str(i), fontsize=8, fontweight="bold")

    ax.scatter(
        case.target_lab[1],
        case.target_lab[2],
        case.target_lab[0],
        s=220,
        marker="*",
        c=_TARGET_COLOR,
        edgecolors="k",
        linewidths=1,
        depthshade=False,
        label="Target",
    )

    # Shadow on a*b* floor
    l_floor = min(Ls) - 5
    ax.plot(As, Bs, [l_floor] * len(As), color="#888888", alpha=0.35, linestyle="--", linewidth=1)
    ax.plot(
        [case.target_lab[1]],
        [case.target_lab[2]],
        [l_floor],
        marker="*",
        color=_TARGET_COLOR,
        markersize=10,
        alpha=0.5,
    )

    ax.set_xlabel("a*")
    ax.set_ylabel("b*")
    ax.set_zlabel("L*")
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(title or f'"{case.raw_name}" in CIELAB', fontweight="bold", pad=12)

    segs = [(t0, t1, fb, color) for t0, t1, fb, color in _transition_feedbacks(case) if fb]
    if segs:
        fig.subplots_adjust(bottom=0.2)
        n = len(segs)
        for i, (t0, _t1, fb, color) in enumerate(segs):
            x = 0.08 + (i + 0.5) * 0.84 / n
            fig.text(
                x,
                0.06,
                f"Turn {t0}: {_wrap_feedback(fb, 36)}",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#111111",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    edgecolor=color,
                    alpha=0.95,
                    linewidth=0.9,
                ),
            )

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        try:
            fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
        except Exception:
            pass
        plt.close(fig)
    return fig


def plot_lab_trajectory(
    case: TrajectoryCase,
    out_path: Path | str | None = None,
    *,
    ax: plt.Axes | None = None,
    show_l_strip: bool = True,
    show_background: bool = True,
    show_ideal_arrows: bool = False,
    title: str | None = None,
    figsize: tuple[float, float] = (4.8, 5.0),
    force_ab_plane: bool = False,
    feedback_layout: str = "auto",
    node_color_mode: str = "hex",
) -> plt.Figure:
    """Plot one trajectory in the a*b* plane with feedback beside or below the path.

    feedback_layout:
        auto — bottom feedback rail + vertical L* strip when this function owns the figure; leaders when embedded
        rail — feedback cards in a row below the plots (default for standalone figures)
        leaders — offset labels with thin lines to each segment (compact multi-panel layouts)
        inline — legacy mid-path text boxes (can obscure the trajectory)
        none — trajectory only

    node_color_mode:
        hex — guess circles use the model's actual hex color
        chromaticity — guess fill matches the a*b* background at target L* (chromaticity only)
    """
    if not force_ab_plane and ax is None and out_path is not None and _ab_span(case) < 8.0:
        return plot_lightness_failure_trajectory(case, out_path, title=title, figsize=(figsize[0] + 1, figsize[1]))

    own_fig = ax is None
    if feedback_layout == "auto":
        feedback_layout = "rail" if own_fig else "leaders"

    has_feedback = any(fb for _, _, fb, _ in _transition_feedbacks(case))
    use_rail = own_fig and feedback_layout == "rail" and has_feedback

    if own_fig:
        if use_rail and show_l_strip:
            fig = plt.figure(figsize=(figsize[0] + 0.85, figsize[1] + 0.55))
            gs = fig.add_gridspec(
                2,
                1,
                height_ratios=[5.0, _FEEDBACK_ROW_RATIO],
                hspace=_FEEDBACK_RAIL_HSPACE,
                **_FEEDBACK_FIG_MARGINS,
            )
            ax = fig.add_subplot(gs[0, 0])
            ax_l = _attach_l_strip(ax)
            ax_fb = fig.add_subplot(gs[1, 0])
        elif use_rail:
            fig = plt.figure(figsize=(figsize[0], figsize[1] + 0.48))
            gs = fig.add_gridspec(
                2,
                1,
                height_ratios=[5.0, _FEEDBACK_ROW_RATIO],
                hspace=_FEEDBACK_RAIL_HSPACE,
                **_FEEDBACK_FIG_MARGINS,
            )
            ax = fig.add_subplot(gs[0, 0])
            ax_fb = fig.add_subplot(gs[1, 0])
            ax_l = None
        elif show_l_strip:
            fig = plt.figure(figsize=(figsize[0] + 0.85, figsize[1]))
            ax = fig.add_subplot(111)
            ax_l = _attach_l_strip(ax)
            ax_fb = None
            fig.subplots_adjust(**_TIGHT_FIG_MARGINS)
        else:
            fig, ax = plt.subplots(figsize=figsize)
            ax_l = None
            ax_fb = None
    else:
        fig = ax.figure
        ax_l = None
        ax_fb = None

    labs = [t["lab"] for t in case.turns]
    ab = np.array([[l[1], l[2]] for l in labs])
    target_ab = (case.target_lab[1], case.target_lab[2])

    pad = 18
    a_lim = (min(ab[:, 0].min(), target_ab[0]) - pad, max(ab[:, 0].max(), target_ab[0]) + pad)
    b_lim = (min(ab[:, 1].min(), target_ab[1]) - pad, max(ab[:, 1].max(), target_ab[1]) + pad)

    L_bg = case.target_lab[0]
    if show_background:
        _draw_ab_background(ax, L_bg, a_lim, b_lim)
    # Ideal direction hints (guess → target), faint
    if show_ideal_arrows:
        for i, t in enumerate(case.turns[:-1]):
            g = (t["lab"][1], t["lab"][2])
            ax.annotate(
                "",
                xy=target_ab,
                xytext=g,
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="#333333",
                    lw=0.9,
                    linestyle=(0, (4, 4)),
                    alpha=0.25,
                    shrinkA=8,
                    shrinkB=10,
                ),
                zorder=2,
            )

    # Guess nodes: dotted white ring, filled with guess color
    for i, t in enumerate(case.turns):
        a, b = t["lab"][1], t["lab"][2]
        fill = _guess_node_mpl_color(case, t, node_color_mode=node_color_mode)
        L_label = case.target_lab[0] if node_color_mode == "chromaticity" else t["lab"][0]
        circ = Circle(
            (a, b),
            radius=3.8,
            facecolor=fill,
            edgecolor="white",
            linewidth=2.0,
            linestyle=(0, (4, 2.5)),
            zorder=5,
        )
        ax.add_patch(circ)
        ax.text(
            a,
            b,
            str(i),
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="white" if L_label < 55 else "black",
            zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground="#00000044")],
        )

    # Path arrows on top of nodes so arrowheads stay visible (below turn labels)
    for i in range(len(case.turns) - 1):
        t0, t1 = case.turns[i], case.turns[i + 1]
        p0 = (t0["lab"][1], t0["lab"][2])
        p1 = (t1["lab"][1], t1["lab"][2])
        arrow = FancyArrowPatch(
            p0,
            p1,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.35,
            color=_PATH_COLOR,
            zorder=6,
            connectionstyle="arc3,rad=0.12",
            shrinkA=9,
            shrinkB=9,
        )
        ax.add_patch(arrow)

    # Ground truth: solid white ring, filled with target color
    target_circ = Circle(
        target_ab,
        radius=4.2,
        facecolor=_hex_mpl(case.target_hex),
        edgecolor="white",
        linewidth=2.5,
        linestyle="solid",
        zorder=9,
    )
    ax.add_patch(target_circ)

    cond = f" · {case.condition}" if case.condition else ""
    ttl = title or f'"{case.raw_name}"{cond}'
    ax.set_title(ttl, fontsize=11, fontweight="bold", pad=5)
    ax.set_xlabel("a* (green ← → red)")
    ax.set_ylabel("b* (blue ← → yellow)")
    ax.set_xlim(a_lim)
    ax.set_ylim(b_lim)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="white", alpha=0.4, linewidth=0.6, zorder=1)

    if show_l_strip and ax_l is not None:
        _draw_lightness_strip(ax_l, case, horizontal=False)

    legend_handles, legend_labels = _border_style_legend_elems(case)
    ax.legend(
        handles=legend_handles,
        labels=legend_labels,
        handler_map={_LegendCircleHandle: _HandlerLegendCircle()},
        loc="upper right",
        fontsize=7,
        framealpha=1.0,
        facecolor="#2b2b2b",
        edgecolor="#555555",
        labelcolor="white",
        borderpad=0.4,
        handlelength=1.15,
        handleheight=1.15,
    )

    if feedback_layout == "inline":
        fb_by_turn = _feedback_by_turn(case)
        for i in range(len(case.turns) - 1):
            t0 = case.turns[i]
            p0 = (t0["lab"][1], t0["lab"][2])
            p1 = (case.turns[i + 1]["lab"][1], case.turns[i + 1]["lab"][2])
            color = _PALETTE_TURNS[min(i, len(_PALETTE_TURNS) - 1)]
            fb = fb_by_turn.get(t0["turn"], "")
            if not fb:
                continue
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            ax.text(
                mid[0],
                mid[1],
                _wrap_feedback(fb, 36),
                fontsize=7.5,
                ha="center",
                va="center",
                color="#111111",
                bbox=dict(
                    boxstyle="round,pad=0.35",
                    facecolor="white",
                    edgecolor=color,
                    alpha=0.92,
                    linewidth=1.0,
                ),
                zorder=6,
                linespacing=1.15,
            )
    elif feedback_layout == "leaders":
        _annotate_feedback_leaders(ax, case)
    elif use_rail and ax_fb is not None:
        _draw_feedback_rail(ax_fb, case)

    if out_path is not None and own_fig:
        _save_trajectory_figure(fig, out_path)

    return fig


def plot_bandwidth_comparison(
    cases: list[TrajectoryCase],
    out_path: Path | str,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (11, 4.2),
    shared_limits: bool = True,
) -> plt.Figure:
    """Side-by-side trajectories (e.g. c1 vs c3) sharing chromaticity context."""
    n = len(cases)
    fig, axes = plt.subplots(1, n, figsize=figsize, squeeze=False)
    axes = axes[0]

    a_lim = b_lim = None
    if shared_limits:
        all_ab = []
        target_ab = None
        for case in cases:
            for t in case.turns:
                all_ab.append((t["lab"][1], t["lab"][2]))
            target_ab = (case.target_lab[1], case.target_lab[2])
        ab = np.array(all_ab)
        pad = 16
        a_lim = (min(ab[:, 0].min(), target_ab[0]) - pad, max(ab[:, 0].max(), target_ab[0]) + pad)
        b_lim = (min(ab[:, 1].min(), target_ab[1]) - pad, max(ab[:, 1].max(), target_ab[1]) + pad)

    for ax, case in zip(axes, cases):
        plot_lab_trajectory(
            case,
            ax=ax,
            show_l_strip=False,
            show_background=True,
            show_ideal_arrows=False,
            title=case.condition or case.raw_name,
            force_ab_plane=True,
        )
        if a_lim is not None and b_lim is not None:
            ax.set_xlim(a_lim)
            ax.set_ylim(b_lim)

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    return fig


def plot_paper_showcase(out_dir: Path | str) -> list[Path]:
    """Generate the full set of paper-ready trajectory figures."""
    root = Path(__file__).resolve().parents[2]
    runs = root / "runs"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    run_c3 = runs / "20260517_201025_feedback_axis_c3_main_qwen3_14b_axis_oracle_main_1000"
    run_c1 = runs / "20260517_171411_feedback_axis_c1_main_qwen3_14b_axis_oracle_main_1000"
    run_c2 = runs / "20260517_172906_feedback_axis_c2_main_qwen3_14b_axis_oracle_main_1000"
    run_llm = runs / "20260517_211306_feedback_llm_hex_only_debug_qwen3_14b_llm_teacher_hex_only_debug_400"
    run_oneshot = runs / "20260516_143421_oneshot_main_qwen3_14b_main_1000"

    # B1 — hero success (2D + 3D)
    c_success = load_trajectory_case(run_c3, raw_name_contains="anchored and alone", condition="axis c=3")
    p = out_dir / "hero_success_anchored_alone.png"
    plot_lab_trajectory(c_success, p, figsize=(7, 6), title=f'"{c_success.raw_name}" — interactive grounding')
    written.append(p)
    p3d = out_dir / "hero_success_anchored_alone_3d.png"
    plot_lab_trajectory_3d(c_success, p3d, title=f'"{c_success.raw_name}" — path in CIELAB')
    written.append(p3d)

    # B7 — bandwidth drama
    c_c1 = load_trajectory_case(run_c1, example_id=293676, condition="1 constraint / turn")
    c_c3 = load_trajectory_case(run_c3, example_id=293676, condition="3 constraints / turn")
    p = out_dir / "bandwidth_ms_paint_blue.png"
    plot_bandwidth_comparison(
        [c_c1, c_c3],
        p,
        title='"ms paint blue" — same guesser, different feedback bandwidth',
    )
    written.append(p)

    # B9 — c1 / c2 / c3 ladder
    cases_ladder = [
        load_trajectory_case(run_c1, example_id=197242, condition="c=1"),
        load_trajectory_case(run_c2, example_id=197242, condition="c=2"),
        load_trajectory_case(run_c3, example_id=197242, condition="c=3"),
    ]
    p = out_dir / "bandwidth_grape_shout_ladder.png"
    plot_bandwidth_comparison(
        cases_ladder,
        p,
        title='"grape shout" — feedback bandwidth ladder',
        figsize=(14, 4.5),
    )
    written.append(p)

    # B5 — LLM failure (L* drift visualization)
    c_llm = load_trajectory_case(run_llm, raw_name_contains="perilous night", condition="LLM teacher")
    p = out_dir / "llm_teacher_failure_perilous_night.png"
    plot_lightness_failure_trajectory(c_llm, p, title=f'"{c_llm.raw_name}" — misaligned LLM feedback')
    written.append(p)

    # One-shot vs final (overlay): oneshot only has turn 0; load c3 for same example crooked sea
    c_game = load_trajectory_case(run_c3, raw_name_contains="crooked sea", condition="axis c=3 (3 turns)")
    p = out_dir / "prototype_crooked_sea.png"
    plot_lab_trajectory(c_game, p)
    written.append(p)

    # Composite "wow" poster — 2x2
    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.18)
    panels = [
        (gs[0, 0], c_success, "Success: abstract description"),
        (gs[0, 1], c_c3, "Bandwidth wins (ms paint blue, c=3)"),
        (gs[1, 0], c_c1, "Failure mode: 1-constraint oscillation"),
        (gs[1, 1], cases_ladder[2], "Converged in LAB (grape shout, c=3)"),
    ]
    for spec, case, subtitle in panels:
        ax = fig.add_subplot(spec)
        plot_lab_trajectory(
            case,
            ax=ax,
            show_l_strip=False,
            title=subtitle,
            force_ab_plane=True,
        )
    fig.suptitle(
        "ColorRef: color grounding trajectories in CIELAB (a*, b*)",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    p = out_dir / "poster_showcase_2x2.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    try:
        fig.savefig(p.with_suffix(".pdf"), bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    written.append(p)

    return written


def _slug_name(raw_name: str, max_len: int = 48) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in raw_name.lower()).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:max_len].rstrip("_") or "unnamed"


def rank_intro_candidates(
    run_dir: Path | str,
    *,
    min_turns: int = 4,
    min_ab_span: float = 12.0,
) -> pd.DataFrame:
    """Score examples for intro-style trajectory figures (higher = better)."""
    run_dir = Path(run_dir)
    traj = pd.read_parquet(run_dir / "games" / "trajectories.parquet")
    fb_path = run_dir / "games" / "feedback.parquet"
    feedback_df = pd.read_parquet(fb_path) if fb_path.exists() else pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for example_id, sub in traj.groupby("example_id"):
        sub = sub.sort_values("turn")
        if len(sub) < min_turns:
            continue

        labs = sub[["guess_lab_a", "guess_lab_b"]].to_numpy()
        target_ab = np.array([float(sub.iloc[0]["true_lab_a"]), float(sub.iloc[0]["true_lab_b"])])
        all_ab = np.vstack([labs, target_ab.reshape(1, 2)])
        ab_span = float(
            max(all_ab[:, 0].max() - all_ab[:, 0].min(), all_ab[:, 1].max() - all_ab[:, 1].min())
        )
        if ab_span < min_ab_span:
            continue

        init_de = float(sub.iloc[0]["error_lab"])
        final_de = float(sub.iloc[-1]["error_lab"])
        improvement = init_de - final_de
        raw_name = str(sub.iloc[0]["raw_name"])
        regime = str(sub.iloc[0].get("regime_label", ""))

        n_fb = 0
        if not feedback_df.empty:
            n_fb = int((feedback_df["example_id"] == example_id).sum())

        # Favor visible arcs, clear improvement, near-convergence, readable names.
        score = 0.0
        score += min(ab_span, 55) * 0.45
        score += min(max(improvement, 0), 45) * 0.35
        if 4 <= final_de <= 22:
            score += 12
        elif final_de < 5:
            score += 6
        if 25 <= init_de <= 70:
            score += 8
        if 8 <= len(raw_name) <= 32:
            score += 4
        if n_fb >= min_turns - 1:
            score += 5
        if regime in {"prototype_mediated", "compound_associative"}:
            score += 3

        rows.append({
            "example_id": int(example_id),
            "raw_name": raw_name,
            "regime_label": regime,
            "init_de": init_de,
            "final_de": final_de,
            "improvement": improvement,
            "ab_span": ab_span,
            "n_turns": len(sub),
            "n_feedback": n_fb,
            "intro_score": score,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("intro_score", ascending=False).reset_index(drop=True)


def _write_prototype_index(
    out_dir: Path,
    entries: list[dict[str, Any]],
    *,
    run_label: str,
) -> Path:
    """Simple HTML gallery for hand-picking intro figures."""
    cards = []
    for e in entries:
        png = e["png_name"]
        cards.append(
            f"""<article class="card">
  <a href="{png}"><img src="{png}" alt="{e['raw_name']}" loading="lazy" /></a>
  <h3><a href="{png}">{e['raw_name']}</a></h3>
  <dl>
    <dt>example</dt><dd>{e['example_id']}</dd>
    <dt>regime</dt><dd>{e['regime_label']}</dd>
    <dt>ΔE</dt><dd>{e['init_de']:.0f} → {e['final_de']:.1f}</dd>
    <dt>score</dt><dd>{e['intro_score']:.1f}</dd>
  </dl>
</article>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ColorRef prototype candidates — {run_label}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #f6f6f6; }}
    h1 {{ font-size: 1.35rem; }}
    .meta {{ color: #555; margin-bottom: 1.25rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 1.25rem; }}
    .card {{ background: #fff; border-radius: 8px; padding: 0.75rem; box-shadow: 0 1px 4px #0002; }}
    .card img {{ width: 100%; height: auto; border-radius: 4px; }}
    .card h3 {{ margin: 0.5rem 0 0.25rem; font-size: 0.95rem; }}
    .card dl {{ display: grid; grid-template-columns: auto 1fr; gap: 0.15rem 0.6rem; margin: 0; font-size: 0.82rem; color: #444; }}
    .card dt {{ font-weight: 600; }}
  </style>
</head>
<body>
  <h1>Prototype trajectory candidates</h1>
  <p class="meta">Run: <code>{run_label}</code> · {len(entries)} figures · sorted by intro score</p>
  <div class="grid">
{''.join(cards)}
  </div>
</body>
</html>"""

    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def plot_prototype_candidates(
    run_dir: Path | str,
    out_dir: Path | str,
    *,
    n: int = 48,
    strategy: str = "curated",
    min_turns: int = 4,
    seed: int = 0,
    condition: str = "axis c=3",
    node_color_mode: str = "hex",
) -> list[Path]:
    """Generate single-game prototype figures for hand-picking a paper intro.

    strategy:
        curated — top-N by intro_score (default)
        random — random sample among scored candidates
        stratified — top picks per regime_label (balanced)
    """
    run_dir = Path(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ranked = rank_intro_candidates(run_dir, min_turns=min_turns)
    if ranked.empty:
        return []

    if strategy == "curated":
        picks = ranked.head(n)
    elif strategy == "random":
        rng = np.random.default_rng(seed)
        k = min(n, len(ranked))
        idx = rng.choice(len(ranked), size=k, replace=False)
        picks = ranked.iloc[idx].sort_values("intro_score", ascending=False)
    elif strategy == "stratified":
        per = max(1, n // 4)
        parts = []
        for regime in ranked["regime_label"].unique():
            sub = ranked[ranked["regime_label"] == regime].head(per)
            parts.append(sub)
        picks = pd.concat(parts).drop_duplicates("example_id").head(n)
        picks = picks.sort_values("intro_score", ascending=False)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    written: list[Path] = []
    index_entries: list[dict[str, Any]] = []

    for row in picks.itertuples(index=False):
        case = load_trajectory_case(run_dir, example_id=int(row.example_id), condition=condition)
        png_name = f"{int(row.example_id):06d}_{_slug_name(case.raw_name)}.png"
        out_path = out_dir / png_name
        plot_lab_trajectory(
            case,
            out_path,
            title=f'"{case.raw_name}"',
            figsize=(4.8, 4.9),
            node_color_mode=node_color_mode,
        )
        written.append(out_path)
        index_entries.append({
            "png_name": png_name,
            "example_id": int(row.example_id),
            "raw_name": case.raw_name,
            "regime_label": str(row.regime_label),
            "init_de": float(row.init_de),
            "final_de": float(row.final_de),
            "intro_score": float(row.intro_score),
        })

    csv_path = out_dir / "candidates.csv"
    picks.to_csv(csv_path, index=False)

    index_path = _write_prototype_index(out_dir, index_entries, run_label=run_dir.name)
    written.append(csv_path)
    written.append(index_path)
    return written


def save_figure(fig: plt.Figure, path: Path | str) -> Path:
    return _save_trajectory_figure(fig, path)
