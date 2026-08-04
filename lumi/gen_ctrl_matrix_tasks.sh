#!/bin/bash
# gen_ctrl_matrix_tasks.sh — emit the 60 exact train command lines for the control-matrix
# campaign (20 features x 3 variants). One full train invocation per line, each with its own
# --save-dir. The output is a reproducible, trim-friendly task list consumed by
# lumi/sbatch/ctrl_matrix_hq.sbatch (fed to hq submit, one HQ task per line).
#
# USAGE:   bash lumi/gen_ctrl_matrix_tasks.sh > lumi/ctrl_matrix_tasks.txt
#          (count is printed to stderr; the command lines go to stdout)
#
# LAYOUT of the 60 lines (grouped by variant so trimming is trivial):
#   lines  1-20 : latch    (LatCH head per feature, train_latch.py --target-source npz)
#   lines 21-40 : film     (sa3_control scalar,      --control-mode scalar)
#   lines 41-60 : filmbpm  (sa3_control dual_scalar, --control-mode dual_scalar + bpm)
#
# PATHS are the fixed LUMI absolutes so the emitted list is self-contained. They can be
# overridden via env before running the generator (FLASH/SCRATCH/CODE).
#
# QUOTE DISCIPLINE: every emitted line is free of apostrophes and backticks so the HQ task
# wrapper (singularity exec ... bash -c "...; <line>") stays quote-safe.
set -euo pipefail

FLASH=${FLASH:-/flash/project_465003186}
SCRATCH=${SCRATCH:-/scratch/project_465003186}
CODE=${CODE:-/project/project_465003186/code}

LAT_SA3=${FLASH}/latents_sa3
LAT_AVP=${FLASH}/latents_avp
RUNROOT=${SCRATCH}/runs/ctrl_matrix

LATCH_TRAINER=${CODE}/stable-audio-3/scripts/latch/train_latch.py

# The 20 campaign features, as BASE names (no _ts). train_latch.py takes the base name via
# --feature; sa3_control takes the per-frame field via --scalar-from-timeseries <F>_ts.
FEATURES=(
  # energy (4)
  rms_energy_bass rms_energy_body rms_energy_mid rms_energy_air
  # spectral (4)
  spectral_flatness spectral_flux spectral_skewness spectral_kurtosis
  # rhythm (3)
  onset_envelope beat_activation downbeat_activation
  # chroma (1)
  hpcp
  # per-stem (8)
  onset_envelope_drums onset_envelope_bass onset_envelope_other onset_envelope_vocals
  rms_drums rms_bass rms_other rms_vocals
)

n=0

# ── variant 1: LatCH head ────────────────────────────────────────────────────────────────
# Validated recipe: fusion + ns5,normuon,sf + EMA 0.999 + grad-accum 2 + standardize + compile
# + adaln_zero t-injection + dim 256 depth 4 + 30 epochs. target-source npz for ALL features
# (hpcp REQUIRES npz under multi-root: the chroma/scalar_json sources collide across two roots;
# npz -> hpcp_ts is the path-correct one).
for F in "${FEATURES[@]}"; do
  echo "python ${LATCH_TRAINER} --feature ${F} --target-source npz --latent-dirs ${LAT_SA3} ${LAT_AVP} --optimizer fusion --components ns5,normuon,sf --ema 0.999 --grad-accum 2 --standardize --compile --t-injection adaln_zero --dim 256 --depth 4 --epochs 30 --save-dir ${RUNROOT}/latch_${F}"
  n=$((n+1))
done

# ── variant 2: FiLM lone scalar ──────────────────────────────────────────────────────────
# Density-reference recipe: fusion, lr 1e-4, random-crop, EMA 0.999, grad-accum 2,
# max-epochs 20, crop-frames 1024. Conditions on the per-frame field <F>_ts (window-mean).
for F in "${FEATURES[@]}"; do
  echo "python -m sa3_control.train --control-mode scalar --scalar-from-timeseries ${F}_ts --encoded-dirs ${LAT_SA3} ${LAT_AVP} --optimizer fusion --lr 1e-4 --random-crop --ema 0.999 --grad-accum 2 --max-epochs 20 --crop-frames 1024 --save-dir ${RUNROOT}/film_${F}"
  n=$((n+1))
done

# ── variant 3: FiLM + BPM (dual scalar) ──────────────────────────────────────────────────
# Same recipe, joint {feature, bpm_madmom} 2-vector (dual_scalar wires the bpm second scalar
# automatically inside the trainer).
for F in "${FEATURES[@]}"; do
  echo "python -m sa3_control.train --control-mode dual_scalar --scalar-from-timeseries ${F}_ts --encoded-dirs ${LAT_SA3} ${LAT_AVP} --optimizer fusion --lr 1e-4 --random-crop --ema 0.999 --grad-accum 2 --max-epochs 20 --crop-frames 1024 --save-dir ${RUNROOT}/filmbpm_${F}"
  n=$((n+1))
done

echo "[gen_ctrl_matrix_tasks] emitted ${n} task lines (20 features x 3 variants)" 1>&2
