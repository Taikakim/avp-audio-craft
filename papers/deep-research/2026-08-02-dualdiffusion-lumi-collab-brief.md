# dualdiffusion (parlance-zz) on LUMI — collaboration feasibility + high-value experiments

*CONTINUITY 2026-08-02, for Kim's potential conversation with Parlance about running his
experiments on LUMI. Grounded in a read of the repo (`~/Projects/dualdiffusion`, branch
`p4_and_ddp`) + his README dev-log + the verified paper (arXiv:2207.10620). NOT a message to
Parlance — substance for Kim to draw on.*

## 1. LUMI / ROCm feasibility — encouraging, two real friction points

**What ports cleanly (most of it):**
- Attention is `torch.nn.functional.scaled_dot_product_attention` — the portable path, ROCm-supported. No flash-attn/xformers hard dependency.
- Multi-GPU via HuggingFace `accelerate` + a custom `trainer.py` → maps to a LUMI node (4× MI250X = 8 GCDs); accelerate runs on ROCm.
- bf16 throughout; no hard-coded `.cuda()` device strings (accelerate handles devices).
- Deps are ordinary Python (torch, torchaudio, torchcodec, einops, datasets, safetensors,
  laion-clap, transformers). The `environment.yml` pins `nvidia::cuda-toolkit` only as the
  build env — swap for the ROCm torch wheels we already run in `SAO/.venv`.

**Two friction points (both surmountable, and squarely our expertise):**
1. **Heavy `torch.compile` reliance.** Every module has `supports_compile=True` and wraps its
   forward in `torch.compile`. On ROCm this is the inductor/Triton path — exactly the
   MIOpen/compile behaviour we fought this week (the dilated-conv first-step stall). Fix:
   run eager for correctness first (there's a per-module `supports_compile` flag to gate),
   then enable compile selectively once cached. **This is the single biggest port item and
   it's precisely what our ROCm experience de-risks.**
2. **One custom CUDA kernel:** `mss_loss_2d_cuda_kernel.cu`, loaded via
   `torch.utils.cpp_extension.load` in `dae_trainer_m1.py` (the 2D multi-scale-PSD loss).
   `cpp_extension` hipifies `.cu` on ROCm and often "just works", but it needs a build check;
   worst case there's a pure-torch fallback path to write for the same loss.

**To verify early:** `laion-clap==1.1.7` + `torchcodec` on ROCm (audio I/O + CLAP embeds).

**Verdict:** no architecture rewrite, no exotic CUDA libs — the port is (a) ROCm torch
wheels, (b) manage torch.compile on ROCm, (c) build/hipify one loss kernel, (d) accelerate
multi-GCD config. Our ROCm/MIOpen scar tissue is the thing that makes this tractable — a real,
concrete value we bring to the exchange, not just compute.

## 2. Where LUMI scale changes the answer (his stated ceiling is "desktop GPU only")

His work has been bounded by one desktop card: SNES/VGM data, 32 kHz, 45 s crops, latent
width 512, a single "U3" larger model just begun (Jul 2025). LUMI unlocks the regimes he
couldn't reach:
- **Bigger / more diverse data at higher SR + stereo** — his interpretable-latent findings
  were established on small VGM data; do they hold on a large, realistic, higher-SR corpus?
- **The U3 larger model at node scale** (his current frontier, compute-limited).
- **His sweeps at scale:** the per-sigma error-variance sampling PDF, EMA-length ensembles,
  the MDCT inverse-wavelength coefficient rescaling / reduced noise-schedule range — all
  things he tunes on one card that a node lets him sweep properly.

## 3. What WE learn back (why it's worth our compute + porting effort)

His architecture is a controlled counter-design to SAME, and testing it at scale answers
questions our own program is actively chasing:
- **Interpretable phase-free latent + diffusion decoder vs SAME's detail-packed latent** —
  his central thesis is "remove fine detail from the latent (even at recon-quality cost),
  restore it with a 2nd-stage diffusion decoder → better LDM musicality." That is a direct,
  at-scale test of our new *phase-in-latent → high-entropy → poor-musicality* root-cause
  hypothesis (links our treble AND melody-wall threads).
- **Supersampled-latent shift-equivariance** — he gets sub-latent-pixel shift equivariance for
  free (no downsampling until a final avg-pool), sidestepping StyleGAN3 filtering / EQ-VAE
  augmentation. Directly relevant to our AFLDM/TIPS/LPS shift-equivariance thread — a cheaper
  answer than any we'd surveyed.
- **2D multi-scale PSD loss without a GAN** — reconstruction "comparable to adversarial" with
  no auxiliary trained model, trainable indefinitely without latent degradation. If it holds
  at scale it simplifies our #62 (maybe no discriminator needed).
- **Convergent validation of our DiT-side bets** — his independently-found "uniform-variance
  latents help the LDM" (= our whitening #65) and "v-pred + cosine ≫ alternatives" (= #66)
  get stress-tested on a second architecture + dataset.

## Bottom line
Technically feasible without a rewrite; the port is mostly our ROCm expertise applied to his
compile-heavy code + one loss kernel. Scientifically it's the highest-leverage external work
we've found — a scaled test of the exact phase-free-representation + diffusion-decoder +
uniform-variance-latent direction our own week converged on. The exchange is genuinely
two-sided: he gets the compute + ROCm porting his project has never had; we get an at-scale,
independent read on whether to bring these ideas into SA3.
