# ColorRef continuation handoff — 2026-10-07

## Repository and current work

- Repository: `pabloloyola/colorref`.
- Active branch: `refactor/quantifier-calibration`; open PR #3.
- A100 bootstrap and direct LAB support are already on `main`.
- Current experiments run Qwen/Qwen3-14B through HF transformers on a single A100 40 GB, bfloat16, thinking disabled, temperature 0.
- Data artifacts are hosted separately in the private HF dataset `paablo111/colorref-data`; GPU-local datasets and outputs are not in Git.
- The historical `HANDOFF.md` predates this refactoring. Use the recent experiment specs and this status for current work.

The numbers below are from user-provided production summaries and raw-response excerpts. The coding workspace has not independently read the full production run folders, which remain on the GPU machine. Keep simulated CPU test results separate from model performance.

## Completed quantifier study

Run: `runs/20261006_130637_580285_quantifier_study_a100_40gb`.

The study has 12 fixed LAB anchors, six directions, four wordings, exact 5/10-unit controls, and a no-change control, under plain and axis-legend prompts. Completed 888/888 responses, all parsed, 444/444 matched pairs.

The axis legend increases correct qualitative directions from 228/288 to 288/288 and strictly increasing quantifier pairs from 172/216 to 210/216. Plain numeric controls are exact in all trials; legend numeric-5 controls are exact in all trials and legend numeric-10 controls in 71/72. No-change controls are exact throughout.

The one numeric miss is identified from its raw response: starting `LAB(65, 8, -18)`, the instruction requests an increase of b by exactly 10; expected `LAB(65, 8, -8)`, actual `LAB(65, 8, 2)`. The output changes b by 20 while preserving L/a. Native control error is 10 ΔE. Do not discard or describe this miss as a parsing error.

Large qualitative steps often project poorly into sRGB: `much` has projection ΔE>1 in 38/72 plain trials and 42/72 legend trials. Direction and magnitude ordering alone do not imply usable displayable-color editing.

## Completed matched reference games

Run: `runs/20261006_143711_709402_interface_study_a100_40gb`.

64 examples, 16 per regime, HEX/plain LAB/LAB with axis legend, three fixed oracle rounds. Same displayed uint8 sRGB state policy and oracle thresholds across conditions; adaptive messages differ when guesses differ. Native LAB outputs remain in diagnostics. See `specs/interface_study.md` for the exact protocol.

Completed 192/192 games, 763/768 maximum generations, three parse failures exclusively in the legend condition. All 64 triplets completed; 61 have full parsed trajectories under all interfaces. Common-cohort results:

| Interface | N | Initial projected ΔE | Final projected ΔE | Gain | Final–best gap | Directional alignment |
|---|---:|---:|---:|---:|---:|---:|
| HEX | 61 | 40.468 | 22.938 | 17.530 | 7.956 | 0.724 |
| Plain LAB | 61 | 59.031 | 46.717 | 12.315 | 3.061 | 0.353 |
| LAB with legend | 61 | 52.133 | 29.386 | 22.747 | 0.204 | 0.782 |

The three failed responses contain unevaluated arithmetic in a LAB expression followed by an incomplete numeric triplet:

- `lab_axis_legend:115362`, “dashed dreams,” turn 1.
- `lab_axis_legend:286712`, “modern times blue,” turn 2.
- `lab_axis_legend:480326`, “tulip sorrow,” turn 1.

Early termination removes two later responses for each turn-1 failure and one for the turn-2 failure, accounting for five missing generation slots. The pattern is consistent with truncation at the configured 64-token budget; finish reasons/token counts were not recorded, so this mechanism is unconfirmed. Retain the failures and original parser behavior.

## Completed shared-start control

Run: `runs/20261007_043619_593902_shared_start_interface_study_a100_40gb`.

The user completed 192/192 games, 576/576 generated revisions, with no parse failures. Both first-revision and full-trajectory cohorts contain all 64 examples. All interfaces start at mean projected error 41.955, and first oracle corrections are identical.

