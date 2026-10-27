#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-16)
# run_chroma_retrain.sh -- the same_chroma LatCH head (other-stem SAME chroma, 384-ch, cosine loss) retrained under the modular
# trainer, as the air and bass heads were. Asked 2026-10-16 after a listening pass on riffer-evals/clips/chroma_steer: the production
# head steers, transparently (pad chords change their notes), most audibly at gain 2048. Production head = AdamW, EMA 0.999, depth 4,
# 20 epochs, train-loss selected. Recipe here = G's bass low-lr bracket (latch/run_bass_lr.sh): modular + Schedule-Free, Shampoo,
# Muon on all 2-D, d512 depth 8, warmup 1 ep, grad clip 1.0, EMA half-life 1 ep (+0.25 ep, +online), every epoch saved, held-out
# val by source relpath. Loss stays cosine and targets stay unstandardised (scale-invariant chroma, as the production head).
# Arms: C3 lr 1e-3, C4 lr 1e-4, C2 lr 1e-2 (reference; the ceiling found on the air head). 20 epochs each (production length).
# Queued LAST: waits for the E12 night chain, the drone-sweep weights test and the anchor-sweep + FiLM-bracket extensions to exit, then G's LatCH queue, then the GPU lock.
#   bash latch/run_chroma_retrain.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT
busy() { pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_(film_e12_night|dronesweep_weights_test|anchor_sweep_ext|film_bracket_ext)\.sh$" >/dev/null || pgrep -f "latch/run_(air|bass)_" >/dev/null; }
while busy; do echo "$(date +%H:%M) earlier queue still running"; sleep 300; done
COMMON="--feature same_chroma --target-source chroma --chroma-dir /run/media/kim/Kosmos/latents/latents_sa3_stem_chroma --chroma-key other --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --num-workers 8 --loss cosine --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 20 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --wandb --wandb-project sa3-latch-chroma --log-every 20 --layer-every 100"
ARMS=(
"C3_chroma_d512_lr1e-3|$COMMON --lr 1e-3"
"C4_chroma_d512_lr1e-4|$COMMON --lr 1e-4"
"C2_chroma_d512_lr1e-2|$COMMON --lr 1e-2"
)
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
# stop the render server only if WINTERMUTE started it (2026-10-16: an unconditional stop killed GHOST-NOTE's server mid-grid)
grep -qs "^WINTERMUTE" "$HOME/.cache/latent-forge/server.8056.holder" && "$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
until "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 120; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; smoke test (20 steps)"
# shellcheck disable=SC2086
$PY "$TRAIN" ${ARMS[0]#*|} --max-steps 20 --save-dir "$OUT/_smoke" --run-name chroma_smoke > "$OUT/smoke.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "$(date +%H:%M) SMOKE FAILED rc=$rc, see $OUT/smoke.log"; exit 1; fi
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  mkdir -p "$OUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s)
  last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
  echo "$(date +%H:%M) $name rc=$rc best=${best:-NA}"
done
echo "$(date +%H:%M) ALL DONE"
