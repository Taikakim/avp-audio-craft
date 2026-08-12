# SigDiffusions: Score-Based Diffusion Models for Time Series via Log-Signature Embeddings (2406.10354)

*Project-POV abstract, CONTINUITY 2026-08-12 (reading-sweep 2/5; deep-read full PDF). Barancikova, Huang,
**Salvi** (Imperial College; ICLR 2025). The **generative** sibling of 2006.00873 — diffusion in signature
space. "Our exact model class" (score-based diffusion) applied to the movement encoding.*

## What it contains
Score-based diffusion that operates on **log-signature embeddings** of a timeseries instead of the raw
series. Pipeline (all deterministic except step 3): (1) step-N signature of the series (closed-form,
Chen's relation); (2) tensor-log → **log-signature**, which lives in the **Lie algebra ℒⁿ(ℝᵈ) ≅ a flat
Euclidean space ℝ^β(d,n)** — so standard diffusion machinery "just works" there; (3) train a plain
score-SDE (transformer + sinusoidal-t) on the log-sigs; (4) sample → synthetic log-sigs; (5) tensor-exp →
signatures; (6) **invert signature → timeseries**.
- **Main technical contribution = closed-form signature INVERSION.** They prove the Fourier / orthogonal-
  polynomial expansion coefficients of a path are explicit **linear functionals on the signature** (=
  polynomial functions of the log-sig). This replaces the previously-hard inversion (Insertion = non-scalable;
  optimization = slow; evolutionary = no guarantees). Time complexity `O(n·d^{n+2})`.
- **Truncation level N = the fidelity/capacity dial:** low N captures overall shape + smooths hi-freq noise;
  high N = detail but exponentially bigger log-sig and *harder to generate* (Fig 4 shows the trade-off).
- **Results:** competitive/SOTA on length-**1000** timeseries generation (Sines, Predator-prey, HEPC,
  Exchange, Weather) at **dramatically smaller+faster models** (200–280K params & 8–12 s sampling vs DDO's
  4.1M & 42 min). The compact flat log-sig embedding is *why* generation is efficient.

## What this gives us / what stays ours
- **A cheap, principled GENERATOR of a low-d movement signal.** Diffuse in the log-sig space of a melodic
  trajectory → invert → a melody with target movement. This is the generative counterpart to the
  signature-as-control-FEATURE idea (2006.00873): a small SigDiffusion could **generate a melodic-contour
  skeleton to condition the audio DiT on** (Zach's prepend-cond needs a source signal — this could *be* it),
  or serve as a movement-prior in guidance. 200K params / seconds → basically free as a side model.
- **`N` = the resolution dial again** (Polansky n-ary; raw↔demeaned↔whitened; signature depth). Same theme.
- **The closed-form inversion formulae are a reusable GEM beyond this paper.** If we ever hold a target in
  signature/whitened space and must map back to a real chroma/latent trajectory (the **de-whitening** step we
  discussed), signature-inversion is the tool — Fourier/orthogonal-poly basis, exact, `signatory`-adjacent.
- **STAYS OURS / caveats:** (1) `β(d,n)` log-sig dimension blows up with channels `d` AND depth `n` → same
  constraint as 2006.00873: works on a **low-d, smooth-ish** stream (their examples d=1–8, N=4), NOT the raw
  256-d SAME latent, and **hi-freq content needs high N = hard to generate** (Fig 4) — a melodic *pitch/
  contour* trajectory (low-d, smooth) fits; audio-rate latents don't. (2) It generates the SIGNAL, it does
  not condition the audio model — so it's a **2nd-wave** idea (a movement-source generator), not the immediate
  control-head sweep. (3) Future-work note flags **discrete-time signatures** for symbolic sequences — a lead
  if we go MIDI/symbolic-conditioning.

**knowledge.md row** (hand to F): *SigDiffusions (2406.10354, Salvi/Imperial, ICLR'25) — score-based diffusion
in log-signature (flat Lie-algebra) space + NEW closed-form signature→timeseries inversion (Fourier/orth-poly
coeffs = linear functionals on the sig). Generates length-1000 TS at 200K params/seconds. FOR US: generative
sibling of 2006.00873 — a cheap generator of a LOW-d melodic-movement skeleton to condition on (Zach
prepend-cond source), N=resolution dial; the inversion formulae = a reusable de-whitening/decode tool. Caveat:
low-d/smooth only (β(d,n) blowup), raw 256-d latent out; 2nd-wave.*
