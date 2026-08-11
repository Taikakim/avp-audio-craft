# prospective-unchecked/ triage sweep — 2026-07-06

Full literature triage + verify pass over 18 papers found in `papers/prospective-unchecked/`.

**Deleted first (step 0):** `Live Music Diffusion Models: Efficient Fine-Tuning and Post-Training of
Interactive Diffusion Music Generators.pdf` — a byte-identical duplicate of the file already
triaged as arXiv 2605.22717 (`2605.22717v1-Live Music Diffusion Models_...pdf`, kept). Removed
before triage; not counted among the 18.

Of the 18 triaged: **14 promoted** (abstract written to `papers/arxiv-<id>.md`, PDF moved to
`papers/`), **4 skipped** (PDF moved to `papers/reviewed-low-relevance/`, no abstract written).
All promoted papers got a light pass (`action: light-abstract`); none were flagged for
`deep-read-abstract` in this batch.

---

## Promoted — light pass (14)

- **Live Music Diffusion Models: Efficient Fine-Tuning and Post-Training of Interactive Diffusion
  Music Generators** (2605.22717) — Turns an offline block-outpainting flow-matching music model
  into a low-latency streaming generator via a routing+attention-mask KV-cache trick, plus
  ARC-Forcing (RL-free adversarial rollout post-training) to fix AR error accumulation. Verdict:
  **promoted-light**. Passes both hard filters (RF, waveform-VAE latent); adjacent-capability
  (streaming/interactive music), not a control-method hit, but the KV-cache mask and rollout-level
  adversarial objective are candidate blueprints for a future streaming SA3 or Longform
  rollout-stability fix. Not previously covered.

- **Diffusion Domain Expansion: Learning to Coordinate Pre-Trained Diffusion Models** (2605.23275)
  — A small trained ViT coordinator reconciles overlapping patches' predicted-clean outputs to
  extend a frozen diffusion model beyond its trained length/conditioning-count, beating naive
  overlap-averaging. Verdict: **promoted-light**. Fails both hard filters (DDPM/EDM, raw-waveform
  UNet1d) as shipped; competes conceptually (not head-to-head) with Longform's training-free
  SDEdit+crossfade approach — worth a future ablation note (trained z0_hat coordinator), not
  urgent. Not previously covered.

- **DEMON: Diffusion Engine for Musical Orchestrated Noise** (2605.28657) — StreamDiffusion-style
  ring-buffer + windowed VAE decode turns ACE-Step 1.5 (DiT+flow-matching, Oobleck VAE) into a
  live-playable instrument at 12+ generations/sec. Verdict: **promoted-light**. Systems/engineering
  paper, not a control method; concrete existence proof that per-frame live denoising-control
  curves are buildable and fast on a fast few-step RF-DiT — a candidate delivery vehicle if SAO
  ever builds a real-time SA3 instrument. Not previously covered.

- **UNISON: A Unified Sound Generation and Editing Framework via Deep LLM Fusion** (2605.31530) —
  MM-DiT unifying T2A + bilingual TTS/cloning + speech-in-scene editing via depth-matched
  per-layer Qwen2.5-Omni hidden-state injection into DiT blocks. Verdict: **promoted-light**. Fails
  hard filter 2 (mel-spectrogram continuous VAE). Depth-matched multi-layer text conditioning is a
  plausible cheap future ablation for SA3's T5Gemma cross-attention; editing-as-channel-concat
  reconfirms rather than extends Longform. Bulk of results (TTS/cloning) off SA3's turf. Not
  previously covered.

- **Score-Control for Hallucination Reduction in Diffusion Models** (2606.00377) — Penalizing a
  DDPM image model's score-Jacobian norm (via a repurposed I-DDPM variance head) shrinks
  off-manifold "hallucination" probability mass. Verdict: **promoted-light**. Fails both hard
  filters (DDPM, pixel/image-LDM); no tractable rectified-flow analog of the Jacobian trick exists
  yet. Conceptual cross-reference only, for the book's "honest frontier"/score-Lipschitz framing
  of SA3's untrained crispness-late regime. Not previously covered.

