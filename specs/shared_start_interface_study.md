# Shared-start output-interface comparison

Implemented in `scripts/run_shared_start_study.py`. This study has not yet been run on the A100; CPU tests use simulated responses. Its purpose is to separate feedback following from the different initial color predictions in the completed interface study. The existing CPU trajectory analysis remains useful alongside this new control.

## Running on the A100

Stay on `refactor/quantifier-calibration` and pull the published changes. First validate the actual saved parent run without loading a model:

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/run_shared_start_study.py \
  --parent-run runs/20261006_143711_709402_interface_study_a100_40gb \
  --dry-run
```

The production parent should produce 64 examples, 192 games, and at most 576 new generations. Model identity/settings, oracle thresholds, three fixed rounds, and prompt texts are inherited from the frozen parent, not read from current live templates or a new YAML. No dataset download is needed.

To run an eight-response checkpoint smoke test:

```bash
uv run python scripts/run_shared_start_study.py \
  --parent-run runs/20261006_143711_709402_interface_study_a100_40gb \
  --limit 8
```

The log prints the new run directory. Resume **that same directory** to finish; invoking `--parent-run` again starts a separate experiment:

```bash
SHARED_RUN=$(find runs -maxdepth 1 -type d \
  -name '*shared_start_interface_study_a100_40gb' | sort | tail -1)

