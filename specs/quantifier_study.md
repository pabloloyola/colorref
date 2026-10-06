# Matched quantifier study (888 calls)

## Frozen protocol

The study compares two prompts: the original adjustment prompt and the same
prompt with the LAB axis-convention legend. All other generation settings,
starting coordinates, directions, and instructions match. Qwen3-14B runs in
bfloat16 on one A100 40 GB, at temperature 0 with thinking disabled and 64
maximum output tokens. Each call starts a fresh context; one model load serves
both prompt conditions.

Twelve fixed anchors combine L = 35, 50, 65 with four coordinate profiles:
neutral (a=0,b=0), warm (18,12), green (-18,12), and blue (8,-18). The warm anchor
differs from the earlier pilot's more chromatic warm anchor. Starting states and
all exact numeric control targets must have LAB-to-clipped-sRGB round-trip error
below 1 Delta E. This is a conservative projection diagnostic with 8-bit
quantization, not an exact gamut membership proof.

Each anchor receives:

- Six directions with four wordings: bare baseline, a little, somewhat, much.
- Six directions with exact 5-unit and 10-unit coordinate controls.
- One instruction to keep the color exactly unchanged.

With two prompts: 12 × [6 × (4 + 2) + 1] × 2 = 888 responses, or 444 matched
pairs. The bare instruction has no ordinal magnitude rank. Numeric and no-change
controls are not entered into quantifier monotonicity.

The shared pair order and the order of prompts within each pair are randomized
with seed 13. Each matched pair stays adjacent to limit timing differences.
This seed controls condition order, not a claim of exact GPU reproducibility.

## Measurements and interpretation

Wording responses have no exact target step size. Report native signed steps,
direction following, off-axis drift, nondecreasing and strictly increasing
quantifier pairs, numerical headroom fractions, and projection error. Projected
movement is measured between the projected starting and predicted colors, so
starting-state quantization is not treated as model movement.

Numeric controls explicitly name the coordinate, specify the increment, and
require the other coordinates to stay unchanged. Their exact expected LAB state
is recorded. Report native target error, accuracy within 0.01 and 1 Delta E,
signed actual/requested step ratio, and projected target error. No-change has no
requested direction; its native movement norm equals its control target error.
These controls test execution of exact coordinate instructions and output
stability; their wording is intentionally different from qualitative feedback.

The paired table compares identical conditions, with axis_legend minus plain
deltas. Only pairs with both outputs parsed enter metric differences. Failed
parsing remains in completion/parse counts and raw outputs. All model outputs
remain in the dataset, including large projection errors. A backend execution
error stops the invocation and leaves that condition pending; it is not counted
as a model parse failure.

These are descriptive measurements on fixed anchors and one response per
condition, not population estimates or direct access to the model's internal
understanding. The study does not replace the paper's paired HEX/LAB
reference-game evaluation, ambiguous-target analysis, or teacher prompting
controls.

## Run

From the repository root:

    uv run python scripts/run_quantifier_study.py --config configs/experiments/quantifier_study_a100_40gb.yaml --dry-run

Expect 888 conditions, 444 pairs, 576 wording trials, 288 numeric trials, and 24
no-change trials. Dry-run does not create a run or load the model.

    uv run python scripts/run_quantifier_study.py --config configs/experiments/quantifier_study_a100_40gb.yaml

No dataset download is needed for these fixed LAB anchors. The runner prints the
run directory immediately, saves full configuration and rendered prompt
snapshots, and checkpoints each response to raw_outputs/responses.jsonl with
flush/fsync. Invocations record the code revision. Changing saved model settings,
prompts, or conditions fails snapshot integrity checks.

To generate only a few responses before continuing, use --limit 8. The full
888-condition plan remains saved:

    uv run python scripts/run_quantifier_study.py --config configs/experiments/quantifier_study_a100_40gb.yaml --limit 8
    uv run python scripts/run_quantifier_study.py --resume runs/YOUR_RUN

Resume loads the saved configuration and prompts, generates only unfinished
conditions, and preserves completed parse failures. An interrupted,
unterminated final JSONL line can be repaired on resume; duplicate, foreign, or
other malformed records cause an error. An already complete run does not load
the model when resumed.

## Outputs and CPU-only reanalysis

- reports/study_summary.md: progress, paired differences, wording metrics,
  exact-control accuracy, and direction breakdowns.
- metrics/study_trials.parquet: per-trial conditions, predictions, and metrics.
- metrics/paired_trials.csv: matched parsed-status flags and metric differences.
- raw_outputs/responses.jsonl: durable full prompts, raw outputs, expected
  control targets, and scored responses.
- raw_outputs/execution_errors.jsonl: backend errors, if any.

    uv run python scripts/run_quantifier_study.py --report-only runs/YOUR_RUN

Reanalysis validates the saved plan and requires no inference imports. Partial
runs can be reanalyzed; uncompleted pairs are not treated as completed evidence.

The older 48-call pilot configs and run_quantifier_calibration.py remain
unchanged and retain their original report-only workflow.
