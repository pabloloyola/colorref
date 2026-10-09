"""Validate and zip the minimal current manuscript for Overleaf import.

Run from any directory. main.tex is at the archive root; generated manuscript
PDFs, previews, old drafts and local build products are excluded.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "paper/overleaf"
FILES = (
    "main.tex", "appendix.tex", "references.bib", "acl.sty", "acl_natbib.bst",
    "figures/reference_game.pdf", "figures/southern_lime_green.pdf",
    "figures/calibration_effects.pdf",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "paper/colorref-overleaf.zip")
    args = parser.parse_args()
    missing = [name for name in FILES if not (PROJECT / name).is_file()]
    if missing:
        parser.error(f"Missing project dependencies: {missing}")
    source = (PROJECT / "main.tex").read_text()
    required = [r"\input{appendix}", r"\bibliography{references}", r"\usepackage{inconsolata}"]
    required.extend("{" + name + "}" for name in FILES if name.endswith(".pdf"))
    if "latex/" in source or any(token not in source for token in required):
        parser.error("The manuscript's expected project-local dependencies changed")
    output = args.output.resolve()
    if output.is_relative_to(PROJECT.resolve()):
        parser.error("Write the archive outside the Overleaf source directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(FILES):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (PROJECT / name).read_bytes())
    with zipfile.ZipFile(output) as bundle:
        if bundle.testzip() or set(bundle.namelist()) != set(FILES):
            raise ValueError("Archive validation failed")
        for name in FILES:
            if bundle.read(name) != (PROJECT / name).read_bytes():
                raise ValueError(f"Archived contents differ: {name}")
    print(json.dumps({"archive": str(output), "files": len(FILES),
                      "bytes": output.stat().st_size,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
