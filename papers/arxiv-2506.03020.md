# InfiniteAudio — Infinite-Length Audio Generation with Consistency (2506.03020)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). KAIST (Jung, Ki, J.-H. Kim,
J. Kim, J.S. Chung). A training-free rolling-window inference wrapper — a direct alternative to
our "reset the clock each window" long-form scheme, though DDPM/mel not RF.*

**What it contains.** A **training-free inference wrapper** for pretrained diffusion TTA models
(tested on AudioLDM, VoiceLDM) giving arbitrary length at **constant memory**. Two mechanisms:
(1) **FIFO sampling** (from FIFO-Diffusion, video): a fixed window of mel-frames each held at a
*different* diffusion timestep on a diagonal schedule — pop the fully-denoised front frame, push
a fresh-noise frame at the back, N frames in N steps. A **"buffer zone"** of clean initial frames
closes the train/inference timestep-distribution gap. (2) **Curved denoising**: self-attention
maps pick which step-regions matter, allocate steps there, skip elsewhere. Numbers: constant vs
AudioLDM's ~35 GB-at-120 s linear growth; matches 200–250-step runs in <150 steps; variable-length
≈ fixed-10 s quality; beats naive concatenation. Diagnostic: AudioLDM attends *early* frames,
VoiceLDM *late* — hence per-model focus choice.

**Status vs our work.** The **FIFO rolling diagonal-noise buffer is the idea to steal**: context
is continuous and always shared, so there is **no per-window seam** — exactly where our
loop-collapse / discontinuity lives, and a direct alternative to Longform's reset-the-clock scheme
(which creates the boundary the FIFO buffer eliminates). Two frictions: (a) it's **DDPM-formulated
on mel**, so on SA3's rectified-flow SAME latent the per-frame timestep must be remapped onto the
straight-path time variable — porting work, not a drop-in; (b) it's mel+vocoder, we're continuous
latent. But it's **training-free and testable on SA3 as-is**, and the **buffer-zone recipe** (clean
context at training-consistent timesteps) is a concrete reset-boundary-artifact fix. Their
**self-attention-map analysis is a ready diagnostic** we should run: does SA3 over-attend a fixed
context region? — that would mechanistically explain loop-collapse. Curved denoising is the weakest
transfer (SA3 already runs few RF steps). What remains ours: the RF/SAME domain, the disintegration
gate, and the conditioning-side arc (which FIFO complements rather than replaces).
