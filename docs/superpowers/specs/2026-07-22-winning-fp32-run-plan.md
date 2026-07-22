# Winning fp32 run — plan + LUMI prep

**WINTERMUTE 2026-07-22.** Turns the DoRA hyperparameter × metric findings (`eval/dora_table.html`)
into a flagship fp32 training run on LUMI, with the ablations that separate the *real* recipe levers
from the small-dataset artifact Kim caught.

## What the data says (grounding)
Top CLAP genre-adherence is driven by a **recipe**, not by precision:
- **α < rank ("adj", rsLoRA α≈α/√r → α45 on r128)** beats the standard α=rank.
- **augmentation** is the cleanest single win (helps adherence + quality + cleanliness).
- **fp32 ≈ bf16 for adherence/buzz** — fp32's value is on the *fidelity/separation* axis (Kim's ear), which CLAP doesn't measure.

**The caveat (Kim caught it):** the headline `dora128adj_avp_aug10` "ep74" run was **3000 steps over a 320-crop augmented set** (`latents_avp_aug10`, N=320) — the model saw ~320 clips 74× = **overfit-risk / prompt-space memorization**. BUT full-corpus goa runs (`fullft_goa`, `fp32frames_goa`, **N=5401**) *match* its CLAP — so the recipe **wins on real data too**. Conclusion: build the fp32 run on the **full corpus**, and ablate the small-set setup as a control.

## The run
DoRA-rows on medium-base, **fp32**, **r128 / α45 (adj)**, **lr 1e-4**, **FusionOpt**, **T512 beat-aware crops**, per-epoch checkpoints. Trained on the **augmented full corpus** (`latents_avp` = 2393 augmented avp crops; `latents_sa3` = 5401 goa), long enough to matter (~20 epochs, not 8), with generalization validation (held-out prompts + disintegration gate + mood-drift).

### Arms (8 GCD, one standard-g node — whole-node billing, so fill it with ablations)
| PROCID | dataset (N) | T | α | precision | purpose |
|---|---|---|---|---|---|
| 0 | avp full (2393) | 512 | **45** | **fp32** | **FLAGSHIP — winning fp32 recipe, avp** |
| 1 | goa (5401) | 512 | **45** | **fp32** | **FLAGSHIP — winning fp32 recipe, goa** |
| 2 | avp full (2393) | 512 | 128 | fp32 | α control — isolates the adj benefit |
| 3 | goa (5401) | 512 | 128 | fp32 | α control, goa |
| 4 | avp_aug10 (320) | 512 | 45 | fp32 | **small-set control — reproduce the 320-crop setup in fp32 (does fp32 alone change the overfit result?)** |
| 5 | avp full (2393) | 1024 | 45 | fp32 | frames control (analysis: T1024 optimum) |
| 6 | avp full (2393) | 512 | 45 | **bf16** | precision control — measures fp32's actual gain (fidelity axis, by ear) |
| 7 | goa (5401) | 512 | 45 | bf16 | precision control, goa |

Reads directly against the existing fp32cmp campaign (α128, 8ep) — arm 0/1 vs the old fp32cmp isolates **α45 + long training**; arm 6/7 vs arm 0/1 isolates **fp32 vs bf16** on the identical winning recipe.

- **BS:** T512 fp32 is cheap (≈47.6 s crops) — BS8 fits comfortably on 64 GB (the fp32cmp T512 arms ran BS8). T1024 (arm 5) BS4. Reuse the template's probe if unsure.
- **Steps/epoch:** avp 2393/BS8 ≈ 300; goa 5401/BS8 ≈ 675. 20 epochs = 6k / 13.5k steps — real training, not 320-crop drilling.
- **Precision plumbing:** inherit `efp_fp32_compare.sbatch`'s SDPA-fp32-probe / `SA3_SDPA_CAST_BF16` island (no fp32 flash-attn exists).

## LUMI prereqs (all agent-crafted; Kim runs — `~/.ssh/id_EFP`, `akekim@efp.lumi.csc.fi`)
The fp32 campaign already staged `latents_avp.tar.gz`, `latents_sa3.tar.gz`, the SIF, models, and the fp32-patched code. **New prereq: the augmented-set tarball + a refreshed code tarball if `train_lora.py` changed.** Verify + stage:

```bash
# 1. what's already on scratch (dry-run doubles as inventory)
ssh -i ~/.ssh/id_EFP akekim@efp.lumi.csc.fi \
  "ls -la /scratch/project_465003186/latents_*.tar.gz"

# 2. stage the aug10 small-set tarball for arm 4 (only if not already there)
#    (local: /home/kim/Projects/latents_avp_aug10 -> tar -> scp)
tar -C /home/kim/Projects -czf /tmp/latents_avp_aug10.tar.gz latents_avp_aug10
rsync -av -e "ssh -i ~/.ssh/id_EFP" /tmp/latents_avp_aug10.tar.gz \
  akekim@efp.lumi.csc.fi:/scratch/project_465003186/

# 3. refresh the code tarball if train_lora.py / transformer.py changed since the fp32 campaign
#    (skip if unchanged — check git log on scripts/train_lora.py first)
```

## Submit + verify
```bash
# submit (from the code tree on LUMI, or paste into the EFP Workflows UI)
ssh -i ~/.ssh/id_EFP akekim@efp.lumi.csc.fi \
  "cd /project/project_465003186/code && sbatch lumi/sbatch/efp_fp32_winning.sbatch"

# verify — count checkpoints, NEVER trust the sbatch exit code (HQ/arm failures don't propagate)
ssh -i ~/.ssh/id_EFP akekim@efp.lumi.csc.fi \
  "ls /scratch/project_465003186/runs/*fp32_winning*/*.ckpt | wc -l"   # expect 8 arms × ~20 ckpts
```

## Post-run (mir/eval side, my lane)
Pull ckpts (fat only on terminal epoch, slims elsewhere — Kim's rule) → render the eval grid →
run **CLAP degeneration + spectral-fidelity + mood-drift + disintegration gate**, held-out prompts
included, and drop each arm into `dora_table.html`. The flagship "wins" only if it beats the
fp32cmp baseline **on held-out prompts** (not just the trained ones) — that's the memorization guard.

## Open decision for Kim
- **Arm set:** 8 arms as above (flagship + full ablation), or trim to just the two flagships (arm 0/1) + the small-set control (arm 4)? The whole-node bills the same either way, so full ablation is "free" — recommend keeping all 8.
- **Epochs:** 20 (my default) vs longer — augmentation means it likely keeps improving; per-epoch ckpts make the stopping point a post-hoc choice.
