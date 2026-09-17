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

⚠ The two sides of each pair-to-pair JOIN are not sample-identical even at the same
nominal time offset: pair i's B_post (clip i+1 continuing past its own transition) has
been bungee tempo-bent by prebend_incoming to catch up to that transition's target BPM,
while pair i+1's own A_head (same clip, same nominal start point) is the RAW, unwarped
file -- two genuinely different renderings of "the same moment." A hard cut between them
produced an audible click/glitch (Kim's ear, 2026-09-17; measured jump up to 0.68 in
normalized amplitude vs a ~0.07-0.11 typical single-sample delta elsewhere in the same
file). Fix: a short (JOIN_XFADE_SEC) linear crossfade AT the splice itself, blending the
tail of the kept material into the head of the next pair's kept material -- the content
on both sides is the same clip at the same moment, so a brief blend reads as a very minor
smoothing, not a second mix, and it eliminates the hard-cut discontinuity.
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

JOIN_XFADE_SEC = 0.04


def assemble(pairs, render_dir, variant, out_path, xfade_sec=JOIN_XFADE_SEC):
    sr = None
    audios, cuts = [], []
    for p in pairs:
        audio, this_sr = load(str(render_dir / f"{p['out_name']}_{variant}.wav"))
        sr = sr or this_sr
        meta = json.loads((render_dir / f"{p['out_name']}_run_meta.json").read_text())
        cut = round((meta["measured"]["a_head_sec"] + meta["measured"]["overlap_sec"]) * this_sr)
        audios.append(audio)
        cuts.append(cut)

    xfade_n = round(xfade_sec * sr)
    segments = []
    for i in range(len(pairs)):
        audio, cut = audios[i], cuts[i]
        end = min(cut + xfade_n, audio.shape[1]) if i < len(pairs) - 1 else audio.shape[1]
        seg = audio[:, :end].copy()
        if i > 0:
            n = min(xfade_n, seg.shape[1], segments[-1].shape[1])
            t = np.linspace(0.0, 1.0, n, dtype=np.float32)
            segments[-1][:, -n:] = segments[-1][:, -n:] * (1.0 - t)[None, :] + seg[:, :n] * t[None, :]
            seg = seg[:, n:]
        segments.append(seg)
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
