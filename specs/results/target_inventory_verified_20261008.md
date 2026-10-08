# Production target inventory — 2026-10-08

Evidence: author-supplied console outputs from `scripts/audit_target_multiplicity.py`
on the GPU host, after downloading the archived dataset from
`paablo111/colorref-data`. These are inventories, not new model generations.
The full machine-side JSON reports remain in `reports/content_audit/`;
they were not independently downloaded into this workspace.

| Quantity | Retained taxonomy | Raw English source |
|---|---:|---:|
| Rows / valid name-color rows | 518,830 | 705,869 |
| Distinct exact descriptions | 518,830 | 705,869 |
| Distinct normalized descriptions | 518,830 | 705,869 |
| Repeated description groups | 0 | 0 |
| Multiple-color description groups | 0 | 0 |
| Exact name-color duplicates beyond first | 0 | 0 |
| Invalid name / color rows | 0 / 0 | 0 / 0 |

Normalization lowercases and collapses whitespace; it does not strip
punctuation or identify synonymous descriptions.

## Filter boundary and corpus labels

All 518,830 retained rows have finite scores >=0.75. Exactly 43,187 are at
0.75; only 475,643 satisfy >0.75. The revised manuscript now states >=0.75.
The dataset, subsets and model outputs are unchanged.

| Regime | Retained rows |
|---|---:|
| abstract_idiosyncratic | 238,416 |
| prototype_mediated | 137,420 |
| compound_associative | 94,246 |
| explicit_grounded | 48,748 |

## Evaluation-record inventory

725,203 records have 725,203 distinct exact descriptions. There are no
duplicate exact-description rows, repeated-description groups, or repeated
descriptions with distinct scores. Thus the builder's last-occurrence lookup
does not encounter exact-description collisions in this archived file.
Fields: `description`, `detected_language`, `language_match`, `reasonING`,
`reasoning`, `score`. No explicit vote counts or alternative-color fields
appear. Field names alone do not establish who scored the records or whether
reasoning text contains other useful information.

## Input provenance

| File | SHA256 |
|---|---|
| colornames_taxonomy.parquet | 8de973e5a98aac179f03c95dfc355f250b8a47f0f3c082fe9833324df699ae46 |
| dataset_colornames_source.json | ee03b587d10b996471ae2c2bef88e1c3728ab22eed83067a907b42f20b8d9b50 |
| colornames_evaluations.json | 50ddd69f3ae9ce3f6409ad1d16bdb486cfc58a25df76e731f5f9918d141e81d9 |

## Manuscript consequences and limits

There is no recorded target multiplicity with which to estimate acceptable
color variation or inter-speaker agreement. This does not show that names
are unambiguous. Delta E measures disagreement with the recorded target;
description validity does not certify target uniqueness. Human alternative
color judgments would require separate collection. Controlled supplied-color
magnitude experiments address instruction execution, not this ambiguity.
No GPU rerun or retrospective filtering is warranted by this audit.

Historical diagnostic denominators/backend provenance and the six changed
same-lexical-set teacher messages remain separate pending checks.