| Interface | First revised ΔE | First gain | Final ΔE | Best ΔE | Final–best gap | Converged N |
|---|---:|---:|---:|---:|---:|---:|
| HEX | 32.099 | 9.856 | 22.781 | 15.155 | 7.626 | 4 |
| Plain LAB | 38.286 | 3.669 | 35.275 | 26.385 | 8.890 | 1 |
| LAB with legend | 32.582 | 9.373 | 23.161 | 21.028 | 2.133 | 7 |

Plain LAB minus HEX first-revision error is +6.187 [0.845, 11.889]; legend minus plain LAB is -5.705 [-11.444, 1.406]; legend minus HEX is +0.483 [-4.773, 6.562]. At the final revision, the corresponding differences are +12.494 [6.570, 18.435], -12.114 [-18.035, -5.489], and +0.380 [-4.848, 6.294]. These are the reported paired regime-stratified 95% percentile intervals, not population significance tests. The legend's first-revision improvement over plain LAB is uncertain; its final improvement is better supported. Close mean endpoints do not establish HEX/legend equivalence.

One supplied start was initially converged and all three conditions lost convergence. Its first movements were 31.959, 51.304, and 37.402 ΔE for HEX/plain LAB/legend, respectively. All first oracle messages had at least one constraint; this case cannot be attributed to an empty correction from the summary. The user has now supplied the inspector excerpt: example 140096, `dull toy red`, begins at ΔE 2.380. Valid feedback requests lightness +2.134 and HSV saturation -0.055, but first movements are 13.4–21.6 times the remaining LAB distance. All three satisfy both requested signs and have positive alignment while sharply increasing error. Outputs parse, terminate at EOS below 64 tokens, and have small projection costs. See `specs/results/close_state_140096.md` for the geometric verification and exact trajectories; the internal cause remains unspecified. Zero-movement revisions are 0/192, 20/192, and 9/192; smaller final–best gaps are not a standalone measure of superior control.

See `specs/results/shared_start_20261007.md` for evidence, interpretation, and the CPU inspection command. The coding workspace has received the production summary, not the raw production folder.

## Current interpretation and next work

In the original name-to-color interface study, HEX has the best final endpoint and the legend substantially improves LAB accuracy and directional alignment. Its different initial predictions prevent interpreting those gains as a causal comparison of feedback alone. The shared-start control now holds starting states fixed; plain LAB retains higher error, while the legend substantially closes the final-error gap under this protocol. A smaller final–best gap may reflect either stable correction or stagnation; inspect saved trajectories before making a control-quality claim. The balanced sample is diagnostic, not a full-scale paper replication.

The next CPU analysis is implemented in `scripts/analyze_interface_study.py`: errors by turn on a fixed common cohort, paired stratified bootstrap intervals, available-pair sensitivity to failures, stationary movement, initially close guesses later lost, and individual final–best gaps. It must run against the actual saved production folder to produce new scientific findings; code tests use simulated responses.

`specs/revision_evidence_map.md` connects expert concerns to supported claims and copy-ready manuscript edits. The source audit found that the appendix's “a little”/“a bit” template examples are absent from the current oracle; corrected examples are generated by the implementation. The current extended-vocabulary oracle also selects only primitive direction keys, so its broad-vocabulary dictionary additions are unused on correction turns. Teacher identity and clause budgets are explicit in available configs, but their dataset paths do not establish provenance for the PDF's `debug_4000` teacher table.

`scripts/run_shared_start_study.py` now implements the next feedback-following control: reuse the 64 parent HEX initial displayed states across all three interfaces, with identical first feedback, up to 576 new revisions. The user completed this A100 run with all 576 revisions parsed; the results are recorded above. First-revision and full-trajectory cohorts are reported separately when later parsing fails, with common-triplet and available-pair bootstrap comparisons. New checkpoints save observed token/EOS/budget diagnostics; old saved outputs remain unchanged. Exact dry-run, smoke, resume, and report commands are in `specs/shared_start_interface_study.md`.

