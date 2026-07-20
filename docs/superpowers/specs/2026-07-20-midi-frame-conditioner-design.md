# MIDI-Driven Generation — Tiered Note-Roll Conditioner for SA3

*Design spec, 2026-07-20 (WINTERMUTE, with Kim). Status: DESIGN APPROVED, gated
on the MuScriptor LUMI run + a Phase-0 validation. Builds on
`2026-07-17-muscriptor-lumi-batch.md`, the `sa3_control` adapter path, and the
384-d `same_chroma` head.*

---

## 1. Goal (the product)

A musician **drags a MIDI file into the tool, types a prompt, and gets it
rendered as a goa track that plays their melody in the prompted sound** —
performed with idiomatic goa expression (portamento, microtonal inflection, the
"feel"), not a stiff note-for-note readout.

> "The model should work with any MIDI thrown at it." — drop a bassline, a lead,
> both, or a full multi-track arrangement, and get audio back.

This is **rendering a user's authored melody**, which is a different problem from
*matching* an existing melody (the a2a / chroma-morph lane). That distinction
drives every representation decision below.

## 2. The core decisions (and why)

| Decision | Choice | Why |
|---|---|---|
| **Mechanism** | Control **adapter** (forward conditioning, `sa3_control`-class), NOT a guidance head | Faithful note-following must be *native*. The "rigid conditioning = mush" failure (Kim's breathing-a2a verdict) is a *guidance* problem — an inference-time constraint fighting the flow. A trained adapter *learns* `(notes → audio)`, so tight following is learned behaviour, not a fight. |
| **Representation** | **Discrete note-roll** (piano-roll: absolute pitch + onset), NOT continuous f0/chroma | The user supplies the *skeleton* (which notes, which octave, what timing); the **model supplies the expression** (slide/bend/microtonality), learned from the audio targets. Notes carry absolute octave + onset timing that chroma throws away — exactly what "play *my* melody" needs. |
| **Why not MIDI 2.0** | Irrelevant to the model | The information loss is at **capture** (audio → 12-TET notes), not **serialization**. MuScriptor is a discrete-note transcriber (`note_on`/`note_off`, no pitch-bend/f0). Re-serializing its notes into a 2.0 container recovers nothing. MIDI 2.0 / MPE belongs only as an **optional authoring overlay** (§7), not the core representation. |
| **Microtonality / portamento** | **Delegated to the model** | The average musician authors the *tune*, not the microtuning. Trained on `(goa-lead-notes → goa-audio)` pairs where the audio *has* the slides, the model learns to perform notes idiomatically. |
| **Tier structure** | **One adapter, three note-channels** (`bass` / `mid` / `high`) + channel dropout | Unifies Kim's `midi_bass` / `midi_other` / `midi_complex` into channel *subsets* of a single adapter. Native composition (jointly trained → learns basslines and leads relate harmonically), any-subset input, one training run. Aligned to the 3-band structure of the 384-d `same_chroma`. |
| **Targets** | Transcribe the **full mix** (MuScriptor's native multi-instrument / MT3 domain), route its per-instrument output to tiers — NOT isolated stems, NOT decoded latents | MuScriptor is **MT3-based**: every note is tagged with a `program`/instrument, so a *full-mix* transcription already separates into per-instrument tracks we route to tiers. Feeding it **isolated stems is out-of-distribution** for a full-mix model (isolated pads/leads + separation artifacts) — Kim's flag. Full-mix is in-distribution, needs no stems, has no separation artifacts, and is **1× transcription, not 3×**. Use original full-mix **audio** (cleaner than decoded latents — the gate's F1 0.74 was codec-decode fragility). |

## 3. Architecture

One frame-level control adapter over the SA3 medium DiT — the **MuseControlLite
class** (dense per-frame conditioning), extending the existing `sa3_control`
adapter (which today takes a scalar/control-token; this adds a dense per-frame
multi-channel input).

**Conditioning input** — a per-frame note tensor at the **latent frame rate
(10.7666 Hz)**, aligned to the generation timeline, with **three register
channels**:

- `bass` channel — bass-register notes, routed from the full-mix transcription (maps to the bass chroma band)
- `mid` channel — mid-register notes (pads / harmony)
- `high` channel — high-register notes (leads)

Each channel is a poly note-roll (`[n_frames, n_pitch_bins]`) — polyphonic, not
a single f0. A monophonic lead is simply a *sparse* poly-roll, so the same
`mid`/`high` channels handle "drop a lead" and "drop pads+lead" with no
special-casing. (Pitch-bin resolution — full 128-MIDI vs a folded/register-scoped
range — is an implementation detail resolved in the plan; start with a per-tier
register-scoped range to keep the tensor small.)

**Channel dropout during training** — each channel is independently zeroed with
some probability per sample, so the adapter learns to work with any subset
present. Kim's three "conditioners" then fall out as usage modes:

- `midi_bass` = `bass` channel active
- `midi_other` = `mid` + `high` active
- `midi_complex` = all three active

**Why unified beats three separate adapters:** (1) native composition — three
independently-trained adapters can *fight* at inference (observed with the LatCH
heads); (2) one training run per config, not three; (3) "complex" is just
"all channels on," so it never needs a separate adapter trained on the *noisy
full-mix* transcription.

## 4. Training-data pipeline

Per source track (corpus = `Goa_Separated`):

1. **Full-mix audio** — the original `full_mix.<ext>` (no stems needed).
2. **Transcribe the full mix** with MuScriptor (MT3-based, multi-instrument) —
   **1× per track, not 3×**. Every note comes tagged with its `program`/instrument.
3. **Route notes to tiers** — split into `bass` / `mid` / `high` channels
   **primarily by register** (pitch thresholds, robust), using the per-note
   `program`/instrument as a **secondary** signal (bass programs → `bass`,
   synth-lead → `high`, synth-pad / strings → `mid`). Register-first because MT3's
   General-MIDI taxonomy may not classify goa's synths cleanly (§8).
4. **Rasterize to per-frame note-rolls** at 10.7666 Hz, aligned to the exact
   crop windows the SA3 latents use (the `latents_sa3` crop map + the whole-track
   timeseries alignment already establish this timeline).
5. **Companion the latents** — one `.MIDIROLL.npz` (3 channels) per crop, beside
   the existing `.npy` / `.TIMESERIES.npz`, same keying.

**Note-space augmentation (critical — the fix for the distribution-shift risk,
§8).** Do NOT train only on the raw transcriptions. Augment each roll — transpose,
re-time (tempo / onset jitter), thin / thicken the polyphony, and inject **non-goa
melodies** — so the adapter must *follow the roll* rather than pattern-complete
from a memorized goa vocabulary. Without this the adapter learns to ignore
off-distribution MIDI and revert to generic goa (C's #1).

**Why not stems:** MuScriptor is a full-mix model; isolated stems are
out-of-distribution (isolated pads/leads + separation artifacts). Its
multi-instrument output already separates the mix internally, so we route *that*
to tiers instead of pre-separating the audio. Stems remain a **fallback** if
Phase-0 routing proves insufficient (accepting the OOD risk, tested then).

**Alignment note:** targets align to the **latent** timeline (10.7666 Hz, T=4096
crops), reusing the `whole_track_target_source` / crop-map machinery that already
slices `[start,end]` and resamples.

## 5. Inference workflow (the drag-drop UX)

1. User **drops a MIDI** + types a **prompt** (+ optional duration/BPM).
2. **Parse + route**: split the MIDI's notes into `bass` / `mid` / `high` by
   register (or honor explicit track→tier tags for multi-track MIDI).
3. **Rasterize** to the 3-channel per-frame roll at 10.7666 Hz, time-scaled to
   the requested duration (MIDI timing drives output onset positions).
4. **Render**: adapter conditions the DiT on `(roll + text)` → SA3 generates the
   audio. Absent channels stay zeroed (dropout-trained → clean).
5. Output: goa audio playing *their* melody in *their* prompted sound.

Home for the UI: `explorer_sa3` (the drag-drop tab is a natural sibling of the
`bend_tab` / `bracket` Latent-lab work).

## 6. Phase 0 — the MIDI ↔ 384-d chroma cross-check (gated on the LUMI run)

Before training anything, validate the representation corpus-wide:

- Render the MuScriptor note transcription into the **same 384-d register-banded
  chroma space** as `same_chroma`, per frame.
- Measure per-frame agreement against the `same_chroma` targets extracted from
  the audio, corpus-wide.

**What it tells us:** (a) that the note representation carries the pitch content
(sanity); (b) **where they diverge is the microtonal / portamento content the
note grid drops** — the exact expression the model must supply. Strong agreement
⇒ notes are a faithful skeleton; systematic divergence on lead-heavy material ⇒
confirms expression-delegation is doing real work (and flags whether a
power-user continuous overlay, §7, is worth it). This is cheap (both derivable
from audio), runs the moment the LUMI transcription lands, and needs no training.

**Caveat (C's #3) — this is a *sanity check*, not the go/no-go.** Both signals
derive from the *same* audio, so agreement only confirms two extractors concur on
one signal; it says nothing about whether the *adapter* can use notes to steer.
The real gate is the small-train run + note-following authority on
**off-distribution** MIDI (§9). Keep Phase 0 (cheap, catches a broken
representation/routing), but don't let it stand in for the real test.

## 7. Expression handling & the MIDI-2.0 question

- **Default (average musician):** notes only; expression is model-idiomatic.
- **Power user (optional, post-v1):** an **MPE / MIDI-2.0 / "glide" overlay** — a
  per-note bend/expression channel a musician *can* author — rendered down to an
  extra continuous conditioning channel. This is where Kim's MIDI-2.0 instinct
  belongs: an authoring nicety on top, **not** the core representation. Out of v1
  scope; the architecture leaves room for it (a 4th channel).
- **Faithfulness dial (C's #4c):** faithfulness and expression are in tension — a
  portamento *deviates* from the grid. Expose a dial from tight note-following to
  idiomatic deviation, so the user (or a preset) picks where to sit. Cheap to wire
  (conditioning strength / a scalar the adapter sees) — the honest knob for "play
  exactly my notes" vs "make it sing."

## 8. Risks (foundational first; C's review 2026-07-20)

**⚠️ THE failure mode — train/inference distribution shift (C's #1).** Training
pairs are `(notes-transcribed-FROM-the-audio → that audio)`, so the adapter only
ever sees *goa-idiomatic* note patterns — its own transcriptions. A user's
arbitrary dropped MIDI is **off-distribution**, and the risk is the Gate-B
conditional-mean failure: off-dist conditioning gets averaged away, the output
**ignores the specific notes and reverts to generic goa**. This is a
*generalization* problem, not an expressiveness one. **Mitigation, baked in:**
heavy **note-space augmentation** at training — transpose / re-time / thin /
thicken the roll, inject non-goa melodies — so the adapter must *follow the roll*,
not pattern-complete from a memorized vocabulary. Single most important design
element; §4 carries it, and the note-following eval (§9) is what proves it worked.

**⚠️ Tier-separability — the routing may not survive even the full mix (C's gate-#0, 2026-07-20).**
The stem probe (10 tracks) confirms stems are *worse* for MuScriptor (full-mix median 1305
notes vs bass 366 / other 641; bass & other < full-mix 10/10) — so the full-mix pivot is
empirically right. **But** full-mix MuScriptor tends to **collapse to a near-mono bassline with
collapsed instrument labels** (#41 + the probe). If it doesn't emit usable per-instrument/register
separation, the 3-channel roll (§3) degrades to "bass + a label-collapsed rest" and the tier design
needs rethinking. **Verify before committing the tier structure** (Phase 0, §9): does the full-mix
transcription carry separable bass/mid/high? If not, fall back to register-only routing, a 2-channel
(bass + rest), or a single roll.

**Legato / sustain recovery (C's #0) — universal, not edge-case.** MuScriptor fragments held notes,
and the probe found **sustained >1 s ≈ 0 on EVERY source** — so a user's cleanly-held MIDI note has
no faithful training target, and an uncorrected adapter never learns to *hold*. Mitigations: a
note-merge post-process on the transcription, and **D4 held-note recovery as a first-class eval rung**
(C's note-following spec). Measure sustain recovery explicitly in the transcription-quality check.

**Injection mechanism is the crux (C's #4b) — pin it in the plan's FIRST task,
not "later."** How the per-frame roll conditions each DiT block — per-frame
decoupled **cross-attention** (the MuseControlLite pattern), add-to-tokens, or
per-frame FiLM — is where faithful-following lives or dies. Lead with the
cross-attn pattern (MuseControlLite is the precedent); first-class decision.

**Frame-rate aliasing (C's #4a).** 10.7666 Hz ≈ 93 ms/frame vs goa 16ths
≈ 100 ms — fast arps alias two notes into one frame. Add an **onset-phase
sub-frame channel** (fractional onset position within the frame) so timing
survives.

**Smaller:** goa-genre transcription quality (~0.74 F1 on decoded full-mix;
better on original — quantify before the full run); instrument/register routing
(route by register, program secondary; Phase-0 validated); tempo/timing mapping
(MIDI timing drives output onsets); pitch-bin resolution (start register-scoped,
not full 128); training cost (dense per-frame conditioning is heavier than the
scalar adapters).

## 9. Sequencing

1. **Phase 0 — sanity + tier-separability (NOT the go/no-go, C's #3)** — (a) MIDI↔384d
   cross-check; (b) **tier-separability check (C's gate-#0):** does full-mix MuScriptor
   actually emit separable bass/mid/high, or collapse to a mono bassline with dead labels?
   This gates the whole tier design (§3) — if it fails, fall back to register-only / 2-channel /
   single roll. Catches a broken representation OR an unroutable transcription. *No training.*
2. **Transcription-quality check** — MuScriptor accuracy on original full-mix goa
   (vs the 0.74 decoded baseline), **including sustain/legato recovery**, before
   the full run.
3. **Note-roll extraction + augmentation** — the `.MIDIROLL.npz` companion pipeline
   *and* the note-space augmentation (transpose / re-time / thin / thicken /
   non-goa), which is what forces note-following (mir lane).
4. **🚦 THE go/no-go — note-following authority (C's #2).** Spec:
   `2026-07-20-note-following-eval-design.md`. Train a *small* adapter, then measure the
   chroma-trap-safe differential **GAP(A,B) = agree(out_A,R_A) − agree(out_A,R_B)** on
   **off-distribution** rolls (D0 held-out → D3 non-goa → D4 sparse held-notes): a
   mode-collapsed generic-goa generator gives GAP≈0, only genuine roll-following gives GAP>0.
   **GAP-on-D3 is the gate** — GAP that collapses by D3 = memorization = v1 fails. *This*, not
   Phase 0, decides whether the method works, before spending the full run.
5. **Full adapter train** — 3-channel dense conditioning + dropout + augmentation,
   injection mechanism pinned (§8) (SAO lane).
6. **Inference tool** — drag-drop UI in `explorer_sa3`, with a faithfulness dial (§7).

Steps 1–3 are cheap and LUMI-gated; **step 4 is the real gate** before committing
the full train.

## 10. Reuse (what already exists)

- **Full-mix audio** — `Goa_Separated` `full_mix` (mir; no separation needed).
- **MuScriptor batch** — `2026-07-17-muscriptor-lumi-batch.md` (full-mix, multi-instrument).
- **`sa3_control` adapter** — the forward-conditioning path to extend (SAO).
- **384-d `same_chroma`** — the Phase-0 comparison target.
- **Crop/timeline alignment** — `whole_track_target_source` + the `latents_sa3`
  crop map.
- **UI** — `explorer_sa3` (`bend_tab` / `bracket` lane).
