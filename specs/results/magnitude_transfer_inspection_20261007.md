# Sequential magnitude-transfer trajectory inspection — 2026-10-07

## Evidence and scope

The author supplied the complete `reports/transfer_inspection.md` export for
`20261007_072214_768541_magnitude_transfer_a100_40gb` as `Pasted text(5).txt`.
It reports 600 planned/completed games and 1,059 saved, parsed revisions.
Bare/calibrated/numeric threshold-stop counts are 148/192/200; remaining
games exhaust the five-revision cap (52/8/0). There are no pending games,
parse failures or unavailable mappings. The raw production JSON checkpoints
remain on the GPU machine; the coding workspace has read the full inspection
export, not that directory.

This is a descriptive audit of the selected nonconverged trajectories and
numeric execution misses, not a new experiment, controller fit, confidence
interval or reason to exclude any case. The completed primary comparison
and calibration remain unchanged. See `magnitude_transfer_20261007.md` for
the full-cohort results and limitations.

## All eight calibrated failures involve large corrections

Four failures are lighter/24 and four are greener/24, on six distinct starts.
Every first correction selects `much`. Each first native output moves in the
requested direction and preserves the other two coordinates to rounding
precision (maximum off-axis native change 0.00185 LAB units). Nevertheless,
projection into displayed uint8 sRGB changes other coordinates: first-turn
off-axis displayed movements exceed five units in seven of these eight
cases. The remaining lighter case develops substantial drift on turn three.

| Case | First native step | Fitted displayed median | First projection ΔE | Final displayed error |
|---|---:|---:|---:|---:|
| transfer_02 lighter/24 | 40.000 | 28.722 | 19.789 | 19.729 |
| transfer_08 lighter/24 | 31.583 | 28.722 | 8.735 | 8.944 |
| transfer_00 lighter/24 | 40.000 | 28.722 | 8.361 | 8.630 |
| transfer_07 greener/24 | 60.000 | 30.038 | 31.352 | 6.299 |
| transfer_10 greener/24 | 103.092 | 30.038 | 57.213 | 16.224 |
| transfer_05 greener/24 | 55.044 | 30.038 | 24.345 | 8.426 |
| transfer_00 greener/24 | 92.530 | 30.038 | 35.444 | 11.544 |
| transfer_05 lighter/24 | 53.821 | 28.722 | 3.999 | 20.268 |

Native steps and displayed medians are different quantities; their difference
is not itself a calibration-error metric. In particular, boundary projection
can compress a large native step while introducing off-axis drift. The green
native outputs are state dependent: three replace a positive `a` coordinate
with its negative counterpart (approximately 51.546 → −51.546,
27.524 → −27.520, and 46.265 → −46.265). This is an observable output pattern,
not proof that the model internally represents “much greener” as a sign flip.

Bare feedback converges in six of these eight cases; numeric feedback converges
in all eight in one call. Calibrated feedback remains much better than bare
in one failed green case (8.426 versus 66.867), illustrating why failure
selection alone cannot establish an overall policy ranking.

## The fixed-axis protocol does not deliberately repair projection drift

The receiving model sees the projected displayed state at each revision, and
the frozen transfer policy continues correcting only the original axis.
Subsequent native updates largely preserve the already shifted coordinates.
Direction reversal can correct overshoot along that axis, but it does not
explicitly restore the other two target coordinates.

For each printed final response, the coding workspace recomputed displayed
LAB with the same `parse_response(..., "lab")` conversion used by the runner.
It then decomposed the final residual into requested-axis disagreement and
the Euclidean norm of the other two coordinates:

| Case | Absolute requested-axis residual | Off-axis residual norm | Total error |
|---|---:|---:|---:|
| transfer_02 lighter/24 | 0.549 | 19.722 | 19.729 |
| transfer_08 lighter/24 | 2.931 | 8.450 | 8.944 |
| transfer_00 lighter/24 | 2.139 | 8.360 | 8.630 |
| transfer_07 greener/24 | 1.962 | 5.986 | 6.299 |
| transfer_10 greener/24 | 0.029 | 16.224 | 16.224 |
| transfer_05 greener/24 | 1.053 | 8.360 | 8.426 |
| transfer_00 greener/24 | 6.105 | 9.798 | 11.544 |
| transfer_05 lighter/24 | 4.512 | 19.759 | 20.268 |

