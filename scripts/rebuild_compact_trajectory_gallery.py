"""Rebuild the transported trajectory gallery without source-run or model access.

Compact exports retain displayed states, metrics and feedback, not full prompts
or original checkpoints. Original source hashes are retained as supplied.
"""

import argparse
import hashlib
import html
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from colorref.saved_trajectory_figures import draw_trajectory, load_compact_trajectories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "paper/evidence/trajectory-gallery-20261009/compact_cases.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "paper/evidence/trajectory-gallery-20261009/manifest.json")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/figures/transported_trajectories")
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(args.input.parent.resolve()):
        parser.error("Keep generated outputs outside the source evidence directory")
    cases = load_compact_trajectories(args.input)
    manifest = json.loads(args.manifest.read_text())
    if (manifest["condition_ids"] != [c["task"]["condition_id"] for c in cases]
            or any(c["run_id"] != manifest["run_id"] for c in cases)):
        raise ValueError("Transport manifest and compact export disagree")
    manifest["compact_export_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    manifest["received_cases"] = len(cases)
    manifest["received_states"] = sum(len(c["records"]) for c in cases)
    manifest["regime_counts"] = dict(Counter(c["task"]["example"]["regime_label"] for c in cases))
    args.out.mkdir(parents=True, exist_ok=True)
    from matplotlib.backends.backend_pdf import PdfPages
    cards = []
    with PdfPages(args.out / "trajectory_gallery.pdf") as pages:
        for case in cases:
            stem = args.out / f"game_{case['task']['slot']:04d}_hex"
            draw_trajectory(case, stem, pdf_pages=pages)
            stem.with_suffix(".json").write_text(json.dumps(case, indent=2, allow_nan=False) + "\n")
            cards.append(
                f'<article><h2>{html.escape(case["task"]["example"]["raw_name"])}</h2>'
                f'<a href="{stem.name}.pdf"><img src="{stem.name}.png" alt="Displayed trajectory"></a>'
                f'<p><a href="{stem.name}.json">Compact exported data</a></p></article>'
            )
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>ColorRef trajectory gallery</title>'
        '<style>body{font-family:system-ui;margin:24px}main{display:grid;'
        'grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:24px}img{width:100%}</style>'
        '<h1>Saved game illustrations</h1><p>' + html.escape(manifest["run_id"]) + '</p>'
        '<p>Rebuilt from a compact export. Full prompts and original checkpoint files are absent. '
        'These illustrations do not estimate average performance. See manifest.json for provenance.</p>'
        '<main>' + ''.join(cards) + '</main>', encoding="utf-8"
    )
    paths = [args.out / name for name in ("index.html", "manifest.json", "trajectory_gallery.pdf")]
    paths.extend(sorted(args.out.glob("game_*.*")))
    with zipfile.ZipFile(args.out / "trajectory_gallery.zip", "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            bundle.write(path, arcname=path.name)
    print(f"Verified and rebuilt {len(cases)} trajectories: {args.out}")


if __name__ == "__main__":
    main()
