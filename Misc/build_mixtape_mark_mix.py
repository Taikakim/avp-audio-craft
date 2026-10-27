#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-27)
"""Builds the 17-clip relcut ORIGINAL mix (4 s equal-power crossfades, tracks RMS-matched, plain beat-agnostic joins) as mix.wav +
cues.json, for the phone listening page (template: Misc/mixtape_mark_page.template.html; two big buttons 'this track sounds bad' /
'the previous transition was bad', marks kept in the artifact db, not the browser). Page: https://claude.ai/artifact/FXLA1E1H6V6UUCZ2NvPQ6A
(private; audio uploaded as mix.mp4 = the 192k AAC repackaged, because the asset store rejects .m4a and caps files at 20 MiB).
Usage: SAO/.venv/bin/python Misc/build_mixtape_mark_mix.py <outdir>   then ffmpeg -i mix.wav -c:a aac -b:a 192k mix.m4a ; replace __CUES__/__MIX_URL__ in the template."""
import glob, json, sys
import numpy as np, soundfile as sf
D = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_z0_relcut_2026-10-21/"
S = sys.argv[1].rstrip("/") + "/"
XF, sr = 4.0, 44100
n = int(XF * sr); t = np.linspace(0, np.pi / 2, n)[:, None]; fin, fout = np.sin(t), np.cos(t)
out, cues = None, []
for i, f in enumerate(sorted(glob.glob(D + "*__orig.wav"))):
    x, s = sf.read(f, dtype="float32"); assert s == sr
    x = x / (np.sqrt((x ** 2).mean()) + 1e-9) * 0.12
    if out is None: out, start = x.copy(), 0
    else:
        start = len(out) - n
        out[start:] = out[start:] * fout + x[:n] * fin
        out = np.concatenate([out, x[n:]])
    cues.append(dict(i=i + 1, id=f.split("/")[-1][:-len("__orig.wav")], start=round(start / sr, 2)))
out = out / np.abs(out).max() * 0.89
for k, c in enumerate(cues): c["end"] = round(cues[k + 1]["start"] + XF if k + 1 < len(cues) else len(out) / sr, 2)
sf.write(S + "mix.wav", out, sr, subtype="PCM_16"); json.dump(dict(xfade=XF, cues=cues), open(S + "cues.json", "w"), indent=1)
