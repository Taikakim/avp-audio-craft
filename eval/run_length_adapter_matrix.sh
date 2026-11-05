#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "Starting Sequence Length x Adapter Weight Matrix Execution"
echo "=========================================================="

PY="/home/kim/Projects/SAO/.venv/bin/python"
MIR_PY="/home/kim/Projects/mir/mir/bin/python"

# 1. Generate 36 audio clips
$PY /home/kim/Projects/SAO/eval/generate_length_adapter_matrix.py

# 2. Build and publish dashboard to DreamHost
/home/kim/Projects/SAO/eval/publish_length_adapter_matrix.sh

# 3. Run automated analytics across the generated clips
echo "=== Running Quantitative Analytics ==="
$MIR_PY /home/kim/Projects/SAO/eval/analyze_length_matrix_p07.py \
    --wav-dir /run/media/kim/Mantu/sa3_lora_runs/length_adapter_matrix/wav \
    --out-json /run/media/kim/Mantu/sa3_lora_runs/length_adapter_matrix/analytics.json \
    --all

echo "=========================================================="
echo "Execution and Publishing Complete!"
echo "Dashboard: https://aavepyora.online/files/evals/length_adapter_matrix.html"
echo "=========================================================="
