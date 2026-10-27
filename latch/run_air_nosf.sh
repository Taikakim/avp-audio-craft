#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: GHOST-NOTE (created 2026-10-15)
# Replicas WITHOUT Schedule-Free (Kim 2026-10-15: "these should be probably replicated without the schedule free component. We've been relying on it quite a lot."). `--no-mod-sf`: plain Muon/Shampoo
# momentum updates; there is no averaged iterate, so 'online' = the live weights and the EMA is the only averaging. Arms: QA2 = the A2 recipe (the reference); QP64 / QP128 = the big-batch cosine recipe
# at lr 1e-2 (SF-free runs need a far smaller lr than SF's, Phase A/B: modular 1e-2 trains; 1e-1 would be reckless); QP64h = the faithful lr 1e-1 twin of P64 (expected to diverge; train_latch now stops at the first NaN epoch).
# Runs after run_air_slow.sh (waits for /tmp/air_slow.done).
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/air_head_2026-10-15_nosf
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
until [ -f /tmp/air_bass.done ]; do sleep 120; done   # after run_bass_lr.sh (Kim 2026-10-16 priority)
BASE="--feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --no-mod-sf --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-radial-brake 0.8 --dim 512 --depth 8 --batch-size 8"
BIG="$BASE --mod-warmup-epochs 1 --mod-late-from-epochs 2 --grad-clip 1.0 --epochs 8 --cosine-epochs 0 8 --ema-halflife-epochs 4 --ema-extra-halflife-epochs 2 0.5"
ARMS=(
"QA2_d512_lr1e-2_nosf|$BASE --max-steps 1000 --epochs 10 --mod-warmup-epochs 0.25 --mod-late-from-epochs 1 --ema-halflife-epochs 0.5 --ema-extra-halflife-epochs 2 --lr 1e-2 --grad-accum 4"
"QP64_d512_lr1e-2_b64_nosf|$BIG --lr 1e-2 --grad-accum 8"
"QP128_d512_lr1e-2_b128_nosf|$BIG --lr 1e-2 --grad-accum 16"
"QP64h_d512_lr1e-1_b64_nosf|$BIG --lr 1e-1 --grad-accum 8"
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
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_sweep.py" --dirs "$OUT"/QA2* "$OUT"/QP64_* "$OUT"/QP128* "$OUT"/QP64h* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
export SWEEP_DIR="$OUT/epoch_sweep"
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" dsp >> "$OUT/sweep.log" 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_epoch_metrics.py" audiobox >> "$OUT/sweep.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/air_epoch_metrics.py" merge >> "$OUT/sweep.log" 2>&1
grep -qE "rc=[1-9]" "$OUT/SUMMARY.tsv" || echo NOSF DONE > /tmp/air_nosf.done   # marker only if every arm exited 0 (a 2-s death once wrote a false marker)
