#!/bin/bash
# aug8_encode.sbatch — DRAFT (2026-07-23, unsubmitted, for Kim's review): stage 1 of
# the aug8 campaign (docs/superpowers/specs/2026-07-23-aug8-15ep-campaign.md; renamed
# from aug10 -> aug8 per Kim's ruling: the variant set now matches
# mir/src/tools/augment_tracks.py exactly, 8 not 10 variants/crop).
# Two-phase, one standard-g node: (A) CPU-only Bungee augmentation of the GOA crop
# corpus via HyperQueue, (B) GPU SAME-L encode of the augmented FLACs to latents,
# on the SAME node/allocation (phase A needs no GPU but the node is already booked
# for phase B, so it doubles as free CPU capacity rather than a separate job).
#
# LOGISTICS — READ BEFORE SUBMITTING (Kim action items):
#   1. bungee_python must be importable inside the container/venv this job uses — the
#      #1 named port risk (see lumi/augment_goa_bungee.py's docstring), STILL OPEN as
#      of this draft (Kim's open-question ruling: this is the one still-open item, and
#      it now also gates the DDP training lane — aug8_train_ddp.sbatch needs real aug8
#      latents to smoke-test against). The prolog below FAILS LOUD on this — it does
#      not silently skip augmentation.
#   2. SOURCE AUDIO — APPROVED, upload list exists: `eval/musicology/goa_src_list.txt`
#      (2676 files, all under /run/media/kim/Mantu; scanned 2026-07-23 against all 5400
#      /home/kim/Projects/latents_sa3/*.json crop records, 153.57 GB total, already
#      deduped — 5400 crops average ~2.0 crops/track). AGREED TRANSFER CONVENTION
#      (Kim): rsync with `--files-from` PRESERVES THE ABSOLUTE PATH STRUCTURE under
#      `$SCRATCH/goa_src/` — i.e. `/run/media/kim/Mantu/ai-music/Goa_Separated/.../
#      full_mix.flac` lands at `$SCRATCH/goa_src/run/media/kim/Mantu/ai-music/
#      Goa_Separated/.../full_mix.flac` (NOT re-rooted/flattened). Exact command:
#        rsync -avzR -e "ssh -i ~/.ssh/id_EFP" \
#          --files-from=eval/musicology/goa_src_list.txt / \
#          akekim@efp.lumi.csc.fi:/scratch/project_465003186/goa_src/
#      (the `-R` / relative flag is what makes `--files-from`'s absolute entries land
#      under goa_src/ preserving their full path; dry-run first, per lumi-ops
#      convention). This is WHY augment_goa_bungee.py's `--source-prefix-map` takes
#      `/=/scratch/project_465003186/goa_src/` below — it just re-roots the leading
#      `/` rather than trying to reconstruct a relative path.
#   3. Crop metadata JSONs: this draft assumes `${CODE}/lumi/goa_crop_meta/` on LUMI
#      mirrors the local `/home/kim/Projects/latents_sa3/*.json` (5400 crop jsons,
#      excluding `*.TIMBRAL.json`) — also Kim's transfer (small, <1 GB of json/npz,
#      unlike the audio). Adjust CROPMETA below if staged elsewhere.
#   4. CODE REFRESH — working tree, never `git archive` (lumi-ops rule): before
#      submitting, verify `${CODE}/lumi/augment_goa_bungee.py` and
#      `${CODE}/lumi/encode_aug_task.py` are the versions on THIS branch (they are new
#      files, uncommitted as of this draft) — a stale/missing copy fails instantly.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_aug8_encode
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
CROPMETA=${CODE}/lumi/goa_crop_meta          # 5400 crop jsons (Kim-staged, see LOGISTICS #3)
SRCROOT=${SCRATCH}/goa_src                   # 2676 full_mix.flac, absolute-path-preserved (LOGISTICS #2)
SRCPREFIXMAP="/=${SRCROOT}/"
AUGROOT=${SCRATCH}/latents_goa_aug8
FLACROOT=${AUGROOT}/aug_flac_all
RUNROOT=${SCRATCH}/runs/aug8_encode
LOGDIR=${RUNROOT}/hq_logs
mkdir -p "${AUGROOT}" "${FLACROOT}" "${RUNROOT}" "${LOGDIR}"

