#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-14)
# Air-RMS head bracket (Kim 2026-10-14): the production rms_energy_air head (AdamW, 20 ep) glitches at the large guidance weights and changes content.
# Retrain under the modular optimiser: Shampoo whitening, Schedule-Free, Muon on every 2-D tensor, overtraining-aware wd, warmup 0.25 ep, radial-brake damping
# armed after epoch 1, EMA half-life 0.5 ep, batch 16 x accum 2 (= 32; b32 at dim512/depth8 OOMs the 16 GB card), 1000 optimizer steps (~6.25 ep of 160 steps).
# Each arm takes the GPU through gpu_guard as GHOST-NOTE; resumable via SUMMARY.tsv. Run:  setsid nohup latch/run_air_bracket.sh > /tmp/air_bracket_train.log 2>&1 &
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-14
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
COMMON="--feature rms_energy_air --latent-dir /home/kim/Projects/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --batch-size 16 --grad-accum 2 --max-steps 1000 --epochs 10 --save-every-epoch"
MOD="--optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 0.25 --mod-late-from-epochs 1 --mod-radial-brake 0.8 --ema-halflife-epochs 0.5"
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
ARMS=(
"A1_d512dp8_lr1e-1|$MOD --lr 1e-1 --dim 512 --depth 8"
"A2_d512dp8_lr1e-2|$MOD --lr 1e-2 --dim 512 --depth 8"
"A3_d512dp8_lr5e-2|$MOD --lr 5e-2 --dim 512 --depth 8"
"A4_d512dp8_lr1e-3|$MOD --lr 1e-3 --dim 512 --depth 8"
"A5_d256dp8_lr1e-2|$MOD --lr 1e-2 --dim 256 --depth 8"
"A6_d512dp8_lr1e-2_soap|${MOD/--mod-whitening shampoo/--mod-whitening soap} --lr 1e-2 --dim 512 --depth 8 --batch-size 8 --grad-accum 4"
"A8_d512dp8_lr1.0|$MOD --lr 1.0 --dim 512 --depth 8"
"A7_d512dp8_lr1e-2_mona_fusion|--optimizer fusion --components ns5,normuon,sf,shampoo,mona --lr 1e-2 --dim 512 --depth 8 --ema-halflife-epochs 0.5 --batch-size 8 --grad-accum 4"
)
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && { echo "[air] skip $name"; continue; }
  until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do echo "[air] GPU busy, waiting"; sleep 120; done
  mkdir -p "$OUT/$name"; echo "[air] start $name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $COMMON $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s)
  "$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  last=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  printf '%s\t%s\t%s\t%s\trc=%s\t%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" "$rest" >> "$OUT/SUMMARY.tsv"
done
echo "[air] ALL DONE"
