# Fast Timing-Conditioned Latent Audio Diffusion (arXiv 2402.04825v3)

**Evans, Carr, Taylor, Hawley, Pons — Stability AI, ICML 2024.** The **Stable Audio 1**
paper — origin of the lineage that leads to SA2 (2404.10301) and our SA3. Read via subagent
deep-read pass 2026-07-21 (CONTINUITY triage of Kim's prospective-unchecked batch).

## What it contains

- Text-to-audio LDM: variable-length, up to **95 s stereo 44.1 kHz**, 8 s render on one A100.
- **VAE (133M)**: DAC-style conv encoder/decoder, no quantizer, Snake activations, 1024×
  downsample → **64-ch / 43 Hz** latent. Losses: A-weighted multires **sum/difference (M/S)
  STFT**, multi-scale complex-STFT discriminator + feature matching, KL 1e-4. Encoder frozen
  at 460k steps, decoder fine-tuned onward.
- **CLAP text encoder trained from scratch** (HTSAT + RoBERTa) on their own data;
  **next-to-last hidden layer** features (NovelAI CLIP trick) via cross-attn. Ablation:
  CLAP_ours ≥ CLAP_LAION ≥ T5, but margins small — picked mostly for distribution match.
- **THE timing-conditioning definition (the headline, and the canonical citation for it):**
  `seconds_start` + `seconds_total` per training chunk, each mapped to **per-second learned
  embeddings, concatenated with text tokens into cross-attention** (not FiLM/global-embed —
  that's a later-lineage move). Short files silence-padded; at inference, request 30 s in a
  95 s window → model fills the tail with silence, trim it. §6.3/App C measure it honestly:
  slightly-short bias (audio ends just before the requested length), error bump at 40–60 s
  where training data is sparse, occasional detector false positives.
- **Diffusion: U-Net, 907M** (Moûsai-inspired; 4 levels 1024/1024/1024/1280; FiLM for the
  diffusion timestep; self+cross attn per block). **v-objective**, cosine schedule, 10% cond
  dropout, DPM-Solver++ CFG 6 at 100 steps (ablation: plateau by ~50).
- **stable-audio-metrics** (second contribution, released): FD_openl3 (stereo via per-channel
  concat, full-band), KL_passt windowed for long audio (10 s / 5 s hop, mean-logits),
  CLAP_score feature-fusion variant for >10 s. The benchmark-comparable eval suite for
  long-form stereo.
- Results: MusicCaps FD_openl3 108.7 vs MusicGen-large-stereo 216.1; VAE costs ~16 FD points
  (autoencoded real data 117.5 vs real 101.5). Loses to AudioGen on SFX KL/CLAP (~5% SFX in
  training data). Human eval pioneers binary stereo-correctness + structure questions
  (intro 92% / development 66% / outro 89% — vs MusicGen 37/–/26).
- Dataset: 806,284 files / 19.5kh AudioSparx (music 66% of files / 94% of GB). **Prompt
  recipe**: half metadata-keyed (`Instruments: Guitar, Drums|Moods: Uplifting`), half plain
  comma-joined, values shuffled, delimiter/case augmented — the lineage's prompting DNA.

## What it does NOT contain / what remains ours

No DiT, no RF (v-objective), latent is a 43 Hz VAE not SAME, no adapters, no per-layer
analysis (WHERE timing acts in the network is never asked — our layer-landscape question is
untouched), no outpainting/longform beyond the 95 s window, no post-training.

## Why keep it

Lineage ancestor + two citable standards: (1) the canonical seconds_start/seconds_total
timing-conditioning definition with its measured accuracy quirks (useful priors when
debugging SA3 length behavior — SA3 moved timing to different pathways, so differences are
informative); (2) stable-audio-metrics for benchmark-comparable long-form stereo numbers.
Also explains why SA-family models respond to key:value prompt structure (rarity-bracket /
prompt-bank relevance).

*Provenance: subagent full-read (14 pp), reviewed by CONTINUITY, 2026-07-21.*
