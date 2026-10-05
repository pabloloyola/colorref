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
