# Fresh 1,000-description grounding replication — completed

Evidence: author-supplied `grounding_summary.md` from
`20261008_022100_355058_grounding_1000_a100_40gb`. Machine-side raw checkpoints,
plans and full metric JSON have not been independently downloaded here.

All 1,000 games and 4,000 generated responses complete; all 1,000 paired
trajectories parse, with zero failures. Qwen3-14B, HF Transformers BF16 on
A100 40GB, pinned configured revision 40c069824f4251a91eefaf281ebe4c544efd3e18,
thinking off, temperature zero, 64 output tokens, HEX output. At most three
deterministic oracle constraints per correction; exactly three revisions,
including close starts. Fresh context, latest feedback only.

250 descriptions per regime, seed 113, excluding every debug_400 ID. Frozen
taxonomy SHA256: 8de973e5a98aac179f03c95dfc355f250b8a47f0f3c082fe9833324df699ae46.
Exclusion SHA256: c13e9e05c477f9eb0dfe7ac0c3f2843491d1fd8cef0b913aac2dc40070562acd.
Subset SHA256: 034bf499be19fa2de52a7826e0d7faf3be369da7403e48ef8a1f8d47aad18f1f.

| Quantity | Mean Delta E | 95% percentile interval |
|---|---:|---|
| Initial (also one-shot baseline) | 42.332 | [40.696, 44.014] |
| Final | 22.147 | [21.284, 22.986] |
| Paired initial-minus-final gain | 20.185 | [18.611, 21.785] |

Initial/final convergence <=5: 5/1,000 and 38/1,000. The reduction of mean
error is about 47.7%; this is not mean per-example relative improvement.

| Regime | N | Initial | Final | Gain |
|---|---:|---:|---:|---:|
| explicit_grounded | 250 | 36.410 | 22.020 | 14.389 |
| prototype_mediated | 250 | 43.393 | 22.412 | 20.981 |
| compound_associative | 250 | 37.887 | 20.643 | 17.244 |
| abstract_idiosyncratic | 250 | 51.638 | 23.513 | 28.125 |

Reported pooled gain and per-regime displayed means can differ in the last
decimal under rounding. Regime comparisons are descriptive: larger absolute
gain on abstract descriptions also accompanies larger initial disagreement,
and does not establish a unique semantic target or an independently tested
between-regime effect.

Mean saved generation latency: 0.334s across 4,000 known responses; this
excludes load, reports/checkpoint overhead and unsaved backend errors. The
first 100 responses were timed and then resumed without replacement.

Whole-description bootstrap resamples within regimes. Equal-regime weights
do not estimate corpus-frequency performance. Extra information and correction
opportunities differ from one-shot; this result does not isolate adaptive
interaction from a matched information budget. It does not rerun the historical
12k protocol or establish global geometry improvement, human agreement, other
models or deployable model-only stopping. Historical outputs are unrecoverable.
