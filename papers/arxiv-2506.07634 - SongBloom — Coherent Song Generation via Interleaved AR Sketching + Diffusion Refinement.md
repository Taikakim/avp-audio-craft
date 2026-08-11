# SongBloom — Coherent Song Generation via Interleaved AR Sketching + Diffusion Refinement (2506.07634)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). NeurIPS 2025, CUHK-Shenzhen /
Tencent AI Lab (Yang, Wang, Chen, Tan, Yu, Li). Shares our VAE+RF-DiT lineage; its coherence
mechanism is a learned alternative to our hand-written prompt arc.*

**What it contains.** A single model jointly trains an **AR "sketch" stage** and a **NAR diffusion
"refinement" stage**, generated **interleaved** at patch granularity: predict a patch of sketch
tokens, diffuse that patch's acoustic latents, feed compressed acoustic context back into the next
sketch patch (bidirectional exchange = coherence). A per-patch hidden vector `h_i` bridges
AR→diffusion (gradients flow back). AR = **LLaMA-2 decoder** over discretized **MuQ SSL sketch
tokens** (codebook 16384 @ **25 Hz**); NAR = **full-attention DiT, rectified-flow-matching**, over
**continuous latents from a stable-audio-vae** (2ch/48kHz), frame-rate matched to 25 Hz; patch =
16 frames = 0.64 s. Full songs to **150 s**; **surpasses Suno-v4.5 on several metrics**; follows
lyric structure where Suno rigidly repeats choruses. **Killer ablation:** remove sketch tokens →
PER 9 → **109** (alignment collapses) — the coarse sketch is *what* enforces long-range structure.
~10 diffusion steps near-optimal.

**Status vs our work.** Architecturally close — the refinement half is a **stable-audio-vae +
rectified-flow DiT**, so the novel part (**AR sketch + hidden-vector bridge**) is graftable onto
SAME without touching our latent or flow objective. The ablation (PER 109→9) is **direct evidence
that a learned coarse "sketch" is the anti-loop-collapse mechanism** — the same failure our
hand-written prompt arc currently patches; SongBloom replaces the arc with a learned, per-patch
structural plan that attends to prior acoustic context. **Frame-rate matching is load-bearing**
(their sketch and latent share 25 Hz); our 10.77 Hz SAME implies a longer patch-in-seconds, and
they found larger patches beat fully-separated stages — favorable for low-rate latents. **The
caution their own limitations flag:** coherence rides on discrete SSL sketch tokens + an AR LM, so
porting means bolting an AR module onto pure-diffusion SA3 (they call the SSL sketch the fragile,
un-interpretable part). What remains ours: pure-diffusion generation without an AR stage; SAME
domain; the disintegration gate; and instrumental long-form (SongBloom is lyric/vocal-centric).
