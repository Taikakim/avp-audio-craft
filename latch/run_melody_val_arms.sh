#!/usr/bin/env bash
# run_melody_val_arms.sh — CONTINUITY 2026-08-18, unattended local run (Kim away ~4h).
#
# WHAT THIS ANSWERS. The D3 melody head (f0_other = lead voice, f0_bass = bassline) has only ever
# been trained as a 3-epoch pilot, and the 2026-08-14 architecture bracket ran 5 epochs per arm and
# came back inside noise (<2% gaps, and the two voices disagreed on the winner). Neither could
# settle anything, because until today train_latch.py had NO held-out set at all: `_best.pt` was
# whichever epoch had the lowest TRAINING loss. That selects the most-memorised checkpoint and
# reports it as the best one.
#
# So these arms are the first honest look at the melody head:
#   1. does it generalise at all, or was the falling pilot loss memorisation?
#   2. WHERE does it turn over — the epoch budget every later run should use;
#   3. concat vs adaln_zero, re-asked at a length where the answer can survive noise.
#
# THE SPLIT IS BY SOURCE TRACK, and that is not a detail: in latents_sa3 every one of the 2676
# tracks contributes >=2 crops, so a crop-level split would leak a sibling crop of nearly every
# val track into train. Sibling goa crops share key, lead patch and often literal repeated loop
# material — for an f0 target that is close to validating on the training set.
#
# PER-ARM SAVE DIRS ARE MANDATORY (2026-08-14, learned the hard way): train_latch.py's checkpoint
# names carry no run id, so two runs sharing a save-dir interleave their epochs into one filename
# sequence that LOOKS like a single training curve and is actually two different random inits.
#
# Sequential on purpose — one 16 GB card, and concurrent GPU jobs have crashed this box twice.
# Caller holds the GPU mutex (SAO/.gpu.lock + /tmp/gpu.lock); this script does not take it.
#
# --num-workers 4: TESTED on this exact script/venv 2026-08-18 (forks fine, reaches training).
# The 2026-08-14 journal note that "any multi-worker DataLoader crashes on fork in SAO/.venv"
# came from a DIFFERENT script and does NOT generalise to train_latch.py — worth knowing,
# because single-process loading is the bottleneck here: with --num-workers 0 one epoch of
# 4581 crops takes ~5 min, and each crop is a 2 MB .npy plus its .npz companion.
set -uo pipefail

SA3=/home/kim/Projects/SAO/stable-audio-3
PY=/home/kim/Projects/SAO/.venv/bin/python
LATENTS=${LATENTS:-/home/kim/Projects/latents_sa3}
OUT=${OUT:-${SA3}/latch_weights_sa3_medium}
LOGDIR=${LOGDIR:-/home/kim/Projects/SAO/latch/val_arm_logs}
# 30 epochs is a budget, not a belief: it is what fits the unattended window at the measured
# epoch cost. summarize_val_arms.py flags an arm whose best epoch IS its last as STILL-IMPROVING
# rather than reporting it as a verdict, so an under-budgeted arm says so instead of lying.
EPOCHS=${EPOCHS:-30}
VAL_FRAC=${VAL_FRAC:-0.15}
SEED=${SEED:-0}

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
mkdir -p "${LOGDIR}"
cd "${SA3}" || exit 1

# arm := <voice>:<ema>. Plain arms first, so a truncated run still answers Q1/Q2 for both
# voices; the EMA comparison is the part that degrades gracefully.
#
# WHY EMA IS THE SECOND AXIS AND NOT ARCHITECTURE. The obvious follow-up to 2026-08-14 was to
# re-run concat-vs-adaln_zero at honest length. But the LatCH precedent argues against asking
# that question first: `spectral_skewness` was once declared ARCHITECTURE-LIMITED, and an
# EMA re-train reversed the verdict — the ceiling was damping-limited all along (MASTER §4).
# The same trajectory work found these heads find the control direction and then DRIFT, with
# averaging (not a smaller LR) as the fix, which is why the standing LatCH recipe is
# EMA + grad-accum + early-stop. Running an architecture bracket on an undamped head therefore
# risks re-deriving that exact mistake. Settle damping first; architecture is then askable at a
# known-good epoch budget, which is precisely what 08-14 lacked.
#
# Only --ema varies. The documented recipe pairs EMA with grad-accum 2, deliberately NOT varied
# here: it doubles the effective batch, which would confound "does averaging help" with "does a
# bigger batch help" — the confound the 8-GPU DDP arm has to reason about on the LUMI side too.
ARMS=(
  "f0_other:0"
  "f0_bass:0"
  "f0_other:0.999"
  "f0_bass:0.999"
)