Machel's remaining concerns include crowdsourced-target ambiguity, few-shot teacher capabilities, and oracle-assisted paraphrase/vocabulary confounds. The output-interface study addresses the representation concern but does not resolve those other issues. Magnitude-calibrated feedback has now been evaluated on held-out coordinate targets and sequential transfer below; mixed name-to-color games remain separate work.

## Completed CPU stopping replay and held-out magnitude pilot

The user ran `scripts/replay_shared_start_stopping.py` on the complete shared-start folder. The frozen ΔE ≤ 5 rule preserves the same 64-example common cohort and uses no new inference. Fixed/stopped final errors are 22.781/22.005 for HEX, 35.275/34.562 for plain LAB, and 23.161/22.822 for legend LAB. Retained convergence counts change from 4/1/7 to 8/4/9; 23 of 576 revisions are saved. Nine previously reached convergence outcomes were lost under fixed rounds, across seven distinct examples. Stopping leaves the interface comparison largely intact. See `specs/results/stopping_replay_20261007.md` for paired intervals, repeated-example denominators, and the concentration of legend mean improvement in the single initially close example.

`scripts/run_magnitude_control.py` now implements the one-step held-out pilot specified in `specs/magnitude_control_pilot.md`. It freezes 12 calibration and 12 separate evaluation RGB colors before querying the model. The fixed candidate channel range is [48, 208], seed 29; old 12 quantifier anchors and the close-case start are excluded from both splits. Targets at single-axis 6/12/24 units undergo feasibility checks before model inference. The production config yields 288 calibration conditions, 196 included targets, and 20 feasibility exclusions, for up to 588 held-out calls. Missing bins are retained in reports, not replaced.

The controller fits positive displayed-state median steps from complete calibration outputs (including wrong-direction/zero values among parsed responses, with parse failures counted). Bare wording remains unranked. Held-out bare/calibrated/numeric arms share the start and target, frozen receiving prompt, and one fresh-context revision. Numeric instructions add exact coordinate precision and holds, so they are not information-matched wording controls. No held-out responses fit the controller. Atomic per-response checkpoints, model-revision consistency when observed, a frozen fitted controller, run locking, generation/input-token diagnostics, and CPU reanalysis support interrupted runs. Paired uncertainty resamples starting-color clusters rather than treating directions/distances as independent colors. HSV saturation and mixed corrections remain later work; the completed single-axis sequential transfer is recorded below.

The user completed GPU run `20261007_054337_204395_magnitude_control_a100_40gb_pilot`: 288 calibration responses (287 parsed), all 588 evaluation responses parsed, and 196 common matched triplets on 12 held-out starting colors. Bare/calibrated/numeric mean displayed errors are 11.770/6.362/0.533; all arms have requested-direction follow rate 1.000. Calibrated minus bare is −5.408 [−10.220, −2.173], about 46% lower mean error, with starting-color cluster resampling. Projection means are 5.411/0.967/0.177; projection >1 counts are 29/10/0. Numeric native execution error averages 0.480, despite the saved smoke's 39-unit arithmetic miss. The completed CPU audit now shows 188/196 native controls within 0.01, 192 within 1, and four errors above 1; the exact-error median/p95 round to zero while the max is 39. See `specs/results/magnitude_control_20261007.md` for the evidence, full limits and manuscript wording candidate.

The report supports a calibrated magnitude policy over bare directional wording in this one-step diagnostic. It does not show that calibration is necessary relative to an uncalibrated graded-wording policy, equate precision budgets, establish internal perceptual understanding, or demonstrate creative-editor transfer. Quantifier choice encodes magnitude information; exact numerals add precision and explicit holds. All evaluation outputs parse, so there is no parse-selection difference between arms in the completed primary comparison. Twelve evaluation colors, not 196 independent colors, are the analysis clusters.

