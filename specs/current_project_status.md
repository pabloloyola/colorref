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

Machel's remaining concerns include crowdsourced-target ambiguity, few-shot teacher capabilities, and oracle-assisted paraphrase/vocabulary confounds. The output-interface study addresses the representation concern but does not resolve those other issues. Magnitude-calibrated feedback should eventually be tested on held-out examples with matched feedback budgets.

## Next runnable CPU analysis: stopping replay

`scripts/replay_shared_start_stopping.py` compares three fixed rounds with stopping at the first saved displayed state at ΔE ≤ 5, including the assigned start. It uses the frozen run threshold by default, validates saved plans/checkpoints, and writes `reports/stopping_replay_summary.md` plus `metrics/stopping_replay.json`. Paired statistics use the same common fully parsed fixed-round cohort; all-planned completion counts separately distinguish early threshold stops, exhaustion, parsing failure and pending cases. It uses no inference, repairs, future best-state selection or endpoint imputation, and preserves original outputs.

The uploaded 140096 case verifies the prefix logic: all three interfaces retain starting error 2.380 with zero new calls rather than the forced-round final errors. This is a one-case check; full-cohort stopping results require running on the GPU-local saved folder. Local verification has 59 passing targeted CPU tests and focused lint, separate from production model performance.

`specs/magnitude_control_pilot.md` specifies the follow-up calibration/evaluation split, single-axis LAB control, quantifier-aware versus bare versus exact-numeric comparison, shared stopping, cluster analysis, and separate HSV saturation calibration. It is a protocol draft, not an implemented/executed GPU study. Do not silently apply medians from the old quantifier prompt to the reference-game prompt.

## Working from the web

Repository changes, CPU tests, and paper planning can proceed without the user's laptop. A new coding task should inspect this file and `specs/interface_study.md`, then work from the active branch. The private HF data, A100 access, and production run outputs require separate access; a GitHub connection does not grant access to them. Do not launch new GPU studies merely to recreate missing outputs when CPU reanalysis of the existing run is sufficient.
