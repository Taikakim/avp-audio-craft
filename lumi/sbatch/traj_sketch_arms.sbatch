#!/bin/bash
# traj_sketch_arms.sbatch — CONTINUITY 2026-08-18, Kim direct: "train a small rank 8 or 16 adapter and
# save every step for 1000 or even 10,000 steps and see how the trajectory really is ... That
# experiment needs to be done on Lumi."
#
# WHAT: eight single-GCD arms (five regime arms + three damping arms, see SPEC) of the sanity16 recipe (LoRA r16 a16, lr 1e-4, T256, bf16 base, goa
# latents_sa3 with its json prompts — the SAME data path the healthy fp32cmp/bf16cmp twins used) that
# differ only in the two axes the weight-space forensics point at:
#     bs1_adamw     bs 1                    10 000 steps   the AdamW-sweep regime (path eff at 1/sqrt(n))
#     accum8_adamw  bs 1 x grad-accum 8      5 000 steps   8x the gradient SNR per step, same data/step as bs8
#     bs8_adamw     bs 8                     5 000 steps   the batch the healthy twins ran at
#     bs1_fusion    bs 1, --optimizer fusion 10 000 steps   optimizer control: NS5/NorMuon/SF flattens
#     bs8_fusion    bs 8, --optimizer fusion  5 000 steps   spectra by construction; is THAT the difference?
# Every optimizer step's UPDATE and GRADIENT are CountSketched (stable-audio-3/scripts/trajectory_sketch.py:
# inner-product-preserving, so the full Gram of the walk — step cosines, path efficiency at every window,
# autocorrelation, gradient SNR, PCA — is recoverable from ~4 KB/step) + trainable-only checkpoints EVERY
# step for the first 1000 and every 5 after (~23 MB each -> ~65 GB/arm; Kim: we have space, delete once
# there is a qualitative result). Sketch seed is fixed and shared, so arms are directly comparable.
#
# WHY THESE ARMS. The AdamW-sweep arms Kim hears as broken have (a) successive epoch displacements
# uncorrelated — path efficiency 0.31-0.38 = the 1/sqrt(9) random-walk floor — and (b) 20-30 % of each
# matrix's delta energy in ONE singular direction shared across arms, where every healthy run is flat.
# The healthy runs were Fusion at bs8; the broken ones AdamW at bs1/bs4. Two axes, confounded in the
# archive. This job separates them at step resolution.
#
# RUN:  sbatch lumi/sbatch/traj_sketch_arms.sbatch            (all eight)
#       ARMS="bs1_adamw bs8_fusion" sbatch ...                (subset)
#       SMOKE=1 sbatch ...                                    (30 steps each, ~5 min, exit code = the gate)
# READ: eval/trajectory_sketch_analyze.py <run>/traj  (CPU; also cross-run with several dirs)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=traj_sketch
#SBATCH --output=%x-%j.out

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
SMOKE=${SMOKE:-0}
RUNROOT=${RUNROOT:-${SCRATCH}/runs/traj_sketch}
LAT=latents_sa3
ARMS=${ARMS:-"bs1_adamw accum8_adamw bs8_adamw bs1_fusion bs8_fusion bs1_fusion_cos bs1_fusion_snr bs1_fusion_cos_snr"}

# arm -> "BS ACCUM OPT STEPS EXTRA..."   (EXTRA = the damping flags; C 2026-08-19, Kim's muon damping
# tests: the magnitude-blind NS5->NorMuon step has no brake, SF only damps a random walk by 1/sqrt(3),
# wd 0.03 binds with a 3e5-step time constant. Three ways to give it one, same seed/data as bs1_fusion:)
#   _cos     in-optimizer cosine decay to 0 over the run (the schedule Muon recipes actually use)
#   _snr     per-neuron SNR gate: step *= |EMA(U)|/RMS(U) (0.23 on noise, 1 on signal — Adam's brake)
#   _cos_snr both
declare -A SPEC=(
  [bs1_adamw]="1 1 adamw 10000"
  [accum8_adamw]="1 8 adamw 5000"
  [bs8_adamw]="8 1 adamw 5000"
  [bs1_fusion]="1 1 fusion 10000"
  [bs8_fusion]="8 1 fusion 5000"
  [bs1_fusion_cos]="1 1 fusion 10000 --fusion-decay cosine"
  [bs1_fusion_snr]="1 1 fusion 10000 --fusion-snr row"
  [bs1_fusion_cos_snr]="1 1 fusion 10000 --fusion-decay cosine --fusion-snr row"
)

[ -n "${SIF}" ] || { echo "[traj] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[traj] FATAL: ${VENV} missing"; exit 1; }
# code-currency guards: this needs the recorder AND its train_lora.py flags rsync'd up
[ -f "${CODE}/stable-audio-3/scripts/trajectory_sketch.py" ] \
  || { echo "[traj] FATAL: scripts/trajectory_sketch.py not on LUMI -- rsync the stable-audio-3 tree"; exit 1; }
grep -q 'traj_sketch_dir' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[traj] FATAL: train_lora.py lacks --traj-sketch-dir -- rsync the stable-audio-3 tree"; exit 1; }
grep -q 'fusion_snr' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[traj] FATAL: train_lora.py lacks --fusion-decay/--fusion-snr -- rsync the stable-audio-3 tree"; exit 1; }
grep -q 'def snr_gate' ${CODE}/lumi/vendor/stable_audio_tools/training/fusion_opt.py \
  || { echo "[traj] FATAL: vendored fusion_opt.py lacks the damping code -- rsync lumi/vendor"; exit 1; }
