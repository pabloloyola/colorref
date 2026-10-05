#!/usr/bin/env bash
# Run v2 bandwidth ablation (B1-B4) sequentially on one GPU.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=reports/bandwidth_batch_$(date -u +%Y%m%d_%H%M%S).log
mkdir -p reports

CONFIGS=(
  feedback_axis_c1_main_qwen3_14b
  feedback_axis_c2_main_qwen3_14b
  feedback_template_c2_main_qwen3_14b
  feedback_template_c3_main_qwen3_14b
)

echo "Logging to $LOG"
exec > >(tee -a "$LOG") 2>&1

for cfg in "${CONFIGS[@]}"; do
  echo "======== $(date -u +%H:%M:%S) START $cfg ========"
  uv run python scripts/run_feedback_game.py --config "configs/experiments/${cfg}.yaml"
  # Find newest matching run dir
  run_dir=$(ls -td runs/*"${cfg}"* 2>/dev/null | head -1)
  if [[ -z "${run_dir:-}" ]]; then
    echo "ERROR: no run dir found for $cfg"
    exit 1
  fi
  echo "Evaluating $run_dir"
  uv run python scripts/recompute_metrics.py --run_dir "$run_dir" --overwrite
  echo "======== $(date -u +%H:%M:%S) DONE $cfg -> $run_dir ========"
done

echo "======== $(date -u +%H:%M:%S) BATCH COMPLETE ========"
