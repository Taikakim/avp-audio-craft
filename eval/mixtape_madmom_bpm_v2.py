#!/usr/bin/env python
"""mixtape_madmom_bpm_v2.py — Kim 2026-09-17: replaces mixtape_madmom_bpm.py's ad hoc
downbeat-interval fold-correction heuristic, which turned out to be the actual bug (it
anchored to a stale/unreliable old BPM estimate and wrongly folded already-correct
measurements down by 2/3 for roughly half the corpus -- confirmed against clips whose
prompt text states a nominal BPM, e.g. "rb_bracket_0" nominal 148, raw madmom beats gave
146.3 correctly, but the old heuristic reported 98.8).

mir/src/rhythm/bpm.py::calculate_bpm_from_beats() already exists and sidesteps the whole
fold-ambiguity class: it computes BPM directly from the mean RAW BEAT interval (not a
downbeat/bar grouping), so there's no "is this really 3 beats or 4" guess to get wrong.
Should have been used from the start instead of writing new fold-guessing logic.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chroma_morph_transitions import load  # noqa: E402

MIR_MADMOM_PY = "/home/kim/Projects/mir/mir/bin/python"
MIR_REPO_ROOT = "/home/kim/Projects/mir"
sys.path.insert(0, MIR_REPO_ROOT + "/src")
from rhythm.bpm import calculate_bpm_from_beats  # noqa: E402


def madmom_beats(audio, sr):
    """Raw beat timestamps (not downbeats) via the same established subprocess pattern
    as dj_beatmatch.py::madmom_downbeats, reading back the sibling .BEATS_GRID file."""
    import soundfile as sf
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = a[None, :]
    with tempfile.TemporaryDirectory(prefix="madmom_") as td:
        tdir = Path(td)
        wav_path = tdir / "clip.wav"
        sf.write(str(wav_path), a.T, sr)
        proc = subprocess.run(
            [MIR_MADMOM_PY, "-m", "src.rhythm.beat_grid", str(wav_path), "--method", "madmom"],
            cwd=MIR_REPO_ROOT, capture_output=True, text=True,
        )
        beats_path = tdir / f"{tdir.name}.BEATS_GRID"
        if not beats_path.exists():
            return np.array([])
        times = np.loadtxt(str(beats_path))
        if times.ndim == 0:
            times = np.array([float(times)])
        return np.sort(times)


def main():
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    clips = json.loads(in_path.read_text())
    print(f"[bpm] {len(clips)} clips (raw-beat method)", flush=True)

    results = []
    for i, c in enumerate(clips):
        try:
            wav_path = Path(c["path"]).with_suffix(".wav")
            used_path = wav_path if wav_path.exists() else Path(c["path"])
            audio, sr = load(str(used_path))
            duration = audio.shape[1] / sr
            beats = madmom_beats(audio, sr)
            if len(beats) < 4:
                bpm = c.get("bpm")
            else:
                bpm, stats = calculate_bpm_from_beats(beats, audio_duration=duration)
        except Exception as e:
            print(f"  [{i:02d}] ERROR {c['file'][:50]}: {e}", flush=True)
            bpm = c.get("bpm")
        c2 = dict(c)
        c2["bpm_v1_buggy"] = c.get("bpm")
        c2["bpm"] = bpm
        results.append(c2)
        print(f"  [{i:02d}/{len(clips)}] {c['file'][:55]:55s} v1={c.get('bpm')} v2={round(bpm,2) if bpm else None}",
              flush=True)

    results.sort(key=lambda r: r["bpm"])
    for i, r in enumerate(results):
        r["arc_pos"] = i
    out_path.write_text(json.dumps(results, indent=2))
    print(f"[done] wrote {out_path} ({len(results)} clips, "
          f"bpm range {results[0]['bpm']:.1f}-{results[-1]['bpm']:.1f})", flush=True)


if __name__ == "__main__":
    main()
