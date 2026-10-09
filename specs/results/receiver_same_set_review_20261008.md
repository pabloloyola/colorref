# Changed same-set receiver messages — 2026-10-08

Evidence: author's complete console export of `inspect_teacher_receiver.py`,
attached as Pasted text(7).txt. Run: 20261007_152230_242355_teacher_receiver_a100_40gb.
No new inference, repair, endpoint selection or score recalculation.

All six pairs are parsed restricted_0 c3 cases. Differences are teacher minus
canonical oracle displayed target Delta E; negative favors the teacher arm.

| Example | Change | Teacher response | Oracle response | Error difference |
|---|---|---|---|---:|
| 115362 | order | #b38686 | #d4af37 | -32.127 |
| 130695 | order | #9b8ccf | #b8a6c2 | -5.731 |
| 57135 | comma instead of and | #7A5C8C | #7A5C8C | 0.000 |
| 106870 | comma instead of and | #3a231e | #3a231f | 0.414 |
| 340456 | order | #C858C8 | #C850C8 | 3.412 |
| 52032 | order | #003366 | #006600 | -92.008 |

## Exact feedback pairs

115362 and 130695:
- Teacher: Make it lighter, more yellow, and more muted.
- Oracle: Make it more yellow, more muted, and lighter.

57135:
- Teacher: Make it more muted, more blue.
- Oracle: Make it more muted and more blue.

106870:
- Teacher: Make it darker, more blue.
- Oracle: Make it darker and more blue.

340456:
- Teacher: Make it lighter, more red, and more blue.
- Oracle: Make it more blue, more red, and lighter.

52032:
- Teacher: Make it darker, more green, and more yellow.
- Oracle: Make it more yellow, more green, and darker.

## Interpretation

Four reorderings yield three wins and one loss; two connective changes yield
one tie and one loss. Sum of displayed differences is -126.040, matching the
earlier group result. Case 52032 contributes 73.0% of this group's net
advantage (not of the whole restricted_0 arm's advantage).
Equivalent direction sets can produce different updates through surface form,
and the aggregate benefit is concentrated. There is no consistent superiority
claim for teacher wording or an identified internal mechanism. This is an
exploratory post-hoc inspection with overlapping example cohorts; it is not a
systematic randomized permutation study or a population estimate.

The full arm also has sixteen messages with additions, so its comparison to
the oracle is not uniformly information matched. Fidelity, target usefulness
and information budget remain distinct. No additional GPU study is needed
to support this descriptive qualification.

## Remaining historical evidence gate

Recover metadata from original May runs or archived report exports before
assigning denominators/backend settings to historical numerical tables.
Required for each retained result: actual completed example count and IDs,
input/subset identity, frozen config, model/revision/backend/dtype, prompts,
round and stopping settings, and result-file linkage. A planned config alone
does not certify the table's realized run. Source conflicts are documented in
`content_source_audit_20261008.md`. If original metadata is unavailable,
quarantine unresolved diagnostics in the author draft or replace them with
explicitly planned reproductions; do not silently guess counts or rerun the
entire old package. The new matched studies retain independent provenance.
