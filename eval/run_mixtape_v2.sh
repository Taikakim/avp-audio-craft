#!/usr/bin/env bash
set -euo pipefail
SAO=/home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SAO"

echo "Acquiring GPU lock..."
until KIND=batch NOTE="Mixtape track pool v2 re-render" "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do sleep 5; done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

"$SAO/.venv/bin/python" -u "$SAO/eval/mixtape_track_pool_v2.py"

"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1
trap - EXIT
echo "Execution finished successfully."
