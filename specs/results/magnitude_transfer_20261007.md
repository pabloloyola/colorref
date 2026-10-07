# Completed sequential magnitude transfer — 2026-10-07

Run: `20261007_072214_768541_magnitude_transfer_a100_40gb`.
Parent: `20261007_054337_204395_magnitude_control_a100_40gb_pilot`.
Source: the user's uploaded completed `reports/transfer_summary.md`. The coding
workspace has read this report, not the production checkpoint folder. Keep
production observations separate from simulated CPU test performance.

## Frozen protocol and completion

The original direction-specific phrase medians are reused without new
calibration or evaluation fitting. Twelve fresh displayed RGB starts (seed 47,
channel range [48,208]) exclude prior calibration/evaluation colors, quantifier
anchors and the close-case start. Targets concern one original LAB axis at
6/12/24 native units. Sixteen target-feasibility exclusions leave 200 targets
and 600 bare/calibrated/numeric games; excluded targets are not replaced.

All conditions inherit the parent's Qwen3-14B HF-transformers settings and
six-decimal direct-LAB axis-legend prompt on the A100 40 GB: bfloat16, thinking
off, temperature zero and 64-token cap. Each response has a fresh context.
Subsequent feedback uses the current displayed uint8 sRGB state, stays on the
original axis, and can reverse sign after overshoot. A target-known oracle
stops at the first displayed ΔE76 ≤5, with at most five generated revisions.
This is a new declared transfer setting, not a rewrite of the original paper's
three-turn protocol. Numeric increments include extra precision and explicit
holds on other coordinates.

The user completed all 600 games with 1,059 generated revisions, all parsed.
All 200 triplets have valid terminal states; there are no pending games,
parse failures, unavailable mappings, zero-call stops or off-axis-residual
endings. All 12 starts enter the common analysis. This avoids parse-selection
or changed-cohort explanations for the reported comparisons, while remaining
a small, fixed one-model/prompt pilot.

## Main results

| Arm | Targets | Mean final ΔE | Median final ΔE | Converged | Mean calls | Total calls | Harmful revisions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bare direction | 200 | 6.461 | 3.935 | 148/200 (74%) | 2.580 | 516 | 152/516 (29.5%) |
| Frozen calibrated wording | 200 | 2.979 | 2.377 | 192/200 (96%) | 1.690 | 338 | 11/338 (3.3%) |
| Exact numeric increment | 200 | 0.095 | 0.000 | 200/200 (100%) | 1.025 | 205 | 1/205 (0.5%) |

Calibrated minus bare, with reported starting-color cluster percentile
95% intervals:

| Measure | Difference [95% interval] |
|---|---:|
| Mean final displayed error | −3.483 [−4.198, −2.739] |
| Mean generated calls | −0.890 [−1.131, −0.654] |
| Convergence proportion | +0.220 [0.158, 0.277] |

This is about 53.9% lower mean terminal error (from rounded means), 178 fewer
evaluation calls (34.5%), and 22 percentage points higher threshold convergence. The
comparison improves both terminal accuracy and generation cost; it does not
obtain the lower error by spending more revisions. Both arms use the same
stopping rule and maximum budget. These savings exclude the parent's 288
one-time calibration calls; the fitted map is already available here. Cold-start
end-to-end savings require amortizing that calibration across later targets. Selected wording still conveys magnitude
information absent from the bare direction, so this is a policy comparison,
not an equal-information wording test or proof that calibration is necessary
relative to every uncalibrated graded-wording policy.

All twelve per-start mean error differences favor calibrated wording; omitting
any single start leaves a favorable descriptive pooled mean, ranging from
−3.730 to −3.312. Summing the exhaustive direction bins gives 115 calibrated
wins, 40 ties and 45 losses at the exploratory 0.01 ΔE tie tolerance. Favorable
mean behavior across starts does not imply improvement on every target.
The 200 targets are repeated observations of twelve starting colors, not 200
independently sampled colors.

## Observed one-/three-/five-revision budgets

All rows use the same 200-target common cohort. An earlier stopped state is
retained without extra generated calls. These are observed prefixes, not
independently rerun conditions.

| Budget | Bare error / successes / mean calls | Calibrated error / successes / mean calls | Numeric error / successes / mean calls |
|---|---|---|---|
| 1 | 10.147 / 82 / 1.000 | 6.434 / 119 / 1.000 | 0.534 / 195 / 1.000 |
| 3 | 7.006 / 139 / 2.000 | 3.339 / 187 / 1.580 | 0.095 / 200 / 1.025 |
| 5 | 6.461 / 148 / 2.580 | 2.979 / 192 / 1.690 | 0.095 / 200 / 1.025 |

Within this new study, calibrated error falls descriptively from 6.434 after
one revision to 2.979 at the shared stopping/five-revision endpoint. This is the
appropriate same-cohort view of repeated control. Comparing the previous
196-target pilot directly with this new 200-target endpoint would additionally
change starting colors and target feasibility.

