# Sequential magnitude transfer — frozen-controller protocol

Status: implemented and CPU-tested in `scripts/run_magnitude_transfer.py`.
The GPU study completed in run `20261007_072214_768541_magnitude_transfer_a100_40gb`: all 600 games, 1,059 parsed revisions and 200 common terminal triplets. See `specs/results/magnitude_transfer_20261007.md` for user-supplied production results and the next CPU inspection. Do not rerun the completed study merely to recreate these results. This follows the completed one-step pilot and CPU
breakdown; it does not replace or retune them.

## Question

Does repeated use of the frozen calibrated phrase policy, with target-known
stopping, turn its prevention of small-step overshoot into reliable localization
of larger residuals? The one-step pilot lowers mean error and harmful updates,
but its phrase ladder is coarse, red corrections underperform at 12/24 units,
and large green corrections have high step-transfer mismatch. Sequential
execution might permit several moderate updates; that remains a hypothesis.

Do not claim that changing display geometry alone explains the result: native
bare/calibrated requested steps already differ. Do not call repeated corrections
human-like perceptual understanding or demonstrated creative editing.

## Frozen inputs and new evaluation starts

- Freeze the completed magnitude run as the parent. Load its validated config,
  prompt, observed model revision, complete calibration responses and fitted
  controller bundle. Preserve provenance digests and reproduce the original
  fitted mapping before use. Do not fit on its 196 evaluated targets.
- Use the same Qwen3-14B receiving prompt and settings, six-decimal displayed LAB
  inputs, fresh context for each response, thinking off, temperature zero and
  64-token generation cap. Each invocation loads one model on the A100 40 GB.
- Select 12 fresh displayed sRGB starts using a declared new seed (47) and the
  same inclusive RGB channel range [48,208]. Exclude all old calibration and
  evaluation starts, the original quantifier anchors and close-case start.
  Exclude by exact HEX before target construction; do not replace starts after
  seeing target feasibility or responses. Freeze all inputs before inference.
- Construct single-axis native target candidates at 6/12/24 units, with the same
  LAB prompt bounds and pre-inference projection ΔE ≤1 feasibility requirement.
  Keep exclusion counts by direction/distance. Freeze native candidates and
  projected target states; derive residuals from displayed states.
- These are new evaluation starts, not new calibration colors. Reusing the
  fitted map tests transfer of a specified policy; it is not evidence that the
  old mapping is universal or optimal.

## Conditions and shared execution rules

Compare three receiving conditions: bare direction, original calibrated phrase
selection, and exact numeric requested-coordinate increment with holds. Each
condition receives the same supplied start and hidden target. Feedback is
restricted throughout a trajectory to the target's original LAB axis. The
requested sign can reverse after overshoot; use the corresponding existing
positive/negative direction mapping. Other coordinates are not intentionally
corrected in this single-axis phase, so model-induced off-axis drift remains
observable rather than being silently fixed by a new multi-axis oracle.

All policies share:

1. Stop before inference whenever displayed total target ΔE ≤5, including the
   supplied start. Count assigned stops separately from generated successes.
2. Otherwise compute the signed residual on the permitted axis. If its absolute
   value is ≤0.01 but total target ΔE remains >5, end with an explicit
   `off_axis_residual` nonconverged outcome. Do not issue an empty correction,
   repair coordinates, or switch axes in this first transfer study.
3. Choose a bare direction, the original nearest-positive-median phrase, or the
   exact numeric increment from that same residual. Numeric holds remain extra
   semantic precision; natural and numeric arms are not information-matched.
   The current displayed starting state, not its last native proposal, enters
   the next prompt and coordinate calculation.
4. Generate one fresh-context response and strictly parse native LAB. Retain
   native and projected uint8 states, prompt, raw text, feedback, generation
   diagnostics and measurements. A parse failure ends the game as a failure;
   a backend execution error leaves its revision pending for resume.
5. Stop after at most five generated revisions. Early stopping retains the first
   threshold state, never a future best-state selection. Record all stopping
   reasons, no usable-mapping cases, revision costs and unresolved drift.

The five-revision cap is a new declared transfer setting, not the original
paper's three-turn protocol. It allows several moderate steps for a 24-unit
residual without expanding the phrase ladder on the tested evaluation set.
Report observed prefix outcomes at one and three revisions as secondary
budget views: an early-stopped state remains unchanged, with no extra generated
calls or fabricated continuation. Actual teacher utterances may diverge after
starts because the states diverge. The policy and allowed axis are shared.

Upper budget: 12 starts ×6 directions ×3 distances ×3 arms ×5 revisions =
3,240 generations before feasibility exclusions and early stopping. The dry
run must print actual target counts and upper budget before inference. A small
limited smoke must retain the full plan for resume, not create a selected test
subset. No second model or new calibration runs are needed.

## Primary outcomes and denominators

The primary contrast is calibrated-minus-bare displayed final target error at
the shared stopping rule/five-revision cap, with starting-color cluster paired
intervals. Report convergence and actual generation counts alongside error;
lower error purchased by more turns is not automatically better efficiency.