`scripts/analyze_magnitude_control.py` adds CPU-only exploratory direction/distance breakdowns, per-color effects, wins/ties/losses, geometric overshoot diagnostics, phrase median-target gaps, actual step-transfer mismatch, and numeric error distributions/miss exports. It validates the frozen run and writes separate breakdown files; it does not alter primary results, refit calibration or query a model. The user has now supplied the completed CPU breakdown; the coding workspace has read the report but not the full raw run folder. CPU tests are simulations, not new scientific findings. The previous stopping-test CI package-import issue was fixed; the implementation commit 8dbfa5f passed all 276 repository tests. New audit checks cover preservation, primary aggregate equivalence, paired cohorts and clustered denominators.

## Magnitude audit interpretation and next study

The completed production audit has 93 calibrated wins, 57 ties and 46 losses, median paired difference zero. Mean convergence improves from 94 to 125 of 196 cases; harmful updates fall from 48 to 3. The gain is concentrated at 6 units (−9.836 paired error) and 12 units (−5.774); at 24 it is +0.846 [−3.137, 3.878]. Red is worse overall (+0.938 [0.374, 1.524]) despite improving on six-unit targets. Its coarse fitted ladder lacks an intermediate phrase near 12/24; green large corrections additionally show high held-out step-transfer mismatch. Do not call the controller universally better or retune it on these held-out cases.

Eleven of twelve starts have favorable mean differences. Omitting any one start leaves a favorable descriptive mean (−6.061 to −3.330), though one high-leverage color contributes strongly. Numeric controls have a mostly exact bulk and a rare large-error tail: eight exceed 0.01, four exceed 1, all four large misses preserve other coordinates, terminate at EOS below the cap and have projection error below 0.5. Expected/actual coordinates support an execution-failure label; an internal digit-loss mechanism is unconfirmed. Native bare/calibrated steps (23.539/11.673) already differ before projection, so display geometry cannot explain all observed policy differences.

`specs/magnitude_transfer_followup.md` records the implemented sequential question: do repeated calibrated corrections plus target-known stopping recover larger residuals on fresh held-out starts? The protocol is now implemented in `scripts/run_magnitude_transfer.py` and CPU-tested; the GPU study is now complete; see the sequential-transfer result below. Reuse the fitted policy without tuning on this evaluated set, use the same receiving prompt and single-axis correction, compare bare/calibrated/numeric arms under the same five-revision cap and ≤5 stopping rule, and report error together with call budgets. A new generation plan must exclude all previously used calibration/evaluation/anchor/close-case starts. Label this as sequential transfer, not a semantic-precision-matched comparison. Saturation and multi-axis reference-game transfer come later.

Machel's zero-/few-shot teacher and literal-restricted versus natural-paraphrase controls remain essential to revising the original teacher-side capability claim. The quantifier improvements do not resolve that criticism. Keep those experiments on the revision roadmap instead of using magnitude results as a substitute for teacher evidence. Code CI on 9912eea passed all 283 repository tests. The new sequential runner adds sixteen CPU tests; full repository CI on ea21e03 passed all 299 tests.

## Completed sequential magnitude transfer

Run: `20261007_072214_768541_magnitude_transfer_a100_40gb`, using the original magnitude pilot's frozen calibration map and twelve fresh RGB starts. The user supplied the completed summary: all 600 games have valid endpoints, all 1,059 generated revisions parse, and all 200 targets enter the common triplets. Sixteen pre-inference feasibility exclusions remain explicit. No new calibration calls or held-out controller fitting occurred.

