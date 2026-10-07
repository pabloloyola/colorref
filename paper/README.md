# ColorRef manuscript

The author supplied this Overleaf source export and compiled PDF on 2026-10-08
(Asia/Tokyo). The imported LaTeX files are unchanged. This establishes the
manuscript baseline before incorporating the completed revision experiments.

- Main source: `latex/color-games.tex`
- Bibliography: `latex/custom.bib`
- Supplied compiled baseline: `baseline/overleaf-20261008.pdf`
- File checksums and archive provenance: `baseline/import_manifest.json`
- Revision entry points: `../specs/manuscript_baseline_20261008.md`
- Experimental evidence: `../specs/results/`

## Compile locally

Run from this directory with TeX Live, latexmk, BibTeX and the font packages
required by the bundled ACL template:

```bash
paper_root="$(pwd)"
TEXINPUTS="$paper_root/latex//:" \
BIBINPUTS="$paper_root/latex//:" \
BSTINPUTS="$paper_root/latex//:" \
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -outdir=build latex/color-games.tex
```

The source keeps its original `latex/figures/` paths, so compile from `paper/`,
not from `paper/latex/`. Select `latex/color-games.tex` as the main document if
importing the project back into Overleaf.

The initial local compilation attempt stopped because `inconsolata.sty` is
absent from this workspace's TeX installation. Do not remove the template's
font package to conceal that dependency. Compilation/layout equivalence to
the supplied PDF has not yet been verified locally.

Before a submission, inspect the complete build log for overfull boxes,
unresolved citations/references and missing assets, then visually review the
rendered PDF. A successful TeX exit alone does not validate formatting.

The source is in ACL review mode. Build products should stay out of version
control. The supplied baseline PDF is retained deliberately as provenance.
