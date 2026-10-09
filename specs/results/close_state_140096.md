# Close-state correction audit — example 140096

Source: the user's saved-case inspector output for shared-start run
`20261007_043619_593902_shared_start_interface_study_a100_40gb`, provided on
2026-10-07. The workspace read the supplied excerpt and checked the geometric
calculations; it has not independently read all production checkpoints.
This is one diagnostic case, not a prevalence estimate.

## Assigned target and feedback

- Description: `dull toy red`; regime: compound associative.
- Target: `#910d08`; starting displayed color: `#8b0000`.
- Starting LAB: (28.089771, 50.999677, 41.290790).
- Target LAB: (30.223299, 50.659926, 40.292123).
- Starting target distance: 2.380065 ΔE76, within the convergence threshold 5.
- All interfaces receive: **Make it more muted and lighter.**

The oracle directions are valid for the selected quantities: required lightness
change is +2.133529 and HSV saturation change is -0.055172 (1.0 → 0.944828).
These slightly exceed the oracle's L threshold 2.0 and S threshold 0.05.
The forced-round diagnostic continues despite the global target distance being
below 5. A rule that stops at the assigned-target convergence threshold would
retain this initial state; that is a protocol-specific counterfactual, not a
result from a new GPU intervention or a model-only stopping capability.

## First corrections

All displayed-state quantities below are calculated from the saved projected
uint8 sRGB states. Movement ratio divides total LAB movement by the starting
target distance; it is a geometric diagnostic, not a requested language scale.

| Interface | Raw output | L increase | S decrease | Total movement ΔE | Movement / remaining distance | New target error ΔE | Constraint satisfaction | Alignment |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| HEX | #A64D4D | 16.075 | 0.464 | 31.959 | 13.428 | 30.026 | 1.000 | 0.825 |
| Plain LAB | LAB(55.0, 20.0, 10.0) | 26.832 | 0.673 | 51.304 | 21.556 | 49.397 | 1.000 | 0.809 |
| Legend LAB | LAB(45.0, 25.0, 20.0) | 16.867 | 0.481 | 37.402 | 15.715 | 35.678 | 1.000 | 0.739 |

The selected constraints are satisfied: lightness increases and saturation
decreases. Their magnitudes greatly exceed the target discrepancies.
Positive directional alignment and perfect sign-based constraint satisfaction
therefore coexist with sharply increased target error. The phrase "more muted"
acts on HSV saturation and can change multiple LAB coordinates; do not label
all resulting a/b movement as irrelevant off-axis drift.

All first outputs parse successfully and end at EOS. Generated-token counts
are 8 for HEX and 20 for each LAB condition, below the 64-token limit.
Native-to-display projection error is 0 for HEX, 0.413158 for plain LAB, and
0.247531 for legend LAB. Neither truncation nor a large projection displacement
accounts for this first correction's error increase.

## Geometric check

Let d be the starting target distance, m the actual displayed-state movement,
and c its cosine alignment with the ideal target correction. Euclidean LAB
distance satisfies:

    error_after² = d² + m² - 2 d m c.

For a nonzero movement to improve error, m must be smaller than 2dc.
For these saved directions the upper bounds are 3.926841 ΔE for HEX,
3.853156 for plain LAB, and 3.519977 for legend LAB. Observed movements
31.958992, 51.303874, and 37.402158 exceed these bounds by a wide margin.
Substitution reproduces each saved first-revision error exactly to displayed
precision. This confirms an excessively large geometric update, while leaving
the model's internal cause unspecified.

## Later revisions

| Interface | Start | Revision 1 | Revision 2 | Revision 3 |
|---|---:|---:|---:|---:|
| HEX | 2.380 | 30.026 | 25.646 | 13.579 |
| Plain LAB | 2.380 | 49.397 | 33.251 | 22.703 |
| Legend LAB | 2.380 | 35.678 | 30.088 | 23.197 |

Later updates reduce error but none recovers the initial accuracy within the
three revisions. HEX's second response violates the darker constraint while
satisfying the other two; the error nevertheless decreases. Consequently,
sign compliance and target-distance gain are distinct measurements in both
directions: compliance need not improve error, and improvement need not satisfy
every selected sign constraint.

## Revision implication and next controls

Copy-ready draft observation:

> A near-target case illustrates the distinction between direction following
> and magnitude control. Starting 2.38 ΔE76 from the assigned target, all three
> interfaces satisfy the oracle's requests for increased lightness and reduced
> saturation, but move 31.96–51.30 ΔE76 and increase target error. The valid,
> normally terminated outputs show that correct-direction updates can still be
> excessively large. This case is drawn from a forced-round diagnostic; stopping
> at the existing target-distance threshold would preserve its initial guess.

This directly motivates testing graded corrections without claiming that
"a little" already fixes the case. The current oracle conveys direction and
feedback count, not intended step size. The axis legend specifies L/a/b
direction conventions and does not specify lightness or saturation magnitudes.
The observed failure is consistent with magnitude miscalibration; description
re-anchoring and multi-constraint interactions remain possible contributors.

Priorities:

1. Reanalyze all saved shared-start trajectories under the existing target-based
   stopping threshold to quantify this benchmark stopping diagnostic. It needs
   no new generations. Retain fixed-round results separately and acknowledge
   that the target-known stopping rule is a benchmark oracle.
2. Develop a held-out magnitude-control pilot using the well-defined LAB-axis
   directions, identical starts, feedback counts, and a matched stopping rule.
   Fit wording-to-step behavior on calibration examples separate from evaluated
   examples. Compare unmodified wording with magnitude-aware wording and exact
   numeric steps as an execution control. Preserve per-case raw responses.
3. Calibrate "muted/saturated" separately before applying that controller to the
   existing four-axis oracle: HSV saturation is not one of the six isolated
   LAB-axis directions in the current quantifier study. Do not borrow a LAB-unit
   quantifier mapping as if it were an HSV saturation mapping.
4. Run the planned direction-preserving × zero-/few-shot teacher controls;
   this deterministic-oracle case does not resolve Machel's teacher-prompt
   concerns or establish a general teacher capability gap.

Do not change the completed experiment's prompts, checkpoints, or parsing to
remove this case. It explains a possible failure mode and motivates a distinct
intervention, rather than proving a downstream creative-application benefit.
