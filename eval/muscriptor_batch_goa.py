#!/usr/bin/env python
"""muscriptor_batch_goa.py — MIDI extraction over a 5% random sample of Goa_Separated
(Kim 2026-07-11: "extract midis from a 5% random selection of our goa set. I'm almost
certain it fails on the legato passages.")

Per sampled track: transcribe full_mix.flac with MuScriptor (medium default) -> OUT/
<track>.mid + <track>.stats.json (note count, notes/sec, duration distribution,
sustained-note fraction — the legato-hypothesis numbers). Resumable (skips tracks whose
.mid exists). Model loads ONCE; env is set for our ROCm stack before torch import.

Run:  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE SAO/.venv/bin/python eval/muscriptor_batch_goa.py \
          --device cuda   # GPU pass (after the board render frees the card)
      ... --device cpu --limit 1   # CPU validation trickle
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import io
import json
import time
from pathlib import Path

import numpy as np

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_goa_midis")
FRACTION = 0.05
SEED = 42


def note_stats(midi_bytes):
    """Legato-hypothesis numbers from the MIDI: density + duration distribution."""
    import mido
    m = mido.MidiFile(file=io.BytesIO(midi_bytes))
    tempo = 500000
    notes = []          # (start_s, end_s, pitch, channel)
    open_notes = {}
    for tr in m.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            sec = mido.tick2second(t, m.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on" and msg.velocity > 0:
                open_notes[(msg.channel, msg.note)] = sec
            elif msg.type in ("note_off", "note_on"):
                k = (msg.channel, msg.note)
                if k in open_notes:
                    notes.append((open_notes.pop(k), sec, msg.note, msg.channel))
    if not notes:
        return {"n_notes": 0}
    durs = np.array([e - s for s, e, _, _ in notes])
    span = max(e for _, e, _, _ in notes) - min(s for s, _, _, _ in notes)
    return {"n_notes": len(notes),
            "span_s": round(float(span), 1),
            "notes_per_sec": round(len(notes) / max(span, 1e-6), 3),
            "dur_median_s": round(float(np.median(durs)), 3),
            "dur_p90_s": round(float(np.quantile(durs, 0.9)), 3),
            "dur_max_s": round(float(durs.max()), 3),
            "frac_sustained_gt1s": round(float((durs > 1.0).mean()), 3),
            "frac_short_lt150ms": round(float((durs < 0.15).mean()), 3),
            "channels": sorted({c for _, _, _, c in notes})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="medium")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=None, help="stop after N tracks (validation)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    dirs = sorted(d for d in CORPUS.iterdir() if (d / "full_mix.flac").exists())
    rng = np.random.default_rng(SEED)
    picks = sorted(rng.choice(len(dirs), size=int(len(dirs) * FRACTION), replace=False))
    sample = [dirs[i] for i in picks]
    todo = [d for d in sample if not (OUT / f"{d.name}.mid").exists()]
    print(f"[batch] corpus {len(dirs)} tracks -> sample {len(sample)} (5%, seed {SEED}); "
          f"{len(todo)} to do", flush=True)
    (OUT / "run_meta.json").write_text(json.dumps(
        {"purpose": "MuScriptor MIDI extraction over a 5% seeded random sample of Goa_Separated "
                    "full mixes (Kim ask 2026-07-11) — test set for the legato-failure hypothesis "
                    "(expect: long sustained/gliding lead passages under-transcribed; stats.json "
                    "carries duration-distribution numbers per track).",
         "tool": "muscriptor (github.com/muscriptor/muscriptor), model " + args.model,
         "sample": {"fraction": FRACTION, "seed": SEED, "n": len(sample)},
         "script": "SAO/eval/muscriptor_batch_goa.py",
         "weights_license": "CC BY-NC 4.0 (research use)"}, indent=2))

    from muscriptor import TranscriptionModel
    model = TranscriptionModel.load_model(args.model, device=args.device)
    print(f"[batch] {args.model} loaded on {args.device}", flush=True)

    done = 0
    for d in todo:
        if args.limit is not None and done >= args.limit:
            break
        t0 = time.time()
        try:
            midi = model.transcribe_to_midi(d / "full_mix.flac")
        except Exception as e:
            print(f"[FAIL {d.name}] {type(e).__name__}: {str(e)[:140]}", flush=True)
            continue
        (OUT / f"{d.name}.mid").write_bytes(midi)
        st = note_stats(midi)
        st["wall_s"] = round(time.time() - t0, 1)
        (OUT / f"{d.name}.stats.json").write_text(json.dumps(st))
        done += 1
        print(f"[{done}/{len(todo)}] {d.name}: {st.get('n_notes',0)} notes "
              f"({st.get('notes_per_sec','-')}/s, sustained>1s {st.get('frac_sustained_gt1s','-')}) "
              f"in {st['wall_s']:.0f}s", flush=True)
    print("[batch done]", flush=True)


if __name__ == "__main__":
    main()
