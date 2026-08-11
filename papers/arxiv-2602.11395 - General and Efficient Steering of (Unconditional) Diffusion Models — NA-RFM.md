# General and Efficient Steering of (Unconditional) Diffusion Models — NA-RFM (2602.11395)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). UCSD HDSI (Wang, Belkin, Wang).
The paper that says **difference-of-means is beatable** — a concrete upgrade path for our DoM
mood-steering, and a scaling trick that speaks directly to the buzz gate.*

**What it contains.** **NA-RFM** = a post-hoc, **gradient-free** recipe to steer a *pretrained
unconditional* diffusion model toward conditions unseen at training. Offline it learns two signals
from labeled target-vs-background examples: (1) **noise alignment** — a high-noise pixel-space
correction (class-conditional PCA denoiser minus full-data PCA denoiser, a Gaussian mimic of CFG);
(2) an **RFM direction** — a Recursive Feature Machine learns a target-discriminative direction in a
chosen block via the **AGOP eigenspace**. At inference: add noise alignment in the high-noise window,
**add the RFM direction to the block activation** over an intermediate/late window with a CFG-like
amplification `s`. Results: CIFAR-10 96.6% target-acc, **16× faster than TFG**; ImageNet/CelebA
beats gradient guidance; rare Male+Blond (1% of data) 68% vs 47%. **Ported to transformer DiT
(SiT-XL/2)** by steering middle blocks. Training-free at inference (weights frozen; directions
trained cheaply offline). Directions stable for σ∈[0.6,2.0], degrade at high σ.

**Status vs our work.** Three things land directly. **(1) It explicitly REJECTS difference-of-means**
for direction discovery — DoM collapses diversity and scores 6.2% vs RFM's 30.5% on a fine-grained
class. That's a **drop-in upgrade candidate for our DoM mood-steering**: swap the mean-difference
vector for an AGOP/RFM-learned direction (covariance-weighted class separation), test whether it
lifts our weaker moods (e.g. the "relaxing" that refused to steer). Note the tension with AxBench
(where DoM was the *best* fixed vector) — RFM is a *stronger* learned direction, not a fixed vector,
so both can be true. **(2) The CFG-like amplification `s` is exactly the over-steer regime our
disintegration/buzz gate bounds** — their Fig-4 Pareto (control vs quality degradation) is the same
curve; their `s`-sweep is a knob our gate could cap objectively. **(3) The activation-norm-
proportional edit** `H + w·‖H‖_F·V` keeps steering magnitude proportional to current activation
scale — a **principled scaling for LatCH/Head-B activation steering that may prevent buzz** from
fixed-magnitude adds (worth adopting regardless). Bonus: **steering WITHOUT text conditioning is the
whole premise** — directions from example activations applied to a null/unconditional model — which
maps onto steering SA3 for **audio attributes not captured by captions** (mood/timbre), mirroring
their uncaptioned depth-of-field case. And it **ports to DiT** (SiT), confirming the choose-layer /
learn-additive-direction / add-during-sampling recipe transfers to our MM-DiT class. What remains
ours: the audio/SAME domain; the RF timestep window-selection sweep (their directions are only
stable over an intermediate-σ window — needs an RF analogue); the buzz gate; Head-B in-generator.
