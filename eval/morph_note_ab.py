#!/usr/bin/env python3
"""D15's transcription measure, applied to the morph grid — base arms only.

WHY NOT MERIT (measured 2026-09-04): MERIT's S_mel is SATURATED on this material. Two
DIFFERENT reference tracks score S_mel 0.611 mean / 0.861 max, while a cell scores
0.49-0.69 against its OWN reference — so "similar to the reference it was conditioned on"
is inside the range of two unrelated goa tracks. The decisive test: at gain 2.0 conditioning
raised similarity to FOREIGN references MORE (+0.041) than to its own (+0.025), difference
-0.017, sign p=0.71. Whatever gain 2.0 does, it is not reference-specific on that axis.

This is the measure that DID have dynamic range on the same question in D15: transcription
to notes, then decomposed into three things a single number conflates —
    key      pitch-class profile cosine   (does it share the tonality)
    content  pitch-set Jaccard            (does it use the same notes)
    melody   (pitch, frame) cell F1       (are the right notes in the right PLACES)
D15's chroma screen reported +0.022 n.s. on exactly the question this decomposition
answered at +0.100, 6/6, p=0.016 — key and content can both match while melody does not,
and only the F1 separates them.

CONTROLS, both required:
  null     same model, projection zeroed  -> did the control do anything
  foreign  the cell vs OTHER stems' refs  -> the floor; without it we cannot tell a real
           F1 from what any two same-corpus clips score

  eval/morph_note_ab.py [--backbone medium-base] [--out eval/morph_note_ab.json]
"""
import argparse, glob, json, os, math, statistics as st
from collections import defaultdict

FPS = 10.766          # SAME latent frame rate; D15 scored note cells on this grid


def load_notes(path):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(path)
    out = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            out.append((n.start, n.end, n.pitch))
    return out


def pc_profile(notes):
    v = [0.0] * 12
    for s, e, p in notes:
        v[p % 12] += max(1e-3, e - s)
    tot = sum(v) or 1.0
    return [x / tot for x in v]


def cos(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def cells(notes):
    """(pitch, frame) occupancy — the D15 grid."""
    s = set()
    for st_, e, p in notes:
        for f in range(int(st_ * FPS), max(int(st_ * FPS) + 1, int(e * FPS))):
            s.add((p, f))
    return s


def f1(a, b):
    if not a or not b:
        return 0.0
    i = len(a & b)
    if not i:
        return 0.0
    pr, rc = i / len(a), i / len(b)
    return 2 * pr * rc / (pr + rc)


def jac(a, b):
    A, B = {p for _, _, p in a}, {p for _, _, p in b}
    return len(A & B) / len(A | B) if (A | B) else 0.0


def sign_p(pos, n):
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--midi", default="eval/morph_midi")
    ap.add_argument("--merit", default="eval/morph_merit.json",
                    help="reused only for the arm/stem/gain/backbone labels")
    ap.add_argument("--backbone", default="medium-base")
    ap.add_argument("--out", default="eval/morph_note_ab.json")
    a = ap.parse_args()

    meta = {}
    for r in json.load(open(a.merit))["rows"]:
        base = os.path.basename(r["wav"])[:-4]
        meta[base] = r
    refs = {os.path.basename(p)[len("ref__"):-4]: p
            for p in glob.glob(f"{a.midi}/ref__*.mid")}
    print(f"refs {len(refs)}")

    N = {}
    def notes(p):
        if p not in N:
            N[p] = load_notes(p)
        return N[p]

    rows = []
    for p in sorted(glob.glob(f"{a.midi}/*.mid")):
        b = os.path.basename(p)[:-4]
        if b.startswith("ref__"):
            continue
        m = meta.get(b.replace("morph__", "", 1)) or meta.get(b)
        if not m or m["backbone"] != a.backbone:
            continue
        own = refs.get(m["stem"])
        if not own:
            continue
        nc, no = notes(p), notes(own)
        r = dict(arm=m["arm"], stem=m["stem"], gain=m["gain"], vocab=m["vocab"], n_notes=len(nc))
        r["own_key"], r["own_content"], r["own_melody"] = (
            cos(pc_profile(nc), pc_profile(no)), jac(nc, no), f1(cells(nc), cells(no)))
        fk, fc, fm = [], [], []
        for s2, p2 in refs.items():
            if s2 == m["stem"]:
                continue
            n2 = notes(p2)
            fk.append(cos(pc_profile(nc), pc_profile(n2)))
            fc.append(jac(nc, n2))
            fm.append(f1(cells(nc), cells(n2)))
        r["foreign_key"], r["foreign_content"], r["foreign_melody"] = (
            st.mean(fk), st.mean(fc), st.mean(fm))
        rows.append(r)
    print(f"cells scored: {len(rows)} (backbone={a.backbone})")

    # DYNAMIC-RANGE GATE, before any verdict: does the measure separate own from foreign?
    for f in ("key", "content", "melody"):
        d = [r[f"own_{f}"] - r[f"foreign_{f}"] for r in rows]
        pos = sum(1 for x in d if x > 0)
        print(f"  own-vs-foreign {f:<8} mean {st.mean(d):+.4f}  {pos}/{len(d)} pos  "
              f"p={sign_p(pos, len(d)):.3g}")

    null = {(r["arm"], r["stem"]): r for r in rows if r["gain"] is None}
    for g in (1.0, 2.0):
        print(f"\n  === gain {g} vs control-off ===")
        for f in ("key", "content", "melody"):
            d = []
            for r in rows:
                if r["gain"] != g:
                    continue
                n = null.get((r["arm"], r["stem"]))
                if n:
                    d.append(r[f"own_{f}"] - n[f"own_{f}"])
            if d:
                pos = sum(1 for x in d if x > 0)
                print(f"    d_{f:<8} {st.mean(d):+.4f}  {pos}/{len(d)} pos  p={sign_p(pos,len(d)):.3g}")
    json.dump({"rows": rows}, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