[ -d "${CROPMETA}" ] || { echo "[aug8-encode] FATAL: ${CROPMETA} missing — stage the crop jsons first"; exit 1; }
[ -d "${SRCROOT}" ] || { echo "[aug8-encode] FATAL: ${SRCROOT} missing — stage source audio first (LOGISTICS #2, eval/musicology/goa_src_list.txt)"; exit 1; }

if [ -z "${HQ_BIN:-}" ]; then
  module use /appl/local/csc/modulefiles || true
  module load hyperqueue || true
  HQ_BIN=$(command -v hq || true)
fi
[ -n "${HQ_BIN:-}" ] || { echo "[aug8-encode] FATAL: no hq binary"; exit 1; }

# bungee lives in the scratch venv overlay (pip bungee-python 0.2.1, installed 2026-07-23
# — resolves the campaign spec's open question 2); venv python runs ONLY the augmenter,
# the encode task keeps the container python3 (torch is in the SIF, not the venv).
# ── bungee import check, up front, fails loud (mirrors augment_goa_bungee.py's own
# check — catching it here too means a broken container fails in seconds, not after
# the whole node spins up) ──────────────────────────────────────────────────────────
singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" \
  /scratch/project_465003186/bungee_venv/bin/python -c "import bungee_python" \
  || { echo "[aug8-encode] FATAL: bungee_python not importable in ${SIF} — see augment_goa_bungee.py LUMI PORT RISK note (venv overlay needed) — STILL OPEN per the campaign spec"; exit 1; }

export HQ_SERVER_DIR="${RUNROOT}/hq-server/${SLURM_JOB_ID}"
mkdir -p "${HQ_SERVER_DIR}"
"${HQ_BIN}" server start &
until "${HQ_BIN}" job list &> /dev/null; do sleep 1; done

# =====================================================================================
# PHASE A — CPU-only Bungee augmentation, sharded via HyperQueue (no GPU needed; runs
# on the same node's CPU cores while phase B's GPU work hasn't started yet).
# =====================================================================================
AUG_SHARDS=${AUG_SHARDS:-32}
SHARDDIR=${RUNROOT}/crop_shards
rm -rf "${SHARDDIR}"; mkdir -p "${SHARDDIR}"
python3 - "$CROPMETA" "$SHARDDIR" "$AUG_SHARDS" <<'PYEOF'
import sys, pathlib
crop_dir, shard_dir, nshard = sys.argv[1], pathlib.Path(sys.argv[2]), int(sys.argv[3])
jsons = sorted(p for p in pathlib.Path(crop_dir).glob("*.json") if not p.name.endswith(".TIMBRAL.json"))
for i, jp in enumerate(jsons):
    d = shard_dir / f"shard{i % nshard:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / jp.name).symlink_to(jp)
print(f"[aug8-encode] {len(jsons)} crops -> {nshard} shards under {shard_dir}")
PYEOF

# CPU-only HQ workers (no ROCR pinning — this phase touches no GPU). Reuse the
# already-allocated 8 ranks x 7 cpus as plain CPU workers.
srun --overlap --cpu-bind=none --mpi=none bash -c '
  '"${HQ_BIN}"' worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
"${HQ_BIN}" worker wait "${SLURM_NTASKS}"
echo "[aug8-encode] phase A: ${SLURM_NTASKS} CPU workers up"

i=0
for SD in "${SHARDDIR}"/shard*/; do
  [ -d "${SD}" ] || continue
  i=$((i+1))
  OUT="${AUGROOT}/aug_flac_shard$(basename "${SD}")"
  "${HQ_BIN}" submit \
    --name="aug8_a${i}" \
    --cpus=7 \
    --stdout="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.out" \
    --stderr="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.err" \
    -- singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "
      set -euo pipefail
      export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
      /scratch/project_465003186/bungee_venv/bin/python ${CODE}/lumi/augment_goa_bungee.py '${SD}' --out '${OUT}' \
        --source-prefix-map '${SRCPREFIXMAP}' --jobs 7
    "
done
echo "[aug8-encode] phase A: submitted ${i} augmentation shard tasks; draining"
"${HQ_BIN}" job wait all || true   # task failures must NOT skip the merge/success-check tail (set -e)
"${HQ_BIN}" job list --all || true

