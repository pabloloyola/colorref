# Efficient evidence expansion — frozen first stage, planned later stages

Author priority: conference impact, efficient A100 40GB use, and enough distinct
sampling units. Historical May outputs are unrecoverable after the original
machine was wiped. Preserve the imported manuscript; do not silently reuse
historical table numbers as fresh verified evidence.

## Stage 1 — implemented and ready for a timing pilot

Freeze 1,000 new descriptions, 250 in each semantic regime, seed 113, from the
verified taxonomy. Exclude every ID in the original debug_400 subset (which
contains the earlier 64-example controls). Selection cannot depend on outputs.
The preparation manifest retains source/exclusion/subset SHA256 and selected
IDs. Existing subset output is never overwritten.

Run Qwen3-14B pinned to model revision
40c069824f4251a91eefaf281ebe4c544efd3e18, HF Transformers BF16, temperature 0,
thinking disabled, 64 output tokens, HEX output and deterministic c3 axis
oracle with the same frozen thresholds/prompts as the new interface pilot.
Exactly three fixed revisions; parse failure terminates its game, backend
failure remains pending, and close states continue. This is a fresh protocol
replication, not an exact reconstruction of the historical 12k result.

Cost: maximum 1,000 initial predictions + 3,000 revisions = 4,000 generations.
Initial predictions provide the one-shot baseline without another inference.
Execute the first 100 generations and then resume the same frozen run: no
separate throwaway timing experiment. Freeze total N before observing effects;
do not change it based on interim significance or favorable outcomes.

Primary outcome: paired mean initial-minus-final displayed Delta E, with
whole-description bootstrap within regimes; initial/final errors and coverage
are also reported. Equal regime weights describe a balanced benchmark, not
the full corpus frequency distribution. Retain failures and pending counts;
do not impute endpoints. Regime analyses are secondary, not four independent
claims selected after looking at results. Descriptions can share target colors;
1,000 descriptions are not 1,000 human agreement judgments.

This establishes feedback benefit under this protocol; information amount
changes, so it does not alone establish adaptation beyond matched information
budgets. HEX only avoids spending two additional interfaces on every example.
The existing matched interface/shared-start pilots remain supporting controls,
explicitly labeled as smaller studies.

Commands:
```
uv run python scripts/prepare_grounding_replication.py
uv run python scripts/run_interface_study.py --config configs/experiments/grounding_1000_a100_40gb.yaml --dry-run
time uv run python scripts/run_interface_study.py --config configs/experiments/grounding_1000_a100_40gb.yaml --limit 100
```
After inspecting throughput and execution integrity, use `--resume RUN_DIR`;
never restart with `--config` to continue. Read `reports/grounding_summary.md`.
Saved response latency excludes model loading and report/checkpoint overhead;
use both elapsed wall time and saved latency. HEX estimates do not predict
longer LAB/teacher generation latency. Backup compact frozen configs/plans,
metadata, reports and response checkpoints off the GPU machine as they accrue.

## Stage 2 — primary magnitude confirmation, implemented

Target 32 calibration colors and 128 distinct held-out starting colors, drawn
before inference with a new seed and explicit exclusion of all pilot colors.
Freeze the same RGB channel range and pre-inference feasibility rules; retain
every exclusion. More directions/targets on 12 starts do not increase the
number of independent color clusters. These are RGB-sampled colors, not human
samples or a proof of general perceptual coverage. 128 is a planned budget,
not a demonstrated power guarantee; interval width/effect heterogeneity matter.

Four matched one-revision arms: bare direction, an unfitted distance-aware
graded rule, fitted calibration, and exact numeric execution control.
Before inference, freeze the unfitted rule as a_little for residual <9,
somewhat for 9<=residual<18, much otherwise. These are midpoint cuts for the
constructed 6/12/24 distances, not cutoffs fitted to receiver outcomes.
This tests a specific fitted controller against a specific unfitted rule;
it cannot prove every possible calibration is necessary or optimal.

Maximum cost: 32*6*4 = 768 calibration calls and
128*6*3*4 = 9,216 evaluation calls before feasibility exclusions.
Primary: paired calibrated-minus-unfitted displayed target error, cluster
bootstrap by starting color with pooled case weights. Bare/numeric contrasts,
distance/direction breakdown, projection and failure diagnostics are secondary.
Calibration/evaluation prompts, scopes and policies must match. Numeric adds
coordinate precision and is not an information-matched linguistic baseline.
No evaluation outputs fit medians or change thresholds, colors or target steps.
Do not launch the existing three-arm runner and label it this four-arm design.

Implementation uses an opt-in `unfitted_cutpoints` field; old configurations
remain three-arm. `scripts/prepare_magnitude_confirmation.py` validates the
frozen original magnitude and transfer plans, excludes all of their stimulus
colors, and writes the new config/manifest without changing parent runs.
Calibration and evaluation starts are disjoint, 32 and 128 respectively;
model revision is pinned as in Stage 1. Evaluation tasks are deterministically
shuffled, while old task order is preserved. Reports name the common four-arm
cohort, its observed color-cluster count and the primary contrast explicitly.
Partial/failed cases remain visible and available-pair sensitivity is retained.
Existing three-arm transfer/inspection scripts should not be used to describe
this four-arm confirmation; sequential-transfer parent validation rejects it.

```
uv run python scripts/prepare_magnitude_confirmation.py --pilot-run runs/20261007_054337_204395_magnitude_control_a100_40gb_pilot --transfer-run runs/20261007_072214_768541_magnitude_transfer_a100_40gb
uv run python scripts/run_magnitude_control.py --config data/confirmatory/magnitude_128/config.yaml --dry-run
time uv run python scripts/run_magnitude_control.py --config data/confirmatory/magnitude_128/config.yaml --limit 100
```
Resume the printed run directory, not another `--config` launch. First 100
calls are part of the 768 calibration calls; a successful timing prefix cannot
yet establish the held-out primary effect or forecast all evaluation latencies.
Save the frozen protocol and checkpoints off-machine before relying on them.

## Stage 3 — replication and task transfer, ordered by remaining budget

Replicate key matched magnitude contrasts with a different model family;
choose the model on hardware/licensing feasibility before seeing scores.
Start with 64 independent held-out colors and a separately fitted model-specific
mapping; do not carry Qwen medians into another receiver and call it calibrated.
Current backend supports inference, but model formatting/thinking conventions
need a smoke check. Report family, model revision and all actual settings.

Only then integrate calibrated corrections into description games under a
matched receiving prompt. Single-axis/no-description medians do not certify
multi-axis/name-context transfer. This needs a frozen calibration protocol and
matched policy comparisons; it is not already implemented by changing YAML.
Sequential controlled-coordinate transfer can reuse the Stage-2 frozen mapping
and fresh starts without repeating calibration, if specified before inference.

No default rerun of all historical ICL/LoRA, teacher variants or 12k scale-up.
Increase breadth of independent stimuli and model replication before adding
many more ablation conditions. Separate current implemented work from future
protocols and do not promise a conference acceptance from sample size alone.
