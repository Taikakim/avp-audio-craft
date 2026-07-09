# LUMI-G Transition Plan — running LATCH / FiLM / DoRA training on the supercomputer

*2026-07-07, WINTERMUTE. Goal: move our SA3 control-head training (LATCH guidance heads,
FiLM/control adapters, DoRA LoRA) from the local RX 9070 XT box to **LUMI-G** (EuroHPC,
AMD MI250X). Written for someone who thinks in Runpod terms — the mental-model shift is
the hard part, not the code.*

## TL;DR — why this is less alien than it looks

**Our entire stack is already ROCm/AMD.** LUMI-G is AMD MI250X (gfx90a). There is **no
CUDA→ROCm port** — the thing that makes most people's LUMI move painful. What's actually
different from Runpod is only the **workflow**, and it comes down to four shifts:

| Runpod mental model | LUMI reality |
|---|---|
| Rent a box, it's yours, `ssh` in interactively | You submit **batch jobs** to a **Slurm** queue against a **project allocation** (GPU-hours) |
| `pip install` whatever, in `$HOME` | You bake deps into a **Singularity container** (`.sif`); pip-in-home is *forbidden* (kills the Lustre filesystem) |
| One GPU you SSH into | A **node = 8 logical GPUs** (4× MI250X = 8 GCDs); the payoff is running our *sweeps in parallel*, not one job faster |
| Internet on the box (wandb, HF download) | **Compute nodes are air-gapped** — no internet; wandb offline + sync, models pre-staged |

So the plan is mostly: (1) get an allocation, (2) package our venv as a container, (3) move
the data, (4) wrap our `train_*.py` in Slurm scripts. The training code barely changes.

---

## Phase 0 — Access & allocation (start THIS week; it has lead time)

Access to LUMI-G goes through the **EuroHPC Access Portal** (peer-reviewed). Three modes:

- **Benchmark & Development access** — small, *fast turnaround*, for porting/testing. **This is
  our entry point** — apply here first to get on the machine and validate the port before
  committing to a big allocation.
- **Regular Access** — the real allocation for the parallel bracketing sweeps (soup-design ×
  crop × LR, the whole reason we want LUMI). Bigger GPU-hour grant, longer review.
- **Extreme Scale** — flagship-size; not us.

**Action steps:**
1. Apply for **Benchmark & Development** access via the EuroHPC Access Portal now (scientific
   justification + methodology + resource estimate). Review is technical+scientific.
2. On approval, a project (`project_465XXXXX`) is auto-created on the EuroHPC Federation
   Platform → accept ToS, note the **project number** (every job needs `--account=`).
3. Set up login: SSH key + **MFA**, add your key in the portal/MyAccessID. Login node is
   `lumi.csc.fi`.
4. In parallel, draft the **Regular Access** application for the sweep campaign (it's the
   slow one — get it in the queue early).
- Helpdesk: `helpdesk@my-eurohpc.eu` / LUMI service desk. When stuck, ask them — they're used to onboarding.

## Phase 1 — Environment as a container (the core shift)

