#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-21)
# run_kuang_plan_b.sh -- test plan section B (docs/modular-opt-test-plan-2026-10-17.md), LatCH head group balance (H2, H3).
# B0 = P0 (kuang_plan_P_20261017/P0_E05_anchor: E05 recipe, seed 0, same N/C4 logging), so it is not re-run.
# Order by information: B2 vs B3 is the H2 kill test (B3 is expected to diverge; train_latch stops on a NaN epoch), then B1, B4, B5.
# Routing is left as E05 ran it (AdaLN emitters / qkv whole in the spectral group, t_embedder in colnorm): a routing fix is a
# new arm, not a default change (plan section P). An arm starts only if it can finish before DEADLINE (epoch time from P0).
#   setsid nohup bash eval/run_kuang_plan_b.sh > <BOUT>/b.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
BOUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/kuang_plan_B_20261021
DEADLINE=${DEADLINE:-$(date -d '06:45' +%s)}; [ "$DEADLINE" -lt "$(date +%s)" ] && DEADLINE=$((DEADLINE + 86400))
ARM_SEC=${ARM_SEC:-6300}   # P0: 99 min for 20 epochs with N/C4 logging, + 6 min margin
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$BOUT"; cd "$SAO" || exit 2
# the P runner holds the lock under the same handle and releases it on exit: wait for it, or its release drops ours
while pgrep -f '^bash eval/run_kuang_plan_p\.sh' >/dev/null; do sleep 30; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE test plan B: LatCH group-balance arms, ~100 min each, until 06:45" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; deadline $(date -d @"$DEADLINE" +%H:%M)"
COMMON="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --epochs 20 --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --optimizer modular --mod-whitening shampoo
  --mod-warmup 500 --batch-size 16 --mod-radial-brake 0.8 --mod-escape-velocity --depth 8
  --log-grad-noise 50 --log-opt-groups --save-best-only"
ARMS=(
  "B2|--lr 3e-2 --mod-sign-lr 2e-3"
  "B3|--lr 3e-2"
  "B1|--lr 1e-2 --mod-sign-lr 2e-3"
  "B4|--lr 1e-2 --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95 --mod-momentum 0.8 --mod-wd 0.05 --mod-warmup 1500"
  "B5|--lr 2e-2 --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95 --mod-momentum 0.8 --mod-wd 0.05 --mod-warmup 1500"
)
for spec in "${ARMS[@]}"; do
  arm=${spec%%|*}; flags=${spec#*|}; d="$BOUT/$arm"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $arm already done"; continue; }
  if [ $(( $(date +%s) + ARM_SEC )) -gt "$DEADLINE" ]; then echo "$(date +%H:%M) $arm not started: would end after the deadline"; break; fi
  mkdir -p "$d"; echo "$(date +%H:%M) $arm: $flags"
  # later flags win in argparse, so the arm's --mod-warmup overrides COMMON's
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/train_latch.py" $COMMON $flags --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $arm rc=$rc; last: $(grep -E '^epoch|val=' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
done
echo "$(date +%H:%M) B runner done"
