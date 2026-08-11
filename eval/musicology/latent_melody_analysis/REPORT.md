# Where (and how linearly) is melody encoded in the SAME latent space?

**Date:** 2026-07-22 · **Analysis:** CONTINUITY (melody-encoding study)
**Purpose:** locate melody/pitch in the SAME (medium-base pretransform) 256-ch latent
(10.7666 Hz) using controlled fluidsynth renders with exactly-known note grids, to
ground the melodic-LatCH design (`docs/superpowers/specs/2026-07-22-melodic-latch-film.md` §7 P3)
and the "does training hear melody" gradient-share question.
**Inputs:** `eval/musicology/test_midis/` (13 MIDIs, manifest.json = ground truth) ×
5 timbres = 65 renders → latents in `eval/musicology/test_midis/latents/*.z0.npy`
(fp16, [256,T]; encoder: `encode_test_midis.py`, pretransform-only load).
**Code:** `analyze_melody_encoding.py` · **Numbers:** `results.json` ·
**Intermediates:** `stage1_pitch_atlas.npz`, `stage3_fifthjump.npz`, `stage4_subspaces.npz`.
Alignment verified: first-note audio onset at 0.023 latent frames; 16th @161.499 BPM = exactly 4096 samples = 1 frame.

---

## (a) Where does melody live? — Distributed, not channel-local

- **No pitch channel exists.** Best single-channel linear R² against MIDI pitch
  (73-note chromatic sweep, C2→C8): 0.35–0.48 depending on timbre; **zero channels
  reach R² 0.5**. Median channel R² ≈ 0.02–0.05.
- **But pitch is very decodable from the full space**: ridge decode of pitch from all
  256 channels, leave-one-out: **R² 0.86–0.97 per timbre**, 0.87 pooled across timbres.
- Cross-timbre *consensus* channels exist but are weak individually (ch 221 best:
  min-across-timbres R² only 0.20; then 53, 203, 227, 41, 20, 151, 102, 50, 46).
- The fifth-jump signature (below) needs ~120 channels for 90% of its energy.
- ANOVA (6 patterns × 5 timbres × 32 bar-replicates): only **2/256 channels are
  pattern-dominant** vs **171/256 timbre-dominant** (frame-averaged). Melody never
  owns a channel; it owns a **subspace**.
- **Melody subspace dimension: ~15** (PCA of timbre-averaged pattern×bar-phase
  trajectories reaches 90% var at 15 comps, 95% at 20; top EV 0.30). For contrast, the
  static timbre subspace is ~3–4 dims for the 5 patches (top EV 0.55).
- Caveat: the 73-slot pitch manifold itself is **high-dimensional as a curve** — PCA of
  the sweep slot-vectors needs 37–44 comps for 90% var. Pitch is a low-dim *readout*
  (linear decode works) living on a high-dim, curved *trajectory*.

## (b) How linear is pitch encoding? — Linear readout is ~all you get; curvature is mild

Per-channel fits on the top-10 pitch channels: quadratic adds ≈0.00–0.09 R² over
linear; per-octave broken-stick adds ≈0.02–0.09. E.g. sawlead ch102: lin 0.482 /
quad 0.491 / octave-broken 0.509; piano ch118: 0.385 / 0.471 / 0.480. So there is
**mild octave structure and saturation, but no strong nonlinearity** at the channel
level; the multivariate **linear** decoder already reaches R² 0.87–0.97. A linear
probe on z0 is the right first tool; nonlinear heads buy little for pitch *level*.

## (c) The interleaving verdict (Kim's core question) — **Superposition, not snapping — but noisy**

Setup: pat2 (E3/G3 alternating 16ths) at BPM 143, where a 16th = 1.129 frames and note
boundaries drift through frame phase. Each frame classified by exact E/G overlap
fraction; pure-E and pure-G frame centroids define an axis; boundary frames projected.

- **Boundary frames land *between* the two note centroids in proportion to overlap**:
  regression slope of projected-vs-true mix fraction ≈ **0.91–1.06** for sawlead,
  squarelead, piano, strings (churchorgan the exception, 0.54). Unbiased linear mixing.
- **No snap-to-one-note**: the distance to the α-interpolated point equals the distance
  to the nearest endpoint (ratio ≈ 1.00 ± 0.02, both full-space and in the 28–96
  discriminative channels); the projected distribution is not bimodal.
- **But it is noisy**: R² of the per-frame mix estimate is 0.44–0.56 (saw, piano) down
  to 0.17–0.19 (strings, square) and 0.03 (churchorgan); boundary frames sit ~5–15%
  farther off-manifold than pure-frame scatter (resid/scatter 1.02–1.15).
- Control: in the frame-locked file the same E/G axis separates the two notes at
  **d′ ≈ 6–8** — the noise above is genuinely sub-frame mixing noise, not axis weakness.

**Verdict: a frame covering two interleaved 16ths encodes an approximately linear
superposition (weighted by temporal overlap) of the two single-note codes — the codec
does not quantize a boundary frame to one note — but a single boundary frame is an
unreliable (R²≈0.2–0.6) witness of the mix ratio.** Sustained/overlapping timbres
(church organ) degrade to unreadable at frame scale.

