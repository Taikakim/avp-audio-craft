#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# Last edited: WINTERMUTE 2026-10-17 -- copied from time_film_optimizers.sh for test plan section T (KUANG C-series flags)
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# time_film_t_section.sh -- modular-opt test plan section T: per-update cost of the C-series speed/precision options on the FiLM trainer.
# T1 today | T2 --mod-ns-dtype bf16 | T3 --mod-state-dtype fp32 | T4 both | T5 T4 + --mod-ns-batch. 400 steps each, ~25 min.
# No GPU lock of its own: run from eval/run_kuang_plan_stream.sh, which holds it.
set -u
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
OUT=/run/media/kim/Mantu/sa3_control_runs/film_t_section_20261017
SCR=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/opt_timing_t
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO/control" || exit 2
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"
cat > "$OUT/run_meta.json" <<EOF
{"purpose": "Test plan section T (docs/modular-opt-test-plan-2026-10-17.md): per-update cost of bf16 Newton-Schulz, fp32 optimizer state and batched NS in the ModularOptimizer on the FiLM trainer.",
 "method": "400 steps per arm, identical args except the optimizer flags; steady steps/s between the step-100 and step-400 log lines.",
 "common": "medium-base bf16, crop 512 random, batch 1, scalar onset_density, control_dim 768, n_tokens 256, cfg dropout 0.1, warmup 50, seed 42, latents_sa3 (Kosmos)",
 "related": ["control/time_film_optimizers.sh", "control/run_film_modular_full.sh", "EXPERIMENTS E12"], "result": null, "kim_feedback": null}
EOF
COMMON="--encoded-dirs /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 --crop-frames 512 --random-crop --batch 1 --warmup-steps 50 --no-checkpoint --no-preencode-text --timestep-sampler logit_normal --control-mode scalar --scalar-field onset_density --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 --num-workers 4 --seed 42 --no-export-onnx-on-finish --steps 400 --save-every 100000 --log-every 20"
ARMS=(
"T1_today|--optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-3"
"T2_ns_bf16|--optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-3 --mod-ns-dtype bf16"
"T3_state_fp32|--optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-3 --mod-state-dtype fp32"
"T4_ns_bf16_state_fp32|--optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-3 --mod-ns-dtype bf16 --mod-state-dtype fp32"
"T5_T4_ns_batch|--optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-3 --mod-ns-dtype bf16 --mod-state-dtype fp32 --mod-ns-batch"
)
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  rm -rf "$SCR"; mkdir -p "$SCR"
  # shellcheck disable=SC2086
  "$PY" sa3_control/train.py $COMMON $rest --save-dir "$SCR" --run-name "time_$name" --step-times "$OUT/$name.steps.tsv" > "$OUT/$name.log" 2>&1
  rc=$?
  stats=$(python3 - "$OUT/$name.steps.tsv" <<'PY' 2>/dev/null || echo "stats=NA"
import sys, statistics as st
L = open(sys.argv[1]).read().splitlines()
startup = float(L[0].split("\t")[1])
rows = [l.split("\t") for l in L[2:] if l.strip()]
dt = {int(r[0]): float(r[2]) for r in rows}
opt = {int(r[0]): r[3] == "1" for r in rows}
ss = [s for s in dt if s > 50]
med = st.median(dt[s] for s in ss)
mo = st.median([dt[s] for s in ss if opt[s]] or [float("nan")])
mn = st.median([dt[s] for s in ss if not opt[s]] or [float("nan")])
first5 = ",".join(f"{dt[s]:.2f}" for s in range(1, 6) if s in dt)
print(f"startup_s={startup:.1f}\tfirst_step_s={dt.get(1, float('nan')):.2f}\tsteps1-5_s={first5}\tsteady_ms={1000*med:.0f}\t"
      f"opt_step_ms={1000*mo:.0f}\tno_opt_ms={1000*mn:.0f}\tsteps_per_s={1/med:.2f}\tn={len(dt)}")
PY
)
  printf '%s\t%s\t%s\trc=%s\n' "$name" "$rest" "$stats" "$rc" >> "$OUT/SUMMARY.tsv"
  echo "$(date +%H:%M) $name $stats rc=$rc"
  rm -rf "$SCR"
done
echo "$(date +%H:%M) ALL DONE"; cat "$OUT/SUMMARY.tsv"
