# Gemma 4 12B magnitude replication

Use `google/gemma-4-12B-it` at revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`, BF16, greedy decoding,
thinking disabled, 64 new tokens and text-only inputs. The official model
interface is AutoProcessor / AutoModelForMultimodalLM. Qwen remains on the
causal loader. This is cross-family replication, not a controlled parameter
count or architecture comparison.

The parent is the completed Qwen 32-calibration/128-evaluation confirmation.
Preparation validates its frozen configuration and plan and verifies exact
plan identity after the model change. It reads no calibration or held-out
responses. Gemma generates its own 768 calibration responses and freezes its
own direction/wording medians before evaluating the same 2,108 cases under
bare, unfitted, calibrated and numeric arms (8,432 planned evaluation calls).
No Qwen medians or model outputs are transferred. Primary contrast remains
calibrated minus unfitted displayed-state target error, clustered by start.
Failed parsing remains in counts; no prompt repair or outcome-based model
selection. Interpretation remains conditional on these stimuli and policies.

First check that the installed Transformers exposes the architecture:

```bash
uv run python -c 'from transformers import AutoProcessor, AutoModelForMultimodalLM, Gemma4UnifiedForConditionalGeneration; print("Gemma loader available")'
```

If unavailable, update Transformers in the GPU environment before proceeding;
do not silently substitute a different loader/model or remote custom code.
CPU tests exercise routing, thinking settings, token slicing and frozen
stimulus identity with mocks; they do not validate real weights or VRAM.
The A100 smoke below must verify actual model loading and generation.

```bash
uv run python scripts/prepare_magnitude_replication.py \
  --parent-run runs/20261008_030403_354222_magnitude_confirmation_128_a100_40gb

time uv run python scripts/run_magnitude_control.py \
  --config data/confirmatory/magnitude_128_gemma/config.yaml --limit 24
```

Resume the printed Gemma run directory using `--resume RUN_DIRECTORY` after
the smoke. Do not launch another `--config` run to continue it. The same
strict parser and output budget remain in force even if Gemma's parse rate
differs. Keep memory available by running only one model process on the GPU.

Sources: https://huggingface.co/google/gemma-4-12B-it and
https://huggingface.co/docs/transformers/model_doc/gemma4_unified
