#!/bin/bash
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=28
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=suomi_dora
#SBATCH --output=%x-%j.out
#SBATCH --open-mode=append
#
# suomisoundi_dora_2x4gpu.sbatch — WINTERMUTE 2026-08-17, Kim direct: "new dataset, let's train
# both a fp32 rank 32 and rank 256 adapter, at lr1e-4 and 3e-5, t256 for both, batch 16 for rank
# 32 and batch 8 for 256. EMA, warmup, Adagc. Spectral WD of 0.03 for each. Each of these gets
# their own 4x GPU setup."
#
# FOUR ARMS, TWO SUBMISSIONS, ONE SCRIPT. Each submission takes one 8-GPU node and runs two
# 4-GPU DDP arms side by side (the layout C proved in smoke 21330059). ARMSET picks which pair:
#
#   ARMSET=r32  sbatch …   → rank 32,  batch 16 : arm A lr 1e-4 | arm B lr 3e-5   (GPUs 0-3 / 4-7)
#   ARMSET=r256 sbatch …   → rank 256, batch 8  : arm A lr 1e-4 | arm B lr 3e-5   (GPUs 0-3 / 4-7)
#
# = 16 GCDs total across the two jobs. Deliberately TWO single-node jobs rather than one
# --nodes=2 job: multi-node DDP is UNSOLVED on this cluster (SKILL.md "Multi-GPU DDP" — adding
# --nodes=N to the working single-node launch silently forms N independent groups). Nothing here
# crosses a node boundary, so that whole failure class is out of scope by construction.
#
# ONE script, not two near-identical ones, on purpose: a second copy is a promise to keep two
# files in sync that nobody keeps (cost us a version-behind rating page this same week).
#
# ── WHAT KIM ASKED FOR vs WHAT THE TRAINER ACTUALLY DOES ──────────────────────────────────
# EMA: **--use-ema IS A NO-OP FOR DoRA/LoRA AND THIS RUN WILL NOT HAVE IT.** Verified in code,
#   not inferred: train_lora.py:487 passes `use_ema=(args.use_ema and args.full_finetune)`, and
#   diffusion.py:232 sets `use_ema = False` again whenever a lora_config is present ("Don't use
#   EMA with LoRA"). The flag is passed below anyway so the intent is on the record and the run
#   log carries train_lora's own "[ema] NOTE: … ignoring it" line. Enabling it for adapters is a
#   real change (SimpleEMA shadows the whole DiT; for an adapter it should shadow only the
#   trainable params, and the demo/save hooks that prefer diffusion_ema.ema_model need to know) —
#   NOT something to smuggle into a 16-GCD launch. C's arms running tonight have the same gap.
# WARMUP + SPECTRAL WD: both are FusionOpt-only knobs, hence --optimizer fusion. --weight_decay
#   routes to param_groups.spectral_wd (train_lora.py:449 — the constructor-level weight_decay is
#   only a fallback, the spectral group overrides it), so 0.03 lands exactly where Kim means it.
# ADAGC: --grad-clip-mode agc (+ --agc-lambda, default 0.01).
# ALPHA: not specified, so alpha = rank (s=1, the MASTER convention). C's concurrent rank-256
#   arms use alpha 196/128 (s<1) — if these are meant to be comparable with those, say so and
#   this needs changing.
#
# ── DATA ──────────────────────────────────────────────────────────────────────────────────
# Suomisoundi, pre-encoded: 1260 latents (256, 4096) fp32 + a T1/T2/T3 caption sidecar keyed by
# LATENT-FILENAME STEM. That key scheme is NOT goa's (goa live-encodes and keys by audio relpath)
# — copying goa's sidecar convention onto this one silently drops every caption and surfaces as a
# RecursionError, not a caption error (SKILL.md live-encode gotcha #3/#4). ARCHITECTURE.md flags
# the same footgun.
# The directory also holds silence.npy with no sibling .json — that is CORRECT: it is the
# variable-length padding latent, loaded separately as silence_latents and explicitly filtered
# out of the training file list (dataset.py:221). 1261 .npy vs 1260 .json is expected, not a gap.
#
# ── VERIFY BEFORE TRUSTING (SKILL.md: count artifacts, never trust rc) ────────────────────
#   grep -h LOCAL_RANK <log> | sort | uniq -c     → want 0,1,2,3 each TWICE (two real 4-way
#                                                    groups), never eight "LOCAL_RANK: 0"
#   ls <run>/epoch=*.ckpt                          → the actual deliverable
#   grep "Found .* files" <log>                    → want 1260, not 1261 and not 0
#   grep "\[ema\]" <log>                           → expect the "ignoring it" NOTE, see above

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

