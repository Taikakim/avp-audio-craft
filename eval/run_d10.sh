#!/usr/bin/env bash
# Owner: CONTINUITY (created 2026-11-03)
# run_d10.sh -- EXPERIMENTS D10: GPU turn for 42 renders (about 10 min), then scoring on CPU. Resumable.
set -u
SAO=/home/kim/Projects/SAO; cd "$SAO" || exit 2
LOG=/home/kim/sao_runs/d10_melody_intermittency_20261103.log; exec >> "$LOG" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
until vram_free && KIND=batch NOTE="D10 melody intermittency, 42 renders, about 10 min" Misc/gpu_guard.sh acquire CONTINUITY $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1' EXIT
echo "$(date '+%F %T') GPU acquired"
.venv/bin/python eval/d10_melody_intermittency.py render; rc=$?; echo "$(date "+%F %T") render rc=$rc"
Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1
.venv/bin/python eval/d10_melody_intermittency.py score; rc=$?; echo "$(date "+%F %T") score rc=$rc"
echo "$(date '+%F %T') ALL DONE"
