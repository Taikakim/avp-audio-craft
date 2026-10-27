#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-20)
# Last edited: WINTERMUTE 2026-10-21 — P1 falls back to the last _epN.pt (P1 was skipped: no _best.pt is written)
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# run_kuang_plan_p.sh -- test plan section P (docs/modular-opt-test-plan-2026-10-17.md) on its own, after P0 crashed at step 0 inside
# the stream (momentum_spectra: svdvals on the zero initial momentum; fixed in stable-audio-tools 1f5c58d). Same P0/P1 commands as
# eval/run_kuang_plan_stream.sh; the crashed attempt is kept as P0_E05_anchor_crash1. Exit codes are captured on their own line (the
# stream printed rc=0 for the crash). Holds the GPU lock as WINTERMUTE (batch). Stops before B (needs the owner's routing decision).
#   setsid nohup bash eval/run_kuang_plan_p.sh > <POUT>/p_rerun.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
POUT=/run/media/kim/Mantu/latch_sweep/kuang_plan_P_20261017
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE test plan P: LatCH E05 re-run with optimizer state + spectral probe (~2.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"
[ -d "$POUT/P0_E05_anchor" ] && [ ! -f "$POUT/P0_E05_anchor/DONE" ] && [ ! -e "$POUT/P0_E05_anchor_crash1" ] && \
    mv "$POUT/P0_E05_anchor" "$POUT/P0_E05_anchor_crash1"
mkdir -p "$POUT/P0_E05_anchor"
if [ ! -f "$POUT/P0_E05_anchor/DONE" ]; then
  echo "$(date +%H:%M) P0: LatCH anchor with optimizer state"
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/train_latch.py" --feature onset_per_beat_ts \
      --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath --epochs 20 --val-frac 0.05 --val-seed 0 \
      --seed 0 --standardize --num-workers 16 --optimizer modular --allow-uniform-lr --mod-whitening shampoo --lr 1e-2 --mod-warmup 500 --batch-size 16 \
      --mod-radial-brake 0.8 --mod-escape-velocity --depth 8 \
      --save-opt-state --log-mom-spectra 200 --log-grad-noise 50 --log-opt-groups \
      --save-dir "$POUT/P0_E05_anchor" > "$POUT/P0_E05_anchor/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) P0 rc=$rc, $(ls "$POUT"/P0_E05_anchor/*.pt 2>/dev/null | wc -l) checkpoints"
  [ "$rc" -eq 0 ] && touch "$POUT/P0_E05_anchor/DONE"
fi
CK=${CK:-$(ls "$POUT"/P0_E05_anchor/*best*.pt 2>/dev/null | head -1)}
# the trainer writes per-epoch snapshots (_epN.pt), not _best.pt, without --save-best-only: fall back to the last epoch
[ -z "$CK" ] && CK=$(ls -v "$POUT"/P0_E05_anchor/*_ep*.pt 2>/dev/null | tail -1)
if [ -n "$CK" ] && [ -f "$POUT/P0_E05_anchor/DONE" ]; then
  echo "$(date +%H:%M) P1: spectral probe on $(basename "$CK")"
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/spectral_probe.py" --ckpt "$CK" \
      --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --feature onset_per_beat_ts --val-frac 0.05 --val-seed 0 \
      --val-group-by relpath --lr 1e-2 --point y --repeats 3 --out "$POUT/P1_probe_y" > "$POUT/P1_probe_y.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) P1 rc=$rc"
else
  echo "$(date +%H:%M) P1 skipped: P0 did not finish"
fi
echo "$(date +%H:%M) P DONE (B not launched: needs the owner's go + routing decision)"
