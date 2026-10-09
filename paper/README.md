# ColorRef manuscript

The current draft is in [`overleaf/`](overleaf/). This is the only active
manuscript source; it contains exactly the eight files needed for compilation.
The paper's wording, numbers, figures and ACL review style are unchanged by
the cleanup.

- [Overleaf import ZIP](colorref-overleaf.zip)
- [Compiled reading PDF](colorref-reading-draft-20261009.pdf)
- Main source: [`overleaf/main.tex`](overleaf/main.tex)
- Appendix: [`overleaf/appendix.tex`](overleaf/appendix.tex)
- References: [`overleaf/references.bib`](overleaf/references.bib)

## Import into Overleaf

1. Download `colorref-overleaf.zip` from GitHub using **Download raw file**.
2. In Overleaf, choose **New Project → Upload Project** and upload the ZIP.
3. Set the main document to **main.tex** and the compiler to **pdfLaTeX**.
4. Recompile. All figure, appendix and bibliography paths are project-local.

The ZIP opens directly at the project root: no enclosing `paper/` or `overleaf/`
folder. It contains `main.tex`, `appendix.tex`, `references.bib`, `acl.sty`,
`acl_natbib.bst` and the three PDF figures under `figures/`. It excludes the
compiled manuscript, old drafts, previews, galleries, data and build products.
The source retains Inconsolata and the original ACL template.

Official [Overleaf import instructions](https://docs.overleaf.com/managing-projects-and-files/uploading-a-project).

## Edit, compile and package

Edit the files under `paper/overleaf/`; there is no second working TeX copy.
With the required TeX Live font packages installed:

```bash
cd paper/overleaf
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=../build main.tex
```

Rebuild the import bundle from the repository root after any source/figure edit:

```bash
uv run python scripts/package_overleaf.py
```

The packager verifies all eight dependencies and their archived contents. It
does not update the separately retained reading PDF. That PDF is a deliberate
GitHub reading artifact; it uses a temporary Courier substitution because this
workspace lacks Inconsolata. Final font/page-limit review remains for Overleaf.
The cleanup changes file paths only, not manuscript content.

## Figure provenance and reproducibility

Supporting data and galleries live in [`../artifacts/paper/`](../artifacts/paper/)
and do not need to be uploaded to Overleaf. Plotting scripts write the paper's
PDF figures to `paper/overleaf/figures/` and PNG previews to local `reports/`.

```bash
uv run python scripts/plot_calibration_evidence.py
uv run python scripts/plot_reference_game.py \
  --compact-export artifacts/paper/evidence/trajectory-gallery-20261009/compact_cases.jsonl \
  --example-id 427046
uv run python scripts/rebuild_compact_trajectory_gallery.py
```

The last command rebuilds all 16 candidates under
`reports/figures/transported_trajectories/`. The selected trajectory is
`game_0538_hex.pdf`; copy it to `paper/overleaf/figures/southern_lime_green.pdf`
if intentionally regenerating that figure. The compact export verifies
displayed states and oracle messages; it does not contain full original
prompts/checkpoints. Figure provenance and the current evidence map retain
these limits.

## History and next step

Unused historical sources, figures and the imported baseline are removed from
the active tree. Their complete pre-cleanup state remains in Git commit
[`0ec264f`](https://github.com/pabloloyola/colorref/tree/0ec264f7703267fea6f06a63f18f607c791225db/paper).
Earlier chronological notes use the old `paper/latex/` paths; the cleanup map
is in [`../specs/paper_cleanup_20261009.md`](../specs/paper_cleanup_20261009.md).

The planned narrative pass is complete. Next is the author's full read before
deciding further content or experiments. Page-limit trimming is deferred.
Current scientific status: [`../specs/revision_evidence_map.md`](../specs/revision_evidence_map.md).