ARMSET=${ARMSET:-r32}
FRAMES=${FRAMES:-256}
PREC=${PREC:-fp32}
EPOCHS=${EPOCHS:-60}
CKEVERY=${CKEVERY:-5}
WARMUP_EPOCHS=${WARMUP_EPOCHS:-2}
WARMUP_FRAC=$(awk -v w="${WARMUP_EPOCHS}" -v e="${EPOCHS}" 'BEGIN{printf "%.6f", w/e}')
SPECTRAL_WD=${SPECTRAL_WD:-0.03}
# CAPTION MIX — deliberately NOT the trainer's 0.6/0.3/0.1 default, because that default was
# tuned for goa, where T1 is built PER TRACK from effnet genre400/moodtheme. Suomisoundi's T1 is a
# single corpus-wide label: measured over the sidecar, t1 is 1 unique string across all 1260
# entries ("suomisoundi, an eclectic Finnish sub-genre of psychedelic goa trance", 68 chars),
# while t2 is 1257/1260 unique (~155 chars) and t3 1257/1260 unique (~1951 chars). So inheriting
# goa's numbers would hand 60% of every epoch the IDENTICAL prompt and leave the per-track
# descriptive text — the only thing that teaches prompt-following — with 40% between them.
# 0.25/0.45/0.30 keeps a real style-anchor share (repeatedly binding the word "suomisoundi" to the
# corpus sound is worth having, and is what makes it a usable trigger at inference) while giving
# the majority to text that actually varies per track. Override with CAPTION_PROBS if you want the
# old behaviour or a pure-anchor run. Still not a MEASURED optimum, but no longer just my
# inference either — Kim reviewed the tier statistics and the 25/45/30 split and confirmed it
# 2026-08-18 ("those values makes sense"). Treat it as the agreed baseline: if the r32/r256 bracket
# shows weak prompt adherence this ratio is the first thing to bracket, and a change from here is
# a deliberate experiment against a ratified default, not a correction of a guess.
CAPTION_PROBS=${CAPTION_PROBS:-0.25,0.45,0.30}
LR_A=${LR_A:-1e-4}
LR_B=${LR_B:-3e-5}
SMOKE=${SMOKE:-0}

LAT_DIR=${LAT_DIR:-suomisoundi_latents}
SIDECAR=${SIDECAR:-${CODE}/lumi/suomisoundi_caption_sidecar.json}
RUNROOT=${SCRATCH}/runs/suomisoundi_dora

case "${ARMSET}" in
  r32)  RANK=32;  BS=${BS:-16} ;;
  r256) RANK=256; BS=${BS:-8}  ;;
  *) echo "[suomi] FATAL: ARMSET must be r32 or r256 (got '${ARMSET}')"; exit 1 ;;
esac
ALPHA=${ALPHA:-${RANK}}

# Preflight: every one of these has cost a real job when it was assumed instead of asserted.
[ -n "${SIF}" ] || { echo "[suomi] FATAL: no lumi-multitorch-full image"; exit 1; }
echo "[env] IMG=$(basename "${SIF}")"     # which image this run ACTUALLY got — the glob follows
                                          # whatever LUMI ships newest and it has moved before
[ -f "${VENV}/bin/activate" ] || { echo "[suomi] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SIDECAR}" ] || { echo "[suomi] FATAL: sidecar ${SIDECAR} not shipped"; exit 1; }
grep -q -- 'LOCAL_RANK.*set_device\|set_device.*LOCAL_RANK' "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[suomi] FATAL: train_lora.py missing the LOCAL_RANK set_device fix (code refresh needed -- without it every rank loads onto physical GPU 0)"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[suomi] FATAL: train_lora.py missing --warmup-frac (code refresh needed)"; exit 1; }
mkdir -p "${RUNROOT}" "${FLASH}"

