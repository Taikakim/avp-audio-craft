#!/bin/bash
# mirctrl_bracket.sbatch — B7 MIR-timeseries conditioner bracket (CONTINUITY 2026-08-21,
# Kim direct: "train some really traditional models, using our mir data as conditioners,
# probably rank 32 DoRAs ... target is every feature we have ... goa+avp aug mixed set").
#
# WHAT EACH ARM IS: medium-base + DoRA-rows rank 32 + a zero-init per-frame additive
# control projection (the DiT's native modular local-cond inlet, installed on blocks
# 12-23 = W's layer-map union) fed with REAL MIR curves from the target crop
# (teacher-forced; per-item control dropout 0.2 = the CFG null). The PACK knob picks the
# feature family; 'all' = every field we have (36 ch: band-RMS 4, stem RMS/onset 8,
# rhythm 3, HPCP 12, spectral 4, position 1, f0 4 [goa-only, zero-filled on avp]).
#
# SELF-REPORTING (train-now-evaluate-later, allocation ends imminently): every arm
# (a) measures the CONTROL-ABLATION meter in-training every 500 steps — RF loss on a
#     fixed batch under {true, shuffled, zero} control; control_gain > 0 <=> the model
#     exploits the time-ALIGNED control (B7 kill-criterion readable from the log alone);
# (b) writes report.md + report.json + control_ablation.jsonl into the run dir at fit
#     end, with an sbatch-epilogue fallback for walltime-truncated runs.
#
# DATASET (fixed): latents_sa3 (goa 5400) + latents_avp (avp aug 2393) with their
# PROVEN longform sidecars (the winning fp32 family pairing). NOT biggoa (Kim: issues).
# PREREQ on ${SCRATCH}: latents_sa3/, latents_avp/, latents_sa3_ctrl/, latents_avp_ctrl/
#   (the _ctrl dirs come from build_ctrl_packs.py locally + rsync; they are SIBLINGS on
#   purpose — a .ctrl.npy INSIDE a latent dir gets globbed as a latent by the dataset).
#
# BRACKET (one arm per job; priority order if budget is short):
#   PACK=all      sbatch lumi/sbatch/mirctrl_bracket.sbatch     # 1. the headline arm
#   PACK=melody   sbatch ...                                    # 2. the melody-wall arm
#   PACK=rhythm   sbatch ...                                    # 3. the channel SA3 keeps
#   PACK=dynamics sbatch ...                                    # 4.
#   PACK=stems    sbatch ...                                    # 5.
#   PACK=spectral sbatch ...                                    # 6.
#   PACK=all BLOCKS=all sbatch ...                              # 7. blocks ablation
#   PACK=all RANK=64    sbatch ...                              # 8. capacity ablation
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=14:00:00
#SBATCH --job-name=mirctrl
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

PACK=${PACK:?set PACK=all|melody|rhythm|dynamics|stems|spectral|f0|structure}
RANK=${RANK:-32}
BLOCKS=${BLOCKS:-12-23}
SEED=${SEED:-1}
LR=${LR:-1e-4}
BS=${BS:-1}
EPOCHS=${EPOCHS:-20}
CKEVERY=${CKEVERY:-2}
DROPOUT=${DROPOUT:-0.2}
NAME=mirctrl_${PACK}_r${RANK}_b$(echo ${BLOCKS} | tr - _)_t1024_s${SEED}
RUN=${SCRATCH}/runs/mirctrl_bracket/${NAME}

DIRS="latents_sa3,latents_avp"
SIDES="${CODE}/lumi/goa_longform_sidecar.json,${CODE}/lumi/avp_longform_sidecar.json"
PROBS="0.6,0.3,0.1"

[ -n "${SIF}" ] || { echo "[mirctrl] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mirctrl] FATAL: ${VENV} missing"; exit 1; }
grep -q 'set_device' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[mirctrl] FATAL: train_lora.py lacks the LOCAL_RANK set_device fix"; exit 1; }
[ -f "${CODE}/stable-audio-3/scripts/mir_control.py" ] \
  || { echo "[mirctrl] FATAL: mir_control.py not synced"; exit 1; }
IFS=',' read -ra SS <<< "${SIDES}"
for s in "${SS[@]}"; do [ -f "$s" ] || { echo "[mirctrl] FATAL: sidecar missing: $s"; exit 1; }; done

