"""Read validated current game checkpoints for CPU-only trajectory illustrations.

Supports run_interface_study.py, including the fresh grounding replication.
Shared-start and magnitude-study plans use other schemas and are rejected.
Figure selection is descriptive, never a performance estimate.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import yaml

from colorref.interface_study import (
    REGIMES,
    build_tasks,
    color_from_hex,
    is_complete,
    validate_checkpoint,
    validate_config,
)
from colorref.quantifier_study import plan_digest


def _read(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def load_compact_trajectories(path: Path) -> list[dict]:
    """Check transported HEX trajectories without claiming full checkpoint recovery.

    Original prompts/raw responses and full source files are absent. Supplied
    source hashes are identifiers, not independently verified here. Recompute
    displayed colors, target errors and canonical feedback before rendering.
    """
    import math

    from colorref.teachers import AxisOracle

    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not cases:
        raise ValueError("Empty compact export")
    seen = set()
    slots = set()

    def check_color(color):
        expected = color_from_hex(color["hex"])
        for field in ("rgb", "lab", "hsv"):
            values = color[field]
            if len(values) != 3 or any(
                not math.isfinite(x) or not math.isclose(x, y, abs_tol=1e-8, rel_tol=0)
                for x, y in zip(values, expected[field])
            ):
                raise ValueError("Compact color disagrees with HEX")

    for case in cases:
        task = case["task"]
        identity = (case["run_id"], task["condition_id"])
        slot = (case["run_id"], task["slot"])
        if identity in seen or slot in slots:
            raise ValueError("Duplicate compact condition or slot")
        seen.add(identity)
        slots.add(slot)
        if (task["variant"] != "hex" or task["output_space"] != "hex"
                or task["condition_id"] != f"hex:{task['example']['example_id']}"
                or case["teacher"]["type"] != "axis_oracle"):
            raise ValueError("Unsupported compact export condition")
        check_color(case["target"])
        if case["target"] != color_from_hex(task["example"]["hex"]):
            raise ValueError("Compact assigned target mismatch")
        records = case["records"]
        if len(records) < 2 or [r["turn"] for r in records] != list(range(len(records))):
            raise ValueError("Compact turns must be contiguous from zero")
        teacher = AxisOracle(**case["teacher"])
        for index, record in enumerate(records):
            check_color(record["displayed_state"])
            error = math.dist(case["target"]["lab"], record["displayed_state"]["lab"])
            if not math.isclose(error, record["projected_error_delta_e"], abs_tol=1e-8, rel_tol=0):
                raise ValueError("Compact error disagrees with displayed colors")
            if index == 0:
                if record["feedback"] is not None:
                    raise ValueError("Initial guess cannot contain revision feedback")
            else:
                expected = teacher.give_feedback(case["target"],
                    records[index - 1]["displayed_state"], task["example"], index - 1)
                if record["feedback"]["text"] != expected.text:
                    raise ValueError("Compact feedback disagrees with the axis oracle")
    return cases


def load_saved_trajectories(run_dir: Path) -> tuple[list[dict], dict]:
    """Validate frozen inputs and saved responses; return full parsed games only.

    All planned statuses remain in the manifest. Feedback for transition t -> t+1
    is stored on response t+1, unlike the old feedback.parquet convention.
    """
    plan, plan_hash = _read(run_dir / "inputs/plan.json")
    metadata, metadata_hash = _read(run_dir / "metadata.json")
    config_bytes = (run_dir / "config.yaml").read_bytes()
    cfg = yaml.safe_load(config_bytes)
    if metadata.get("schema_version") != 1 or (
        metadata.get("plan_sha256") != plan_digest([plan])
        or metadata.get("config_sha256") != plan_digest([cfg])
    ):
        raise ValueError("Frozen plan/configuration integrity validation failed")
    validate_config(cfg, plan["templates"])
    if build_tasks(cfg, plan["examples"]) != plan["tasks"]:
        raise ValueError("Frozen task list disagrees with the example/configuration plan")
    raw_root = run_dir / "raw_outputs/games"
    expected_paths = {raw_root / f"{t['slot']:04d}.json" for t in plan["tasks"]}
    if set(raw_root.glob("*.json")) - expected_paths:
        raise ValueError("Unknown game checkpoint in run")
    sources = {
        "inputs/plan.json": plan_hash,
        "metadata.json": metadata_hash,
        "config.yaml": hashlib.sha256(config_bytes).hexdigest(),
    }
    manifest = {
        "run_id": metadata["run_id"],
        "source_sha256": sources,
        "model": metadata["model"],
        "run_metadata": metadata,
        "frozen_config": cfg,
        "teacher": cfg["teacher"],
        "max_revisions": cfg["execution"]["max_turns"],
        "planned_games": len(plan["tasks"]),
        "statuses": [],
        "limits": [
            "Selected full parsed trajectories are illustrations, not a performance sample.",
            "Assigned-start and magnitude plans are not supported by this entry point.",
            "All points use saved displayed uint8 sRGB states; no model outputs are repaired.",
            "The a*b* view omits lightness; full three-dimensional error is shown separately.",
            "Background colors are a clipped sRGB rendering at target L*, not a gamut boundary.",
        ],
    }
    cases = []
    for task in plan["tasks"]:
        path = raw_root / f"{task['slot']:04d}.json"
        status = "missing"
        if path.exists():
            saved, checkpoint_hash = _read(path)
            if (saved["run_id"] != metadata["run_id"]
                    or saved["condition_id"] != task["condition_id"]):
                raise ValueError(f"Checkpoint belongs to another run/condition: {path}")
            records = saved["records"]
            validate_checkpoint(task, records, cfg, plan["templates"])
            if records and not records[-1]["parse_ok"]:
                status = "parse_failure"
            elif not is_complete(records, cfg["execution"]["max_turns"]):
                status = "pending"
            else:
                status = "full_parsed"
                cases.append({
                    "run_id": metadata["run_id"],
                    "task": task,
                    "target": color_from_hex(task["example"]["hex"]),
                    "records": records,
                    "model": metadata["model"],
                    "teacher": cfg["teacher"],
                    "source_sha256": {**sources, str(path.relative_to(run_dir)): checkpoint_hash},
                })
        manifest["statuses"].append({
            "condition_id": task["condition_id"], "variant": task["variant"],
            "regime": task["example"]["regime_label"], "status": status,
        })
    return cases, manifest


def select_illustrations(cases, *, variant="hex", n=16, seed=113, example_id=None):
    """Seeded round-robin regime selection, without ranking by improvement."""
    if n < 1:
        raise ValueError("n must be positive")
    candidates = [x for x in cases if x["task"]["variant"] == variant]
    if example_id is not None:
        chosen = [x for x in candidates if str(x["task"]["example"]["example_id"]) == str(example_id)]
        if len(chosen) != 1:
            raise ValueError("Requested example/variant has no unique full parsed trajectory")
        return chosen
    rng = random.Random(seed)
    pools = {}
    for regime in REGIMES:
        pool = sorted(
            [x for x in candidates if x["task"]["example"]["regime_label"] == regime],
            key=lambda x: str(x["task"]["example"]["example_id"]),
        )
        rng.shuffle(pool)
        pools[regime] = pool
    chosen = []
    while len(chosen) < n:
        added = False
        for regime in REGIMES:
            if pools[regime] and len(chosen) < n:
                chosen.append(pools[regime].pop())
                added = True
        if not added:
            break
    if not chosen:
        raise ValueError("No full parsed games available for this variant")
    return chosen


def draw_trajectory(case, output_stem: Path, *, pdf_pages=None):
    """a*b* path, actual swatches, L* strip, full error and exact feedback rows."""
    import textwrap

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import patheffects

    from colorref.colors import lab_to_rgb

    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    records = case["records"]
    target = case["target"]
    labs = np.array([x["displayed_state"]["lab"] for x in records])
    points = np.vstack([labs[:, 1:], np.array(target["lab"])[None, 1:]])
    lower, upper = points.min(axis=0), points.max(axis=0)
    span = max(upper - lower) + 24
    center = (upper + lower) / 2
    a_lim, b_lim = [(float(x - span / 2), float(x + span / 2)) for x in center]
    axis_a = np.linspace(*a_lim, 64)
    axis_b = np.linspace(*b_lim, 64)
    background = np.array([
        [lab_to_rgb(target["lab"][0], float(a), float(b)) for a in axis_a]
        for b in axis_b
    ]) / 255
    messages = [textwrap.fill(
        f"{r['turn'] - 1} → {r['turn']}: " + r["feedback"]["text"], width=86
    ) for r in records[1:]]
    message_lines = sum(x.count("\n") + 1 for x in messages)
    rail_height = max(1.45, 0.45 + 0.28 * message_lines)
    fig = plt.figure(figsize=(6.1, 4.45 + rail_height))
    grid = fig.add_gridspec(2, 2, width_ratios=[3.6, 1.3], height_ratios=[4, rail_height],
                            left=0.12, right=0.98, top=0.85, bottom=0.075,
                            wspace=0.32, hspace=0.23)
    ax = fig.add_subplot(grid[0, 0])
    ax.imshow(background, extent=[*a_lim, *b_lim], origin="lower", alpha=0.75)
    for left, right in zip(labs[:-1], labs[1:]):
        ax.annotate("", xy=right[1:], xytext=left[1:],
                    arrowprops={"arrowstyle": "->", "color": "#25323c", "lw": 1.5,
                                "shrinkA": 9, "shrinkB": 9})
    # Shared locations receive one combined turn label; coordinates never change.
    labels = {}
    for record, lab in zip(records, labs):
        ax.scatter(*lab[1:], s=135, c=record["displayed_state"]["hex"],
                   edgecolors="white", linewidths=1.5, zorder=4)
        labels.setdefault(tuple(lab[1:]), []).append(str(record["turn"]))
    for location, turns in labels.items():
        label = ax.annotate(",".join(turns), location, xytext=(6, 6), textcoords="offset points",
                            weight="bold", fontsize=9, zorder=6)
        label.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground="white")])
    ax.scatter(*target["lab"][1:], s=210, marker="*", c=target["hex"],
               edgecolors="#17232e", linewidths=1.1, zorder=5)
    target_label = ax.annotate("Target", target["lab"][1:], xytext=(-7, 12), ha="right",
                               textcoords="offset points", fontsize=8, zorder=6)
    target_label.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground="white")])
    ax.set(xlim=a_lim, ylim=b_lim, xlabel="a* (green to red)", ylabel="b* (blue to yellow)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.18, color="white")
    strip = fig.add_subplot(grid[0, 1])
    turns = [x["turn"] for x in records]
    strip.barh(turns, labs[:, 0], color=[x["displayed_state"]["hex"] for x in records],
               edgecolor="#53616d", linewidth=0.5)
    strip.axvline(target["lab"][0], color="#26343e", ls="--", lw=1.1)
    strip.set(xlim=(0, 100), yticks=turns, xlabel="L*", ylabel="Turn",
              ylim=(len(turns) - 0.3, -0.7), title="Lightness")
    feedback = fig.add_subplot(grid[1, :])
    feedback.axis("off")
    errors = "   |   ".join(f"{r['turn']}: {r['projected_error_delta_e']:.1f}" for r in records)
    feedback.text(0, 0.97, "Full LAB error (ΔE76), by turn: " + errors,
                  fontsize=8, weight="bold", va="top", transform=feedback.transAxes)
    y = 0.70
    for message in messages:
        feedback.text(0, y, message, fontsize=8, va="top", transform=feedback.transAxes)
        y -= (message.count("\n") + 1) * 0.28 / rail_height
    description = case["task"]["example"]["raw_name"]
    fig.suptitle(textwrap.fill(f'"{description}"', width=52), y=0.98,
                 weight="bold", fontsize=11)
    fig.text(0.5, 0.875,
             f"{case['model']['model_name']}  |  {case['task']['variant']}  |  axis oracle",
             ha="center", fontsize=8)
    fig.text(0.5, 0.025, "Displayed states. Background: target L* slice. Dashed line: target L*.",
             ha="center", fontsize=7.5)
    for suffix in (".png", ".pdf"):
        fig.savefig(output_stem.with_suffix(suffix), dpi=200)
    if pdf_pages is not None:
        pdf_pages.savefig(fig)
    plt.close(fig)
