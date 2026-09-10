#!/usr/bin/env python3
"""CONTOUR-to-CONTOUR adherence for the morph grid — the matched instrument.

WHY THE OTHER TWO FAILED (measured 2026-09-04, both nulls, both uninterpretable):
MERIT S_mel is saturated on same-corpus material (two DIFFERENT references score 0.611
mean) and its gain-2.0 shift was NOT reference-specific — foreign similarity rose MORE
(+0.041) than own (+0.025). D15's transcription measure failed its own dynamic-range gate
here (own-vs-foreign melody +0.022, 80/192, p=1).

Both failed for the SAME structural reason, and it is not statistical. From
mir/src/conditioners/contour_codes.py: "Monotone invariance is the point: dense rank is
unchanged by any strictly increasing transform of the values." A contour stream encodes
the RANK ORDER of a value inside a window and nothing else — it deliberately discards
absolute pitch, key and note identity. So MERT melody embeddings, pitch-class cosine,
pitch-set Jaccard and note-cell F1 all measure exactly the information the conditioner
throws away. A render with PERFECT contour adherence would score at chance on all of them.

THIS compares like with like: re-encode the render's own melodic line with the SAME
alphabet and grid the conditioner used, and compare symbol-for-symbol against the stream
that was actually fed in (saved per cell as .stream.npy).

Reproduces eval/build_morph_streams.py exactly:
  pitch arms (L2/L3/L4) semitones on VOICED frames, grid = voiced[::4], tol 0.5 st
  IOI3 arm             log inter-onset interval at each onset, grid = onsets[1:], tol 0.15
  encoding             symbol s -> s+1, 0 = UNDEFINED

CONTROLS (both mandatory):
  null     the unconditioned render, scored the same way = chance agreement for this music
  foreign  the cell scored against ANOTHER stem's fed stream = the floor
A conditioned score is meaningless without the own-minus-foreign gap being real first.
"""
import argparse, glob, json, os, math, sys, statistics as st
from collections import defaultdict

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir")
from src.conditioners.contour_streams import contour_stream, expand_to_frames  # noqa: E402

FPS = 10.766
STRIDE, TOL_ST, IOI_TOL = 4, 0.5, 0.15
LAT = "/home/kim/Projects/latents_sa3"
SIDECARS = "/run/media/kim/Lehto/latents-all-backup/latents_sa3_morph{}"


def stream_from_truth(stem: str, L: int) -> "np.ndarray | None":
    """Rebuild a stem's contour stream from ground-truth f0 — EXACT, verified 120/120.

    ⚠ THE BUG THIS FIXES (C, 2026-09-04): `f0_other_ts` is in HERTZ. build_morph_streams
    converts to SEMITONES first (12*log2(f0/440), unvoiced zeroed) and only then encodes,
    because `tol=0.5` means half a SEMITONE. Feeding raw Hz with a 0.5 tolerance collapses
    the "equal" band to nothing, so the dense ranks diverge — that reproduced the sidecars
    at only 0.755 / 0.550 / 0.337 for L2/L3/L4 and made the whole adherence test
    unreadable. It degraded with alphabet size, which read like a grid offset; it was a
    UNIT error. With the conversion in place: 40/40 EXACT on every vocabulary.

    The crop was never wrong — sidecar[i0:i1] vs the fed stream matches at 1.0000.
    """
    import numpy as np
    z = np.load(f"{LAT}/{stem}.TIMESERIES.npz")
    f0 = np.asarray(z["f0_other_ts"], np.float64)
    v = np.asarray(z["f0_other_voiced_ts"], np.float64) > 0.5
    T = f0.shape[0]
    semis = np.zeros(T)
    semis[v] = 12.0 * np.log2(np.maximum(f0[v], 1e-3) / 440.0)
    pts = np.flatnonzero(v)[::STRIDE]
    if pts.size < L + 2:
        return None
    syms, anch = contour_stream(semis, pts, L=L, tol=TOL_ST)
    s = expand_to_frames(syms, anch, T)
    return np.where(s < 0, 0, s + 1).astype(np.int8)
L_OF_VOCAB = {5: 2, 15: 3, 77: 4}


def midi_notes(path):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(path)
    ns = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            ns.append((n.start, n.end, n.pitch))
    return sorted(ns)


