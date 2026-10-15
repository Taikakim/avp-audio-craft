#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15)
# Overnight air-RMS head runs at 4x the bracket length (4000 optimizer steps = 25 epochs of 160), Kim 2026-10-15: keep the lr>=5e-2 runs (which DIVERGED in epoch 1: loss 0.81 vs 0.076,
# then Shampoo's eigh failed on the NaN covariance) in check with the untapped damping, a doubled minibatch, or a halved Schedule-Free-unchecked window. Schedules are in EPOCHS so they scale with the
# run: warmup 1 ep (was 0.25), damping armed at 4 ep (was 1) or 2 ep ("halved"), EMA half-life 2 ep (was 0.5), cosine LR 17.5->25 (the 7->10 of a 10-epoch run), overtraining wd sqrt(epoch).
# New guards: --grad-clip 1.0 (SNR gate dropped: Kim, it behaved as a plain lr multiplier in the DoRA ablation), O2 tracks EMA half-lives 1/2/4 epochs in ONE run, b64 arms at lr 3e-2, eigh failure keeps the previous preconditioner. Waits for /tmp/air_chain.done, stops the render server for the GPU, restarts it at the end.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/air_head_2026-10-15_overnight
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
until [ -f /tmp/air_chain.done ]; do sleep 60; done
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
COMMON="--feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --max-steps 4000 --epochs 25 --save-every-epoch"
MOD="--optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --ema-halflife-epochs 2 --cosine-epochs 17.5 25"
ARMS=(
"O1_d256_lr5e-2_clip_late2|$MOD --mod-late-from-epochs 2 --grad-clip 1.0 --lr 5e-2 --dim 256 --depth 8 --batch-size 16 --grad-accum 2"
"O2_d256_lr1e-1_clip_late2_3ema|$MOD --mod-late-from-epochs 2 --grad-clip 1.0 --lr 1e-1 --dim 256 --depth 8 --batch-size 16 --grad-accum 2 --ema-extra-halflife-epochs 1 4"
"O3_d256_lr3e-2_clip_b64|$MOD --mod-late-from-epochs 4 --grad-clip 1.0 --lr 3e-2 --dim 256 --depth 8 --batch-size 16 --grad-accum 4"
"O4_d256_lr3e-2_clip_b64_late2|$MOD --mod-late-from-epochs 2 --grad-clip 1.0 --lr 3e-2 --dim 256 --depth 8 --batch-size 16 --grad-accum 4"
"O5_d512_lr1e-2_long|$MOD --mod-late-from-epochs 4 --lr 1e-2 --dim 512 --depth 8 --batch-size 16 --grad-accum 2"
)
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done
  mkdir -p "$OUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $COMMON $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s)
  "$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  last=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  printf '%s\t%s\t%s\t%s\trc=%s\t%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" "$rest" >> "$OUT/SUMMARY.tsv"
done
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
echo OVERNIGHT DONE > /tmp/air_overnight.done