# merge shard outputs: symlink all flacs into one flat dir, concat manifests (ids are
# crop_id__variant — unique across shards since sharding split by CROP, not variant).
for D in "${AUGROOT}"/aug_flac_shard*/; do
  [ -d "${D}" ] || continue
  find "${D}" -maxdepth 1 -name '*.flac' -exec ln -sf {} "${FLACROOT}/" \;
done
cat "${AUGROOT}"/aug_flac_shard*/manifest.jsonl > "${AUGROOT}/aug_manifest.jsonl" 2>/dev/null || true
NFLAC=$(ls "${FLACROOT}"/*.flac 2>/dev/null | wc -l)
echo "[aug8-encode] phase A SUCCESS CHECK: ${NFLAC} augmented flacs merged into ${FLACROOT} (expect up to $((5400*8)))"

# =====================================================================================
# PHASE B — GPU SAME-L encode, one HQ task per GCD-pinned shard (ROCR-only pinning —
# HIP_VISIBLE_DEVICES additionally would STACK, see lumi-ops SKILL.md non-negotiables).
# =====================================================================================
python3 - "$AUGROOT/aug_manifest.jsonl" "$RUNROOT" <<'PYEOF'
import sys, json, pathlib
manifest_path, runroot = sys.argv[1], pathlib.Path(sys.argv[2])
ids = []
with open(manifest_path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("status") in ("ok", "skipped-exists"):
            ids.append(f"{row['crop_id']}__{row['variant']}")
n = 8
shards = [[] for _ in range(n)]
for i, cid in enumerate(ids):
    shards[i % n].append(cid)
sdir = runroot / "encode_shards"
sdir.mkdir(parents=True, exist_ok=True)
for i, s in enumerate(shards):
    (sdir / f"shard{i}.txt").write_text("\n".join(s) + "\n")
print(f"[aug8-encode] {len(ids)} ids -> 8 encode shards under {sdir}")
PYEOF

srun --overlap --cpu-bind=none --mpi=none bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  '"${HQ_BIN}"' worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
"${HQ_BIN}" worker wait "${SLURM_NTASKS}"
echo "[aug8-encode] phase B: ${SLURM_NTASKS} GCD-pinned workers up"

for i in 0 1 2 3 4 5 6 7; do
  "${HQ_BIN}" submit \
    --name="aug8_b${i}" \
    --cpus=7 \
    --stdout="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.out" \
    --stderr="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.err" \
    -- singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "
      set -euo pipefail
      export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
      export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
      export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
      export MIOPEN_USER_DB_PATH=/tmp/miopen-\$HQ_TASK_ID MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-\$HQ_TASK_ID
      export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
      rm -rf \$MIOPEN_USER_DB_PATH; mkdir -p \$MIOPEN_USER_DB_PATH
      echo [aug8-encode-b task \$HQ_TASK_ID] GCD ROCR=\$ROCR_VISIBLE_DEVICES
      python3 ${CODE}/lumi/encode_aug_task.py \
        --shard ${RUNROOT}/encode_shards/shard${i}.txt \
        --flac-dir ${FLACROOT} \
        --manifest ${AUGROOT}/aug_manifest.jsonl \
        --out ${AUGROOT}
    "
done
echo "[aug8-encode] phase B: submitted 8 encode tasks; draining"
"${HQ_BIN}" job wait all || true
"${HQ_BIN}" job list --all || true
"${HQ_BIN}" worker stop all || true
"${HQ_BIN}" server stop || true

NLAT=$(ls "${AUGROOT}"/*.npy 2>/dev/null | wc -l)
echo "[aug8-encode] phase B SUCCESS CHECK: ${NLAT} latents in ${AUGROOT} (expect == ${NFLAC})"
echo "[aug8-encode] per-task errors (if any): ${LOGDIR}/j*-t*.err — sbatch rc 0 is NOT task success"

# stage for training: tar so aug8_train.sbatch / aug8_train_ddp.sbatch can extract it
# the same way as the existing latents_avp.tar.gz / latents_sa3.tar.gz
# (efp_fp32_compare.sbatch convention).
tar -czf "${SCRATCH}/latents_goa_aug8.tar.gz" -C "${AUGROOT}" $(ls "${AUGROOT}" | grep -E '\.(npy|json)$')
echo "[aug8-encode] DONE -> ${SCRATCH}/latents_goa_aug8.tar.gz"
