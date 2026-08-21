#!/usr/bin/env bash
# local_traj_sketch_damping.sh — C 2026-08-19, Kim: "write the code for those muon damping tests".
# Three arms after local_traj_sketch_fusion.sh, same recipe/seed/data (bs1, Fusion, LoRA r16, goa):
#   fusion_cos      --fusion-decay cosine          (in-optimizer cosine to 0 over the 5000 steps)
#   fusion_snr      --fusion-snr row               (per-neuron SNR gate on the spectral step)
#   fusion_cos_snr  both
# The plain fusion arm is the control; the sketch reader compares them in one report.
set -uo pipefail
VENV=/home/kim/Projects/SAO/.venv; CODE=/home/kim/Projects/SAO/stable-audio-3
ROOT=${ROOT:-/home/kim/Projects/SAO/runs/traj_sketch}; LAT=/home/kim/Projects/latents_sa3
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONPATH="${CODE}:${PYTHONPATH:-}"
cd "${CODE}" || exit 1
declare -A DAMP=( [goa_r16_bs1_fusion_cos]="--fusion-decay cosine"
                  [goa_r16_bs1_fusion_snr]="--fusion-snr row"
                  [goa_r16_bs1_fusion_cos_snr]="--fusion-decay cosine --fusion-snr row" )
for ARM in goa_r16_bs1_fusion_cos goa_r16_bs1_fusion_snr goa_r16_bs1_fusion_cos_snr; do
  D="${ROOT}/${ARM}"; mkdir -p "${D}"
  [ -f "${D}/traj/done.json" ] && { echo "[traj] SKIP ${ARM}"; continue; }
  echo "[traj] === ${ARM} $(date -Iseconds)"
  # shellcheck disable=SC2086
  "${VENV}/bin/python" scripts/train_lora.py --model medium-base --encoded_dir ${LAT} --frames 256 --batch_size 1 --adapter_type lora --rank 16 --lora_alpha 16 --optimizer fusion ${DAMP[$ARM]} --lr 1e-4 --base_precision bf16 --no_demos --num_workers 0 --checkpoint_every 100000 --steps 5000 --accumulate_grad_batches 1 --save_dir "${D}/run" --traj-sketch-dir "${D}/traj" --traj-ckpt-every 50 --traj-ckpt-dense-until 100 > "${D}/train.log" 2>&1
  rc=$?; echo "[traj] ${ARM} rc=${rc} $(date -Iseconds)"
  cat > "${D}/run_meta.json" <<META
{"run": "${ARM}", "created": "$(date -Iseconds)", "exit_code": ${rc},
 "purpose": "Muon damping test (Kim 2026-08-19): does giving the magnitude-blind NS5->NorMuon step a brake (cosine decay / per-neuron SNR gate / both) turn the bs1 diffusion into convergence? Control = goa_r16_bs1_fusion_lr1e4 (same seed/data).",
 "recipe": {"adapter": "lora", "rank": 16, "alpha": 16, "lr": 1e-4, "optimizer": "fusion", "damping": "${DAMP[$ARM]}", "precision": "bf16", "frames": 256, "batch_size": 1, "steps": 5000},
 "dataset": {"latents": "${LAT}", "corpus": "goa (latents_sa3, json prompt captions)"},
 "artifacts": {"trajectory": "${D}/traj", "log": "${D}/train.log"},
 "recorder": "stable-audio-3/scripts/trajectory_sketch.py", "script": "lumi/local_traj_sketch_damping.sh",
 "result": null, "kim_feedback": null}
META
done
echo "[traj] damping arms done $(date -Iseconds)"
