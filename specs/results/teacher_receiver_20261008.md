# Completed matched teacher-feedback reception

Run: `20261007_152230_242355_teacher_receiver_a100_40gb`.
Parent: `20261007_134620_125917_teacher_fidelity_a100_40gb`.
Source: author-supplied completed receiver summary, 2026-10-08 Asia/Tokyo.

All 600 revisions parse; all 120 example/budget quintets are available on
60 examples. No pending/failed outputs, empty teacher messages or literal
teacher target-HEX mentions are reported. All arms share supplied HEX starts
and one 64-token-budget fresh-context revision. Starting error is 39.827.

| Feedback arm | Final ΔE | Gain | Oracle-constraint satisfaction | Alignment (N) | Converged / 120 |
|---|---:|---:|---:|---|---:|
| natural_0 | 36.893 | 2.934 | 0.650 | 0.334 (119) | 0 |
| natural_4 | 34.403 | 5.425 | 0.863 | 0.616 (119) | 1 |
| restricted_0 | 31.943 | 7.885 | 0.867 | 0.636 (119) | 1 |
| restricted_4 | 33.680 | 6.148 | 0.868 | 0.631 (119) | 1 |
| canonical oracle | 33.784 | 6.044 | 0.868 | 0.627 (119) | 1 |

Reported gains use unrounded source values and can differ from subtraction of
displayed rounded means. One undefined alignment per arm is excluded from
alignment only; target accuracy retains every parsed case. No threshold stops
occur in this fixed one-revision study.

## Paired interpretation

Intervals are exploratory percentile 95% intervals resampling whole examples
within regimes and retaining both budgets. No multiplicity correction or
generation-randomness uncertainty is provided. All common-quintet and
available-pair counts/effects coincide because there are no failures.

| Right minus left | Δ final error | 95% interval |
|---|---:|---|
| natural_4 − natural_0 | -2.491 | [-5.760, 0.795] |
| restricted_0 − natural_0 | -4.951 | [-8.394, -1.315] |
| restricted_4 − natural_4 | -0.723 | [-2.818, 1.674] |
| restricted_4 − restricted_0 | 1.737 | [0.224, 3.711] |
| restricted_0 − oracle | -1.841 | [-3.772, -0.322] |
| restricted_4 − oracle | -0.104 | [-0.397, 0.085] |

Restricted zero-shot has the lowest mean error in this cohort. Its interval
against natural zero-shot excludes zero; natural four-shot improves the mean
over natural zero-shot but that interval includes zero. Four-shot restricted
feedback does not outperform zero-shot restricted feedback in this pilot.
Restricted four-shot is close to the canonical oracle in the observed mean,
but an interval spanning zero does not establish equivalence.

The teacher-restatement audit showed restricted_0 adds unsupplied directions
in sixteen messages. Its receiving advantage therefore cannot be treated as
an information-matched benefit of better restatement. Added directions might
provide useful information, but this summary does not show where the paired
advantage originates. Wording/order can differ even when direction sets match.
Do not assert a causal explanation without the saved-message audit or a new
randomized control. Natural comparisons can be semantically valid yet have
weaker average downstream movement than explicit instructions; this does not
make every comparative message wrong or useless.

## Bandwidth diagnostic

| Arm | c1 final ΔE | c3 final ΔE |
|---|---:|---:|
| natural_0 | 39.058 | 34.729 |
| natural_4 | 35.472 | 33.333 |
| restricted_0 | 33.973 | 29.913 |
| restricted_4 | 35.246 | 32.114 |
| oracle | 35.511 | 32.057 |

All arms have lower mean target error at c3 than c1 on these same examples.
These subgroup means are descriptive; the summary does not give paired
bandwidth intervals or establish population effects.

## Manuscript consequences and next step

Separate three findings: supplied-direction restatement, usefulness to a
receiving guesser, and magnitude/stopping control. Four-shot oracle-assisted
restatement can be faithful without producing the best receiving accuracy.
The broad claim that models can follow feedback but cannot generate it must
remain restricted to tested prompts and protocols. This new run does not test
unaided teacher geometry or reproduce the historical teacher table.

The current planned GPU package is complete. Next run the CPU-only message
audit to partition literal message equivalence and restricted-zero-shot
additions; this does not change primary scores or require model calls:

```bash
git pull --ff-only origin refactor/quantifier-calibration
uv run python scripts/inspect_teacher_receiver.py --run "$RECEIVER_RUN"
cat "$RECEIVER_RUN/reports/receiver_message_audit.md"
```

Group labels are frozen lexical diagnostics, not semantic ground truth for
natural comparisons. The audit records paired error contributions, exact
prompt/output equivalence, and whether added primitive directions are among
all threshold-qualified oracle candidates. Subgroups overlap and are
exploratory; their differences are not randomized causal effects. Original
reports, frozen messages and response checkpoints remain intact. Then
consolidate tables/figures and revise the paper before scheduling further GPU
experiments. Crowdsourced-target ambiguity and unaided teacher capabilities
remain explicit scope limits, not resolved by this supplied-start study.
