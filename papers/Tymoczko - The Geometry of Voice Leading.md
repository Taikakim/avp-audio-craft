# Tymoczko — The Geometry of Musical Chords / Voice Leading

*Project-POV abstract, CONTINUITY 2026-08-12 (reading-sweep 3/5; deep-read — the file is the *Science* 2006
"Geometry of Musical Chords," the foundational orbifold paper behind Tymoczko's voice-leading geometry).
The **polyphonic/harmonic-movement** complement to Polansky contour (single-voice) + path signatures (path).*

## What it contains
Chords live in a geometric space; **voice leadings are paths in it**.
- **Pitch** = real number `p = 69 + 12·log₂(f/440)` (log-frequency: semitone 1, octave 12). **Pitch class** =
  the circle `ℝ/12ℤ` (chroma). Chords = **multisets** of pitch classes.
- The music operations ARE geometric transforms: **transposition = translation** (add mod 12), **inversion =
  reflection**, **permutation = reorder**. The space of n-note chords = the **orbifold `Tⁿ/Sₙ`** (n-torus mod
  the symmetric group), with **singular mirror boundaries** where notes coincide. `T²/S₂` = a **Möbius strip**.
- **Efficient (short) voice leadings exist only between NEARLY-SYMMETRIC chords** (near T-symmetric = divide
  octave evenly / P-symmetric = duplicate notes / I-symmetric = reflection-invariant).
- **Consonance ↔ geometry:** acoustically consonant chords (≈ harmonic-series segments) divide the octave
  **nearly evenly** → cluster at the **CENTER** of the orbifold → linkable by efficient voice leading. *This
  is why Western counterpoint works.* (Cites **Sethares** for acoustic consonance — my #5.)
- **Two unifications flagged as extensions:** cyclic **RHYTHMS are points on the SAME `Tⁿ/Sₙ`** (rhythm and
  harmony share the geometry); and **orbifold distance ↔ perceptual chord-similarity judgments**.

## What this gives us / what stays ours
- **Grounds the chroma representation in real geometry.** Our 12-bin chroma IS a distribution on Tymoczko's
  pitch-class circle `ℝ/12ℤ`; **transposition = rotation of that circle** → the transposition-INVARIANT
  reduction is the **DFT-magnitude on the circle** (= the chroma-DFT / Tonal-Interval-Vector idea), now with a
  first-principles geometric justification, not just a trick.
- **The invariance dial, as a geometric QUOTIENT** (the deepest version of the theme): mod translation =
  transposition-invariant; mod reflection = inversion-invariant; mod permutation = chord-not-sequence. Choose
  the invariance by choosing the quotient — the same choice Polansky makes with n-ary, chroma makes with
  raw↔whitened, signatures make with augmentations.
- **A principled consonance measure** = distance-from-even-division-center. Bridges directly to **Sethares
  (#5)**: Tymoczko = even-division/log-frequency consonance; Sethares = spectral/roughness consonance —
  two theories to reconcile (Tymoczko even cites him). Candidate: a geometric "harmonic tension" control/eval
  signal (distance from orbifold center).
- **Voice-leading distance = a harmonic-MOVEMENT metric** — the minimal voice leading (short orbifold path) =
  "how far the harmony moved," a candidate control target / a2a eval (did the progression's voice-leading
  survive). The **rhythm=harmony** unification hints onset-control + chroma-control could share a geometry.
- **STAYS OURS / caveats:** Tymoczko's objects are **symbolic** (discrete pitch classes, chords as multisets,
  explicit voices) → directly usable for **MIDI/symbolic** conditioning; for our **continuous** chroma the
  usable form is the pitch-class-circle + DFT-magnitude (voices aren't explicit, so voice-leading distance
  needs a voice-assignment or a continuous optimal-transport analog on the circle). Descriptive geometry, not
  learned — but the circle+DFT part is differentiable.

**knowledge.md row** (hand to F): *Tymoczko, Geometry of Musical Chords (Science 2006) — chords = points in an
orbifold `Tⁿ/Sₙ`; voice leadings = paths; transposition/inversion/permutation = translation/reflection/
reorder; consonance ↔ near-even-division ↔ orbifold center (cites Sethares). FOR US: geometric grounding of
the chroma pitch-class circle `ℝ/12ℤ` and transposition-invariance-as-rotation (→ chroma-DFT/TIV justified);
invariance-dial as a quotient choice; voice-leading distance = harmonic-movement metric (symbolic/MIDI-native,
continuous-chroma needs OT analog); rhythm=harmony on the same orbifold. Complements Polansky contour +
signatures.*
