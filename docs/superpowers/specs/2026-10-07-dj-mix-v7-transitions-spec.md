# DJ mix v7 — transition rebuild (spec for GHOST-NOTE)

Owner: GHOST-NOTE (`OWNERSHIP.md`). Written by CONTINUITY 2026-10-07 from Kim's listening of v6 and from measurements.
Kim's decisions are marked **KIM**. Read the whole thing before starting; section 5 is the list of traps that have
already cost us a day each. **Work in phases; each phase has a numeric gate; do not start a phase until the
previous gate is met; report numbers, not impressions.** If a step fails twice, stop and report to C or Kim
instead of patching around it.

## 1. What Kim heard, and what we measured

**Kim, listening to v6 (a2a and smoothed, not the pure crossfade):** (a) as the clips transition into each other
there is a *temporal gap*; (b) the transitions are quite short. His hypothesis: BPM stretching that is not
compensated. His proposed rule: **KIM: neither clip may have its tempo changed while the crossfade is active.**

**Measured cause of (a), and it is not the stretching.** `eval/mixtape_audit_continuity.py` tracks where in its
source clip each window of the mix comes from. On v6 *every one of the 39 splices* replays the incoming clip:
the audio after the splice is the source clip at its **entry point**, not ~10 s later where the crossfade left
it (found to within 10 ms; e.g. splice 0 should be at 12.24 s into the clip and is at 2.34 s). Mechanism:
`chain_simple_crossfade.py` renders each pair as a composite `[A_head | crossfade | B_post]`;
`mixtape_assemble_continuous.py` cuts pair i at `a_head + overlap` and appends pair i+1, whose `A_head` starts at
that clip's entry (`a_start_sec`). The v5 "fix" (threading `a_start_sec`) only stopped the replay from sample 0;
it still replays by exactly the crossfade length. The clean sample-jump scores of v6 could not see this
(the audio is clean, just in the wrong place) — that is an instrument blind spot, now covered by the audit.

**Kim's BPM hypothesis is real but second.** Today B is slowed at its start and caught up *inside* the window
(`prebend_incoming`), A's tempo is stepped up in the tail (`prebend_outgoing`, ±2 BPM), and the alignment search
only looks ±80 ms (G's audit of the v6 per-pair records: 16/40 offsets > 40 ms, two at the bound; transition 0
is a 7.6 % bend because of one 120 BPM head clip). Fixing tempo alone would leave the replay in place, and
fixing the replay alone would still leave the tempo ramps. Do both, replay first.

**Cause of (b):** the window is 10 s (≈ 5 bars at 140 BPM).

## 2. Phase 0 — continuity, constant tempo, longer windows (blocking; CPU-first)

**R0.1 One timeline, no concatenated pair renders.** Build the mix from a *placement list*: for clip i,
`source_in_i`, `source_out_i` (bar-aligned, in source samples), `timeline_start_i` (samples), the tempo schedule,
and gain envelopes. Render by overlap-add. A clip's body after its crossfade MUST continue from the exact source
sample where the crossfade left it. Positions are integers (samples), derived from the placement list, never from
`a_head_sec` / `overlap_sec` of a pair run_meta (those are in a different time base once audio is stretched).
Add an `assert` at every splice that source position advances by exactly the number of timeline samples
(± the stretch factor).

**R0.2 Tempo rule (KIM).** Inside a crossfade window neither clip's tempo changes. Recommended implementation:
only the **outgoing** clip A is time-stretched; its tempo ramps in A's body *before* the window (≥ 8 bars,
slew ≤ 0.5 BPM per bar, ramp placed on quiet material where the detector finds it) and lands exactly on B's
native tempo; A is then held at a constant factor through the window; **B is never stretched.** If |BPM gap| > 5,
fix the *order* (re-sort, drop the outlier clip; drop the lone 120 BPM head clip) instead of stretching harder.
Stretch engine: bungee only (never sox); keep the factor within ±6 %. After the stretch recompute *every* grid
(beats, downbeats, quiet points) on the stretched audio.

