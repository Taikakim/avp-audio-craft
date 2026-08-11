# Closing the Loop: PID Feedback Control for Interpretable Activation Steering in Symbolic Music (2606.18790)

*Project-POV abstract, THE-FINN 2026-07-30. Prokopiou, Vikatos, Kaliakatsos-Papakostas,
Giannakopoulos, Stafylakis. **ICML 2026 Workshop "Learning to Listen" (ML for Audio).**
Symbolic music (Multitrack Music Transformer). **Same group / heavily overlapping with the
Gram-Schmidt disentanglement paper (2605.31295)** — read the two together. **Abstract-level
(WebFetch) — full PDF deep-read pending;** note the fetched abstract foregrounds the diff-in-
means + Gram-Schmidt content, while the **PID feedback loop is the paper's titular framing**
(and the ~5%-lower-FMD-vs-static figure comes from our 2026-07-30 citation audit, not the
abstract text) — treat the PID specifics as title/audit-level until the body is read.*

**What it contains.** Interpretable, retraining-free control of discrete musical attributes in
a Transformer music model. Uses **Difference-in-Means** to find latent directions for **Pitch**
and **Duration** in the residual stream, validates the **Linear Representation Hypothesis**
(strong correlation between steering magnitude and attribute shift), and — to handle
entanglement in multi-attribute steering — proposes a **Dual Steering framework using
Gram-Schmidt Orthogonalization**, which "reduces conceptual interference and signal degradation
compared to naive vector addition," giving independent deterministic control at inference. The
titular contribution is the **closed-loop PID controller on the steering coefficient**: monitor
the target attribute in intermediate activations and micro-adjust the coefficient per step so a
steered attribute is *held constant* across long autoregressive generation instead of washing
out (the audit records ~5% lower Fréchet Music Distance than static steering).

**Status vs our work — one half already CONFIRMED, one half a fresh lead.** The **diff-in-means
+ Gram-Schmidt dual-steering** half is the *same mechanism* our task-#58 already **CONFIRMED
strong-form on SA3 audio** (see 2605.31295): orthogonalize before summing to kill the
cross-concept disintegration — so that half is verified on our stack, and this paper is
external corroboration in a symbolic domain. The **genuinely new lead is the PID / closed-loop
coefficient controller** as a candidate for **keeping a steered attribute from washing out
across SA3's windowed long-form generation** — an *attribute-hold* mechanism, adjacent to but
distinct from the loop-collapse *structure-memory* problem (it holds a scalar target, it does
not recall musical form). Compare against: **2605.31295** (same GS mechanism, our confirmed
result), **AxBench 2501.17148** (the diff-in-means baseline both rest on), and our **LatCH
readout heads** (a PID loop is a control-theoretic alternative to a trained forward-conditioner).
What does NOT transfer: the symbolic-token domain (Multitrack Music Transformer, discrete AR),
Pitch/Duration as discrete targets, the FMD metric. What remains ours: the SA3 audio domain,
the buzz/disintegration gate, and whether a per-step PID loop stays stable on rectified-flow
*continuous* latents (a real risk — per-step coefficient swings are exactly what the gate
watches for).
