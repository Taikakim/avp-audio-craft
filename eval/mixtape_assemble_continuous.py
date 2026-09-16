#!/usr/bin/env python
"""mixtape_assemble_continuous.py — Kim 2026-09-17: stitches chain_simple_crossfade.py's
N-1 independent pairwise renders into ONE continuous, non-duplicating mixtape.

Each pair's saved wav is [A_head + overlap + B_post] -- i.e. clip i's own material
through its handoff into clip i+1, followed by clip i+1's remaining tail run out to
the end of ITS OWN file. Concatenating pair wavs whole would hear clip i+1 twice (once
as this pair's B_post, again as the next pair's A_head). Instead: keep only
[0 : a_head_sec+overlap_sec] (clip i's contribution, ending exactly at the handoff)
from every pair except the LAST, whose B_post tail (the final clip in the mixtape,
which has no further pair to re-supply it) is kept in full.
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chroma_morph_transitions import load  # noqa: E402
from sa3_control.audio_io import save_audio  # noqa: E402


def assemble(pairs, render_dir, variant, out_path):
    segments = []
    sr = None
    for i, p in enumerate(pairs):
        wav_path = render_dir / f"{p['out_name']}_{variant}.wav"
        meta_path = render_dir / f"{p['out_name']}_run_meta.json"
        audio, this_sr = load(str(wav_path))
        sr = sr or this_sr
        meta = json.loads(meta_path.read_text())
        cut = round((meta["measured"]["a_head_sec"] + meta["measured"]["overlap_sec"]) * this_sr)
        if i < len(pairs) - 1:
            segments.append(audio[:, :cut])
        else:
            segments.append(audio)  # last pair: keep its B_post too (final clip's tail)
    full = np.concatenate(segments, axis=1)
    save_audio(str(out_path), torch.tensor(full), sr)
    return full.shape[1] / sr


def main():
    pairs_json = Path(sys.argv[1])
    render_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = json.loads(pairs_json.read_text())
    missing = [p["out_name"] for p in pairs
               if not (render_dir / f"{p['out_name']}_a2a.wav").exists()]
    if missing:
        print(f"[wait] {len(missing)}/{len(pairs)} pair renders not done yet: {missing[:3]}...", flush=True)
        sys.exit(1)

    for variant in ("plain", "a2a"):
        dur = assemble(pairs, render_dir, variant, out_dir / f"mixtape_full_{variant}.wav")
        print(f"[done] mixtape_full_{variant}.wav -- {dur / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