**R0.3 Phase alignment.** Pick B's entry so that a B downbeat lands on an A downbeat (shared bar grid). Estimate
the residual by cross-correlating the kick/bass band (40–150 Hz) over the whole window with a search of ±¼ beat
(≈ ±100–200 ms; today's ±80 ms is too small), mild penalty on large shifts, and apply it as ONE constant shift
(never time-varying). Store residual, shift and the tempo schedule in the run_meta.

**R0.4 Window length in bars, not seconds.** `TRANSITION_BARS` parameter. Arithmetic to respect: a 47.55 s clip is
27.7 bars at 140 BPM, so an entry window plus an exit window of 16 bars (≈ 27 s each) do not fit. Options (a
**KIM** decision, default b): (a) lengthen every clip ≥ 2× with the existing outpaint tool
(`eval/mixtape_lengthen_and_prep.py` / `outpaint_lengthen.py`; needs the GPU, and every latent it produces must
be decoded with the adaptive ceiling, `eval/decode_z0_clamped.py`), then use 16 bars; (b) keep the clips and use
`bars = min(12, (clip_bars - 4) // 2)` (≈ 20 s, the clip is nearly always in a blend, which is normal DJ practice).

**R0.5 a2a smoothing, if kept.** Window-local only: process `[window - 2 bars, window + 2 bars]`, depth ≤ 0.7,
and blend the result back with ≥ 1 bar equal-power at both edges. Do NOT re-encode whole clips through the
autoencoder per pair (that is what changes timbre at joins today). Merge the adapter after load (13e;
`merge_adapters`, already in `chain_simple_crossfade.py`). Check z0 std of anything you decode; apply the ceiling.

**R0.6 Corpus and outputs.** Start from `mixtape_v6_rerender/work48b/order_final.json` (41 clips, each already
decoded at its per-clip ceiling) minus the 120 BPM head clip. Write to a NEW dir `mixtape_v7_*`; never touch v6.
The assembler writes `timeline.json` itself (`dur`, `clip_bounds`, `trans`: the format of
`build_dj_mixes_section.py::timeline`) and a `run_meta.json` (purpose, hypothesis, kill criterion, every measured
value, `kim_feedback: null`).

**Phase 0 gate (all must hold, on the a2a and the plain mix; paste the numbers):**
1. `mixtape_audit_continuity.py` reports **0 findings** (tol 0.25 s). The tool is noisy inside crossfades
   (it can invent a −25 s or +7 s finding where two clips overlap); a finding there must be re-checked by hand,
   but the v6 signature, a median deviation of about −10 s at every splice, must be gone.
2. Kick-grid continuity: beat positions (madmom raw beats, mir venv) across every transition keep inter-beat
   intervals within ±15 ms of the meeting tempo; write this check as `eval/mixtape_audit_grid.py`.
3. Sample-jump screen (|diff| > 0.6): ≤ 6 per minute and no 30 s window above 20 (v6 a2a: 4.5/min).
4. Transition length in bars as configured, read from `timeline.json`.
5. Per-30 s RMS within ±3 dB of the mix median (no level steps).
6. Every clip's source position is monotone (from the audit's tracked positions).

## 3. Phase 1 — feasibility spikes for Kim's stem idea (do not build before these pass)

Kim's design (kept as stated): separate each clip into stems; let the **kick** crossfade smoothly; **mask** the
transition on the **bass** and the **percussion** and inpaint them; fade the **other** stem of the outgoing clip out
and the incoming one in with a sweeping filter (outgoing low-passed down, incoming high-passed so it first plays
the extreme highs and then sweeps down to full range, then the filter switches off), gate the two "other" stems with
the downbeat activation map of the full mix and mix them in **latent space**; the incoming "other" may start one
bar early (pre-roll); compile it all to one master transition that is audio-crossfaded with some overlap into
the in- and outgoing clips. **Review: the structure is sound; three parts are unproven and each gets a spike (S2 is a hope worth testing, not a presumed failure).**

