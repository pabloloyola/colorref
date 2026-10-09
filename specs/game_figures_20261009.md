# Game diagram and empirical trajectory

The manuscript should explain the game before asking the reader to interpret
its results. Page-limit trimming is deferred. The two visuals have distinct roles:

- The compact vector robot diagram in the introduction defines the guesser,
  teacher, description, hidden recorded target, verbal correction and revision loop.
  Blue icons represent the same guesser at two points in the interaction. Its current swatches and exact oracle message come from the first exchange
  of example 427046; the role icons and layout are schematic.
- A saved-game trajectory near the Framework explanation will show the actual
  movement caused by successive feedback messages. The a*b* panel is accompanied
  by L* per turn and full three-dimensional displayed-state Delta E76. Target
  proximity in the two-dimensional panel alone must not imply convergence.

The uploaded `025703_backyard_american_dream.png` provides the design reference:
numbered swatches, arrows, an attached lightness panel and exact transition text.
Its underlying historical raw trajectory is not recovered, so it is not presented
as a fresh experimental result. The current reading PDF includes both the robot diagram and the transported
empirical trajectory. No synthetic test trajectory is inserted into the paper.

## Generate current candidates without inference

The legacy `plot_trajectory_figures.py` showcase hard-codes lost May run paths.
The new entry point reads the current `run_interface_study.py` game schema,
including the completed 1,000-description grounding replication. It validates
the frozen plan/configuration hashes and reconstructs saved prompts, feedback,
parsing and metrics before plotting. Its output directory must be outside the
source run. No weights, GPU access or additional responses are needed.

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/plot_saved_trajectories.py \
  --run runs/20261008_022100_355058_grounding_1000_a100_40gb \
  --out reports/figures/current_trajectories \
  --n 16 --seed 113 --bundle
```

This writes `reports/figures/current_trajectories/trajectory_gallery.zip` with
16 PNG/PDF pairs, the corresponding original checkpoint records and source
SHA-256 hashes, a manifest of every planned game's completion, and an HTML
gallery. Selection samples full parsed games by seeded round-robin semantic
regime, without ranking by gain. The candidates are illustrations, not a
representative performance estimate. Missing, failed and unfinished games remain
visible in the manifest and are never assigned invented endpoints.

To regenerate a particular example after reviewing the candidates:

```bash
uv run python scripts/plot_saved_trajectories.py \
  --run runs/20261008_022100_355058_grounding_1000_a100_40gb \
  --example-id EXAMPLE_ID \
  --out reports/figures/selected_game --bundle
```

The original matched interface run also works with `--variant hex`, `lab_plain`
or `lab_axis_legend`. Shared-start and magnitude-transfer plans use different
schemas and are intentionally not supported by this entry point.

## Integration after choosing the example

Use one clear trajectory to explain the game, retaining its ID, run ID and
source hashes. If showing an overshoot or failure to motivate magnitude control,
identify it as an illustrative case rather than typical behavior. Keep aggregate
claims in the cohort results. Prefer using the selected description/swatches in
both the diagram and trajectory once the raw files are available.

The empirical caption should identify the model, deterministic teacher, output
interface, fixed-round policy and displayed-state evaluation, and explain the
L* panel, full Delta E76, and fixed-lightness background. Feedback is the exact
saved message for the transition, stored on the receiving response in the
current checkpoint schema. No projection-error filter or response repair is used.

## Validation

Five CPU acceptance checks cover immutable source reading, source/plan mismatch,
altered feedback or displayed colors, visible pending/failed/missing completion,
and stable regime selection. A separate clearly labeled synthetic test fixture
exercises the CLI, PNG/PDF rendering and ZIP packaging; it is not evidence.
The updated paper is compiled and visually inspected with the same temporary
Courier substitution as the preceding reading copy. Publication sources keep
the original Inconsolata package.

## Received gallery and manuscript integration

The author supplied a compact JSONL export of 16 HEX trajectories, four from
each regime, from `20261008_022100_355058_grounding_1000_a100_40gb`.
All 64 displayed colors, 16 targets, full Delta E76 values and 48 exact canonical
oracle messages agree with recomputation. The compact source and a provenance
manifest are committed under `paper/evidence/trajectory-gallery-20261009/`.
Full checkpoints, original prompts/raw responses and full-run completion data
are absent; supplied original SHA identifiers are retained, not independently
verified. No recovered historical output or new generation enters the figures.

The introductory diagram and Framework trajectory use example 427046,
"southern lime green". Its errors are 32.82, 18.53, 14.05, 8.79. It is chosen
for a readable progressive example and explicitly remains nonconverged at the
threshold of 5. Other gallery candidates exhibit regression and overshoot.
Selection is illustrative; no cohort statistic is estimated from this gallery.
The diagram now shows this case's actual ungraded first oracle correction;
its text does not imply that the grounding run used calibrated modifiers.

The ZIP and combined 16-page gallery PDF are committed at
`paper/trajectory-gallery-20261009.zip` and `.pdf` for browser access.
Rebuild the transported gallery with
`uv run python scripts/rebuild_compact_trajectory_gallery.py`.
Rebuild its matching diagram with
`uv run python scripts/plot_reference_game.py --compact-export
paper/evidence/trajectory-gallery-20261009/compact_cases.jsonl --example-id 427046`.
The default diagram without arguments remains a constructed example.

Eight CPU acceptance checks now include compact read-only roundtrip,
tampered colors/errors/messages and duplicate slots. All sixteen plots were
rendered and visually reviewed; the paper was compiled and inspected with
the same temporary Courier substitution. Page-limit compression is deferred.
