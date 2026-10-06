# Matched output-interface reference games

This diagnostic tests Machel's concern that a language-to-HEX pipeline can conflate color grounding with output encoding. It connects the quantifier study's plain/axis-legend contrast to actual color-name reference games. It does not yet address target ambiguity, few-shot teachers, or constrained teacher paraphrases.

## Design

Select 64 examples from the existing `data/eval_subsets/debug_400.parquet`: exactly 16 from each of the four semantic regimes, seed 13. Sample from stable example-ID order; insufficient quotas or duplicate IDs fail validation. Every selected example receives these three conditions:

| Condition | Output | Axis directions explained? |
|---|---|---|
| `hex` | `#RRGGBB` | No |
| `lab_plain` | `LAB(L, a, b)` | No; only D65 and encoding bounds |
| `lab_axis_legend` | `LAB(L, a, b)` | Yes, in both initial and revision prompts |

The LAB prompts differ only by the axis legend. The old LAB initial prompt already contains axis explanations, so archived game prompts remain unchanged and this study uses new matched templates. HEX and LAB share the same description, task framing, and revision wording apart from the representation instructions. The legend does not explain HSV saturation or give numerical step sizes.

All conditions use Qwen3-14B, HF transformers, bfloat16, temperature 0, thinking disabled, and at most 64 generated tokens. The validated A100 40 GB loading configuration is retained. One model is loaded per invocation, shared across all conditions. Example order and within-example interface order are seeded and frozen. Each response is generated in a fresh context with only the current state and latest feedback.

Each game has an initial guess and three fixed oracle feedback rounds: up to 192 games and 768 generations. Initially close guesses still receive three rounds. This measures equal-round behavior and allows overshooting; it is not the archived early-stopping protocol. A genuine parse failure terminates that game and remains in completion counts. Backend errors leave the interrupted turn pending.

## Common displayed state and scoring

This is a **displayable-color control experiment**. LAB responses retain their native triplets for diagnostics, then convert to clipped, rounded uint8 sRGB. HEX responses already specify that state. The oracle and the next revision prompt use the displayed state for all three conditions; LAB revisions show its recomputed D65 LAB coordinates to six decimals. The target is likewise derived from its original HEX code. This prevents feedback from mixing native LAB coordinates with saturation from a different projected color.

The oracle policy is identical across conditions: the existing deterministic `AxisOracle`, maximum three constraints, thresholds L=2, a=3, b=3, HSV saturation=0.05. Adaptive messages can differ because the guesses differ. There are no magnitude quantifiers in this experiment; the unmodified oracle separates representation/prompt effects from the later question of calibrated magnitude wording.

Primary accuracy is ΔE76 between the displayed state and the target, measured after both are represented in LAB. Native LAB target error is secondary. Projection error includes clipping and uint8 rounding; a projection error greater than 1 is a diagnostic flag, not proof of being outside the gamut. No model output is removed for having high projection error.

Reports include initial/final projected error, projected gain, final native error, best error, final–best gap, final convergence at projected ΔE≤5, constraint satisfaction, directional alignment, and projection diagnostics. Constraint satisfaction is strict positive displayed-state movement on an emitted axis, including saturation; numerical noise below 1e-8 is ignored. Directional alignment is the cosine between the displayed-state update and ideal target correction; zero-length vectors are undefined and excluded. These metrics are averaged within games before averaging across examples.

Accuracy and paired differences use the **common set** of examples with all four responses parsed in all three interfaces. Reports explicitly show completed games, failed parses, completed triplets, and fully parsed triplets; consult these denominators to detect selection effects. Differences are right minus left; negative error differences favor the right interface. Initial-error differences are reported because a legend can also alter initial grounding. Means are descriptive for this balanced diagnostic sample, not population confidence intervals.

## Run on the GPU machine

Update the existing branch; no new data or model download is needed if the prior study setup is intact:

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/run_interface_study.py \
  --config configs/experiments/interface_study_a100_40gb.yaml \
  --dry-run

uv run python scripts/run_interface_study.py \
  --config configs/experiments/interface_study_a100_40gb.yaml
```

The dry-run should show 64 examples, 192 games, and 768 maximum generations. It reads the data and validates quotas but does not load the model or create a run folder. For a short initial execution, add `--limit 8`; this saves the full plan, and `--resume` finishes the remainder without regenerating the saved responses.

```bash
I_RUN=$(find runs -maxdepth 1 -type d \
  -name '*interface_study_a100_40gb*' | sort | tail -1)

uv run python scripts/run_interface_study.py --resume "$I_RUN"
uv run python scripts/run_interface_study.py --report-only "$I_RUN"
cat "$I_RUN/reports/interface_summary.md"
```

The printed run directory is the authoritative path; the `find` shortcut assumes the latest matching run is the intended one. Resume and reanalysis use frozen examples, configuration, and prompts, without reading live dataset or template files. Checkpoint JSON is replaced atomically after every generated response; resume validates prompts, oracle messages, parsing, and scores against the saved plan. Only a response interrupted before checkpoint publication needs regeneration. A process lock prevents simultaneous writers to one run. Reports are regenerated from checkpoints and need no model import.

## Inspect the prior numeric-control miss (CPU only)

The single non-exact legend/numeric-10 response cannot be identified from its aggregate mean. Run:

```bash
uv run python scripts/inspect_quantifier_controls.py \
  --run "$STUDY_RUN"
```

If the shell variable is no longer set, use the known production path:

```bash
uv run python scripts/inspect_quantifier_controls.py \
  --run runs/20261006_130637_580285_quantifier_study_a100_40gb
```

This prints each control with native error greater than 0.01 ΔE (or a parse failure), including its frozen prompt, raw response, base, expected coordinates, actual coordinates, and coordinate residual. It validates the frozen quantifier plan and reparses raw outputs; it performs no generation and modifies no results.

## Interpretation

Lower projected error with LAB would support an output-interface effect in this setting. Improvement from the legend would support a prompting effect on axis interpretation. Neither contrast alone establishes internal perceptual representations, general creative-editing performance, or resolution of ambiguous descriptions. Fixed rounds, projection at every state transition, and the shared displayed-state oracle are intentional protocol choices that must be stated alongside any results. Follow-up calibrated-quantifier feedback should use held-out colors/examples and matched budgets rather than fit and evaluate on the same anchors.