* **Tools that already exist:** BS-RoFormer lives in the mir venv (`/home/kim/Projects/mir/mir/bin/python`, weights in
  `mir/models/bs-roformer/`, wrapper `mir/src/preprocessing/bs_roformer_sep.py`, ≈ 5.6× realtime, ≈ 3 GB VRAM).
  The 4-stem model gives drums / bass / other / vocals. **It has no kick stem**; kick = drums low-passed < 150 Hz
  with a transient mask, percussion = drums − kick (a DSP split; psytrance kick and rolling bass overlap, so expect
  bleed). BS-RoFormer and madmom run in the mir venv, SA3 in the SAO venv: exchange files, do not mix venvs.
* **S1 Separation quality.** On 10 clips: residual `mix − Σ stems` must be ≤ −20 dB re the mix; kick/bass bleed
  (low-band energy of `other` and of percussion) reported; Kim listens to 3 clips' stems.
* **S2 Stem inpainting.** *(Corrected 2026-10-07 after Kim: SA3 was trained on loads of stems and single-instrument
  sounds, and our paper note agrees: the AudioSparx caption language has `TrackType: Instrument` (stems) / `SFX`,
  present in about half the training captions. My first draft called isolated stems "off-distribution"; that was
  wrong.)* Isolated stems are therefore in-distribution for SA3 and SAME. The remaining risks are different:
  (a) **separator output is not a studio stem** (bleed, phasey high end, residual of the other stems), so it is a
  different distribution from the clean stems SA3 saw; (b) the model should be **told it is a stem**: put
  `TrackType: Instrument` and `Instruments: bass` (or percussion) in the prompt, using the field-prefixed caption
  forms the paper documents; (c) the masked window has two real ends as context, which is the easy case.
  Spike on 5 transitions: inpaint the masked bass stem (the existing inpaint path, mask over the window) with and
  without the stem tags. Pass: bass f0 track has no jump > 1 semitone at the mask edges, kick/bass phase
  relationship preserved, latent std <= 1.25 (else ceiling), and Kim says it is not worse than a plain hand-over.
  **Fail => do not build inpainting.** Fallback: no overlap of basslines at all (the core DJ rule): outgoing bass
  plays to a downbeat, incoming bass starts on the next one (the existing `bass_swap_crossfade` idea, made hard),
  percussion crossfades; kick crossfades.
