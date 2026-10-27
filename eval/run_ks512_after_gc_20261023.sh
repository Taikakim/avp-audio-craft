#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-23)
# Activation-checkpointing speed test before KS512 (request 2026-10-23). Width 512 at T=4096 ran out of memory at micro-batch
# 32 and 16, so Muon512 trains at 8 x 8 (2.70 s/step). --grad-ckpt (train_latch.py, CPU A/B weight diff 0.0) should let
# micro-batch 32 fit. This script:
#   1 waits until eval/run_soups_d512_20261023.sh has finished Muon512 and exited (KS512 was marked DONE so that queue stops)
#   2 trains Muon512's recipe for 1 epoch at micro-batch 32 x 2 with --grad-ckpt (16 x 4 if 32 still runs out), logging
#     s/step and peak VRAM, into d512_20261023/gc_test_Muon512
#   3 runs KS512 (same args as the queue) with whichever setting is faster per step: 8 x 8 plain, or the checkpointed one.
#     Micro-batch x accum at a fixed effective batch 64 changes speed, not the update.
#   4 KS512's bell soup (sigma 2) and eval D
# RUN: setsid nohup bash eval/run_ks512_after_gc_20261023.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$R/d512_20261023
SP=$R/soups_20261023
F=latch_sa3_onset_per_beat_ts
LOG=/home/kim/sao_runs/soups_d512_20261023.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
while [ ! -f "$OUT/Muon512/DONE" ] || pgrep -f '^bash eval/run_soups_d512_20261023\.sh' >/dev/null; do sleep 60; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE grad-ckpt speed test (1 epoch) then KS512 (20 epochs)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired for the grad-ckpt test + KS512"

COMMON="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --grad-clip 1.0 --lr-watchdog 2
  --log-grad-noise 10 --save-best-only --stop-val-ratio 0 --stop-rising-epochs 0"
MUON="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --mod-ns-dtype fp32 --mod-warmup-epochs 0.68 --mod-radial-brake 0.8 --lr 9e-4 --dim 512"
KS="--optimizer kl_soap --lr 1.82e-4 --warmup-epochs 0.68 --cosine-epochs 0 40 --dim 512"

sps() {   # mean s/step over steps 21.. of a steps.jsonl (the first steps carry kernel warm-up)
  "$LPY" -c "import json,sys; L=[json.loads(l) for l in open(sys.argv[1])][20:]; print(f'{sum(r[\"sec\"] for r in L)/max(len(L),1):.3f}')" "$1"
}

# 2 the test
T=$OUT/gc_test_Muon512; mkdir -p "$T"
gc_mb=32; gc_acc=2
for try in 1 2; do
  echo "$(date +%H:%M) grad-ckpt test: Muon512 recipe, 1 epoch, micro-batch $gc_mb x $gc_acc, --grad-ckpt"
  ( while sleep 5; do rocm-smi --showmeminfo vram 2>/dev/null | grep -oE 'GPU\[0\].*Used Memory \(B\): [0-9]+' | grep -oE '[0-9]+$'; done ) > "$T/vram_$gc_mb.txt" &
  mon=$!
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $COMMON $MUON --epochs 1 --step-log --grad-ckpt --batch-size $gc_mb --grad-accum $gc_acc \
      --save-dir "$T" > "$T/train_$gc_mb.log" 2>&1 )
  rc=$?; kill $mon 2>/dev/null
  if [ $rc -ne 0 ] && grep -qiE 'out of memory|OutOfMemory' "$T/train_$gc_mb.log" && [ $try = 1 ]; then
    echo "$(date +%H:%M) grad-ckpt test: out of memory at $gc_mb, retrying at 16 x 4"; mv "$T/steps.jsonl" "$T/steps_oom.jsonl" 2>/dev/null
    gc_mb=16; gc_acc=4; continue
  fi
  break
done
peak=$(sort -n "$T/vram_$gc_mb.txt" | tail -1)
base=$(sps "$OUT/Muon512/steps.jsonl"); gc=nan
[ $rc -eq 0 ] && gc=$(sps "$T/steps.jsonl")
echo "$(date +%H:%M) grad-ckpt test rc=$rc: micro-batch $gc_mb x $gc_acc --grad-ckpt $gc s/step, peak VRAM $(( ${peak:-0} / 1048576 )) MiB," \
     "val $(grep -oE 'val=[0-9.]+' "$T/train_$gc_mb.log" | tail -1 | cut -d= -f2); plain 8 x 8 (Muon512) $base s/step"
"$LPY" - "$T/result.json" "$gc_mb" "$gc_acc" "$gc" "$base" "${peak:-0}" "$rc" <<'EOF'
import json, sys
p, mb, acc, gc, base, peak, rc = sys.argv[1:8]
json.dump({"purpose": "Does activation checkpointing (--grad-ckpt) at a larger micro-batch beat plain micro-batch 8 x 8 per step at "
                      "width 512, T=4096? Same effective batch 64, same update; speed and memory only.",
           "test": f"Muon512 recipe, 1 epoch, micro-batch {mb} x {acc}, --grad-ckpt", "rc": int(rc),
           "sec_per_step_gradckpt": None if gc == "nan" else float(gc), "sec_per_step_plain_8x8": float(base),
           "peak_vram_mib": int(peak) // 1048576, "reference": "d512_20261023/Muon512 (plain, micro-batch 8 x 8)",
           "script": "eval/run_ks512_after_gc_20261023.sh", "kim_feedback": None}, open(p, "w"), indent=1)
EOF

# 3 KS512 with the faster setting
KS_FLAGS="--batch-size 8 --grad-accum 8"; how="plain 8 x 8"
if [ "$gc" != nan ] && "$LPY" -c "import sys; sys.exit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)" "$gc" "$base"; then
  KS_FLAGS="--batch-size $gc_mb --grad-accum $gc_acc --grad-ckpt"; how="--grad-ckpt $gc_mb x $gc_acc"
fi
d=$OUT/KS512
# the DONE written by hand only so run_soups_d512 would skip KS512; this script trains it
[ -f "$d/DONE" ] && [ ! -f "$d/train.log" ] && mv "$d/DONE" "$d/queue_skip_marker.txt"
echo "$(date +%H:%M) KS512 ($how): $KS"
t0=$(date +%s)
# shellcheck disable=SC2086
( cd /tmp && "$LPY" "$TRAIN" $COMMON $KS --epochs 20 --save-every-epoch --save-resume --step-log --layer-log 20 --flight-recorder \
    $KS_FLAGS --save-dir "$d" > "$d/train.log" 2>&1 )
rc=$?
echo "$(date +%H:%M) KS512 rc=$rc; best val $(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1);" \
     "$(( ($(date +%s) - t0) / 60 )) min for $(grep -c 'val=' "$d/train.log") epochs"
"$LPY" - "$d/run_meta.json" "$how" <<'EOF'
import json, sys
p, how = sys.argv[1:3]
m = json.load(open(p)); m["batching"] = how; m["launched_by"] = "eval/run_ks512_after_gc_20261023.sh"
json.dump(m, open(p, "w"), indent=1)
EOF
if [ $rc -eq 0 ]; then
  touch "$d/DONE"
  echo "$(date +%H:%M) soup bell_KS512"
  "$LPY" eval/latch_head_soup.py --bell "$d" --sigma 2 --out "$SP/bell_KS512/${F}_best.pt" | tail -8
fi
echo "$(date +%H:%M) eval D (KS512)"; bash eval/run_opt_grid_eval.sh D; echo "$(date +%H:%M) eval D rc=$?"
echo "$(date +%H:%M) KS512 queue done"
