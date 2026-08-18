#!/usr/bin/env bash
# local_traj_sketch_fusion.sh — the optimizer control for local_traj_sketch.sh (C 2026-08-18): same
# recipe/data at bs1, --optimizer fusion (NS5/NorMuon/SF). The healthy LUMI twins were Fusion at bs8;
# the broken sweep AdamW at bs1/4 — this arm + the AdamW bs1 arm separate optimizer from batch on the
# same card, same data order (seed 42 both). 5000 steps (~1 h). Chained after the AdamW arms.
set -uo pipefail
VENV=/home/kim/Projects/SAO/.venv; CODE=/home/kim/Projects/SAO/stable-audio-3
ROOT=${ROOT:-/home/kim/Projects/SAO/runs/traj_sketch}; LAT=/home/kim/Projects/latents_sa3
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONPATH="${CODE}:${PYTHONPATH:-}"
cd "${CODE}" || exit 1
ARM=goa_r16_bs1_fusion_lr1e4; D="${ROOT}/${ARM}"; mkdir -p "${D}"
[ -f "${D}/traj/done.json" ] && { echo "[traj] SKIP ${ARM}"; exit 0; }
echo "[traj] === ${ARM} $(date -Iseconds)"
"${VENV}/bin/python" scripts/train_lora.py --model medium-base --encoded_dir ${LAT} --frames 256 --batch_size 1 --adapter_type lora --rank 16 --lora_alpha 16 --optimizer fusion --lr 1e-4 --base_precision bf16 --no_demos --num_workers 0 --checkpoint_every 100000 --steps 5000 --accumulate_grad_batches 1 --save_dir "${D}/run" --traj-sketch-dir "${D}/traj" --traj-ckpt-every 5 --traj-ckpt-dense-until 500 > "${D}/train.log" 2>&1
rc=$?; echo "[traj] ${ARM} rc=${rc} $(date -Iseconds)"
cat > "${D}/run_meta.json" <<META
{"run": "${ARM}", "created": "$(date -Iseconds)", "exit_code": ${rc},
 "purpose": "Optimizer control for the step-resolution trajectory pair (bs1 vs accum8 AdamW): same recipe/data at bs1 with FusionOpt (NS5/NorMuon/SF). Separates 'AdamW geometry' from 'small batch' as the cause of the AdamW-sweep signature (random-walk path efficiency + rank-1-dominant deltas).",
 "recipe": {"adapter": "lora", "rank": 16, "alpha": 16, "lr": 1e-4, "optimizer": "fusion", "precision": "bf16", "frames": 256, "batch_size": 1, "steps": 5000},
 "dataset": {"latents": "${LAT}", "corpus": "goa (latents_sa3, json prompt captions)"},
 "artifacts": {"trajectory": "${D}/traj", "log": "${D}/train.log"},
 "recorder": "stable-audio-3/scripts/trajectory_sketch.py", "script": "lumi/local_traj_sketch_fusion.sh",
 "result": null, "kim_feedback": null}
META
