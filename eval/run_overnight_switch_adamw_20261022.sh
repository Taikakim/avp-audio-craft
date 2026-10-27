#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-22)
# Night queue after run_overnight_dpo_batch_20261021.sh (LatCH onset_per_beat head, goa_bigset, same split/seed as
# batch_sweep_20261021/EB64). Three questions, cheapest first; GPU must be free again by DEADLINE for a steering session.
#   S1/S2  Muon -> AdamW late switch: AdamW (lr 3e-4 / 1e-3) from the EB64 Muon head's best checkpoint (epoch 27,
#          val 0.1802), 13 more epochs. Does a fresh AdamW get below Muon's best?
#   AW64   AdamW-everywhere control at batch 64, 40 epochs, lr 3e-4 (the LatCH AdamW recipe). Does Muon buy anything here?
#   EB256L batch 256 with LINEAR lr scaling (4e-3; momentum/EMA horizons fixed in samples as in EB256s). CONTINUITY's
#          delta_beta estimate says no matrix is noise-dominated, where the sqrt rule (EB256s, 0.1964) under-steps.
#          wd stays 0.01: decoupled decay per step is lr*wd, so lr x4 alone keeps it fixed per sample.
# An arm is only started if its expected duration fits before DEADLINE.
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$ROOT/switch_adamw_20261022
CK=$ROOT/batch_sweep_20261021/EB64/latch_sa3_onset_per_beat_ts_best.pt
LOG=/home/kim/sao_runs/overnight_20261022.log
DEADLINE=$(date -d "tomorrow 07:40" +%s); [ "$(date +%H)" -lt 12 ] && DEADLINE=$(date -d "today 07:40" +%s)
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
while pgrep -f 'run_overnight_dpo_batch_20261021\.sh' >/dev/null; do sleep 60; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH Muon->AdamW switch + AdamW control + linear-lr EB256 (ends by 07:40)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; deadline $(date -d @"$DEADLINE" +%H:%M)"

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --batch-size 32 --grad-accum 2
  --grad-clip 1.0 --lr-watchdog 2 --log-grad-noise 10 --save-best-only"
MOD="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --log-opt-groups --mod-warmup-epochs 0.68 --mod-radial-brake 0.8 --mod-ns-dtype fp32"

arm() {   # name, minutes expected, purpose, train args...
  local name=$1 mins=$2 purpose=$3; shift 3; local d="$OUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return; }
  if [ $(( $(date +%s) + mins * 60 )) -gt "$DEADLINE" ]; then echo "$(date +%H:%M) $name skipped: ${mins} min would pass the deadline"; return; fi
  mkdir -p "$d"; echo "$(date +%H:%M) $name: $*"
  "$LPY" - "$d/run_meta.json" "$name" "$purpose" "$*" <<'EOF'
import json, sys
p, name, purpose, args = sys.argv[1:5]
json.dump({"name": name, "purpose": purpose, "train_args": args, "script": "eval/run_overnight_switch_adamw_20261022.sh",
           "reference": "batch_sweep_20261021/EB64 (modular Muon, lr 1e-3, best val 0.1802 at epoch 27)",
           "dataset": "latents_goa_bigset, onset_per_beat_ts, held-out 617 relpaths (val_seed 0)"}, open(p, "w"), indent=1)
EOF
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $ONSET "$@" --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $name rc=$rc; best val $(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1)"
  [ $rc -eq 0 ] && touch "$d/DONE"
}

arm S1_adamw3e-4 60 "Muon->AdamW switch: fresh AdamW lr 3e-4 from the EB64 Muon head (epoch 27), 13 epochs" \
    --optimizer adamw --lr 3e-4 --epochs 13 --init-from "$CK"
arm S2_adamw1e-3 60 "Muon->AdamW switch: fresh AdamW lr 1e-3 from the EB64 Muon head (epoch 27), 13 epochs" \
    --optimizer adamw --lr 1e-3 --epochs 13 --init-from "$CK"
arm AW64 170 "AdamW-everywhere control at batch 64, 40 epochs, lr 3e-4 (LatCH AdamW recipe), same data/split as EB64" \
    --optimizer adamw --lr 3e-4 --epochs 40
# shellcheck disable=SC2086
arm EB256L 125 "Batch 256, LINEAR lr scaling from EB64 (lr 4e-3); horizons in samples as EB256s (sqrt rule, 0.1964)" \
    $MOD --batch-size 32 --grad-accum 8 --epochs 30 --lr 4e-3 --mod-momentum 0.6 --mod-normuon-beta 0.8 \
    --mod-precond-beta 0.8 --mod-adam-beta2 0.96 --mod-precond-freq 3 --mod-wd 0.01
echo "$(date +%H:%M) queue done"