Frame-lock confirmation (locked files, latents projected on the pooled pitch axis):
pat2 shows a clean period-2 ACF comb (+ at even lags, − at odd), pat3 a period-4 comb
(lag4 +0.37, lag8 +0.71), exactly the ground-truth periods. NOTE: the *raw* latent ACF
is instead dominated by a pitch-independent ~1.30 Hz (≈8.3-frame) oscillation present
even for constant-pitch pat1 (0.40 Hz for the two lead patches) — a synth/LFO-scale
amplitude artifact, ~12–16% concentrated in its top-5 channels. Any frame-level melody
probe should expect strong non-melodic slow structure in the same latents.

## (d) Fifth-jump (pat5): a single deviant 8th is robustly, redundantly encoded

- The B3 jump frames (bar phases 8–9) are separated from the E3 pedal distribution at
  **100.0% balanced accuracy (LDA) for all 5 timbres**.
- z-scored distance profile across the 16 bar phases: flat ≈1.0 everywhere except
  exactly phases 8–9 (1.15–1.85×) plus a release-bleed at phase 10 (piano 1.24).
- Effect is **distributed**: 33–82 channels with |Cohen's d| > 1; ~120 channels needed
  for 90% of the Δμ energy. Not sparse.
- **Direction is timbre-specific**: mean cross-timbre cosine of the jump direction is
  only **0.27**. The *event* is always encoded; the *direction* it moves the latent in
  depends on the patch.

## (e) Timbre invariance — partial: a shared pitch subspace exists but is a minority component

- Single-timbre pitch decoders **do not transfer** (mean cross-timbre transfer R² =
  −0.09; sawlead→piano −2.25). Per-timbre pitch weight vectors agree only at cos ≈ 0.41
  (per-channel correlation profiles cos ≈ 0.46).
- Yet a **pooled decoder generalizes to a held-out timbre**: leave-one-timbre-out
  R² = 0.65–0.79 (mean **0.74**). So a timbre-invariant linear pitch subspace exists,
  but each timbre also carries larger timbre-specific pitch correlates that a
  single-timbre fit latches onto.
- Frame-wise decoding of fast material inherits the attack profile: the sweep-trained
  decoder tracks the pat3 arp (1 note/frame) for sawlead/squarelead/piano
  (corr 0.54–0.63, correct ordering) but fails for strings (−0.21) and churchorgan
  (−0.59) — slow attack + sustain means a frame's content is not the frame's note.

## Variance fraction / "does training hear melody"

On these renders (30 locked files): **melody variance** — the timbre-shared, time-resolved
pattern trajectory — is **19.7% of total latent variance**; static timbre offsets are
24.8%; the rest is interaction + bar-to-bar/residual. In pure pattern-identity ANOVA
terms melody is only 6–8%. Projected onto real corpus latents (22 files from
`/home/kim/Projects/latents_sa3`): the 15-dim melody subspace captures **8.5%** of
corpus latent variance vs 5.9% for a random 15-dim subspace (≈**1.45× enrichment,
~0.085 variance fraction**). **RF training pressure on melody-aligned directions is
real but small — roughly a twelfth of the gradient's variance budget** — consistent
with the working hypothesis that melody is under-weighted in the RF loss and a
melody meter/head adds information the loss barely sees (meter-in-the-gradient scope
rule, MASTER §4: use meters for what RF can't see — melody timing/identity qualifies).

## Implications for the melodic LatCH head (spec §7 P3)

1. **Linear, full-width probe**: read pitch from all 256 channels; channel selection is
   futile (nothing is sparse) and a linear layer already gets R² ~0.9.
2. **Train multi-timbre from day one** — a probe fit on narrow timbre data learns
   non-transferable directions (transfer R² < 0!). The pooled/LOTO result (0.74) is the
   realistic timbre-general ceiling for a *linear* frame-level readout; a small MLP +
   temporal context should close the gap to per-timbre performance (0.86–0.97).
3. **Frame-rate melody supervision is legitimate**: at 161.5 BPM-equivalent note rates
   the latent is note-periodic (clean ACF combs) and a deviant single 8th is 100%
   detectable; 1-frame notes are readable for sharp-attack sources.
4. **Sub-frame boundaries: use soft targets.** Boundary frames are ~linear overlap
   mixtures — supervise with overlap-weighted chroma/pitch labels rather than nearest
   note snapping; that matches what the codec actually stores.
5. **Expect smearing for slow-attack material** — supervision should weight note
   *centers* (or ≥2-frame notes) and/or provide ±1-frame context; strings/organ-like
   sustains are not frame-decodable.
6. **De-noise slow oscillations**: a pitch-independent 0.4–1.3 Hz latent oscillation is
   a dominant raw-variance component; high-pass or learned temporal filtering will
   raise probe SNR.
7. **Gradient share ~8.5%** supports adding an explicit melodic loss channel (FiLM head
   or meter) rather than trusting RF to allocate attention to melody.

## Caveats

- fluidsynth pitch sweeps confound pitch with register brightness/energy (inherent).
- Monophonic single-patch renders; polyphony/mixtures untested (the interleave test is
  the closest proxy — it supports linear mixing).
- fp16 encode, single pass; slot readout uses the 2nd frame of each sweep slot to dodge
  onset transients; locked analyses use frames 0–511 (release tail excluded).
