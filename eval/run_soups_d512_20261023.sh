#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-23)
# Second listening pass on latch_opt_grid_c.html (2026-10-23): KL-SOAP sounded about as good as Muon or better, AdEMAMix more
# transient but less smooth, AdaGC cleaner. This queue, after eval/run_cont_20261023.sh (KSc075 + its eval) releases the GPU:
#   1 soups (CPU): Muon_b64 + KSc075 50/50, Muon_b64 + KSc 50/50, Muon_b64 + KSc075 + AWcG 1/3 each, Gaussian epoch soups of
#     KSc075 and AEMc_cont (saved every 5 epochs only) -> eval D -> latch_opt_grid_d.html
#   2 MuonG    Muon_b64's recipe + AdaGC (lambda 1.04), lr 9e-4 (0.9x), 20 epochs
#   3 Muon512  Muon_b64's recipe at width 512, lr 9e-4, 20 epochs
#   4 KS512    KL-SOAP at width 512, lr 1.82e-4 (KSc075's 2.25e-4 x 0.9 x 0.9), warmup 0.68, cosine planned over 40 epochs
#              (so a continuation to 40 keeps the same schedule), first 20 epochs trained
# Every run: --save-every-epoch (bell soups), --save-resume (continue later with --resume-from <dir>/resume.pt --epochs 40),
# --step-log (per-step loss / raw grad norm / step size / path length / distance from init; per-layer and per-block weight std,
# grad and movement every 20 steps), --flight-recorder (gradient spikes with the crops that caused them), grad-noise + opt groups.
# After each run: its epoch soup (sigma 2 around the best epoch) and eval D again (renders only what is new).
# A run whose first attempt runs out of memory is retried at micro-batch 16 x accum 4 (same effective batch 64).
# RUN: setsid nohup bash eval/run_soups_d512_20261023.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
SP=$R/soups_20261023
OUT=$R/d512_20261023
F=latch_sa3_onset_per_beat_ts
LOG=/home/kim/sao_runs/soups_d512_20261023.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT" "$SP"; cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
# wait for the KSc075 queue (same handle: its exit releases the lock), then take the GPU
while [ ! -f "$R/cont_20261023/KSc075/DONE" ] || pgrep -f '^bash eval/run_cont_20261023\.sh' >/dev/null; do sleep 120; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH soups + MuonG / Muon512 / KS512 (20 epochs each), ~15 h" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; free on the UUID drive: $(df -h --output=avail "$R" | tail -1)"

soup() {   # name, args...
  local n=$1; shift
  [ -f "$SP/$n/${F}_best.pt" ] && return 0
  echo "$(date +%H:%M) soup $n"; "$LPY" eval/latch_head_soup.py "$@" --out "$SP/$n/${F}_best.pt" | tail -8
}
C=$R/cont_20261023; A=$R/adamw_cosine_20261022
soup MK50     --in "$R/batch_sweep_20261021/EB64/${F}_best.pt:1" --in "$C/KSc075/${F}_best.pt:1"
soup MK50_ksc --in "$R/batch_sweep_20261021/EB64/${F}_best.pt:1" --in "$A/KSc/${F}_best.pt:1"
soup MKA33    --in "$R/batch_sweep_20261021/EB64/${F}_best.pt:1" --in "$C/KSc075/${F}_best.pt:1" --in "$A/AWcG/${F}_best.pt:1"
soup bell_KSc075    --bell "$C/KSc075" --sigma 5
soup bell_AEMc_cont --bell "$C/AEMc_cont" --sigma 3
echo "$(date +%H:%M) eval D (soups)"; bash eval/run_opt_grid_eval.sh D; echo "$(date +%H:%M) eval D rc=$?"

COMMON="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --epochs 20 --grad-clip 1.0 --lr-watchdog 2
  --log-grad-noise 10 --save-best-only --save-every-epoch --save-resume --step-log --layer-log 20 --flight-recorder
  --stop-val-ratio 0 --stop-rising-epochs 0"
MUON="--optimizer modular --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --mod-ns-dtype fp32 --mod-warmup-epochs 0.68 --mod-radial-brake 0.8 --log-opt-groups --lr 9e-4"

arm() {   # name, purpose, train args...
  local name=$1 purpose=$2; shift 2; local d="$OUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return 0; }
  mkdir -p "$d"
  "$LPY" - "$d/run_meta.json" "$name" "$purpose" "$*" <<'EOF'
import json, sys
p, name, purpose, args = sys.argv[1:5]
json.dump({"name": name, "purpose": purpose, "train_args": args, "script": "eval/run_soups_d512_20261023.sh",
           "hypothesis": "Second listening pass on latch_opt_grid_c.html (2026-10-23): KL-SOAP sounded about as good as Muon or better; "
                         "AdaGC cleaner but steering less. Does width 512 or AdaGC on Muon's recipe keep Muon's reach with a cleaner sound?",
           "reference": "batch_sweep_20261021/EB64 (Muon, width 256, best val 0.1802); cont_20261023/KSc075 (KL-SOAP 0.75x lr)",
           "continue": "same args + --resume-from <this dir>/resume.pt --epochs 40",
           "dataset": "latents_goa_bigset, onset_per_beat_ts, held-out 617 relpaths (val_seed 0)", "kim_feedback": None}, open(p, "w"), indent=1)
EOF
  local mb=32 acc=2 rc t0
  t0=$(date +%s)
  for try in 1 2; do
    echo "$(date +%H:%M) $name (micro-batch $mb x $acc): $*"
    # shellcheck disable=SC2086
    ( cd /tmp && "$LPY" "$TRAIN" $COMMON "$@" --batch-size $mb --grad-accum $acc --save-dir "$d" > "$d/train.log" 2>&1 )
    rc=$?
    if [ $rc -ne 0 ] && grep -qiE 'out of memory|HIP error: out|OutOfMemory' "$d/train.log" && [ $try = 1 ]; then
      echo "$(date +%H:%M) $name: out of memory at micro-batch 32, retrying at 16 x 4"; mv "$d/train.log" "$d/train_oom.log"
      rm -f "$d"/*.jsonl "$d"/resume.pt; mb=16; acc=4; continue
    fi
    break
  done
  echo "$(date +%H:%M) $name rc=$rc; best val $(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1);" \
       "$(( ($(date +%s) - t0) / 60 )) min for $(grep -c 'val=' "$d/train.log") epochs; $(du -sh "$d" | cut -f1) on disk"
  [ $rc -eq 0 ] && touch "$d/DONE"
  [ $rc -eq 0 ] && soup "bell_$name" --bell "$d" --sigma 2
  echo "$(date +%H:%M) eval D ($name)"; bash eval/run_opt_grid_eval.sh D; echo "$(date +%H:%M) eval D rc=$?"
}

# shellcheck disable=SC2086
arm MuonG "Muon_b64's recipe (NorMuon + Shampoo on matrices, Schedule-Free AdamW on scalars) + AdaGC per-tensor clip, lr 0.9x" \
    $MUON --adagc 1.04
# shellcheck disable=SC2086
arm Muon512 "Muon_b64's recipe at width 512 (4x the parameters), lr 0.9x" $MUON --dim 512
arm KS512 "KL-SOAP at width 512, lr KSc075 x 0.9 x 0.9 = 1.82e-4, cosine planned over 40 epochs, first 20 trained" \
    --optimizer kl_soap --lr 1.82e-4 --warmup-epochs 0.68 --cosine-epochs 0 40 --dim 512
echo "$(date +%H:%M) queue done"
