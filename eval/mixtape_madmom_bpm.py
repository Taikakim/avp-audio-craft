#!/usr/bin/env python
"""mixtape_madmom_bpm.py — Kim 2026-09-16: real madmom BPM for every mixtape clip,
replacing the corpus-metadata `bpm` field (clip_metrics.db, method/precision unknown)
with a direct measurement via the same madmom pipeline used throughout tonight's DJ-mix
work (dj_beatmatch.madmom_downbeats -> median inter-downbeat interval -> BPM). Writes a
new arc file sorted by this real BPM. CPU-only, mir venv, no GPU.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import numpy as np

from chroma_morph_transitions import load as load_mono  # noqa: E402 (has the m4a/ffmpeg fallback)
from dj_beatmatch import madmom_downbeats  # noqa: E402


def bpm_from_downbeats(downbeats, anchor=None):
    """bpm = 240/bar_sec, then fold octave/subdivision locks (the tracker regularly
    locks onto 2/3 subdivisions -- same correction chroma_morph_transitions.tempo_of()
    applies) and pick the candidate closest to `anchor` (this clip's OWN corpus-
    metadata bpm) rather than a fixed global target. A single hardcoded "goa trance"
    band (110-185, chroma_morph_transitions.py's original constant, calibrated for
    Kim's own fast tracks) was tried first and found WRONG for this corpus: the AVP
    mixtape spans 92.3-153.8 bpm per its own metadata, so that band force-folded
    genuinely slow clips upward (measured 148.15 for several clips whose corpus bpm
    was 99.4 -- a 3/2 fold of a real ~98.8 bpm, not tracker error). Anchoring per-clip
    to the corpus's own estimate avoids re-hardcoding a second wrong band."""
    if len(downbeats) < 4:
        return None
    diffs = np.diff(downbeats)
    bar_sec = float(np.median(diffs))
    if bar_sec <= 0:
        return None
    t = 240.0 / bar_sec
    cands = [t * f for f in (1.0, 2.0, 0.5, 1.5, 2.0 / 3.0, 3.0, 1.0 / 3.0)]
    sane = [c for c in cands if 40.0 <= c <= 300.0]
    if not sane:
        return t
    target = anchor if anchor is not None else 145.0
    return min(sane, key=lambda c: abs(c - target))


def main():
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    clips = json.loads(in_path.read_text())
    print(f"[bpm] {len(clips)} clips", flush=True)
    results = []
    for i, c in enumerate(clips):
        try:
            audio, sr = load_mono(c["path"])
            downbeats = madmom_downbeats(audio, sr)
            bpm = bpm_from_downbeats(downbeats, anchor=c.get("bpm"))
        except Exception as e:
            print(f"  [{i:02d}] ERROR {c['file'][:50]}: {e}", flush=True)
            bpm = None
        c2 = dict(c)
        c2["bpm_madmom"] = bpm
        c2["bpm_old"] = c.get("bpm")
        results.append(c2)
        print(f"  [{i:02d}/{len(clips)}] {c['file'][:55]:55s} old={c.get('bpm')}"
              f" madmom={bpm if bpm is None else round(bpm, 2)}", flush=True)

    missing = [r for r in results if r["bpm_madmom"] is None]
    if missing:
        print(f"[bpm] {len(missing)} clips got no madmom BPM, falling back to old bpm for sort", flush=True)
        for r in missing:
            r["bpm_madmom"] = r["bpm_old"]

    results.sort(key=lambda r: r["bpm_madmom"])
    for i, r in enumerate(results):
        r["arc_pos"] = i
    out_path.write_text(json.dumps(results, indent=2))
    print(f"[done] wrote {out_path} ({len(results)} clips, "
          f"bpm range {results[0]['bpm_madmom']:.1f}-{results[-1]['bpm_madmom']:.1f})", flush=True)


if __name__ == "__main__":
    main()