Common valid terminal pairs/triplets include parsed threshold stops, parsed
budget exhaustion and explicit parsed off-axis-residual endings. Parse failures
remain in completion counts and all-planned failure-aware convergence rates;
never convert their last parsed prefix into a successful endpoint. Pending
execution must be shown separately. Available-pair sensitivity preserves a
natural-wording pair if the numeric condition fails.

Secondary diagnostics:

- error, convergence and cumulative actual calls at observed one-/three-revision
  prefixes; early-stopped states are retained and labeled;
- per-step harmful updates, overshoot geometry, native/displayed signed steps,
  projection costs and off-axis drift;
- stopping-turn distributions and whether large red residuals reach threshold
  through repeated moderate instructions;
- direction/distance breakdowns with planned/included/parsed denominators,
  error medians and win/tie/loss counts;
- per-start means and descriptive leave-one-start-out leverage;
- numeric exact-coordinate error counts, quantiles and raw large-miss exports;
- actual prompt/completion tokens and emitted axis-correction counts.

Fit no policies or thresholds on these new evaluation outputs. Any wider ladder
or state-conditioned policy needs separate calibration and another fresh test.
Subgroup analyses are exploratory and unadjusted for multiple comparisons.

## Revision priorities beyond this transfer

The one-step magnitude result is already interpretable for the paper without
this extension. Sequential transfer is a focused follow-up, not a prerequisite
for acknowledging its limits. A future creative-interface claim needs saturation,
multi-axis corrections, descriptions/images or human interaction evaluated
separately. HSV saturation must use its own native S calibration and cannot
reuse LAB-axis unit medians.

Machel's strongest unresolved criticism concerns the teacher, not the guesser's
magnitude control. Run matched zero-/few-shot teacher controls with literal
restricted-axis restatement versus the old natural paraphrase prompt before
retaining broad claims about inability to generate correct feedback. Keep
model identity, exact example split and clause/constraint budgets explicit.
The direct-LAB and magnitude controls do not substitute for that experiment.


## A100 commands and saved evidence

Pull the active branch, then validate the completed parent and inspect the
fresh plan without loading a model or creating a new run:

```bash
git pull --ff-only origin refactor/quantifier-calibration
MAG_RUN=runs/20261007_054337_204395_magnitude_control_a100_40gb_pilot
uv run python scripts/run_magnitude_transfer.py --parent-run "$MAG_RUN" --dry-run
```

Under the unchanged production parent configuration, the deterministic target
construction gives 12 fresh colors, 200 feasible targets, 16 feasibility
exclusions, 600 games and at most 3,000 new revisions. These are plan counts,
not model performance. No new calibration generations occur. The parent must
have complete calibration/evaluation checkpoints and an existing frozen
controller; its calibration-only fitted map and saved scores are reproduced
for validation. The dry run prints the required observed model revision.

Start a 12-revision smoke while retaining that full plan:

```bash
uv run python scripts/run_magnitude_transfer.py --parent-run "$MAG_RUN" --limit 12
```

Use the exact run directory printed by this invocation. The helper below selects
the latest default-name run; verify it matches the printed path when multiple
runs exist. Resume this run instead of starting another `--parent-run` run:

```bash
TRANSFER_RUN=$(find runs -maxdepth 1 -type d \
  -name '*magnitude_transfer_a100_40gb' | sort | tail -1)
cat "$TRANSFER_RUN/reports/transfer_summary.md"
uv run python scripts/run_magnitude_transfer.py --resume "$TRANSFER_RUN"
```

CPU-only reporting after completion or during an interrupted run:

```bash
uv run python scripts/run_magnitude_transfer.py --report-only "$TRANSFER_RUN"
cat "$TRANSFER_RUN/reports/transfer_summary.md"
```

The new run copies `inputs/parent_snapshot.json` containing validated parent
configuration, plan, metadata, calibration responses and controller, together
with the completed parent evaluation count/digest. Resume does not depend on
the parent folder's continuing presence. The new plan/config/snapshot are
hashed and reproduced before resume/reporting. The copied provenance does not
include the entire parent evaluation outputs; those remain in the parent run.

Each generated revision atomically updates its game's
`raw_outputs/games/NNNN.json`. Frozen task inputs, raw response, native/projected
state, score, token/EOS diagnostics and prompt-token counts remain in the
checkpoint. Unknown game files, altered inputs/scores and revisions after a
terminal state are rejected. A changed observed HF model revision is rejected
before generation. Each invocation loads one model only if inference is still
needed. Backend errors leave a pending revision and save a diagnostic; strict
parse failures terminate that game without repair.

`metrics/transfer_analysis.json` and `reports/transfer_summary.md` report
terminal/common and available-pair effects for error, calls and convergence,
observed one-/three-call prefixes, all-planned completion, stopping reasons,
native/displayed overshoot and drift, tokens, exploratory direction/distance
bins and per-start leverage, and numeric execution tails with raw miss exports.
Report-only mode updates only those two files and never queries a model. All
counts and intervals remain provisional for incomplete runs.
