# Point-and-Play: Instrument Cloning from Music Mixtures

**Authors:** Tian, Chen, Wang, Duan (University of Rochester)  
**arXiv:** [2610.19445v1](https://arxiv.org/abs/2610.19445) (14 Oct 2026)  
**Code:** https://github.com/User-tian/Point-and-Play  
**Read:** ANTIGRAVITY (2026-10-26, full paper + architecture review)

---

## 1. Core Contribution

Addresses **instrument timbre cloning directly from polyphonic music mixtures** without intermediate waveform source separation. Given a multi-instrument mix and an audio or text cue, the system extracts a 512-dimensional continuous timbre code $z$ and uses it to condition a latent flow-matching note synthesizer (FlowSynth DiT style) conditioned on MIDI pitch and velocity.

### Architecture
1. **Mixture Encoder:** Music-domain CLAP HTSAT-base audio encoder fine-tuned with LoRA (rank 8, $\alpha=16$) on all `qkv, fc1, fc2` projections. Outputs frame token sequence $H = [h_1, \dots, h_T]$ (`[B, 1024, 1024]`) and global code $g$ (`[B, 512]`).
2. **Cue Encoder:** Frozen CLAP text or audio encoder yielding normalized cue embedding $q \in \mathbb{R}^{512}$.
3. **Cue-Gated Statistics Pooling (CGSP):**
   * Elementwise sigmoid gate: $a_i = \text{sigmoid}\left(\frac{(W_h h_i)^\top W_q q}{\sqrt{d}}\right) \in (0, 1)$ (independent per token; unlike softmax, does not sum to 1).
   * Weighted mean $\mu$ and standard deviation $\sigma_h$:
     $$\mu = \frac{\sum a_i h_i}{\sum a_i + \epsilon}, \quad \sigma_h = \sqrt{\frac{\sum a_i (h_i - \mu)^2}{\sum a_i + \epsilon} + \epsilon}$$
   * Residual fusion with zero-initialized final layer:
     $$z = \text{norm}(\text{norm}(q) + R_\theta[\mu; \sigma_h])$$
     Starts exactly at cue prior $q$ at step 0.
4. **Training Losses:**
   * $\mathcal{L}_{\text{inv}}$: Symmetric InfoNCE ($\tau=0.1$) between paired mixtures sharing identical instrument patch but different musical content and backing tracks (forces content invariance).
   * $\mathcal{L}_{\text{algn}}^a, \mathcal{L}_{\text{algn}}^t$: InfoNCE aligning audio/text-extracted $z$ to isolated teacher embedding $t = C_a(s)$.
   * $\mathcal{L}_{\text{sel}}^a$: Hinge loss pushing mismatched cue extraction $\bar{z}^a$ away from target $t$.
5. **Synthesizer:** Flow-matching DiT (24 layers, width 1024) predicting DiffRhythm VAE latents, conditioned via AdaLN on $W_z z + E_p(p) + E_v(v)$. Generates 8 candidates, selecting best by CLAP similarity to $z$.

---

## 2. Results Reported (27 held-out NSynth identities)

* **Oracle Timbre (clean solo note):** CLAP 0.811, FAD 1.78, MSS 2.04
* **Separate-then-clone (Demucs-closest):** CLAP 0.541, FAD 4.13, MSS 3.55
* **Point-and-Play (from mixture directly):**
  * Text cue: CLAP 0.706, FAD 2.23, MSS 1.92
  * Same-category audio cue: CLAP 0.678, FAD 1.92, MSS 1.92
  * Target-instrument audio cue: CLAP 0.696, FAD 1.92, MSS 1.92
* **Pitch Invariance Probe:** Ridge regression pitch probe $R^2$ drops from 0.783 (raw CLAP) to 0.263 on extracted codes (pitch is suppressed, though not entirely eliminated).

---

## 3. Status vs. Our Work

* **What it does NOT do:**
  * Does NOT predict physical synthesizer parameters (knobs, switches, ADSR, filter routing). It renders one-shot audio clips via a diffusion DiT.
  * Tested on acoustic/pop/rock mixtures (NSynth, Slakh, MoisesDB). Does not evaluate electronic music with overlapping sub-bass (kick + synth bass).
  * Does not eliminate the need for pitch conditioning (synthesizer still requires MIDI pitch $p$).
* **What is transferable to SAO Synth Inversion:**
  * **CGSP Module:** Can replace manual multi-note consensus by gating active synth frames across a phrase.
  * **Paired-Mixture Invariance Loss ($\mathcal{L}_{\text{inv}}$):** Forces encoders to discard melodic/pitch contours and isolate patch state.
  * **Cheaper Internal Adaptation:** Rather than introducing full CLAP + LoRA, the CGSP gate can be applied to our existing `temporal_asp` encoder and aligned to the Synth-JEPA embedding.
