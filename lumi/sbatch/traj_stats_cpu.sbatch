#!/bin/bash
# traj_stats_cpu.sbatch — CONTINUITY 2026-08-18, Kim direct: "before pruning, I think it would be
# interesting to generate statistics on the training paths from every checkpoint we have."
#
# WHY NOW AND NOT LATER: this is the one analysis that REQUIRES every checkpoint to still exist.
# Pruning or the allocation ending destroys the input permanently, and the trajectory is exactly
# what tells us where a long run stopped moving productively — the weight-side answer to the same
# question the audition sweep asks by ear (longrun_epoch_sweep_render.sbatch). If the two agree on
# where a run went off, that is a strong signal; if they disagree, that is more interesting still.
# Standing practice per MASTER: record the trajectory of every run.
#
# 🔴 CPU PARTITION ON PURPOSE. checkpoint_trajectory_stats.py is CPU-only (map_location="cpu", no
# cuda anywhere), and the project has **1000 core-hours allocated and 0.0% used** while GPU-hours are
# the scarce resource (2037 left, 4 days). Running this on standard-g would bill the scarce budget
# to do arithmetic a CPU node does for free.
#
# 🔴 RAM IS THE LIMIT, NOT CORES. flat() concatenates every parameter into a float64 vector: ~11 GB
# for a 1.4B full-FT, and the tool holds W0 + previous + current at once, so peak is ~34 GB PER RUN
# being processed. 56 cores would happily start 56 of those and OOM the node. Concurrency below is
# set from memory, and deliberately looks low.
#
# 🔴 PREFERS SLIM CHECKPOINTS. The tool reads state_dict, which the slim .weights.ckpt carries in
# full — 4.3 GB vs a 31 GB fat, a ~7x reduction in Lustre reads for identical output. Optimizer
# state is irrelevant to a weight trajectory. Falls back to fats where no slims were kept.
#
# RUN:
#   sbatch lumi/sbatch/traj_stats_cpu.sbatch                    # every run dir under runs/
#   RUNS="/scratch/.../runs/fullft/fullft_avp_t256" sbatch ...  # or an explicit list
#
#SBATCH --account=project_465003186
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=224G
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_traj_stats
#SBATCH --output=%x-%j.out

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
OUTDIR=${OUTDIR:-${SCRATCH}/checkpoint-stats}
# ~34 GB peak per concurrent run against 224 GB -> 6, with headroom for page cache on a Lustre read
# path this heavy. Raise only if you have measured the actual peak for the runs you are feeding it.
PAR=${PAR:-6}

mkdir -p "${OUTDIR}"
[ -n "${SIF}" ] || { echo "[traj] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[traj] FATAL: ${VENV} missing"; exit 1; }

# every dir holding >=3 checkpoints — fewer than that is not a trajectory, it is two points
if [ -n "${RUNS:-}" ]; then
  read -ra DIRS <<< "${RUNS}"
else
  mapfile -t DIRS < <(find "${SCRATCH}/runs" -name 'epoch=*.ckpt' -printf '%h\n' | sort -u)
fi
echo "[traj] candidate run dirs: ${#DIRS[@]}"
echo "[traj] out=${OUTDIR}  parallel=${PAR} (RAM-bound, not core-bound)  cores=${SLURM_CPUS_PER_TASK:-?}"

