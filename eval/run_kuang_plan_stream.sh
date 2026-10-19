#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-17)
# run_kuang_plan_stream.sh -- the self-running part of docs/modular-opt-test-plan-2026-10-17.md, in the plan's order:
#   T  (control/time_film_t_section.sh: bf16 NS / fp32 optimizer state / batched NS, 5 x 400 FiLM steps, ~25 min)
#   A  FiLM precision, E12 bracket recipe + fp32 optimizer state (--mod-state-dtype fp32), 6000 steps each:
#      A4 lr 3e-4, A5 lr 1e-3, A6 lr 3e-3, A7 lr 1e-3 seed 43 (repeat), A8 lr 1e-3 --grad-accum 1 --ema 0 (the shipped run's
#      accumulation/EMA). A1-A3 (bf16 state) = the E12 bracket arms (film_modular_bracket_20261015), reused: the new options
#      at their defaults reproduce the old optimizer bit-for-bit. Grad-noise (N) and per-group (C4) logs on A4-A7. ~4 h.
#   P0 LatCH anchor = Phase E E05 recipe + --save-opt-state --log-mom-spectra 200 --log-grad-noise 50 --log-opt-groups, ~1.5 h.
#   P1 spectral probe on P0 (--point y), read-only.
# STOPS there: B needs the owner's go (Phase F overlap) and a decision on the LatCH routing regex first (plan section P).
# Holds the GPU lock as WINTERMUTE (batch) for the whole stream. Each stage is resumable (skips arms already in its SUMMARY).
#   bash eval/run_kuang_plan_stream.sh        (run detached: setsid nohup ... &)
set -u
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
LPY=$SAO/.venv-rocm10-amd/bin/python
AOUT=/run/media/kim/Mantu/sa3_control_runs/film_precision_A_20261017
POUT=/run/media/kim/Mantu/latch_sweep/kuang_plan_P_20261017
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE modular-opt test plan stream: T, A (FiLM precision), P0/P1 (~6.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

# ---- T ----
echo "$(date +%H:%M) T: throughput"
bash control/time_film_t_section.sh

# ---- A ----
echo "$(date +%H:%M) A: FiLM precision"
mkdir -p "$AOUT"; touch "$AOUT/SUMMARY.tsv"
cat > "$AOUT/run_meta.json" <<EOF
{"purpose": "Test plan section A (docs/modular-opt-test-plan-2026-10-17.md): does fp32 optimizer state (--mod-state-dtype fp32) fix the bf16 rounding of ModularOptimizer steps on the FiLM adapter (KUANG F21/H1)?",
 "hypothesis": "fp32-state arms at lr 3e-4 / 1e-3 train clearly better than the bf16 E12 arms at the same lr; the lr optimum moves down.",
 "kill": "fp32 arms within noise of bf16 at every lr",
 "baseline_bf16_arms": "/run/media/kim/Mantu/sa3_control_runs/film_modular_bracket_20261015 (A1-A3, same recipe, bf16 state)",
 "recipe": "E12 bracket: medium-base bf16, crop 512 random, batch 1, accum 2, EMA 0.999, Shampoo, warmup 300, scalar onset_density, 6000 steps, save every 2000; + --mod-state-dtype fp32",
 "reading": "6000 steps is too short for a density response (production FiLM: spread 0.2 at its own step 5400), so read loss, opt_groups.jsonl (per-group relative update) and grad_noise.jsonl; density only on a later long run",
 "dataset": "latents_sa3 (Kosmos), goa corpus, no augmentation", "result": null, "kim_feedback": null}
EOF
COMMON="--encoded-dirs /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 --crop-frames 512 --random-crop --batch 1 --optimizer modular --mod-whitening shampoo --warmup-steps 300 --no-checkpoint --no-preencode-text --timestep-sampler logit_normal --control-mode scalar --scalar-field onset_density --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 --num-workers 4 --no-export-onnx-on-finish --steps 6000 --save-every 2000 --mod-state-dtype fp32 --log-opt-groups"
ARMS=(
"A4_fp32state_lr3e-4|--lr 3e-4 --seed 42 --log-grad-noise 50"
"A5_fp32state_lr1e-3|--lr 1e-3 --seed 42 --log-grad-noise 50"
"A6_fp32state_lr3e-3|--lr 3e-3 --seed 42 --log-grad-noise 50"
"A7_fp32state_lr1e-3_seed43|--lr 1e-3 --seed 43 --log-grad-noise 50"
"A8_fp32state_lr1e-3_acc1_noema|--lr 1e-3 --seed 42 --grad-accum 1 --ema 0"
)
cd "$SAO/control" || exit 2
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$AOUT/SUMMARY.tsv" && continue
  mkdir -p "$AOUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  "$PY" sa3_control/train.py $COMMON $rest --save-dir "$AOUT/$name" --run-name "$name" --step-times "$AOUT/$name/steps.tsv" > "$AOUT/$name/train.log" 2>&1
  rc=$?
  last=$(grep -oE "^\[step [0-9]+/6000\] loss [0-9.]+" "$AOUT/$name/train.log" | tail -50 | awk '{s+=$NF;n++} END{if(n) printf "%.4f", s/n}')
  printf '%s\t%s\tlast50log_mean_loss=%s\tfinal=%s\trc=%s\n' "$name" "$(( $(date +%s) - t0 ))" "${last:-NA}" \
      "$([ -f "$AOUT/$name/riffer_final.pt" ] && echo yes || echo NO)" "$rc" >> "$AOUT/SUMMARY.tsv"
  echo "$(date +%H:%M) $name rc=$rc final=$([ -f "$AOUT/$name/riffer_final.pt" ] && echo yes || echo NO)"
done
cd "$SAO" || exit 2

# ---- P0 ----
echo "$(date +%H:%M) P0: LatCH anchor with optimizer state"
mkdir -p "$POUT/P0_E05_anchor"
cat > "$POUT/run_meta.json" <<EOF
{"purpose": "Test plan section P (docs/modular-opt-test-plan-2026-10-17.md): P0 = the Phase E E05 head recipe re-run with --save-opt-state / momentum spectra / grad-noise / per-group logs, so the P1 spectral probe can read the run's own momentum at the gradient point; P1 = that probe, read-only.",
 "recipe": "E05_depth8_ep20 (latch_sweep/modular_2026-09-30/phaseE_arms.txt): onset_per_beat_ts, latents_goa_bigset, 20 ep, modular Shampoo lr 1e-2, warmup 500, batch 16, radial brake 0.8, escape velocity, depth 8, val 5% by relpath, seed 0",
 "result": null, "kim_feedback": null}
EOF
if [ ! -f "$POUT/P0_E05_anchor/DONE" ]; then
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/train_latch.py" --feature onset_per_beat_ts \
      --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath --epochs 20 --val-frac 0.05 --val-seed 0 \
      --seed 0 --standardize --num-workers 16 --optimizer modular --mod-whitening shampoo --lr 1e-2 --mod-warmup 500 --batch-size 16 \
      --mod-radial-brake 0.8 --mod-escape-velocity --depth 8 \
      --save-opt-state --log-mom-spectra 200 --log-grad-noise 50 --log-opt-groups \
      --save-dir "$POUT/P0_E05_anchor" > "$POUT/P0_E05_anchor/train.log" 2>&1 ) && touch "$POUT/P0_E05_anchor/DONE"
  echo "$(date +%H:%M) P0 rc=$? $(ls "$POUT"/P0_E05_anchor/*.pt 2>/dev/null | wc -l) checkpoints"
fi

# ---- P1 ----
CK=$(ls "$POUT"/P0_E05_anchor/*best*.pt 2>/dev/null | head -1)
if [ -n "$CK" ]; then
  echo "$(date +%H:%M) P1: spectral probe on $(basename "$CK")"
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/spectral_probe.py" --ckpt "$CK" \
      --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --feature onset_per_beat_ts --val-frac 0.05 --val-seed 0 \
      --val-group-by relpath --lr 1e-2 --point y --repeats 3 --out "$POUT/P1_probe_y" > "$POUT/P1_probe_y.log" 2>&1 )
  echo "$(date +%H:%M) P1 rc=$?"
else
  echo "$(date +%H:%M) P1 skipped: no P0 checkpoint"
fi
echo "$(date +%H:%M) STREAM DONE (B not launched: needs the owner's go + routing decision)"
