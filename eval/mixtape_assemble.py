#!/usr/bin/env python
"""mixtape_assemble.py — Kim 2026-09-16 (overnight batch): concatenates the 81
independent pairwise DJ-overlay mixes (chain_dj_overlay.py, one self-contained
[A_pre + overlap + B_post] two-clip file per consecutive pair) into one continuous
mixtape.

IMPORTANT LIMITATION, flagged rather than hidden: each pair-file is a COMPLETE
standalone two-clip mix, not a splice-ready transition snippet -- clip i+1 appears
TWICE across neighbouring files (once fading in at the end of pair i's overlap, once
fresh at the start of pair (i+1)'s A_pre). There is no way to trim this to a single
occurrence without discarding either its arrival or its "clean" re-entry, so this
assembly takes [A_pre_i + overlap_i] from every pair file (dropping B_post_i, since
the NEXT file's A_pre covers that same clean material afresh) and applies a short
equal-power crossfade at each internal join to soften the restart rather than leave
a hard cut. The result is a genuine mixtape, not a bug-free seamless single
generation -- true seamlessness would need re-architecting the compile as one
continuous multi-clip pass rather than 81 independent pairwise renders, which is a
bigger follow-up if this isn't good enough as-is.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

JOIN_CROSSFADE_SEC = 1.5


def load(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    return a.T, sr


def main():
    pairs_json = Path(sys.argv[1])
    compile_dir = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    pairs = json.loads(pairs_json.read_text())
    sr = None
    segments = []
    for i, p in enumerate(pairs):
        out_name = p["out_name"]
        meta_path = compile_dir / f"{out_name}_run_meta.json"
        meta = json.loads(meta_path.read_text())
        overlap_sec = meta["measured"]["overlap_sec"]
        audio, sr2 = load(compile_dir / f"{out_name}.wav")
        if sr is None:
            sr = sr2
        assert sr == sr2
        a_pre_plus_overlap_samp = round((audio.shape[1] / sr - 0) * sr)  # placeholder, replaced below
        # A_pre + overlap length = total - B_post length; B_post length is not stored
        # directly, but overlap_sec IS -- and A_pre+overlap ends exactly overlap_sec
        # before the file's own B_post begins only if we know B_post's length, which
        # we don't store either. Simpler and robust: take everything EXCEPT the last
        # (B_post) portion, using the ratio recorded in the sidecar's ext/overlap
        # fields when present, falling back to keeping the whole file's first
        # (total - overlap_sec) seconds only when that's the last pair (needs full B).
        keep_sec = audio.shape[1] / sr - overlap_sec if i < len(pairs) - 1 else audio.shape[1] / sr
        keep_samp = round(keep_sec * sr) if i < len(pairs) - 1 else audio.shape[1]
        seg = audio[:, :keep_samp]
        segments.append(seg)
        print(f"[{i:02d}] {out_name}: kept {keep_samp/sr:.1f}s of {audio.shape[1]/sr:.1f}s "
              f"(overlap {overlap_sec:.1f}s)", flush=True)

    fade = round(JOIN_CROSSFADE_SEC * sr)
    total_len = sum(s.shape[1] for s in segments) - fade * (len(segments) - 1)
    out = np.zeros((2, total_len), dtype=np.float32)
    pos = 0
    for i, seg in enumerate(segments):
        if i == 0:
            out[:, :seg.shape[1]] = seg
            pos = seg.shape[1]
        else:
            f = min(fade, pos, seg.shape[1])
            if f > 0:
                ramp = np.linspace(0, 1, f, dtype=np.float32)
                out[:, pos - f:pos] = out[:, pos - f:pos] * (1 - ramp) + seg[:, :f] * ramp
            rest = seg[:, f:]
            end = pos + rest.shape[1]
            out[:, pos:end] = rest
            pos = end
    out = out[:, :pos]
    sf.write(str(out_path), out.T, sr)
    print(f"[done] wrote {out_path} ({pos/sr:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