* **S3 Latent mixing is not audio mixing.** SAME is a non-linear autoencoder: `z(a+b) ≠ z(a)+z(b)`, and the
  **zero latent is not silence**. Kim's "do not let the zero values affect the product" is therefore a hard
  requirement: build all level ramps and filter sweeps in the AUDIO domain before encoding; mix latents with a
  validity-weighted mean `z = Σ wᵢ mᵢ zᵢ / Σ wᵢ mᵢ` where `mᵢ` is 1 only where source i has real content; where only
  one source is valid use its latent unchanged (weight 1, no rescaling); never zero-fill; for silence use
  `encode(silence)`. Spike: for 5 transitions compare audio-domain sum vs latent mean of the two "other" stems
  (level, spectral flatness, absence of a "third sound", Kim's ear) and use the winner.
* **S4 Perfect reconstruction at the seams.** Stems from a separator do not sum to the clip; a recomposed transition
  would step in timbre where it meets the untouched clip. Keep the residual `R = mix − Σ stems` and add it back with
  the clip's own gain envelope, so at unit gains the recomposition equals the original and the master transition
  is bit-continuous with the unprocessed clip at its edges; then crossfade ≥ 1 bar into/out of the master.

## 4. Phase 2 — the stem transition (only after S1–S4 pass; Phase 0 gate still applies)

On the Phase 0 timeline, window = N bars at constant tempo:
* **kick:** crossfade, kicks on the shared grid (latent crossfade via the existing machinery or audio equal-power).
* **bass, percussion:** per S2 (inpainted, or the hard hand-over fallback). Never two basslines at once.
* **other:** complementary **Linkwitz-Riley 4th-order crossover with one moving crossover `fc(t)`**: outgoing gets
  `LP(fc)`, incoming gets `HP(fc)`; `fc` sweeps exponentially (log-frequency) from ≈ 16 kHz to ≈ 40 Hz over the window,
  so the incoming first plays only the extreme highs, then more and more, while the outgoing keeps only the
  lows, then nothing; the LR4 pair sums to a flat magnitude, so level does not dip. At the end the incoming filter is
  bypassed through a ≥ 50 ms crossfade. Incoming pre-roll: 1 bar earlier with an audio-domain gain ramp; outgoing
  "other" must be fully gone by the window end. Gate both with the downbeat activation map of the full mix
  (madmom `RNNDownBeatProcessor`), computed **after** the stretch.
* **master transition** = sum of the above + residual (S4), crossfaded ≥ 1 bar into the clips.
Time-varying filters: `sosfilt` with state carried across blocks (not `filtfilt`), cutoff updated per small block
with interpolation; check a spectrogram for zipper noise.

## 5. Hidden-risk checklist (read twice)

1. **Time bases.** After any stretch every beat, downbeat, quiet point and activation map must be recomputed on the
   stretched audio. A grid from the source time base applied to stretched audio is the classic silent bug.
2. **Sample exactness.** Integers, one conversion from seconds, asserted at every splice (R0.1). Floats rounded
   twice is how the 40 ms "fix" crept in.
3. **Do not trust per-pair run_meta positions** in a stretched composite (`a_head_sec`, `overlap_sec`).
4. **Latent size.** Anything you decode from latents (a2a, inpaint, outpaint) can exceed std 1.25 and then corrupts
   (EXPERIMENTS A14). Log z0 std; apply `decode_z0_clamped.py`'s ceiling; a clamped clip is ~5–14 % duller (v6 sidecar).
5. **Live-adapter fault (13e).** Merge adapters before rendering (`merge_adapters`); the `--duration-seconds 47.55`
   rule for `d48` clips (default duration = a different clip for the same seed).
6. **GPU.** W holds the lock for H6 (~24 h from 2026-10-07 08:44); use `Misc/gpu_guard.sh`; never run a second GPU job
   beside an unattended one (it OOM-killed LatCH D13). Do the CPU phases first (Phase 0 needs no GPU except
   a2a/outpaint). Run Python scripts from the eval dir or `/tmp`, not the SAO root (`SAO/torchcodec/` shadows the real
   package). **bungee only, never sox.**
7. **Zero-latent trap** (S3). 8. **Clipping:** stems/transitions can sum above 1.0; normalise the *whole mix once* at the
   end, never per transition (level steps). 9. **LR4:** magnitude-flat only when both filters use the same `fc(t)` and
   the same order.
10. **Page contract.** The phone page reads `timelines.json` (`dur`, `clip_bounds`, `trans`, `clips`); the builder
    (`eval/build_dj_mixes_section.py`) must accept a `timeline.json` written by the new assembler. Public files must
    contain no model, checkpoint or local path names (W's publish leak-scan). You stage, **W publishes**, `ratings.php`
    already accepts the four flags (`mixflag`).
11. **Do not claim "faultless".** Report the Phase 0 gate numbers; Kim's ears and the four phone buttons decide.
12. **Protocol:** `run_meta.json` at launch, journal / task log / WORKLOG at the end, commit at each phase via
    `Misc/agent_commit.sh GHOST-NOTE`, push only when Kim asks. v6 and older stay untouched.
13. **Ask before inventing.** Latent / decode / SA3-inpaint questions go to CONTINUITY by DM; website and publish
    questions to WINTERMUTE.

## 6. What to report after each phase

| Phase | Report |
|---|---|
| 0 | the six gate numbers for the plain and a2a mix; tempo schedule of 3 transitions; any clip dropped and why; the v7 dir |
| 1 | per spike: pass/fail against its stated criterion, the numbers, 3 audio files for Kim |
| 2 | the Phase 0 gate again plus Kim's phone-tap summary on the previous mix |

*Tools committed with this spec:* `eval/mixtape_audit_continuity.py` (the replay detector, validated on v6),
`eval/decode_z0_clamped.py`, `eval/build_dj_mixes_section.py`, `eval/mixtape_assemble_continuous.py` (the old
concatenating assembler — reference for what NOT to keep).
