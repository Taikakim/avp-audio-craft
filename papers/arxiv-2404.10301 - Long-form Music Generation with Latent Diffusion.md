# Long-form Music Generation with Latent Diffusion (arXiv 2404.10301v2)

**Evans, Parker, Carr, Zukowski, Taylor, Pons — Stability AI, Jul 2024 (v2).**
This is the **Stable Audio 2** paper — the lineage step between SA1 (2402.04825) and SA3
(2605.17991). Deep-read by CONTINUITY 2026-07-21 (Kim's ask; note the author list — Zach
Evans is the same Zach whose Discord commentary we captured in
`docs/ai-research/2026-07-21-zach-stability-discord-notes.md`, and Julian Parker also
first-authors StemGen 2312.08723).

## What it contains

- **Target: full tracks, 4m45s (285 s) stereo 44.1 kHz in one context.** Motivated by a
  600k-track popularity analysis: 285 s covers ~83% of popular music; prior models' 90 s
  covered ~4%. Explicit thesis: structure needs long temporal context, NOT semantic tokens.
- **Autoencoder: VAE, raw-waveform, 157M**, DAC-like conv blocks + Snake activations with a
  *trainable β*, tanh removed from the decoder output (it caused harmonic distortion), 2048×
  temporal downsample → **21.5 Hz / 64-ch continuous latent** (vs SA1's 43 Hz, vs SAME's
  10.77 Hz / 256-d). Losses: perceptually-weighted multires STFT on **M/S plus L/R (L/R
  weighted 0.5)** to dodge L/R-assignment ambiguity; 5 conv discriminators (~4× param count
  of prior work); KL weighted 1e-4. Their stated design law: **keep perceptual quality at a
  LOW latent rate — that's what makes long-context training feasible** (SAME at 10.77 Hz is
  the continuation of exactly this argument).
- **DiT replaces the U-Net: 1.1B**, standard serial blocks (self-attn → cross-attn → gated
  MLP, skip connections, pre-LN), **RoPE on the lower half of q/k dims**, block-wise attention
  + gradient checkpointing to survive the sequence length. Conditioning: text (CLAP,
  from-scratch, next-to-last-layer features) via cross-attn; **timing (seconds_start/total,
  sinusoidal now — SA1 used learned per-second embeds) via cross-attn AND prepend**; diffusion
  timestep prepended as sinusoidal embed. — i.e. the AdaLN/global-embed pathway SA3 has does
  NOT exist yet here; everything rides cross-attn/prepend.
- **v-objective** (not RF yet), DPM-Solver++ 100 steps, CFG 7.0. AdamW 1e-5, exp ramp+decay,
  EMA, weight decay 0.001.
- **THE context-extension recipe (most relevant result for us):** pre-train at 3m10s for 70k
  GPU-h, then **fine-tune to 4m45s for only 15k GPU-h (~18% extra)**. Metrics show NO
  degradation pre→post extension ("confirming the viability of extending context length via
  this mechanism"). Table 2/3: FD_openl3 89.3→82.0 (at max length), beats
  MusicGen-large-stereo (~218) by ~2.7× while sampling 13 s vs 12m53s.
- **Variable length = generate full window, timing-conditioning fills the tail with silence,
  trim.** Same trick as SA1, at 285 s scale.
- **Structure findings:** SSM (self-similarity-matrix) analysis — generations show real
  intro/development/outro and *late sections echoing early motifs*, unlike MusicGen. MOS 4.0+
  across the board except **structure at 2 m length = 3.5 ("fair")**: 2-minute generations are
  *worse* than 4m45s ones. Their reading: full-structured 2 m tracks are scarce in training
  data (2 m music tends to be repetitive loops) — **length-conditional quality tracks the
  DATA distribution at that length, not model capacity**. Also: structure only emerged once
  context reached 4m45s — 3m10s wasn't enough.
- **Stereo correctness** 96–100% vs MusicGen ~60% (MusicGen pans center-instruments like
  bass/kick off to one side — the mixing-engineer failure mode).
- Data: same 806k-file/19.5kh AudioSparx set as SA1, same metadata-concat prompt recipe.
  Memorization study: top-50 CLAP-nearest training neighbors audited by ear, none found.
- Extras (§4.6): **audio-to-audio style transfer by initializing sampling noise from a
  recording** (proto-SDEdit, "beatbox→drums", voice-as-instrument feel); vocals produce
  melodic-but-unintelligible texture (no lyric conditioning); short-form still works.

## What it does NOT contain / what remains ours

No RF (v-objective), no SAME (VAE), no AdaLN or local-additive conditioning pathways, no
adapters/PEFT of any kind, no per-layer analysis (layer landscape untouched), no probes
(LatCH), no outpainting/stitching — their "long-form" is one giant window, so our
SDEdit+crossfade longform machinery solves a problem this paper sidesteps by brute context.
No post-training/ARC. Timing conditioning is used but never localized in the network.

## Why it matters to SAO right now

1. **Direct prior art for #50 / the frame sweep (#54):** pretrain-short → finetune-long at
   ~18% extra compute with no metric regression is exactly the lane our
   longctx_t2048/t4096 arms live in. Citable justification that context extension by
   fine-tuning is cheap and safe in this exact model lineage.
2. **The 2m-worse-than-4m45s result is a warning for eval design:** short-duration eval cells
   punish a long-context model for the *data distribution* at that length, not its quality.
   Bears on how we read 20 s matrix cells vs native-length cells (the native-cells lane
   exists for precisely this reason — keep them separated on the pages).
3. **"Structure emerges from context length, not semantic tokens"** — supports Kim's
   long-context program over token-planner add-ons; also matches Zach's Discord layer-roles
   framing (middle = knowledge) captured the same day.
4. The low-latent-rate design law is the published argument for why SAME's 10.77 Hz is a
   feature, not a compromise.

*Provenance: full deep-read of all 8 pages, 2026-07-21.*
