# ColorRef Ablations — Handoff (2026-05-20)

Past chat context: [ColorRef ablations session](09fb07af-61b8-4f6d-9000-d7913ee1ede5)

---

## Where we are

All four GPU-intensive **run** stages are DONE.
Three of the four **comparison/report** stages still need to be run (CPU-only, no GPU needed).
Step 4 (ICL game runs) still needs GPU.

---

## Status by step

| Step | Runs | Compare / Report |
|------|------|-----------------|
| §4.1 Teacher-pair visualization | ✅ done | ✅ done (`reports/comparisons/teacher_pair_visualization/`) |
| §4.2 Convergence sweep | ✅ done (t=1,2,5,7,10 × 1000 ex) | ⚠️ **STALE** — ran before t=5/7/10 finished; only covers t=1,2,3 |
| §4.3 Information budget | ✅ done (7 conditions × 1000 ex) | ❌ not run yet |
| §4.4 ICL calibration | ✅ contexts built (k=2/4/8 × 3 modes) | ❌ **game runs not started yet** |
| §4.5 Final polish report | — | ❌ not run yet |

---

## Exact commands to run (in order)

### 1. Re-run convergence comparison (CPU, ~2 min)
```bash
uv run python scripts/compare_convergence.py \
  --run_dirs runs/*convergence_axis_c3* runs/*feedback_axis_c3_main_qwen3_14b* \
  --out_dir reports/comparisons/convergence_sweep
```
- Baseline for comparison: `runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_...` (c3, t=3 default)
- Output: `reports/comparisons/convergence_sweep/combined_report.md` + figures

### 2. Run information-budget comparison (CPU, ~2 min)
```bash
uv run python scripts/compare_information_budget.py \
  --run_dirs runs/*budget_axis* \
  --out_dir reports/comparisons/information_budget
```
- 7 conditions already run; budget_metrics.parquet present in each run dir

### 3. ICL game runs (GPU required — H100, ~3–4 h total)

ICL contexts are already built in `data/icl_contexts/`:
- `main_1000_{random,regime_matched,text_similar}_k{2,4,8}.parquet`

Run ICL one-shot experiments:
```bash
uv run python scripts/run_icl_oneshot.py \
  --contexts_dir data/icl_contexts \
  --modes random regime_matched text_similar \
  --ks 2 4 8 \
  --out_dir runs
```

Run ICL feedback-game experiments:
```bash
uv run python scripts/run_icl_feedback_game.py \
  --contexts_dir data/icl_contexts \
  --base_config configs/experiments/feedback_axis_c3_main_qwen3_14b.yaml \
  --modes random regime_matched text_similar \
  --ks 2 4 8 \
  --out_dir runs
```

Then compare:
```bash
uv run python scripts/compare_icl.py \
  --run_dirs runs/*icl* \
  --baseline_run runs/20260517_201025_feedback_axis_c3_main_qwen3_14b_* \
  --out_dir reports/comparisons/icl_calibration
```

### 4. Final polish report (CPU, ~1 min)
```bash
uv run python scripts/polish_final_ablations.py \
  --reports_dir reports/comparisons \
  --out_dir reports/final_ablations
```

---

## Key run directories

| Purpose | Run dir (under `runs/`) |
|---------|------------------------|
| Baseline axis c3 14B (used in ALL comparisons) | `20260517_201025_feedback_axis_c3_main_qwen3_14b_*` |
| Convergence t=1 | `20260520_010549_convergence_axis_c3_t1_*` |
| Convergence t=2 | `20260520_011437_convergence_axis_c3_t2_*` |
| Convergence t=5 | `20260520_012615_convergence_axis_c3_t5_*` |
| Convergence t=7 | `20260520_015531_convergence_axis_c3_t7_*` |
| Convergence t=10 | `20260520_023551_convergence_axis_c3_t10_*` |
| Budget rounds1_c1_budget1 | `20260520_022135_budget_axis_rounds1_c1_*` |
| Budget rounds1_c2_budget2 | `20260520_023200_budget_axis_rounds1_c2_*` |
| Budget rounds1_c3_budget3 | `20260520_013005_budget_axis_rounds1_c3_*` |
| Budget rounds2_c1_budget2 | `20260520_024154_budget_axis_rounds2_c1_*` |
| Budget rounds2_c2_budget4 | `20260520_025726_budget_axis_rounds2_c2_*` |
| Budget rounds3_c1_budget3 | `20260520_014125_budget_axis_rounds3_c1_*` |
| Budget rounds3_c3_budget9 | `20260520_020116_budget_axis_rounds3_c3_*` |

---

## Key source modules created this session

| Module | Purpose |
|--------|---------|
| `src/colorref/stopping.py` | Convergence metrics (best-so-far, plateau, regression rate) |
| `src/colorref/budget.py` | `BudgetedTeacher` — enforces total constraint budget across turns |
| `src/colorref/icl.py` | ICL context retrieval (random / regime-matched / text-similar) + prompt formatting |
| `src/colorref/pairing.py` | Oracle↔LLM teacher alignment, feedback-precision scoring |
| `src/colorref/trajectory_pair_viz.py` | Overlay (default): single a\*–b\* + attached L* strip + stacked full-width feedback rows (paper-style column); `split` = two LAB panels |

---

## Environment

- Python env: `uv` venv (already set up, all deps installed incl. scikit-learn, matplotlib, pandas, vllm)
- Model: `Qwen/Qwen3-14B` (vLLM, fp16, fits on single H100 80 GB)
- GPU: single H100 — load model once per script invocation; scripts are sequential-friendly
- Data: `data/main_1000.parquet` (1000 eval examples), `data/train_pool.parquet` (ICL pool)