if [ "${SMOKE}" != "1" ] && [ "${VENV}" != "" ]; then :; fi

if [ ! -d "${FLASH}/${LAT}" ]; then
  echo "[traj] staging ${LAT} -> ${FLASH}"
  mkdir -p "${FLASH}/${LAT}"
  cp "${SCRATCH}/${LAT}"/*.npy "${SCRATCH}/${LAT}"/*.json "${FLASH}/${LAT}/" 2>/dev/null || true
fi
NLAT=$(ls "${FLASH}/${LAT}"/*.npy 2>/dev/null | wc -l)
NJSON=$(ls "${FLASH}/${LAT}"/*.json 2>/dev/null | wc -l)
[ "${NLAT}" -gt 0 ] || { echo "[traj] FATAL: no latents in ${FLASH}/${LAT}"; exit 1; }
# the json prompts ARE the captions on this corpus (no sidecar; same as the healthy twins) — a
# latent without its json trains on an empty caption, silently
[ "${NJSON}" -ge "$((NLAT * 9 / 10))" ] || { echo "[traj] FATAL: ${NJSON} json for ${NLAT} latents -- prompts missing"; exit 1; }
echo "[traj] latents=${NLAT} json=${NJSON} arms: ${ARMS}  smoke=${SMOKE}"

run_arm() {  # run_arm NAME GCD
  local NAME=$1 GCD=$2
  read -r BS ACC OPT STEPS EXTRA <<< "${SPEC[$NAME]}"
  EXTRA=${EXTRA:-}
  [ "${SMOKE}" = "1" ] && STEPS=30
  local DENSE=1000; [ "${SMOKE}" = "1" ] && DENSE=30
  local RUN="${RUNROOT}/${NAME}"; mkdir -p "${RUN}"
  local PORT=$((29600 + GCD))
  local OPT_ARGS="--optimizer ${OPT} ${EXTRA}"
  # fusion on LUMI needs the vendored SAT (lumi/vendor) — on the PYTHONPATH below, same as every fusion job
  cat > "${RUN}/run_meta.json" <<META
{"run": "traj_sketch_${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Step-resolution weight trajectory (Kim 2026-08-18): does constant-LR AdamW at small effective batch random-walk (uncorrelated steps, path efficiency at 1/sqrt(n)) or drift, and is the flat-vs-spiky singular spectrum an optimizer (Fusion NS5) or a batch-size effect?",
 "recipe": {"adapter": "lora", "rank": 16, "alpha": 16, "lr": 1e-4, "optimizer": "${OPT}", "damping": "${EXTRA}", "precision": "bf16", "frames": 256, "batch_size": ${BS}, "accumulate_grad_batches": ${ACC}, "effective_batch": $((BS*ACC)), "steps": ${STEPS}},
 "dataset": {"latents": "${LAT}", "n_latents": ${NLAT}, "captions": "per-crop json prompt (no sidecar), as the healthy fp32cmp/bf16cmp twins"},
 "artifacts": {"trajectory": "${RUN}/traj", "ckpt_dense_until": ${DENSE}, "ckpt_every": 5},
 "recorder": "stable-audio-3/scripts/trajectory_sketch.py", "script": "lumi/sbatch/traj_sketch_arms.sbatch",
 "result": null, "kim_feedback": null}
META
  srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=6 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export ROCR_VISIBLE_DEVICES='"${GCD}"'
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
export SLURM_JOB_NAME=bash
export MASTER_PORT='"${PORT}"'
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${GCD}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${GCD}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${GCD}"' PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  --adapter_type lora --rank 16 --lora_alpha 16 \
  '"${OPT_ARGS}"' --lr 1e-4 \
  --encoded_dir '"${FLASH}"'/'"${LAT}"' \
  --frames 256 --batch_size '"${BS}"' --accumulate_grad_batches '"${ACC}"' --num_workers 4 \
  --steps '"${STEPS}"' --checkpoint_every 100000 --no_demos --seed 1 \
  --save_dir '"${RUN}"'/run \
  --traj-sketch-dir '"${RUN}"'/traj --traj-ckpt-every 5 --traj-ckpt-dense-until '"${DENSE}"' \
  2>&1 | sed "s/^/['"${NAME}"'] /"
' &
}

PIDS=(); NAMES=(); i=0
for A in ${ARMS}; do
  [ -n "${SPEC[$A]:-}" ] || { echo "[traj] unknown arm ${A}"; continue; }
  echo "[traj] launching ${A} on GCD ${i}"
  run_arm "${A}" "${i}"; PIDS+=($!); NAMES+=("${A}"); i=$((i+1)); sleep 5
done
NFAIL=0
for k in "${!PIDS[@]}"; do
  if wait "${PIDS[$k]}"; then echo "[traj] arm OK      ${NAMES[$k]}"
  else echo "[traj] arm FAILED  ${NAMES[$k]}"; NFAIL=$((NFAIL+1)); fi
done
for A in ${ARMS}; do
  echo "[traj]   ${A}: $(python3 -c "import json,sys;print(json.load(open('${RUNROOT}/${A}/traj/done.json'))['rows_written'])" 2>/dev/null || echo '?') steps recorded, $(ls ${RUNROOT}/${A}/traj/ckpt 2>/dev/null | wc -l) ckpts"
done
echo "[traj] ${NFAIL} arm(s) failed"
[ "${NFAIL}" -eq 0 ] || exit 1
echo "[traj] READ: eval/trajectory_sketch_analyze.py ${RUNROOT}/<arm>/traj   (all arms share the sketch seed)"
