# Held-out magnitude-control pilot — protocol draft

This is a specified follow-up, not an implemented runner or a completed model
experiment. First run the CPU stopping replay on the completed shared-start
study; its results will distinguish loss after reached convergence from errors
that remain above threshold. Preserve the existing forced-round results.

## Question and scope

Can an oracle choose a graded magnitude phrase that improves target localization
over an unmodified direction instruction, once coordinate direction conventions
are explicit? Test Qwen/Qwen3-14B on the A100 40 GB with direct LAB output and
the axis legend. Initial trials use one L/a/b direction at a time. This measures
behavior in a controlled color-adjustment interface, not yet a creative editing
application or a few-shot teacher's ability to generate feedback.

Avoid transferring the existing quantifier medians directly into the reference
game: its prompts, descriptions, and simultaneous corrections differ. Fit and
evaluate the controller under the same new frozen receiving prompt. The old
quantifier experiment motivates the phrase ladder, but is not evidence of
transfer calibration.

## Calibration and evaluation separation

- Generate a seeded candidate pool of displayed sRGB starting colors with stable
  IDs, retaining the generator seed, conversion convention and inclusion rules.
- Use 12 calibration colors and 12 distinct evaluation colors for a small pilot;
  no identical HEX/RGB starts across splits. Exclude the 12 anchors from the
  existing quantifier study and the inspected `dull toy red` case from evaluation
  tuning. Freeze the splits before querying the model.
- Match the fixed axis-legend adjustment prompt across stages. Omit color-name
  descriptions initially so vocabulary re-anchoring cannot dominate the result.
  Add descriptions and multi-axis reference games in a later transfer study.
- Record all feasibility exclusions before model inference, with counts by
  direction and target distance. Do not filter generated outputs by projection
  error or choose evaluation cases after observing responses.

Calibration asks each starting color to follow six LAB directions with bare,
`a little`, `somewhat`, and `much` wording: at most **12 × 6 × 4 = 288 calls**.
Fit per-direction median signed movement from the graded responses; keep
direction failures, parsing failures, off-axis drift and projected movement in
the calibration report. Require a positive usable median for a phrase to be a
candidate; label a direction with no usable phrase rather than supplying an
invented default mapping. Do not assign the bare instruction an ordinal rank.

The primary controller mapping should use displayed-state signed-axis movement,
because the task's perceptual output is displayed sRGB. Retain the native LAB
mapping as a diagnostic. Phrase ordering need not be perfect; select the usable
phrase whose calibrated median is nearest the absolute requested-axis residual,
with deterministic ties favoring the smaller median and then a fixed phrase
order. Store the fitted table, sample counts, model/prompt digest and tie rule.

## Matched held-out evaluation

Construct targets along one LAB direction at requested distances 6, 12, and 24
units from each evaluation start. Use distances above the common stopping
threshold 5 so the pilot evaluates corrections rather than intentionally editing
already-converged inputs. These native candidate coordinates must be valid and
have round-trip displayed projection ΔE ≤ 1; check and freeze stimuli before
inference. This is a feasibility criterion for constructed stimuli, not an exact
sRGB-gamut proof and not a response filter. Display rounding means the final
target may have small non-axis components; record both the native candidate and
the projected target and derive directions/residuals from the displayed pair.

All conditions receive the same starting displayed color and hidden target.
Run each response in a fresh context under three conditions:

| Condition | Teacher correction | Role |
|---|---|---|
| Bare direction | Unmodified direction phrase | Current magnitude-unspecified baseline |
| Calibrated quantifier | One direction plus the phrase selected from calibration | Tests graded feedback as a control signal |
| Exact numeric | Explicit requested coordinate increment, other coordinates held fixed | Execution/encoding control with more precise information |

The numeric condition is an oracle precision control, not an information-matched
natural-language baseline. Direction counts can match while precision differs.
Record emitted text, constraint counts and token counts rather than claiming
equal information payload.

One-step evaluation costs at most **12 × 6 × 3 × 3 = 648 calls** before feasibility
exclusions, plus at most 288 calibration calls. The actual frozen plan must
state counts and coverage; do not silently fill missing bins with post hoc
easier cases. This is a pilot, so a smaller feasible plan can run if its missing
coverage is explicit. Use one model load per phase/invocation and per-response
checkpointing; no second teacher model is needed for a deterministic controller.

For this first pilot, the supplied start is fixed and only one revision is
generated. A shared target-threshold rule stops before correction if a
constructed displayed pair is unexpectedly within 5; count such cases as
zero-call assigned-state outcomes, not successful generated corrections.
Multi-turn comparisons follow only after the one-step pilot, with the same cap
and stopping rule across feedback policies.

## Measurements and analysis

Primary: paired displayed-target error after the first correction, calibrated
minus bare, on held-out cases. Also report parse rate and failures by condition,
absolute gain, signed movement, off-axis drift, projection cost, direction
following, and overshooting geometry. For nonzero ideal correction d and actual
update m, retain m/d and cosine alignment; improvement requires m < 2d cos θ.
Do not confuse sign satisfaction or quantifier monotonicity with localization.

Analyze exact numeric target error separately from color-name grounding. Native
expected numeric coordinates and their displayed target are both known, so
conversion cost can be separated from execution error.

Resample evaluation **starting colors** as clusters, retaining all their
directions, target distances and paired conditions. Do not treat 216 correlated
start/direction/distance cases as independent colors. Keep common parsed and
available paired cohorts explicit; interpret intervals as small fixed-pilot
uncertainty, not model/population generalization. Freeze analysis choices before
examining evaluation responses; no evaluation-guided phrase fitting or threshold
tuning.

## Saturation follow-up

`more muted` and `more saturated` concern HSV saturation in the present oracle.
They are not isolated LAB-axis directions and must not inherit the LAB-unit
phrase mapping. A separate calibration should vary S at fixed H/V, track both
S movement and induced LAB changes, include near-S=0/1 starts, and record gamut,
rounding and saturation headroom. Transfer the resulting mapping to mixed
lightness/saturation instructions only after evaluating each independently.

Stopping remains a target-known benchmark control; a deployed editor without
the target requires a separate stopping criterion. Machel's restricted wording
and zero-/few-shot teacher experiments and crowdsourced-target ambiguity audit
remain separate revision requirements.
