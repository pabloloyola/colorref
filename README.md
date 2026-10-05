# ColorRef

ColorRef is an interactive reference-game framework for studying how language
models map color descriptions to perceptual color space, follow directional
feedback, and generate feedback for another model.

This repository is being restored from the EMNLP 2026 experimental snapshot.
The original experiment code is preserved on `main`; portability and new
experiments are developed through reviewed branches.

## Repository layout

- `src/colorref/`: game logic, teachers, metrics, geometry, and visualization
- `scripts/`: experiment runners and analysis entry points
- `configs/experiments/`: reproducible experiment configurations
- `configs/prompts/`: model and teacher prompts
- `tests/`: CPU unit tests
- `HANDOFF.md`: historical May 2026 experiment handoff

Generated datasets, model caches, runs, and reports are intentionally not stored
in GitHub.

## Setup

Requirements:

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- For local inference: Linux, CUDA, and an NVIDIA GPU

```bash
git clone https://github.com/pabloloyola/colorref.git
cd colorref
uv sync --frozen --group dev
```

## Download the data

The immutable dataset snapshot is stored in the private Hugging Face dataset
repository
[`paablo111/colorref-data`](https://huggingface.co/datasets/paablo111/colorref-data).

Authenticate once:

```bash
uv run hf auth login
```

For tests and the GPU smoke run, download only the evaluation subset:

```bash
uv run python scripts/download_data.py --profile smoke
```

To restore every archived dataset artifact:

```bash
uv run python scripts/download_data.py --profile full
```

The downloader pins Hugging Face commit
`9270f1bee4fe28ed79109bd09efc3bb5f2add925` by default.

## CPU verification

```bash
uv run --frozen pytest -q
```

The unit suite does not load an LLM or require a GPU.

## A100 40 GB smoke test

The portable smoke configuration uses Qwen3-14B in bfloat16, batch size 1,
one feedback round, and four examples. It does not assume the legacy
`/rit-as-pvc` filesystem.

```bash
nvidia-smi
uv run python scripts/run_feedback_game.py \
  --config configs/experiments/smoke_a100_40gb_qwen3_14b.yaml
```

Outputs are written under `runs/`. A successful smoke run should produce
`games/trajectories.parquet`, `games/feedback.parquet`,
`metrics/per_example.parquet`, and a report within its timestamped run
directory.

Do not begin a full experiment sweep until the CPU suite and this smoke test
both pass.

## Direct CIELAB control

The direct-LAB condition tests whether results depend on asking the model to
encode colors as hexadecimal strings. It uses the same game and teacher logic,
but the guesser emits `LAB(L, a, b)` coordinates:

```bash
uv run python scripts/run_feedback_game.py \
  --config configs/experiments/smoke_a100_40gb_qwen3_14b_lab.yaml
```

For this condition, ΔE is computed from the model's native LAB coordinates.
The trajectory also stores a clipped sRGB/hex projection for visualization and
HSV-derived diagnostics, plus `lab_projection_delta_e` so out-of-gamut outputs
are not silently hidden. Legacy configurations without an `interface` section
continue to use hexadecimal output.

## Data and output policy

- GitHub contains source, tests, prompts, and experiment configurations.
- Hugging Face contains immutable input data.
- `runs/` and `reports/` are local generated artifacts.
- Model weights remain in the standard Hugging Face cache or a user-provided
  `HF_HOME`.

## Current scientific roadmap

The next experimental phase will address expert feedback by adding direct
perceptual-coordinate controls, ambiguity-aware evaluation, stricter teacher
relay conditions, few-shot teacher baselines, and a calibrated study of
magnitude expressions such as “a little” and “much.”