Bare/calibrated/numeric mean terminal errors are 6.461/2.979/0.095, convergence is 148/192/200 of 200, and calls are 516/338/205 (means 2.580/1.690/1.025). Calibrated minus bare error is −3.483 [−4.198, −2.739], mean calls −0.890 [−1.131, −0.654], and convergence +0.220 [0.158, 0.277]. Calibrated wording yields about 53.9% lower mean error and 34.5% fewer calls, with the same target-known stopping rule and five-revision cap. All twelve per-start mean differences favor calibrated wording; available-pair and common-triplet effects coincide. This is a frozen-policy result on twelve sampling clusters, not an equal-information comparison or creative-editor validation.

Within this same fresh cohort, calibrated error changes from 6.434 at budget one to 3.339 at three and 2.979 at five; successes are 119/187/192. Revisions four/five add five successes at 22 additional calls. The exploratory 24-unit aggregate now favors calibrated wording (−1.940 [−3.534, −0.510], 58 cases), but lighter/24 is worse in mean (+5.552 [−0.266, 12.179], seven cases); red/24 remains close and uncertain. Eight calibrated games exhaust the five-revision cap. Harmful updates are 152/516 for bare versus 11/338 for calibrated. Native requested steps differ before projection, so geometry alone is not an established explanation.

All numeric games converge, with five using a second call, but execution still has five errors >1 (max 44), plus one other error >0.01. Subsequent corrections come from the target-known oracle; successful endpoints do not prove autonomous self-correction or erase the intermediate misses. Inspect saved trajectories before explaining the mechanism.

See `specs/results/magnitude_transfer_20261007.md` for evidence, budget/subgroup qualifications, manuscript wording and a read-only CPU command that validates checkpoints and exports the eight calibrated nonconverged endings plus numeric tails. `specs/magnitude_transfer_followup.md` remains the implemented protocol/command reference. Do not rerun completed GPU inference. The targeted CPU inspection is now complete; its evidence is recorded below. The next experiment priority is Machel's zero-/few-shot and restricted-restatement teacher controls. The original teacher capability claim remains unresolved by the magnitude studies.

## Working from the web

Repository changes, CPU tests, and paper planning can proceed without the user's laptop. A new coding task should inspect this file and `specs/interface_study.md`, then work from the active branch. The private HF data, A100 access, and production run outputs require separate access; a GitHub connection does not grant access to them. Do not launch new GPU studies merely to recreate missing outputs when CPU reanalysis of the existing run is sufficient.

## Completed CPU inspection: sequential trajectories and numeric recovery

The author supplied the complete export from `scripts/inspect_magnitude_transfer.py`
for run `20261007_072214_768541_magnitude_transfer_a100_40gb`.
See `specs/results/magnitude_transfer_inspection_20261007.md` for exact cases,
reconstructed final residuals, limitations and manuscript wording. This workspace
has read the inspection report, not the raw production JSON directory.

All eight calibrated endings are 24-unit targets: four lighter and four greener,
on six starting colors. All start with `much`. Their first native updates follow
the requested axis and preserve other coordinates to rounding precision, but
seven introduce >5 units of displayed off-axis drift immediately; the eighth
develops it on turn three. Every final off-axis residual norm exceeds five;
seven final requested-axis residuals are below five. The frozen original-axis
policy does not deliberately repair those other coordinates. This supports a
specific display-projection limitation, not a perceptual-nonuniformity or internal
reasoning explanation. Preserve the completed primary experiment and mapping.

All six numeric misses occur on revision one, preserve other coordinates, and
finish at EOS below the token cap. The five errors >1 (44, 15, approximately 10,
10, 10) reach threshold after an oracle-supplied second correction. The remaining
one-unit miss ends within the displayed stopping threshold after one call.
Execution failures remain in estimates; eventual success is not autonomous
self-correction. No additional GPU generation is required for this completed audit.

The CPU inspector implementation passed all 303 repository tests at `1e9be5b`.
This new evidence update changes documentation only. Next implement Machel's
matched natural/restricted × zero-/few-shot oracle-assisted teacher fidelity
control, with separate demonstrations and evaluation states, adequate clause
budgets and explicit model/prompt provenance. Magnitude and display controls do
not resolve the original teacher capability claim or dataset target ambiguity.

