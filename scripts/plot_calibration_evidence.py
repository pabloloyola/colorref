"""Plot reported calibration contrasts; no raw-response analysis or inference."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "paper/overleaf/figures"
    directory.mkdir(parents=True, exist_ok=True)
    previews = root / "reports/figures/paper"
    previews.mkdir(parents=True, exist_ok=True)
    data = json.loads((root / "artifacts/paper/figure-data/calibration_effects.json").read_text())
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.75), gridspec_kw={"width_ratios": [1, 1.25]})
    colors = ["#20639b", "#b34d12"]
    markers = ["o", "s"]
    for index, model in enumerate(data["models"]):
        mean, low, high = model["overall"]
        axes[0].errorbar(mean, 1 - index, xerr=[[mean - low], [high - mean]],
                         fmt=markers[index], color=colors[index], capsize=4, markersize=5)
        for position, distance in enumerate(["6", "12", "24"]):
            mean, low, high = model["distance"][distance]
            axes[1].errorbar(mean, 2 - position + (0.10 if index == 0 else -0.10),
                             xerr=[[mean - low], [high - mean]], fmt=markers[index],
                             color=colors[index], capsize=3, markersize=4,
                             label=model["name"] if position == 0 else None)
    axes[0].set_yticks([1, 0], [m["name"] for m in data["models"]])
    axes[0].set_ylim(-0.5, 1.5)
    axes[0].set_xlim(-6.4, 0.4)
    axes[0].set_xticks([-6, -4, -2, 0])
    axes[0].set_title("(a) Primary aggregate contrast", loc="left", fontsize=9)
    axes[1].set_yticks([2, 1, 0], ["6 units", "12 units", "24 units"])
    axes[1].set_ylim(-0.6, 2.6)
    axes[1].set_xlim(-21, 1)
    axes[1].set_xticks([-20, -15, -10, -5, 0])
    axes[1].set_title("(b) Requested distance (exploratory)", loc="left", fontsize=9)
    axes[1].legend(frameon=False, loc="lower right", fontsize=8)
    for axis in axes:
        axis.axvline(0, color="#777777", linestyle="--", linewidth=0.8, zorder=0)
        axis.set_xlabel("Calibrated minus unfitted error")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
        axis.grid(axis="x", alpha=0.15)
    fig.text(0.5, 0.01, "Negative favors calibration; bars show 95% cluster intervals.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=2)
    fig.savefig(directory / "calibration_effects.pdf", bbox_inches="tight")
    fig.savefig(previews / "calibration_effects.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
