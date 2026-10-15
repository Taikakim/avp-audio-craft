#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15)
# Owner's idea after listening to the epoch sweep (2026-10-15): O2 (lr 1e-1, EMA half-life 4 ep) at ONE epoch sounded bright and only a bit grainy; try that recipe at d512 with a BIG batch
# (64 and 128, via gradient accumulation of micro-batch 8: any effective batch fits in 16 GB without gradient checkpointing) and a cosine from step 0 to epoch 8 ("enough to show if this helps").
# P64m = insurance (2026-10-15, owner: "enough to get them to finish even the 8ep run cleanly"): the same recipe at lr 3e-2 in case lr 1e-1 diverges; train_latch now stops at the first NaN epoch.
# Each epoch saves EMA 4 ep (main), EMA 2 ep, EMA 0.5 ep and online weights. Runs after run_air_lowlr.sh; run_air_slow.sh waits for /tmp/air_big.done.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_big
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
until [ -f /tmp/air_dora_blend.done ]; do sleep 120; done   # lowlr -> dora_blend -> big
COMMON="--feature rms_energy_air --latent-dir /home/kim/Projects/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-late-from-epochs 2 --mod-radial-brake 0.8 --grad-clip 1.0 --lr 1e-1 --dim 512 --depth 8 --batch-size 8 --epochs 8 --cosine-epochs 0 8 --ema-halflife-epochs 4 --ema-extra-halflife-epochs 2 0.5"
ARMS=("P64_d512_lr1e-1_b64_cos8|$COMMON --grad-accum 8" "P64m_d512_lr3e-2_b64_cos8|${COMMON/--lr 1e-1/--lr 3e-2} --grad-accum 8" "P128_d512_lr1e-1_b128_cos8|$COMMON --grad-accum 16")
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
echo BIG TRAIN DONE > /tmp/air_big.done      # lets run_air_slow.sh start; the sweep below needs the render server, which slow stops again
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_sweep.py" --dirs "$OUT"/P64_* "$OUT"/P64m* "$OUT"/P128* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
export SWEEP_DIR="$OUT/epoch_sweep"
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" dsp >> "$OUT/sweep.log" 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_epoch_metrics.py" audiobox >> "$OUT/sweep.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" merge >> "$OUT/sweep.log" 2>&1
echo BIG DONE > /tmp/air_big_sweep.done