## Implemented teacher-fidelity control — GPU run pending

`scripts/run_teacher_fidelity_study.py` implements Machel's matched
**natural/restricted × zero-/four-shot** oracle-assisted restatement comparison.
It takes the saved shared-start run as its parent, validates and snapshots its
frozen assigned starts, and selects four input-only demonstrations (one per
regime). Evaluation excludes those IDs, matching normalized descriptions,
identical target/guess pairs, and empty oracle sets. All conditions share each
held-out case's supplied oracle directions, with up-to-one/up-to-three budgets
and a clause budget at least as large as the actual supplied direction count.
Absent further exclusions, the 64-example parent yields 60 held-out examples
and 480 teacher responses. The archived natural zero-shot prompt is unchanged;
the new literal prompt asks for exact canonical primitive directions.

The runner inherits the parent HF model configuration, with 80 output tokens
for every condition, fresh contexts and one loaded model per invocation.
Atomic response checkpoints, strict frozen-plan reproduction, parent snapshots,
observed model-revision guards, run locks, pending backend errors without fallback,
and CPU-only reanalysis support interrupted runs. Empty/ambiguous teacher text
remains in completion and audit counts rather than being repaired or excluded.

Reports separate finite-vocabulary conservative preservation, simple keyword
set equality, restricted canonical compliance, recognized geometric precision,
negation/broad-vocabulary/unknown-content flags, additions/omissions/reversals,
redundancy, magnitude language and token cost. Raw diagnostic examples and
full manual-review candidates are retained. Uncertified natural feedback is
not automatically wrong; inspect ambiguous wording before attributing any
conservative audit gap to geometric incompetence. Paired uncertainty resamples
whole examples within regimes, retaining both bandwidths; common quartets
and available-pair sensitivity retain completion denominators.

See `specs/teacher_fidelity_study.md` for dry-run, eight-response smoke, resume
and report-only commands. No production teacher result has been run or supplied
yet; CPU simulations validate software only. Local tests pass 117 available
cases, including twelve new teacher tests, with focused lint passing. The next
user action is the dry-run followed by the limited smoke, not a new magnitude
sweep or a rerun of archived completed experiments. Downstream receiving-guesser
effects and unaided teacher generation still need separate evidence.

## 2026-10-07 completed teacher pilot and supplementary meaning audit

The production teacher run completes all 480 responses on 60 held-out examples.
The supplied diagnostic export exposes two lexical-score limitations: descriptions
of the guess relative to the target need direction inversion, and the harmless
`Feedback:` label flags faithful explicit corrections. The exploratory finite
grammar resolves natural zero-shot as 81 matches, 17 mismatches and 22 unresolved
cases. Both four-shot conditions match all 120 supplied sets; restricted zero-shot
matches 104/120 and adds unsupplied directions in sixteen. Omitted canonical
passes are aggregate-only in the uploaded export, not reconstructed raw records.
See `specs/results/teacher_fidelity_20261007.md` for evidence and limits.

Next run `scripts/inspect_teacher_semantics.py --run "$TEACHER_RUN"` (CPU only)
to validate all checkpoints and produce separate supplementary reports. It never
changes primary scores, responses or prompts. Review unresolved wording before
claiming semantic failures, then evaluate matched receiving-guesser revisions.
The original historical teacher table is not reproduced by this new study.

## 2026-10-08 full teacher audit and contextual review

The supplied full-checkpoint report audits all 480 raw responses, with no
aggregate-only records, and exactly confirms the earlier supplementary counts.
`specs/results/teacher_manual_review_20261008.md` records contextual assistant
review of all 22 unresolved messages: fourteen matches under stated task/context
readings, five set mismatches (one scope-sensitive), and three ambiguous cases.
These post-hoc assistant notes do not replace independently reviewed labels or
the frozen finite-grammar report. Named targets such as `lilac rug` explain some
valid comparisons rejected by the deliberately narrow grammar.

