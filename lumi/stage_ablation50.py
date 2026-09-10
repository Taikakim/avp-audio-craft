#!/usr/bin/env python
"""stage_ablation50.py — CONTINUITY 2026-08-13 (Kim direct): stage a 50-track raw-audio
subset (symlinks to Mantu/Goa_Separated full_mix.ogg + a one-line genre caption each) for
the local single-variable-at-a-time full-FT ablation (EMA / augment / optimizer / force_scalar
/ wd+clip, isolating which of OUR deltas from Stability's upstream training path causes the
drone/square-wave divergence). --data_dir mode so --augment (live-encode only) is testable.

Deterministic stride-sample over the corpus (not the first N — avoids any alphabetical/artist
bias). Caption = "<genre>, instrumental" from the track's .INFO (lowercased, comma-joined) —
good enough for a mechanism-isolation test, not a caption-quality one.
"""
import json
import os
from pathlib import Path

SRC = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
DST = Path("/home/kim/Projects/goa_ablate50_raw")
N = 50


def main():
    DST.mkdir(parents=True, exist_ok=True)
    tracks = sorted(d for d in SRC.iterdir() if d.is_dir())
    stride = max(1, len(tracks) // N)
    picked = tracks[::stride][:N]
    print(f"[stage] {len(tracks)} tracks in corpus, stride={stride}, picked={len(picked)}")

    n_ok = 0
    for i, td in enumerate(picked):
        mixes = list(td.glob("full_mix.*"))
        info = td / f"{td.name}.INFO"
        if not mixes:
            print(f"[stage] SKIP (no full_mix.*): {td.name}")
            continue
        mix = mixes[0]
        safe = f"{i:03d}_{''.join(c if c.isalnum() else '_' for c in td.name)[:60]}"
        link = DST / f"{safe}{mix.suffix}"
        txt = DST / f"{safe}.txt"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(mix)

        genre = "instrumental electronic"
        if info.exists():
            try:
                meta = json.loads(info.read_text())
                g = meta.get("track_metadata_genre", "")
                if g:
                    genre = g.lower() + ", instrumental"
            except Exception:
                pass
        txt.write_text(genre)
        n_ok += 1

    print(f"[stage] DONE — {n_ok} audio+caption pairs in {DST}")


if __name__ == "__main__":
    main()
