# Windowed descriptor time-series — design (Kim 2026-07-10)

*Kim's ask: "time series data of my rhythmic and melodic descriptors like
rhythmic_complexity_drums, harmonic_variance_bass… if they need a window, save
as windows, and at training choose stepped or smoothed series, i.e. 32 steps per
4096 latent. There must be a mathematical way to set this up. Every feature the
MIR project extracts should eventually be feasibility-tested on LUMI (FiLM/LatCH
+ paradigms we haven't looked at), and the book double-checked for recipes."*

## The key insight — no audio pass needed for most of them

The whole-track npz (21 fields @ 100 Hz: per-stem onset envelopes, beat/downbeat
activations, hpcp, per-stem + multiband RMS, spectral stats) already carries the
PRIMITIVES these descriptors are computed from. A windowed descriptor series is a
**sliding-window functional over an existing 100 Hz primitive**:

    D[i] = f( primitive[ i·H : i·H + W ] )        i = 0 … (N−W)/H

pure numpy over the npz — cheap, resumable, no stems re-read, LUMI-trivial.

| descriptor series | primitive(s) in the npz | f (per window) |
|---|---|---|
| `rhythmic_complexity_{drums,bass,other}_ts` | `onset_envelope_<stem>_ts` | peak-pick → IOIs → entropy/CV (the exact functional `rhythm/complexity.py` uses) |
| `rhythmic_evenness_<stem>_ts` | same | regularity = 1/CV of IOIs |
| `syncopation{,_drums,_bass,_other}_ts` | `onset_envelope_<stem>_ts` + `beat_activation_ts` | off-beat onset mass vs beat grid (`rhythm/syncopation.py` functional) |
| `onset_density_<stem>_ts` | `onset_envelope_<stem>_ts` | peaks / window-seconds |
| `harmonic_movement_ts` | `hpcp_ts` | mean ‖Δchroma‖ across window frames |
| `harmonic_variance_ts` | `hpcp_ts` | mean per-bin variance |
| `on_beat_ratio_ts`, `ioi_{mean,std}_ts` | envelopes + beats | direct |

**Gap:** per-stem *harmonic* series (`harmonic_variance_bass_ts`) need per-stem
chroma, which the npz lacks. Two options, in preference order:
1. **SAME 3-octave-band chroma** (the 384-d readout's bands ≈ bass/mid/high) —
   already computable per crop from latents (`extract_same_chroma_targets.py`),
   the bass band is a serviceable bass-chroma proxy, zero audio.
2. Add `hpcp_<stem>_ts` fields to the whole-track producer (audio pass over the
   existing stems; fold into the next producer run / the LUMI clean-room regen).

## Window math + storage (the "mathematical way")

- **Window/hop:** descriptor-dependent defaults, stored per field. Rhythm
  functionals need ≥ ~4 bars of context → `W = 8 s`, `H = 1 s` (matches the
  validated recurrence-meter geometry). Harmonic ones are stable at `W = 4 s`,
  `H = 1 s`. Series rate = 1/H = 1 Hz — ~380 values per 380 s track.
- **Storage:** same npz, new fields, each with its own rate in `__meta__`
  (`{field: {"rate_hz": 1.0, "window_sec": 8.0}}`). The existing consumer
  (`whole_track_target_source.resample_axis0`) is already rate-agnostic — it
  slices `[start,end]` in seconds and resamples to any target T.
- **Stepped vs smoothed = a CONSUMER choice, not two stored copies.** For a
  4096-frame latent window and a requested `n_steps` (e.g. 32):
  - *stepped:* nearest/zero-order hold — `D_step(t) = D[⌊t·n_steps/T⌋]` →
    piecewise-constant target, 32 plateaus per window.
  - *smoothed:* linear (current `resample_axis0`) or Hann-kernel interpolation
    to full T — continuous target.
  One `mode={"hold","linear","hann"}` + `n_steps` kwarg on the target source
  covers Kim's "32 steps per 4096, or something" exactly, and the tolerance
  window from the chroma work (`w_sec`) is the same dial in loss space.
- **Guidance caveat (today's lesson):** piecewise-constant targets are fine for
  *training* heads, but scalar-constant GUIDANCE failed quality gates for a
  possibly Jacobian-shaped reason — when these series reach guidance, prefer the
  smoothed mode first and always run the CE/PQ/ZCR gates.

## The LUMI feasibility matrix (every feature × every paradigm)

Extends Campaign A (`lumi/sbatch/latch_all_features.sbatch`) from 20 fields to
20 + ~14 windowed-descriptor fields, each tested per paradigm:

1. **LatCH guidance head** (existing trainer; the encodability screen
   (`stats/latent_dim_feature_xcorr.csv`) predicts viability BEFORE training —
   run the screen on the new fields first, expectation-order the array).
2. **FiLM / control-adapter conditioning** (the `sa3_control` decoupled
   cross-attn path — works even where guidance is dead, cf. onset).
3. **Meter-in-the-gradient (FusionCC)** — only where the RF loss can't see the
   attribute (MASTER §4 scope rule).
4. **Paradigms not yet tried** (from TADA + the Sourcebook): *training-free
   CAA/activation steering* at the functional layers (cheapest possible
   baseline — the layer map says late self_attn/ff for acoustic attributes);
   *local_add_cond dense conditioning* (Music-ControlNet/MuseControlLite path,
   Sourcebook ch8/11) for time-dense series; *noise-band-scheduled variants*
   (Axis-2) per attribute family.
5. **Book pass:** THE-FINN sweeps `CONTROL_METHODS_SOURCEBOOK` for recipe
   insights per feature family (rhythm/harmony/timbre/dynamics) — deliverable:
   a per-family "recommended first paradigm" column for the matrix.

## Division + order

- W: this doc; the extractor (`mir/src/spectral/windowed_descriptors.py`, numpy
  post-processor over existing npz) + consumer `mode`/`n_steps` kwargs; the
  encodability screen over the new fields.
- F: the Sourcebook recipe sweep (column 5).
- C: paradigm notes from the control-adapter side; sanity on functional
  equivalence (windowed f == the scalar f on full-crop windows — the unit test).
- LUMI: the matrix IS the first big campaign after the rarity job — budget est
  after the screen prunes dead rows.
