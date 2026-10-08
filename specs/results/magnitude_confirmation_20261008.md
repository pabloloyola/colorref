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
## Completed saved-output subgroup audit (author report)

Common quartets reproduce −5.497 [−5.786, −5.203]. Wins/ties/losses:
556/1,419/123 at 0.01 tolerance; median paired difference zero.
Requested-distance contrasts: 6 units −0.708 [−0.798, −0.613];
12 units 0.000 [0.000,0.000]; 24 units −18.352 [−19.765,−17.009].
Approximately 95% of the pooled summed reduction is contributed by the
24-unit stratum (calculated from rounded subgroup counts and means).
This is descriptive, not a causal decomposition.

Largest direction/distance contrasts: red/24 −39.449, yellow/24 −25.126,
blue/24 −33.552. Darker cases and all 12-unit cases tie exactly in error;
phrase/prompt identity remains to be checked from saved records before
interpreting those as identical interventions.

Harmful updates: unfitted 318/2,098, calibrated 58/2,098. All displayed
per-start average deltas are negative; one is only −0.002 (within the
exploratory tie tolerance). Leave-one-start-out means span −5.528 to −5.459.
Individual cases do not all improve. Subgroup intervals are exploratory,
not multiplicity adjusted; repeated targets share starting colors.

Numeric control: 2,106 parsed responses, 2 parse failures; 2,035 native
errors ≤0.01, 2,067 ≤1, 39 >1. Native error mean/median/p95/max:
0.296/0.000/0.001/51.004. Largest ten misses include large positive
requested-coordinate deviations; these do not reveal an internal mechanism.
Misses remain included. Source: author attachment `Pasted text(8).txt`.

Next CPU-only check: `scripts/audit_magnitude_identity.py`. No new inference,
prompt replacement, controller refitting, case selection or primary analysis
change is required.

## Completed identity audit (author report)

Among 2,108 planned pairs, 1,386 have identical selected wording and prompts.
Available parsed pairs: 2,103; identical native LAB 1,416; identical displayed
HEX 1,419. No parsed prompt-identical pair has differing native LAB.
On the primary common-quartet cohort, 1,385 prompt-identical cases tie exactly;
713 prompt-different cases have mean calibrated minus unfitted error
−16.175041, with 556 wins, 34 ties and 123 losses. Their composition is
post hoc; this is not a replacement primary contrast or independent experiment.

Every 12-unit case and every darker case has identical prompts. Policy changes
are lighter/red/green at 6 units (a_little → somewhat), and red/yellow/blue
at 24 units (much → somewhat). The latter avoids the excessively large
displayed steps induced by much in this model/prompt. Magnitude selection can
choose a verbally weaker term for a larger chromatic correction because phrase
responses are direction-dependent. It does not imply that somewhat has a
universal 24-unit meaning or that all large corrections are solved.

The first report printed 1,385/0 under the boolean Same prompt column due to
a dictionary-key collision between the grouping label and count. The code
now keeps the label as prompt_identical; subgroup membership, effects, counts,
saved responses, controller and primary report are unchanged.
