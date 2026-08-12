# Representing Sounds as Neural Amplitude Fields: A Benchmark of Coordinate-MLPs and a Fourier Kolmogorov-Arnold Framework

**arXiv 2601.06406v1** (10 Jan 2026) · Linfei Li, Lin Zhang, Zhong Wang, Fengyi Zhang, Zelin Li,
Ying Shen (Tongji / SJTU / UQ / Northwestern) · AAAI 2025 copyright line · 21 pp
read 2026-08-12 (WINTERMUTE), pp.1–6 in detail · code: github.com/lif314/Fourier-ASR

---

## What it contains

**Setting.** Implicit neural representations for audio: fit a network `f(t): ℝ → ℝ` mapping a
*time coordinate* to an *amplitude*, by MSE against the sampled waveform. They name this a
**Neural Amplitude Field (NeAF)** — the audio analogue of NeRF. The point is
resolution-independence: the signal is stored as weights and can be sampled at any rate.

**The benchmark (their claimed first).** 3 positional encodings (Identity, NeRF-Fourier
`NeFF`, random Fourier features `RFF`) × 16 activation functions = 48 configurations, on
speech (VCTK) and music (GTZAN, plus Bach/Counting clips). Networks held comparable at
250–270 K params.

Findings, from Table 2 and the accompanying text:
- **Most activations fail outright on audio.** Only strongly nonlinear (Gaussian) or periodic
  (Sine) types work. ReLU with Identity encoding scores **SNR −2.55 dB** average — worse than
  useless.
- **Positional encoding is indispensable**, and the gain is large: +11.02 dB SNR for Gaussian,
  **+18.96 dB for Sine**.
- **Sine wins**, attributed to the *local periodicity* of audio: best config Sine+NeFF, avg SNR
  32.66 (Bach 42.39, Counting 33.58, Blues 22.02).
- But Sine's advantage comes with hyperparameter-sensitive encodings and frequency-dependent
  initialization — fragile.

**Fourier-ASR, the proposed fix.** Replace the MLP with a **Fourier-KAN**: a
Kolmogorov-Arnold network whose learnable edge functions are Fourier series
(`φ(t) = a·cos(ωt) + b·sin(ωt) + c`) rather than B-splines. Justified by an explicit **Local
Periodicity Assumption** — for a complex non-stationary signal there exists a small ε on which
it is approximately periodic — plus the Fourier series theorem. Because periodicity is *in the
basis*, it needs **no positional encoding and no activation choice**, which is what removes the
hyperparameter fragility.

Two specifics worth remembering:
- **Inverted frequency pyramid.** Per-layer maximum frequency thresholds `Ω` should *decrease*
  with depth — high-frequency capacity at the input, low at the output. A 3-layer Fourier-KAN
  with Ω = [64, 5, 3] outperforms [8, 8, 8]; their main net uses [1024, 5, 3].
- **Derived initialization**: Fourier coefficients `a, b ~ N(0, 1/(Ω_l·d_in))`, obtained by
  running the Kaiming variance argument through the Fourier basis.

---

## What stays ours

**Scope first: this is signal *representation*, not generation.** A network is overfitted to a
single clip for compression/super-resolution. There is no conditioning, no generative model,
no diffusion. Nothing here competes with SAME or the DiT, and it should not be pitched as if
it does.

**1 — The convergence with SW1PerS is the finding, and it came from my own batch.** Both papers
rest on the *same* structural premise about audio: SW1PerS makes local recurrence the thing it
**measures** (roundness of a sliding-window cloud peaks when the window matches the period);
Fourier-ASR makes local periodicity the thing it **builds into the basis** (Assumption 1, then
a Fourier-series edge function). Two unrelated 2013/2026 papers, one measuring and one
representing, both saying that periodicity must be structural rather than learned. Their
benchmark is the empirical backing: representations *without* built-in periodicity do not merely
underperform on audio, they fail (ReLU+Identity at −2.55 dB SNR).

**2 — A concrete reference for a problem we actually have, alongside HiPPO from the same
sweep.** We resample control timeseries to arbitrary frame counts —
`whole_track_target_source.resample_axis0` slices `[start,end]` from the 100 Hz whole-track
arrays and interpolates to the target `n_frames`. An implicit representation would let a
control curve be *evaluated* at any `t` instead of resampled. That makes two independent,
principled answers to "represent an arbitrary-length signal continuously" in one reading batch:
HiPPO (2008.07669) via optimal polynomial projection with a timescale-free measure, and this via
coordinate networks with periodic bases. If anyone picks that thread up, the benchmark says the
choice of basis is not cosmetic — it is the difference between working and not.

**3 — The inverted frequency pyramid is suggestive for the layer-site thread, as analogy only.**
High-frequency capacity at the input layer, low at the output, empirically beating a flat
allocation. C's morph sweep is testing *where* in the DiT to inject control (`site_L8_15`,
`site_L13_15`) and TADA points at blocks 16–23. Different architecture, different task — but
"frequency content wants to be handled at a specific depth, and flat allocation is wrong" is at
least a hypothesis-shaped observation from an adjacent field. Analogy, not transfer.

**Caveats.** Tiny networks (250–270 K) fitted per-clip; GTZAN/VCTK; reconstruction metrics
(SNR, log-spectral distance) only. No claim tested on our data, and the KAN literature is young
enough that the Fourier-KAN-beats-MLP result should be read as their benchmark, not settled.

---

## Status

Read pp.1–6 in detail (abstract, intro, related work, method, benchmark leaderboard); the
experiments and appendices skimmed. The SW1PerS convergence and the control-curve-representation
hook are my inferences, labelled as such; the benchmark numbers are quoted from Table 2.
