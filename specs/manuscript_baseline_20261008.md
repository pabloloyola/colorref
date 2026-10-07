# Overleaf manuscript baseline and revision entry points

The author supplied `color_games_emnlp_latest_source.zip` and
`color_games_emnlp_latest.pdf` on 2026-10-08 (Asia/Tokyo). The LaTeX directory
is imported byte-for-byte under `paper/latex/`. The supplied PDF is retained
under `paper/baseline/overleaf-20261008.pdf`; the manifest records SHA-256
checksums of the original source archive, PDF and imported source files.
This import does not alter the manuscript or assert that new study results
already appear in it. The expert's separate review text is not part of the
public manuscript import.

## Baseline checks

- The supplied PDF has 14 A4 pages; its conclusion ends on page 8 and
  Limitations starts on page 9. Page 8 was visually inspected.
- The active main file is `latex/color-games.tex`, with ACL review mode,
  `custom.bib`, and one active included figure, `latex/figures/example.png`.
  All these assets are present; additional archived figures are preserved.
- A static check after removing commented TeX finds no missing citation
  keys or unresolved label names. This does not replace a full TeX build.
- Local latexmk/pdflatex stops at missing `inconsolata.sty`. Source-to-PDF
  reproducibility and whole-document formatting remain unverified locally.
- The Phase 2 condition list already uses breakable prose. Do not restore
  the old unbreakable inline mathematical set.
- The source still presents the original zero-shot teacher conclusions and
  contains no results from the new matched interface, magnitude or teacher
  studies. It also retains the historical `debug_4000` teacher table, whose
  exact table-producing run provenance has not been recovered.

Line references below refer to this unmodified imported source and will move
after editing. Evidence files record author-supplied GPU summaries, rather
than claiming access to raw production runs on the GPU machine.

## Revision map

| Location | Current issue | Concrete revision |
|---|---|---|
| Abstract (73-88), Introduction teacher preview (268-284) | Broad following-versus-generating capability conclusion | Introduce the decomposition into initial prediction, output interface, direction, magnitude and feedback production/usefulness. State prompt-conditioned teacher findings and the new calibration result with its scope. |
| Framework metrics (598-641), dataset/regimes (500-581) | Recorded crowd target can be read as the uniquely correct semantic color | Keep the Delta E76 definition; describe disagreement from the assigned target and distinguish description validity from target agreement. No new human ambiguity result exists. |
| Experimental Setup (790-911) | Only legacy phases; model roles and protocols need separation | Add matched HEX/plain LAB/LAB-legend shared-start control; isolate fresh-context quantifier probes; describe held-out calibration and sequential transfer; specify teacher and receiver identities/budgets for the new studies. Distinguish legacy early stopping from new fixed rounds and target-known stopping. |
| Teacher results (1290-1337), Discussion (1593-1612), Conclusion (1618-1627) | DP=0.11 is treated as proof of wrong geometric language and a general generation bottleneck | Retain historical numbers only with traceable provenance and scoring caveats. Report the zero/four-shot natural/restricted restatement control separately from receiving performance. Lexical direction words in guess-versus-target comparisons require scope-aware interpretation. |
| Additional results/Discussion | No magnitude control evidence | Present independent quantifier probes, one-step held-out control and sequential transfer as controlled coordinate localization. Report projection drift, coarse phrase resolution, numeric execution tails and calibration cost. Creative editing remains motivation. |
| Appendix A.5 (1880-1926) | Template examples contain magnitude modifiers absent from the actual phrase bank | Replace with the code-generated examples already recorded in `revision_evidence_map.md`. Keep graded magnitude wording confined to the new quantifier studies. |
| Limitations (1629-1649), AI disclosure (2179-2188) | New evidence and AI-assisted research work are absent | State single-model/prompt and finite-start sampling limits, oracle-known targets/stopping, projection constraints, unresolved target ambiguity and unaided teacher geometry. Accurately disclose coding, drafting and supplementary assistant review, with author verification; do not call assistant labels independent human review. |

## Evidence to prioritize in the revised story

1. Preserve the original empirical benefit of controlled interactive feedback,
   while qualifying it as localization of a recorded target.
2. Use the completed shared-start interface study to show that encoding and
   explicit axis instructions affect feedback following even with identical
   starts. Similar HEX and legend endpoints do not establish equivalence.
3. Make magnitude control the main extension: calibrated wording reduces
   error and evaluation calls on fresh sequential targets. The 34.5% call
   reduction excludes calibration cost, and eight calibrated cap endings
   expose projected off-axis drift under a fixed-axis controller.
4. Use matched teacher restatement and receiving studies to replace the
   universal capability-gap claim. Four-shot restatement can preserve
   supplied directions without giving the best receiver target accuracy.
   Restricted zero-shot's mean advantage is concentrated in changed messages;
   its median paired difference from the oracle is zero. Surface and addition
   contributions are descriptive, not randomized causal effects.

Relevant completed evidence:

- `results/shared_start_20261007.md`
- `results/magnitude_transfer_20261007.md`
- `results/magnitude_transfer_inspection_20261007.md`
- `results/teacher_fidelity_20261007.md`
- `results/teacher_manual_review_20261008.md`
- `results/teacher_receiver_20261008.md`

The next writing pass should replace outdated claims throughout the manuscript,
then redistribute diagnostics between the main text and appendix. Establish
the main results table and figure plan before adding prose; keep study cohorts,
interfaces, fixed-round versus stopping protocols and uncertainty denominators
distinct. No additional GPU experiment is needed to establish this baseline.
