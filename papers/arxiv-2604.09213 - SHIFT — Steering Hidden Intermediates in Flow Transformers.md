# SHIFT — Steering Hidden Intermediates in Flow Transformers (2604.09213)

*Project-POV abstract, THE-FINN 2026-07-30 (deep-read pp.1-8). FusionBrain/HSE (Konovalova,
Kuznetsov, Alanov). The architecturally-closest steering paper to SA3 — it targets the exact
MM-DiT / rectified-flow family SA3 lives in, and independently confirms our stable-direction result.*

**What it contains.** Inference-time **activation steering for Multimodal Diffusion Transformers
(MM-DiT)** — the FLUX / SD3.5 family (explicitly the same class as SA3: unified attention over
concatenated text+image tokens, rectified-flow). Primary task is **concept erasure** (remove a
concept at inference, no retraining), with the same mechanism doing style-domain shift and
object add/change. Mechanics:
- **Where to steer:** two points — the text-encoder **pooled embedding** (CLIP) and the
  **diffusion-transformer text tokens after the shared attention layer** (`Y_steered = Y_t + α·v`);
  steering both beats text-encoder alone.
- **Steering vector:** contrastive prompt pairs (concept vs neutral) → **mean-difference**
  (`v_diff = mean(a⁺−a⁻)`, token-averaged, channel-normalized) *or* a **linear-SVM** hyperplane
  normal. (Both are the DiffMean/SVM family AxBench crowned.)
- **KEY finding — temporally INVARIANT:** a single time-independent steering vector applied across
  **all diffusion timesteps** works; "semantic concepts are encoded as stable, global directions
  in DiT latent manifolds." Only 20–135 prompt pairs needed.
- **Adaptive strength (anti-over-steer):** an SVM concept-presence score `η_cls` scales α down when
  activations are far from the target class and up when concept evidence is strong — suppressing
  over-steering in weakly-separated layers/timesteps.
- Steering vectors **transfer across distillation boundaries** (Flux schnell→dev).

**Status vs our work — the closest-to-SA3 steering method, and a confirmation.** SA3 is an
MM-DiT (rectified-flow, unified attention), so SHIFT's intervention **ports more directly than
AxBench's LLM steering** (2501.17148): it names concrete SA3 hook points (post-shared-attention
text tokens; pooled embedding). It **independently confirms CONTINUITY's "steering direction is
temporally stable across generation"** result — on exactly this architecture class, via the
time-invariant vector. Its `η_cls` adaptive strength (gate by *concept-presence*) is a
**complement** to our disintegration gate (gate by *audio-buzz*) — orthogonal failure axes that
could compose into one strength controller. Contrastive-pair DiffMean = our mood-probe direction.
**Concept ERASURE** is a use case we haven't tried (negative/removal steering — worth a probe for
suppressing unwanted elements). **What remains ours:** the audio domain; the disintegration/buzz
gate (SHIFT has no audio-quality screen — `η_cls` catches "concept gone," not "clip turned to
noise"); Head-B forward-**conditioning** (train the model to USE a handed stream — distinct from
all of SHIFT's inference-time readout steering); and our LatCH numeric-feature heads + the
distilled-checkpoint transfer question (their cross-distillation result predicts our APT-distilled
SA3 checkpoints should share steering vectors — testable).
