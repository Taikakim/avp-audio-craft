#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""air_escalate.py -- render the air head at -10 dB / gain 24000 over the 64 punch seeds, measure the 2.5 kHz+ band of each clip against its original, and
re-render still-dark clips at a higher target (0 dB, then +10 dB).
WHY (Kim 2026-10-14): the seed-764 bracket found -10 dB @ 24000 nearly restores the air balance; "measure hf rms from each clip and increase target if they're
still dark". DARK = (air minus total RMS, dB) of the level-matched steered clip is more than DARK_DB below the original's.
Presets cleanest_air2/3/4 (-10/0/+10 dB, gain 24000) live in punch_rating_20261014/presets.json. All renders enter the rating manifest. Output: air_escalate.json.
"""
import json, os, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P

DARK_DB = 1.0
LADDER = ["cleanest_air2", "cleanest_air3", "cleanest_air4"]


def rel_air(path):
    x, sr = sf.read(path, dtype="float32")
    m = x.mean(1) if x.ndim > 1 else x
    S = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= 2500].sum() / S.sum()))


seeds = [764, 1337] + list(range(3001, 3063))
res = {}
for i, s in enumerate(seeds):
    hist = []
    for pr in LADDER:
        e = P.make_pair(s, pr)
        d = rel_air(f"{P.CLIPS}/{e['matched']}") - rel_air(f"{P.CLIPS}/{e['base']}")
        hist.append({"preset": pr, "id": e["id"], "d_air_vs_base_db": d})
        print(f"[{i+1}/64] seed {s} {pr} d_air {d:+.2f} dB", flush=True)
        if d > -DARK_DB:
            break
    res[s] = hist
    json.dump(res, open(f"{P.DATA}/air_escalate.json", "w"), indent=1)
print("ESCALATE DONE")
