#!/bin/bash
# fullft_3src_t512_fp32_bounded.sbatch — CONTINUITY 2026-08-17, Kim direct:
#   "stage yet one more fp32 full-ft comparison at t512: lr 3e-5 and 1e-4 (I have a feeling Fusion
#    goes fast, I want to see about a bit slower rates if it finds some smaller paths to new
#    places) EMA, batch of 2, gradient accumulation steps 2. If that OOMs, batch 1, GAS 4.
#    Datasets: suomisoundi, goa large, avp aug x8. AVP prompts need to be granite ones. We have the
#    full music flamingo prompts, we could use them too 10% of the time (taken away from the granite
#    prompts, leave unconditional as it is). And, each runs on 8x GPUs. #1 hyperball, #2 EDM2, #3 both."
#
# ONE ARM PER SUBMIT — MODE x LR. Six arms total:
#   MODE=hyperball LR=3e-5 | MODE=hyperball LR=1e-4     <- #1
#   MODE=edm2      LR=3e-5 | MODE=edm2      LR=1e-4     <- #2
#   MODE=both      LR=3e-5 | MODE=both      LR=1e-4     <- #3
# ALL SIX ARE READY (2026-08-17): --forced-weight-norm landed in stable-audio-3 1d6474c with 12
# tests. What the two bounds actually differ in, since the arms are only worth running if they are
# not the same experiment:
#   hyperball -> whole-tensor ‖W‖_F FROZEN at ‖W0‖_F, optimizer-side, on EVERY spectral matrix.
#                Output magnitude cannot change at all.
#   edm2      -> per-output-channel DIRECTION normalised with a LEARNABLE per-channel gain, on the
#                output projection only (transformer.py:1171). Magnitude can still adapt, but
#                through one well-conditioned parameter per channel instead of drifting across the
#                whole matrix. Strictly the weaker, more expressive constraint.
#   both      -> hyperball on the bulk + per-channel gain control at the output.
# Both are retrofit-safe (each reproduces the pretrained function at step 0, so no fine-tune spike).
#
# WHY THESE TWO BOUNDS AND NOT MORE WARMUP/EMA/AdaGC: warmup, EMA and AdaGC all shape the PATH,
# none bounds the DESTINATION. Warmup only delays onset (equilibrium norm unchanged); EMA averages a
# drifting trajectory so the average drifts too; AdaGC clips against an EMA of recent clipped norms,
# so it catches SPIKES while sustained drift passes every test unremarked. Hyperball and EDM2-style
# forced weight norm are the two retrofit-safe options that put a HARD bound on ‖W‖. Full reasoning +
# the 12-paper read: papers/CONTINUITY-drone-optimizer-synthesis-2026-08-11.md.
#
# CONTEXT WORTH KNOWING BEFORE READING THE RESULTS (2026-08-17): the latent-scale runaway that
# motivated all of this is ALREADY BOUNDED by `--weight_decay` — the wd-fixed full-FT measures ep7
# global z0 std 1.134 with 0/256 channels over 2.0, vs the runaway's 5.6 and 166/256. So these arms
# are asking the FINER question Kim posed: at a bounded norm, does a slower LR find different
# (better) minima? They are NOT rescuing a diverging run. Judge them on Kim's ears + the
# disintegration DSP, not on the z0 number, which all arms should pass.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_fullft_3src_t512
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

MODE=${MODE:-hyperball}          # hyperball | edm2 | both
LR=${LR:-1e-4}                   # Kim's pair: 1e-4 and 3e-5
BS=${BS:-2}; GA=${GA:-2}         # EMA+full-FT: the ONLY proven-safe shape. On OOM: BS=1 GA=4.
FRAMES=${FRAMES:-512}
PREC=${PREC:-fp32}
EPOCHS=${EPOCHS:-8}; CKEVERY=${CKEVERY:-1}
WARMUP_EPOCHS=${WARMUP_EPOCHS:-0.5}
WARMUP_FRAC=$(awk -v w="${WARMUP_EPOCHS}" -v e="${EPOCHS}" 'BEGIN{printf "%.6f", w/e}')
GRAD_CLIP_MODE=${GRAD_CLIP_MODE:-agc}
WEIGHT_DECAY=${WEIGHT_DECAY:-0.03}
SMOKE=${SMOKE:-0}

