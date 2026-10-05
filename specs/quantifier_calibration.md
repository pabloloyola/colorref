# Quantifier calibration

This pilot isolates operational semantics of graded color instructions from
color-name grounding.

For a known CIELAB state, the model receives one of:

- Make it lighter.
- Make it a little lighter.
- Make it somewhat lighter.
- Make it much lighter.

The same ladder is evaluated for darker, more red, more green, more yellow, and
more blue. The model returns a native LAB state. We measure signed movement
along the requested axis, orthogonal drift, direction-following rate, and
within-trajectory monotonicity across a_little < somewhat < much. The
unmodified instruction is a comparison condition with no ordinal rank.
Nondecreasing comparisons include ties; strictly increasing comparisons are
reported separately. Zero steps and wrong-direction steps are distinguished.

The pilot uses two LAB anchors, six directions, and four wording conditions:
48 calls with Qwen3-14B on an A100 40 GB. It is a calibration study, not a
reference-game result. A later experiment can use the estimated quantifier
mapping to choose feedback wording as a function of remaining target distance.

## Reanalyze saved trials without the GPU

    uv run python scripts/run_quantifier_calibration.py --report-only runs/YOUR_RUN

This reads the saved configuration and raw response records, updates only the
Markdown report, and does not load the model or generate new responses.
Archived baseline rank 0 is ignored when scoring quantifier monotonicity.
The report also shows signed steps by starting color and direction, zero versus
wrong-direction counts, off-axis drift, raw nonpositive responses, and projection
diagnostics. These are pilot measurements, not established calibration constants.

## Matched axis-convention diagnostic

    uv run python scripts/run_quantifier_calibration.py --config configs/experiments/quantifier_calibration_a100_40gb_axis_legend.yaml

This second 48-call pilot adds only a LAB axis-convention legend to the original
prompt. Starting colors, directions, wording conditions, model settings, output
format, and metrics match the original pilot. The legend specifies the signs of
L, a, and b but gives no numerical step sizes or examples. There is no additional
instruction to preserve the other coordinates.

Compare direction following, nonpositive responses, strict quantifier ordering,
off-axis drift, and projection error against the original run. Improved axis
following with retained magnitude ordering would support the hypothesis that
some original failures arose from coordinate interpretation. Persistent errors
would warrant explicit numeric-axis instruction controls before treating the
magnitudes as a reliable control interface. This intervention diagnoses prompting
dependence; it does not establish unaided perceptual understanding.

The initial two-anchor pilot produced 33/36 nondecreasing magnitude pairs, with
27 strict increases and 6 ties. Its reported nonpositive responses show that all
green instructions changed b rather than a, and the warm anchor's quantified
blue instructions increased b rather than decreased it. These observations
motivate the axis legend. They should not be generalized beyond this pilot.
Nine of 48 outputs had LAB-to-sRGB projection error above 1, so the native LAB
results also require gamut diagnostics before claiming practical color editing
performance.
