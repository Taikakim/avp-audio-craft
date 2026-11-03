---
name: bass-transcriber-low-priority
description: Own DSP bass->MIDI transcriber (src/transcription/bass/) was rebuilt 2026-10-05 but Kim considers Muscriptor clearly better -- keep effort on it small
metadata:
  node_type: memory
  type: project
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-05T13:56:55.848Z
---

2026-10-05: rebuilt the non-Muscriptor bass transcriber as `src/transcription/bass/transcribe.py`
(successor to `src/bass_midi_pipeline.py`, which was left untouched). Synthetic goa-bass benchmark
`synth_bench.py` + scorer `bench_eval.py` (mir_eval note F1, 50 ms / 50 cents). Held-out test F1:
old 0.48, Basic Pitch 0.58, new 0.87. CPU only, ~12 s per 7-min track, grid-quantized MIDI.

Kim, mid-session: "Muscriptor beats this so clearly, that very much trouble should not be used" --
said before trying the new version.

Head-to-head 2026-10-05 (same 60 held-out synthetic clips, bass-only input, Muscriptor medium on GPU):
note F1 new 0.87 vs Muscriptor 0.81 (bass-restricted 0.79); offsets 0.79 vs 0.54. Muscriptor wins only
rolling 16ths (0.88-0.90 vs 0.87) and ties wobble. Caveat: production Muscriptor runs on the FULL MIX,
which a July probe found better than stems -- not tested here.

REAL-STEM A/B 2026-10-05 (24 real bass phrases in Mantu/surge_200k_models/real_stems_eval, all MIDI
played through the same inverted Surge patch; listen: real_stems_eval/ab/): Muscriptor wins on real
stems -- envelope corr 0.21 vs new 0.15 vs old 0.11, low-band chroma corr 0.68 vs 0.62 vs 0.55; best
on 13/24 (env) and 16/24 (chroma) stems vs new 5 and 3. So the synthetic win did NOT transfer;
Kim's verdict stands. New still clearly beats the old pipeline.

**Why:** Muscriptor (GPU, full mix, CC BY-NC weights) is the preferred transcriber; this DSP one is
a cheap CPU fallback / bass-specific complement.
2026-10-06 Kim: "the muscriptor patches ... offer a transcribing with sound never seen before" -- "We can safely forget about our own bass transcription." DROPPED.

**How to apply:** do NOT work on src/transcription/bass/ again unless Kim reopens it; use MuScriptor. Real-stem comparison done (Muscriptor better); Kim's ear on ab/ files is the final word. Known weak spots: delay-echo polyphony (acid), weak-bump re-triggers in rolling basses,
~5% stray low notes from note-end pitch drops on real stems.