The next control is 600 matched, single-revision guesser generations: sixty
examples times two budgets times four original teacher messages plus a canonical
oracle baseline. Messages must remain unchanged, no review-label filtering or
target leakage is allowed, and comparison starts/interface/budgets must match.
This receiving-guesser extension is specified in the review document but is not
yet implemented or run. Full repository CI for the preceding semantic-audit
commit 5d3a600 passed all 330 tests.

## 2026-10-08 receiving-guesser control implemented

`scripts/run_teacher_receiver_study.py` now implements the specified matched
five-arm, one-revision HEX experiment. It requires and validates the complete
teacher run, snapshots every original message, uses identical starts and supplied
constraints across arms, and never selects or repairs feedback using audit labels.
The production plan is 60 examples, 120 example/budget cases, 600 generations.
The shared-start receiver decoding setup is inherited (64 production output
tokens), rather than the teacher's 80-token budget. Recorded model revisions,
frozen-input reproduction, atomic checkpoints and pending backend errors guard
resume; empty/invalid receiver responses remain failures without imputed endpoints.

Reports separate planned completion, common parsed quintets, available pairs,
oracle-constraint movement satisfaction, alignment denominators, close-start drift
and token counts. Paired intervals resample whole examples within regimes with
both budgets retained. Seven added CPU tests cover matched inputs/no injected
target, complete/empty teacher snapshots, smoke/resume and parent preservation,
pending errors and parse failures, integrity/revision guards, matched cohorts,
and production-shape dry-run without model loading. No production receiving
responses exist yet. Commands and limits are in `specs/teacher_receiver_study.md`;
next user step is dry-run followed by a ten-response smoke.

## 2026-10-08 receiving-guesser study complete; stop new GPU experiments

The author reports all 600 receiving revisions parsed, 120 common quintets on
60 examples, no pending/failures or literal target-HEX mentions. Final errors
for natural_0/natural_4/restricted_0/restricted_4/oracle are
36.893/34.403/31.943/33.680/33.784. Restricted zero-shot has the lowest mean,
although its teacher messages added unsupplied directions in sixteen cases.
Faithful restatement and useful receiving feedback are distinct outcomes;
the extra-information hypothesis remains untested by the aggregate report.
See `specs/results/teacher_receiver_20261008.md` for paired intervals and limits.

The planned GPU package is complete. `scripts/inspect_teacher_receiver.py`
adds a CPU-only saved-message audit of literal equivalence, paired error
contributions and lexical additions versus all threshold-qualified oracle
candidates. It validates snapshots/checkpoints and writes separate reports only.
It neither repairs messages nor filters/refits the primary study. Run that
audit, then consolidate evidence/tables/figures and revise the manuscript.
Independent target ambiguity and unaided teacher geometry remain scope limits.

## 2026-10-08 saved-message audit complete; experiment package closed

The author supplied all paired audit groups. Restricted zero-shot has 11 wins,
104 ties and 5 losses versus the oracle, median difference zero. Its 98 literal
identical messages all tie. Six changed messages with the same lexical direction
set contribute -126.040 summed error difference (57.1% of the net advantage);
sixteen addition messages contribute -94.853 (42.9%). These arithmetic
contributions are not causal effects; the six raw same-set messages must be
inspected before naming a particular surface mechanism. The advantage is
concentrated rather than broadly shared across cases.

Natural four-shot has 18 wins / 80 ties / 22 losses despite lexical set
preservation; restricted four-shot has 1 / 118 / 1. No identical actual prompt
produces a different parsed color in the audit, without proving backend
determinism. Lexical additions in natural comparisons are not semantic labels.
See specs/results/teacher_receiver_20261008.md for the disjoint decomposition.

