"""Package saved manuscript evidence without inference or report regeneration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def build_bundle(project_root, inventory_path, destination, include_raw=False):
    root = Path(project_root).resolve()
    inventory_path = Path(inventory_path).resolve()
    destination = Path(destination).resolve()
    inventory = json.loads(inventory_path.read_text())
    if destination.exists():
        raise FileExistsError(f"Refusing to replace {destination}")
    entries = []
    statuses = []
    for study in inventory["studies"]:
        run_id = study["run_id"]
        if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("Run IDs must be single directory names")
        run = root / "runs" / run_id
        if destination.is_relative_to(run.resolve()):
            raise ValueError("Output must be outside the frozen run folders")
        if run.is_symlink():
            raise ValueError(f"Symlinked run is unsupported: {run_id}")
        paths = [run / "config.yaml", run / "metadata.json"]
        folders = ["inputs", "metrics", "reports"]
        if include_raw:
            folders.append("raw_outputs")
        for folder in folders:
            directory = run / folder
            if directory.is_symlink():
                raise ValueError(f"Symlinked evidence directory: {directory}")
            if directory.exists():
                paths.extend(directory.rglob("*"))
        files = []
        for path in sorted(set(paths)):
            if path.is_symlink():
                raise ValueError(f"Symlinked evidence file: {path}")
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".jsonl", ".yaml", ".yml", ".md", ".txt"}:
                continue
            if not path.resolve().is_relative_to(run.resolve()):
                raise ValueError(f"Evidence escapes run directory: {path}")
            files.append(path)
        required = ["config.yaml", "metadata.json", "inputs/plan.json", study["primary_report"]]
        relative = {p.relative_to(run).as_posix() for p in files}
        missing = [name for name in required if name not in relative]
        statuses.append({
            "run_id": run_id,
            "directory_present": run.is_dir(),
            "missing_required_files": missing,
            "selected_files": len(files),
            "raw_selected_files": sum("raw_outputs" in p.relative_to(run).parts for p in files),
        })
        for path in files:
            data = path.read_bytes()
            name = path.relative_to(root).as_posix()
            entries.append((name, data))
    supplemental = []
    for name in inventory.get("supplemental_files", []):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Supplemental file escapes project: {name}")
        present = path.is_file()
        supplemental.append({"path": name, "present": present})
        if present:
            entries.append((path.relative_to(root).as_posix(), path.read_bytes()))
    manifest = {
        "schema_version": 1,
        "include_raw": include_raw,
        "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "studies": statuses,
        "supplemental_files": supplemental,
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in entries],
        "limits": [
            "Hashes preserve bytes; they do not verify scientific outcomes or completeness of checkpoints.",
            "Missing evidence remains missing; no report or model output is regenerated.",
            "No models, dataset files, environment files or credentials are collected.",
            "Run only after generation and analysis writers have finished; concurrent mutation is unsupported.",
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
                archive.writestr("paper_evidence_inventory.json", inventory_path.read_bytes())
                for name, data in entries:
                    archive.writestr(name, data)
    except Exception:
        # Delete only an output created by this invocation, not an existing file.
        if destination.exists() and 'stream' in locals():
            destination.unlink()
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path, default=ROOT / "specs/paper_evidence_inventory.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-raw", action="store_true",
                        help="Include saved JSON/JSONL response checkpoints, not just plans/reports/metrics")
    args = parser.parse_args()
    manifest = build_bundle(args.project_root, args.inventory, args.output, args.include_raw)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "files": len(manifest["files"]),
        "include_raw": args.include_raw,
        "missing_required_files": {s["run_id"]: s["missing_required_files"]
                                   for s in manifest["studies"] if s["missing_required_files"]},
        "missing_supplemental_files": [s["path"] for s in manifest["supplemental_files"]
                                       if not s["present"]],
    }, indent=2))


if __name__ == "__main__":
    main()
