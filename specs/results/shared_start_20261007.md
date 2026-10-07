# Completed shared-start control — 2026-10-07

Source: the production summary pasted by the user for
`runs/20261007_043619_593902_shared_start_interface_study_a100_40gb`.
The coding workspace has not independently loaded the production checkpoints.
These are actual user-reported A100 results, separate from simulated CPU tests.

## Completion and comparison

- Qwen/Qwen3-14B, HF transformers, A100 40 GB, bfloat16, thinking disabled,
  temperature zero, maximum 64 output tokens.
- 64 examples (16 per regime), three interfaces, three fixed revisions.
- Completed 192/192 games, generated and parsed 576/576 revisions.
- No parse failures; first-revision and full-trajectory common cohorts both N=64.
- Common mean starting projected error: 41.955 ΔE76. Every example receives the
  same first oracle message/directions across interfaces.
- Later corrections are adaptive and can differ. All conditions use displayed
  uint8 sRGB states for feedback and subsequent prompts.

| Interface | First revised ΔE | First gain | First satisfaction | First alignment (N) | Final ΔE | Best ΔE | Final–best gap |
|---|---:|---:|---:|---:|---:|---:|---:|
| HEX | 32.099 | 9.856 | 0.888 | 0.717 (64) | 22.781 | 15.155 | 7.626 |
| Plain LAB | 38.286 | 3.669 | 0.823 | 0.638 (61) | 35.275 | 26.385 | 8.890 |
| LAB with legend | 32.582 | 9.373 | 0.906 | 0.773 (63) | 23.161 | 21.028 | 2.133 |

First constraint satisfaction uses all 64 cases. Alignment excludes zero-length
vectors, so its denominators differ. Native final errors are 22.781, 35.589,
and 23.325 respectively; projected/displayed error remains primary.

### Paired error differences

Right minus left; a negative value favors the right interface. Intervals below
are the reported paired regime-stratified 95% percentile bootstrap intervals.
Because starts match, gain differences are the negatives of error differences.
Available-pair and common-triplet cohorts agree because all outputs parsed.

| Comparison | First revision ΔE difference [95% interval] | Final revision ΔE difference [95% interval] |
|---|---:|---:|
| HEX → plain LAB | +6.187 [0.845, 11.889] | +12.494 [6.570, 18.435] |
| Plain LAB → legend LAB | -5.705 [-11.444, 1.406] | -12.114 [-18.035, -5.489] |
| HEX → legend LAB | +0.483 [-4.773, 6.562] | +0.380 [-4.848, 6.294] |

## What this supports

1. Plain LAB's higher error persists when initial guesses are held fixed.
   The earlier whole-pipeline gap therefore cannot be attributed solely to
   different initial name-to-color predictions under this protocol.
2. The axis legend substantially reduces the final plain-LAB error gap.
   The primary first-revision improvement is less certain: its interval includes
   zero. Keep primary and secondary endpoints explicit.
3. HEX and legend LAB have close mean endpoints, but these intervals do not
   establish equivalence or noninferiority. No equivalence margin was specified.
4. The smaller legend final–best gap does not alone demonstrate better control.
   HEX reaches a lower mean best error (15.155 versus 21.028) while ending at
   similar error. This suggests a possible accuracy/trajectory tradeoff, whose
   mechanism requires paired trajectory inspection. Best-so-far selection here
   uses the target and is not an available deployment stopping rule by default.
5. Directional compliance is useful but does not guarantee target localization;
   correction size and stopping remain separate issues.

Findings are conditional on the HEX-derived starting-state policy, one model,
and the prompt/interface intervention. All cases parsed here, but bootstrap
intervals still concern variation across this sampled cohort, not generation
randomness or unrestricted population generalization. The three-round forced
protocol differs from the original paper's early stopping.

## Drift and projection observations

Final convergence counts (ΔE ≤ 5) are 4/64 HEX, 1/64 plain LAB, and 7/64 legend
LAB. These small counts do not establish a convergence advantage.
Zero-movement revisions are 0/192, 20/192, and 9/192 respectively.

Mean generated-state projection errors are 0, 0.783, and 0.937; projection
ΔE > 1 counts are 0/192, 13/192, and 25/192 respectively. The legend does not
uniformly reduce projection cost. These are this run's values, not the previous
whole-pipeline study's projection results.

One supplied starting state was initially within ΔE ≤ 5. All three interfaces
lost convergence, with first movement 31.959/51.304/37.402 ΔE and first gain
-27.646/-47.017/-33.298 for HEX/plain LAB/legend. There are no first messages
without constraints in this run. The close case therefore received a nonempty
oracle correction; its exact direction/count and raw responses are needed
before identifying a cause. It is one diagnostic case, not an estimate of a
general near-target failure rate.

## Next CPU-only check

The inspector validates the frozen plan and saved checkpoints, then prints
initially converged cases by default. It reports description, target/start,
each interface's first prompt, errors by turn, feedback constraints, raw
responses, projected/native states, and generation diagnostics. It neither
loads a model nor rewrites scientific outputs.

```bash
git pull --ff-only origin refactor/quantifier-calibration

uv run python scripts/inspect_shared_start_cases.py \
  --run runs/20261007_043619_593902_shared_start_interface_study_a100_40gb
```

This production summary implies one selected example and three trajectories.
To inspect another example, supply `--example-id ID`. Keep raw parse failures
and unknown diagnostics as recorded; do not repair outputs.

After inspecting this case, the next interventions should distinguish
stopping at the existing convergence threshold from selecting magnitude words
by remaining distance. A magnitude controller must be calibrated and evaluated
on disjoint examples with matched feedback budgets; it has not yet demonstrated
downstream creative-editing benefits. Machel's teacher concerns still require
restricted/unrestricted wording and zero-/few-shot teacher controls, and target
ambiguity remains unresolved.
