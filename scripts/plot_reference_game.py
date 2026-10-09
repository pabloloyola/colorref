"""Compact vector robot diagram, optionally using a saved compact HEX example.

The default is constructed; --compact-export supplies measured states/messages.
"""

import argparse
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402


def robot(ax, x, y, color):
    """Small vector icon, with no font/emoji or external image dependency."""
    edge = "#354657"
    ax.plot([x, x], [y + 0.35, y + 0.46], color=edge, lw=0.9)
    ax.add_patch(Circle((x, y + 0.47), 0.028, fc=color, ec=edge, lw=0.7))
    ax.add_patch(FancyBboxPatch(
        (x - 0.17, y + 0.12), 0.34, 0.24,
        boxstyle="round,pad=0.008,rounding_size=0.045",
        facecolor=color, edgecolor=edge, linewidth=0.9,
    ))
    for dx in (-0.08, 0.08):
        ax.add_patch(Circle((x + dx, y + 0.25), 0.029, fc="white", ec=edge, lw=0.6))
        ax.plot([x + dx, x + dx], [y - 0.015, y - 0.06], color=edge, lw=1.5)
    ax.plot([x - 0.065, x + 0.065], [y + 0.17, y + 0.17], color=edge, lw=0.9)
    ax.add_patch(FancyBboxPatch(
        (x - 0.125, y), 0.25, 0.105,
        boxstyle="round,pad=0.005,rounding_size=0.025",
        facecolor=color, edgecolor=edge, linewidth=0.8,
    ))
    for sign in (-1, 1):
        ax.plot([x + sign * 0.13, x + sign * 0.2],
                [y + 0.075, y + 0.01], color=edge, lw=1.2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact-export", type=Path)
    parser.add_argument("--example-id")
    args = parser.parse_args()
    description, target, initial, revised = "dark green", "#35734c", "#5b8ec7", "#4c866e"
    message = "A little darker and more green."
    if args.compact_export:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from colorref.saved_trajectory_figures import load_compact_trajectories
        cases = load_compact_trajectories(args.compact_export)
        selected = [c for c in cases if c["task"]["example"]["example_id"] == args.example_id]
        if len(selected) != 1:
            parser.error("Select one exported --example-id")
        case = selected[0]
        description = case["task"]["example"]["raw_name"]
        target = case["target"]["hex"]
        initial, revised = [r["displayed_state"]["hex"] for r in case["records"][:2]]
        message = case["records"][1]["feedback"]["text"]
    directory = Path(__file__).resolve().parents[1] / "paper/latex/figures"
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(7.4, 2.55))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.98)
    ax.set(xlim=(0, 7.4), ylim=(0, 2.55))
    ax.axis("off")

    def box(x, y, width, height, fill="#f3f6fa", edge="#748394"):
        ax.add_patch(FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.02,rounding_size=0.055",
            linewidth=0.8, edgecolor=edge, facecolor=fill,
        ))

    def arrow(start, end):
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "color": "#46505b", "lw": 1.1})

    def swatch(x, y, color):
        ax.add_patch(Rectangle((x, y), 0.40, 0.29,
                               facecolor=color, edgecolor="#66717b", linewidth=0.6))

    # Inputs are above their receiving role; target has no guesser arrow.
    box(0.12, 1.96, 2.03, 0.47)
    ax.text(1.14, 2.29, "Color description", ha="center", va="center", weight="bold")
    ax.text(1.14, 2.09, f'"{description}"', ha="center", va="center", fontsize=8.5)
    box(2.68, 1.96, 2.04, 0.47, "#eef6ee")
    swatch(2.82, 2.05, target)
    ax.text(3.36, 2.29, "Recorded target", va="center", weight="bold")
    ax.text(3.36, 2.08, "Visible to teacher only", va="center", fontsize=8)

    for x, fill, role, icon_color in (
        (0.12, "#f3f6fa", "Guesser", "#8fb7df"),
        (2.68, "#eef6ee", "Teacher", "#91c6a0"),
        (5.25, "#f3f6fa", "Guesser", "#8fb7df"),
    ):
        box(x, 0.59, 2.03, 1.12, fill)
        robot(ax, x + 0.38, 1.20, icon_color)
        ax.text(x + 0.76, 1.44, role, weight="bold", va="center")

    swatch(0.38, 0.80, initial)
    ax.text(0.94, 1.00, "1. Initial guess", va="center", weight="bold", fontsize=8.5)
    ax.text(0.94, 0.79, "From description", va="center", fontsize=8)
    ax.text(3.70, 1.00, "2. Verbal correction", ha="center", weight="bold", fontsize=8.5)
    ax.text(3.70, 0.85, textwrap.fill(f'"{message}"', width=29),
            ha="center", va="top", fontsize=7.8, style="italic")
    swatch(5.51, 0.80, revised)
    ax.text(6.07, 1.00, "3. Revised guess", va="center", weight="bold", fontsize=8.5)
    ax.text(6.07, 0.79, "Direction + step size", va="center", fontsize=8)

    arrow((1.14, 1.96), (1.14, 1.71))
    arrow((3.70, 1.96), (3.70, 1.71))
    arrow((2.15, 1.22), (2.68, 1.22))
    arrow((4.72, 1.22), (5.25, 1.22))
    ax.text(2.415, 1.38, "Guess", ha="center", fontsize=7.7)
    ax.text(4.985, 1.38, "Feedback", ha="center", fontsize=7.7)

    ax.plot([6.26, 6.26, 3.70], [0.59, 0.33, 0.33], color="#46505b", lw=1.1)
    arrow((3.70, 0.33), (3.70, 0.59))
    ax.text(4.99, 0.09, "New guess returns to the teacher; repeat until stopping or the cap",
            ha="center", fontsize=7.8)
    fig.savefig(directory / "reference_game.pdf")
    fig.savefig(directory / "reference_game.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
