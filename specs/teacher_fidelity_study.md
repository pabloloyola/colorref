# Matched oracle-assisted teacher fidelity

## Question and scope

Machel's review asks whether the low oracle-assisted teacher precision reflects
the evaluated paraphrase prompt rather than a general teacher capability gap.
This experiment first isolates **restatement of supplied correct directions**.
It does not yet test unaided geometric feedback generation or run a receiving
guesser. Use the teacher-fidelity results to choose the subsequent matched
teacher-to-guesser experiment; do not substitute these scores for color error.

| Condition | Wording instructions | Demonstrations |
|---|---|---:|
| natural_0 | Archived natural-paraphrase prompt | 0 |
| natural_4 | Same natural-paraphrase prompt | 4 |
| restricted_0 | Exact supplied primitive directions; canonical sentence | 0 |
| restricted_4 | Same restricted prompt | 4 |

The natural template is the existing
`configs/prompts/llm_teacher_oracle_assisted.txt`, including its warmer/cooler
and gray/less-gray vocabulary. The comparator is
`configs/prompts/teacher_fidelity_restricted.txt`. Natural zero-shot prompts
have no appended instruction edits. Restricted prompting changes both the
direction-preservation instructions and allowed output language/format: it is
a prompting intervention, not an isolation of one individual instruction.

## Frozen inputs and matched states

The parent is the completed shared-start run:

```
runs/20261007_043619_593902_shared_start_interface_study_a100_40gb
```

The runner validates its frozen configuration and plan; it uses the assigned
HEX-derived initial displayed states, not later model-generated revisions.
No parent output parsing/performance chooses evaluation membership. Target
LAB/HSV is recomputed from target HEX. Every condition sees the same description,
target HEX, guess HEX and supplied oracle directions for a given case.

The primitive oracle is the existing `_compute_candidate_deltas` policy:
LAB lightness/red-green/yellow-blue plus HSV saturation, with the parent's
thresholds and normalized ranking. Two bandwidths supply up to one or three
directions. The clause budget is respectively one or three, always at least
the supplied count. When fewer directions pass the thresholds, retain the
actual count; do not pad. Do not conflate an added valid-but-unsupplied
direction with a geometric sign error.

A seed-59 input-only split selects one distinct nonempty demonstration per
semantic regime, four in total. Selection uses neither teacher responses nor
their performance. Evaluation excludes these IDs and any normalized matching
description or identical target/guess HEX pair. Cases with no oracle constraint
are recorded as input exclusions, not silently replaced. Evaluation must
retain at least one example per regime; otherwise preparation stops.

The same four demonstrations and order appear in both few-shot conditions.
Their correct answers are deterministic canonical oracle sentences. A c1
prompt demonstrates c1 answers and a c3 prompt demonstrates c3 answers.
Direction coverage is explicitly logged; four demonstrations need not cover
every primitive direction. All generations use a fresh context, with the
demonstrations present only within that prompt.

With the 64-example parent, four demonstration exclusions and no additional
overlap/empty-set exclusions, evaluation contains 60 examples, 120 matched
bandwidth cases, and **480 teacher generations**. The dry-run reports actual
counts and exclusions rather than assuming those numbers.

## Model and execution

Inherit the parent's Qwen/Qwen3-14B HF-transformers model/backend, A100-compatible
bfloat16/device-map settings, temperature zero and thinking-disabled settings.
All four conditions have **80 output tokens**, matching the archived teacher
budget; few-shot input prompts are necessarily longer. Save input/output token
counts and observed finish/EOS/budget diagnostics. One model instance is loaded
per invocation, never separate teacher and guesser instances simultaneously.

Freeze configuration, templates, rendered prompts, split, oracle directions and
a self-contained parent snapshot before querying the model. Hash and reproduce
the frozen plan on resume. Check the observed model revision against the first
invocation and, when available, the parent's recorded revision. If parent model
revision is unavailable, do not claim verified identity with a historical run.

Each response is atomically checkpointed. Empty or malformed feedback is a
completed output, retained in denominators and not regenerated. Backend errors
remain pending for resume; no fallback feedback is inserted. Unknown checkpoints,
tampered scores, changed frozen plans and observed model-revision changes stop
execution. A run lock prevents concurrent writes. CPU report-only mode does not
load a model or modify checkpoints/configuration/calibration.

