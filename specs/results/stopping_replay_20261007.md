# Production stopping replay — 2026-10-07

Source: the user's GPU-local `reports/stopping_replay_summary.md` for
`20261007_043619_593902_shared_start_interface_study_a100_40gb`.
The coding workspace has received this summary, not the full raw run folder.
This is CPU reanalysis of saved trajectories, with zero new generations.

The frozen target-known rule retains the first displayed state at ΔE ≤ 5,
including an assigned turn-zero state. All 64 examples (16 per regime) have
fully parsed matched trajectories, so the fixed and stopped cohorts match.

| Interface | Fixed final ΔE | Stopped ΔE | Fixed / stopped converged | Fixed / stopped calls | Calls saved |
|---|---:|---:|---:|---:|---:|
| HEX | 22.781 | 22.005 | 4 / 8 | 192 / 185 | 7 |
| Plain LAB | 35.275 | 34.562 | 1 / 4 | 192 / 186 | 6 |
| LAB with legend | 23.161 | 22.822 | 7 / 9 | 192 / 182 | 10 |

Stopped-minus-fixed error differences with the reported paired, regime-stratified
95% percentile intervals are −0.776 [−1.681, −0.137] for HEX,
−0.713 [−1.594, −0.033] for plain LAB, and −0.339 [−1.039, 0.051]
for LAB with a legend. The latter includes zero. These are exploratory,
cohort-conditional intervals, with no adjustment for multiple comparisons.

Across the three conditions, stopping saves 23/576 revisions (4.0%) and retains
21 converged interface–example outcomes instead of 12. These are repeated
observations of the same 64 examples, not 192 independent colors. Nine fixed
trajectories lose a previously reached threshold, spread over seven distinct
examples. Three of those trajectories share the same initially close
`dull toy red` example; do not count them as three independent close cases.

The smaller legend error reduction is particularly concentrated in that case:
using the rounded summaries, retaining 2.380 rather than its forced endpoint
23.197 contributes about 0.325 of the 0.339 mean improvement. Thus, the aggregate
mean change is not evidence of a broad improvement in step-size calibration.

## Interface comparison after stopping

| Comparison (right minus left) | Stopped mean Δ error [95% interval] |
|---|---:|
| HEX → plain LAB | +12.557 [6.536, 18.586] |
| Plain LAB → legend LAB | −11.740 [−17.658, −5.019] |
| HEX → legend LAB | +0.817 [−4.467, 6.686] |

The plain-LAB disadvantage and the legend's final improvement over plain LAB
persist. Similar HEX/legend means do not establish equivalence. Stopping
addresses loss after reached success; it does not account for the substantial
remaining target error or demonstrate calibrated magnitudes above threshold.

## Manuscript wording candidate

> A target-known stopping replay retained the first state within ΔE76 ≤ 5,
> including the supplied start, on the same 64 matched examples. Compared with
> three forced revisions, it preserved nine otherwise lost convergence outcomes
> and saved 23 of 576 revisions. Mean final error decreased modestly, while the
> plain-LAB disadvantage persisted. This diagnostic separates loss after reached
> convergence from inaccurate corrections above threshold; it is an oracle
> benchmark policy, not a deployable model-only stopping mechanism.

Do not silently replace the forced-round results, claim best-state selection,
or interpret this as a reproduction of the paper's historical early-stopping
protocol. The next single-axis magnitude pilot fits new calibration responses
and evaluates a controller on separately frozen held-out colors.
