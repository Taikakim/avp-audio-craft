# Head A activation-tap ceiling — consolidated verdict (2026-07-23)

(Written by CONTINUITY from summary.json/results.json — the running agent hit a session
limit after its chain completed cleanly, 0 failed cells; numbers verified from artifacts.)

## Layer x t table (test bacc, MLP unless noted; chance 0.125)
t=0.2: L00 .188(lin) L02 .237 L04 .241 L06 .237 L08 .243 L10 .259 L12 .267 L14 .252 L16 .232 L18 .231 L20 .221 L22 .211
t=0.5: peak L10 .256; t=0.8: peak L14 .215. Sequence readout (GRU, best layer): .215.

## The three-experiment verdict on per-frame contour reading
1. LATENT ceiling (head_a_ceiling/): bacc .280 / F1 .273, artist-disjoint, alignment-verified.
2. ACTIVATION ceiling (here): .267 @ L12/t0.2 — mid-stack peaks exactly where the layer
   landscape predicts, but NO lift over latents; temporal integration doesn't help.
3. SYNTH CROSS-EVAL (head_a_ceiling/REPORT.md §SYNTH-XEVAL): corpus-trained head transfers
   to NOTHING (sine = chance; solo .148; mix .243 > solo — OOD asymmetry). CAUTION: this
   does NOT prove representation-limited — earlier IN-DOMAIN probes decode intervals at
   .79-.89 from the same synthetic latents. It proves the readout is DOMAIN-BOUND.

## What we can and cannot conclude
- CAN: shallow per-frame contour readouts on real corpus mixes cap at ~0.27-0.28 with
  everything tried (linear/MLP/context/12 layers/3 noise levels/GRU); the binding failure
  is lead-presence detection; readouts do not transfer across acoustic domains.
- CANNOT: attribute the corpus ceiling cleanly between (a) representation entangling
  voices in real mixes (gm_multifont says mixes are non-additive) and (b) skyline-target
  noise. The experiment that would split them (in-domain training on synthetic mixes) was
  NOT run: either answer leaves the program decision unchanged, so it fails the
  worth-the-tokens bar (Kim's autonomy rule).

## Program consequences (feeds #53 rider spec)
- Head B (forward-conditioned melody FiLM) is THE melody path — unchanged and reinforced;
  it never depended on readability. Its acceptance instrument (chromaturn harness) and
  training-set recipe (font-first sampling; mix-native targets) stand.
- Head A per-frame contour as a z0-side FREE METRIC: not viable (acceptance r=.083).
- Head A's realistic v1 scope: COARSE targets (lead-presence rate, pedal-occupancy)
  possibly trained multi-domain (corpus + synthetic) to break the domain-binding; a
  presence-head is also the cheap detector for the no-lead eval column already shipping.
- Guidance-time contour steering: already closed empirically (chroma turning 0/20).