## Measures and interpretive safeguards

Save raw prompts, required and all geometrically valid oracle directions,
responses, model/finish/token metadata, and:

- Word-boundary primitive/synonym direction detection and supplied-set equality.
- Conservative preservation: exact detected set, nonempty output, no duplicate
  direction mentions or audit flags. This is a finite-vocabulary certification,
  **not proof of semantic correctness**; uncertified outputs are not automatically
  wrong. Ambiguous natural wording must be reviewed.
- Negation/scope, broad warmer/cooler/gray vocabulary, numeric/HEX content, and
  unrecognized wording flags; retain manual-review candidates in the JSON.
- Omissions, additions, reversals on supplied axes, contradictory signs,
  duplicate mentions, and direction-mention count versus budget.
- Magnitude modifiers separately; they do not automatically invalidate a
  natural direction-preserving sentence but violate the restricted grammar.
- Exact canonical-format compliance, a restricted-output diagnostic rather
  than a standalone fair ranking of natural paraphrases.
- Recognized-direction geometric precision against all threshold-qualified
  oracle candidates, with its recognized-output denominator. Preserve the
  archived keyword detector's precision separately for comparison; neither
  keyword precision resolves negation or broad-vocabulary meaning.

Report completion and pending counts by condition/bandwidth, observed score
counts, token cost, and paired conservative-preservation effects for few-shot
versus zero-shot within each form and restricted versus natural within each
shot count. Primary paired effects use completed common quartets; available
pairs are completion sensitivity. Empty/ambiguous outputs remain as observed
uncertified responses, not excluded parsing failures.

Paired percentile intervals resample whole examples within semantic regimes,
keeping both bandwidths together and preserving observed pooled case weights.
They condition on the fixed split and observed completed cohorts, do not
measure generation randomness, remove pending-work selection effects or prove
population generalization, and are not multiplicity-adjusted. Singleton strata
have no bootstrap variation. Keep raw text for manual adjudication before
attributing low conservative certification to wrong teacher semantics.

## Commands: dry-run, eight-response smoke, resume

From the GPU repository root on `refactor/quantifier-calibration`:

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/run_teacher_fidelity_study.py \
  --parent-run runs/20261007_043619_593902_shared_start_interface_study_a100_40gb \
  --dry-run
```

Check actual evaluation counts, split exclusions, demonstration direction
coverage, model settings and the clause-budget check. The dry-run does not
create a teacher run or load a model.

Start the frozen full plan but generate only eight responses:

```bash
uv run python scripts/run_teacher_fidelity_study.py \
  --parent-run runs/20261007_043619_593902_shared_start_interface_study_a100_40gb \
  --limit 8
```

The terminal logs the new run directory. Capture it explicitly; do not confuse
the parent or an older pilot with the new teacher run. For convenience when
only one such run has just been created:

```bash
TEACHER_RUN=$(find runs -maxdepth 1 -type d \
  -name '*_teacher_fidelity_a100_40gb' | sort | tail -1)

cat "$TEACHER_RUN/reports/teacher_summary.md"
```

After inspecting that smoke, resume the **same** frozen run:

```bash
uv run python scripts/run_teacher_fidelity_study.py --resume "$TEACHER_RUN"
```

CPU-only reanalysis:

```bash
uv run python scripts/run_teacher_fidelity_study.py --report-only "$TEACHER_RUN"
```

Outputs are `reports/teacher_summary.md`, `metrics/teacher_analysis.json`,
frozen `inputs/plan.json` / `inputs/parent_snapshot.json`, and individual
`raw_outputs/responses/*.json` checkpoints. No new dataset download is needed
when the saved shared-start parent folder is present.

## Next stage after this evidence

Manually audit flagged natural responses, then evaluate teacher-feedback
conditions in matched receiving-guesser revisions with a deterministic oracle
baseline. That stage must preserve shared starts and feedback budgets, retain
teacher/output failures, and distinguish restatement fidelity from unaided
feedback generation. No teacher-side performance claim is supplied by the CPU
simulations used to validate this implementation.
