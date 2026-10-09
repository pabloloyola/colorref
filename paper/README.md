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
- Current content audit and expert-feedback checklist: `../specs/manuscript_content_audit_20261009.md`
- Current experiment status: `../specs/revision_evidence_map.md`
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

## Calibration evidence figure

The working draft now centers receiver-calibrated graded feedback. Its two-panel
figure shows the primary within-model contrasts and exploratory distance effects.
Rebuild the figure with `uv run python scripts/plot_calibration_evidence.py`.
Reported rounded estimates and run IDs are recorded in
`latex/figures/calibration_effects.json`; they were not recomputed from raw
responses in this workspace. The PDF figure was rendered and visually inspected.
The 2026-10-09 reading copy includes these additions; its temporary-font layout
has been compiled and visually checked across all pages.

The 2026-10-09 content audit confirms the scoped two-model calibration claim,
distinguishes exploratory pilot results from confirmation, and records the
remaining scientific limits and submission checks. Completed experiments are
not pending reruns. Historical content-review notes are retained as chronology.
The 2026-10-09 reading PDF compiled and was visually inspected using a temporary
Courier substitution; final publication-font layout still requires Overleaf.

## Full-read handoff

The reference check, current run inventory and CPU evidence-export command are
recorded in `../specs/paper_reading_handoff_20261009.md`. The frozen run list is
`../specs/paper_evidence_inventory.json`. The revised bibliography now cites
the CIE 2018 colorimetry report and the Gemma 4 technical report; the Bayesian
color-semantics entry has verified publisher/DOI metadata.
The exporter packages saved evidence from the GPU machine without inference.
The full raw-checkpoint reconciliation awaits that export; pasted summaries
alone cannot verify every production setting or figure input.