- **SegTune: Structured and Fine-Grained Control for Song Generation** (2606.02638) — A song DiT
  (genuine flow-matching, Stable-Audio-lineage 1D VAE) adds hierarchical global+segment
  natural-language text conditioning, channel-concatenated per time-window, plus an LLM lyric
  duration predictor. Verdict: **promoted-light**. Passes both hard filters loosely; lyrics/vocal
  task is outside SA3's scope, but the segment-broadcast text-conditioning pattern is a third
  design option (alongside LatCH's trained probes and FusionCC's frozen-meter consistency), and
  channel-concat-beats-linear-mix fusion is a reusable empirical finding. Not previously covered.

- **UAT: Unified Audio-Text Diffusion for Audio Generation, Editing, and Captioning** (2606.04939)
  — A dual-stream DiT makes the text-conditioning stream an actively co-updated peer of the audio
  stream, so one backbone does generation, SDEdit editing, and (via masked discrete text
  diffusion) captioning. Verdict: **promoted-light**; **already covered** in the sense that its
  editing mechanism is exactly SAO's shipped SDEdit re-anchor and its guidance is plain CFG — both
  already in the book. Cosine/EDM schedule (not RF), backbone is a weaker prior than SA3 by the
  paper's own ablation. The co-updated conditioning stream is outside SAO's current control-method
  mandate (no captioning thread).

- **Entropy as a Structural Prior: How a Log-Barrier on DiT Belief Space Drives Musical Diversity
  and Development** (2606.07207) — A parameter-free per-sample training-loss weight, computed from
  a DiT output's own temporal-energy entropy, claimed to fight mode collapse in DoRA fine-tunes of
  SA3 Medium. Verdict: **promoted-light**. Training-loss curriculum, outside the control-methods
  sourcebook's scope. Evidentiary base is weak (single seed/prompt, qualitative only, validating
  ablations explicitly deferred, mostly-"Anonymous"-looking citation list) — flagged as a
  speculative, unverified lead, not an adopted technique. Not previously covered.

