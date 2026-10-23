#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-23)
# Last edited: WINTERMUTE 2026-10-23 -- WINDOW_END overridable from the env (KSc075 run past 09:00)
# Follow-up to eval/run_adamw_cosine_20261022.sh after the listening pass on latch_opt_grid.html (6 h GPU window from ~03:00):
#   AEMc_cont  AEMc's best head (epoch 28, val 0.1990) continued 20 epochs with AdEMAMix: fresh optimizer state (the run kept no
#              optimizer state), lr 1e-4 (about where AEMc's own cosine stood at epoch 28), 1-epoch warmup, cosine to 0 over 20.
#   -> eval C: the wider grid asked for (gains 32/64/128/512/1024/2048/4096, requested 1-16 onsets/s) on the Muon reference, AWcG,
#              AEMc, AEMc_cont best + last, KSc; page latch_opt_grid_c.html. Renders on the UUID drive (Mantu is 98% full).
#   KSc075     KL-SOAP from scratch at 0.75x the lr (2.25e-4), 40 epochs, AWc's schedule otherwise. The first KSc was stopped at
#              epoch 17 by the rising-val rule (best 0.1894 at epoch 14). Only if it fits the window (~8.3 min/epoch -> ~5.5 h);
#              if it runs, eval C is re-run afterwards to add its heads.
# Both arms: --save-every 5 (ep5/10/... + the last epoch) besides _best.pt; the early-stop rule is off (the full schedule is asked for).
# RUN: setsid nohup bash eval/run_cont_20261023.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$ROOT/cont_20261023
AEMC=$ROOT/adamw_cosine_20261022/AEMc/latch_sa3_onset_per_beat_ts_best.pt
LOG=/home/kim/sao_runs/cont_20261023.log
WINDOW_END=${WINDOW_END:-$(date -d "today 08:55" +%s)}   # six hours from the request; WINDOW_END=<epoch> overrides
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH AEMc continuation + eval grid (+ KSc 0.75x if it fits), until ~09:00" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; free on the UUID drive: $(df -h --output=avail "$ROOT" | tail -1)"

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --batch-size 32 --grad-accum 2
  --grad-clip 1.0 --lr-watchdog 2 --log-grad-noise 10 --save-best-only --save-every 5 --stop-val-ratio 0 --stop-rising-epochs 0"

arm() {   # name, expected minutes, purpose, train args...
  local name=$1 mins=$2 purpose=$3; shift 3; local d="$OUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return 0; }
  if [ $(( $(date +%s) + mins * 60 )) -gt "$WINDOW_END" ]; then echo "$(date +%H:%M) $name skipped: ${mins} min would pass $(date -d @"$WINDOW_END" +%H:%M)"; return 1; fi
  mkdir -p "$d"; echo "$(date +%H:%M) $name: $*"
  "$LPY" - "$d/run_meta.json" "$name" "$purpose" "$*" <<'EOF'
import json, sys
p, name, purpose, args = sys.argv[1:5]
json.dump({"name": name, "purpose": purpose, "train_args": args, "script": "eval/run_cont_20261023.sh",
           "hypothesis": "Listening pass on latch_opt_grid.html (2026-10-23) found AdEMAMix and KL-SOAP interesting; AEMc ended on a flat "
                         "val (0.199-0.201 over its last 12 epochs) and KSc was cut at epoch 17 by the early-stop rule, so neither is a settled result.",
           "reference": "batch_sweep_20261021/EB64 (modular Muon, best val 0.1802); adamw_cosine_20261022/AEMc (0.1990), KSc (0.1894)",
           "dataset": "latents_goa_bigset, onset_per_beat_ts, held-out 617 relpaths (val_seed 0)", "kim_feedback": None}, open(p, "w"), indent=1)
EOF
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $ONSET "$@" --save-dir "$d" > "$d/train.log" 2>&1 )
  local rc=$?
  echo "$(date +%H:%M) $name rc=$rc; best val $(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1); ckpts: $(ls "$d" | grep -c '\.pt$')"
  [ $rc -eq 0 ] && touch "$d/DONE"
  return 0
}

arm AEMc_cont 85 "AEMc (AdEMAMix) continued: its epoch-28 best head + 20 epochs, fresh AdEMAMix state (alpha/beta3 ramp over the 20), lr 1e-4, 1-epoch warmup, cosine to 0" \
    --optimizer ademamix --ademamix-beta3 0.999 --ademamix-alpha 5 --lr 1e-4 --epochs 20 --warmup-epochs 1 --cosine-epochs 0 20 --init-from "$AEMC"
echo "$(date +%H:%M) eval C"
bash eval/run_opt_grid_eval.sh C
echo "$(date +%H:%M) eval C rc=$?"

if arm KSc075 335 "KL-SOAP from scratch at 0.75x the lr of KSc (2.25e-4), warmup 0.68 epoch, cosine to 0 over 40 epochs, early stop off" \
    --optimizer kl_soap --lr 2.25e-4 --epochs 40 --warmup-epochs 0.68 --cosine-epochs 0 40; then
  if [ -f "$OUT/KSc075/DONE" ]; then
    echo "$(date +%H:%M) eval C (adds KSc075)"
    bash eval/run_opt_grid_eval.sh C
    echo "$(date +%H:%M) eval C rc=$?"
  fi
fi
echo "$(date +%H:%M) queue done"
