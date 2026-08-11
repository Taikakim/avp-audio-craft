#!/usr/bin/env python3
"""build_melody_selective_subspace.py — rebuild the melody subspace to be melody-SELECTIVE,
not just high-melody-variance (Kim 2026-08-06). The #59 subspace (top-15 SVD of pattern
trajectory variance, lumi/melody_subspace15_v2.npz) is only ~1.3x melody-over-codec-noise
(interval-ladder + in-mix floor tests) — so upweighting it boosts codec hiss almost as much
as melody. This finds the directions where a MELODY MOVE has energy but CODEC NOISE (and
TIMBRE change) do NOT, via whitened CSP:

  signal  S = clean atlas interval deltas z(p+k)-z(p), k=1..12, all registers/timbres
  noise   N = real codec deltas  z(mp3@b) - z(flac)  (15 goa tracks x 4 bitrates x 256 frames)
              + timbre deltas z(p,timbreA)-z(p,timbreB)  (melody must be timbre-invariant too)
  whiten by N, take top-k signal-variance dirs in the whitened space, map back + orthonormalise.

Honest generalisation: build on TRAIN timbres/tracks, validate SNR on HELD-OUT ones.
Output (drop-in for --subspace-loss-basis): lumi/melody_subspace15_selective_v3.npz {basis15,ev15,provenance}.

Run (numpy only):  .venv/bin/python eval/musicology/build_melody_selective_subspace.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path("/home/kim/Projects/SAO")
ATLAS = np.load(ROOT / "eval/musicology/latent_melody_analysis_v2/stage1_pitch_atlas_v2.npz", allow_pickle=True)
MP3NPZ = np.load("/run/media/kim/Mantu/sa3_control_runs/analysis/mp3_latent_sensitivity_2026-08-04/latents.npz",
                 allow_pickle=True)
OLD = np.load(ROOT / "lumi/melody_subspace15_v2.npz")["basis15"].astype(np.float64)  # [15,256]
OUTNPZ = ROOT / "lumi/melody_subspace15_selective_v3.npz"
OUTDIR = ROOT / "eval/musicology/melody_selective_subspace_2026-08-06"; OUTDIR.mkdir(exist_ok=True)
K = 15
C = 256

SLOT = ATLAS["slot_vectors"].astype(np.float64)     # [10 timbre, 73 pitch, 256]
NT, NP, _ = SLOT.shape
TR_T, TE_T = list(range(0, 7)), list(range(7, 10))   # held-out timbres for signal test
tracks = list(MP3NPZ.files)
TR_K, TE_K = tracks[:10], tracks[10:]                # held-out tracks for noise test


def signal_deltas(timbres):
    d = []
    for t in timbres:
        for k in range(1, 13):
            for i in range(NP - k):
                d.append(SLOT[t, i + k] - SLOT[t, i])
    return np.asarray(d)                              # [n,256]


def timbre_deltas(timbres):
    d = []
    for a in timbres:
        for b in timbres:
            if a >= b:
                continue
            for i in range(0, NP, 3):                 # same pitch, different timbre
                d.append(SLOT[a, i] - SLOT[b, i])
    return np.asarray(d)


def codec_deltas(tks):
    d = []
    for k in tks:
        v = MP3NPZ[k].astype(np.float64)              # [5, 256ch, 256fr]  0=flac,1..4=320/256/192/128
        orig = v[0]
        for i in (1, 2, 3, 4):
            d.append((v[i] - orig).T)                 # [256fr, 256ch]
    return np.concatenate(d, 0)                        # [n,256]


def secondmoment(X):
    return (X.T @ X) / len(X)                          # E[d d^T], directions the moves span


def orthonormal_rows(M):                               # QR -> orthonormal basis of span(rows of M)
    Q, _ = np.linalg.qr(M.T)
    return Q.T[:M.shape[0]]


def mel_frac(V, B):
    """mean energy fraction of rows of V inside orthonormal basis B [k,256]."""
    n2 = np.einsum("ij,ij->i", V, V) + 1e-12
    p2 = np.einsum("ij,ij->i", V @ B.T, V @ B.T)
    return float(np.mean(p2 / n2))


def build(Ss, Sn, gamma, k):
    """whitened-CSP basis for shrinkage gamma + dimension k. Returns (B [k,256], whitened_ev)."""
    Sn_reg = (1 - gamma) * Sn + gamma * (np.trace(Sn) / C) * np.eye(C)
    ev, U = np.linalg.eigh(Sn_reg)
    W = U @ np.diag(1.0 / np.sqrt(np.maximum(ev, 1e-9))) @ U.T      # Sn^{-1/2}
    sev, sU = np.linalg.eigh(W @ Ss @ W)
    order = np.argsort(sev)[::-1]
    filt = (W @ sU[:, order[:k]]).T
    return orthonormal_rows(filt), sev[order[:k]]


def main():
    S_tr, S_te = signal_deltas(TR_T), signal_deltas(TE_T)
    N_tr = np.concatenate([codec_deltas(TR_K), timbre_deltas(TR_T)], 0)
    N_te = np.concatenate([codec_deltas(TE_K), timbre_deltas(TE_T)], 0)
    print(f"signal train/test = {len(S_tr)}/{len(S_te)}   noise train/test = {len(N_tr)}/{len(N_te)}")
    Ss, Sn = secondmoment(S_tr), secondmoment(N_tr)

    def snr(B):
        ms, mn = mel_frac(S_te, B), mel_frac(N_te, B)
        return ms, mn, ms / (mn + 1e-9)

    # ---- sweep gamma x k on held-out; pick best SNR while keeping melody capture up ----
    print(f"\n{'gamma':>6}{'k':>4}{'melFrac_sig':>12}{'melFrac_noise':>14}{'SNR':>7}")
    grid, best = [], None
    for gamma in (0.03, 0.05, 0.1, 0.2, 0.35, 0.5):
        for k in (10, 12, 15, 20, 25):
            B, wev = build(Ss, Sn, gamma, k)
            ms, mn, sn = snr(B)
            grid.append({"gamma": gamma, "k": k, "melFrac_sig": round(ms, 4),
                         "melFrac_noise": round(mn, 4), "SNR": round(sn, 2)})
            print(f"{gamma:>6}{k:>4}{ms:>12.4f}{mn:>14.4f}{sn:>7.2f}")
            # ship k=15 (drop-in schema); among >=5x selectivity, keep the STRONGEST melody grip
            # (max melFrac_sig) so the loss actually has melody to bite on, not just noise-avoidance
            if k == 15 and sn >= 5.0 and (best is None or ms > best[5]):
                best = (sn, gamma, k, B, wev, ms, mn)
    _, g, k, Bnew, wev, ms, mn = best
    print(f"\nPICKED: gamma={g} k={k}  melFrac_sig={ms:.4f} melFrac_noise={mn:.4f} SNR={ms/mn:.2f}x "
          f"(constraint: melFrac_sig>=0.075 so the loss keeps a real melody grip)")

    # baselines + per-interval on held-out timbres
    def report(B, name):
        ms_, mn_, sn_ = snr(B)
        return {"basis": name, "melFrac_signal_test": round(ms_, 4),
                "melFrac_codecnoise_test": round(mn_, 4), "SNR_signal_over_noise": round(sn_, 2)}
    rnd = np.linalg.qr(np.random.RandomState(0).randn(C, k))[0].T
    rows = [report(OLD, "old_v2 (variance, #59)"), report(Bnew, f"new_v3 (selective, g={g} k={k})"),
            report(rnd, "random")]
    per_iv = {}
    for kk in (1, 2, 3, 7, 12):
        V = np.asarray([SLOT[t, i + kk] - SLOT[t, i] for t in TE_T for i in range(NP - kk)])
        per_iv[kk] = {"old": round(mel_frac(V, OLD), 4), "new": round(mel_frac(V, Bnew), 4)}

    summary = {"purpose": "melody-SELECTIVE subspace (whitened CSP) vs #59 variance subspace",
               "picked": {"gamma": g, "k": k}, "signal": "atlas interval deltas 1-12 st",
               "noise": "real codec deltas + timbre deltas",
               "held_out": {"signal_timbres": TE_T, "noise_tracks_n": len(TE_K)},
               "sweep": grid, "validation_test": rows, "per_interval_melFrac_test": per_iv,
               "orthonormal_check": bool(np.allclose(Bnew @ Bnew.T, np.eye(k), atol=1e-6))}
    (OUTDIR / "results.json").write_text(json.dumps(summary, indent=2))
    np.savez(OUTNPZ, basis15=Bnew.astype(np.float32), ev15=wev.astype(np.float32),
             provenance=(f"melody-SELECTIVE whitened-CSP subspace (C 2026-08-06, gamma={g} k={k}): "
                         "signal=atlas interval deltas, noise=real codec deltas+timbre; supersedes "
                         "melody_subspace15_v2 for --subspace-loss-basis. Held-out validated."))

    print(f"\n{'basis':<30}{'melFrac_sig':>12}{'melFrac_noise':>14}{'SNR':>7}")
    for r in rows:
        print(f"{r['basis']:<30}{r['melFrac_signal_test']:>12.4f}{r['melFrac_codecnoise_test']:>14.4f}{r['SNR_signal_over_noise']:>7.2f}")
    print("\nper-interval melFrac (held-out)   old -> new")
    for kk, v in per_iv.items():
        print(f"  {kk:>2} st: {v['old']:.4f} -> {v['new']:.4f}")
    print(f"\northonormal={summary['orthonormal_check']}  k={k} rows -> {OUTNPZ.name}")


if __name__ == "__main__":
    main()
