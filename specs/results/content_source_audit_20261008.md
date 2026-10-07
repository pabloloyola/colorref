# Content source audit — 2026-10-08

Inspected repository snapshot: `714d65f623f676ee3982ade52a4ba590d3386652`,
original/revised manuscript sources, uploaded teacher diagnostic JSON, and
author-supplied completed reports. This is a source/availability audit, not a
production dataset or original-run recomputation.

## 1. Original experiment metadata is internally inconsistent

| Archive evidence | What it establishes | What it does not establish |
|---|---|---|
| Original Phase 2 says main_1000; its bandwidth-table caption says main_4000. The information-budget and convergence captions also say main_4000. | The supplied manuscript contradicts itself about diagnostic subsets. | Which subset actually produced the numerical rows. |
| Checked bandwidth, budget, convergence, and 8B configs point to main_1000. Separate c3 14B scale-up configs point to main_4000. | Planned subset paths in this source snapshot. | Actual run counts, exact file contents at execution, or later overrides. |
| May-20 HANDOFF explicitly lists 1,000 examples for convergence and budget conditions. | Contemporaneous evidence supports 1k for those listed runs. | That every manuscript table uses those same runs. |
| The archived teacher configs point to debug_400, while the supplied manuscript says debug_4000. | Historical teacher cohort provenance is unresolved. | A verified 4k teacher result or a reproduced DP=0.11. |
| Checked YAML uses HF Transformers/bfloat16; HANDOFF describes vLLM/fp16. | Backend/dtype descriptions also need reconciliation. | Actual model-loading settings for a historical table. |
| The subset builder accepts arbitrary --sizes but defaults to 400/1,000/4,000; no 12k config is in the checked archive. | The archive is incomplete for reproducing the claimed 12k run directly. | That the author-reported 12k results are false or were never run. |

Do not assign final denominators/backend identities by matching values or
filenames alone. Preserve original files. Recover frozen configs, metadata,
input hashes and observed completion counts for table-producing runs; otherwise
quarantine unresolved diagnostic tables during author review. The 12k results
remain explicitly inherited author-reported baseline evidence, not a new
independently reproduced result.

## 2. The dataset builder preserves target multiplicity but not agreement fields

`scripts/build_dataset.py` loops over every English source entry and does not
deduplicate identical names or name/color pairs. Its output retains name, HEX,
RGB/LAB/HSV and a description quality score. `build_canonical.py` lowercases and
collapses whitespace for normalized_name, preserves raw_name and HEX, and also
does not deduplicate. Consequently, multiplicity can be audited if the source
contains repeated names; its actual frequency is not known in this workspace.

Quality evaluations are joined by exact description through a dictionary.
Repeated evaluation descriptions overwrite earlier entries in input order.
The builder does not carry alternative judgments, votes, or language_match into
the parquet. This establishes what the pipeline retains, not that such fields
are absent from the raw evaluations or that collisions occurred in production.
Inspect raw field names and duplicate-description counts before drawing either
conclusion. Do not call quality scores target-agreement measures.

The available builder excludes `score < 0.75`, so it keeps scores equal to 0.75.
Original prose and the first rewritten appendix said `score > 0.75`. The working
appendix now says a threshold of 0.75 without asserting an unverified historical
boundary rule. The new audit counts equality and both inclusive/strict totals;
we still need actual data to determine whether this affects the corpus count.

`scripts/audit_target_multiplicity.py` provides a CPU-only inventory of:

- exact duplicate name/color records versus exact names with multiple colors;
- lowercasing/whitespace collisions versus actual repeated raw names;
- recorded unique-color LAB dispersion, without treating a centroid as truth;
- quality-score boundary counts and optional raw evaluation field/collision
  inventories;
- source file hashes and invalid-input counts.

It never changes or filters the source file. Detailed JSON is separate and
refuses to overwrite existing inputs/reports. Counts concern the supplied file,
not automatically the paper's evaluation subset. Raw-source inventories precede
quality filtering; taxonomy inventories concern the supplied processed corpus.
No audit of production data is claimed until the command runs on those files.

Run on the machine containing the full taxonomy dataset:

```bash
uv run python scripts/audit_target_multiplicity.py \
  --input data/colornames_taxonomy.parquet \
  --output reports/content_audit/taxonomy_inventory.json
```

If the original raw files are available, separately inventory pre-filtering
source multiplicity and evaluation fields:

```bash
uv run python scripts/audit_target_multiplicity.py \
  --input data/colornames-raw/dataset_colornames_source.json \
  --evaluations data/colornames-raw/colornames_evaluations.json \
  --output reports/content_audit/raw_source_inventory.json
```

These observations cannot establish that every alternative target is reasonable
for the name, estimate human agreement, or resolve which initial predictions are
semantically wrong. Those require additional judgments or a narrower claim.

## 3. The six same-set message pairs are not in the uploaded teacher export

The uploaded `teacher_analysis.json` contains 262 diagnostics and omits certified
canonical outputs. It contains zero restricted-zero-shot keyword-set-equal
diagnostics. Therefore it cannot reveal the six different-text/same-set pairs
identified by the receiver aggregate audit. Their exact wording, responses and
error effects are retained in the full GPU-machine receiver-message JSON.

The inspector's Markdown previously showed only added-direction cases. It now
also prints every restricted-zero-shot pair with different literal feedback but
the same frozen lexical set, including raw receiver responses and paired error.
Pending/unparsed pairs stay visible with n/a effects. This changes presentation
only; no scores, checkpoints, teacher messages or primary summaries are changed.

Rerun the CPU-only inspector on the existing receiver run:

```bash
uv run python scripts/inspect_teacher_receiver.py \
  --run runs/20261007_152230_242355_teacher_receiver_a100_40gb
```

Inspect the final section of reports/receiver_message_audit.md. The completed
production audit predicts six cases, but the inspector does not hard-code that
count or infer their wording from aggregate statistics. Ordering, synonym or
other surface mechanisms remain unnamed until the actual pairs are reviewed.

## Validation and scope

Five focused CPU checks pass using fabricated fixtures: duplication versus
normalization, score boundaries and duplicate-weight-invariant dispersion,
evaluation collisions, input preservation/overwrite protection, empty/invalid
data, and unchanged same-set message export with pending endpoints. They verify
software behavior, not target ambiguity or new model findings. No model loading,
inference, data download, fitting, raw production-data access or format work
occurs in this audit. Required production observations remain a machine-side
handoff.
