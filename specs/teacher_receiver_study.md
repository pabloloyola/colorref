# Matched teacher-feedback reception

This extension tests whether a guesser benefits from the original saved teacher
messages, including comparative feedback rejected by a lexical direction audit.
It does not fit or use semantic-review labels to select cases or repair messages.

## Frozen protocol

Parent: completed `teacher_fidelity_a100_40gb` run. Every planned teacher response
must be saved, including empty text; backend-pending runs cannot be used. All
teacher inputs and checkpoint scores are validated and snapshotted together.
The new run is self-contained after creation; moving the parent is permitted.

For each held-out example and c1/c3 budget, five receiving arms share the same
HEX start, target, description, oracle constraints and revision template:

| Arm | Feedback received |
|---|---|
| natural_0 | Original archived-prompt zero-shot teacher message |
| natural_4 | Original four-shot natural-prompt teacher message |
| restricted_0 | Original restricted zero-shot teacher message |
| restricted_4 | Original restricted four-shot teacher message |
| oracle | Canonical feedback from the supplied direction set |

Four teacher arms are frozen model outputs; the oracle arm costs no new teacher
generation. All original text, including Feedback labels and comparisons, is
passed unchanged. The inherited HEX revision template receives only the name,
current HEX and feedback. Target HEX/LAB, oracle direction JSON, teacher prompt
and review annotations are not appended. If a teacher itself mentions the
target HEX, that input is flagged and preserved rather than silently excluded.

The receiver uses the shared-start parent's Qwen3-14B configuration: HF
transformers, bfloat16, device_map auto, temperature zero, thinking disabled,
64 output tokens in the production parent. All arms use HEX outputs and one
fresh-context revision. The teacher generation budget of 80 tokens is not the
receiver budget. One model loads per invocation; no initial prediction or
teacher regeneration occurs. A recorded teacher-model revision is required
when available, and the first resolved receiver revision is checked on resume.
If the historical revision is unknown, the run does not invent it.

Sixty examples times two budgets times five arms yields **600 generations**.
Seed 61 shuffles arm order within each case; cases follow the frozen teacher
plan. A ten-response smoke covers one example at both budgets. It preserves
the full plan and is resumed in place. Fixed revisions include close starts;
there is no target-known early stop or retrospective best-state selection.

## Analysis

Primary target disagreement is Euclidean LAB distance after displaying HEX as
uint8 sRGB. Parsed HEX native/displayed states coincide. Gain is starting error
minus revised error. Oracle constraint satisfaction measures movement against
the supplied directions (including HSV saturation), not a lexical inference
of teacher intent. Alignment excludes zero-length movement or target vectors.
All close-start records are retained for drift inspection.

Completion reports retain all planned, pending, parsed and failed revisions.
Empty/malformed outputs are completed failures with no imputed color, repair
or retry. Backend errors are recorded as pending for resume. Primary accuracy
uses cases with all five arms parsed. Available-pair effects check sensitivity
to requiring all five outputs. Separate bandwidth summaries are exploratory.

Eight paired contrasts compare each teacher arm with the canonical oracle,
natural zero-shot with four-shot, restricted zero-shot with four-shot, and
natural with restricted wording at each demonstration count. Error deltas
are right minus left; gain differences have the opposite sign because starts
match. Percentile intervals use 2,000 regime-stratified whole-example cluster
draws, seed 13, keeping both budgets together and pooled case weighting.
One-example cohorts receive no interval; singleton strata have no variation.

This is one receiving revision on HEX-derived supplied starts, not a reproduction
of the historical teacher table, unaided teacher geometry, multi-turn convergence
or cross-model generalization. Intervals condition on observed parsed outputs;
they do not measure generation randomness, eliminate failure-selection bias,
provide multiplicity correction or establish population generalization. The
previous start/teacher-generation costs are separate from the 600-call receiver
budget. Simulated acceptance tests validate software, not model performance.

## Run step by step

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/run_teacher_receiver_study.py \
  --parent-run "$TEACHER_RUN" \
  --dry-run
```

Expected production plan: 60 examples, 120 cases, 600 generations, five arms,
HEX output, one revision, no semantic-label selection. Parent validation and
dry-run load no model and create no receiving experiment directory.

```bash
uv run python scripts/run_teacher_receiver_study.py \
  --parent-run "$TEACHER_RUN" \
  --limit 10

RECEIVER_RUN=$(find runs -maxdepth 1 -type d \
  -name '*_teacher_receiver_a100_40gb' | sort | tail -1)

cat "$RECEIVER_RUN/reports/receiver_summary.md"
```

After checking the smoke, resume that same directory:

```bash
uv run python scripts/run_teacher_receiver_study.py --resume "$RECEIVER_RUN"
```

CPU-only reanalysis:

```bash
uv run python scripts/run_teacher_receiver_study.py --report-only "$RECEIVER_RUN"
```

Outputs: frozen `config.yaml`, `inputs/plan.json`, `inputs/parent_snapshot.json`,
per-response `raw_outputs/responses/*.json`, invocation/model metadata,
`reports/receiver_summary.md`, and `metrics/receiver_analysis.json` containing
denominators, pairs, bandwidth summaries, failure prompts and close-start drift.
Original parent files and previously saved receiver responses are preserved.
