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

## Current interpretation and next work

HEX has the best final endpoint; the legend substantially improves LAB accuracy and directional alignment. Different initial predictions prevent interpreting gains as a causal comparison of feedback alone. A smaller final–best gap may reflect either stable correction or stagnation; inspect saved trajectories before making a control-quality claim. The balanced sample is diagnostic, not a full-scale paper replication.

The next CPU analysis is implemented in `scripts/analyze_interface_study.py`: errors by turn on a fixed common cohort, paired stratified bootstrap intervals, available-pair sensitivity to failures, stationary movement, initially close guesses later lost, and individual final–best gaps. It must run against the actual saved production folder to produce new scientific findings; code tests use simulated responses.

Machel's remaining concerns include crowdsourced-target ambiguity, few-shot teacher capabilities, and oracle-assisted paraphrase/vocabulary confounds. The output-interface study addresses the representation concern but does not resolve those other issues. Magnitude-calibrated feedback should eventually be tested on held-out examples with matched feedback budgets.

## Working from the web

Repository changes, CPU tests, and paper planning can proceed without the user's laptop. A new coding task should inspect this file and `specs/interface_study.md`, then work from the active branch. The private HF data, A100 access, and production run outputs require separate access; a GitHub connection does not grant access to them. Do not launch new GPU studies merely to recreate missing outputs when CPU reanalysis of the existing run is sufficient.