The planned GPU studies and CPU audits are complete. Proceed to evidence-table
consolidation and manuscript revision; schedule new inference only for a concrete
remaining central claim. Crowdsourced-target ambiguity and unaided teacher
geometry remain unresolved scope limits. This update changes documentation only;
the preceding implementation passed all 339 repository CI tests.

## 2026-10-08 first manuscript rewrite

The imported Overleaf baseline remains unchanged. A separate working main,
`paper/latex/color-games-revised.tex`, incorporates the completed matched
controls, quantifier and magnitude transfer results, teacher scope diagnostics,
and unchanged-message reception. New appendices preserve protocol details,
failure tails, stopping replay, original diagnostic tables, and AI disclosure.
The revised claims concern recorded-target control and oracle-assisted
restatement, not unaided perception or universal teacher incapability.

Source checks and a scratch-only alternate-font diagnostic build pass;
the diagnostic has no overfull boxes or undefined references/citations.
The publication-font build still requires Overleaf because local inconsolata
is unavailable. No final revised PDF is claimed. Author review of historical
diagnostic denominators and exact-font layout remains necessary.
See `specs/manuscript_revision_20261008.md` for changes, run provenance, and
remaining checks. No code or GPU protocol changes accompany this rewrite.

## 2026-10-08 content-first expert review

The author has deferred formatting to focus on the scientific content.
`specs/revision_evidence_map.md` is now a current concern-to-evidence checklist,
replacing stale pending-work guidance. Direct-LAB, teacher few-shot/restricted
wording, new model disclosure, and clause-budget controls are complete.
Target ambiguity is addressed by reframing, not resolved empirically;
historical teacher-score provenance remains open.

`specs/manuscript_content_review_20261008.md` records the argument hierarchy:
direction and magnitude are central, held-out frozen-policy transfer is the
constructive finding, and interfaces/teacher reception are supporting controls.
It identifies required archival denominator checks, a source-data availability
audit for target multiplicity, and raw trace review before a second prose pass.
These audits are not claimed completed. No new GPU study or formatting change
is requested; broad capability, human-calibration, and creative-editing claims
remain outside the tested scope. The title and first revised main are unchanged.

## 2026-10-08 source/availability audit and CPU handoff

The checked original configs and May-20 HANDOFF support planned 1k diagnostic
runs, but original captions say 4k; historical teacher debug_400/debug_4000 and
backend/dtype descriptions also conflict. Actual historical table provenance
cannot be established without frozen run metadata. The dataset builder retains
all English entries and joins quality scores by last-occurrence exact-name
lookup; neither target multiplicity nor evaluation collisions have yet been
measured on production data. The builder keeps score >=0.75, while manuscript
prose said >0.75; the working appendix now uses neutral threshold wording.

Added CPU-only target multiplicity inventory and extended the receiver inspector
to print changed same-lexical-set restricted-zero-shot pairs. The uploaded
262-row diagnostic teacher export contains none of those certified pairs.
Five local fixture checks pass. No scientific result, primary report, inference
or controller fitting changes. See specs/results/content_source_audit_20261008.md
for findings, limits and commands to run where the full data/checkpoints reside.

## 2026-10-08 completed production target inventory

The author's machine-side audits now confirm 518,830 unique retained
descriptions and 705,869 unique raw English descriptions, also unique after
case/whitespace normalization. There are no repeated targets. The 725,203
evaluation records have unique exact descriptions, resolving the potential
last-occurrence collision concern for this archived file. Fields contain no
explicit votes or alternative-color targets; human agreement is unmeasured.
Exactly 43,187 retained rows score 0.75, confirming >=0.75 and disproving the
previous strict-threshold wording. Main text and appendix now state the exact
threshold and recorded-target limitation without changing data or results.
See `specs/results/target_inventory_verified_20261008.md` for counts, input
hashes, evidence provenance and limits. Earlier pending-audit notes above are
historical; denominator provenance and raw same-set message review remain open.
