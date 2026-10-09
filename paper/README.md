# ColorRef manuscript

The author supplied this Overleaf source export and compiled PDF on 2026-10-08
(Asia/Tokyo). The imported LaTeX files are unchanged. This establishes the
manuscript baseline before incorporating the completed revision experiments.

- [Compiled reading PDF](colorref-reading-draft-20261009.pdf) (includes the game diagram and a saved empirical trajectory)
- Revised working draft: `latex/color-games-revised.tex`
- Original unchanged source: `latex/color-games.tex`
- Bibliography: `latex/custom.bib`
- Supplied compiled baseline: `baseline/overleaf-20261008.pdf`
- File checksums and archive provenance: `baseline/import_manifest.json`
- Revision entry points: `../specs/manuscript_baseline_20261008.md`
- First-revision changes and remaining checks: `../specs/manuscript_revision_20261008.md`
- Current content audit and expert-feedback checklist: `../specs/manuscript_content_audit_20261009.md`
- Current experiment status: `../specs/revision_evidence_map.md`
- Completed narrative pass and full-read handoff: `../specs/discussion_closure_20261009.md`
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

The source is in ACL review mode. Routine build products should stay out of
version control. The supplied baseline PDF is retained as provenance, and
`colorref-reading-draft-20261009.pdf` is a deliberate exception for reading on
GitHub. It uses the temporary Courier substitution described above.

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

## Game-first narrative revision

The abstract and introduction now explain the guesser, teacher, hidden target,
verbal correction and repeated revision before introducing the calibration
results. The motivation connects interactive reference to measurable direction
and step size; the single-axis adjustment studies are explicitly distinguished
from full description-based games. All experimental numbers and results sections
remain unchanged.

Figures 1 and 2 now use the same actual example, "southern lime green"
(example 427046) from the fresh 1,000-description Qwen3-14B grounding run.
Figure 1 uses vector robot icons to explain the first exchange; its swatches
and canonical oracle message are saved values. Figure 2 follows all three
fixed revisions, with an a*b* path, L* strip, full LAB error and exact feedback.
The case was chosen for explanatory clarity, not to estimate average performance.
No graded wording was added to the direction-only oracle messages.

- [All 16 trajectory candidates (PDF)](trajectory-gallery-20261009.pdf)
- [Downloadable gallery ZIP](trajectory-gallery-20261009.zip): individual PDF/PNG
  figures, compact data, manifest, combined PDF and an HTML index.
- Compact source: `evidence/trajectory-gallery-20261009/compact_cases.jsonl`.
- Transport provenance and limits: `evidence/trajectory-gallery-20261009/manifest.json`.
- Selected figure data: `latex/figures/southern_lime_green.json`.

The compact export was supplied by the author. Its 64 displayed states, target
errors and 48 canonical oracle messages were recomputed and checked. Original
checkpoint hashes are retained as supplied; full raw prompts/responses and the
full-run completion manifest were not transported, so their original-file
integrity cannot be independently verified from this compact gallery.

Rebuild without inference, from the repository root:

```bash
uv run python scripts/rebuild_compact_trajectory_gallery.py
uv run python scripts/plot_reference_game.py \
  --compact-export paper/evidence/trajectory-gallery-20261009/compact_cases.jsonl \
  --example-id 427046
```

The first command writes `reports/figures/transported_trajectories/`. The original
full-checkpoint gallery command remains documented in
`../specs/game_figures_20261009.md`. Page-limit compression is deferred.

## Introduction developed paragraph by paragraph

The current opening starts from human color descriptions and their ambiguity,
then introduces one-shot model interpretation, interactive correction, the
reference-game roles, direction/magnitude, and the research questions. The
closing connects those questions to the controlled comparisons and the
receiver-calibrated policy, then explains the main findings in context.
One-shot prediction means prediction without revision; it is not a claim
about zero-shot prompting or the absence of demonstrations.

The compiled reading PDF includes this complete introduction pass and the
introductory schematic. The current temporary-font build has no unresolved references/citations or
overfull boxes; all pages were rendered and inspected.
The abstract, results, and later sections were not changed during this
paragraph-by-paragraph introduction pass.

## Framework and experimental progression

The next content pass makes the game protocol explicit: description, recorded
target, initial prediction, displayed guess, feedback and revision remain
distinct. Turn 0 is a prediction or supplied state; the grounding/shared-start
studies use three fixed revisions, while the sequential magnitude pilot uses
target-known stopping with a five-revision cap. Native LAB, displayed uint8 sRGB,
projection, direction and magnitude are defined before the results.

A new Framework subsection gives the receiver-calibrated procedure: per-direction
medians of parsed displayed signed steps, positive graded candidates, nearest-step
phrase selection from a hidden-target residual, deterministic ties and unavailable
mappings. Calibration remains separated from held-out colors and model weights
are unchanged. The Experimental Setup now explains the purpose of each control
and distinguishes description-based games from isolated adjustment policy tests.
Oracle thresholds and fixed ranking ranges were checked against the implementation.

This pass changes Framework and Experimental Setup only; the approved introduction,
experimental outputs, Results and Discussion remain unchanged. See
`../specs/framework_revision_20261009.md` for scope and checks. The reading PDF
includes the complete pass and both saved-game figures. Its temporary Courier
substitution remains a reading convenience; final publication-font layout awaits
Overleaf. Page-limit compression is deferred.

## Results narrative

The Results now connect each comparison to its motivating question and finding:
description-based correction, shared-start interface control, direction versus
magnitude, receiver-specific phrase selection, sequential transfer and teacher
reception. Both models' primary calibration comparisons precede the exploratory
policy-identity and overshoot breakdowns. The smaller sequential pilot has its
own subsection, separating its evidence from the two-model one-step confirmation.
Teacher preservation and usefulness remain separate outcomes.

All numerical values, tables and figure blocks are preserved. The approved
introduction and methods, Discussion and later sections are unchanged in this
pass. The reading PDF includes the revised narrative; validation and scope are
recorded in `../specs/results_narrative_revision_20261009.md`. Discussion and
conclusion alignment is the next content step, before the author's full read.

## Discussion, conclusion and full-read handoff

The planned narrative pass is complete. Discussion returns to the human
description/interpretation problem, then connects the reference game to
receiver-specific magnitude, output representation, teacher reception and
stopping. Conclusion returns to the motivating exchange and states the
scoped contribution before outlining extensions. All experimental results,
figures, methods, the approved introduction and Limitations are preserved.

The current reading PDF contains the complete pass. The next step is the
author's full read, focusing on the story, terminology, explanation of the game
and match between claims and evidence. Further content or experiments can be
decided after that read. Page-limit trimming and final publication-font layout
remain deferred; machine-side raw-output reconciliation remains documented
separately and is not claimed complete by this prose revision.
