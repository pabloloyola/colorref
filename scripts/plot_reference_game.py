"""Draw an illustrative reference game, with no experimental outputs or metrics.

The example colors and correction are constructed for explanation. They must
not be attributed to a model, a measured trajectory, or a historical run.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402


def main():
    directory = Path(__file__).resolve().parents[1] / "paper/latex/figures"
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.98)
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 2.6)
    ax.axis("off")

    def box(x, y, width, height, fill="#f5f7f9"):
        ax.add_patch(FancyBboxPatch(
            (x, y), width, height, boxstyle="round,pad=0.025,rounding_size=0.06",
            linewidth=0.8, edgecolor="#66717b", facecolor=fill,
        ))

    def arrow(start, end):
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "color": "#46505b", "lw": 1.0})

    def swatch(x, y, color):
        ax.add_patch(Rectangle((x, y), 0.38, 0.30,
                               facecolor=color, edgecolor="#66717b", linewidth=0.6))

    # Visible description and teacher-only target stay separate.
    box(0.15, 1.98, 1.90, 0.48)
    ax.text(1.10, 2.32, "Description", ha="center", va="center", weight="bold")
    ax.text(1.10, 2.10, '"dark green"', ha="center", va="center")
    box(2.55, 1.98, 1.90, 0.48, "#edf5ee")
    swatch(2.73, 2.07, "#35734c")
    ax.text(3.23, 2.30, "Hidden target", va="center", weight="bold")
    ax.text(3.23, 2.10, "Teacher only", va="center", fontsize=8)

    box(0.15, 0.68, 1.90, 0.92)
    ax.text(1.10, 1.40, "1. Guesser predicts", ha="center", weight="bold")
    swatch(0.48, 0.96, "#5b8ec7")
    ax.text(1.05, 1.11, "Initial guess", va="center")
    ax.text(1.10, 0.81, "Target is not shown", ha="center", fontsize=8)

    box(2.55, 0.68, 1.90, 0.92, "#edf5ee")
    ax.text(3.50, 1.40, "2. Teacher corrects", ha="center", weight="bold")
    ax.text(3.50, 1.10, '"A little darker', ha="center", style="italic")
    ax.text(3.50, 0.91, 'and more green."', ha="center", style="italic")

    box(4.95, 0.68, 1.90, 0.92)
    ax.text(5.90, 1.40, "3. Guesser revises", ha="center", weight="bold")
    swatch(5.26, 0.96, "#4c866e")
    ax.text(5.83, 1.11, "Revised guess", va="center")
    ax.text(5.90, 0.81, "Direction + step size", ha="center", fontsize=8)

    arrow((1.10, 1.98), (1.10, 1.60))
    arrow((3.50, 1.98), (3.50, 1.60))
    arrow((2.05, 1.15), (2.55, 1.15))
    arrow((4.45, 1.15), (4.95, 1.15))
    ax.text(2.30, 1.31, "Guess", ha="center", fontsize=7.5)
    ax.text(4.70, 1.31, "Feedback", ha="center", fontsize=7.5)

    # The new guess returns to the teacher; the loop is bounded by the protocol.
    ax.plot([5.90, 5.90, 3.50], [0.68, 0.38, 0.38], color="#46505b", lw=1.0)
    arrow((3.50, 0.38), (3.50, 0.68))
    ax.text(4.70, 0.16, "Compare again; repeat until stopping or the revision cap",
            ha="center", fontsize=8)

    fig.savefig(directory / "reference_game.pdf")
    fig.savefig(directory / "reference_game.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
