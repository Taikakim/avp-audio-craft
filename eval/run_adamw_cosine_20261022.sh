#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-22)
# Follow-up to run_overnight_switch_adamw_20261022.sh, batch 64 only (LatCH onset_per_beat head, goa_bigset, same split/seed
# as batch_sweep_20261021/EB64, Muon best 0.1802 at epoch 27). The overnight AdamW arms were not fair tests:
#   AW64 ran a constant lr with no averaging (val swung 0.21-0.29), and the switch arms got a cold-start kick (a fresh
#   AdamW moves every weight ~lr at step 1: 0.180 -> 0.338 in one epoch at lr 3e-4).
#   C1     Muon -> AdamW switch, done properly: lr 1e-4, 1-epoch linear warmup, cosine to 0 over 13 epochs.
#   AWc    AdamW control with a schedule: lr 3e-4, warmup 0.68 epoch (as the Muon arm), cosine to 0 over 40 epochs.
#   AWcG   AWc + AdaGC (per-tensor clip, paper defaults lambda 1.04 / beta 0.99, 100-step warmup). One variable vs AWc.
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$ROOT/adamw_cosine_20261022
CK=$ROOT/batch_sweep_20261021/EB64/latch_sa3_onset_per_beat_ts_best.pt
LOG=/home/kim/sao_runs/adamw_cosine_20261022.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH AdamW cosine / +AdaGC / Muon->AdamW warm switch (~6 h); kill eval/run_adamw_cosine_20261022.sh to yield" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --batch-size 32 --grad-accum 2
  --grad-clip 1.0 --lr-watchdog 2 --log-grad-noise 10 --save-best-only --optimizer adamw"

arm() {   # name, purpose, train args...
  local name=$1 purpose=$2; shift 2; local d="$OUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return; }
  mkdir -p "$d"; echo "$(date +%H:%M) $name: $*"
  "$LPY" - "$d/run_meta.json" "$name" "$purpose" "$*" <<'EOF'
import json, sys
p, name, purpose, args = sys.argv[1:5]
json.dump({"name": name, "purpose": purpose, "train_args": args, "script": "eval/run_adamw_cosine_20261022.sh",
           "reference": "batch_sweep_20261021/EB64 (modular Muon, lr 1e-3, best val 0.1802 at epoch 27); "
                        "switch_adamw_20261022/AW64 (AdamW constant lr 3e-4, 0.2080)",
           "dataset": "latents_goa_bigset, onset_per_beat_ts, held-out 617 relpaths (val_seed 0)"}, open(p, "w"), indent=1)
EOF
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $ONSET "$@" --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $name rc=$rc; best val $(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1)"
  [ $rc -eq 0 ] && touch "$d/DONE"
}

arm C1_switch1e-4 "Muon->AdamW switch with warmup: AdamW lr 1e-4 from the EB64 Muon head (epoch 27), 1-epoch warmup, cosine to 0 over 13 epochs" \
    --lr 1e-4 --epochs 13 --warmup-epochs 1 --cosine-epochs 0 13 --init-from "$CK"
arm AWc "AdamW control at batch 64 with a schedule: lr 3e-4, warmup 0.68 epoch, cosine to 0 over 40 epochs" \
    --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40
arm AWcG "AWc + AdaGC per-tensor gradient clip (lambda 1.04, beta 0.99, 100-step warmup), one variable vs AWc" \
    --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40 --adagc 1.04
echo "$(date +%H:%M) queue done"
