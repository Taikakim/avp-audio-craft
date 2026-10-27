#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: GHOST-NOTE (created 2026-10-15)
# Follow-up to the overnight air-head runs (Kim 2026-10-15): (O6) O1 again -- lr 5e-2, d256 -- but damping armed after ONE epoch and the cosine decay starting at epoch 3 (window 3..25);
# (A2b) the A2 bracket recipe re-run. Both save, every epoch: EMA half-life 2 ep (the overnight setting), EMA half-life 0.5 ep (A2's setting) and ONLINE weights (Schedule-Free averaged iterate),
# all from ONE trajectory, so the EMA-vs-online question is answered on identical training. Queues behind any GPU holder; stops the render server; then renders the epoch sweep.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/air_head_2026-10-15_followup
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
COMMON="--feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-radial-brake 0.8 --batch-size 16 --grad-accum 2"
ARMS=(
"O6_d256_lr5e-2_late1_cos3|$COMMON --max-steps 4000 --epochs 25 --mod-warmup-epochs 1 --mod-late-from-epochs 1 --cosine-epochs 3 25 --ema-halflife-epochs 2 --ema-extra-halflife-epochs 0.5 --grad-clip 1.0 --lr 5e-2 --dim 256 --depth 8"
"A2b_d512_lr1e-2_rerun|$COMMON --max-steps 1000 --epochs 10 --mod-warmup-epochs 0.25 --mod-late-from-epochs 1 --ema-halflife-epochs 0.5 --ema-extra-halflife-epochs 2 --lr 1e-2 --dim 512 --depth 8"
)
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
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
echo TRAIN DONE > /tmp/air_followup_train.done
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_sweep.py" --dirs "$OUT"/O6* "$OUT"/A2b* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
export SWEEP_DIR="$OUT/epoch_sweep"
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" dsp >> "$OUT/sweep.log" 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_epoch_metrics.py" audiobox >> "$OUT/sweep.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" merge >> "$OUT/sweep.log" 2>&1
echo FOLLOWUP DONE > /tmp/air_followup.done
