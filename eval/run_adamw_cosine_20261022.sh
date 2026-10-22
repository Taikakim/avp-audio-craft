#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-22)
# Last edited: WINTERMUTE 2026-10-22 -- AEMc and KSc arms; two phases with an eval render + page publish between them (14 h GPU window)
# Batch-64 optimizer comparison on the LatCH onset_per_beat head (goa_bigset, same split/seed as batch_sweep_20261021/EB64,
# Muon best 0.1802 at epoch 27). The overnight AdamW arms were not fair tests: AW64 ran a constant lr with no averaging
# (val swung 0.21-0.29) and the switch arms got a cold-start kick (0.180 -> 0.338 in one epoch at lr 3e-4).
#   Phase A (the owner's three):
#   C1     Muon -> AdamW switch, done properly: lr 1e-4, 1-epoch linear warmup, cosine to 0 over 13 epochs.
#   AWc    AdamW with a schedule: lr 3e-4, warmup 0.68 epoch (as the Muon arm), cosine to 0 over 40 epochs.
#   AWcG   AWc + AdaGC (per-tensor clip, paper defaults lambda 1.04 / beta 0.99, 100-step warmup). One variable vs AWc.
#   -> eval A: onset gain x density grids for those heads + the Muon/AdamW/EB256L references, page published.
#   Phase B (only what fits before TRAIN_END):
#   AEMc   AdEMAMix with AWc's schedule (Adam + a slow gradient EMA; arXiv 2409.03137). One variable vs AWc.
#   KSc    KL-SOAP on the hidden matrices with AWc's schedule: does Adam in the Shampoo eigenbasis beat plain AdamW?
#   -> eval B: grids for the phase B heads, page rebuilt and published.
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$ROOT/adamw_cosine_20261022
CK=$ROOT/batch_sweep_20261021/EB64/latch_sa3_onset_per_beat_ts_best.pt
LOG=/home/kim/sao_runs/adamw_cosine_20261022.log
TRAIN_END=$(date -d "today 22:45" +%s)     # the owner is back ~23:30; eval B needs ~40 min after the last arm
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH optimizer comparison + eval grids until ~23:30 (owner's window)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --batch-size 32 --grad-accum 2
  --grad-clip 1.0 --lr-watchdog 2 --log-grad-noise 10 --save-best-only --optimizer adamw"

arm() {   # name, expected minutes, purpose, train args...
  local name=$1 mins=$2 purpose=$3; shift 3; local d="$OUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return; }
  if [ $(( $(date +%s) + mins * 60 )) -gt "$TRAIN_END" ]; then echo "$(date +%H:%M) $name skipped: ${mins} min would pass $(date -d @"$TRAIN_END" +%H:%M)"; return; fi
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

# ---- phase A ----
arm C1_switch1e-4 55 "Muon->AdamW switch with warmup: AdamW lr 1e-4 from the EB64 Muon head (epoch 27), 1-epoch warmup, cosine to 0 over 13 epochs" \
    --lr 1e-4 --epochs 13 --warmup-epochs 1 --cosine-epochs 0 13 --init-from "$CK"
arm AWc 165 "AdamW at batch 64 with a schedule: lr 3e-4, warmup 0.68 epoch, cosine to 0 over 40 epochs" \
    --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40
arm AWcG 165 "AWc + AdaGC per-tensor gradient clip (lambda 1.04, beta 0.99, 100-step warmup), one variable vs AWc" \
    --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40 --adagc 1.04
echo "$(date +%H:%M) eval A"
bash eval/run_opt_grid_eval.sh A
echo "$(date +%H:%M) eval A rc=$?"

# ---- phase B ----
arm AEMc 165 "AdEMAMix (slow EMA beta3 0.999 ~5 epochs, alpha 5, both ramped over the run) with AWc's schedule: lr 3e-4, warmup 0.68 epoch, cosine to 0 over 40 epochs" \
    --optimizer ademamix --ademamix-beta3 0.999 --ademamix-alpha 5 --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40
arm KSc 190 "KL-SOAP (NVIDIA kl_soap: Adam in the KL-Shampoo eigenbasis) on the hidden matrices, AdamW on the rest, with AWc's schedule: lr 3e-4, warmup 0.68 epoch, cosine over 40 epochs. Rotation-only change vs AWc" \
    --optimizer kl_soap --lr 3e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40
echo "$(date +%H:%M) eval B"
bash eval/run_opt_grid_eval.sh B
echo "$(date +%H:%M) eval B rc=$?; queue done"
