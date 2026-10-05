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
within-trajectory monotonicity across quantifier ranks.

The pilot uses two LAB anchors, six directions, and four quantifier levels:
48 calls with Qwen3-14B on an A100 40 GB. It is a calibration study, not a
reference-game result. A later experiment can use the estimated quantifier
mapping to choose feedback wording as a function of remaining target distance.
