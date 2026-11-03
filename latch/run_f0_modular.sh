#!/usr/bin/env bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep
# Owner: WINTERMUTE (created 2026-11-03)
# run_f0_modular.sh -- EXPERIMENTS E2: the lead f0 head retrained under the modular recipe that gave same_chroma about 10x the steering (E13 C3), to see whether
# it also moves the temporal ceiling found in D16 (the current head is AdamW, d256, depth 4). Same data, voiced weighting and source-track split as val30_f0_other.
# A 20-step smoke test first. Stops under 20 GB free. About 1 h.
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/__f0/f0_modular_2026-11-03
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR="$OUT"
DATA="--feature f0_other --target-source npz --standardize --voiced-field f0_other_voiced_ts --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.15 --val-seed 0 --val-group-by source_track --seed 0 --num-workers 8 --loss smooth_l1"
LOGS="--save-every-epoch --save-online --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 12 --wandb --wandb-project sa3-latch-f0 --log-every 20 --layer-every 100 --step-log --layer-log 50 --log-grad-noise 100 --log-grad-noise-t 100 --grad-noise-t-bins 5 --val-t-bins 10"
C3="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --batch-size 8 --grad-accum 4 --lr 1e-3 --dim 512 --depth 8"
until KIND=batch NOTE="E2 f0 head retrain, about 1 h, ask if you need the card" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
cd "$SAO" || exit 1
"$PY" "$TRAIN" $DATA $LOGS $C3 --max-steps 20 --save-dir "$OUT/_smoke" --run-name smoke > "$OUT/smoke.log" 2>&1
echo "$(date '+%F %T') smoke rc=$?"
if [ "$(df --output=avail -BG "$OUT" | tail -1 | tr -dc 0-9)" -lt 20 ]; then echo "under 20 GB free, stopping"; exit 1; fi
"$PY" "$TRAIN" $DATA $LOGS $C3 --save-dir "$OUT/E2_c3_d512_L8" --run-name E2_c3_d512_L8 > "$OUT/train.log" 2>&1
echo "$(date '+%F %T') train rc=$?"
echo "$(date '+%F %T') ALL DONE"