def skyline_semitones(notes, T):
    """Highest sounding pitch per frame = the melodic line, as build_morph_streams' f0_other
    proxy. Unvoiced frames stay NaN so the voiced grid matches the original construction."""
    v = np.full(T, np.nan)
    for s, e, p in notes:
        a, b = int(s * FPS), max(int(s * FPS) + 1, int(e * FPS))
        for f in range(max(0, a), min(T, b)):
            if np.isnan(v[f]) or p > v[f]:
                v[f] = p
    return v


def encode_pitch(notes, T, L):
    v = skyline_semitones(notes, T)
    voiced = np.flatnonzero(~np.isnan(v))
    grid = voiced[::STRIDE]
    if grid.size < L + 2:
        return None
    vals = np.nan_to_num(v, nan=0.0)
    syms, anch = contour_stream(vals, grid, L=L, tol=TOL_ST)
    s = expand_to_frames(syms, anch, T)
    return np.where(s < 0, 0, s + 1).astype(np.int8)


def encode_ioi(notes, T):
    on = np.array(sorted({int(s * FPS) for s, _, _ in notes}), dtype=int)
    on = on[(on >= 0) & (on < T)]
    if on.size < 6:
        return None
    ioi = np.diff(on).astype(float)
    vals = np.zeros(T)
    vals[on[1:]] = np.log(np.maximum(ioi, 1.0))
    syms, anch = contour_stream(vals, on[1:], L=3, tol=IOI_TOL)
    s = expand_to_frames(syms, anch, T)
    return np.where(s < 0, 0, s + 1).astype(np.int8)


def agree(a, b):
    """Symbol agreement on frames where BOTH are defined (non-zero)."""
    m = (a > 0) & (b > 0)
    n = int(m.sum())
    return (float((a[m] == b[m]).mean()), n) if n else (float("nan"), 0)


