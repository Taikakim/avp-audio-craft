#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-24)
# Next stage after latch_opt_grid_d.html (2026-10-24): continue MuonG, Muon512 and KS512 from their epoch-20 resume states to
# 40 epochs (the plan when they were launched: "train initially for 20 epochs, save the states for continuing"). Cheapest first:
# MuonG (~1.5 h), Muon512 (~3 h, micro-batch 8 x 8), KS512 (~7 h, 8 x 8; its cosine was planned over 40 epochs from the start).
# Same args as eval/run_soups_d512_20261023.sh (resume refuses any change to optimizer / dim / lr / batching / split) + --epochs 40.
# Before each: the 20-epoch best is copied to *_best_ep1-20.pt, so page D's heads stay identifiable. After each: a Gaussian epoch
# soup over all 40 epochs (bell40_<run>, sigma 2) and eval E (latch_opt_grid_e.html; renders only heads not yet rendered).
# RUN: setsid nohup bash eval/run_cont40_20261024.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$R/d512_20261023
SP=$R/soups_20261023
F=latch_sa3_onset_per_beat_ts
LOG=/home/kim/sao_runs/cont40_20261024.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH MuonG / Muon512 / KS512 epochs 21-40 (~12 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; free on the UUID drive: $(df -h --output=avail "$R" | tail -1)"

COMMON="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8 --epochs 40 --grad-clip 1.0 --lr-watchdog 2
  --log-grad-noise 10 --save-best-only --save-every-epoch --save-resume --step-log --layer-log 20 --flight-recorder
  --stop-val-ratio 0 --stop-rising-epochs 0"
MUON="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --mod-ns-dtype fp32 --mod-warmup-epochs 0.68 --mod-radial-brake 0.8 --log-opt-groups --lr 9e-4"

cont() {   # name, train args...
  local name=$1; shift; local d="$OUT/$name" rc t0
  [ -f "$d/DONE40" ] && { echo "$(date +%H:%M) $name already at 40"; return 0; }
  [ -f "$d/resume.pt" ] || { echo "$(date +%H:%M) $name: no resume.pt, skipped"; return 0; }
  [ -f "$d/${F}_best_ep1-20.pt" ] || cp -p "$d/${F}_best.pt" "$d/${F}_best_ep1-20.pt"
  [ -f "$d/train_ep1-20.log" ] || cp -p "$d/train.log" "$d/train_ep1-20.log"
  echo "$(date +%H:%M) $name epochs 21-40: $*"
  t0=$(date +%s)
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $COMMON "$@" --resume-from "$d/resume.pt" --save-dir "$d" > "$d/train_ep21-40.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $name rc=$rc; vals ep21-40: $(grep -oE 'val=[0-9.]+' "$d/train_ep21-40.log" | cut -d= -f2 | tr '\n' ' ');" \
       "$(( ($(date +%s) - t0) / 60 )) min"
  "$LPY" - "$d/run_meta.json" "$rc" <<'EOF'
import json, sys
p, rc = sys.argv[1:3]
m = json.load(open(p))
m["continued"] = {"epochs": "21-40", "from": "resume.pt at epoch 20", "script": "eval/run_cont40_20261024.sh", "rc": int(rc),
                  "log": "train_ep21-40.log", "best_of_first_20": "latch_sa3_onset_per_beat_ts_best_ep1-20.pt"}
json.dump(m, open(p, "w"), indent=1)
EOF
  if [ $rc -eq 0 ]; then
    touch "$d/DONE40"
    echo "$(date +%H:%M) soup bell40_$name"
    "$LPY" eval/latch_head_soup.py --bell "$d" --sigma 2 --out "$SP/bell40_$name/${F}_best.pt" | tail -8
  fi
  echo "$(date +%H:%M) eval E ($name)"; bash eval/run_opt_grid_eval.sh E; echo "$(date +%H:%M) eval E rc=$?"
}

# shellcheck disable=SC2086
cont MuonG $MUON --adagc 1.04 --batch-size 32 --grad-accum 2
# shellcheck disable=SC2086
cont Muon512 $MUON --dim 512 --batch-size 8 --grad-accum 8
cont KS512 --optimizer kl_soap --lr 1.82e-4 --warmup-epochs 0.68 --cosine-epochs 0 40 --dim 512 --batch-size 8 --grad-accum 8
echo "$(date +%H:%M) queue done"
