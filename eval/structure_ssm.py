#!/usr/bin/env python3
"""
structure_ssm.py -- large-scale MUSICAL STRUCTURE via self-similarity matrices (Kim 2026-07-22,
from the Stable Audio longform paper §4.4). The one axis CLAP/mood-drift/spectral-fidelity DON'T
touch: does a long generation build coherent FORM (intro→develop→recall→outro), or fall into the
paper's two failure modes -- (a) never repeating (meandering) or (b) stuck in a loop (a section
that won't evolve = the droning-pad collapse at the structural level). Most meaningful on the
NATIVE-LENGTH clips (190-380 s); says little on a 20 s grid cell.

An SSM is a frame×frame cosine-similarity matrix over a feature (chroma here; MAEST optional).
From it we derive three interpretable scalars (turning the paper's visual comparison into metrics):
  boundaries_per_min : Foote checkerboard-novelty peak rate = section count. Too few = meandering.
  recall             : p90 of FAR off-diagonal similarity (|i-j| > L/4) = do LATE sections resemble
                       EARLY ones (the paper's red marks / motif recall). High = real longform form.
  loop_score         : max over 30 s windows of mean intra-window similarity = the most homogeneous
                       stretch = the 'stuck'/drone section (the paper's blue). High = pad-fill/loop.
Plus mean_ssm (overall self-similarity: high = static/repetitive, low = varied).

Corpus baseline (--corpus-ref): the SAME metrics on goa/avp real tracks, read straight from the
existing whole-track hpcp_ts timeseries (no re-extraction), downsampled to the analysis rate ->
structural drift-from-source, a sibling of corpus_reference.json's stereo/mood baselines.

RUN (mir venv):
  # native eval clips:
  mir/bin/python eval/structure_ssm.py --sample-per-model 8 --out /tmp/structure.csv [--save-img DIR]
  # corpus structural reference:
  mir/bin/python eval/structure_ssm.py --corpus-ref --out eval/structure_reference.json
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

CLIPS = Path.home() / ".cache/evals_aac/model_matrix"
CLAP = Path("/home/kim/Projects/SAO/eval/clap_degen_model_matrix.csv")
LT = Path("/run/media/kim/Kosmos/timeseries")
AVP = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed")
HZ = 2.0            # analysis frame rate for structure (coarse -- form is slow)
KERN = 16           # Foote checkerboard half-width (frames) ~= 8 s at 2 Hz


def _checkerboard(L):
    g = np.outer(np.hanning(2 * L), np.hanning(2 * L))
    s = np.ones((2 * L, 2 * L))
    s[:L, L:] = -1; s[L:, :L] = -1               # +/-/-/+ checkerboard
    return g * s


def ssm_from_chroma(C):
    """C: (n_frames, 12) -> RECURRENCE affinity SSM (n,n). Raw chroma-cosine saturates near 1
    (tonal music -> all frames similar); the paper uses binary/affinity SSMs precisely to make
    off-diagonal STRUCTURE stand out. librosa k-NN recurrence affinity does that: ~0 everywhere
    except genuinely recurrent frame pairs, so far-off-diagonal energy becomes discriminative."""
    import librosa
    n = C.shape[0]
    k = max(3, int(0.04 * n))                     # ~4% nearest neighbours
    R = librosa.segment.recurrence_matrix(
        C.T, k=k, width=int(HZ * 4), sym=True, mode="affinity")   # width: ignore |i-j|<4s
    return np.asarray(R, dtype=np.float64)


def structure_metrics(S, dur):
    from scipy.signal import find_peaks
    n = S.shape[0]
    if n < 2 * KERN + 4:
        return None
    # boundaries via Foote novelty
    g = _checkerboard(KERN)
    nov = np.zeros(n)
    for i in range(KERN, n - KERN):
        nov[i] = float((S[i - KERN:i + KERN, i - KERN:i + KERN] * g).sum())
    nov = np.clip(nov, 0, None)
    nov /= (nov.max() + 1e-9)
    peaks, _ = find_peaks(nov, height=0.30, distance=int(HZ * 8))     # >=8 s apart
    bpm_struct = len(peaks) / (dur / 60.0 + 1e-9)
    # long-range recall: the strongest FAR-lag diagonal STRIPE = a late section repeating an
    # early one (the paper's "diagonal lines" / red marks). Mean affinity along each far diagonal;
    # recall = the best. A thin repeat stripe survives this where a whole-region percentile washes out.
    recall = 0.0
    minstripe = int(HZ * 8)                                  # a repeat worth counting >= 8 s
    for tau in range(int(0.25 * n), n - minstripe):
        diag = np.diagonal(S, offset=tau)
        if diag.size >= minstripe:
            recall = max(recall, float(diag.mean()))
    # loop / homogeneity: most self-similar 30 s window
    W = max(4, int(30 * HZ))
    loop = 0.0
    for s in range(0, max(1, n - W), max(1, W // 2)):
        loop = max(loop, float(S[s:s + W, s:s + W].mean()))
    return {"boundaries_per_min": round(bpm_struct, 3), "recall": round(recall, 3),
            "loop_score": round(loop, 3), "mean_ssm": round(float(S.mean()), 3), "n_frames": n}


def eval_clip_chroma(path):
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = int(sr / HZ)
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop).T          # (n,12)
    return C, len(y) / sr


def corpus_reference(out):
    """Structural baseline from the whole-track hpcp_ts timeseries (goa + avp), no re-extraction."""
    import glob
    files = glob.glob(str(LT / "*.npz"))
    if AVP.exists():
        files += glob.glob(str(AVP / "**" / "*.TIMESERIES.npz"), recursive=True)
    acc = {"goa": [], "avp": []}
    for f in files:
        try:
            d = np.load(f, allow_pickle=True)
            meta = json.loads(str(d["__meta__"])) if "__meta__" in d.files else {}
        except Exception:
            continue
        src = (meta.get("source") or "").lower()
        corp = "goa" if "goa_separated" in src else ("avp" if "avp" in src else None)
        if corp is None or len(acc[corp]) >= 400 or "hpcp_ts" not in d.files:
            continue
        hp = np.asarray(d["hpcp_ts"], dtype=np.float64)                  # (N,12) @ ~100 Hz
        rate = meta.get("frame_rate", 100)
        step = max(1, int(round(rate / HZ)))
        C = hp[::step]                                                   # downsample to ~HZ
        if C.shape[0] < 2 * KERN + 4:
            continue
        try:
            m = structure_metrics(ssm_from_chroma(C), C.shape[0] / HZ)
        except Exception:
            continue                                                     # degenerate k-NN graph -> skip
        if m:
            acc[corp].append(m)
    ref = {}
    for c in ("goa", "avp"):
        if acc[c]:
            arr = {k: np.array([x[k] for x in acc[c]]) for k in ("boundaries_per_min", "recall", "loop_score", "mean_ssm")}
            ref[c] = {k: {"mean": round(float(v.mean()), 3), "std": round(float(v.std()), 3)} for k, v in arr.items()}
            ref[c]["n"] = len(acc[c])
    Path(out).write_text(json.dumps(ref, indent=1))
    print(f"[struct-ref] wrote {out}")
    for c in ("goa", "avp"):
        if c in ref:
            print(f"  {c}: bounds/min {ref[c]['boundaries_per_min']['mean']} · recall {ref[c]['recall']['mean']} · "
                  f"loop {ref[c]['loop_score']['mean']} · mean_ssm {ref[c]['mean_ssm']['mean']}  (n={ref[c]['n']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-ref", action="store_true", help="build the goa/avp structural baseline instead")
    ap.add_argument("--sample-per-model", type=int, default=8)
    ap.add_argument("--native-only", action="store_true", default=True, help="only long native clips (structure needs length)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--save-img", type=Path, default=None, help="dir to save SSM PNGs (optional)")
    a = ap.parse_args()

    if a.corpus_ref:
        corpus_reference(a.out)
        return

    rows = [r for r in csv.DictReader(CLAP.open())]
    # native clips = the long ones (d190/d380 in filename)
    rows = [r for r in rows if ("_d190" in r["file"] or "_d380" in r["file"])]
    by = {}
    for r in rows:
        by.setdefault(r["model"], []).append(r)
    sel = []
    for rs in by.values():
        step = max(1, len(rs) // a.sample_per_model)
        sel += rs[::step][:a.sample_per_model]
    print(f"[struct] {len(sel)} native clips over {len(by)} models")

    out = []
    for i, r in enumerate(sel):
        p = CLIPS / r["file"]
        if not p.exists():
            continue
        try:
            C, dur = eval_clip_chroma(p)
            m = structure_metrics(ssm_from_chroma(C), dur)
        except Exception as ex:
            print(f"[struct] skip {r['file']}: {ex}")
            continue
        if m is None:
            continue
        m.update({"file": r["file"], "model": r["model"], "ckpt": r["ckpt"],
                  "cfg": r["cfg"], "strength": r["strength"], "clap_matched": r.get("clap_matched"),
                  "dur": round(dur, 1)})
        out.append(m)
        if a.save_img:
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                a.save_img.mkdir(parents=True, exist_ok=True)
                plt.figure(figsize=(4, 4)); plt.imshow(ssm_from_chroma(C), origin="lower", cmap="magma")
                plt.title(r["file"][:40], fontsize=6); plt.axis("off")
                plt.savefig(a.save_img / (p.stem + ".png"), dpi=80, bbox_inches="tight"); plt.close()
            except Exception:
                pass
        if (i + 1) % 20 == 0:
            print(f"[struct] {i + 1}/{len(sel)}")

    cols = ["file", "model", "ckpt", "cfg", "strength", "clap_matched", "dur",
            "boundaries_per_min", "recall", "loop_score", "mean_ssm", "n_frames"]
    with a.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k) for k in cols})
    print(f"[struct] wrote {a.out} ({len(out)} clips)")


if __name__ == "__main__":
    main()
