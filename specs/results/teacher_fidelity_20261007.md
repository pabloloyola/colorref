# Oracle-assisted teacher restatement and exploratory meaning audit

Production run: `20261007_134620_125917_teacher_fidelity_a100_40gb`.
Qwen/Qwen3-14B, HF transformers, temperature zero, thinking disabled,
80 output tokens; four frozen demonstrations and 60 held-out descriptions,
15 per regime. Both c1/c3 budgets and four conditions complete: 480/480,
120 matched quartets. No receiving-guesser responses were generated.

The supplied original `teacher_analysis.json` contains 262 raw diagnostic
outputs, not all 480 raw outputs. Its original selection excludes certified
canonical non-magnitude responses. Aggregate canonical counts reconcile with
the 218 omitted passes, but their raw text and paired identities are unavailable
in this export. They are explicitly labeled aggregate-only in the new audit.

## Why lexical precision cannot stand in for meaning

`Your guess is darker than the target color.` implies a lighter adjustment.
Likewise `Your guess is more muted than the target color.` implies increased
saturation. A keyword detector interprets the literal direction words as commands
and reverses their meaning in such comparisons. Some comparisons are genuinely
inconsistent with supplied directions, so reversing every detected word without
checking whole-sentence scope is also unsafe.

All 117 diagnostic `natural_4` outputs are explicit `Feedback: Make it ...`
corrections. The harmless label triggers the original unknown-word flag; the
other three outputs are aggregate canonical passes. All fifteen diagnostic
`restricted_4` outputs have the same label issue; 105 other outputs are aggregate
canonical passes. Both four-shot conditions preserve the supplied direction set
in all 120 cases under the exploratory finite grammar and aggregate reconciliation.

## Supplementary finite-grammar audit

The grammar resolves whole `Make it ...` instructions and explicit
`Your guess is ... than/compared to the target color` comparisons. It supports
primitive directions, declared synonyms, and less-red/green/yellow/blue/muted
comparatives. It reverses comparisons before consulting the required answer,
ignores a single leading Feedback label, and leaves mixed or unknown wording
unresolved. This grammar was developed after inspecting the pilot and is
exploratory. It does not replace the frozen lexical score.

| Condition | Budget | Resolved exact-set matches | Resolved mismatches | Needs manual review | Total |
|---|---:|---:|---:|---:|---:|
| natural_0 | 1 | 52 | 1 | 7 | 60 |
| natural_0 | 3 | 29 | 16 | 15 | 60 |
| natural_4 | 1 | 60 | 0 | 0 | 60 |
| natural_4 | 3 | 60 | 0 | 0 | 60 |
| restricted_0 | 1 | 48 | 12 | 0 | 60 |
| restricted_0 | 3 | 56 | 4 | 0 | 60 |
| restricted_4 | 1 | 60 | 0 | 0 | 60 |
| restricted_4 | 3 | 60 | 0 | 0 | 60 |

Thus natural zero-shot has 81 resolved matches, 17 resolved mismatches and 22
unresolved cases; unresolved is not semantically wrong. Some unresolved outputs
are clearly useful, such as `Your guess is too dark; try making it lighter.`
Others mix reference frames, introduce objects, omit an explicit target relation,
or use broader vocabulary. These remain visible for manual review rather than
being silently interpreted from the expected answer.

Restricted zero-shot contains the required directions but adds unsupplied ones
in sixteen outputs. Twelve c1 messages exceed that direction budget. Three c3
messages exceed the maximum budget and a fourth adds a third direction to a
two-direction supplied set. Some added directions are geometrically valid;
exact restatement fidelity and geometric validity are different quantities.

## Consequences for manuscript claims

The original natural_0 recognized precisions (0.117 at c1, 0.417 at c3) are
keyword diagnostics, not estimates of semantic directional correctness. The
certified-preservation contrasts are also affected by harmless label formatting.
They must not be presented as teacher-capability comparisons without scope-aware
review. Four examples produce explicit faithful correction wording in this
oracle-assisted task, despite incomplete demonstration direction coverage.

This establishes a failure mode of lexical evaluation in this new matched
pilot. It does not establish that the original paper's teacher-table result is
entirely an artifact: historical run provenance and raw outputs are still needed.
Nor does it test unaided teacher geometry, receiving-guesser response to
comparisons, arbitrary natural language, population generalization, or magnitude
calibration. Do not replace the broad following-versus-generating claim with
another broad claim that teachers are reliable. Next: validate the supplementary
audit against all checkpoints, review the 22 unresolved messages, then compare
guesser revisions receiving original teacher messages and a canonical oracle
from identical starting states.

## CPU-only commands

```bash
git pull --ff-only origin refactor/quantifier-calibration
uv run python scripts/inspect_teacher_semantics.py --run "$TEACHER_RUN"
cat "$TEACHER_RUN/reports/teacher_semantic_audit.md"
```

The script validates the frozen run and checkpoint scores. It writes only
`reports/teacher_semantic_audit.md` and `metrics/teacher_semantic_audit.json`.
Original summaries, raw outputs, prompts, plans, demonstrations and scores are
preserved. No model loads, inference, repair or demonstration reselection occurs.
Full-checkpoint results should reconcile with this diagnostic-export audit.
