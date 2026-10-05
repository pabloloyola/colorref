#!/usr/bin/env bash
# Recompute v2 metrics for all v1 Qwen3-14B runs (no LLM inference).
set -euo pipefail
cd "$(dirname "$0")/.."

RUNS=(
  runs/20260516_143421_oneshot_main_qwen3_14b_main_1000
  runs/20260516_121822_feedback_minimal_main_qwen3_14b_minimal_oracle_main_1000
  runs/20260516_123429_feedback_axis_main_qwen3_14b_axis_oracle_main_1000
  runs/20260516_141639_feedback_template_main_qwen3_14b_template_oracle_main_1000
  runs/20260516_150504_feedback_llm_teacher_pilot_qwen3_14b_llm_teacher_debug_400
)

for run_dir in "${RUNS[@]}"; do
  echo "=== $run_dir ==="
  uv run python scripts/recompute_metrics.py --run_dir "$run_dir" --overwrite
done

echo "Done. Regenerate teacher_variants comparison separately if needed."
