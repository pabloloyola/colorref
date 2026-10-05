"""Paper-facing figures and combined reports for multi-run comparisons."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from colorref.geometry import alignment_summary_df, compute_geometry_alignment
from colorref.plotting import (
    _PALETTE,
    _REGIME_LABELS,
    _REGIME_ORDER,
    _save,
    plot_error_by_turn_multi,
    plot_relative_improvement_multi,
)

ComparisonKind = Literal["bandwidth", "llm", "model", "final_main_4000"]

_BANDWIDTH_ORDER = [
    "axis_c1",
    "axis_c2",
    "axis_c3",
    "template_c1",
    "template_c2",
    "template_c3",
    "minimal_c1",
    "minimal_main",
]

_FINAL_ORDER = [
    "oneshot",
    "axis_c3",
    "minimal_c1",
    "template_c3",
    "template_oracle_llm_vocab",
]

_LLM_ORDER = [
    "llm_teacher_hex_only",
    "llm_teacher_lab_aware",
    "llm_teacher_oracle_assisted",
    "template_oracle_llm_vocab",
]

_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_LAB_RE = re.compile(r"\b(?:L\*?|a\*?|b\*?)\s*[=:]\s*[-+]?\d", re.I)
_RGB_RE = re.compile(r"\bRGB\s*[\(:]?\s*\d", re.I)


def condition_label_from_run_id(run_id: str) -> str:
    """Short condition label parsed from a run directory name."""
    if "oneshot" in run_id:
        return "oneshot"
    m = re.search(r"feedback_(.+?)_(?:main|debug|qwen3)", run_id)
    if m:
        label = m.group(1)
        if label == "minimal":
            return "minimal_c1"
        if label == "template_llm_vocab":
            return "template_oracle_llm_vocab"
        return label
    if "template_llm_vocab" in run_id:
        return "template_oracle_llm_vocab"
    return run_id.split("_")[2] if len(run_id.split("_")) > 2 else run_id


def max_constraints_from_label(label: str) -> int:
    m = re.search(r"_c(\d+)$", label)
    if m:
        return int(m.group(1))
    if label.startswith("minimal"):
        return 1
    if label == "oneshot":
        return 0
    if "llm" in label or "template_oracle" in label:
        return 1
    return 1


def teacher_family_from_label(label: str) -> str:
    if label.startswith("axis"):
        return "axis"
    if label.startswith("template"):
        return "template"
    if label.startswith("minimal"):
        return "minimal"
    if label.startswith("llm"):
        return "llm"
    if label == "oneshot":
        return "oneshot"
    return "other"


def _figures_dir(out_dir: Path) -> Path:
    d = out_dir / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_combined(out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    pe_path = out_dir / "combined_per_example.parquet"
    if not pe_path.exists():
        raise FileNotFoundError(f"Missing {pe_path}; run evaluate/compare first.")
    pe = pd.read_parquet(pe_path)
    pe = pe.copy()
    pe["condition"] = pe["run_id"].map(condition_label_from_run_id)
    traj_path = out_dir / "combined_per_turn.parquet"
    traj = pd.read_parquet(traj_path) if traj_path.exists() else None
    if traj is not None:
        traj = traj.copy()
        traj["condition"] = traj["run_id"].map(condition_label_from_run_id)
    return pe, traj


def _metric_barplot(
    summary: pd.DataFrame,
    *,
    y_col: str,
    ylabel: str,
    title: str,
    out_dir: Path,
    stem: str,
    order: list[str],
    hue_col: str | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(max(7, len(order) * 0.9), 4.5))
    labels = [l for l in order if l in summary.index]
    if not labels:
        plt.close(fig)
        return

    if hue_col and hue_col in summary.columns:
        families = sorted(summary[hue_col].dropna().unique())
        x = np.arange(len(labels))
        width = 0.8 / max(len(families), 1)
        for i, fam in enumerate(families):
            sub = summary[summary[hue_col] == fam]
            vals = [sub.loc[l, y_col] if l in sub.index else np.nan for l in labels]
            errs = [sub.loc[l, f"{y_col}_sem"] if l in sub.index else 0.0 for l in labels]
            offset = (i - len(families) / 2 + 0.5) * width
            ax.bar(
                x + offset,
                vals,
                width * 0.9,
                yerr=errs,
                capsize=3,
                label=fam,
                color=_PALETTE[i % len(_PALETTE)],
                alpha=0.88,
            )
        ax.legend(fontsize=9)
    else:
        vals = [summary.loc[l, y_col] for l in labels]
        errs = [summary.loc[l, f"{y_col}_sem"] for l in labels]
        ax.bar(range(len(labels)), vals, yerr=errs, capsize=4, color=_PALETTE[0], alpha=0.88)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, out_dir, stem)


def _summarize_by_condition(pe: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cond, g in pe.groupby("condition"):
        rows.append(
            {
                "condition": cond,
                "family": teacher_family_from_label(cond),
                "max_constraints": max_constraints_from_label(cond),
                "n": len(g),
                "final_error_lab": g["final_error_lab"].mean(),
                "final_error_lab_sem": g["final_error_lab"].sem(),
                "relative_improvement": g["relative_improvement"].mean(),
                "relative_improvement_sem": g["relative_improvement"].sem(),
                "mean_constraint_satisfaction": g["mean_constraint_satisfaction"].mean(),
                "mean_constraint_satisfaction_sem": g["mean_constraint_satisfaction"].sem(),
                "mean_directional_alignment": g["mean_directional_alignment"].mean(),
                "mean_directional_alignment_sem": g["mean_directional_alignment"].sem(),
                "convergence_rate": g["converged"].mean() if "converged" in g.columns else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("condition")


def plot_bandwidth_figures(pe: pd.DataFrame, traj: pd.DataFrame | None, fig_dir: Path) -> None:
    summary = _summarize_by_condition(pe)
    order = [c for c in _BANDWIDTH_ORDER if c in summary.index] + [
        c for c in summary.index if c not in _BANDWIDTH_ORDER
    ]

    _metric_barplot(
        summary,
        y_col="final_error_lab",
        ylabel="Mean final ΔE",
        title="Final error by bandwidth condition",
        out_dir=fig_dir,
        stem="final_error_by_constraints",
        order=order,
        hue_col="family",
    )

    _metric_barplot(
        summary,
        y_col="relative_improvement",
        ylabel="Mean relative improvement",
        title="Relative improvement by bandwidth condition",
        out_dir=fig_dir,
        stem="relative_improvement_by_constraints",
        order=order,
        hue_col="family",
    )

    _metric_barplot(
        summary,
        y_col="mean_constraint_satisfaction",
        ylabel="Constraint satisfaction",
        title="Constraint satisfaction by bandwidth condition",
        out_dir=fig_dir,
        stem="constraint_satisfaction_by_constraints",
        order=order,
        hue_col="family",
    )

    _metric_barplot(
        summary,
        y_col="mean_directional_alignment",
        ylabel="Directional alignment",
        title="Directional alignment by bandwidth condition",
        out_dir=fig_dir,
        stem="directional_alignment_by_constraints",
        order=order,
        hue_col="family",
    )

    # Error vs max constraints (axis vs template families)
    fig, ax = plt.subplots(figsize=(6, 4))
    for fam, color in zip(("axis", "template", "minimal"), _PALETTE):
        sub = summary[summary["family"] == fam]
        if sub.empty:
            continue
        ax.plot(
            sub["max_constraints"],
            sub["final_error_lab"],
            marker="o",
            label=fam,
            color=color,
            linewidth=2,
        )
    ax.set_xlabel("Max constraints per message")
    ax.set_ylabel("Mean final ΔE")
    ax.set_title("Final error vs feedback bandwidth")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save(fig, fig_dir, "final_error_vs_max_constraints")

    # Regime × condition heatmap (final error)
    if "regime_label" in pe.columns:
        pivot = pe.pivot_table(
            index="regime_label",
            columns="condition",
            values="final_error_lab",
            aggfunc="mean",
        )
        regimes = [r for r in _REGIME_ORDER if r in pivot.index]
        cols = [c for c in order if c in pivot.columns]
        if regimes and cols:
            fig, ax = plt.subplots(figsize=(max(8, len(cols) * 0.7), 4))
            data = pivot.loc[regimes, cols].values
            im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
            ax.set_xticks(range(len(cols)))
            ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=8)
            ax.set_yticks(range(len(regimes)))
            ax.set_yticklabels([_REGIME_LABELS.get(r, r) for r in regimes])
            plt.colorbar(im, ax=ax, label="Mean final ΔE")
            ax.set_title("Final error by regime × condition")
            fig.tight_layout()
            _save(fig, fig_dir, "regime_x_bandwidth_final_error")

    if traj is not None and not traj.empty:
        runs = []
        for cond in order:
            sub = traj[traj["condition"] == cond]
            if not sub.empty:
                runs.append((cond, sub))
        if runs:
            plot_error_by_turn_multi(
                runs,
                fig_dir,
                stem="error_by_turn_bandwidth",
                title="Error by turn — bandwidth ablation",
            )


def plot_llm_figures(
    pe: pd.DataFrame,
    traj: pd.DataFrame | None,
    fig_dir: Path,
    audit_path: Path | None,
) -> None:
    summary = _summarize_by_condition(pe)
    order = [c for c in _LLM_ORDER if c in summary.index]

    _metric_barplot(
        summary,
        y_col="final_error_lab",
        ylabel="Mean final ΔE",
        title="Final error — LLM teacher decomposition",
        out_dir=fig_dir,
        stem="llm_teacher_final_error",
        order=order,
    )

    if traj is not None and not traj.empty:
        runs = [(c, traj[traj["condition"] == c]) for c in order if c in traj["condition"].values]
        if runs:
            plot_error_by_turn_multi(
                runs,
                fig_dir,
                stem="error_by_turn_llm_teacher_variants",
                title="Error by turn — LLM teacher variants",
            )

    if audit_path and audit_path.exists():
        audit = pd.read_csv(audit_path)
        _plot_llm_audit_figures(audit, pe, fig_dir)


def _plot_llm_audit_figures(audit: pd.DataFrame, pe: pd.DataFrame, fig_dir: Path) -> None:
    variant_col = "teacher_variant" if "teacher_variant" in audit.columns else None
    if not variant_col:
        return

    detected = audit[audit["detected_axis"].notna()].copy()
    if not detected.empty:
        prec = (
            detected.groupby(variant_col)["teacher_constraint_correct"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "precision"})
        )
        fig, ax = plt.subplots(figsize=(7, 4))
        labels = [v for v in _LLM_ORDER if v in prec.index]
        vals = [prec.loc[v, "precision"] for v in labels]
        ax.bar(range(len(labels)), vals, color=_PALETTE[: len(labels)], alpha=0.88)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels([v.replace("llm_teacher_", "") for v in labels], rotation=25, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Directional precision (detected constraints)")
        ax.set_title("Teacher directional correctness by variant")
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        _save(fig, fig_dir, "teacher_precision_recall_by_variant")

    # Leakage heuristic from feedback text
    def _leakage(text: str) -> bool:
        if not isinstance(text, str):
            return False
        return bool(_HEX_RE.search(text) or _LAB_RE.search(text) or _RGB_RE.search(text))

    audit = audit.copy()
    audit["leakage_flag"] = audit["feedback_text"].map(_leakage)
    leak = audit.groupby(variant_col)["leakage_flag"].mean()
    labels = [v for v in _LLM_ORDER if v in leak.index]
    if labels:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(
            range(len(labels)),
            [leak[v] for v in labels],
            color=_PALETTE[2],
            alpha=0.88,
        )
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels([v.replace("llm_teacher_", "") for v in labels], rotation=25, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Leakage rate (heuristic)")
        ax.set_title("Feedback leakage rate by variant")
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        _save(fig, fig_dir, "leakage_rate_by_variant")

        leak_summary = audit.groupby(variant_col).agg(
            n_messages=("feedback_text", "count"),
            leakage_rate=("leakage_flag", "mean"),
            precision=("teacher_constraint_correct", lambda s: s.dropna().mean()),
        )
        leak_summary.to_csv(fig_dir.parent / "teacher_feedback_audit_summary.csv")

    # Correctness vs game success
    if "teacher_constraint_correct" in audit.columns and not pe.empty:
        per_ex = (
            audit[audit["teacher_constraint_correct"].notna()]
            .groupby("example_id")["teacher_constraint_correct"]
            .mean()
            .rename("teacher_precision_ex")
        )
        merged = pe.set_index("example_id").join(per_ex, how="inner")
        if len(merged) > 10:
            fig, ax = plt.subplots(figsize=(6, 4.5))
            ax.scatter(
                merged["teacher_precision_ex"],
                merged["relative_improvement"],
                alpha=0.35,
                s=12,
                color=_PALETTE[0],
            )
            ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
            ax.set_xlabel("Per-example teacher precision")
            ax.set_ylabel("Relative improvement")
            ax.set_title("Teacher correctness vs game success")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            _save(fig, fig_dir, "llm_teacher_correctness_vs_game_success")


def plot_model_figures(pe: pd.DataFrame, traj: pd.DataFrame | None, fig_dir: Path) -> None:
    pe = pe.copy()
    pe["condition"] = pe["run_id"].map(condition_label_from_run_id)

    # Final error: model × condition
    pivot = pe.pivot_table(
        index="model_alias",
        columns="condition",
        values="final_error_lab",
        aggfunc="mean",
    )
    models = sorted(pivot.index)
    conds = ["oneshot", "axis_c3", "template_c1"]
    conds = [c for c in conds if c in pivot.columns]
    if models and conds:
        fig, ax = plt.subplots(figsize=(7, 4))
        x = np.arange(len(conds))
        w = 0.8 / len(models)
        for i, model in enumerate(models):
            vals = [pivot.loc[model, c] for c in conds]
            ax.bar(x + (i - len(models) / 2 + 0.5) * w, vals, w * 0.9, label=model, color=_PALETTE[i])
        ax.set_xticks(x)
        ax.set_xticklabels(conds)
        ax.set_ylabel("Mean final ΔE")
        ax.set_title("Final error by model and condition")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        _save(fig, fig_dir, "model_final_error_by_teacher")

        fig, ax = plt.subplots(figsize=(7, 4))
        pivot_rel = pe.pivot_table(
            index="model_alias",
            columns="condition",
            values="relative_improvement",
            aggfunc="mean",
        )
        for i, model in enumerate(models):
            vals = [pivot_rel.loc[model, c] for c in conds]
            ax.bar(x + (i - len(models) / 2 + 0.5) * w, vals, w * 0.9, label=model, color=_PALETTE[i])
        ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(conds)
        ax.set_ylabel("Mean relative improvement")
        ax.set_title("Relative improvement by model and condition")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        _save(fig, fig_dir, "model_relative_improvement_by_teacher")

    if traj is not None and not traj.empty:
        runs = []
        for (model, cond), sub in traj.groupby(["model_alias", "condition"]):
            if cond in ("axis_c3", "template_c1", "oneshot"):
                runs.append((f"{model}/{cond}", sub))
        if runs:
            plot_error_by_turn_multi(
                runs,
                fig_dir,
                stem="model_error_by_turn",
                title="Error by turn — model comparison",
            )

    # Regime gap: best minus worst regime final error per model
    if "regime_label" in pe.columns:
        gaps = []
        for model, g in pe.groupby("model_alias"):
            by_reg = g.groupby("regime_label")["final_error_lab"].mean()
            if len(by_reg) >= 2:
                gaps.append({"model": model, "regime_gap": by_reg.max() - by_reg.min()})
        if gaps:
            gdf = pd.DataFrame(gaps)
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.bar(gdf["model"], gdf["regime_gap"], color=_PALETTE[4], alpha=0.88)
            ax.set_ylabel("Max − min regime final ΔE")
            ax.set_title("Regime difficulty gap by model")
            ax.grid(True, axis="y", alpha=0.3)
            fig.tight_layout()
            _save(fig, fig_dir, "model_regime_gap")

    runs_pe: list[tuple[str, pd.DataFrame]] = []
    for m in sorted(pe["model_alias"].dropna().unique()):
        for c in ("axis_c3", "template_c1"):
            sub = pe[(pe["model_alias"] == m) & (pe["condition"] == c)]
            if len(sub) > 0:
                runs_pe.append((f"{m}/{c}", sub))
    if runs_pe:
        plot_relative_improvement_multi(
            runs_pe,
            fig_dir,
            stem="model_improvement_by_regime",
            title="Relative improvement by regime — models",
        )


def plot_final_figures(pe: pd.DataFrame, traj: pd.DataFrame | None, fig_dir: Path) -> None:
    """Scale-up comparison uses the same figure set as bandwidth."""
    plot_bandwidth_figures(pe, traj, fig_dir)
    summary = _summarize_by_condition(pe)
    order = [c for c in _FINAL_ORDER if c in summary.index]
    if traj is not None and order:
        runs = [(c, traj[traj["condition"] == c]) for c in order if c in traj["condition"].values]
        if runs:
            plot_error_by_turn_multi(
                runs,
                fig_dir,
                stem="error_by_turn_final",
                title="Error by turn — main_4000 scale-up",
            )


def plot_geometry_by_condition(
    geo_df: pd.DataFrame,
    fig_dir: Path,
    *,
    stem: str = "geometry_alignment_by_constraints",
) -> None:
    if geo_df.empty:
        return
    geo_df = geo_df.copy()
    geo_df["condition"] = geo_df["run_id"].map(condition_label_from_run_id)
    final = geo_df[geo_df["representation"] == "final_guess"]
    if final.empty:
        return

    order = sorted(final["condition"].unique(), key=lambda c: (_FINAL_ORDER + _BANDWIDTH_ORDER).index(c) if c in (_FINAL_ORDER + _BANDWIDTH_ORDER) else 99)
    fig, ax = plt.subplots(figsize=(max(7, len(order) * 0.6), 4))
    vals = [final[final["condition"] == c]["spearman_rho"].iloc[0] if len(final[final["condition"] == c]) else np.nan for c in order]
    ax.bar(range(len(order)), vals, color=_PALETTE[5], alpha=0.88)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=35, ha="right", fontsize=8)
    ax.set_ylim(-0.05, 1.0)
    ax.set_ylabel("Spearman ρ (final guess vs true LAB)")
    ax.set_title("Geometry alignment by condition")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, fig_dir, stem)


def compute_geometry_for_runs(
    run_dirs: list[Path],
    out_dir: Path,
    *,
    subsample: int = 500,
    seed: int = 13,
) -> pd.DataFrame:
    """Compute and save geometry_alignment_all.csv under out_dir."""
    summaries: list[pd.DataFrame] = []
    for run_dir in run_dirs:
        traj_path = run_dir / "games" / "trajectories.parquet"
        oneshot_path = run_dir / "games" / "oneshot_predictions.parquet"
        if traj_path.exists():
            traj_df = pd.read_parquet(traj_path)
        elif oneshot_path.exists():
            traj_df = pd.read_parquet(oneshot_path)
            if "turn" not in traj_df.columns:
                traj_df = traj_df.copy()
                traj_df["turn"] = 0
        else:
            continue
        results = compute_geometry_alignment(
            traj_df,
            max_turns=4,
            subsample=subsample if subsample > 0 else None,
            seed=seed,
        )
        summary = alignment_summary_df(results)
        summary["run_id"] = run_dir.name
        summaries.append(summary)

    if not summaries:
        return pd.DataFrame()

    combined = pd.concat(summaries, ignore_index=True)
    combined.to_csv(out_dir / "geometry_alignment_all.csv", index=False)
    return combined


def write_combined_report(
    kind: ComparisonKind,
    out_dir: Path,
    run_dirs: list[Path],
    pe: pd.DataFrame,
    teacher_ci: pd.DataFrame | None = None,
    geo_df: pd.DataFrame | None = None,
) -> Path:
    """Write combined_report.md for a comparison directory."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Combined Comparison Report: {kind.replace('_', ' ').title()}",
        f"_Generated: {now}_",
        "",
        "## Runs included",
        "",
        "| Condition | Run ID | N |",
        "|---|---|---:|",
    ]

    for rd in run_dirs:
        label = condition_label_from_run_id(rd.name)
        n = len(pe[pe["run_id"] == rd.name]) if "run_id" in pe.columns else "?"
        lines.append(f"| {label} | `{rd.name}` | {n} |")

    lines += ["", "---", "", "## Teacher / condition summary", ""]
    if teacher_ci is not None and not teacher_ci.empty:
        lines += [
            "| Teacher / condition | N | Final ΔE | Rel imp | C-sat | Dir align |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for _, row in teacher_ci.iterrows():
            tt = row.get("teacher_type", "")
            if pd.isna(tt) or tt == "":
                tt = "oneshot"
            lines.append(
                f"| {tt} | {int(row['n'])} | "
                f"{row['mean_final_error']:.2f} | {row['mean_relative_improvement']:+.3f} | "
                f"{row.get('mean_constraint_satisfaction', float('nan')):.3f} | "
                f"{row.get('mean_directional_alignment', float('nan')):.3f} |"
            )
    else:
        summary = _summarize_by_condition(pe)
        lines += [
            "| Condition | N | Final ΔE | Rel imp | C-sat | Dir align |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for cond, row in summary.iterrows():
            lines.append(
                f"| {cond} | {int(row['n'])} | {row['final_error_lab']:.2f} | "
                f"{row['relative_improvement']:+.3f} | "
                f"{row['mean_constraint_satisfaction']:.3f} | "
                f"{row['mean_directional_alignment']:.3f} |"
            )

    if geo_df is not None and not geo_df.empty:
        final = geo_df[geo_df["representation"] == "final_guess"].copy()
        final["condition"] = final["run_id"].map(condition_label_from_run_id)
        lines += ["", "## Geometry alignment (final guess)", ""]
        lines += ["| Condition | Spearman ρ | Kernel align |", "|---|---:|---:|"]
        for _, row in final.iterrows():
            lines.append(
                f"| {row['condition']} | {row['spearman_rho']:.3f} | {row['kernel_alignment']:.3f} |"
            )

    lines += [
        "",
        "## Output files",
        "",
        f"```text",
        f"{out_dir}/",
        "  aggregate_by_teacher_ci.csv",
        "  combined_per_example.parquet",
        "  combined_report.md",
        "  geometry_alignment_all.csv",
        "  figures/*.png",
        "```",
        "",
    ]

    path = out_dir / "combined_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def polish_comparison(
    kind: ComparisonKind,
    out_dir: Path,
    run_dirs: list[Path],
    *,
    subsample_geometry: int = 500,
    skip_geometry: bool = False,
) -> None:
    """Generate figures, geometry CSV, and combined_report.md for a comparison."""
    out_dir = Path(out_dir)
    pe, traj = _load_combined(out_dir)
    fig_dir = _figures_dir(out_dir)

    if kind == "bandwidth":
        plot_bandwidth_figures(pe, traj, fig_dir)
    elif kind == "llm":
        audit_path = out_dir / "teacher_feedback_audit.csv"
        plot_llm_figures(pe, traj, fig_dir, audit_path)
    elif kind == "model":
        plot_model_figures(pe, traj, fig_dir)
    elif kind == "final_main_4000":
        plot_final_figures(pe, traj, fig_dir)
    else:
        raise ValueError(f"Unknown comparison kind: {kind}")

    geo_path = out_dir / "geometry_alignment_all.csv"
    geo_df = pd.DataFrame()
    if not skip_geometry and run_dirs:
        geo_df = compute_geometry_for_runs(
            run_dirs, out_dir, subsample=subsample_geometry
        )
    elif geo_path.exists():
        geo_df = pd.read_csv(geo_path)

    if not geo_df.empty:
        plot_geometry_by_condition(geo_df, fig_dir)
        if kind == "model":
            plot_geometry_by_condition(
                geo_df, fig_dir, stem="model_geometry_alignment"
            )

    teacher_ci_path = out_dir / "aggregate_by_teacher_ci.csv"
    teacher_ci = (
        pd.read_csv(teacher_ci_path) if teacher_ci_path.exists() else None
    )
    write_combined_report(kind, out_dir, run_dirs, pe, teacher_ci, geo_df)