# stage latents AND their sibling _ctrl dirs to flash
FDIRS=""
IFS=',' read -ra DD <<< "${DIRS}"
for d in "${DD[@]}"; do
  for sub in "${d}" "${d}_ctrl"; do
    # stage if EMPTY, not just if absent — a failed earlier run leaves an empty flash dir
    # (mkdir succeeded, cp had nothing), and dir-existence checks then skip staging forever
    # (bit the first mirctrl batch twice, 2026-08-21)
    if [ "$(ls ${FLASH}/${sub}/*.npy 2>/dev/null | wc -l)" -eq 0 ]; then
      echo "[mirctrl] staging ${sub} -> flash"; mkdir -p "${FLASH}/${sub}"
      cp "${SCRATCH}/${sub}"/*.npy "${FLASH}/${sub}/" 2>/dev/null
      cp "${SCRATCH}/${sub}"/*.json "${FLASH}/${sub}/" 2>/dev/null || true
    fi
  done
  NL=$(ls "${FLASH}/${d}"/*.npy 2>/dev/null | wc -l)
  NC=$(ls "${FLASH}/${d}_ctrl"/*.ctrl.npy 2>/dev/null | wc -l)
  [ "${NL}" -gt 0 ] || { echo "[mirctrl] FATAL: no latents staged for ${d}"; exit 1; }
  [ "${NC}" -gt 0 ] || { echo "[mirctrl] FATAL: no ctrl arrays for ${d} — rsync ${d}_ctrl first"; exit 1; }
  # ONE-KEY RESOLUTION CHECK (skill rule): a latent's ctrl file must exist by stem
  K=$(ls "${FLASH}/${d}"/*.npy | head -1 | xargs -n1 basename | sed 's/\.npy$//')
  [ -f "${FLASH}/${d}_ctrl/${K}.ctrl.npy" ] \
    || { echo "[mirctrl] FATAL: ctrl key mismatch: ${K}.ctrl.npy missing in ${d}_ctrl"; exit 1; }
  echo "[mirctrl]   ${d}: ${NL} latents, ${NC} ctrl arrays (key check: ${K} OK)"
  FDIRS="${FDIRS:+${FDIRS},}${FLASH}/${d}"
done
SIDE_ARG=$(IFS=','; echo "${SS[*]}")

mkdir -p "${RUN}"
echo "[mirctrl] CONFIG NAME=${NAME} PACK=${PACK} RANK=${RANK} BLOCKS=${BLOCKS} SEED=${SEED} LR=${LR} BS=${BS}/rank EPOCHS=${EPOCHS} DROPOUT=${DROPOUT}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "B7 (Kim direct 2026-08-21): MIR-timeseries conditioning bracket — pack '${PACK}' curves into the DiT's native modular local-cond inlet (zero-init, blocks ${BLOCKS}) + DoRA-rows r${RANK}. Teacher-forced on goa+avp-aug mixed set. Executes the parked ATTRIBUTE_BRANCHES milestone (2026-06-19) via the fleet train_lora stack.",
 "recipe": {"adapter": "dora-rows", "rank": ${RANK}, "alpha": ${RANK}, "optimizer": "adamw",
            "lr": "${LR}", "lr_schedule": "NONE (constant) -- judge by soups/EMA-of-ladder",
            "precision": "fp32", "frames": 1024, "batch_per_rank": ${BS}, "gpus": 8,
            "effective_batch": $((8*BS)), "epochs": ${EPOCHS}, "seed": ${SEED},
            "mir_ctrl": {"pack": "${PACK}", "blocks": "${BLOCKS}", "dropout": ${DROPOUT},
                         "source": "prebuilt _ctrl sibling dirs (build_ctrl_packs.py)"}},
 "dataset": {"name": "goa5400+avpaug2393", "dirs": "${DIRS}", "caption_probs": "${PROBS}",
             "note": "NOT biggoa (Kim: issues). f0 fields zero-filled on avp."},
 "reports": "control_ablation.jsonl + report.md/json in this dir; control_gain>0 = inlet used",
 "script": "lumi/sbatch/mirctrl_bracket.sbatch", "result": null, "kim_feedback": null}
META

# TORCHRUN PATTERN (converted 2026-08-21 after the fleet-wide Pattern-2 failure was
# CONFIRMED live: eight 'LOCAL_RANK: 0' + colliding -vN ckpts + per-rank full-dataset
# step counts on fullft_fleet/winning_fleet — the exact 21161065 signature the skill
# warns about; the old srun --ntasks=8 --gpus-per-task=1 + Lightning SLURMEnvironment
# auto-detect NEVER formed a group). CSC reference: one task, all GPUs visible,
# torchrun coordinates ranks via RANK/LOCAL_RANK/WORLD_SIZE.
srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-mirctrl MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-mirctrl
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-mirctrl PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-mirctrl /tmp/triton-mirctrl; mkdir -p /tmp/miopen-mirctrl /tmp/triton-mirctrl
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision fp32 \
  --adapter_type dora-rows --rank '"${RANK}"' --lora_alpha '"${RANK}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${FDIRS}"' --caption_sidecar '"${SIDE_ARG}"' --caption_probs "'"${PROBS}"'" \
  --mir_ctrl_pack '"${PACK}"' --mir_ctrl_source ctrl --mir_ctrl_blocks '"${BLOCKS}"' \
  --mir_ctrl_dropout '"${DROPOUT}"' --mir_ctrl_ablation_every 500 \
  --frames 1024 --batch_size '"${BS}"' --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[mirctrl] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
# report fallback for walltime-truncated runs (fit-end writer never ran)
if [ ! -f "${RUN}/report.md" ]; then
  echo "[mirctrl] no report.md (truncated run?) — writing fallback report"
  singularity exec --bind ${PROJ},${SCRATCH} "${SIF}" bash -c '
    source '"${VENV}"'/bin/activate
    export PYTHONPATH='"${VENV}"'/lib/python3.12/site-packages:'"${CODE}"'/stable-audio-3/scripts${PYTHONPATH:+:${PYTHONPATH}}
    python -c "from mir_control import write_report; print(write_report(\"'"${RUN}"'\", arm_meta={\"pack\": \"'"${PACK}"'\", \"rank\": '"${RANK}"', \"blocks\": \"'"${BLOCKS}"'\", \"truncated\": True}))"'
fi
echo "[mirctrl] VERIFY DDP NOW (do not trust without it): grep -h \"LOCAL_RANK\" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out | sort | uniq -c  -- want LOCAL_RANK 0..7 ONCE each, ckpts UN-versioned"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
echo "[mirctrl] VERIFY INLET: grep control_gain ${RUN}/report.md  (>0 = control exploited)"
exit ${rc}