echo "[arms] start $(date -Iseconds)  epochs=${EPOCHS} val_frac=${VAL_FRAC} seed=${SEED}"
for arm in "${ARMS[@]}"; do
  voice="${arm%%:*}"; ema="${arm##*:}"
  tag=$([ "${ema}" = "0" ] && echo "plain" || echo "ema${ema}")
  name="val${EPOCHS}_${voice}_${tag}"
  save="${OUT}/${name}"
  log="${LOGDIR}/${name}.log"
  if [ -f "${save}/latch_sa3_${voice}_best.pt" ]; then
    echo "[arms] SKIP ${name} (already has a best ckpt)"; continue
  fi
  mkdir -p "${save}"
  echo "[arms] ${name} -> ${log}  $(date -Iseconds)"
  "${PY}" scripts/latch/train_latch.py \
    --feature "${voice}" --target-source npz --voiced-field "${voice}_voiced_ts" \
    --latent-dir "${LATENTS}" \
    --val-frac "${VAL_FRAC}" --val-seed "${SEED}" --val-group-by source_track \
    --t-injection adaln_zero --loss smooth_l1 --ema "${ema}" \
    --epochs "${EPOCHS}" --batch-size 32 --num-workers 4 --standardize \
    --save-best-only --seed "${SEED}" \
    --save-dir "${save}" > "${log}" 2>&1
  rc=$?
  echo "[arms] ${name} rc=${rc}  $(date -Iseconds)"

  # Self-describing output (MASTER §4): purpose + provenance beside the weights, written now,
  # not later. `result` stays null until the curve is read.
  cat > "${save}/run_meta.json" <<META
{
  "run": "${name}",
  "created": "$(date -Iseconds)",
  "purpose": "First held-out-validated training of the D3 melody head. Answers whether the head generalises on unseen tracks, at which epoch it turns over, and whether EMA damping helps -- none of which the 3-epoch pilot or the 5-epoch 2026-08-14 bracket could, both having been scored on training loss only.",
  "voice": "${voice}",
  "ema": ${ema},
  "recipe": {"t_injection": "adaln_zero", "loss": "smooth_l1", "epochs": ${EPOCHS}, "ema": ${ema},
             "batch_size": 32, "lr": 3e-4, "optimizer": "adamw", "precision": "bf16",
             "dim": 256, "depth": 4, "heads": 8, "standardize": true,
             "voiced_field": "${voice}_voiced_ts", "seed": ${SEED}},
  "validation": {"val_frac": ${VAL_FRAC}, "val_seed": ${SEED}, "group_by": "source_track",
                 "why_grouped": "every track in latents_sa3 has >=2 crops; a crop-level split leaks a sibling crop of nearly every val track into train",
                 "best_ckpt_selected_on": "val_loss"},
  "dataset": {"latents": "${LATENTS}", "corpus": "goa (Goa_Separated), beat-aligned T=4096 crops",
              "target": "PredominantPitchMelodia f0 on the separated stem, 100 Hz, masked by voiced fraction"},
  "script": "latch/run_melody_val_arms.sh",
  "trainer": "stable-audio-3/scripts/latch/train_latch.py",
  "log": "${log}",
  "exit_code": ${rc},
  "result": null,
  "kim_feedback": null
}
META
done

echo "[arms] all done $(date -Iseconds)"
echo "[arms] read the curves with: latch/summarize_val_arms.py ${LOGDIR}"
