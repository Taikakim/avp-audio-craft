# Interval-resolution ladder — "are we even seeing a small second before we update the weights?"

**Kim's question, 2026-08-06.** The melody machinery was only ever *calibrated* on a fifth (7 st).
This places every interval 1–12 st on the same axis as the SAME/MP3 codec-noise floor, in the
SAME latent + the SAME 15-dim subspace the #59 loss upweighted (`lumi/melody_subspace15_v2.npz`).
Source = the clean single-note pitch atlas (`stage1_pitch_atlas_v2.npz`, 10 timbres × 73 pitches) =
the **best-case resolution ceiling**. Controlled design: fix register, vary only the interval,
aggregate over 13 registers × 10 timbres.

## Answer: yes, we see it — the "small second → small signal" premise is FALSE, and that's the finding

| interval | ‖Δz‖ | /fifth | melFrac | SNR vs codec | dirCos | detect |
|---|---|---|---|---|---|---|
| minor 2nd (1 st) | 10.63 | **0.94** | 0.096 | **1.20×** | 0.121 | 0.99 |
| major 2nd (2)    | 11.10 | 0.98 | 0.106 | 1.33× | 0.140 | 0.99 |
| minor 3rd (3)    | 11.19 | 0.99 | 0.108 | 1.34× | 0.162 | 1.00 |
| major 3rd (4)    | 11.24 | 1.00 | 0.105 | 1.31× | 0.147 | 1.00 |
| perfect 4th (5)  | 11.20 | 0.99 | 0.101 | 1.26× | 0.140 | 0.99 |
| perfect 5th (7)  | 11.28 | 1.00 | 0.100 | 1.24× | 0.138 | 0.99 |
| octave (12)      | 11.04 | 0.98 | 0.088 | 1.10× | 0.096 | 0.95 |

Codec floor: magnitude 0.22–0.74× a fifth · melFrac 0.073–0.080 · random melFrac 0.0586.
(detect_acc is in-sample = an upper bound; melFrac/dirCos are unbiased.)

## Three things this settles

1. **A minor 2nd is NOT below the noise floor.** Its latent move is 94% of a fifth's, it's
   detectable, and its melody-subspace share (0.096) beats codec hiss (0.080) and random (0.059).
   The codec does **not** quantize pitch coarser than a semitone — the note-change is visible before
   the weight update.

2. **Magnitude SATURATES — the real surprise.** A semitone ≈ a fifth ≈ an octave in ‖Δz‖ (all ~11,
   6% spread). Euclidean latent distance encodes *"a note changed,"* not *"by how much."* **Melodic
   step-size / contour is not linearly legible from displacement magnitude.** Any metric or loss
   keyed on displacement magnitude (or raw-chroma energy) is contour-blind — which likely poisons the
   whitened-chroma melody-recurrence readout that scored #59.

3. **The #59 target subspace is only weakly melody-selective (SNR ~1.1–1.3× over codec).** A real
   melodic move puts 0.088–0.108 of its energy in the 15-dim subspace; codec fidelity noise puts
   0.073–0.080; random 0.059. So upweighting that subspace (the #59 loss, weight 5) amplifies codec
   hiss almost as much as melody → a low-SNR intervention. **This, not a detectability floor, is the
   probable reason #59 came back weak/inconclusive.**

## Scope caveat (keeps the worry partly alive)

This is the **clean isolated-note ceiling.** The codec floor (0.22–0.74) was measured on **dense real
mixes** (per-frame). A melodic lead buried under bass+pads+drums has a far smaller *effective*
displacement than an isolated note's ~11 — that's where a small step could approach the floor. The
atlas proves the codec *can* resolve a semitone; it does **not** prove a semitone lead survives inside
a full mix. Closing that needs the in-mix version (semitone-shift a melodic stem inside a full mix →
Δlatent), which needs stems/rendering.

## Implications / next moves

- The weak #59 / whitened-chroma null is **confounded**: explained by (a) a contour-blind magnitude
  metric and (b) a low-SNR target subspace — **not** by melody being invisible. Any small-interval
  melody verdict (melody-wall included) inherits (a).
- **(i)** Rebuild the melody subspace to be melody-*selective* — maximize melody-vs-codec-noise
  contrast (LDA/CCA against codec-perturbation directions), not just melody variance — to raise the
  loss SNR. **(ii)** Score melody by contour / pitch-decode, never latent-displacement magnitude
  (which saturates). **(iii)** Run the in-mix floor test to settle scope.

Artifacts: `results.json`, `ladder.png`. Reproduce: `eval/musicology/interval_resolution_ladder.py`.
