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

See `specs/results/magnitude_transfer_20261007.md` for evidence, budget/subgroup qualifications, manuscript wording and a read-only CPU command that validates checkpoints and exports the eight calibrated nonconverged endings plus numeric tails. `specs/magnitude_transfer_followup.md` remains the implemented protocol/command reference. Do not rerun completed GPU inference. The next work is that targeted CPU inspection, followed by Machel's zero-/few-shot and restricted-restatement teacher controls. The original teacher capability claim remains unresolved by the magnitude studies.

## Working from the web

Repository changes, CPU tests, and paper planning can proceed without the user's laptop. A new coding task should inspect this file and `specs/interface_study.md`, then work from the active branch. The private HF data, A100 access, and production run outputs require separate access; a GitHub connection does not grant access to them. Do not launch new GPU studies merely to recreate missing outputs when CPU reanalysis of the existing run is sufficient.