# Stage latents to node-local /flash (Lustre random reads on 1260 small .npy are the slow path).
# The corpus is ALREADY an extracted directory on /scratch (uploaded with the archive/stems/
# captions before this script existed), so the directory is the primary path and the .tar.gz the
# fallback — the other training scripts here assume a tarball because that is how THEIR corpora
# arrived, which is a per-corpus accident, not a rule.
if [ ! -d "${FLASH}/${LAT_DIR}" ]; then
  if [ -d "${SCRATCH}/${LAT_DIR}" ]; then
    mkdir -p "${FLASH}/${LAT_DIR}"
    cp "${SCRATCH}/${LAT_DIR}"/*.npy "${SCRATCH}/${LAT_DIR}"/*.json "${FLASH}/${LAT_DIR}/" 2>/dev/null || true
  elif [ -f "${SCRATCH}/${LAT_DIR}.tar.gz" ]; then
    mkdir -p "${FLASH}/${LAT_DIR}"
    tar -xzf "${SCRATCH}/${LAT_DIR}.tar.gz" -C "${FLASH}/${LAT_DIR}" --strip-components=1
  else
    echo "[suomi] FATAL: neither ${SCRATCH}/${LAT_DIR}/ nor ${SCRATCH}/${LAT_DIR}.tar.gz exists"; exit 1
  fi
fi
NLAT=$(ls ${FLASH}/${LAT_DIR}/*.npy 2>/dev/null | wc -l)
echo "[suomi] ${LAT_DIR}: ${NLAT} .npy staged (1261 expected = 1260 samples + silence.npy)"
[ "${NLAT}" -ge 1000 ] || { echo "[suomi] FATAL: only ${NLAT} latents staged -- refusing to train on a truncated corpus"; exit 1; }

# CAPTION-KEY PREFLIGHT — the one failure here that is SILENT rather than loud.
# make_caption_sampler's _default_key takes basename-without-extension of info["latent_filename"]
# and looks it up in the sidecar; on a MISS it returns {} — no reject, no warning, no crash. The
# run trains happily on EMPTY PROMPTS and you find out from the renders days later. (The live-
# encode path keys by audio relpath instead, which is exactly the mismatch ARCHITECTURE.md flags
# between goa's sidecar and this one — copy the wrong convention and this is how it fails.)
# So: take a real staged latent, resolve its key the same way, and assert the sidecar has it.
python3 - "${FLASH}/${LAT_DIR}" "${SIDECAR}" <<'PYEOF' || { echo "[suomi] FATAL: caption-key preflight failed -- would have trained on empty prompts"; exit 1; }
import glob, json, os, sys
lat_dir, sidecar = sys.argv[1], sys.argv[2]
names = [p for p in sorted(glob.glob(os.path.join(lat_dir, "*.npy")))
         if os.path.basename(p) != "silence.npy"]
if not names:
    print("[suomi] preflight: no latents found"); raise SystemExit(1)
table = json.load(open(sidecar))
keys = [os.path.splitext(os.path.basename(p))[0] for p in names]
hit = [k for k in keys if k in table]
print(f"[suomi] caption keys: {len(hit)}/{len(keys)} latents resolve in the sidecar "
      f"(sidecar has {len(table)} entries; sample key {keys[0]!r})")
if len(hit) < 0.99 * len(keys):
    print(f"[suomi] preflight: MISS -- e.g. {[k for k in keys if k not in table][:3]}")
    raise SystemExit(1)
tiers = table[hit[0]]
print(f"[suomi] tiers present on a sample entry: {sorted(t for t in ('t1','t2','t3') if tiers.get(t))}")
raise SystemExit(0 if tiers.get("t1") else 1)   # t1 is the fallback tier; without it a t2/t3 miss yields ""
PYEOF

run_arm() {
  local ARM_NAME=$1 LR=$2 PORT=$3 GPUS=$4
  local RUN=${RUNROOT}/${ARM_NAME}
  mkdir -p "${RUN}"
  # Self-describing output (MASTER §4): what this arm is, why it exists, what it trained on, and
  # the exact recipe -- written AT CREATION, because a run dir whose provenance lives only in a
  # chat log is a dead end nobody can revive. `result`/`kim_feedback` stay null until measured
  # and until Kim has actually listened; the eval pages read that to mark a run UNAUDITED.
  cat > "${RUN}/run_meta.json" <<META
{
  "run": "${ARM_NAME}",
  "created": "$(date -Iseconds)",
  "slurm_job": "${SLURM_JOB_ID:-unset}",
  "purpose": "Suomisoundi (Kim's own-corpus finetune target) DoRA capacity x LR bracket: does rank 256 buy anything over rank 32 on a 1260-track corpus, and which LR holds. fp32 throughout, T=256 crops.",
  "hypothesis": "At 1260 tracks the corpus may not support rank 256; if r32 matches or beats it, the cheaper adapter is the one to ship. LR 1e-4 vs 3e-5 brackets the drift-vs-underfit axis.",
  "dataset": {"name": "suomisoundi", "latents": "${LAT_DIR}", "n_latents": ${NLAT}, "pre_encoded": true,
              "caption_sidecar": "$(basename ${SIDECAR})", "caption_tiers": "t1/t2/t3",
              "caption_probs": "${CAPTION_PROBS}",
              "caption_note": "t1 is ONE corpus-wide string on all 1260 tracks (not per-track as in goa); t2 1257/1260 unique, t3 1257/1260 unique. Probs shifted off the 0.6/0.3/0.1 default so 60% of samples do not share an identical prompt.",
              "augmentation": "none (pre-encoded)"},
  "recipe": {"adapter": "dora-rows", "rank": ${RANK}, "alpha": ${ALPHA}, "lr": "${LR}",
             "batch_size": ${BS}, "gpus": 4, "effective_batch": $((BS*4)), "frames": ${FRAMES},
             "precision": "${PREC}", "optimizer": "fusion", "spectral_wd": ${SPECTRAL_WD},
             "grad_clip": "agc", "warmup_epochs": ${WARMUP_EPOCHS}, "epochs": ${EPOCHS}},
  "known_gaps": ["EMA requested by Kim but NOT active: train_lora.py force-disables it for LoRA/DoRA (full-finetune only). Flag is passed; the log carries the trainer's own ignore notice."],
  "script": "lumi/sbatch/suomisoundi_dora_2x4gpu.sbatch",
  "result": null,
  "kim_feedback": null
}
META
  local STEP_ARGS="--epochs ${EPOCHS}"
  # NB: omitting --epochs is NOT "unlimited" -- max_steps falls back to --steps (default 10000),
  # and on a resumed run already past that it trains ZERO steps and exits COMPLETED 0:0.
  [ "${SMOKE}" = "1" ] && STEP_ARGS="--steps 20"
  srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=28 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUN='"${RUN}"'
VENV='"${VENV}"'
export ROCR_VISIBLE_DEVICES='"${GPUS}"'   # ROCR only -- never also HIP_VISIBLE_DEVICES (they stack)
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${ARM_NAME}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${ARM_NAME}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${ARM_NAME}"' PYTORCH_TUNABLEOP_ENABLED=0
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

# fp32 + SDPA: the math fallback materializes a T*T attention matrix. At T=256 that is trivial,
# but probe anyway so the answer is measured on THIS image rather than assumed from the last one.
if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 256, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    print("fp32 fused SDPA: OK")
except Exception as e:
    print(f"fp32 fused SDPA unavailable: {e}")
    raise SystemExit(1)
PYEOF
then export SA3_SDPA_CAST_BF16=0; else export SA3_SDPA_CAST_BF16=1; fi

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[suomi/'"${ARM_NAME}"'] resuming from ${FATCKPT}"; }

echo "[suomi/'"${ARM_NAME}"'] node=$(hostname) ROCR=${ROCR_VISIBLE_DEVICES} torchrun nproc=4 rdzv_port='"${PORT}"'"
torchrun --nnodes=1 --nproc-per-node=4 \
  --rdzv-backend=c10d --rdzv-endpoint=localhost:'"${PORT}"' --rdzv-id='"${ARM_NAME}"' \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base \
  --adapter_type dora-rows --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --encoded_dir ${FLASH}/'"${LAT_DIR}"' \
  --caption_sidecar '"${SIDECAR}"' --caption_probs '"${CAPTION_PROBS}"' \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion --base_precision '"${PREC}"' \
  --weight_decay '"${SPECTRAL_WD}"' \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode agc \
  --lr '"${LR}"' --batch_size '"${BS}"' \
  --frames '"${FRAMES}"' \
  '"${STEP_ARGS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  ${RESUME} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${ARM_NAME}"' 2>&1 | tee -a ${RUN}/train.log
echo "[suomi/'"${ARM_NAME}"'] step finished"
' &
}

# Distinct rdzv ports (two rendezvous servers on one node collide on a shared port) and an
# explicit disjoint GPU split, rather than trusting the step scheduler to hand out disjoint sets.
# Ports are ARMSET-scoped as well as arm-scoped. The two submissions each take a whole 8-GPU
# node so they cannot land together, but a port scheme that only works because of a scheduling
# assumption is one node-packing change away from a silent rendezvous collision.
case "${ARMSET}" in r32) P_A=29531; P_B=29541 ;; r256) P_A=29551; P_B=29561 ;; esac
run_arm "suomi_${ARMSET}_lr${LR_A}" "${LR_A}" "${P_A}" 0,1,2,3
run_arm "suomi_${ARMSET}_lr${LR_B}" "${LR_B}" "${P_B}" 4,5,6,7
wait

echo "[suomi] both arms finished (or timed out) -- verify the ARTIFACTS, never this script's rc:"
for A in "suomi_${ARMSET}_lr${LR_A}" "suomi_${ARMSET}_lr${LR_B}"; do
  echo "  ${A}: $(ls ${RUNROOT}/${A}/epoch=*.ckpt 2>/dev/null | grep -v weights | sort -V | tail -1)"
done
echo "[suomi] DDP check: grep -h LOCAL_RANK ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out | sort | uniq -c   (want 0,1,2,3 each twice)"
