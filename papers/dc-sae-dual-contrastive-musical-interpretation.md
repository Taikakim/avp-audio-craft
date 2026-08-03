# Dual-Contrastive Sparse Autoencoders Reveal Features of Musical Interpretation (DC-SAE)

*PDF: `dc-sae-dual-contrastive-musical-interpretation.pdf` (sole copy — was stranded in
prospective-unchecked/ as `534_Dual_Contrastive_Sparse_Au (1).pdf` after the 07-30 deep-read;
filed beside this note by W 2026-08-03).*

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). Chen (TUM/MIT), Cherep (MIT), Maes
(MIT), Singh (Dartmouth). **ICML'26 Mechanistic Interpretability Workshop — a double-blind
submission (no arXiv id), which is exactly why it had zero web footprint.** Verification saga on
record: F/C wrongly flagged it "likely fabricated" 2026-07-30, then confirmed **real** when Kim
produced the PDF — a false-fabrication (blocked-source ≠ fabricated; see the knowledge.md preamble).
Now properly deep-read. Direct successor to our indexed SAE-music-steering paper (2505.18186), same
MIT group.*

**What it contains.** A **two-branch TopK sparse autoencoder** on the frozen residual stream of
**MusicGen-Large (layer 24)**. It factors activations into a **work-identity code z_i** (constant
across performances of the same piece) and a **performance-variation code z_j** (how a realization
differs), via parallel TopK encoders sharing one linear decoder. Supervision uses **work-level
metadata only** (performer labels held out for eval). The specialization trick: for each anchor it
builds a **bag of same-work different-recording "pivots"** (MERT-retrieved) — these are **positives
for z_i** (multi-positive MIL-NCE) and simultaneously **hard negatives for z_j** (InfoNCE with the
augmented copy as z_j's only positive), forcing the branches apart. "Features of interpretation" =
z_j directions capturing phrasing, rubato, timbre, arrangement. Results: z_i wins work-ID probes
(Classical 0.856 vs MERT 0.492); **z_j survives held-out channel augmentation** (codec/EQ/hum/gain)
where MERT/CLAP collapse to chance, and **emergent performer structure** appears with no performer
labels. **Steering** (rank-1 z_j direction into layer 24) beats matched-random on **70% of contexts**
(effects small, proof-of-concept). Dict width 32,768, TopK k=50.

**Status vs our work.** **Direct lineage to 2505.18186** (Singh/Cherep/Maes, our indexed
"discovering + steering interpretable concepts in generative music"): that recovered *flat*
dictionaries mixing genre/instrument/timbre; **DC-SAE's contribution is making the work-identity vs
performance-variation boundary explicit** via two branches — treat it as the **"interpretation-axis"
successor** to the paper we already track. Portability: **(1) partial substrate transfer** — DC-SAE
reads MusicGen's *discrete-token AR* residual stream at a named layer; SA3 has **no layer-24 residual
stream** — you'd pick DiT block activations at a timestep, so the injection site does *not* port. **(2)
The dual-branch / same-work-pivots-as-both-positive-and-hard-negative recipe IS the portable core** —
architecture-agnostic, and directly informs how to split "content" from "interpretation" in an SA3
SAE, extending our SAE lane. **(3) Interpretation/performance nuance is now a named, steerable axis**
(the z_j gallery: rubato piano, relaxed-swing sax) — evidence expressive nuance is linearly
recoverable, supporting an SA3 "steer the interpretation, preserve the piece" feature. **(4) Steering
is honest-but-weak (~70% vs random, small)** — a **calibration warning**: expect to need multi-feature
or larger-α interventions on SA3, and their MERT target-margin-gain + CLAP-sanity eval is a
ready-made steering metric. Cross-checks cleanly with **AxBench (2501.17148)**: SAEs underperform for
raw *steering*, but DC-SAE's value here is *interpretable disentanglement* (the detection/analysis
axis), not beating prompting for control — consistent, not contradictory. What remains ours: the
SA3-DiT injection site, the RF domain, and the disintegration gate.