uv run python scripts/run_shared_start_study.py --resume "$SHARED_RUN"
cat "$SHARED_RUN/reports/shared_start_summary.md"
```

The summary is written after the smoke test and every invocation, including a backend error. A partial report is not a completed scientific result. Alternatively, omit `--limit` in the initial command to run the entire plan in one model load. `--output-root` and `--experiment-name` can be supplied at creation; `--limit` caps new generations during creation or resume.

Rebuild reports without inference:

```bash
uv run python scripts/run_shared_start_study.py --report-only "$SHARED_RUN"
```

Default bootstrap settings are 5,000 resamples and seed 13; `--resamples` (at least 100) and `--bootstrap-seed` change analysis only. Reports include common-triplet and available-pair comparisons for the first and final revisions separately. Detailed per-game statistics and failure prompts/responses are in `metrics/shared_start_analysis.json`.

## Saved-state implementation

The parent loader validates frozen hashes, tasks, and every saved checkpoint under the existing run lock. Creation freezes the parent run/plan/config hashes and each selected HEX initial record's digest. The child's examples store the assigned starting HEX and recomputed LAB/HSV; prompts and task order are frozen too. Parent config/checkpoints/reports are not rewritten. The child can resume or reanalyze after the parent folder or live dataset becomes unavailable.

Checkpoints contain generated revision records only, with turns 1–3 and `record_kind: generated_revision`. Supplied turn zero has `record_kind: supplied_start`, no raw response, and is reconstructed from the frozen plan. It is never counted as a generation or included in generated-state projection diagnostics.

New HF responses expose generated-token counts and observed EOS/budget flags in their `raw` diagnostics; the shared-start checkpoints save these under `generation`. Counts include generated special/EOS tokens. HF finish labels (`eos`, `length`, or unknown) are inferred from observed output tokens and explicitly labeled `observed_output_tokens`, rather than claiming a server-reported reason. EOS on the last allowed token can set both EOS and budget flags. Compatible APIs retain their backend-reported finish reason and completion-token count when supplied. Existing saved outputs cannot acquire these diagnostics retrospectively. Generation settings, output parsing, and existing study protocols are unchanged.

CPU acceptance tests cover a simulated 576-call plan, eight-call start plus 568-call resume, one model load per invocation, no model import for dry-run/report-only or completed resume, identical starts/first feedback, parent preservation, missing/tampered parent rejection, backend vs parse failures, separate first/final cohorts, no-constraint drift, empty cohorts, paired error/gain interval identities, and HF diagnostic extraction without real weights. Simulated outcomes do not constitute model performance.

## Question and estimand

For the same color description, assigned target, displayed starting color, and first oracle correction, how does the revised displayed color depend on HEX/plain LAB/legend-LAB output instructions?

Primary endpoint: the paired difference in displayed-color ΔE76 after the **first revision**, conditional on the shared starting-state policy. All three interfaces receive identical first feedback. Secondary endpoints track three adaptive rounds; after the first response diverges, feedback remains policy-matched but need not have identical wording.

This comparison can attribute within-protocol differences to the representation/prompt intervention from shared states. It does not measure internal representations or eliminate effects of interface familiarity. An axis legend is still a prompting intervention.

## Inputs and state selection

Use the existing run `20261006_143711_709402_interface_study_a100_40gb` as a frozen parent input. For each of its 64 selected examples, take the HEX condition's parsed turn-0 displayed state as the common start. HEX turn 0 parsed for every example in the reported run, so all 64 are eligible; the old legend failures do not determine membership in the new experiment.

- Validate the parent's saved plan, configuration, and checkpoints using the existing CPU loader.
- Freeze example ID, description, original target HEX, shared start HEX, its recomputed LAB/HSV, and parent condition/run ID.
- Render that same displayed state as HEX for the HEX condition and as six-decimal D65 LAB for both LAB conditions.
- Mark the supplied start as externally assigned, not a prediction generated by the receiving condition. Error at this state must be identical across interfaces.
- Preserve 16 examples in each regime and seed/order the interfaces within each example.

Choosing a HEX-derived start is a declared anchoring policy, not a neutral distribution over all colors. Findings are conditional on these states; a later grid/alternative-start replication would test robustness to that choice. Do not select starting states from the target to make a correction artificially easy.

## Conditions and feedback

Keep the three existing matched revision templates unchanged:

| Condition | Shared state shown as | Output | Axis legend |
|---|---|---|---|
| HEX | HEX | HEX | Absent |
| Plain LAB | LAB | LAB | Absent |
| LAB with legend | LAB | LAB | Present |

Use the parent's model identity/settings, including 64 output tokens, temperature zero, thinking disabled, and the same deterministic c3 oracle thresholds. This preserves the existing output protocol; a separate token-budget/output-format intervention should use its own labeled run.

The oracle sees only the displayed uint8 sRGB state in every condition. It observes the same target/start pair and therefore must emit identical direction lists, feedback text, and constraint counts at the first revision. After each response, retain native coordinates for diagnostics and use projected displayed states for feedback and the next prompt. The target remains hidden from the guesser.

Run three fixed revisions per example and condition: maximum **64 × 3 × 3 = 576 generated responses**. The externally assigned starting state costs no generation. Cases already close to the target remain in the fixed-round diagnostic, and cases with no emitted directional constraint are explicitly flagged. Direction/constraint-following means exclude undefined no-constraint cases; displayed target error and drift remain reportable.

## Failure and completeness handling

Reuse the turn-level checkpoint principles: one model load per invocation, frozen prompts/configuration, atomic checkpoints, a run lock, genuine parse failures retained as completed unsuccessful outcomes, and backend errors left pending.

Log the supplied state separately from generated revisions. Saved-response counts must exclude supplied starts. A failed first revision has no valid first-revision accuracy; a failed later revision must not erase an earlier successful first-revision observation. Reports therefore have separate primary first-revision and secondary full-trajectory cohorts, plus all-available paired sensitivity tables. Never report accuracy solely over full three-round trajectories when analyzing the first revision.

Record generated-token counts and finish reasons when the backend exposes them. This addresses the unconfirmed truncation explanation for the previous failures. Do not evaluate arithmetic expressions or rescue partial triplets within the original strict output condition; any tolerant parser is a separate diagnostic.

## Measurements

1. Check that initial displayed errors, first feedback strings, oracle directions, and constraint counts match across the three conditions for every example.
2. Primary: first-revision projected ΔE, absolute gain from the shared start, direction alignment, constraint satisfaction, and parse rate.
3. Secondary: final/best displayed error, convergence, final–best gap, stationary steps, native LAB error, and projection cost over three revisions.
4. Separate initially converged starts and no-constraint starts from ordinary correction cases when interpreting drift.
5. Estimate paired first-revision error/gain differences with regime-stratified whole-example bootstrap resampling, preserving matching and observed cohort sizes. Report denominators and common/all-available cohorts explicitly.

Because starting errors are identical, paired first-revision error differences are the negative of paired gain differences. Their confidence intervals should satisfy the same relation; this is a useful analysis integrity check. This identity does not hold for the earlier study, whose initial guesses differ.

## Implementation acceptance gates

- Parent inputs can be frozen and checked without a model or live dataset.
- All 64 examples receive precisely the same displayed starting state and first teacher correction across interfaces.
- Supplied starts are labeled correctly and are not counted as generated/model-inferred states.
- Resume after a partially completed game regenerates only unfinished revisions.
- Parse/backend failures remain distinct; first-revision and full-trajectory denominators differ correctly when a later revision fails.
- A full simulated run has at most 576 generated responses and loads the model only once per invocation.
- Reanalysis leaves the parent run unchanged and uses no inference imports.

## Paper role

Use this as the feedback-following control next to the existing name-to-color interface diagnostic. The latter measures an entire prediction-and-revision pipeline; this protocol tests revisions from shared states. Do not replace the old experiment or silently rewrite its results as if initial states had been matched.
