#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-16)
# Owner's ask (2026-10-16): "a by the book pure Muon baseline at 1e-3 and 1e-4, just to see what we are competing against". Bass head, same data/arch/schedule as run_bass_lr.sh (d512 dp8, 10 epochs,
# EMA half-life 1 ep, every epoch saved, wandb offline) but with NOTHING of ours: M3/M4 = NVIDIA Emerging-Optimizers Muon (--optimizer muon_ref: Muon on hidden 2-D, AdamW on the rest, one lr),
# A3/A4 = plain AdamW (--optimizer adamw, default betas, wd 0.01) as the second baseline. lr 1e-3 and 1e-4 each. Compare with B3/B4 (modular+SF, same lrs) and B2 (lr 1e-2).
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/bass_baselines_2026-10-16
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT
COMMON="--feature rms_energy_bass --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --ema-halflife-epochs 1 --epochs 10 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --wandb --wandb-project sa3-latch-bass-baselines --log-every 20 --layer-every 100"
ARMS=(
"M3_bass_muonref_lr1e-3|$COMMON --optimizer muon_ref --lr 1e-3"
"M4_bass_muonref_lr1e-4|$COMMON --optimizer muon_ref --lr 1e-4"
"A3_bass_adamw_lr1e-3|$COMMON --optimizer adamw --lr 1e-3"
"A4_bass_adamw_lr1e-4|$COMMON --optimizer adamw --lr 1e-4"
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
grep -qE "rc=[1-9]" "$OUT/SUMMARY.tsv" || echo BASELINES DONE > /tmp/bass_baselines.done