# ── datasets: avp aug×8 + suomisoundi + goa ─────────────────────────────────────────────────────
AVP_DIR=${AVP_DIR:-latents_avp}                 # ALREADY the ×8 bungee-aug set (289 base + 2105 aug)
SUOMI_DIR=${SUOMI_DIR:-suomisoundi_latents}
GOA_DIR=${GOA_DIR:-latents_sa3}                 # see the CAPTION AUDIT note below re: latents_goa_bigset
SIDECAR_AVP=${SIDECAR_AVP:-${CODE}/lumi/avp_captions_tiered.json}
SIDECAR_SUOMI=${SIDECAR_SUOMI:-${CODE}/lumi/suomisoundi_caption_sidecar.json}
SIDECAR_GOA=${SIDECAR_GOA:-${CODE}/lumi/goa_longform_sidecar.json}

# ── caption tiers, PER SOURCE (t1,t2,t3 = style / granite / full Music Flamingo) ────────────────
# Kim: granite prompts, MF 10% taken out of the granite share, unconditional untouched (conditioning
# dropout stays with the training wrapper — we do NOT set caption_dropout here, which would
# double-drop).
# ⚠️ THE GOA SOURCE IS DELIBERATELY DIFFERENT, and this is the reason per-source probs exist.
# eval/audit_caption_sidecar.py measured each granite tier's rare-term recall against its OWN
# track's MF prose, paired vs shuffled (ratio >>1 = grounded, ~1 = the tag ignored its input):
#     suomisoundi  16.17x  GROUNDED (99.8% genre agreement)   -> safe at t2=0.9
#     avp           3.84x  grounded, anchor-dominated          -> safe at t2=0.9
#     goa bigset    1.24x  NOT GROUNDED — chance               -> MUST ride t3 (MF) only
# The goa bigset's granite tier was generated from FOLDER NAMES (G's find): 28.8% of its 23231
# captions open with the identical "mid 90s goa trance" and 17.4% with "mid 90s psytrance full" —
# year+genre, i.e. what `Goa.PsyTrance.Collection.1997` carries. Its 99.8% distinct-string rate does
# NOT clear it; the template just gets slot-filled with word swaps and a BPM.
# ⇒ goa stays 0,0,1 until G's granite revision (job 21255037) lands AND re-audits >= ~8x. Then flip
#   CAPTION_PROBS to "0,0.9,0.1;0,0.9,0.1;0,0.9,0.1". A missing tier falls back to t1 SILENTLY, so a
#   wrong mix trains on boilerplate without erroring — re-audit, don't assume.
CAPTION_PROBS=${CAPTION_PROBS:-0,0.9,0.1;0,0.9,0.1;0,0,1}
# ✅ THE GRANITE-EVERYWHERE PATH IS NOW VERIFIED (2026-08-18) — use it in preference to the
# conservative default above. G's granite v5 (job 21255037, read_mf() fix 63546e6) re-audits at
# rare-term ratio 19.24x vs the pre-fix 1.24x=chance, BEATING suomisoundi's 16.17x; templating
# collapsed from 28.8% of the corpus sharing one 4-word opening to 3.9%, and all 23231 captions are
# distinct. Re-keying onto the bigset's synthetic latent ids matched 12523/12523 (100%), ALL via
# exact relpath with zero fallbacks. So:
#   GOA_DIR=latents_goa_bigset \
#   SIDECAR_GOA=/project/project_465003186/code/lumi/goa_bigset_v5_relkeyed_sidecar.json \
#   CAPTION_PROBS="0,0.9,0.1;0,0.9,0.1;0,0.9,0.1"
# ⚠️ The DEFAULTS below stay conservative on purpose: they point at GOA_DIR=latents_sa3 with
# goa_longform_sidecar.json, which has NO entries carrying both t2 AND t3 — it cannot even be
# audited for grounding, and a missing tier falls back to t1 SILENTLY. So a granite-led tier mix is
# valid ONLY on the bigset+v5 pairing above, NOT on the default pairing. Audit before flipping any
# other corpus: python3 eval/audit_caption_sidecar.py <sidecar>
SOURCE_WEIGHTS=${SOURCE_WEIGHTS:-}   # empty => natural per-crop proportions

case "${MODE}" in
  hyperball) BOUND_ARGS=(--hyperball) ;;
  edm2)      BOUND_ARGS=(--forced-weight-norm) ;;
  both)      BOUND_ARGS=(--hyperball --forced-weight-norm) ;;
  *) echo "[3src] FATAL: MODE must be hyperball|edm2|both (got '${MODE}')"; exit 1 ;;
esac
NAME=fullft_3src_t512_fp32_${MODE}_lr${LR}
RUN=${SCRATCH}/runs/fullft_3src_t512/${NAME}
mkdir -p "${RUN}" "${FLASH}"

