#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-28)
# Last edited: GHOST-NOTE 2026-10-28 -- content guard (per-second RMS, drops clips with >2 s below -45 dB or < 60 s unbroken content from the start)
"""Glue used for the 17-original v7c mix (EXPERIMENTS F7 step 2): part 1 = madmom downbeats of the 3x-extended clips (db17.py), part 2 = content guard + BPM order + stem symlinks + per-clip entry/exit bounds (prep.py). Run order: eval/mixtape_lengthen_only.py -> eval/mixtape_v7_separate.py -> part 1 -> part 2 -> eval/render_v7_smoketest.py --band-swap --clash-aware --no-generate --assemble-mix --tempo-source kicks --phase-mode kicks --tempo-plan --w-bars 16 --clips 0:N. Paths were /tmp/m17/*."""

# ===== part 1: db17.py =====
import json, sys, soundfile as sf
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from dj_beatmatch import madmom_downbeats
o = json.load(open("/tmp/mix17_order_len3x.json")); out = {}
for c in o:
    a, sr = sf.read(c["path"], dtype="float32", always_2d=True)
    out[c["id"]] = [round(x, 3) for x in madmom_downbeats(a.T, sr)]
    print(c["id"][:40], len(out[c["id"]]), flush=True)
json.dump(out, open("/tmp/m17/downbeats_native.json", "w"))


# ===== part 2: prep.py =====
import json, sys, os, numpy as np, soundfile as sf
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import mixtape_v7_dsp as dsp
O = json.load(open("/tmp/mix17_order_len3x.json")); DB = json.load(open("/tmp/m17/downbeats_native.json"))
ST = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_mix17_stems"
rows = []
for i, c in enumerate(O):
    d = DB[c["id"]]; rows.append(dict(c, old=i, bpm=float(dsp.fit_bpm(d)), n_db=len(d)))
rows.sort(key=lambda r: r["bpm"])

# ---- content guard (owner ask 2026-10-28): per-second RMS on every extended clip; a clip must have content from its entry to its exit
# (> 2 s below -45 dB in that span = unusable) and at least MIN_RUN s of unbroken content from the start. Prints the list.
FLOOR_DB, MAX_BAD_S, MIN_RUN_S = -45.0, 2, 60
def content_report(path, start, end):
    x, sr = sf.read(path, dtype="float32", always_2d=True); m = x.mean(1); n = len(m) // sr
    db = np.array([20 * np.log10(np.sqrt((m[i * sr:(i + 1) * sr] ** 2).mean()) + 1e-9) for i in range(n)])
    low = db < FLOOR_DB
    run = int(np.argmax(low)) if low.any() else n          # unbroken content from t=0
    bad_in_span = int(low[int(start):int(end)].sum())
    return run, bad_in_span
keep, dropped = [], []
for r in rows:
    run, bad = content_report(r["path"], 0.0, 1e9)
    (dropped if (bad > MAX_BAD_S or run < MIN_RUN_S) else keep).append((r, run, bad))
for r, run, bad in dropped:
    print(f"GUARD DROP {r['id'][:60]}: {bad} s below {FLOOR_DB:.0f} dB, unbroken content {run} s")
print(f"GUARD: kept {len(keep)} of {len(rows)}")
rows = [r for r, _, _ in keep]
print([round(r["bpm"], 1) for r in rows])
os.makedirs("/tmp/m17/stems_ordered", exist_ok=True)
bounds = {}
for j, r in enumerate(rows):
    link = f"/tmp/m17/stems_ordered/{j:02d}"
    if os.path.lexists(link): os.remove(link)
    os.symlink(f"{ST}/{r['old']:02d}", link)
    d = np.array(DB[r["id"]]); x, sr = sf.read(r["path"], dtype="float32", always_2d=True); m = x.mean(1); dur = len(m) / sr
    start = float(d[d >= 0.0][0])
    # exit: a downbeat 4k bars after the entry, in the last 12..30 s, quietest following bar
    cand = []
    for k in range(4, len(d), 4):
        t = d[k]
        if dur - 30 <= t <= dur - 12 and k + 1 < len(d):
            seg = m[int(t * sr):int(d[k + 1] * sr)]
            cand.append((float(np.sqrt((seg ** 2).mean())), float(t)))
    end = min(cand)[1] if cand else float(d[-5])
    bounds[r["id"]] = dict(start=start, end_pre_zc=end)
json.dump([dict(id=r["id"], path=r["path"], bpm=r["bpm"]) for r in rows], open("/tmp/m17/order_final.json", "w"), indent=1)
json.dump(bounds, open("/tmp/m17/bounds.json", "w"), indent=1)
print("clips", len(rows), "bounds span s:", [round(b["end_pre_zc"] - b["start"]) for b in bounds.values()][:6])
