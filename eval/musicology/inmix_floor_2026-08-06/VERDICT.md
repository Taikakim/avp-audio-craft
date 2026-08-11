# In-mix semitone floor test — does a small second survive inside a full mix?

**Kim 2026-08-06.** The atlas ladder was the clean isolated-note ceiling; the open caveat was
whether a semitone melodic move survives above the codec floor once the lead is buried in a dense
mix. Test: real multitrack (**No Doubt – Don't Speak**, 5 **leaf** stems, no bus/group-mix summed),
transpose ONLY the vocal (the melody) with **bungee** (never sox), reconstruct the mix, SAME-encode.
Window: 86.0s + 23.8s (vocal RMS 0.26 over band 0.096 — prominent lead, full band). Codec floor arm =
the same mix through mp3@256 → back.

| arm | frame Δ | / fifth (calib) | / fifth (in-mix) | melFrac |
|---|---|---|---|---|
| **vocal +1 semitone** | **12.38** | 2.19 | **0.87** | 0.112 |
| vocal +7 (fifth) | 14.24 | 2.52 | 1.00 | 0.087 |
| **mp3@256 codec noise** | **0.97** | 0.17 | 0.07 | 0.087 |

*(refs: isolated-note fifth calib 5.64 · random melFrac 0.059 · mp3@256 codec melFrac 0.073)*

## Verdict: YES — a semitone survives in-mix, decisively

- **Magnitude SNR (semitone ÷ codec noise) = 12.7×.** A +1-semitone melodic move on the vocal, at a
  natural mix level, moves the SAME latent ~13× more than the codec's own fidelity noise. The
  "buried lead could sink below the floor" worry does **not** materialize here — there is ~22 dB of
  headroom, i.e. the lead would have to drop ~20 dB below its current level before its semitone move
  reached the codec floor. The codec clearly registers the note-change before the weight update.

## But both structural findings from the atlas HOLD in real material

1. **Magnitude still saturates in-mix:** semitone = **0.87×** a fifth's ‖Δ‖ (atlas isolated = 0.94).
   Displacement magnitude encodes "the melody changed," not "by how much" — contour/step-size is not
   legible from ‖Δ‖, in a real mix too.
2. **The #59 melody subspace is only ~1.3× melody-over-codec-noise in-mix** (semitone melFrac 0.112
   vs codec 0.087 vs random 0.059). Weakly selective in real material — the same low-SNR lever the
   atlas exposed, and the probable reason #59 came back weak.

## So the full answer to "are we even seeing a small second before we update the weights?"

**Yes — clean-note AND in-mix, a small second is a large, well-above-floor latent event; the
"small signal we might miss" premise is false.** The melody-wall / #59 weakness is NOT a
detectability floor. It is (a) a magnitude metric that is contour-blind (saturates), and (b) a target
subspace that is only ~1.3× melody-over-noise. Fixes: rebuild the subspace to be melody-*selective*
(LDA/CCA against codec-noise directions), and score melody by contour/pitch-decode, never ‖Δ‖.

## Caveats
- Vocal at a prominent level (not deeply buried); the 12.7× headroom implies survival until ~20 dB
  quieter, but a very-low goa synth line under a loud kick/bass could sit closer to the floor.
- Whole-phrase transpose (includes vocal↔backing harmonic clash) — the maximal-signal version of "a
  semitone melodic change"; a single-note change is smaller but recoverable on its own frames.
- Pop/rock vocal as a monophonic-melody proxy (no goa multitrack on hand); codec floor is
  genre-agnostic and the headroom is large.

Reproduce: `inmix_stage1_build.py` (mir/pitch_venv) → `inmix_stage2_encode.py` (.venv, GPU).
Artifacts: `mix_{orig,min2,fifth,codecnoise}.wav`, `results.json`.
