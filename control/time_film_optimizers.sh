#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# time_film_optimizers.sh -- why does the modular-optimizer FiLM train at 2.29 steps/s when the shipped FusionOpt FiLM (June) ran ~3.2?
# Same trainer, data and adapter, 400 steps per arm, only the optimizer path changes; steady steps/s is measured between the step-100
# and step-400 log lines (the log's rate is cumulative, so t(step) = step / rate). The GPU was at 93-99% during the full run, i.e. GPU-bound.
# Note: the trainer's defaults are now --ema 0.999 --grad-accum 2; the June run predates both flags (no EMA, an optimizer step every
# micro-batch), so arm F0 reproduces that recipe explicitly.
# Arms: F0 fusion as shipped (no EMA, accum 1) | F1 fusion + EMA + accum 2 (today's defaults) | A1 adamw | L1 lion |
#       M1 modular as the full run (Shampoo + NorMuon + Schedule-Free + EMA) | M2 no whitening (plain Scion-style LMO) | M3 SOAP |
#       M4 no NorMuon | M5 no Schedule-Free | M6 no EMA. ~4-5 min each incl. model load, ~45 min total.
# Queued after the chroma retrain (latch/run_chroma_retrain.sh), then the GPU lock. Output: SUMMARY.tsv under OUT.
#   bash control/time_film_optimizers.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
OUT=/run/media/kim/Mantu/sa3_control_runs/film_optimizer_timing_20261016
SCR=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/opt_timing
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
while pgrep -f "^bash (/home/kim/Projects/SAO/)?latch/run_chroma_retrain\.sh$" >/dev/null; do echo "$(date +%H:%M) chroma retrain still queued/running"; sleep 300; done
cd "$SAO/control" || exit 2
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE FiLM optimizer timing (10 x 400 steps, ~45 min)" \
      "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
cat > "$OUT/run_meta.json" <<EOF
{"purpose": "Throughput of the FiLM control-adapter trainer per optimizer path: the modular-optimizer full run trains at 2.29 steps/s vs ~3.2 for the shipped FusionOpt FiLM in June; find which component costs the time.",
 "method": "400 steps per arm, identical args except the optimizer flags; steady steps/s between the step-100 and step-400 log lines.",
 "common": "medium-base bf16, crop 512 random, batch 1, scalar onset_density, control_dim 768, n_tokens 256, cfg dropout 0.1, warmup 50, seed 42, latents_sa3 (Kosmos)",
 "related": ["control/time_film_optimizers.sh", "control/run_film_modular_full.sh", "EXPERIMENTS E12"], "result": null, "kim_feedback": null}
EOF
COMMON="--encoded-dirs /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 --crop-frames 512 --random-crop --batch 1 --warmup-steps 50 --no-checkpoint --no-preencode-text --timestep-sampler logit_normal --control-mode scalar --scalar-field onset_density --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 --num-workers 4 --seed 42 --no-export-onnx-on-finish --steps 400 --save-every 100000 --log-every 20"
ARMS=(
"F0_fusion_shipped|--optimizer fusion --lr 1e-4 --ema 0 --grad-accum 1"
"F1_fusion_ema_acc2|--optimizer fusion --lr 1e-4"
"A1_adamw|--optimizer adamw --lr 1e-4"
"L1_lion|--optimizer lion --lr 1e-5"
"M1_modular_full|--optimizer modular --mod-whitening shampoo --lr 1e-3"
"M2_modular_nowhiten|--optimizer modular --mod-whitening none --lr 1e-3"
"M3_modular_soap|--optimizer modular --mod-whitening soap --lr 1e-3"
"M4_modular_no_normuon|--optimizer modular --mod-whitening shampoo --no-mod-normuon --lr 1e-3"
"M5_modular_no_sf|--optimizer modular --mod-whitening shampoo --no-mod-sf --lr 1e-3"
"M6_modular_no_ema|--optimizer modular --mod-whitening shampoo --ema 0 --lr 1e-3"
)
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  rm -rf "$SCR"; mkdir -p "$SCR"
  # shellcheck disable=SC2086
  "$PY" sa3_control/train.py $COMMON $rest --save-dir "$SCR" --run-name "time_$name" > "$OUT/$name.log" 2>&1
  rc=$?
  r100=$(grep -E "^\[step 100/" "$OUT/$name.log" | grep -oE "[0-9.]+ it/s" | cut -d' ' -f1)
  r400=$(grep -E "^\[step 400/" "$OUT/$name.log" | grep -oE "[0-9.]+ it/s" | cut -d' ' -f1)
  steady=$(python3 -c "print(round(300/(400/$r400-100/$r100),3))" 2>/dev/null || echo NA)
  printf '%s\t%s\tsteady=%s\tcum400=%s\trc=%s\n' "$name" "$rest" "$steady" "${r400:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
  echo "$(date +%H:%M) $name steady=$steady steps/s rc=$rc"
  rm -rf "$SCR"
done
echo "$(date +%H:%M) ALL DONE"; cat "$OUT/SUMMARY.tsv"
