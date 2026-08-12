# DAWPROJECT.md — parsing Bitwig `.dawproject` exports into ground truth

Master reference for turning Kim's **Bitwig `.dawproject` exports** (his own tracks — rights-clear,
see MASTER §4 commercial-music tiers) into **tick-exact ground truth**: note-grids, gate/negative-space
streams, and song structure. This is the highest-quality reference we have — above MuScriptor
transcription (voice-attribution-noisy) and madmom (activation-estimated) — used to validate every
movement/gate/structure descriptor. Founded 2026-08-12 on `Two Suns in Phrygia` (first export).

**Tooling (reuse index — check before writing new parsers):**
- `eval/musicology/dawp_align.py` — stem ↔ track ↔ clip ↔ **section** aligner; resolves the flat-stem
  group ambiguity from the track hierarchy, converts arrangement to seconds, cross-refs clips→sections
  (per-section element presence). `python3 dawp_align.py <project.xml> <stems_dir> [--json OUT]`.
- `eval/musicology/dawp_to_frames.py` — notes → **tick-exact (T,88) key-roll + gate duty-cycle** at the
  10.7666 Hz SAME-latent frame rate (loop-expanded), per track + merged voice-agnostic. DAW-truth
  counterpart to `prep_notegrid88.py` (MuScriptor). `python3 dawp_to_frames.py <project.xml> [--kmin --kmax]`.

## Format basics (dawproject 1.0)
- `.dawproject` = a **ZIP**: `project.xml` (the data), `metadata.xml`, `audio/*.wav|aiff|mp4` (embedded
  clip audio), `plugins/*` (plugin state). Unzip → parse `project.xml` with stdlib `xml.etree`.
- `Project` > `Transport` (`Tempo@value` bpm, `TimeSignature@numerator/denominator`), `Structure`
  (the track tree), `Arrangement` (the timeline), `Scenes` (clip-launcher).
- **Times are in BEATS** (quarter-notes), `timeUnit="beats"`. Seconds = `beats × 60 / bpm`. A bar =
  `numerator` beats. (Two Suns: 138 bpm, 4/4 → beat 0.4348 s, bar 1.739 s.)
- **`Track`**: `@id`, `@name`, `@contentType` ∈ {`notes` (MIDI), `audio`, `audio notes` (both),
  `tracks` (a **group** — nests child `Track` elements)}. The group nesting is explicit → it tells you
  which flat stem is a sub-mix of which group.
- **`Note`**: `@time` (clip-relative beats), `@duration` (beats = the **GATE**, the note length /
  negative-space that MuScriptor cannot give), `@key` (MIDI pitch), `@vel` (note-on 0–1), `@rel`
  (release velocity — recently added to the format, **often all-default/unused in older projects; do
  not treat as signal without checking**), `@channel`.
- **`Clip`**: `@time` (track-timeline position, beats), `@duration`, `@playStart`, `@loopStart`,
  `@loopEnd`, `@name`. Notes live inside `Clip > Notes > Note`. Audio clips reference `audio/…` files.

## ⚠️ THE critical gotcha: CLIPS LOOP — you MUST expand them
A `Clip` with `loopEnd − loopStart < duration` **repeats** its loop-window notes every
`L = loopEnd − loopStart` beats until the clip ends. **Kim composes heavily this way — a short loop
(≈1 bar) repeated over a long clip (e.g. 30 bars)** — so a naive "read each Note once" parse
undercounts massively. On Two Suns: **7722 raw notes → 20,414 loop-expanded events (~2.6×)**. Any
note-grid / gate / density figure computed without loop expansion is wrong.

**Loop algorithm (general, incl. the `playStart ≠ loopStart` case):**
playback starts at content position `playStart`; when content reaches `loopEnd` it jumps to
`loopStart`. So content position as a function of elapsed beats `e = a − clip.time`:
- non-looping (`loopEnd` absent, or `L ≥ duration`): `content = playStart + e`; place each note once.
- looping: first segment `playStart → loopEnd` (length `loopEnd − playStart`), then `[loopStart,
  loopEnd)` repeats. A note at content-time `t` sounds at every `e` with `content(e)=t`, for
  `clip.time + e < clip.time + duration`; clip each placed note's duration to the clip end.
- **`playStart == loopStart` is the common case** (all but 5 of ~200 Two Suns clips) and simplifies to
  `e = (t − loopStart) + j·L`, j=0,1,…. **`playStart ≠ loopStart`** (Kim's Bassline example: clip at
  bar 73, 30 bars long, loop region offset from content start) needs the first-partial-segment handling
  above. **KNOWN LIMITATION (2026-08-12):** `dawp_to_frames.py` currently places the 5 offset clips
  *once* (place-once fallback) rather than expanding — a minor undercount; refine with the general
  algorithm above when it matters. It reports these as `loop_warnings.playstart_ne_loopstart`.

## Structure conventions (learned from Two Suns — verify per project, but stable so far)
- **Track 1 is the song structure.** A top-level `notes` track named **`Arrangement`** holds named,
  empty clips = the **SECTIONS** (Intro / A #1 / Break 1 / A #2 / Main Break / B #1 / … / Outro), with
  exact beat positions → ground-truth section boundaries in seconds. It carries no key data (empty
  blocks); skip it when building rolls.
- **Group hierarchy is explicit** (Two Suns: `Kickbass`→{Kick, future kick, Bassline}; `Other`→{…,
  sub-groups `Speech`, `Gated Pad Group`}; `Drums`→{Percussion, Ride, …}).
- **Stem export naming scheme** (Bitwig track-export): `NN <TrackName>` = an individual track,
  `<Group> GROUP Master` = a group sub-mix, `<Name> SEND` = an FX return, `Master` = the full mix. The
  `NN` prefix is export order, not group. Match individual stems to tracks by the name-after-prefix;
  the track tree then gives the parent group. (This resolves Kim's "not evident which stems are
  sub-mixes" — the hierarchy is in the project, not the filenames.)

## Key range: 88 is enough
Goa note range is narrow: Two Suns uses **MIDI 26–103** (0 notes outside 21–108). **88 keys (21–108,
A0–C8) is sufficient**; 128 (full MIDI) would spend ~45% more compute on empty top/sub octaves. Default
`--kmin 21 --kmax 108`; `dawp_to_frames` reports the actual range so this stays an evidence call.

## Why it matters (the threads this feeds)
1. **Gate/movement (88-key roll):** DAW-truth roll + exact gate settles the **z→88 register ceiling**
   (the MuScriptor-limited 0.5 centroid-corr) — encode the track → SAME latent → readout vs *this* clean
   roll. Register movement is graded right in the truth: kick 0.0 / perc 0.84 / pads 2.3 (static) →
   acid 11.7 / arp 13.7 / liquid 18.6 (high) — the octave movement chroma/`melody8` discard.
2. **Repetition / structure detector:** the section boundaries + per-section element-presence timeline
   are the ground-truth label to validate the SSM-variety metric + W's `cycle_boundaries` against.
3. **Negative-space / gate:** exact note durations = the true gate-rhythm to calibrate `nspace` (the
   RMS-trough approximation) against.

*Related: `papers/` movement thread (Polansky contour, signatures, Tymoczko), `ARCHITECTURE.md` reuse
index, MASTER §4 (own-music rights tier makes these publishable-model-eligible later).*
