#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-16)
# Owner OK'd 2026-10-16: "the decorrelation test should be interesting". Bass head, the B2 recipe (modular+SF, lr 1e-2, d512 dp8, 10 epochs, EMA 1 ep, every epoch saved) plus a DeCov-style penalty on the
# head's final hidden features (--decorr-lambda): D1 lambda 0.1, D2 lambda 1.0. B2 is the control (same seed/recipe, lambda 0). Judged by the cross-talk meter (eval/latch_crosstalk.py, CT_BASS = the bass
# checkpoint under test): gradient cosine of the bass head with production body/mid/air heads, and the decoded-audio response of the other bands when bass is raised. Also val loss and, if worthwhile, the bass page/grid.
# Order: 12-step smoke (aborts everything if the penalty does not run) -> D1, D2 -> cross-talk for B2, D1, D2 -> /tmp/bass_decorr.done (success only).
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/bass_decorr_2026-10-16
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT
COMMON="--feature rms_energy_bass --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --save-every-epoch --save-online --optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 10 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --lr 1e-2 --wandb --wandb-project sa3-latch-bass-decorr --log-every 20 --layer-every 100"
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
lock() { until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done; }
unlock() { "$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1; }
lock
# shellcheck disable=SC2086
$PY "$TRAIN" $COMMON --decorr-lambda 1.0 --max-steps 12 --epochs 1 --save-dir "$OUT/smoke" --run-name smoke > "$OUT/smoke.log" 2>&1
unlock
grep -qE "decorr=[0-9.]+" "$OUT/smoke.log" || { echo "SMOKE FAILED" > "$OUT/SMOKE_FAILED"; exit 1; }
for a in "D1_bass_decorr0.1|0.1" "D2_bass_decorr1.0|1.0"; do
  name=${a%%|*}; lam=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  lock; mkdir -p "$OUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $COMMON --decorr-lambda $lam --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s); unlock
  last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
done
B=/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16
for x in "B2|$B/B2_bass_d512_lr1e-2" "D1|$OUT/D1_bass_decorr0.1" "D2|$OUT/D2_bass_decorr1.0"; do
  n=${x%%|*}; d=${x#*|}
  [ -f "$OUT/ct_$n/audit/realised.json" ] && continue
  lock
  CT_BASS="$d/latch_sa3_rms_energy_bass_ep10.pt" CT_OUT="$OUT/ct_$n" "$SAO/.venv/bin/python" "$SAO/eval/latch_crosstalk.py" run > "$OUT/ct_$n.log" 2>&1
  unlock
  /home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_realised_levels.py" "$OUT/ct_$n/audit" > "$OUT/ct_$n.realised.log" 2>&1
  CT_OUT="$OUT/ct_$n" "$SAO/.venv/bin/python" "$SAO/eval/latch_crosstalk.py" report > "$OUT/ct_$n.report.txt" 2>&1
done
grep -qE "rc=[1-9]" "$OUT/SUMMARY.tsv" || echo DECORR DONE > /tmp/bass_decorr.done
