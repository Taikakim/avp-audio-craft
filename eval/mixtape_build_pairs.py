#!/usr/bin/env python
"""mixtape_build_pairs.py — Kim 2026-09-17: builds the 76-pair chain_simple_crossfade.py
input from the 77-clip BPM-ordered mixtape (mixtape_final_order.json) plus the bar-aware
entry/exit points from mixtape_bar_aware_bounds.py (mixtape_clip_bounds.json). Each pair's
a_end_sec/b_start_sec are the precomputed bounds -- chain_simple_crossfade.py uses them
directly instead of recomputing a plain a_frac/b_frac downbeat snap.
"""
import json
import sys
from pathlib import Path

ORDER = Path(
    "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
    "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_final_order.json")
BOUNDS = Path(
    "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
    "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_clip_bounds.json")
OUT = Path(
    "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/"
    "cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/mixtape_pairs.json")


def main():
    clips = json.loads(ORDER.read_text())
    bounds = json.loads(BOUNDS.read_text())

    missing = [c["file"] for c in clips if c["file"] not in bounds]
    if missing:
        print(f"[wait] {len(missing)}/{len(clips)} clips not yet bounded: {missing[:3]}...", flush=True)
        sys.exit(1)

    pairs = []
    for i in range(len(clips) - 1):
        a, b = clips[i], clips[i + 1]
        ba, bb = bounds[a["file"]], bounds[b["file"]]
        # a_start_sec: clip A's OWN entry point -- 0.0 for the very first clip in the
        # sequence (nothing plays before it), otherwise the SAME value used as
        # b_start_sec one pair back, so a clip's contribution to the continuous mix
        # runs from where it faded in to where it fades out, never from its file's
        # absolute sample 0 (see chain_simple_crossfade.py::process_pair).
        a_start = 0.0 if i == 0 else ba["start"]
        pairs.append({
            "a_path": ba["path_used"],
            "b_path": bb["path_used"],
            "a_bpm": a["bpm"],
            "b_bpm": b["bpm"],
            "a_start_sec": a_start,
            "a_end_sec": ba["end"],
            "b_start_sec": bb["start"],
            "a_bars": ba["bars"],
            "b_bars": bb["bars"],
            "out_name": f"{i:02d}_{a['id'][:40]}_TO_{b['id'][:40]}",
        })

    OUT.write_text(json.dumps(pairs, indent=2))
    print(f"[done] {len(pairs)} pairs -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
