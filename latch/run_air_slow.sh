#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15)
# Every overnight air-head recipe (O1-O5) again at a 10x SLOWER lr for 15 epochs (Kim 2026-10-15: "try every run at a 10x slower LR for 15 epochs"). Same settings as overnight
# (grad clip, warmup 1 ep, EMA half-life 2 ep, radial brake 0.8, overtraining wd, Muon on all 2-D) except: cosine window 10.5..15 (the 70..100% of the run that 17.5..25 was), lr/10, epochs 15.
# TRIMMED 2026-10-15 (Kim: "only the runs with LRs lower than the lowest in the last runs, to save time"): only S5 (lr 1e-3) is below the lowest lr of the other queued runs (L2 2e-3); S1 5e-3, S2 1e-2, S3/S4 3e-3 dropped.
# Each epoch saves EMA 2 ep, EMA 0.5 ep and online (Schedule-Free average) weights. d512 uses batch 8 x 4 (b16 x 2 ran out of memory in A2b). Runs after run_air_lowlr.sh.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_slow
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
until [ -f /tmp/air_lowlr.done ]; do sleep 120; done
COMMON="--feature rms_energy_air --latent-dir /home/kim/Projects/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --ema-halflife-epochs 2 --ema-extra-halflife-epochs 0.5 --cosine-epochs 10.5 15 --epochs 15 --depth 8"
ARMS=(
"S5_d512_lr1e-3|$COMMON --mod-late-from-epochs 4 --lr 1e-3 --dim 512 --batch-size 8 --grad-accum 4"
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
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_sweep.py" --dirs "$OUT"/S5* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
export SWEEP_DIR="$OUT/epoch_sweep"
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" dsp >> "$OUT/sweep.log" 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_epoch_metrics.py" audiobox >> "$OUT/sweep.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" merge >> "$OUT/sweep.log" 2>&1
echo SLOW DONE > /tmp/air_slow.done
