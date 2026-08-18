#!/usr/bin/env python3
"""trajectory_sketch_analyze.py — read a step-resolution trajectory recorded by
stable-audio-3/scripts/trajectory_sketch.py and say how the run actually moved.

WHAT IT ANSWERS (C, 2026-08-18; Kim: "see how the trajectory really is")
  1. Is the walk drifting or diffusing, and at which timescale?  multiscale path efficiency
     eff(w) = |Σ_{t..t+w} u| / Σ|u| averaged over start points, against the 1/sqrt(w) random-walk
     line. Drift+noise rises toward a plateau; pure diffusion sits ON the line at every w.
  2. How long does an update "remember" its direction?  autocorrelation cos(u_t, u_{t+τ}) vs τ.
     Adam's momentum alone gives rho^τ (rho = beta1 = 0.9 -> ~10 steps) on PURE-NOISE gradients,
     so short-lag correlation is not evidence of learning; correlation at τ >> 10 is.
  3. How much of the gradient is signal?  window SNR = |Σ_w g|² / (w Σ|g|²): 1/w for pure noise,
     -> 1 for a constant direction. And cos(u_t, g_t), cos(u_t, mean of the last-w grads).
  4. WHERE does the walk happen?  per-tensor update energy by site/block over time.
  5. (ckpts present) singular-spectrum concentration of B·A per matrix over steps: top-1 fraction
     and effective rank — the flat-vs-spike axis from task_vector_gram/spike.
  6. (several dirs, same sketch seed) cross-run: cos between the runs' cumulative displacements
     over time — do bs1 and bs8 walk in the same direction, just at different noise?
Sketch algebra: rows are CountSketch images, so every inner product below is an unbiased estimate of
the true one (rel. error ~1/sqrt(4096) ≈ 1.6 %); nothing here needs the raw coordinates.

USAGE
  .venv/bin/python eval/trajectory_sketch_analyze.py <run>/traj [<run2>/traj ...] [--png out.png]
  [--ckpt-every-n 20]   (spectra: read every n-th saved ckpt; 0 = skip spectra)
CPU, numpy (+ torch only for the ckpt spectra). Text report to stdout and <traj>/analysis.txt.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

import numpy as np

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")


# ---------------------------------------------------------------------------------------------
# pure functions (tested)
# ---------------------------------------------------------------------------------------------

def step_cos_series(U):
    n = np.linalg.norm(U, axis=1)
    num = (U[1:] * U[:-1]).sum(1)
    den = n[1:] * n[:-1]
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def autocorr_cos(U, lags=(1, 2, 3, 5, 8, 12, 20, 30, 50, 100, 200, 500, 1000)):
    """mean over t of cos(u_t, u_{t+τ}), for each τ that fits."""
    n = np.linalg.norm(U, axis=1)
    out_l, out_c = [], []
    for l in lags:
        if l >= len(U) - 1:
            break
        num = (U[l:] * U[:-l]).sum(1); den = n[l:] * n[:-l]
        ok = den > 0
        out_l.append(l); out_c.append(float((num[ok] / den[ok]).mean()) if ok.any() else np.nan)
    return out_l, out_c


def multiscale_efficiency(U, windows=(1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096), stride_frac=0.25):
    """eff(w) = |X_{t+w} − X_t| / Σ|u| over the window, averaged over start points t."""
    X = np.vstack([np.zeros((1, U.shape[1])), np.cumsum(U, axis=0)])
    L = np.linalg.norm(U, axis=1); Lc = np.concatenate([[0.0], np.cumsum(L)])
    out_w, out_e = [], []
    for w in windows:
        if w > len(U):
            break
        stride = max(1, int(w * stride_frac))
        starts = np.arange(0, len(U) - w + 1, stride)
        net = np.linalg.norm(X[starts + w] - X[starts], axis=1)
        path = Lc[starts + w] - Lc[starts]
        ok = path > 0
        out_w.append(w); out_e.append(float((net[ok] / path[ok]).mean()) if ok.any() else np.nan)
    return out_w, out_e


def window_snr(G, windows=(1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024), stride_frac=0.25):
    """|Σ_w g|² / (w Σ_w |g|²): 1/w for iid noise, 1 for a constant direction."""
    X = np.vstack([np.zeros((1, G.shape[1])), np.cumsum(G, axis=0)])
    E = np.concatenate([[0.0], np.cumsum((G * G).sum(1))])
    out_w, out_s = [], []
    for w in windows:
        if w > len(G):
            break
        stride = max(1, int(w * stride_frac))
        starts = np.arange(0, len(G) - w + 1, stride)
        num = np.linalg.norm(X[starts + w] - X[starts], axis=1) ** 2
        den = w * (E[starts + w] - E[starts])
        ok = den > 0
        out_w.append(w); out_s.append(float((num[ok] / den[ok]).mean()) if ok.any() else np.nan)
    return out_w, out_s


# ---------------------------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------------------------

def load_traj(d):
    meta = json.load(open(os.path.join(d, "params.json")))
    n = None
    if os.path.exists(os.path.join(d, "done.json")):
        n = json.load(open(os.path.join(d, "done.json")))["rows_written"]
    sc = np.load(os.path.join(d, "scalars.npy"), mmap_mode="r")
    if n is None:                                   # still running: rows with wall_s > 0
        n = int((sc[:, 3] > 0).sum())
    U = np.array(np.load(os.path.join(d, "upd_sketch.npy"), mmap_mode="r")[:n], dtype=np.float64)
    G = np.array(np.load(os.path.join(d, "grad_sketch.npy"), mmap_mode="r")[:n], dtype=np.float64)
    UN = np.array(np.load(os.path.join(d, "upd_norms.npy"), mmap_mode="r")[:n], dtype=np.float64)
    GN = np.array(np.load(os.path.join(d, "grad_norms.npy"), mmap_mode="r")[:n], dtype=np.float64)
    return {"dir": d, "meta": meta, "n": n, "U": U, "G": G, "UN": UN, "GN": GN,
            "scal": np.array(sc[:n]), "name": os.path.basename(os.path.dirname(os.path.abspath(d)))}


def site_of(name):
    for s, pat in (("q", r"\.to_q\."), ("k", r"\.to_k\."), ("v", r"\.to_v\."), ("out", r"\.to_out\."),
                   ("ff", r"\.ff\."), ("cross", r"cross_attn"), ("cond", r"conditioner")):
        if re.search(pat, name):
            return s
    return "other"


def spectra_over_steps(d, every_n=20, max_ckpts=60):
    """top-1 σ² fraction and effective rank of B·A, median over matrices, per saved ckpt."""
    import torch
    torch.set_num_threads(4)
    ps = sorted(glob.glob(os.path.join(d, "ckpt", "step*.pt")),
                key=lambda p: int(re.search(r"step(\d+)", p).group(1)))
    if not ps:
        return []
    ps = ps[::every_n]
    if len(ps) > max_ckpts:
        ps = ps[:: math.ceil(len(ps) / max_ckpts)]
    out = []
    for p in ps:
        sd = torch.load(p, map_location="cpu")["state_dict"]
        pre = sorted({k.rsplit(".", 1)[0] for k in sd if k.endswith("lora_A")})
        t1, er = [], []
        for q in pre:
            A = sd[q + ".lora_A"].float(); B = sd[q + ".lora_B"].float()
            Qb, Rb = torch.linalg.qr(B); Qa, Ra = torch.linalg.qr(A.T)
            s = torch.linalg.svdvals(Rb @ Ra.T); s2 = s * s
            if s2.sum() > 0:
                t1.append(float(s2[0] / s2.sum())); er.append(float(s.sum() ** 2 / s2.sum()))
        t1.sort(); er.sort()
        out.append((int(re.search(r"step(\d+)", p).group(1)), t1[len(t1) // 2], er[len(er) // 2],
                    int(B.shape[1])))
    return out


# ---------------------------------------------------------------------------------------------

def report_one(T, P, ckpt_every_n):
    U, G, n = T["U"], T["G"], T["n"]
    P(f"=== {T['name']}   {n} optimizer steps, D={T['meta']['D']:,} trainable, sketch {U.shape[1]}-d")
    sc = T["scal"]
    P(f"  loss first/last 100 mean: {np.nanmean(sc[:100,1]):.3f} / {np.nanmean(sc[-100:,1]):.3f}   "
      f"lr {sc[0,2]:.1e}   wall {sc[-1,3]/60:.0f} min")
    un = np.linalg.norm(U, axis=1); gn = np.linalg.norm(G, axis=1)
    P(f"  |update| first10 {un[:10].mean():.4f}  mid {un[n//2-50:n//2+50].mean():.4f}  last100 {un[-100:].mean():.4f}"
      f"    |grad| first10 {gn[:10].mean():.2f}  last100 {gn[-100:].mean():.2f}")
    # 1. multiscale efficiency
    ws, eff = multiscale_efficiency(U)
    P("  path efficiency vs window (net/path):   [random walk = 1/sqrt(w)]")
    P("    w     " + " ".join(f"{w:>6d}" for w in ws))
    P("    eff   " + " ".join(f"{e:>6.3f}" for e in eff))
    P("    1/√w  " + " ".join(f"{1/math.sqrt(w):>6.3f}" for w in ws))
    # 2. autocorrelation
    lags, ac = autocorr_cos(U); lg, acg = autocorr_cos(G)
    P("  autocorrelation cos(x_t, x_{t+τ}):      [Adam momentum alone: 0.9^τ]")
    P("    τ      " + " ".join(f"{l:>6d}" for l in lags))
    P("    update " + " ".join(f"{c:>6.3f}" for c in ac))
    P("    grad   " + " ".join(f"{c:>6.3f}" for c in acg[:len(lags)]))
    P("    0.9^τ  " + " ".join(f"{0.9**l:>6.3f}" for l in lags))
    # 3. gradient SNR + update/grad alignment
    ws2, snr = window_snr(G)
    P("  gradient window SNR |Σg|²/(wΣ|g|²):    [pure noise = 1/w]")
    P("    w     " + " ".join(f"{w:>6d}" for w in ws2))
    P("    snr   " + " ".join(f"{s:>6.3f}" for s in snr))
    P("    1/w   " + " ".join(f"{1/w:>6.3f}" for w in ws2))
    cug = (U * G).sum(1) / np.maximum(un * gn, 1e-30)
    P(f"  cos(update_t, grad_t): mean {np.nanmean(cug):+.3f}   (SGD would be -1; Adam+momentum is weakly negative)")
    for w in (10, 100, 1000):
        if w < n:
            Gm = np.cumsum(G, 0); Gw = (Gm[w:] - Gm[:-w]) / w
            c = (U[w:] * Gw).sum(1) / np.maximum(np.linalg.norm(U[w:], axis=1) * np.linalg.norm(Gw, axis=1), 1e-30)
            P(f"  cos(update_t, mean grad over last {w:>4d}): {np.nanmean(c):+.3f}")
    # 4. where
    names = T["meta"]["names"]; UN = T["UN"]
    by = {}
    for j, nm in enumerate(names):
        by.setdefault(site_of(nm), []).append(j)
    tot = (UN ** 2).sum()
    P("  update energy by site (whole run):  " + "  ".join(
        f"{s} {100*(UN[:, idx]**2).sum()/tot:.0f}%" for s, idx in sorted(by.items(), key=lambda kv: -(UN[:, kv[1]]**2).sum())))
    early = (UN[:max(1, n//10)] ** 2).sum(0); late = (UN[-max(1, n//10):] ** 2).sum(0)
    blk = {}
    for j, nm in enumerate(names):
        m = re.search(r"layers\.(\d+)\.", nm)
        b = int(m.group(1)) if m else -1
        blk.setdefault(b, [0.0, 0.0]); blk[b][0] += early[j]; blk[b][1] += late[j]
    P("  update energy share by block, first 10% -> last 10% of the run:")
    P("    " + " ".join(f"L{b:02d}:{100*blk[b][0]/early.sum():.0f}>{100*blk[b][1]/late.sum():.0f}" for b in sorted(blk) if b >= 0))
    # 5. spectra
    if ckpt_every_n:
        sp = spectra_over_steps(T["dir"], ckpt_every_n)
        if sp:
            r = sp[0][3]
            P(f"  B·A spectrum over steps (median over matrices; flat rank-{r} = top1 {1/r:.3f}, eff-rank {r}):")
            P("    step   " + " ".join(f"{s:>6d}" for s, _, _, _ in sp))
            P("    top1   " + " ".join(f"{t:>6.3f}" for _, t, _, _ in sp))
            P("    effrk  " + " ".join(f"{e:>6.1f}" for _, _, e, _ in sp))
    P("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--ckpt-every-n", type=int, default=20)
    ap.add_argument("--png", default=None)
    a = ap.parse_args()
    Ts = [load_traj(d) for d in a.dirs]
    L = []; P = L.append
    for T in Ts:
        report_one(T, P, a.ckpt_every_n)
    if len(Ts) > 1:
        P("=== cross-run (same sketch seed): cos of cumulative displacement at matched step counts")
        seeds = {T["meta"]["sketch_seed"] for T in Ts}
        if len(seeds) != 1:
            P("  sketch seeds differ — cross-run inner products are meaningless; skipped")
        else:
            X = [np.cumsum(T["U"], 0) for T in Ts]
            for i in range(len(Ts)):
                for j in range(i + 1, len(Ts)):
                    m = min(len(X[i]), len(X[j]))
                    pts = [p for p in (10, 100, 300, 1000, 3000, m - 1) if p < m]
                    c = [float(X[i][p] @ X[j][p] / (np.linalg.norm(X[i][p]) * np.linalg.norm(X[j][p]) + 1e-30)) for p in pts]
                    P(f"  {Ts[i]['name']} vs {Ts[j]['name']}: " + " ".join(f"@{p}:{v:+.3f}" for p, v in zip(pts, c)))
        P("")
    P("READ: eff(w) on the 1/√w line at all w = diffusion (no direction survives); rising above it = drift.")
    P("      update autocorr at τ ≤ 10 is momentum, not learning; at τ ≥ 100 it is learning (or runaway).")
    P("      SNR ≈ 1/w means the gradient carries no repeatable direction at that window.")
    rep = "\n".join(L)
    print(rep)
    for T in Ts:
        open(os.path.join(T["dir"], "analysis.txt"), "w").write(rep + "\n")
    if a.png:
        try:
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            fig, ax = plt.subplots(1, 3, figsize=(15, 4))
            for T in Ts:
                ws, eff = multiscale_efficiency(T["U"]); ax[0].plot(ws, eff, "o-", label=T["name"])
                lags, ac = autocorr_cos(T["U"]); ax[1].plot(lags, ac, "o-", label=T["name"])
                ws2, snr = window_snr(T["G"]); ax[2].plot(ws2, snr, "o-", label=T["name"])
            ax[0].plot(ws, [1/math.sqrt(w) for w in ws], "k--", label="1/√w"); ax[0].set_xscale("log"); ax[0].set_title("path efficiency vs window")
            ax[1].plot(lags, [0.9**l for l in lags], "k--", label="0.9^τ"); ax[1].set_xscale("log"); ax[1].set_title("update autocorr")
            ax[2].plot(ws2, [1/w for w in ws2], "k--", label="1/w"); ax[2].set_xscale("log"); ax[2].set_yscale("log"); ax[2].set_title("grad window SNR")
            for x in ax: x.legend(fontsize=7); x.grid(alpha=.3)
            fig.tight_layout(); fig.savefig(a.png, dpi=110); print(f"-> {a.png}")
        except Exception as e:
            print(f"[png skipped: {e}]")


if __name__ == "__main__":
    main()
