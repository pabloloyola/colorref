# Four-arm magnitude confirmation — author-provided completed report

Run: `20261008_030403_354222_magnitude_confirmation_128_a100_40gb`.
Source: completed machine report pasted by the author on 2026-10-08;
raw response files have not been independently downloaded here.

Calibration: 32 colors, 768 completed responses, 767 parsed. Held-out:
128 distinct starting colors, 2,108 frozen feasible cases, 196 input-only
feasibility exclusions. All four arms completed 2,108 generations, no pending
responses or unavailable mappings. Parse failures: bare 3, unfitted 5,
calibrated 0, numeric 2. Common parsed quartets: 2,098, covering all 128 starts.

| Arm | Common-cohort mean displayed target ΔE |
|---|---:|
| bare | 11.910 |
| unfitted | 12.357 |
| calibrated | 6.860 |
| numeric | 0.346 |

Primary calibrated minus unfitted: −5.497 [−5.786, −5.203]; available
pairs: 2,103, −5.528 [−5.814, −5.245]. Bare-to-unfitted: +0.447
[−0.690, 1.516]. Bare-to-calibrated: −5.050 [−6.102, −4.074].
Intervals resample whole starting colors with pooled case weights.
The 44.5% reduction is a ratio of common-cohort means, not the mean of
case-relative improvements. Conditions within a color are not independent colors.

All-parsed diagnostics (different denominators): unfitted direction follow
0.990, calibrated 0.999; projection ΔE 7.722 versus 1.043; off-axis drift
2.240 versus 0.551. These differences do not identify a causal mechanism.
Numeric mean native execution error 0.296; displayed execution error 0.297;
instructed-result disagreement with displayed target 0.072.

The result supports this receiver-calibration policy over the fixed cutpoint
rule [9,18], for this model, prompt, RGB sampling range and one-revision task.
It does not prove all unfitted policies inferior, human perceptual magnitude
calibration, model-family generalization or creative image-editing effectiveness.
Direction/distance subgroup and numeric-tail audits are next, CPU-only.
