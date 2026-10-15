# Learning metrics on spectrotemporal modulations reveals the perception of musical instrument timbre — Thoret et al. (Nature Human Behaviour 5, 343–353, 2021)

Étienne Thoret, Baptiste Caramiaux, Philippe Depalle, Stephen McAdams. *Nature Human Behaviour* 5, 343–353 (2021). DOI: [10.1038/s41562-020-00987-5](https://doi.org/10.1038/s41562-020-00987-5). Original PDF: `s41562-020-00987-5.pdf` (symlinked).
**Status: DEEP-READ (full paper & methods reviewed 2026-09-30, filed & sidecar created 2026-10-11).**
Theoretical backbone for Ben Hayes's [`timbre-dissimilarity-metrics`](https://github.com/ben-hayes/timbre-dissimilarity-metrics) repository and empirical benchmark suite.

---

## 1. What It Shows

### A. The Collapse of 45 Years of 2D/3D MDS Timbre Spaces
- **Historical paradigm (1977–2016):** Psychoacoustic timbre literature traditionally reduced musical timbre to a 2D or 3D Euclidean coordinate space via Multidimensional Scaling (MDS) on pairwise dissimilarity matrices, attempting to correlate dimensions with hand-crafted scalar acoustic descriptors:
  - Dim 1: Log Attack Time (LAT) $\to$ "Percussive vs. Sustained"
  - Dim 2: Spectral Centroid (SC) $\to$ "Bright vs. Dark"
  - Dim 3: Spectral Flux / Harmonic Odd-Even Ratio $\to$ "Nasal / Hollow"
- **Meta-analysis of 17 historical datasets:** Re-analyzing 17 perceptual datasets across 8 landmark studies (Grey 1977, Grey & Gordon 1978, McAdams et al. 1995, Iverson & Krumhansl 1993, Lakatos 2000, Barthet et al. 2010, Patil et al. 2012, Siedenburg et al. 2016) demonstrated that original correlation claims were largely unreplicable across differing acoustic corpora. Reported correlations were heavily inflated by implicit experimenter tuning (choice of MDS metric variant, selective descriptor formulations, outlier filtering).
- **The "Cochlear Implant (CI) Paradox":** Severe clinical counter-evidence: hearing-impaired listeners with cochlear implants (who cannot distinguish an oboe from a violin or identify instrument families) produce the **exact same 2D MDS space** as normal-hearing conservatory musicians. Proves conclusively that 2D/3D scalar projections capture only coarse macroscopic envelope energy while discarding the acoustic substrates of genuine musical timbre identity.

### B. Biologically Inspired 4D Cortical Spectrotemporal Modulations (STM)
- Rather than reducing audio to scalar summary statistics, the authors adopt the Chi, Ru, & Shamma (2005) computational model of the primary auditory cortex (A1, via NSL Tools):
  1. **Auditory Spectrogram:** Audio downsampled to 16 kHz $\to$ 128 constant-Q asymmetric bandpass cochlear filters spanning 5.3 octaves with lateral inhibition and 4 ms midbrain phase-loss integration.
  2. **Cortical STRFs (Spectrotemporal Receptive Fields):** 2D modulation filterbank applied to the spectrogram, characterizing rate (temporal modulations) and scale (spectral modulations).
  3. **Full STMF Tensor:** Spans 128 log-frequency channels $\times$ 22 temporal rates ($r \in \pm [4.0, 5.7, 8.0, 11.3, 16.0, 22.6, 32.0, 45.3, 64.0, 90.5, 128.0]\text{ Hz}$) $\times$ 11 spectral modulation scales ($s \in [0.25, 0.35, 0.50, 0.71, 1.00, 1.41, 2.00, 2.83, 4.00, 5.66, 8.00]\text{ cycles/octave}$).
  4. Time-averaged to produce a static 3D tensor of dimension $128 \times 22 \times 11 = 30,976$, with marginal 2D projections: Scale–Rate ($11 \times 22 = 242$), Frequency–Rate ($128 \times 22 = 2,816$), and Frequency–Scale ($128 \times 11 = 1,408$).

### C. Metric Distance Learning on Perceptual Dissimilarity
- Instead of unweighted Euclidean distance, the authors optimize a diagonal Gaussian RBF kernel on vectorized STMF tensors $x, y$:
  $$k(x, y) = \exp\left( - \sum_{i=1}^{N} \frac{(x_i - y_i)^2}{w_i^2} \right)$$
- The optimized kernel explains **78%–83% of variance** ($R^2$) in human perceptual dissimilarity ratings across diverse acoustic stimuli (vs. only 11%–30% for raw spectral Euclidean distance).
- **Core perceptual substrates:**
  - **Scale–Rate is generic:** Across all 17 datasets, kernel weights concentrate in **slow temporal modulations ($<15\text{ Hz}$)** (envelope phrasing, vibrato, tremolo) and **spectral modulation scales around $1.0\text{ cycle/octave}$** (macro-formant peak/valley spacing).
  - **Frequency–Scale and Frequency–Rate are stimulus-specific:** Listeners dynamically weight finer frequency-dependent modulation patterns to differentiate instruments with overlapping macroscopic envelopes.

---

## 2. Relevance to SAO & Implementation Takeaways

1. **Theoretical Grounding of Ben Hayes's Benchmark:**
   - This paper is the primary scientific basis for Ben Hayes's [`timbre-dissimilarity-metrics`](https://github.com/ben-hayes/timbre-dissimilarity-metrics) library, which packages these 17 (expanded to 21) human listening datasets into a standardized PyTorch evaluation suite.
   - We utilized this suite in `scripts/synth_inversion/timbre_alignment_check.py` to evaluate loss formulations against human perceptual judgments.

2. **Validation of Audio Inversion Loss Formulations:**
   - Single-window STFT and Euclidean spectral losses fail perceptually because they penalize inaudible high-frequency phase shifts equally with gross body resonances.
   - Multi-scale STFT (MSS) and multi-band log-mel L1 perform significantly better because varying window lengths (e.g. 10 ms, 25 ms, 100 ms) implicitly capture multi-resolution temporal rates and spectral scale modulations, aligning closely with human cortical filtering.

3. **Implications for Controllable Generation & LatCH Heads:**
   - Decomposing timbre into isolated scalar hand-crafted features (`rms_energy`, `spectral_flatness`, `spectral_centroid`) replicates the exact flaw of 1970s MDS.
   - A principled alternative for holistic timbre control is a low-dimensional cortical embedding (e.g. PCA or small encoder projecting the STMF or multi-scale modulation tensor into a 16-D latent vector), providing a continuous, perceptually linear timbre manifold without phase artifacts.

4. **Objective Perceptual Sanity Check:**
   - Provides an external, human-grounded metric for checking whether autoencoder latents (SAME, Oobleck), diffusion activations, or JEPA representations ($z_a$) preserve human perceptual timbre geometry.