LUMI requires containers for Python/ML: thousands of small `.py`/package files on the shared
**Lustre** filesystem degrade it for everyone. **Singularity/Apptainer** is the only runtime.
Build a `.sif` with **`cotainr`** (LUMI's tool that turns a conda/pip env into a container):

```bash
# on a LUMI login node
module load LUMI cotainr
cotainr build sa3-train.sif \
  --base-image=/appl/local/containers/sif-images/lumi-rocm-<ver>.sif \
  --conda-env=sa3-env.yml
```

`sa3-env.yml` = our deps (python, torch-rocm, stable_audio_tools, sa3_control, numpy pin,
einops, etc.), pip section for the rest. Then run everything *inside* the container with
`singularity exec sa3-train.sif python train_latch.py …`.

**🚨 The #1 technical risk — ROCm/torch version.** Our local stack is **torch 2.10 + ROCm 7.2**
(bleeding-edge custom wheels). LUMI's *provided* PyTorch containers are **ROCm 5.5–6.x**.
gfx90a (MI250X) is supported by all ROCm versions, but a container's ROCm userspace must be
compatible with **LUMI's system driver**. **Recommendation: target LUMI's provided PyTorch
ROCm container and accept a torch-version change** (likely down to ~2.2–2.4 / ROCm 6.x) rather
than forcing our exact 2.10/7.2 — porting the workload is easier than porting the whole ROCm
stack. Validate a tiny run first; only fight for 2.10 if something we need requires it.

**Flash-attention:** our CK FA2 wheel is built for **gfx1201** — it won't run on gfx90a.
Options: (a) use LUMI's **AI container images** which already ship an AMD-ported FA2 for
gfx90a (easiest); (b) rebuild the CK FA2 for `GPU_ARCHS=gfx90a` inside the container. Start
with (a). (We already know FA is optional — SDPA fallback works, just slower.)

## Phase 2 — Data transfer

Move latents + timeseries + checkpoints to LUMI storage. Lustre tiers:
- `/users/$USER` — home, **small quota + inode limit** (don't put data or envs here).
- `/project/project_465XXXXX` — persistent shared project space → **latents, timeseries, the container**.
- `/scratch/...` — large, **auto-purged** → active run outputs.
- `/flash/...` — fast NVMe, purged → hot training data if I/O-bound.

Transfer: `rsync -avP` over ssh for the checkpoints/configs; **LUMI-O** (S3-style object
storage) for the big latent sets (`latents_sa3` ~13 GB, `timeseries` ~21 GB). Keep our
single-copy latents backed up before/after (the standing cold-backup risk).

## Phase 3 — Slurm job scripts + the actual payoff

A run becomes an `sbatch` script, not an interactive session:

```bash
#!/bin/bash
#SBATCH --account=project_465XXXXX
#SBATCH --partition=dev-g        # dev-g for testing; standard-g for the campaign
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1        # 1 GCD for a LATCH head; MI250X GCD ≈ our workload size
#SBATCH --time=02:00:00
srun singularity exec \
  --bind /project/project_465XXXXX:/data \
  sa3-train.sif python train_latch.py --encoded-dir /data/latents_sa3 …
```

**The payoff = parallelism.** Our bracketing sweeps (soup-design position×σ×epoch-span,
crop 256/512/1024, LR/optimizer ablations — see `lumi-cluster-bracketing`) are
**embarrassingly parallel**: one config per GCD → **8 configs/node**, or a **Slurm job array**
(`--array=0-31`) fanning a 32-cell sweep across 4 nodes at once. That's the thing the local
single-GPU box can only do serially. Soups are CPU-only to *build*; only eval needs GPU.

## Phase 4 — Code adaptation (small)

- **ROCm env:** our `rocm_env.py` / SAT `rocm_env.yaml` target gfx1201 — swap the arch-specific
  bits for **gfx90a** (MIOpen find-mode, `HSA_OVERRIDE_GFX_VERSION` not needed, TunableOp cache
  is per-arch → regenerate). The CK-flash-attn env var (`FLASH_ATTENTION_TRITON_AMD_ENABLE`)
  behaves per the container's FA build.
- **Paths:** replace local drive paths (`/run/media/kim/…`, NVMe) with the Lustre `/project`
  and `/scratch` paths.
- **WandB:** compute nodes have no internet → `WANDB_MODE=offline`, then `wandb sync` from a
  login node afterward. Same for any HF download — **pre-stage models into the container or
  `/project`** (no `from_pretrained` hitting the hub at runtime).
- **GPU binding:** MI250X is 2 GCDs/module with NUMA affinity — use LUMI's recommended
  `--gpu-bind` / CPU-affinity wrapper for multi-GCD runs (single-GCD runs don't care).

## Phase 5 — Validate → scale

1. **Parity run** (B&D access, 1 GCD): train one LATCH head on a small slice inside the
   container; confirm loss curve + a checkpoint that loads and steers like the local one.
2. **One sweep node** (8 GCDs): fan an 8-cell crop/LR bracket across a node; confirm the array
   pattern + telemetry (per-run wandb offline → synced).
3. **Campaign** (Regular access): the full soup-design × crop × LR sweep the local box can't do.

---

## Gotchas checklist (the stuff that bites)

- [ ] **Apply for access NOW** — peer review has weeks of lead time; everything else is blocked on it.
- [ ] **Never pip-install into `$HOME`** — container only (Lustre inode limits are real and enforced).
- [ ] **ROCm/torch version compat** — target LUMI's container ROCm, don't force 2.10/7.2 blindly.
- [ ] **Flash-attn is gfx1201-only in our wheel** — use LUMI's AI image FA2 or rebuild for gfx90a.
- [ ] **Compute nodes are air-gapped** — wandb offline, models pre-staged, no runtime downloads.
- [ ] **Base `.sif` symlinks in `/appl/local/containers` drift** — copy the image for reproducibility.
- [ ] **`--account=project_465XXXXX` on every job**, or it's rejected.
- [ ] **Back up the single-copy latents** before/after the transfer.

## First-week concrete action list

1. Submit the **Benchmark & Development** application (EuroHPC portal) + draft the Regular one.
2. Set up SSH key + MFA; confirm login to `lumi.csc.fi`.
3. Write `sa3-env.yml` (our deps) and do a **local dry `cotainr build`** targeting a LUMI base
   image so the container recipe is ready the day access lands.
4. Stage a **backup + a transfer-ready tarball** of `latents_sa3` + one checkpoint.
5. Write the parity-run `sbatch` script (Phase 3 template) pointing at `train_latch.py`.

## Sources
- EuroHPC allocations & access: https://docs.my-eurohpc.eu/allocations/ , https://docs.my-eurohpc.eu/requesting_resources/
- LUMI PyTorch/containers: https://lumi-supercomputer.github.io/LUMI-EasyBuild-docs/p/PyTorch/ ,
  https://lumi-supercomputer.github.io/LUMI-training-materials/ai-20240529/extra_06_BuildingContainers/ ,
  https://lumi-supercomputer.github.io/LUMI-training-materials/2day-20240502/09_Containers/
- MI250X scaling / RCCL: https://lumi-supercomputer.eu/scaling-the-pre-training-of-large-language-models-of-100b-parameters-to-thousands-of-amd-mi250x-gpus-on-lumi/
