# DiffRhythm 2 — Efficient High-Fidelity Song Generation via Block Flow Matching (2510.22950)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). ASLP Lab / Xiaomi MiLM (Jiang,
Chen et al.). **The most portable anti-loop-collapse mechanism in this batch** — block flow
matching grafts causal dependency onto an RF-MM-DiT without changing the flow objective, and it
shares our exact VAE lineage.*

**What it contains.** End-to-end **semi-autoregressive** song generator on **block flow matching**:
partition the latent into fixed-length blocks; generate each block **non-autoregressively via
conditional flow matching**, but enforce **AR dependency *between* blocks** through an attention
mask (clean block i attends only to clean blocks 1…i-1 + its own noisy block). Clean/noisy
sequences are concatenated and distinguished by the **FM timestep** (style/lyrics t=−1, clean=1,
noisy∼U[0,1]) — no delimiter tokens. Variable length via an **End-of-Prediction frame** (constant
N(1,0) vector padded at the end). **Block-level KV cache** for speed. Custom **Music VAE @ 5 Hz**
(24kHz in, 48kHz out) whose **encoder reuses the Stable Audio 2 VAE architecture**, BigVGAN
decoder. Full-song mixed-track, **up to 210 s**. Best open-source Mulan/PER; **block-size ablation:
PER best at block 5 (0.11), worse at 100 (0.23)**; RTF 0.455→0.154 (block 5→20). **Stochastic
block REPA loss** (MuQ SSL, whole-sequence) is the cited fix for structural coherence.

**Status vs our work.** **Block flow matching is the single most graftable idea** for our
loop-collapse: it injects genuine **causal dependency into a flow-matching model** (which pure
bidirectional flow lacks) via only an attention-mask + training-scheme change — **no change to
SA3's RF objective or SAME latent**. They **share our VAE lineage** (SA2 encoder) but push to
**5 Hz vs our 10.77 Hz** to make 210 s tractable, *explicitly noting low frame-rate upper-bounds
fidelity* — direct evidence on the rate/length/fidelity trade-off we navigate, and a caution
against lowering rate. **Stochastic block REPA** (MuQ SSL alignment on the whole sequence to dodge
conv-misalignment) is portable as an auxiliary coherence loss regardless of block-AR adoption. The
**EOP variable-length trick** is a clean continuous-latent termination mechanism. The block-size/RTF
ablation quantifies the AR-overhead we'd inherit (block-AR reintroduces sequential cost; caching +
moderate blocks recover most speed — contradicts "flow matching is fast because parallel"). What
remains ours: SAME @ 10.77 Hz, instrumental focus, the disintegration gate. (Cross-pair preference
optimization is lyric/song-specific, less relevant.)
