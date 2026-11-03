#!/bin/bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# goa5k r128 DoRA: shampoo-run recipe (modular Shampoo + multiplicative magnitudes + VADD + radial brake
# + SNR gate + delayed Schedule-Free) + melody-subspace loss K=5 on the v3 basis, on latents_sa3 (5,400 crops).
# 24 epochs x 337 steps = 8088 steps, ~8.5 h at ~3.8 s/step; checkpoint + demo milestone every 3 epochs.
# Launched by WINTERMUTE 2026-09-26 on request. Log: <run>/train.log
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
NAME=goa5k_r128_shampoo_subloss_k5_2026-09-26
OUT=/run/media/kim/Mantu/sa3_lora_runs
mkdir -p "$OUT/$NAME"
KIND=batch NOTE="W: overnight training $NAME (~8.5 h), not yieldable" Misc/gpu_guard.sh acquire WINTERMUTE $$ || { echo "GPU busy" >> "$OUT/$NAME/train.log"; exit 9; }
trap 'Misc/gpu_guard.sh release WINTERMUTE $$' EXIT
.venv/bin/python stable-audio-3/scripts/train_lora_modular.py \
  --encoded_dir /run/media/kim/Kosmos/latents/latents_sa3 --caption_probs '0,0.9,0.1' \
  --frames 256 --model medium-base --rank 128 --lora_alpha 128 --adapter_type dora-rows \
  --modular-magnitude-update multiplicative --var-dampening 1.15 --var-barrier-weight 0.08 --var-damp-opt \
  --modular-radial-brake 0.8 --modular-beta1 0.9 --modular-snr-gate \
  --subspace-loss-basis lumi/melody_subspace15_selective_v3.npz --subspace-loss-weight 5 \
  --name "$NAME" --output-dir "$OUT" --batch-size 16 --num-workers 10 --lr 3e-4 --warmup-steps 1000 \
  --optimizer modular --allow-uniform-lr --modular-lmo-poly cubic5 --modular-whitening shampoo \
  --modular-schedule-free --modular-sf-c-warmup 1000 --modular-sf-r 1.0 --modular-wd 0.02 --modular-wd-overtraining \
  --eval_demos --no-inline-demos --steps 8088 \
  --eval_milestones 1011 2022 3033 4044 5055 6066 7077 8088 --checkpoint_every 200000 \
  --purpose 'Shampoo-run recipe + melody-subspace loss (K=5, v3 basis) on the 5,400-crop goa set; 24 epochs overnight' \
  --hypothesis 'K=5 subspace upweighting (best of the earlier K-grid by metrics) adds melodic definition on top of the stabilised modular/Shampoo recipe' \
  >> "$OUT/$NAME/train.log" 2>&1
echo "exit rc=$?" >> "$OUT/$NAME/train.log"
