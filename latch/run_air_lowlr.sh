#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15)
# NOTE 2026-10-15: b8 x accum4 (same effective batch 32): b16 x2 at d512 OOM-ed (A2b died in epoch 2 with 14.8 GB allocated). A2c = the A2 recipe re-run (replaces the OOM-ed A2b) so EMA 0.5 / EMA 2 / online come from one trajectory.
# Lower-lr bracket for the air head (Kim 2026-10-15: "run the lower-lr bracket too"): the A2 recipe (d512 depth 8, 1000 steps, warmup 0.25 ep, damping from ep 1, radial brake 0.8, EMA half-life 0.5 ep)
# at lr 2e-3 and 5e-3 (1e-2 = A2/A2b, 1e-3 = A4 already exist). Saves EMA 0.5 ep + EMA 2 ep + online weights every epoch. Question: does a lower lr stretch the glitch-free window past
# the ~3 epochs the owner heard at lr 1e-2 (overnight O5)? Runs AFTER run_air_followup.sh (waits for /tmp/air_followup.done), stops the render server for the GPU, then restarts it and renders the epoch sweep.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_lowlr
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
until [ -f /tmp/air_followup.done ]; do sleep 120; done
COMMON="--feature rms_energy_air --latent-dir /home/kim/Projects/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-radial-brake 0.8 --batch-size 8 --grad-accum 4 --max-steps 1000 --epochs 10 --mod-warmup-epochs 0.25 --mod-late-from-epochs 1 --ema-halflife-epochs 0.5 --ema-extra-halflife-epochs 2 --dim 512 --depth 8"
ARMS=("A2c_d512_lr1e-2_b8x4|$COMMON --lr 1e-2" "L2_d512_lr2e-3|$COMMON --lr 2e-3" "L5_d512_lr5e-3|$COMMON --lr 5e-3")
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
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_sweep.py" --dirs "$OUT"/A2c* "$OUT"/L2* "$OUT"/L5* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
export SWEEP_DIR="$OUT/epoch_sweep"
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" dsp >> "$OUT/sweep.log" 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_epoch_metrics.py" audiobox >> "$OUT/sweep.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" merge >> "$OUT/sweep.log" 2>&1
echo LOWLR DONE > /tmp/air_lowlr.done