All eight off-axis residual norms alone exceed the stopping threshold of five;
seven requested-axis residuals are already below five. For example,
`transfer_10` ends within 0.029 units of the target `a` value, but its remaining
lightness/blue-yellow error has norm 16.224. `transfer_02` has lightness error
0.549 while its remaining chromatic error has norm 19.722.

Holding the other coordinates fixed, setting the requested coordinate exactly
to its target would leave the listed off-axis residual. This is a geometric
diagnostic of each current endpoint, not a lower bound on every possible
future projected trajectory: further clipping could change other coordinates
incidentally. The protocol's `off_axis_residual` terminal label requires the
requested-axis residual to be at most 0.01; none of these endings meets that
condition, so all correctly retain `budget_exhausted`.

These traces establish a concrete display-projection effect. They do not
establish perceptual nonuniformity as the explanation, nor separate the causal
contribution of wording from starting-state geometry in a randomized ablation.
Every native output remains inside the prompt's coordinate bounds; those
bounds do not guarantee a feasible displayed sRGB color.

## Numeric mistakes are execution failures followed by oracle-assisted recovery

| Case and initial request | Native execution error | Unrequested coordinate residual | Final displayed error | Calls |
|---|---:|---:|---:|---:|
| transfer_04 red/6 | 44.000 | 0 | 0.000 | 2 |
| transfer_08 yellow/24 | 15.000 | 0 | 0.405 | 2 |
| transfer_11 yellow/24 | 10.000039 | 0 | 0.000 | 2 |
| transfer_09 green/12 | 10.000 | 0 | 0.682 | 2 |
| transfer_08 green/12 | 10.000 | 0 | 0.228 | 2 |
| transfer_09 blue/24 | 1.000 | 0 | 1.147 | 1 |

All six misses occur on revision one. The five misses above one unit finish
at EOS after 33–34 tokens, without reaching the 64-token budget; the one-unit
miss uses 35 tokens and also finishes at EOS. All preserve the unrequested
coordinates. Thus these observed cases are neither parse failures nor
truncated arithmetic expressions. The first five converge after a new,
target-known numeric correction; the one-unit miss is already within the
five-unit displayed stopping threshold and therefore receives no second call.

For the largest miss, −48.440426 + 5.943433 should produce −42.496993,
but the response gives +1.503007, an error of 44. The repeated near-integer
offsets characterize the observed tail; they do not identify a digit-handling
or internal arithmetic mechanism. Native execution accuracy and eventual
displayed convergence remain separate metrics. Recovery is oracle assisted,
not autonomous model self-correction.

## Revision implication and next work

The practical limitation is that reliable directional signs and ordinal
quantifier ordering do not ensure a suitable, displayable step. A
direction-specific median may transfer on average while a large update
creates drift that this deliberately single-axis protocol cannot directly
repair. State-dependent magnitude calibration, gamut-aware steps and
multi-axis repair are future, separately evaluated controls. Do not change
the frozen controller or retrofit those policies to these evaluated cases.

The next priority remains Machel's oracle-assisted teacher concern. Compare
the original natural paraphrase and literal restricted-axis restatement,
each zero-shot and few-shot, on identical held-out target/guess states and
supplied oracle directions. Demonstrations must be separate from evaluated
states/descriptions; clause budgets must accommodate all supplied directions.
Report exact direction-set preservation, additions/omissions/substitutions,
contradictory signs, unsupported vocabulary and completion separately.
Automatic keyword detection alone does not resolve natural-language meaning
(especially negation or broad warmer/cooler terms); retain raw outputs and
manually audit ambiguous cases. Audit teacher fidelity first, then test its
downstream effect on a guesser with matched starts. These controls need no
second simultaneous 14B model instance on the A100.

Suggested manuscript wording:

> Inspection of the eight nonconverged calibrated trajectories identifies a
> limitation of single-axis control after display projection. All involve
> 24-unit targets and begin with a large graded correction. Although native
> responses initially preserve the unrequested coordinates, sRGB projection
> introduces drift; at every final endpoint, off-axis disagreement alone
> exceeds the convergence threshold. Subsequent feedback corrects only the
> original axis, leaving those changes without explicit repair. Exact numeric
> feedback also retains rare coordinate-execution errors, including those
> subsequently corrected by target-known oracle feedback; all remain in the
> reported execution metrics.