WORK=()
for d in "${DIRS[@]}"; do
  NS=$(ls "${d}"/epoch=*.weights.ckpt 2>/dev/null | wc -l)
  NF=$(ls "${d}"/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' | grep -v -- '-v[0-9]*\.ckpt$' | wc -l)
  # DERIVE steps-per-epoch PER RUN. --epoch-steps defaults to 5400 and is what converts step ->
  # epoch in the output; every run here has a different value, so the default would label every
  # point with a wrong epoch. From the last checkpoint: epoch=E-step=S => S/(E+1). Checked against
  # a run whose value we know independently: the wd03 full-FT is epoch=7-step=1952 -> 244, and 244
  # steps/epoch is exactly what its DDP verification measured.
  LASTCK=$(ls "${d}"/epoch=*.ckpt 2>/dev/null | grep -v -- '-v[0-9]*\.ckpt$' | sort -V | tail -1)
  ES=5400
  if [ -n "${LASTCK}" ]; then
    E=$(basename "${LASTCK}" | sed 's/.*epoch=//; s/-step=.*//')
    S=$(basename "${LASTCK}" | sed 's/.*step=//; s/[^0-9].*//')
    if [ -n "${E}" ] && [ -n "${S}" ] && [ "${E}" -ge 0 ] 2>/dev/null; then ES=$(( S / (E + 1) )); fi
    [ "${ES}" -lt 1 ] 2>/dev/null && ES=1
  fi
  if [ "${NS}" -ge 3 ]; then WORK+=("${d}|epoch=*.weights.ckpt|${NS}|slim|${ES}")
  elif [ "${NF}" -ge 3 ]; then WORK+=("${d}|epoch=*.ckpt|${NF}|fat|${ES}")
  fi
done
echo "[traj] runs with >=3 checkpoints: ${#WORK[@]}"
for w in "${WORK[@]}"; do IFS='|' read -r d g n k es <<< "$w"; printf "[traj]   %-4s %3d ckpt  %6s steps/ep  %s\n" "$k" "$n" "$es" "$d"; done
[ "${#WORK[@]}" -gt 0 ] || { echo "[traj] nothing to do"; exit 0; }

printf '%s\n' "${WORK[@]}" > /tmp/traj_work.txt

srun --ntasks=1 --cpus-per-task=${SLURM_CPUS_PER_TASK:-32} \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control${PYTHONPATH:+:${PYTHONPATH}}
# no GPU in this job at all; keep torch from probing one
export ROCR_VISIBLE_DEVICES="" HIP_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4     # per worker, not per node — PAR workers x 4 threads
# NO xargs -I{} HERE, and no exported function. The first version passed a "|"-delimited record
# through `xargs -I{} bash -c "run_one {}"` -- and bash parses the un-quoted "|" as a PIPELINE, so
# `run_one /path | epoch=*.weights.ckpt | 8 | slim | 299` ran nothing at all: 91 runs listed, zero
# outputs, zero OK/FAILED lines, and no error either. Positional args + a plain batching loop have
# no quoting surface to get wrong.
run_one() {
  local d="$1" g="$2" n="$3" k="$4" es="$5"
  local L; L=$(echo "${d}" | sed "s|.*/runs/||; s|/|__|g")
  echo "[traj] START ${L} (${n} ${k} ckpts, ${es} steps/ep)"
  if python ${CODE}/control/sa3_control/checkpoint_trajectory_stats.py \
       --ckpt-dir "${d}" --glob "${g}" --label "${L}" --out-dir "${OUTDIR}" \
       --epoch-steps "${es}"; then
    echo "[traj] OK ${L}"
  else
    echo "[traj] FAILED ${L} (continuing)"
  fi
}
export OUTDIR='"${OUTDIR}"'
PAR='"${PAR}"'
i=0
while IFS="|" read -r d g n k es; do
  [ -n "${d}" ] || continue
  run_one "${d}" "${g}" "${n}" "${k}" "${es}" &
  i=$((i+1))
  if [ $((i % PAR)) -eq 0 ]; then wait; fi
done < /tmp/traj_work.txt
wait
echo "[traj] all ${i} run(s) dispatched"

'
echo "[traj] done. outputs:"; ls -la "${OUTDIR}" 2>/dev/null | tail -20
echo "[traj] VERIFY by artifact count, not rc — per-run failures are caught and logged, not fatal."
echo "[traj] Pull these home before pruning: they are small (json/csv), and the CHECKPOINTS they"
echo "[traj]   describe are what gets deleted."
