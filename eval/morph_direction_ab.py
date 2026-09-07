#!/usr/bin/env python3
"""Does the morph conditioner move pitch in the REQUESTED DIRECTION? (continuous, CPU)

WHY THIS INSTEAD OF SYMBOL AGREEMENT (C, 2026-09-05, Kim's ask): the contour stream is a
RANK CODE with tol=0.5 semitones. Three independent extractors failed to recover it from
rendered audio -- LatCH head 0.175, transcription skyline 0.146, melodia on the mix 0.110,
against a ~0.15 chance floor for a 13-symbol alphabet. That is ONE fact, not three bugs:
sub-semitone rank order does not survive an encode->decode round trip, so symbol agreement
has a cliff and collapses to chance.

A CONTINUOUS comparison has no cliff. It degrades gracefully, which is why the SAME LatCH
f0 head that is useless for rank agreement is usable here: its ~6.4-semitone MAE destroys
ranks but leaves a 0.51-correlation pitch-height signal intact, and correlation is what this
measures.

IT ALSO ASKS THE RIGHT QUESTION. "Reproduce this rank sequence" is neither measurable nor
what anyone wants from a control. "Ask for a rise, get a rise" is the product requirement,
and Pearson r is offset- and scale-invariant -- which matches a conditioner whose target is
monotone-invariant BY DESIGN (contour_codes.py: "dense rank is unchanged by any strictly
increasing transform").

  requested  = the reference stem's ground-truth f0_other (semitones) over the render window
  rendered   = the f0 LatCH head applied to the render's SAVED z0 -- no audio, no GPU needed
  own        = corr(rendered, its own requested trajectory)
  foreign    = corr(rendered, OTHER stems' trajectories)   <- the floor
  effect     = own(gain) - own(null), paired by (arm, stem)

Base-arm cells only: the full-FT arms sit on a Pattern-2 replica backbone (EXPERIMENTS
A10) and measure the damage, not the conditioner.
"""
import argparse, glob, json, math, os, statistics as st, sys
from collections import defaultdict
import numpy as np

LAT = "/home/kim/Projects/latents_sa3"
HEAD = ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/"
        "ftstack_heads/latch_f0_other_s1/latch_sa3_f0_other_ep30.pt")


def sign_p(pos, n):
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n)


def corr(a, b, m):
    a, b = a[m], b[m]
    if len(a) < 8 or np.std(a) < 1e-6 or np.std(b) < 1e-6:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", default="/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/morph")
    ap.add_argument("--out", default="eval/morph_direction_ab.json")
    a = ap.parse_args()

    import torch
    sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
    from stable_audio_3.models.latch import load_latch_from_checkpoint
    head = load_latch_from_checkpoint(HEAD, device="cpu").eval()

    # requested trajectories: ground-truth f0 (semitones) per stem, over that stem's window
    req = {}
    cells = []
    for jf in sorted(glob.glob(f"{a.renders}/*/*.json")):
        d = json.load(open(jf))
        if str(d.get("backbone", "")).startswith("/scratch"):
            continue                                   # full-FT arms excluded, see docstring
        z = jf[:-5] + ".z0.npy"
        stem = str(d["stem"])
        if not os.path.exists(z) or not os.path.exists(f"{LAT}/{stem}.TIMESERIES.npz"):
            continue
        i0, i1 = d["window"]
        if stem not in req:
            n = np.load(f"{LAT}/{stem}.TIMESERIES.npz")
            f0 = np.asarray(n["f0_other_ts"], np.float64)[i0:i1]
            v = np.asarray(n["f0_other_voiced_ts"], np.float64)[i0:i1] > 0.5
            s = np.zeros(len(f0))
            s[v] = 12.0 * np.log2(np.maximum(f0[v], 1e-3) / 440.0)
            req[stem] = (s, v)
        cells.append({"arm": os.path.basename(os.path.dirname(jf)), "stem": stem, "z": z,
                      "gain": None if not d.get("conditioned") else float(d.get("gain", 1.0)),
                      "vocab": int(d["vocab"])})
    print(f"  base-arm cells {len(cells)} · stems {len(req)}")

    rows = []
    for i, c in enumerate(cells, 1):
        arr = np.load(c["z"]).astype(np.float32)
        t = torch.from_numpy(arr)
        while t.ndim < 3:
            t = t.unsqueeze(0)
        if t.shape[1] != 256 and t.shape[-1] == 256:
            t = t.transpose(1, 2)
        with torch.no_grad():
            pred = head(t, torch.zeros(t.shape[0])).squeeze().float().numpy()
        s_own, v_own = req[c["stem"]]
        n = min(len(pred), len(s_own))
        own = corr(pred[:n], s_own[:n], v_own[:n])
        fo = []
        for st2, (s2, v2) in req.items():
            if st2 == c["stem"]:
                continue
            m = v2[:n] & v_own[:n] if len(v2) >= n else None
            fo.append(corr(pred[:n], s2[:n], (v2[:n] if len(v2) >= n else v_own[:n])))
        fo = [x for x in fo if x == x]
        if own != own or not fo:
            continue
        rows.append({**{k: c[k] for k in ("arm", "stem", "gain", "vocab")},
                     "own": own, "foreign": st.mean(fo)})
        if i % 48 == 0:
            print(f"    {i}/{len(cells)}", flush=True)

    print(f"  scored {len(rows)}\n")
    d = [r["own"] - r["foreign"] for r in rows]
    pos = sum(1 for x in d if x > 0)
    print("DISCRIMINATION GATE (own trajectory vs other stems'):")
    print(f"  own {st.mean(r['own'] for r in rows):+.4f}  foreign {st.mean(r['foreign'] for r in rows):+.4f}"
          f"  diff {st.mean(d):+.4f}  {pos}/{len(d)} pos  p={sign_p(pos,len(d)):.3g}")

    null = {(r["arm"], r["stem"]): r for r in rows if r["gain"] is None}
    for g in (1.0, 2.0):
        dd = [r["own"] - null[(r["arm"], r["stem"])]["own"]
              for r in rows if r["gain"] == g and (r["arm"], r["stem"]) in null]
        if dd:
            p = sum(1 for v in dd if v > 0)
            print(f"  gain {g}: d_corr {st.mean(dd):+.4f}  {p}/{len(dd)} pos  p={sign_p(p,len(dd)):.3g}")
    json.dump(rows, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
