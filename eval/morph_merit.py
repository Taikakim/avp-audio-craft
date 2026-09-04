#!/usr/bin/env python3
"""MERIT disentangled similarity for the morph-conditioner grid.

Kim 2026-09-03: "can we run merit melody similarity on these?" — and he was right that we
already had it: github.com/AMAAI-Lab/MERIT is cloned at ~/Projects/MERIT with all three
heads, wrapped by control/sa3_control/merit_eval.py (MeritScorer). Frozen MERT-330M + 3
projection heads give three INDEPENDENT cosines per audio pair: S_mel / S_rhy / S_tim.

WHY THIS BEATS TRANSCRIPTION HERE. D15 used MuScriptor note-cell F1 because its control was
a PIANOROLL — explicit notes, compared against the roll itself. The morph control is a
CONTOUR stream and the comparison is render-vs-reference AUDIO, which is what MERIT is built
for. It also DISENTANGLES melody from timbre, which matters right now: Kim reports the
full-FT arms sound like "weird glitchy organic noises" while the base arms respond at gain
2.0. A single similarity number cannot separate "melody transferred but timbre is broken"
from "nothing transferred" — S_mel vs S_tim can.

THE CONTROL ARMS, both mandatory (audit-the-instrument, CLAUDE.md):
  null      the same model with the projection zeroed = the true negative for "did the
            control do anything". A conditioned score means nothing without it.
  foreign   the same cell scored against a DIFFERENT stem's reference = the floor. Without
            it we cannot tell a real S_mel from the value any two goa clips get for being
            goa. This is the arm that would have caught the chroma-metric failure in D15.
Report DELTAS against those, never the raw cosine.

Embeds each clip ONCE and caches, so all pairings are free after the first pass.

  eval/morph_merit.py --renders <dir> --out eval/morph_merit.json [--device cpu]
"""
import argparse, json, os, sys, glob, random
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
RENDERS = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/morph"


def load_wav(p):
    """Return (C,T), which is what MeritScorer.embed expects.

    soundfile returns (T,C) for stereo; embed() does wav.mean(0) for a 2-D input, so
    handing it (T,C) averages over TIME and leaves a 2-sample "waveform". That raised a
    kernel-size error here only because C=2 is smaller than the conv kernel — with more
    channels it would have silently embedded noise and produced plausible numbers.
    """
    import soundfile as sf
    import numpy as np
    w, sr = sf.read(p, always_2d=False)
    if w.ndim == 2:
        w = w.T                      # (T,C) -> (C,T)
    return np.ascontiguousarray(w), sr


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", default=RENDERS)
    ap.add_argument("--out", type=Path, default=Path("eval/morph_merit.json"))
    ap.add_argument("--device", default=os.environ.get("MERIT_DEVICE", "cpu"))
    ap.add_argument("--limit", type=int, default=0, help="score only N cells (smoke test)")
    args = ap.parse_args()

    from control.sa3_control.merit_eval import MeritScorer, FACTORS

    cells = []
    for f in sorted(glob.glob(f"{args.renders}/*/*.json")):
        d = json.load(open(f))
        wav = f[:-5] + ".wav"
        if not os.path.exists(wav):
            continue
        cells.append({"wav": wav, "arm": os.path.basename(os.path.dirname(f)),
                      "stem": str(d.get("stem")), "vocab": d.get("vocab"),
                      "backbone": "full-FT" if str(d.get("backbone", "")).startswith("/scratch")
                                  else "medium-base",
                      "cond": bool(d.get("conditioned")),
                      "gain": None if not d.get("conditioned") else float(d.get("gain", 1.0))})
    refs = {}
    for w in glob.glob(f"{args.renders}/*/refs/*.wav"):
        stem = os.path.basename(w)[:-4].replace("ref__", "")
        refs.setdefault(stem, w)
    if args.limit:
        cells = cells[:args.limit]
    print(f"cells {len(cells)} · refs {len(refs)} · device {args.device}", flush=True)
    if not cells or not refs:
        sys.exit("no cells or no refs — check --renders")

    sc = MeritScorer(device=args.device)

    # SELF-CHECK before any real number: identical input must score ~1.0 on every factor.
    # A head that does not do that is not measuring similarity and nothing below is valid.
    w0, sr0 = load_wav(next(iter(refs.values())))
    self_sim = sc.score(w0, sr0, w0, sr0)
    print(f"[self-check] identical clip: {self_sim}", flush=True)
    if min(self_sim.values()) < 0.98:
        sys.exit(f"MERIT self-similarity {self_sim} is not ~1.0 — instrument is wrong, aborting")

    emb = {}
    def E(p):
        if p not in emb:
            w, sr = load_wav(p)
            emb[p] = {k: v.detach().cpu() for k, v in sc.embed(w, sr).items()}
        return emb[p]

    def cos(a, b):
        ea, eb = E(a), E(b)
        return {f"S_{f}": float((ea[f] * eb[f]).sum().item()) for f in FACTORS}

    stems = sorted(refs)
    rows = []
    for i, c in enumerate(cells, 1):
        own = refs.get(c["stem"])
        if not own:
            continue
        # FOREIGN BASELINE = mean over EVERY other stem, not one draw. A single foreign
        # reference is far too noisy to be a floor: in the 6-cell smoke run one draw scored
        # HIGHER than the true reference (0.801 vs 0.663), which would read as "the control
        # did nothing" purely from the draw. Averaging the 7 alternatives is nearly free
        # because embeddings are cached, and it is the difference between a baseline and a
        # coin flip.
        others = [s for s in stems if s != c["stem"]]
        fscores = [cos(c["wav"], refs[o]) for o in others]
        r = dict(c)
        r.update({f"own_{k}": v for k, v in cos(c["wav"], own).items()})
        for k in fscores[0]:
            vals = [f[k] for f in fscores]
            r[f"foreign_{k}"] = sum(vals) / len(vals)
            r[f"foreignmax_{k}"] = max(vals)
        r["n_foreign"] = len(others)
        rows.append(r)
        if i % 40 == 0:
            print(f"  {i}/{len(cells)}", flush=True)

    args.out.write_text(json.dumps({"rows": rows, "self_check": self_sim,
                                    "n_cells": len(rows)}, indent=1) + "\n")
    print(f"wrote {args.out}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
