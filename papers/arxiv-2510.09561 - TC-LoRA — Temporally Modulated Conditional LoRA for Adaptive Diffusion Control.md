# TC-LoRA — Temporally Modulated Conditional LoRA for Adaptive Diffusion Control (2510.09561)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). NeurIPS 2025 Workshop (SpaVLE),
NVIDIA / U. Michigan (Cho et al.). Directly relevant to whether our control-adapters should be
static or timestep-generated — a weight-space alternative to our FiLM/onset/LatCH activation
injections.*

**What it contains.** Instead of a static adapter injecting features into *activations*
(ControlNet-style), a single shared **hypernetwork H_φ generates the LoRA matrices B, A on-the-fly
per denoising step**: `W'_i = W_i + B(i,t,y)A(i,t,y)`, functions of layer-index `i`, diffusion
timestep `t`, and conditioning signal `y` (e.g. depth map). This lets the model apply a
**stage-dependent** conditioning strategy — coarse structure early, fine detail late — rather than
one fixed operation across all steps. Only the hypernetwork trains (base frozen; B zero-init =
identity at start); adapters attach to the linear projections in all self/cross-attn blocks.
Distinct from T-LoRA (which only rescales a *static* B,A by a time-dependent magnitude — here the
adapters are fully regenerated). Base = Cosmos DiT; trained on MS-COCO, **beats a ControlNet
baseline on depth-conditioned generation (si-MSE 1.06 vs 1.56) with 251M vs 900M trainable params**.
Domain: image. Caveat: per-step weight regen adds inference cost; temporal consistency across frames
is unsolved (their future work).

**Status vs our work.** The **core thesis is a live design question for our adapter stack**: SA3
already has FiLM/timestep conditioning on *activations*, but TC-LoRA argues (App. D) that
**weight-space adaptation is strictly more expressive** than adding to activations. So: should our
DoRA / onset / LatCH / Head-B control-adapters be **static, or hypernetwork-generated per
flow-time**? The **coarse→fine stage specialization maps cleanly onto rectified-flow trajectories**
(early steps = global form, late steps = transient/timbre detail) — one flow-time-conditioned
adapter could serve both regimes instead of a fixed control strength, the audio analogue of their
depth result. The **parameter-efficiency argument** matters for our adapter-heavy stack: one shared
hypernetwork conditioned on layer-ID produced all adapters at ~3.6× fewer params — a single
conditioning hypernetwork could replace a proliferation of static per-control adapters. **The
caution is squarely aimed at us:** their own limitation is that per-step weight-swaps threaten
**temporal consistency**, validated only on single images with modest margins — a real warning for
audio's inherently sequential signal, exactly where our loop-collapse lives. So: promising for
adherence, but pilot against a continuity/disintegration gate before trusting it on long-form. What
remains ours: the audio/SAME domain, the buzz gate, and Head-B forward-conditioning (a different
lever than weight-modulated control).
