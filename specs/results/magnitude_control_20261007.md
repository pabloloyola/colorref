# Completed held-out magnitude pilot — 2026-10-07

Run: `20261007_054337_204395_magnitude_control_a100_40gb_pilot`.
Source: the user's uploaded `Pasted text(3).txt`, containing the completed GPU
log and `reports/magnitude_summary.md`. The coding workspace has read this
report, not the raw 876-response folder. Keep production evidence separate from
simulated CPU test outputs.

## Protocol and completion

Qwen/Qwen3-14B, HF transformers, one A100 40 GB, bfloat16, thinking disabled,
temperature 0, 64 generated-token cap. The model snapshot observed in the log
is `40c069824f4251a91eefaf281ebe4c544efd3e18`. Each adjustment is a fresh context
with the same six-decimal direct-LAB axis-legend prompt. Displayed uint8 sRGB
states and ΔE76 target error are primary; native coordinates remain diagnostic.

Twelve calibration colors fit direction-specific medians; twelve distinct
held-out colors do not fit them. All colors/target candidates are frozen before
model queries. Calibration completes 288/288 responses, 287 parsed. Evaluation
completes all 588 planned responses, all parsed: 196 matched triplets on the
12 held-out colors. The 20 target-feasibility exclusions remain explicit;
no missing bin is filled using a replacement color. Each target concerns one
LAB direction and one requested 6/12/24-unit distance.

## Main completed results

| Condition | Matched cases | Mean displayed target ΔE | Mean gain | Displayed direction follow | Mean off-axis drift | Mean projection ΔE | Projection > 1 N |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bare direction | 196 | 11.770 | 1.395 | 1.000 | 1.164 | 5.411 | 29 |
| Calibrated quantifier | 196 | 6.362 | 6.803 | 1.000 | 0.438 | 0.967 | 10 |
| Exact numeric | 196 | 0.533 | 12.632 | 1.000 | 0.167 | 0.177 | 0 |

Calibrated minus bare mean error: **−5.408**, with the reported starting-color
cluster bootstrap 95% percentile interval **[−10.220, −2.173]**. This is about
46% lower mean disagreement, calculated from the rounded displayed means.
Numeric minus bare: **−11.237 [−16.746, −7.746]**. Common-triplet and available-pair
estimates match because all evaluation outputs parse. The 196 target cases
are repeated observations of 12 starting colors, not 196 independent colors.
These are conditional pilot intervals, not evidence of broad population or
model-family generalization; there is no multiplicity adjustment.

Mean prompt tokens are 168.520, 169.668 and 187.954; mean generated tokens are
34.490, 34.724 and 34.510 for bare/calibrated/numeric. Small token-count changes
are not proof of equal information content: calibrated wording conveys a
selected magnitude category, and numeric instructions convey exact increments
and explicit coordinate holds.

## What this supports

1. Directional compliance is insufficient for localization: all three conditions
   follow the requested displayed axis, but their remaining target errors differ.
2. A direction-specific policy using empirically fitted magnitude phrases improves
   one-step held-out localization over bare directional corrections under this
   receiving prompt. Lower projection error and off-axis drift accompany the
   improvement; aggregate means do not establish a causal decomposition.
3. More precise coordinate instructions produce much lower average error in
   this task, while still permitting numeric execution failures. This is an
   encoding/execution control with additional information, not a fair test of
   natural wording versus numerals at identical semantic precision.

This comparison does not establish that empirical calibration is necessary:
there is no separate uncalibrated graded-phrase selection policy in this pilot.
It does not prove a learned internal perceptual semantics, human agreement on
quantifier magnitude, multi-turn transfer, or usefulness in an image editor.
The claim concerns operational behavior under a frozen oracle policy.

## Quantifier resolution and the geometry hypothesis

Displayed medians for `a little` span 1.139–4.917 requested-axis units across
directions; `somewhat` spans 5.073–10.094. The median `much` steps span
28.722–75.844. These are fitted calibration medians, not evaluation predictions
or universal perceptual distances. In red, `somewhat` yields 5.073 versus
75.844 for `much`, leaving a wide gap in the phrase ladder.

Large native steps change substantially after display projection: `much`
blue has native/displayed medians 103.642/48.137; yellow 103.067/54.333;
green 51.465/30.038. Calibration `much` outputs have projection ΔE>1
in 54/72 trials. This supports investigating direction- and start-dependent
boundary effects. It does not by itself explain how the model chooses its
native step. Equal L/a/b coordinate movements have equal norm in ΔE76,
while human perceptual uniformity is approximate and the sRGB feasible region
is restricted. Small native steps also vary by direction despite low projection
cost, so a geometry-only explanation is not established.

The completed CPU audit retains native and displayed steps and reports direction/distance
bins, per-start means, phrase median-target gaps and actual step-transfer
mismatches. Those quantities diagnose resolution and transfer variability;
they are not independent or additive causal components of final target error.

## Completed exploratory breakdown supplied by the user

The CPU audit has now run on the production folder. All 196 triplets remain in
its common cohort. The median paired error difference is 0.000, with
93 wins, 57 ties and 46 losses for calibrated versus bare wording at the
explicit exploratory 0.01 ΔE tie tolerance. Do not describe the aggregate 46%
mean reduction as a 46% improvement for a typical target or as universal gain.

| Endpoint | Bare | Calibrated | Numeric |
|---|---:|---:|---:|
| Converged (displayed ΔE ≤ 5) | 94/196 | 125/196 | 192/196 |
| Worse than supplied starting error | 48/196 | 3/196 | 2/196 |
| Beyond geometric improvement bound | 48/196 | 3/196 | 2/196 |
| Mean native requested-axis step | 23.539 | 11.673 | 13.633 |
| Mean displayed requested-axis step | 18.524 | 11.086 | 13.633 |

