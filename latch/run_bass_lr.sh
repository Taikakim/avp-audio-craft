#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: GHOST-NOTE (created 2026-10-16)
# Owner's ask (2026-10-16): "our LRs have been quite high ... try 1e-3 and 1e-4 for something we know steers well like the bass or mid head. Log interesting things, EMA at maybe one epoch
# length, save every checkpoint." Bass head, modular trainer + Schedule-Free, d512 depth 8, constant lr after 1 epoch warmup, 10 epochs, grad clip 1.0.
# Arms: B3 lr 1e-3, B4 lr 1e-4, B2 lr 1e-2 (reference: the ceiling found on the air head; bass never ran under the modular trainer, so the two low-lr arms need a same-recipe control).
# Each epoch saves EMA half-life 1 ep (main ep<N>.pt), EMA 0.25 ep, and online (Schedule-Free average) weights. Full tiered telemetry (per-layer norms, distance from init, trajectory)
# goes to wandb in OFFLINE mode (nothing leaves the machine; `wandb sync` later if wanted). Runs after run_air_slow.sh; run_air_nosf.sh waits for /tmp/air_bass.done (written only if every arm exits 0).
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT
until [ -f /tmp/air_slow.done ]; do sleep 120; done
COMMON="--feature rms_energy_bass --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 10 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --wandb --wandb-project sa3-latch-bass-lr --log-every 20 --layer-every 100"
ARMS=(
"B3_bass_d512_lr1e-3|$COMMON --lr 1e-3"
"B4_bass_d512_lr1e-4|$COMMON --lr 1e-4"
"B2_bass_d512_lr1e-2|$COMMON --lr 1e-2"
)
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done
  mkdir -p "$OUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s)
  "$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
  last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
done
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
"$SAO/.venv/bin/python" "$SAO/eval/bass_epoch_sweep.py" --dirs "$OUT"/B3_* "$OUT"/B4_* "$OUT"/B2_* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
grep -qE "rc=[1-9]" "$OUT/SUMMARY.tsv" || echo BASS DONE > /tmp/air_bass.done