# ── preflight ───────────────────────────────────────────────────────────────────────────────────
[ -n "${SIF}" ] || { echo "[3src] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[3src] FATAL: ${VENV} missing"; exit 1; }
TL=${CODE}/stable-audio-3/scripts/train_lora.py
grep -q -- 'LOCAL_RANK.*set_device\|set_device.*LOCAL_RANK' "${TL}" \
  || { echo "[3src] FATAL: train_lora.py missing the LOCAL_RANK set_device fix — REQUIRED for torchrun (else every rank loads onto GPU 0 and OOMs). Code refresh needed."; exit 1; }
grep -q "_parse_caption_probs" "${TL}" \
  || { echo "[3src] FATAL: train_lora.py missing per-source --caption_probs (semicolon syntax). Without it ALL sources would take one tuple and the goa source's NOT-GROUNDED granite tier would poison the mix. Code refresh needed."; exit 1; }
grep -q -- '"--hyperball"' "${TL}" \
  || { echo "[3src] FATAL: train_lora.py missing --hyperball"; exit 1; }
if [ "${MODE}" = "edm2" ] || [ "${MODE}" = "both" ]; then
  grep -q -- '"--forced-weight-norm"' "${TL}" \
    || { echo "[3src] FATAL: MODE=${MODE} needs --forced-weight-norm, which is NOT IMPLEMENTED yet (EDM2-style forced weight norm on the output projection). Arm #1 (MODE=hyperball) runs today; #2/#3 unblock when that lands."; exit 1; }
fi
for S in "${SIDECAR_AVP}" "${SIDECAR_SUOMI}" "${SIDECAR_GOA}"; do
  [ -f "${S}" ] || { echo "[3src] FATAL: sidecar ${S} not shipped"; exit 1; }
done

# ── ECHO THE CONFIG *BEFORE* THE EXPENSIVE STEP ─────────────────────────────────────────────────
# Learned the hard way on the first smoke (job 21334767): staging came first, so the .out sat at
# ZERO BYTES for 10+ minutes while the job was perfectly healthy — and a healthy staging job is then
# indistinguishable from one that died before its first echo, exactly when you most want to check.
# Anything cheap and diagnostic goes before anything slow.
echo "[3src] node=$(hostname) MODE=${MODE} LR=${LR} PREC=${PREC} FRAMES=${FRAMES} BS=${BS} GA=${GA} (per-GPU $((BS*GA)), GLOBAL eff batch $((BS*GA*8)) over 8 torchrun ranks) EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_EPOCHS=${WARMUP_EPOCHS} (frac=${WARMUP_FRAC}) GRAD_CLIP_MODE=${GRAD_CLIP_MODE} WEIGHT_DECAY=${WEIGHT_DECAY} SMOKE=${SMOKE} NAME=${NAME}"
echo "[3src] caption_probs (per source, t1,t2,t3) = ${CAPTION_PROBS}"
echo "[3src] sidecars: avp=$(basename ${SIDECAR_AVP}) suomi=$(basename ${SIDECAR_SUOMI}) goa=$(basename ${SIDECAR_GOA})"
echo "[3src] image=${SIF}"

