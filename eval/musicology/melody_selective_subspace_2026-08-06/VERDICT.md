# Melody-SELECTIVE subspace rebuild (whitened CSP) — the lever both floor tests pointed at

**Kim 2026-08-06.** The interval-ladder + in-mix floor tests showed we DO see a small second before
the weight update — the #59 weakness is not a detectability floor but (a) a contour-blind magnitude
metric and (b) a target subspace only ~1.3× melody-over-codec-noise. This rebuilds (b): a basis
chosen to be melody-**selective**, not high-melody-**variance**.

## Method — whitened CSP
- **signal** S = clean atlas interval deltas z(p+k)−z(p), k=1..12, all registers/timbres.
- **noise** N = real codec deltas z(mp3@{320,256,192,128}) − z(flac) on 15 goa tracks × 256 frames,
  **plus** timbre deltas (melody must be timbre-invariant too).
- whiten by N (shrinkage γ=0.1), take the top-15 signal-variance directions in the noise-whitened
  space, map back + orthonormalise. Built on TRAIN timbres/tracks, validated on HELD-OUT ones.

## Result — held-out (never-seen timbres + tracks)

| subspace | melFrac melody | melFrac codec-noise | SNR |
|---|---|---|---|
| old v2 (#59, variance) | 0.100 | 0.100 | **1.00×** |
| **new v3 (selective)** | 0.080 | **0.016** | **5.11×** |
| random 15-d | 0.057 | 0.050 | 1.14× |

The old subspace has **no** selectivity on held-out data — codec noise lands in it exactly as much
as melody (1.0×). The new one keeps melody (0.080, still 1.4× random) while pushing codec noise
*below* random (0.016) → **5.1× melody-over-noise**. Per-interval (held-out timbres) the new basis
stays melody-responsive down to a minor 2nd (0.065) — it doesn't win by going blind to small steps.

## Reading + caveats
- The win is **noise REJECTION**, not higher melody capture (melody is near-full-rank, so no 15-d
  basis captures a large fraction — old 0.10, new 0.08, random 0.057). Upweighting error in v3 hits
  melody error ~5× more than codec-noise error; upweighting v2 hit them equally. That is exactly the
  #59 lever, fixed.
- Prototype knobs to tune before committing compute: shrinkage γ, k (15 for drop-in), and folding
  **in-mix** melody deltas into S (currently isolated-note atlas only).
- This is a basis-quality result. The real proof is a **training A/B**: subspace-loss with v3 vs v2
  vs baseline on melody outcomes — needs a LUMI submit.

## Output
`lumi/melody_subspace15_selective_v3.npz` {basis15 [15,256], ev15, provenance} — **drop-in** for
`--subspace-loss-basis` (same schema as melody_subspace15_v2.npz). Reproduce:
`eval/musicology/build_melody_selective_subspace.py`.
