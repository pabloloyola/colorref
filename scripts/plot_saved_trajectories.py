"""Generate a traceable trajectory gallery from current frozen game checkpoints.

CPU-only: no model loading, inference, response repair, or source-run writes.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colorref.saved_trajectory_figures import (  # noqa: E402
    draw_trajectory,
    load_saved_trajectories,
    select_illustrations,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/figures/current_trajectories"))
    parser.add_argument("--variant", choices=("hex", "lab_plain", "lab_axis_legend"), default="hex")
    parser.add_argument("--n", type=int, default=16)
    parser.add_argument("--seed", type=int, default=113)
    parser.add_argument("--example-id", help="Draw one explicitly selected full parsed example")
    parser.add_argument("--bundle", action="store_true", help="Write a small shareable gallery ZIP")
    args = parser.parse_args()
    cases, manifest = load_saved_trajectories(args.run)
    selected = select_illustrations(cases, variant=args.variant, n=args.n, seed=args.seed,
                                   example_id=args.example_id)
    # Keep all generated artifacts outside the frozen source run.
    if args.out.resolve().is_relative_to(args.run.resolve()):
        raise ValueError("Output directory must be outside the frozen source run")
    args.out.mkdir(parents=True, exist_ok=True)
    written = []
    cards = []
    manifest["selection"] = {
        "method": "explicit example" if args.example_id else "seeded round-robin regime sample",
        "seed": args.seed, "variant": args.variant,
        "selected_condition_ids": [x["task"]["condition_id"] for x in selected],
    }
    for case in selected:
        stem = args.out / f"game_{case['task']['slot']:04d}_{case['task']['variant']}"
        draw_trajectory(case, stem)
        stem.with_suffix(".json").write_text(json.dumps(case, indent=2, allow_nan=False) + "\n")
        written.extend(stem.with_suffix(suffix) for suffix in (".pdf", ".png", ".json"))
        example = case["task"]["example"]
        cards.append(
            f'<article><h2>{html.escape(example["raw_name"])}</h2>'
            f'<p>{html.escape(case["task"]["condition_id"])}; '
            f'{html.escape(example["regime_label"])}</p>'
            f'<a href="{stem.name}.pdf"><img src="{stem.name}.png" alt="Saved trajectory"></a>'
            f'<p><a href="{stem.name}.json">Checkpoint and source hashes</a></p></article>'
        )
    manifest["completion_counts"] = dict(Counter(x["status"] for x in manifest["statuses"]))
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    index = args.out / "index.html"
    index.write_text(
        '<!doctype html><meta charset="utf-8"><title>ColorRef trajectory candidates</title>'
        '<style>body{font-family:system-ui;margin:24px;background:#f6f7f9}'
        'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px}'
        'article{background:white;padding:16px}img{width:100%}h2{font-size:18px}</style>'
        f'<h1>Saved trajectory illustrations</h1><p>{html.escape(manifest["run_id"])}</p>'
        '<p>Seeded regime selection among full parsed games; no performance ranking. '
        'Use an example to explain behavior, not to estimate average performance.</p>'
        '<main>' + "".join(cards) + '</main>', encoding="utf-8",
    )
    written.extend((manifest_path, index))
    if args.bundle:
        archive = args.out / "trajectory_gallery.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in written:
                bundle.write(path, arcname=path.name)
        print(f"Share: {archive}")
    print(f"Wrote {len(selected)} figures; gallery: {index}")
    print("Source completion:", manifest["completion_counts"])


if __name__ == "__main__":
    main()