# ── stage latents to node-local /flash ──────────────────────────────────────────────────────────
for DS in "${AVP_DIR}" "${SUOMI_DIR}" "${GOA_DIR}"; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    if [ -d "${SCRATCH}/${DS}" ]; then
      # NB the bigset is ~25k files / ~25 GB off Lustre — minutes, not seconds. Announce start AND
      # finish with a count, so a slow copy reads as progress rather than as a hang.
      echo "[3src] staging ${DS} from ${SCRATCH} -> ${FLASH} ($(ls -1 ${SCRATCH}/${DS} 2>/dev/null | wc -l) entries to copy) ..."
      mkdir -p "${FLASH}/${DS}"
      cp "${SCRATCH}/${DS}"/*.npy "${SCRATCH}/${DS}"/*.json "${FLASH}/${DS}/" 2>/dev/null || true
      echo "[3src] staged ${DS}: $(ls -1 ${FLASH}/${DS} 2>/dev/null | wc -l) entries"
    elif [ -f "${SCRATCH}/${DS}.tar.gz" ]; then
      echo "[3src] extracting ${DS}.tar.gz -> ${FLASH} ..."
      mkdir -p "${FLASH}/${DS}"
      tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
      echo "[3src] staged ${DS}: $(ls -1 ${FLASH}/${DS} 2>/dev/null | wc -l) entries"
    else
      echo "[3src] FATAL: neither ${SCRATCH}/${DS}/ nor ${SCRATCH}/${DS}.tar.gz exists"; exit 1
    fi
  else
    echo "[3src] ${DS} already staged at ${FLASH} ($(ls -1 ${FLASH}/${DS} 2>/dev/null | wc -l) entries)"
  fi
done
NAVP=$(ls ${FLASH}/${AVP_DIR}/*.npy 2>/dev/null | wc -l)
NSUO=$(ls ${FLASH}/${SUOMI_DIR}/*.npy 2>/dev/null | wc -l)
NGOA=$(ls ${FLASH}/${GOA_DIR}/*.npy 2>/dev/null | wc -l)
for N in "${NAVP}:${AVP_DIR}" "${NSUO}:${SUOMI_DIR}" "${NGOA}:${GOA_DIR}"; do
  [ "${N%%:*}" -gt 0 ] || { echo "[3src] FATAL: 0 crops staged for ${N#*:}"; exit 1; }
done

echo "[3src] sources: ${AVP_DIR}=${NAVP} ${SUOMI_DIR}=${NSUO} ${GOA_DIR}=${NGOA} crops (total ~$((NAVP+NSUO+NGOA)))"
echo "[3src] steps/epoch ≈ $(( (NAVP+NSUO+NGOA) / (BS*8) )) batches per rank; optimizer steps ≈ $(( (NAVP+NSUO+NGOA) / (BS*8*GA) )) — multiply by the log's it/s for the real per-epoch wall time before committing to EPOCHS=${EPOCHS}"
if [ "${MODE}" = "hyperball" ] || [ "${MODE}" = "both" ]; then
  echo "[3src] NOTE --hyperball DROPS Schedule-Free from FusionOpt components and IGNORES weight decay (the ‖W‖=‖W0‖ constraint replaces it) — so WEIGHT_DECAY=${WEIGHT_DECAY} is inert on this arm, and the LR is constant apart from warmup. Expected, not a misconfiguration."
fi
echo "[3src] DISK: fat ckpt ≈31.4 GB; at CKEVERY=${CKEVERY} over ${EPOCHS} epochs ≈ $(( EPOCHS / CKEVERY )) fats ≈ $(( (EPOCHS / CKEVERY) * 31 )) GB for THIS arm on /scratch (50 TB quota — fine there)."
echo "[3src] DISK: but do NOT pull them all — the pull target had 481 GB free (2026-08-18) and 3 arms of fats is ~$(( 3 * (EPOCHS / CKEVERY) * 31 )) GB. Standing rule: run lumi/prune_optimizer_states.py, then pull the TERMINAL fat only (~31 GB/arm) + slims (~4.3 GB each) — that lands ~223 GB for 3 arms, which fits."

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_ARGS=()
[ -n "${FATCKPT}" ] && { RESUME_ARGS=(--resume_ckpt "${FATCKPT}"); echo "[3src] resuming from ${FATCKPT}"; }

STEP_ARGS=(--epochs "${EPOCHS}")
[ "${SMOKE}" = "1" ] && STEP_ARGS=(--steps 20)   # omitting --epochs silently caps max_steps=--steps
SW_ARGS=()
[ -n "${SOURCE_WEIGHTS}" ] && SW_ARGS=(--source_weights "${SOURCE_WEIGHTS}")

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
# overlay site-packages FIRST, but APPEND the inherited path -- a bare assignment drops the
# container /opt/venv where torch itself lives (ModuleNotFoundError: No module named torch).
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-3src MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-3src
export TRITON_CACHE_DIR=/tmp/triton-3src PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-3src /tmp/triton-3src; mkdir -p /tmp/miopen-3src /tmp/triton-3src
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

echo "[3src] node=$(hostname) launching torchrun --nproc-per-node=8"
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune \
  --encoded_dir ${FLASH}/'"${AVP_DIR}"',${FLASH}/'"${SUOMI_DIR}"',${FLASH}/'"${GOA_DIR}"' \
  --caption_sidecar '"${SIDECAR_AVP}"','"${SIDECAR_SUOMI}"','"${SIDECAR_GOA}"' \
  --caption_probs "'"${CAPTION_PROBS}"'" \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion '"${BOUND_ARGS[*]}"' \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode '"${GRAD_CLIP_MODE}"' \
  --weight_decay '"${WEIGHT_DECAY}"' \
  --base_precision '"${PREC}"' \
  --lr '"${LR}"' --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --frames '"${FRAMES}"' \
  '"${STEP_ARGS[*]}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  '"${SW_ARGS[*]}"' '"${RESUME_ARGS[*]}"' \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train.log
'
echo "[3src] DONE — verify by READING THE LOG, never the exit code:"
echo "  DDP formed:  grep -h LOCAL_RANK ${RUN}/train.log | sort -u    (want LOCAL_RANK 0..7, NOT eight 0s)"
echo "  no dup writers: ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD || echo ok"
echo "  captions landed: grep '\[captions\] source' ${RUN}/train.log   (3 lines, goa must show 0,0,1)"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train.log" | head
