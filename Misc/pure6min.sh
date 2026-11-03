#!/bin/bash
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
wait_gpu(){ for i in $(seq 1 40); do u=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiE 'used memory \(b\): [0-9]+' | grep -oE '[0-9]+'); [ "${u:-0}" -lt 2000000000 ] && return; sleep 6; done; }
cd /home/kim/Projects/SAO/stable-audio-3 || exit 1
echo "=== PURE 6-min longform, NO density head $(date +%H:%M) ==="; wait_gpu
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $SA3PY scripts/longform_render.py \
  --model medium-base --prompt "goa trance, psychedelic, driving, 145 bpm" \
  --duration 360 --window-sec 30 --overlap-sec 5 -o /home/kim/longform_pure_6min.wav 2>&1 \
  | grep -iE 'longform|drift|error|Trace|OutOfMemory' | tail -8
echo "RESULT size: $(ls -la /home/kim/longform_pure_6min.wav 2>/dev/null | awk '{printf "%.1fMB", $5/1048576}')"
echo "PURE6_DONE"