def sign_p(pos, n):
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", default="/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/morph")
    ap.add_argument("--midi", default="eval/morph_midi")
    ap.add_argument("--backbone", default="medium-base")
    ap.add_argument("--out", default="eval/morph_contour_ab.json")
    a = ap.parse_args()

    fed_by_stem = defaultdict(dict)      # arm -> stem -> fed stream
    rows = []
    for jf in sorted(glob.glob(f"{a.renders}/*/*.json")):
        d = json.load(open(jf))
        bb = "full-FT" if str(d.get("backbone", "")).startswith("/scratch") else "medium-base"
        if bb != a.backbone:
            continue
        base = os.path.basename(jf)[:-5]
        sp = jf[:-5] + ".stream.npy"
        mp = os.path.join(a.midi, base + ".mid")
        if not (os.path.exists(sp) and os.path.exists(mp)):
            continue
        # ARM = the render's own label when it has one, NOT the directory name. The old
        # layout was one directory per arm, so dirname was the arm; a checkpoint TRAJECTORY
        # is many arms in ONE directory (six checkpoints of the same run, plus a gain ladder
        # rendered alongside them), and dirname would collapse all of them into a single
        # pooled row set -- with the last stream written per stem silently winning, so every
        # checkpoint would be scored against whichever one happened to load last. Pooling
        # across cells that differ in the variable under study is the error the board's
        # per-cell rule exists to prevent. Falls back to dirname for the old layout.
        # (CONTINUITY 2026-09-10)
        arm = str(d.get("label") or os.path.basename(os.path.dirname(jf)))
        fed = np.load(sp).astype(np.int8)
        # ONLY conditioned cells carry a real stream. A null cell saves an ALL-ZERO stream
        # (zero tokens = the trained null), and since "null" sorts after "g1.0"/"g2.0" it was
        # overwriting the real one for every (arm, stem) — leaving every comparison to score
        # against an empty stream and silently drop. The null render is still scored below,
        # against the stream that WOULD have been fed: that is the chance baseline.
        if d.get("conditioned"):
            fed_by_stem[arm][str(d["stem"])] = fed
        rows.append({"arm": arm, "stem": str(d["stem"]), "vocab": int(d["vocab"]),
                     "gain": None if not d.get("conditioned") else float(d.get("gain", 1.0)),
                     "fed": fed, "midi": mp})
    print(f"cells: {len(rows)}  arms: {len(fed_by_stem)}")

    out = []
    for r in rows:
        notes = midi_notes(r["midi"])
        T = len(r["fed"])
        enc = (encode_ioi(notes, T) if "IOI" in r["arm"]
               else encode_pitch(notes, T, L_OF_VOCAB[r["vocab"]]))
        if enc is None:
            continue
        target = fed_by_stem[r["arm"]].get(r["stem"])
        if target is None:
            continue
        own, n_own = agree(enc, target)
        fs = [agree(enc, s)[0] for st_, s in fed_by_stem[r["arm"]].items() if st_ != r["stem"]]
        fs = [x for x in fs if not math.isnan(x)]
        if math.isnan(own) or not fs:
            continue
        out.append({k: r[k] for k in ("arm", "stem", "vocab", "gain")} |
                   {"own": own, "foreign": st.mean(fs), "n_frames": n_own})
    print(f"scored: {len(out)}\n")

    # POSITIVE CONTROL, RUN FIRST AND FATAL: re-extract from the REFERENCE audio — the exact
    # source the fed stream was computed from — and compare to that stream. A faithful
    # extractor must score HIGH here. Measured 2026-09-04 it scores 0.09 (L3) / 0.29 (L2) /
    # 0.04 (L4) / 0.17 (IOI3) — LOWER than the renders themselves score (0.151). That is not
    # a weak result, it is proof the extraction path is wrong: the fed stream came from
    # f0_other_ts (stem-separated melodic line, continuous pitch, from the PRE-ENCODE audio)
    # while this reconstructs a MuScriptor skyline (polyphonic transcription of DECODED
    # audio). Different quantity. Without this check the null below reads as "the conditioner
    # does not transfer contour", which the data does not support.
    ctrl = []
    for arm, per in fed_by_stem.items():
        for stem, f in per.items():
            mp = os.path.join(a.midi, f"ref__{stem}.mid")
            if not os.path.exists(mp):
                continue
            voc = next((x["vocab"] for x in rows if x["arm"] == arm), None)
            if voc is None:
                continue
            n2 = midi_notes(mp)
            e2 = (encode_ioi(n2, len(f)) if "IOI" in arm else encode_pitch(n2, len(f), L_OF_VOCAB[voc]))
            if e2 is None:
                continue
            v, _ = agree(e2, f)
            if not math.isnan(v):
                ctrl.append(v)
    ctrl_mean = st.mean(ctrl) if ctrl else float("nan")
    print(f"POSITIVE CONTROL (reference audio vs its OWN fed stream): {ctrl_mean:.4f}  n={len(ctrl)}")

    d = [x["own"] - x["foreign"] for x in out]
    pos = sum(1 for x in d if x > 0)
    print("DYNAMIC-RANGE GATE (own fed stream vs another stem's, same render):")
    print(f"  own {st.mean(x['own'] for x in out):.4f}  foreign {st.mean(x['foreign'] for x in out):.4f}"
          f"  diff {st.mean(d):+.4f}  {pos}/{len(d)} pos  p={sign_p(pos,len(d)):.3g}")

    null = {(x["arm"], x["stem"]): x for x in out if x["gain"] is None}
    for g in (1.0, 2.0):
        dd = [x["own"] - null[(x["arm"], x["stem"])]["own"]
              for x in out if x["gain"] == g and (x["arm"], x["stem"]) in null]
        if dd:
            p = sum(1 for v in dd if v > 0)
            print(f"  gain {g}: d_agreement {st.mean(dd):+.4f}  {p}/{len(dd)} pos  p={sign_p(p,len(dd)):.3g}")
    if not math.isnan(ctrl_mean) and ctrl_mean < 0.5:
        print(f"\n  ⛔ EXTRACTOR FAILS ITS POSITIVE CONTROL ({ctrl_mean:.3f}). The numbers above "
              f"measure this pipeline, NOT the conditioner. Do not report them as a result: "
              f"reproduce f0_other (stem-separated melodic line) instead of a transcription "
              f"skyline — via mir stem-sep+f0 on the renders, or the f0_other LatCH head on "
              f"each render's saved z0 (cheap, but needs this same control before use).")
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