The native step already differs substantially between bare and calibrated
conditions, before display projection. This is evidence of different generated
update magnitudes, not proof of an internal reasoning mechanism. Projection
also changes the displayed step and error, but cannot be the only observed
difference. The geometric bound counts and worsening counts agree in this run;
all directions remain followed, demonstrating that excessive magnitude can
harm localization despite correct signs.

Convergence rises from about 48.0% to 63.8% (+15.8 percentage points), while
harmful updates fall from 48 to 3. Reductions in harmful updates are a clearer
behavioral characterization here than claiming uniformly more precise steps.

| Requested native distance | N | Bare error | Calibrated error | Paired difference [95% interval] | Calibrated wins / ties / losses |
|---|---:|---:|---:|---:|---:|
| 6 | 72 | 12.377 | 2.541 | −9.836 [−14.777, −6.573] | 52 / 18 / 2 |
| 12 | 69 | 9.323 | 3.549 | −5.774 [−11.334, −1.941] | 25 / 28 / 16 |
| 24 | 55 | 14.046 | 14.892 | +0.846 [−3.137, 3.878] | 16 / 11 / 28 |

The mean advantage concentrates on small and medium corrections; there is no
clear aggregate advantage at 24 units. Feasibility exclusions give the distance
bins unequal sizes. In red, the calibrated policy is worse overall by
+0.938 [0.374, 1.524], improving at distance 6 but worsening at 12 and 24.
These subgroup intervals are exploratory and not multiplicity-adjusted.

The red phrase median-target gaps average 0.918, 7.000 and 18.914 across the
three distances, while actual step-transfer mismatch averages 1.822 throughout.
This is consistent with coarse phrase resolution contributing to undercorrection.
It is not a causal attribution based on a separate ladder intervention. The
calibration table has `somewhat` near 5 and `much` near 76, so the frozen
nearest-median policy lacks an intermediate calibrated phrase for red targets.

Green at 24 units has a smaller median-target gap (6.007) but much larger
step-transfer mismatch (16.973), indicating a different diagnostic pattern:
the selected calibration median is a poor predictor of some actual held-out
steps. Native/displayed outputs and prompts must be inspected before attributing
that variability solely to gamut geometry or linguistic interpretation.

Eleven of twelve starting colors have a favorable mean difference; one does
not. Omitting any one start leaves a favorable descriptive mean difference,
ranging from −6.061 to −3.330. Start evaluation_09 has especially large leverage
(−27.293 mean difference over 17 cases), but removing it still leaves −3.330.
Leave-one-start-out values are descriptive checks, not new confidence intervals
or grounds to discard difficult colors.

## Numeric failures

Completed mean native execution error is 0.480; mean error against the projected
instructed result is 0.487. Mean disagreement between the projected instructed
result and hidden displayed target is 0.049, separating display construction
from model coordinate execution.

The earlier smoke identified `evaluation_06:more_red:6:numeric`: increasing
a from −43.698223 by 5.758459 should yield −37.939764, but the model returned
1.060236, preserving L/b. Native execution error is exactly 39. The response
ends at EOS after 34 tokens, below the 64-token cap. It remains in performance
statistics. The completed CPU audit finds 188/196 controls within 0.01 native ΔE
(95.9%), 192/196 within 1 (98.0%), and four above 1. Native error median and
p95 both round to 0.000; max is 39. Eight controls exceed 0.01. The largest
miss contributes 41.4% of summed native errors, so neither a low mean nor the
rounded p95 captures the catastrophic tail adequately.

The four errors above 1 are 39, 32, 12 and 10 units; all concern the requested
coordinate while preserving the other coordinates. All four have EOS finish
labels below the token limit and projection ΔE under 0.5. Their expected
requested coordinates are negative; three actual coordinates become positive,
and the fourth changes −11.201189 to −1.201189. These are observable numeric
execution/transcription failures. An internal digit-loss or sign mechanism is
not established by the outputs alone. The one-unit error and small rounding
errors remain in the full metrics too. No errors are repaired or removed.

## Manuscript wording candidate

> In a one-step held-out control pilot, a direction-specific oracle calibrated
> on 12 starting colors selected graded corrections for 196 targets constructed
> from 12 separate colors. Calibrated wording reduced mean displayed ΔE76 from
> 11.770 to 6.362 (paired difference −5.408; starting-color cluster bootstrap
> 95% interval [−10.220, −2.173]) despite perfect requested-axis compliance
> under both conditions. It reduced harmful updates from 48 to 3 and increased
> threshold convergence from 94 to 125 cases. Exploratory breakdowns localize
> the gains to small and medium corrections; large corrections and red updates
> expose limited phrase resolution and transfer. Exact coordinate instructions
> achieved 0.533 mean target error, with 188/196 native updates within 0.01 of
> the instructed result and a small tail of large execution mistakes. These
> results distinguish direction following, magnitude control, and coordinate
> execution; multi-turn and creative-editing transfer remain open.

## Next CPU command

```bash
git pull --ff-only origin refactor/quantifier-calibration
MAG_RUN=runs/20261007_054337_204395_magnitude_control_a100_40gb_pilot
uv run python scripts/analyze_magnitude_control.py --run "$MAG_RUN"
cat "$MAG_RUN/reports/magnitude_breakdown.md"
```

This writes only `metrics/magnitude_breakdown.json` and
`reports/magnitude_breakdown.md`; primary summaries, configuration, plans,
controller and checkpoints remain unchanged. The completed subgroup analysis is
exploratory after seeing aggregate results. The proposed sequential follow-up
is specified in `specs/magnitude_transfer_followup.md` and is not implemented. Do not retune the controller on
this evaluation set; a changed policy needs a fresh held-out comparison.