Most calibrated successes occur within three revisions (187 versus 192 at
five). The fourth/fifth revisions add five successes at 22 additional calls;
this is a descriptive cost comparison, not a newly optimized or predeclared
three-revision policy. Preserve the frozen five-revision primary endpoint and
report the secondary prefixes transparently.

## What happens at larger distances?

| Requested native distance | N | Bare final ΔE | Calibrated final ΔE | Calibrated − bare [95% interval] | Wins / ties / losses |
|---|---:|---:|---:|---:|---|
| 6 | 72 | 7.188 | 2.319 | −4.869 [−5.874, −3.909] | 54 / 12 / 6 |
| 12 | 70 | 5.736 | 2.402 | −3.334 [−4.693, −2.031] | 34 / 19 / 17 |
| 24 | 58 | 6.434 | 4.493 | −1.940 [−3.534, −0.510] | 27 / 9 / 22 |

The aggregate 24-unit comparison now favors calibrated wording in this new
sequential study. It does not prove that every large correction is resolved:
only 27/58 large-distance cases strictly favor calibrated wording, and the
median paired difference is zero. Subgroup intervals are exploratory and not
multiplicity-adjusted.

The main remaining weakness is lighter/24: calibrated mean error is 9.066
versus 3.514 for bare wording, difference +5.552 [−0.266, 12.179] on seven
feasible starts. Its interval crosses zero and is wide, but its worse mean
motivates inspecting the actual saved trajectories. Red/24 ends at 3.331
versus 3.044, difference +0.288 [−0.490, 1.116], rather than a clear advantage.
Do not infer a perceptual-uniformity, gamut, or internal reasoning cause from
these aggregate bins alone.

## Overshoot, projection and numeric execution

Bare/calibrated have 152/11 harmful revisions and 174/48 revisions whose
requested sign reverses relative to the original target direction. These
patterns are consistent with less excessive movement under the calibrated
policy, but the adaptive histories and counts differ; per-revision rates are
descriptive, not independent samples for a significance test. Native mean
requested steps are 21.290/10.752, while displayed steps are 19.681/10.243.
Different magnitudes therefore appear before display projection. Mean
projection errors are 1.972/0.932, with projection ΔE>1 in 49/14 responses.
Both the chosen native updates and the display boundary matter; this summary
does not identify their independent causal contributions.

Numeric games all converge, with 195 stopping after one call and five after
two. Nevertheless, native execution has five revisions with error >1 and one
additional revision above 0.01; 199/205 are within 0.01 and 200/205 within 1.
Mean/median/p95/max are 0.439/0.000/0.001/44.000. Final success cannot erase
those intermediate mistakes. The target-known oracle supplies subsequent
corrections; this is not evidence of autonomous model self-correction. Inspect
the miss exports before describing the large error mechanism or associating
individual errors with particular second-call recoveries.

## Manuscript wording candidate

> On twelve fresh starting colors, a frozen direction-specific wording policy
> improved sequential single-axis control under a shared target-known stopping
> rule. Across 200 feasible targets, calibrated feedback reduced mean displayed
> ΔE76 from 6.461 to 2.979 (paired difference −3.483; starting-color cluster
> bootstrap 95% interval [−4.198, −2.739]), increased threshold convergence from
> 74% to 96%, and required 34.5% fewer model calls during evaluation. Exploratory breakdowns show
> an aggregate advantage at 24-unit target distances, while large lightness
> corrections remain a limitation. Exact numeric feedback reached all targets
> but retained a small tail of intermediate coordinate-execution failures.
> These results demonstrate transfer of the frozen feedback policy in a
> controlled coordinate task; human quantifier judgments and creative editing
> remain untested.

## Next action: inspect the eight calibrated endings and numeric tails

No new GPU generation or controller fitting is needed. The CPU inspector
validates the frozen transfer plan and every saved checkpoint, then exports
calibrated nonconverged endings and parsed native numeric misses >0.01.
It writes separate inspection files; original summaries, raw responses and
calibration inputs remain unchanged. Run from the repository root:

```bash
TRANSFER_RUN=runs/20261007_072214_768541_magnitude_transfer_a100_40gb
uv run python scripts/inspect_magnitude_transfer.py --run "$TRANSFER_RUN"
cat "$TRANSFER_RUN/reports/transfer_inspection.md"
```

The report shows error traces, selected phrases and calibration medians,
native/displayed movement, off-axis drift, projection error, and matched
bare/numeric endpoints for each calibrated ending. Numeric misses retain
expected/actual coordinates, prompts/responses, generation diagnostics and
final game outcomes. Full revision records and input digests are exported to
`metrics/transfer_inspection.json`. Pending games are counted separately;
failed/unavailable endpoints never receive imputed final errors. For the
completed production run, expect eight calibrated endings and six numeric
revisions above 0.01 (five above 1); the inspector derives counts from the
saved data rather than assuming them.

After that audit, prioritize Machel's matched zero-/few-shot teacher controls
and literal restricted-axis restatement versus the original paraphrase prompt.
These receiving-model magnitude results do not resolve the original teacher
capability criticism. Avoid broadening the quantifier ladder on evaluated
colors or launching another broad sweep before addressing the teacher evidence.
