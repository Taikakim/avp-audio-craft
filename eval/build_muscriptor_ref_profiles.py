#!/usr/bin/env python3
"""Reference pitch-class profiles per crop from encode-time chroma companions
(latents_sa3_chroma) -> tiny json shipped to LUMI for the batch integrity screen."""
import glob, json, sys
import numpy as np
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import fold_to_12
out = {}
files = sorted(glob.glob("/home/kim/Projects/latents_sa3_chroma/*.npz"))
for k, f in enumerate(files):
    cid = f.split("/")[-1][:-4]
    with np.load(f) as z:
        key = "full_mix" if "full_mix" in z.files else z.files[0]
        f12 = fold_to_12(z[key].astype(np.float32))       # (3,12,T)
    prof = f12[1].mean(-1)                                 # mid band, time-avg
    s = prof.sum()
    out[cid] = [round(float(v), 4) for v in (prof / s if s > 0 else prof)]
    if k % 1000 == 0: print(k, flush=True)
json.dump(out, open("/home/kim/Projects/SAO/lumi/muscriptor_ref_profiles.json", "w"))
print("wrote", len(out), "profiles")
