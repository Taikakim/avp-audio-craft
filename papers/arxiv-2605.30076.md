# UniSteer — Text-Guided Flow Matching in Activation Space for Versatile LLM Steering (2605.30076)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). ShanghaiTech (Shi, Zhang, Li,
Yang, Zhang, Yu, Ren), preprint. LLM-domain, but the mechanism is our exact math — a trained
conditional flow over activations — and it sits squarely in the Head-B readout-vs-conditioning
tension.*

**What it contains.** Learns **one conditional velocity field over a frozen LLM's residual-stream
activations**, conditioned on a **natural-language description** of a behavior ("be concise and
harmless"). Trains with flow-matching on the linear path `a_t=(1−t)a₀+ta₁` (Gaussian→real
activation), target velocity `u=a₁−a₀`. The text condition is encoded by a frozen Qwen3-0.6B and
injected into a **DiT-style transformer via cross-attention**, plus layer-index + token-position
embeddings. At inference (**"flow inversion"**): transport an observed activation *backward* under
a source condition to an intermediate noisy latent, then *forward* under the target condition, and
inject the edited activation back (edit strength λ). The same model **doubles as a classifier** by
conditional reconstruction energy `E=‖a−ã(c)‖²`. Beats **CAA (difference-of-means)** and RepE/LoReFT
on persona traits + multi-constraint steering across Llama-3.2-1B / Qwen2.5-1.5B/7B; edits localize
to the constraint-relevant token positions (not a global perturbation). No SAE baseline.

**Status vs our work.** **Same generative substrate as SA3** — a rectified-flow/flow-matching
velocity field, here trained *on internal activations* rather than the output latent, with
DiT+cross-attention-to-text conditioning that maps directly onto MM-DiT. Two things it sharpens for
us: (1) **the Head-B tension** — UniSteer is a **middle path** between our two poles: a *separately
trained* steering module (not the frozen generator, not a fixed vector) that still acts at
inference via flow-inversion. It **informs but does not validate Head-B**: it argues compositional
control is achievable *without* retraining the generator, a counter-premise to "forward-conditioning
is required" worth testing against our adapter approach. (2) **It beats difference-of-means** on
composed/multi-constraint targets — directly relevant to our diff-of-means mood-steering result and
its known failure mode (vector interference when composing moods); a learned conditional flow could
exceed a fixed mood vector. Its **reconstruction-energy classifier** is a template for turning our
LatCH feature-heads into label scorers, and a probe for *whether/where* a concept is represented
before committing to forward-conditioning it. What remains ours: the audio domain (all their results
are text; long-form explicitly unevaluated), the disintegration/buzz gate, and Head-B trained into
the generator itself (vs their external editor).
