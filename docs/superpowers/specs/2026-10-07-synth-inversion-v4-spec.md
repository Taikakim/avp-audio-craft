# Synth inversion v4 — compact spec (2026-10-07)

Owner while W is out of tokens: Kim + Kuang. Code: `stable-audio-tools/scripts/synth_inversion/` (branch
`feature/surge-xt-neural-inversion`, remote `avp`). Background: EXPERIMENTS.md H1/H4/H6, the "renderer bug" and
"v3 clean retrain" entries; MASTER section 5 (Surge FX mix-0 gotcha); docs/TRAINING.md (read before launching).

## 0. Why v4
- The 23-param space (one oscillator, one filter, AEG/FEG, waveshaper subset) cannot express how real basses are
  built (Kim's Bitwig audit, 2026-10-07): filter feedback, dual filters, Osc 2 sub/unison layers, FEG -> pulse width,
  phase retrigger, analog envelopes.
- v3 (FX truly off, cond-noise flow, MAE) finishes ~2026-10-08 10:30; its real-stem result decides how much of the
  gap the recipe closes inside the old space. v4 keeps whatever v3 shows works and widens the space.

## 1. Renderer: native `surgepy` (`/home/kim/Projects/surge/build/src/surge-python/`)
Replaces pedalboard. Accept it only after these pass (write them as tests, not checks by eye):
1. **FX off is really off:** with FX disabled, one 8th note's tail falls below -60 dB within 0.4 s (no repeats).
   Re-use `test_fx_off_single_note_has_no_delay_trail` logic.
2. **No state between renders:** a reference patch renders identically (mel L1 below repeat noise) before and
   after 20 unrelated random patches, including ones with FX on.
3. **Preset round trip:** export -> load in a FRESH instance -> every parameter equal and the render equal. The
   pedalboard exports failed this (FX showed the init preset's chorus 100% / delay 50% while the live state was Off).
4. **Speed:** renders/s per CPU worker at least equal to pedalboard (training is render-bound on CPU).

## 2. Parameter space (all within preset-derived bounds; Kim's 13 presets add to them, never replace)
Bounds source: the existing manifold (`real_bass_manifold.npz`, preset-derived) UNION the 13 hand-made presets
`~/Documents/Surge XT/Patches/AI Inversions/kim_bass_*.fxp`. The 13 also enter the prior as extra archetypes.

| Group | Parameters | Notes |
|---|---|---|
| Oscillators 1-3 | type, mute, volume, octave, pitch, shape/width/sub/sync per type, unison voices + detune | type-specific params are only active for that type |
| Osc routing | route to filter 1 / 2 / both; ring mod 1x2, 2x3 (mute, volume, route) | |
| Phase | retrigger on gate (on/off) | Juno punch vs free-running for detuned stacks |
| Filters 1-2 | type (all LP types, others if presets use them), cutoff, resonance, keytrack, FEG amount | |
| Filter config | routing template, **filter balance** (single-filter patches: 0 = 100% filter 1), **filter feedback** | |
| Envelopes | AEG/FEG A/D/S/R, **mode analog/digital** | |
| Modulation | FEG -> pulse width (amount), FEG -> cutoff (as now) | add others only if presets use them |
| Waveshaper | all types in all categories, drive | |
| FX (optional, later) | A1 chorus: mix, delay time max 20 ms, feedback max 90%, EQ low/high cut | only once renderer test 2 passes with FX on |

## 3. Activity masks: which parameter is inactive when (the lookup Kim asked for)
A parameter that cannot be heard must not be a training target: the flow would learn to guess the prior for it,
wasting capacity and adding loss noise. This does not reliably emerge on its own.

**3a. Declarative table (source of truth), one module, e.g. `surge_activity.py`:**
```python
ACTIVE_IF = {
    "osc2_*":            lambda p: not p["osc2_mute"],
    "osc{n}_unison_detune": lambda p: p[f"osc{n}_unison_voices"] > 1,
    "osc{n}_width":      lambda p: p[f"osc{n}_type"] in TYPES_WITH_WIDTH,
    "filter2_*":         lambda p: p["filter_balance"] > 0 or p["filter_config"] != "single",
    "waveshaper_drive":  lambda p: p["waveshaper_type"] != "off",
    "ringmod_12_*":      lambda p: not p["ringmod_12_mute"],
    "feg_to_pw":         lambda p: any(osc_has_pw(p, n) for n in (1, 2, 3)),
    "chorus_*":          lambda p: p["fx_a1_on"],
    # ... complete from Surge semantics; wildcards expand to concrete names
}
```
**3b. Use it in three places:** (1) `canonicalize(p)` sets inactive params to a fixed value before rendering and in
targets (generalises today's `canonicalize_vector`: unison detune, drive, delay fb); (2) `codec.encode(p)` returns
`(x, mask)` and the flow/JEPA losses weight by `w_enc * mask`; (3) metrics report errors on active params only.

**3c. Verify the table EMPIRICALLY (catches what the table misses or gets wrong):** an identifiability probe.
For each parameter k and each condition state of its gate, over ~200 random valid patches: render with k at its
min vs its max (all else fixed); audio distance (mel L1) below the repeat-noise floor in >= 95% of patches =>
"inactive under that condition". Write the result as `activity_probe.json` and a test that fails when the probe and
the table disagree. Surge's own metadata (surgepy exposes parameter groups and, for some, an "appears deactivated"
flag) can seed the table, but the probe is the referee.

## 4. Sampling and the validity gate
- Sample each continuous parameter uniformly within its bounds, categoricals by preset frequency with a floor
  (so rare types still appear); apply hard rules: single-filter => balance 0; chorus limits; mask via 3b.
- Mix: ~70% "archetype + jitter" (the current prior, now with the 13 extra archetypes), ~30% "independent within
  bounds". Report both splits separately in validation.
- **Validity gate before a patch enters training:** (a) RMS of the note above -50 dBFS (Synth-JDF used -60);
  (b) a fundamental is detectable: pyin/YIN voiced confidence above a threshold on >= 50% of frames AND median f0
  within +-1 semitone of the played note or of an octave of it (log which). Log the rejection rate per category;
  a category above ~30% rejection means its bounds are wrong.
- Held-out FAMILIES stay held out (fold by archetype id; the 17-preset val split was too small, see H4 leak finding).

## 5. Model and training
- Start from v3's recipe (ladders + ordinal loss, OT coupling, EMA, cond-noise, MAE) unless v3's result says drop
  something. Losses masked per 3b.
- Parameter encoder: one token per parameter (Synth-JDF supp. 3.1.2; our JEPA side already does this). Flow
  inverter: replace the ResMLP's single whole-vector linear with per-parameter tokens + grouped inverse projection
  (H7a). With 3 oscillators, consider Param2Tok-style learned assignment (2506.07199) for the oscillator symmetry.
- Ladders: extend to the new axes that matter musically (filter feedback, FEG->PW, osc2 volume, envelope mode).
- Logging per docs/TRAINING.md (per-step loss, grad norm, LR, held-out by kind, run_meta at launch).

## 6. Evaluation (unchanged protocol + additions)
- The 24 real stems, held-out-half refinement, MSS / wMFCC / envelope cos, eval page with same-playhead cells,
  everything rendered with FX OFF, the Oct-5 model and v3 as references.
- Add: per-group parameter error on held-out families (active params only); preset round-trip check on every
  exported preset; one listening pass by Kim before any verdict.

## 7. Order of work (each step gated by its test)
1. surgepy renderer + tests 1-4.  2. Parameter registry + bounds (manifold UNION Kim's 13).  3. `surge_activity.py`
table + probe + agreement test.  4. Validity gate + rejection report.  5. Codec v3 (encode -> x, mask).
6. Smoke train (1k steps) on CPU/GPU.  7. Full run.  8. Eval page.
