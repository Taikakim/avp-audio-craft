#!/usr/bin/env bash
# local_traj_sketch.sh — CONTINUITY 2026-08-18, Kim direct: "train a small rank 8 or 16 adapter and
# save every step for 1000 or even 10,000 steps and see how the trajectory really is."
#
# Two arms of the sanity16 recipe (LoRA r16 a16, lr 1e-4, T256, AdamW, bf16, goa latents_sa3),
# differing ONLY in effective batch — the axis the AdamW-sweep forensics point at (bs1/bs4 arms sit
# on the 1/sqrt(n) random-walk floor, the bs8 twins drift):
#   bs1     : 1 crop per optimizer step, 10 000 steps           (the sweep's regime)
#   accum8  : 8 crops per optimizer step via grad-accum, 2 000 steps  (the healthy regime; same
#             data per step as the bs8 arms, 8x fewer optimizer steps per epoch)
# Every optimizer step's update+gradient is CountSketched (scripts/trajectory_sketch.py) — the
# whole Gram of the walk from ~4 KB/step — plus trainable-only ckpts every 100 steps.
# Sequential on the local card; caller holds the GPU mutex.
set -uo pipefail
VENV=/home/kim/Projects/SAO/.venv; CODE=/home/kim/Projects/SAO/stable-audio-3
ROOT=${ROOT:-/home/kim/Projects/SAO/runs/traj_sketch}
LAT=/home/kim/Projects/latents_sa3
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONPATH="${CODE}:${PYTHONPATH:-}"
cd "${CODE}" || exit 1
COMMON="--model medium-base --encoded_dir ${LAT} --frames 256 --batch_size 1 --adapter_type lora --rank 16 --lora_alpha 16 --optimizer adamw --lr 1e-4 --base_precision bf16 --no_demos --num_workers 0 --checkpoint_every 100000 --traj-ckpt-every 5 --traj-ckpt-dense-until 500"
declare -A ARMS=( [goa_r16_bs1_lr1e4]="--steps 10000 --accumulate_grad_batches 1"
                  [goa_r16_accum8_lr1e4]="--steps 2000 --accumulate_grad_batches 8" )
for ARM in goa_r16_bs1_lr1e4 goa_r16_accum8_lr1e4; do
  D="${ROOT}/${ARM}"; mkdir -p "${D}"
  [ -f "${D}/traj/done.json" ] && { echo "[traj] SKIP ${ARM} (done)"; continue; }
  echo "[traj] === ${ARM} $(date -Iseconds)"
  # shellcheck disable=SC2086
  "${VENV}/bin/python" scripts/train_lora.py ${COMMON} ${ARMS[$ARM]} --save_dir "${D}/run" --traj-sketch-dir "${D}/traj" > "${D}/train.log" 2>&1
  rc=$?; echo "[traj] ${ARM} rc=${rc} $(date -Iseconds)"
  cat > "${D}/run_meta.json" <<META
{"run": "${ARM}", "created": "$(date -Iseconds)", "exit_code": ${rc},
 "purpose": "Step-resolution weight trajectory of the sanity16 LoRA recipe on goa, to see whether constant-LR AdamW at small effective batch random-walks (uncorrelated steps, path efficiency at the 1/sqrt(n) floor) or drifts, and how the picture changes at 8x the effective batch. Kim direct 2026-08-18.",
 "recipe": {"adapter": "lora", "rank": 16, "alpha": 16, "lr": 1e-4, "optimizer": "adamw", "precision": "bf16", "frames": 256, "batch_size": 1, "extra": "${ARMS[$ARM]}"},
 "dataset": {"latents": "${LAT}", "corpus": "goa (latents_sa3, T4096 crops, random T256 crops, json prompt captions)"},
 "artifacts": {"trajectory": "${D}/traj (CountSketch rows + per-tensor norms + coord subsample + ckpt/step*.pt)", "log": "${D}/train.log"},
 "recorder": "stable-audio-3/scripts/trajectory_sketch.py", "script": "lumi/local_traj_sketch.sh",
 "result": null, "kim_feedback": null}
META
done
echo "[traj] all done $(date -Iseconds)"
