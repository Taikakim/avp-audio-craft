#!/usr/bin/env python
"""z0_scale_vs_corruption.py — is waveform corruption a LATENT-SCALE phenomenon?

Kim 2026-09-17. GHOST-NOTE's audio_corruption_scan.py found genuine waveform corruption
(adjacent-sample jumps too large to be physical at 44.1 kHz) concentrated in the OOD
genre-fusion renders: clean clips show 0-2 jumps >0.6 in ~47 s, the worst showed 5783-8161.
On 12 fresh renders of my own the count tracked z0 std at rho +0.64 (p=0.026) -- suggestive,
but n=12 and one clip contradicted it within itself.

This is the real-n version. If corruption tracks latent scale across the saved corpus, the
lever is cheap: a latent-scale regulariser or early-stop is PURE LATENT SPACE, no VAE decode
in the training loop. A waveform-discontinuity loss would need one, which is the expensive
meter-in-the-gradient pattern. It also sits correctly inside MASTER's scope condition --
RF loss operates on latents and is structurally blind to what the decoder does with an
off-manifold one.

Reference points: healthy z0 std ~1.13-1.15; the 2026-08-10 full-FT runaway family 5.6;
the 2026-09-08 NaN/DC clips were 100% non-finite and wrote full-scale DC.

WAV ONLY, and that is not a detail. The metric counts single-sample differences, and AAC
decoding changes individual sample values -- a count taken on an .m4a is not comparable to
one taken on a .wav. Clips without a .wav sibling are skipped rather than silently mixed in.

Clustered reporting: one rho per ARM as well as pooled. 75k clips over a few hundred arms is
pseudo-replication, and the standing rule is to cluster at run level or not quote a p-value.

Run:  mir/bin/python eval/z0_scale_vs_corruption.py [--n 2000]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, random
import numpy as np

ROOT = "/run/media/kim/Mantu/sa3_lora_runs/model_matrix"
THRESH = 0.6          # identical to audio_corruption_scan.py


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--out", default="/tmp/z0_corruption.json")
    a = ap.parse_args()
    import soundfile as sf

    z0s = glob.glob(f"{ROOT}/**/*.z0.npy", recursive=True)
    print(f"z0 files on disk: {len(z0s)}", flush=True)
    paired = []
    for z in z0s:
        w = z[:-7] + ".wav"          # strip ".z0.npy"
        if os.path.exists(w):
            paired.append((z, w))
    print(f"with a .wav sibling (the only comparable ones): {len(paired)}", flush=True)
    random.seed(1)
    sample = random.sample(paired, min(a.n, len(paired)))

    rows = []
    for i, (zp, wp) in enumerate(sample):
        try:
            z = np.load(zp, mmap_mode="r")
            zf = np.asarray(z, dtype=np.float32)
            if not np.isfinite(zf).all():
                rows.append({"arm": os.path.basename(zp).split("__")[0],
                             "z0_std": None, "jumps": None, "nonfinite": True})
                continue
            zstd = float(zf.std())
            au, sr = sf.read(wp, always_2d=True)
            m = au.mean(axis=1)
            d = np.abs(np.diff(m))
            rows.append({"arm": os.path.basename(zp).split("__")[0],
                         "z0_std": zstd, "jumps": int((d > THRESH).sum()),
                         "peak": float(np.max(np.abs(au))), "nonfinite": False})
        except Exception:
            pass
        if (i + 1) % 250 == 0:
            print(f"  {i+1}/{len(sample)}", flush=True)

    ok = [r for r in rows if r.get("z0_std") is not None]
    json.dump(rows, open(a.out, "w"))
    print(f"\nmeasured {len(ok)} clips ({sum(1 for r in rows if r.get('nonfinite'))} non-finite z0)")
    if len(ok) < 50:
        print("too few to analyse"); return 1

    from scipy.stats import spearmanr
    x = np.array([r["z0_std"] for r in ok]); y = np.array([r["jumps"] for r in ok])
    rho, p = spearmanr(x, y)
    print(f"\nPOOLED   z0 std vs corruption: rho={rho:+.3f}  p={p:.2e}  n={len(ok)}")

    per = collections.defaultdict(list)
    for r in ok:
        per[r["arm"]].append((r["z0_std"], r["jumps"]))
    rr = []
    for arm, v in per.items():
        if len(v) < 12:
            continue
        xx = np.array([q[0] for q in v]); yy = np.array([q[1] for q in v])
        if np.std(xx) == 0 or np.std(yy) == 0:
            continue
        c, _ = spearmanr(xx, yy)
        if np.isfinite(c):
            rr.append(c)
    if rr:
        from scipy.stats import wilcoxon
        print(f"PER-ARM  median rho {np.median(rr):+.3f}  ({len(rr)} arms, "
              f"wilcoxon p={wilcoxon(rr).pvalue:.3f})")
        print("  pooled >> per-arm would mean the effect is BETWEEN arms, not within one")

    print(f"\n{'z0 std bin':>14s} {'n':>5s} {'median jumps':>13s} {'% >100 jumps':>13s}")
    edges = [0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 99]
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = [r for r in ok if lo <= r["z0_std"] < hi]
        if not s:
            continue
        j = np.array([r["jumps"] for r in s])
        print(f"{lo:5.1f}-{hi:5.1f}  {len(s):5d} {np.median(j):13.0f} "
              f"{100*np.mean(j>100):12.1f}%")
    print(f"\n  healthy z0 std is ~1.13-1.15; the 2026-08-10 runaway family sat at 5.6")
    print(f"[done] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
