#!/usr/bin/env python
"""audio_corruption_scan.py — Kim 2026-09-17: flags clips with genuine waveform-level
corruption (rapid, large-amplitude sign-alternation -- not clipping, not DC, not a
normal percussive transient) by counting single-sample amplitude jumps above a
threshold. Built while rebuilding the mixtape: a naive "biggest single jump" metric is
a false-alarm magnet (a hard kick transient in hot-mastered dance music can legitimately
hit 0.4-1.0+ in ONE sample), but the COUNT of such jumps cleanly separates real
corruption from normal transients -- a clean 47.5s clip in this corpus shows 0-2 jumps
above 0.6; the worst corrupted clips found this way showed 5783 and 8161 (found in
genre_fusion_probe_local's OOD-prompt ptm renders -- see census entries for
dora128adj_avp_8ep / dora16_avp_originals_earlyeps).

Usage: audio_corruption_scan.py <clips.json with a "path" field per entry> [threshold] [min_count]
Prints every clip whose count of |diff|>threshold samples exceeds min_count, sorted worst-first.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chroma_morph_transitions import load  # noqa: E402


def scan_clip(path, threshold=0.6):
    audio, sr = load(str(path))
    mono = audio.mean(0)
    d = np.abs(np.diff(mono))
    return int(np.sum(d > threshold)), float(d.max())


def main():
    clips_json = Path(sys.argv[1])
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
    min_count = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    clips = json.loads(clips_json.read_text())
    results = []
    for c in clips:
        p = Path(c["path"])
        wav = p.with_suffix(".wav")
        used = wav if wav.exists() else p
        try:
            n_bad, max_jump = scan_clip(used, threshold)
        except Exception as e:
            print(f"[error] {c.get('file', p.name)}: {e}", flush=True)
            continue
        if n_bad >= min_count:
            results.append((n_bad, max_jump, c.get("file", p.name)))

    results.sort(reverse=True)
    print(f"[scan] {len(results)}/{len(clips)} clips with >={min_count} jumps above {threshold}:")
    for n_bad, max_jump, fname in results:
        print(f"  n_bad={n_bad:6d}  max_jump={max_jump:.3f}  {fname}")


if __name__ == "__main__":
    main()
