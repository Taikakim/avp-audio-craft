#!/usr/bin/env python
"""mixtape_bar_aware_bounds.py — Kim 2026-09-17: per-clip entry/exit points for the
mixtape crossfader, refining chain_simple_crossfade.py's plain a_frac/b_frac downbeat
snap with two rules Kim asked for:

1. "the eventual clips you're mixing have downbeats divisible by four" -- the exit
   point (a_end) must be a downbeat that is a multiple of 4 BARS after the entry
   point (b_start), same convention as mir's create_training_crops.py `div4` crops
   (reused directly: find_end_for_div4_downbeats, count_downbeats_in_range). "if a
   clip has two beats too much, roll back two and crop at the nearest zero crossing"
   -- find_end_for_div4_downbeats already searches BACKWARDS for the nearest
   divisible-by-4 downbeat; the result is then snapped to the nearest zero crossing
   BEFORE it (find_zero_crossing_backwards, same tool), so the cut never overshoots
   and never lands on a sample edge.
2. "place the mixing point at a section with low RMS to try to avoid mixing in a
   busy part" -- among the div4-eligible downbeats in the search window (the
   "latter part" of the clip, A_FRAC_LO..A_FRAC_HI of duration), prefer whichever
   sits closest to one of dj_beatmatch.detect_quiet_points()'s local RMS minima
   (already used elsewhere in this pipeline for prebend catch-up points) rather
   than always taking the one nearest the raw target fraction.

Each clip's bounds are computed ONCE from the clip's OWN downbeat grid (start via
b_frac, end via the above) -- independent of its neighbours in the mix, matching
how chain_simple_crossfade.py already treats A/B independently per pair. Output is
consumed by mixtape_build_pairs.py.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chroma_morph_transitions import load  # noqa: E402
from dj_beatmatch import detect_quiet_points, madmom_downbeats  # noqa: E402

sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from create_training_crops import (count_downbeats_in_range,  # noqa: E402
                                    find_closest_downbeat, find_downbeat_before,
                                    find_end_for_div4_downbeats,
                                    find_zero_crossing_backwards)

B_FRAC = 0.03       # clip's own entry point, matches chain_simple_crossfade.py default
A_FRAC_LO = 0.75    # "latter part" search window for the exit/mixing point
A_FRAC_HI = 0.97
ZC_SEARCH_SEC = 0.05


def choose_clip_bounds(audio, sr):
    duration = audio.shape[1] / sr
    db = np.asarray(madmom_downbeats(audio, sr))
    mono = audio.mean(0)

    start = find_closest_downbeat(db, B_FRAC * duration)
    start = float(start) if start is not None else B_FRAC * duration

    lo_t, hi_t = A_FRAC_LO * duration, A_FRAC_HI * duration
    div4_in_window = [t for t in db if lo_t <= t <= hi_t
                       and count_downbeats_in_range(db, start, t) > 0
                       and count_downbeats_in_range(db, start, t) % 4 == 0]

    quiet = detect_quiet_points(audio, sr)
    quiet = [q for q in quiet if lo_t <= q <= hi_t] or quiet

    if div4_in_window and quiet:
        end = min(div4_in_window, key=lambda t: min(abs(t - q) for q in quiet))
        method = "div4+quiet"
    elif div4_in_window:
        end = div4_in_window[-1]  # nearest to hi_t (list is sorted ascending)
        method = "div4 only (no quiet point in window)"
    else:
        end = find_end_for_div4_downbeats(db, start, hi_t)
        if end is None:
            end = find_downbeat_before(db, hi_t)
        end = float(end) if end is not None else hi_t
        method = "div4 fallback (window too short for a clean multiple)"

    end_idx = find_zero_crossing_backwards(mono, round(end * sr), search_window=round(ZC_SEARCH_SEC * sr))
    end_zc = end_idx / sr

    return {
        "start": start, "end": end_zc, "end_pre_zc": end,
        "duration": duration, "bars": count_downbeats_in_range(db, start, end),
        "method": method, "n_downbeats": len(db), "n_quiet": len(quiet),
    }


def main():
    order_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
        "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_final_order.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
        "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_clip_bounds.json")

    clips = json.loads(order_path.read_text())
    results = {}
    if out_path.exists():
        results = json.loads(out_path.read_text())

    for c in clips:
        key = c["file"]
        if key in results:
            print(f"[skip] {key}", flush=True)
            continue
        wav_path = Path(c["path"]).with_suffix(".wav")
        used_path = wav_path
        if not wav_path.exists():
            used_path = Path(c["path"])  # m4a fallback for the one still-transferring clip
            print(f"[WARN] no .wav yet, using m4a: {key}", flush=True)
        audio, sr = load(str(used_path))
        bounds = choose_clip_bounds(audio, sr)
        bounds["path_used"] = str(used_path)
        bounds["bpm"] = c["bpm"]
        results[key] = bounds
        out_path.write_text(json.dumps(results, indent=2))
        print(f"[done] {key} start={bounds['start']:.2f}s end={bounds['end']:.2f}s "
              f"bars={bounds['bars']} ({bounds['method']})", flush=True)

    print(f"[all done] {len(results)}/{len(clips)} clips bounded -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
