#!/bin/bash
# local_drone_ablation.sh — CONTINUITY 2026-08-13 (Kim direct, away-from-keyboard ask):
# "run small tests with like only 50 tracks with the components different from Stability
# AI's upstream turned on one by one". Isolates, ONE VARIABLE AT A TIME, which of OUR
# additions to the full-FT training path (EMA / live-encode augment / FusionOpt-Muon /
# force_scalar routing / spectral wd+grad-clip) is implicated in the drone/square-wave
# divergence seen on the LUMI drone-sweep (adamw_fair_s2 diverged to a square wave at ep9
# despite being the "closest to upstream" AdamW recipe with clip already on — so optimizer
# choice alone doesn't explain it; this campaign tests each axis in isolation instead of
# the LUMI sweep's bundled recipes).
#
# Dataset: 49-track raw-audio subset of Goa_Separated (goa_ablate50_raw, stage_ablation50.py,
# stride-sampled, NOT the first N), --data_dir mode throughout (same live-encode path for
# EVERY arm, including the ones not testing --augment) so the encode path itself is never a
# confound between arms. T512 (47.56s) crops, batch_size 1, --steps 200 (measured 0.44 it/s
# AdamW/bf16+SR -> ~8 min/arm, ~4 epochs over 49 tracks) — a SCREENING pass, not a full
# reproduction; extend --steps if an arm looks borderline. All arms share --base_precision
# bf16 (+ --stochastic-rounding for the AdamW arms — the desktop-16GB full-FT enabler,
# unit-tested 2026-08-04, now ALSO smoke-validated end-to-end 2026-08-13, 20 steps exit 0).
#
# HARNESS GOTCHA (2026-08-13): launching train_lora.py under the CLI's run_in_background
# Bash mode gets silently killed ~15-20s in (right after imports, before model load) with
# no error — reproduced 3x, sandbox-disabled too, so it is NOT an OOM/driver/sandbox issue,
# just this environment's background-task handling disliking this GPU workload. Foreground
# calls (timeout up to 600s) work fine and are what this script + the campaign use — run
# arms as direct foreground Bash calls, not backgrounded, if driving this by hand.
#
# Single local 16GB card, sequential (no local multi-GPU) — GPU-locked for the whole
# campaign (one exclusive holder is simpler/safer than per-arm acquire/release racing
# against a background loop). ROCR pin N/A (single card).
set -uo pipefail   # NOT -e: one arm crashing (e.g. OOM) must not kill the rest of the sweep
VENV=/home/kim/Projects/SAO/.venv
CODE=/home/kim/Projects/SAO/stable-audio-3
DATADIR=/home/kim/Projects/goa_ablate50_raw
ROOT=/home/kim/Projects/SAO/runs/local_drone_ablation
LOCK=/home/kim/Projects/SAO/.gpu.lock
STEPS=${STEPS:-200}   # ~0.44 it/s measured (AdamW/bf16+SR, T512, local RDNA4 16GB) -> ~200
                       # steps/~8min per arm; smoke-validated 2026-08-13 (20 steps, exit 0)
mkdir -p "${ROOT}"

python3 /home/kim/Projects/SAO/Misc/filelock.py acquire "${LOCK}" --handle continuity --pid-aware --pid $$ \
  || { echo "[ablation] FATAL: could not acquire GPU lock"; exit 1; }
trap 'python3 /home/kim/Projects/SAO/Misc/filelock.py release "${LOCK}" --handle continuity' EXIT

source "${VENV}/bin/activate"
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
export PYTHONPATH="${CODE}:${PYTHONPATH:-}"
cd "${CODE}"

COMMON="--model medium-base --data_dir ${DATADIR} --full-finetune --frames 512 \
  --batch_size 1 --steps ${STEPS} --no_demos --num_workers 0"
# --num_workers 0 is REQUIRED on this venv (2026-08-13): SAO/.venv's torch build needs
# librocm-openblas.so.0 + librocprofiler-sdk.so.1 for torch_shm_manager (multiprocess
# DataLoader shared-memory IPC) and neither lib is installed on this system -> any
# num_workers>0 crashes the moment the DataLoader forks workers. Never caught before
# because this venv's prior use was inference-only / unit tests, never a real multi-
# worker training DataLoader. num_workers=0 sidesteps it entirely (single-process load,
# slower but correct); the real fix (installing the missing ROCm packages) is Kim's call.

declare -A ARMS=(
  [00_baseline_adamw]="--optimizer adamw --stochastic-rounding --base_precision bf16"
  [01_ema]="--optimizer adamw --stochastic-rounding --base_precision bf16 --use-ema"
  [02_augment]="--optimizer adamw --stochastic-rounding --base_precision bf16 --augment"
  [03_fusion]="--optimizer fusion --base_precision bf16"
  [04_fusion_wd_clip]="--optimizer fusion --base_precision bf16 --weight_decay 0.1 --gradient_clip_val 1.0"
  [05_fusion_force_scalar]="--optimizer fusion --base_precision bf16 --force-scalar-output"
  [06_adamw_wd_clip]="--optimizer adamw --stochastic-rounding --base_precision bf16 --weight_decay 0.1 --gradient_clip_val 1.0"
)
ORDER=(00_baseline_adamw 01_ema 02_augment 03_fusion 04_fusion_wd_clip 05_fusion_force_scalar 06_adamw_wd_clip)

for ARM in "${ORDER[@]}"; do
  SAVE="${ROOT}/${ARM}"
  mkdir -p "${SAVE}"
  echo "[ablation] === ${ARM} === $(date +%H:%M:%S)"
  echo "[ablation] args: ${ARMS[${ARM}]}"
  # shellcheck disable=SC2086
  python scripts/train_lora.py ${COMMON} ${ARMS[${ARM}]} --save_dir "${SAVE}" \
    2>&1 | tee "${SAVE}/train.log"
  RC=${PIPESTATUS[0]}
  echo "[ablation] ${ARM} exit=${RC} $(date +%H:%M:%S)"
done
echo "[ablation] campaign done. per-arm logs + CSVs under ${ROOT}/<arm>/"
