# Weight-garden audition notes (qualitative catalog)

*Kim's ear-verdicts on weight-mutation renders, paired with recipe + CONTINUITY's
mechanistic read. Recipes are in each dir's `run_meta.json`; this is the perceptual
layer that machine sidecars can't hold. Growing catalog — the "interesting" ones
first; the failed/neutral ones are a TODO (Kim, 2026-07-06: "should one day
qualitatively address the failed ones too").*

> Reproducibility note: filenames carry the audio GENERATION seed (s1234/s4242);
> the tour's MUTATION seed is fixed at 1234. Same mutated model, different sampling.

## The keepers so far

### shuffle (value-preserving permutation) — the "rewired mind" family
Shuffle permutes a fraction of weight entries among themselves; the weight multiset
is unchanged, only the wiring moves. Statistically on-manifold → sounds MUSICAL, not
noisy (unlike the value-changing ops). Intensity is a dial:

- **explore1 / `shuffle_05`** (amount 0.05, target all, decay late r0.3, mut-seed 777) —
  **goa + ambient, gen-seed 1234.** Kim: "evolved to new musical forms compared to
  baseline… the melody changed" (rhythm TBD in a DAW), no noise/artifacts. → the
  strongest garden result; 5% rewiring changes the *form*.
- **tour / `shuffle`** (amount 0.02, target all, decay late r0.5, mut-seed 1234) —
  **goa, gen-seed 4242.** Kim: "some potential, a bit different dynamics, very slight
  timbre change." → the gentler 2% version: character/dynamics shift, not yet new
  melody. Corroborates shuffle-amount as a musical intensity dial (2% subtle → 5% new form).

### tour / `blur_attn` — temporal smearing, "dried" transients
Recipe: blur amount 0.5, **target = attention only**, decay late r0.3, mut-seed 1234 —
**goa, gen-seed 4242.** Kim: "sounds different, not just a sheen of noise — a slightly
DRIED sound, like a slight transient filter compressing down the decays; timbre
changed slightly at the instrument level; pitch maybe decreased a bit."

Mechanism (CONTINUITY): blur low-passes/smooths adjacent weights; applied to the
ATTENTION matrices it smooths the attention pattern → less selective, fuzzier temporal
focus. Attention carries temporal relationships (which frames attend to which), so
blurring it should soften transients and compress decays — which is exactly the "dried
/ transient-filtered decays" percept. The instrument-timbre and slight pitch drift fit
attention also carrying some relational/harmonic info. **Notable:** this is mild
evidence FOR the attn ≈ time/structure hypothesis (blurring attn hit TIME) — which the
shuffle_05 melody-change result had complicated. The layer×feature probe
(`latch/probe_layer_feature_map.py`) is what will settle it: if onset/beat features
localize to attention layers, this percept has its mechanism.

## TODO (Kim, when time allows)
- Qualitative pass over the failed/neutral mutations (drift/contrast/tilt/life at
  various settings) — for completeness, so the catalog covers the whole palette, not
  just the wins.
