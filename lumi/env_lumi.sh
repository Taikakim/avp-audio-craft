#!/bin/bash
# env_lumi.sh — source at the top of every sbatch script (INSIDE the srun/singularity line
# or exported before it). The gfx90a/LUMI replacement for our local rocm_env profiles.
# Local gfx1201-isms deliberately ABSENT: no FLASH_ATTENTION_TRITON_AMD_ENABLE (container's
# FA build decides), no TunableOp cache (per-arch; regenerate on LUMI if ever enabled).

# --- project (fill in when the allocation lands) ---
export SA3_PROJECT="${SA3_PROJECT:-project_465XXXXX}"
export SA3_DATA="/project/${SA3_PROJECT}/data"        # latents_sa3 / latents_avp / captions live here
export SA3_RUNS="/scratch/${SA3_PROJECT}/runs"        # active run outputs (scratch is auto-purged!)
export SA3_MODELS="/project/${SA3_PROJECT}/models"    # pre-staged HF weights (T5-Gemma, SA3 base)

# --- air-gapped compute nodes ---
export WANDB_MODE=offline                              # `wandb sync` from a login node afterwards
export HF_HOME="${SA3_MODELS}/hf"                      # never hit the hub at runtime
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# --- CPU binding: LUMI-G gives 7 usable cores per GCD (56/8) ---
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-7}
export MKL_NUM_THREADS=$OMP_NUM_THREADS
export OPENBLAS_NUM_THREADS=$OMP_NUM_THREADS
export NUMEXPR_NUM_THREADS=$OMP_NUM_THREADS

# --- ROCm on gfx90a (CDNA2) ---
export MIOPEN_FIND_MODE=2            # conservative; mode-6 crashed SA3-medium's DiT locally — don't gamble first
export PYTORCH_TUNABLEOP_ENABLED=0   # off until parity is confirmed; tuning caches are per-arch anyway
export PYTORCH_ALLOC_CONF=garbage_collection_threshold:0.8,max_split_size_mb:512
export HIP_FORCE_DEV_KERNARG=1
export TORCH_COMPILE=${TORCH_COMPILE:-0}  # our --compile worked on the LatCH heads locally; re-enable per-run after parity