- **DirectAudioEdit: Inversion-Free Text-Guided Audio Editing via Diffusion Prediction Contrast**
  (2606.07356) — Inversion-free DDPM audio editing via shared-noise re-noising plus one-step
  reverse-dynamics contrast (rather than raw prediction-difference contrast), with a dynamic
  increasing target CFG schedule. Verdict: **promoted-light**; **already covered** — this is the
  DDPM/mel sibling of FlowEdit (already in the sourcebook), and the paper's own justification
  (needed because diffusion SDE paths are curved, unlike RF's straight paths) argues FlowEdit
  remains the right tool for SA3. No new method for us, just a confirming pointer.

- **Unified Audio Generation and Editing via Joint Condition Modeling and Progressive Training /
  AudioWeave** (2606.16435) — A single DiT does TTA plus six instruction-editing tasks by
  concatenating reference-audio latents as context tokens (factorized global/local RoPE), trained
  with a staged base-then-mix curriculum. Verdict: **promoted-light**. Mel+vocoder small
  from-scratch backbone doesn't port, but two patterns are worth banking: concat-not-channel-expand
  reference conditioning with factorized RoPE, and the empirical finding that naive joint
  multi-task training measurably underperforms a staged curriculum. Not previously covered
  (adjacent to Longform's territory, not a duplicate).

- **Audio-to-Audio via Diffusion Warm Initialization** (2606.18968) — A DAFx26 empirical study
  locating the SDEdit skip-fraction sweet spot for timbre transfer via a pitch-Jaccard-distance +
  FAD metric sweep, on Stable Audio Open. Verdict: **promoted-light**; **already covered** — the
  core mechanism is exactly Longform's shipped SDEdit re-anchor. The JD+FAD grid-search tuning
  methodology is the one possibly-useful nugget, if Longform's re-anchor timestep selection is ever
  revisited.

- **Hybrid Diffusion Transformer for Instruction-Guided Audio Editing via Rectified Flow**
  (2606.20101) — A two-stage coarse-to-fine joint/cross-attention mel-domain DiT for
  instruction-guided add/remove/replace editing, RF-trained, small (78.6M params) and fast.
  Verdict: **promoted-light**; **already covered** in the sense that the RF objective and
  source-latent channel-concat conditioning are things SAO already has analogs of (Longform,
  LatCH). Mel+vocoder architecture doesn't port. The one actionable takeaway: a procedural
  mix-two-clips synthetic data recipe for generating add/remove/replace instruction triples,
  architecture-agnostic.

- **STAR-VAE: Structured Topology-Aware Regularization for Audio Reconstruction and Generation**
  (2606.23064) — A channel-wise Gamma-Growth KL power-law regularizer forces low-index VAE
  channels to store structure and high-index channels to store texture, paired with a CNN+Mamba
  bottleneck; beats SAO's own VAE on matched-rate reconstruction. Verdict: **promoted-light**.
  Autoencoder/tokenizer-layer paper, out of scope while SAME stays frozen — a parallel (KL-based)
  route to a goal SAME already pursues by different means (soft-norm + linear-decodability
  losses), not a checked box or a gap. Worth checking against only if SAME is ever retrained. Not
  previously covered. *(Note: source abstract_markdown for this paper arrived truncated/malformed
  in the triage batch; the file written to `papers/arxiv-2606.23064 - STAR-VAE: Structured Topology-Aware Regularization for Audio Reconstruction and Generation.md` was reconstructed from the
  paper's one-liner, relevance, and POV notes to match house format — flag for a spot-check against
  the PDF if precision matters later.)*

- **SwiftAudio: Data-Efficient Caption-Only Distillation for One-Step Text-to-Audio
  Diffusion-based Generation** (2606.31259) — Distills a pretrained multi-step DDPM mel-spectrogram
  TTA teacher (Auffusion) into a one-step generator using only text captions (no paired audio), via
  Variational Score Distillation plus a temporal-TV latent smoothness regularizer. Verdict:
  **promoted-light**; **already covered** in the sense that the *goal* (one-step/few-step TTA) is
  already solved for SA3 by APT distillation, a different mechanism. DDPM+mel architecture doesn't
  port. The L1 temporal-TV regularizer on latent frame-differences is a cheap, architecture-agnostic
  idea worth a footnote for future distillation/consistency work.

## Skipped (4)

- **WaveNeXt 2: ConvNeXt-Based Fast Neural Vocoders With Residual Denoising and Sub-Modeling for
  GAN and Diffusion Models** (2605.25506) — Reason: out of scope by construction. SA3 has no
  separate mel-to-waveform vocoder stage at all (SAME decodes its own latent directly to waveform);
  this is a classic TTS-pipeline (text→mel→vocoder→waveform) paper that SA3's architecture bypasses
  entirely. Nobody needs to re-review this — the domain doesn't apply, not just low priority.

- **FiPA-SR: FiLM-Conditioned Perceptually Informed Audio Super-Resolution** (2605.30594) —
  Reason: fails both hard filters at once (single-shot GAN, not RF/diffusion; operates on complex
  STFT spectrograms, not the SAME latent), and the task (bandwidth extension from a bandlimited
  input) has no analog anywhere in SA3's generative-control surface. The one transferable idea
  (FiLM conditioning on a scalar) is architecturally identical to what AdaLN already does in SA3 —
  confirms existing practice, adds nothing. Skip is final; no re-review needed.

- **EntangleCodec: A Unified Discrete Audio Tokenizer via Semantic-Acoustic Entanglement**
  (2606.02739) — Reason: different modality of audio modeling entirely — a discrete-VQ
  single-codebook tokenizer feeding an autoregressive LLM (next-token prediction over a learned
  codebook), with a small rectified-flow decoder used only to invert mel-spectrogram tokens back to
  mel-spectrograms. No DiT, no continuous SAME-style latent, no RF-on-continuous-latent relevance.
  SA3 already gets rich semantic latent structure via SAME's own contrastive text alignment and
  linear-decodable regressors. Skip is final; no re-review needed.

- **SURF: Separation via Unsupervised Remixing Flow** (2606.04921) — Reason: solves single-channel
  blind source separation (unmixing K unknown, unobserved sources from one waveform) — a task with
  no analog anywhere in SAO's pipeline, which does conditional generation/editing of one latent
  audio stream, not source separation. The core mechanism (ReMixIT/self-remixing, mixture-additivity
  exploitation) has no substrate to attach to in SA3. Skip is final unless SAO takes on a
  separation/demixing product feature, which is out of scope today.

---

## Summary counts

- Deleted (duplicate): 1
- Triaged total: 18
- Promoted (abstract + PDF moved to `papers/`): 14
- Skipped (PDF moved to `papers/reviewed-low-relevance/`): 4
