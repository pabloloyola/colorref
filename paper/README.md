# ColorRef manuscript

The author supplied this Overleaf source export and compiled PDF on 2026-10-08
(Asia/Tokyo). The imported LaTeX files are unchanged. This establishes the
manuscript baseline before incorporating the completed revision experiments.

- Revised working draft: `latex/color-games-revised.tex`
- Original unchanged source: `latex/color-games.tex`
- Bibliography: `latex/custom.bib`
- Supplied compiled baseline: `baseline/overleaf-20261008.pdf`
- File checksums and archive provenance: `baseline/import_manifest.json`
- Revision entry points: `../specs/manuscript_baseline_20261008.md`
- First-revision changes and remaining checks: `../specs/manuscript_revision_20261008.md`
- Content hierarchy and expert-feedback checklist: `../specs/manuscript_content_review_20261008.md`
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
  -outdir=build latex/color-games-revised.tex
```

The source keeps its original `latex/figures/` paths, so compile from `paper/`,
not from `paper/latex/`. Select `latex/color-games-revised.tex` as the main
document for the revision in Overleaf; `latex/color-games.tex` still compiles
the original baseline. Revision appendix files must be uploaded too.

The exact-font local compilation is blocked because `inconsolata.sty` is
absent from this workspace's TeX installation. The committed source retains
that package and the unchanged ACL style, fonts, margins, and font sizes.
A temporary, uncommitted Courier-font diagnostic compiled successfully with
no overfull boxes or unresolved references/citations, and its rendered pages
were inspected. This does not verify the publication-font layout. Compile the
working draft in Overleaf and inspect that PDF before treating it as final.

The working draft inputs `latex/revision-appendix.tex`; unrecoverable historical
numerical tables in `latex/revision-legacy-results.tex` are archived but excluded.
Upload the revised main document and revision appendix into
the corresponding `latex/` folder of the existing Overleaf project, retain
its original styles/bibliography/figures, and select the revised main document.
Appendix tables stay beside their explanations; bibliography wrapping is
ragged-right to avoid a small inherited overfull line without shrinking text.

Before a submission, inspect the complete build log for overfull boxes,
unresolved citations/references and missing assets, then visually review the
rendered PDF. A successful TeX exit alone does not validate formatting.

The source is in ACL review mode. Build products should stay out of version
control. The supplied baseline PDF is retained deliberately as provenance.

The 2026-10-08 intermediate review copy incorporates fresh 1,000-description
grounding evidence, the completed four-arm 128-color magnitude confirmation,
subgroup/identity audits, and corrected parse-failure denominators. The local
review PDF uses Courier instead of unavailable Inconsolata for monospace text;
committed source keeps Inconsolata. It is a content review, not a final
publication-font or submission-readiness check. The working source now also incorporates the completed Gemma 4 12B replication
and its saved-output breakdown/identity audits. The earlier review PDF predates
these additions. The Gemma numeric failure inspection is now incorporated: all 27 failures
concern decreasing the a coordinate; 25 finish at EOS and two reach the token
cap. Seventeen omit a coordinate and ten emit invalid negative lightness.
No failed response is repaired or excluded from completion counts.
