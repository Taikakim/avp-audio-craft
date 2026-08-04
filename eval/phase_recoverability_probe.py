#!/usr/bin/env python
"""phase_recoverability_probe.py — G2 of the reality-structured plan (spec
docs/superpowers/specs/2026-07-31-reality-structured-model-experiments.md).

Question: do SAME latents carry recoverable PHASE, or is phase entirely the decoder's?
Gates the complex/PhaseSpin/Kuramoto branch. Nyquist caveat honored: at 10.77 Hz the
latent can at most carry SLOW-MODULATION phase (band-envelope phase, beat phase), never
audio-partial phase.

Design: K tracks from Goa_Separated (with .BEATS_GRID), encode a 95 s segment each
(SAME encode, GPU), then per frame predict from z[256]:
  (a) per-octave-band envelope Hilbert phase (envelope low-passed < 4 Hz),
  (b) beat-relative phase from the BEATS_GRID (2*pi * fractional inter-beat position),
via ridge readout onto (cos phi, sin phi), TRACK-LEVEL split-half (phase-fair folds —
the probe-method lesson), scored as circular R^2 = 1 - (1 - R2_cos+sin avg) equivalent:
we report R^2 on cos & sin jointly and the resultant vector length of angular residuals.

Verdicts (spec): circ-R2 >= .5 on (a) or (b) => phase-native weights plausible;
< .2 => branch closed (phase is the decoder's).

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/phase_recoverability_probe.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, hilbert, sosfiltfilt, resample_poly

from stable_audio_3 import StableAudioModel

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/phase_probe")
SEG = (60.0, 155.108)          # 95.108 s -> T=1024 latent frames
N_TRACKS = 24
BANDS = [(60, 120), (120, 250), (250, 500), (500, 1000),
         (1000, 2000), (2000, 4000), (4000, 8000)]
FRATE = 10.7666015625          # latent frame rate


def band_env_phase(y, sr, lo, hi, n_frames):
    """Hilbert phase of the <4 Hz band-envelope, resampled to the latent grid."""
    sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    b = sosfiltfilt(sos, y)
    env = np.abs(b)
    sos_lp = butter(4, 4.0, btype="low", fs=sr, output="sos")
    env = sosfiltfilt(sos_lp, env)
    dec = int(sr // 100)
    env100 = resample_poly(env, 1, dec)          # ~100 Hz intermediate
    env100 = env100 - env100.mean()
    ph = np.angle(hilbert(env100))
    idx = np.clip((np.arange(n_frames) / FRATE * (sr / dec)).astype(int), 0, len(ph) - 1)
    return ph[idx]


def beat_phase(grid_file, n_frames):
    beats = np.array([float(l.split()[0]) for l in open(grid_file) if l.strip()])
    t = SEG[0] + np.arange(n_frames) / FRATE
    idx = np.searchsorted(beats, t) - 1
    ok = (idx >= 0) & (idx < len(beats) - 1)
    ph = np.full(n_frames, np.nan)
    ph[ok] = 2 * np.pi * ((t[ok] - beats[idx[ok]]) / (beats[idx[ok] + 1] - beats[idx[ok]]))
    return ph - np.pi        # [-pi, pi]


def ridge_circ(Ztr, phtr, Zte, phte, lam=10.0):
    """Ridge z -> (cos,sin); return held-out circular concordance (mean resultant of
    angular error) and joint R^2 on cos/sin."""
    ok_tr, ok_te = ~np.isnan(phtr), ~np.isnan(phte)
    Xtr, Xte = Ztr[ok_tr], Zte[ok_te]
    Ytr = np.stack([np.cos(phtr[ok_tr]), np.sin(phtr[ok_tr])], 1)
    Yte = np.stack([np.cos(phte[ok_te]), np.sin(phte[ok_te])], 1)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
    W = np.linalg.solve(Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1]), Xtr.T @ Ytr)
    P = Xte @ W
    r2 = 1 - ((Yte - P) ** 2).sum() / ((Yte - Yte.mean(0)) ** 2).sum()
    ang_err = np.angle(np.exp(1j * (np.arctan2(P[:, 1], P[:, 0]) -
                                    np.arctan2(Yte[:, 1], Yte[:, 0]))))
    concord = float(np.abs(np.mean(np.exp(1j * ang_err))))   # 1 = perfect, 0 = chance
    return float(r2), concord


def mlp_circ(Ztr, phtr, Zte, phte):
    """Small MLP readout (nonlinear check on the same split)."""
    from sklearn.neural_network import MLPRegressor
    ok_tr, ok_te = ~np.isnan(phtr), ~np.isnan(phte)
    Xtr, Xte = Ztr[ok_tr], Zte[ok_te]
    Ytr = np.stack([np.cos(phtr[ok_tr]), np.sin(phtr[ok_tr])], 1)
    Yte = np.stack([np.cos(phte[ok_te]), np.sin(phte[ok_te])], 1)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
    m = MLPRegressor(hidden_layer_sizes=(128,), max_iter=60, early_stopping=True,
                     random_state=1)
    m.fit(Xtr, Ytr)
    P = m.predict(Xte)
    r2 = 1 - ((Yte - P) ** 2).sum() / ((Yte - Yte.mean(0)) ** 2).sum()
    ang_err = np.angle(np.exp(1j * (np.arctan2(P[:, 1], P[:, 0]) -
                                    np.arctan2(Yte[:, 1], Yte[:, 0]))))
    return float(r2), float(np.abs(np.mean(np.exp(1j * ang_err))))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tracks = sorted(d for d in CORPUS.iterdir()
                    if (d / "full_mix.flac").exists()
                    and (d / f"{d.name}.BEATS_GRID").exists())[:N_TRACKS]
    print(f"[probe] {len(tracks)} tracks")

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    mdtype = next(cdm.model.parameters()).dtype
    device = next(cdm.model.parameters()).device

    Z, PH = [], []      # per track: [T,256], {target: [T]}
    for d in tracks:
        audio, sr = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True)
        if audio.shape[0] < int(SEG[1] * sr):
            continue
        seg = audio[int(SEG[0] * sr):int(SEG[1] * sr)].T
        with torch.no_grad():
            z = cdm.pretransform.encode(
                torch.tensor(seg[None]).to(device, mdtype))
        z = z[0].float().cpu().numpy().T          # [T,256]
        n = z.shape[0]
        mono = seg.mean(0)
        tgt = {f"band_{lo}-{hi}": band_env_phase(mono, sr, lo, hi, n)
               for lo, hi in BANDS}
        tgt["beat"] = beat_phase(d / f"{d.name}.BEATS_GRID", n)
        Z.append(z); PH.append(tgt)
        print(f"[enc] {d.name[:40]}: T={n}", flush=True)
    np.savez_compressed(OUT / "probe_arrays.npz",
                        **{f"z_{i}": z for i, z in enumerate(Z)},
                        **{f"ph_{i}_{k}": v for i, p_ in enumerate(PH) for k, v in p_.items()})

    k = len(Z) // 2
    Ztr, Zte = np.concatenate(Z[:k]), np.concatenate(Z[k:])
    results = {}
    print(f"\n{'target':<16} {'R2':>7} {'circ-concord':>13}")
    for name in PH[0]:
        ptr = np.concatenate([p[name] for p in PH[:k]])
        pte = np.concatenate([p[name] for p in PH[k:]])
        r2, cc = ridge_circ(Ztr, ptr, Zte, pte)
        r2m, ccm = mlp_circ(Ztr, ptr, Zte, pte)
        results[name] = {"r2": round(r2, 4), "circ_concordance": round(cc, 4),
                         "mlp_r2": round(r2m, 4), "mlp_circ_concordance": round(ccm, 4)}
        print(f"{name:<16} {r2:>7.3f} {cc:>13.3f}   mlp: {r2m:.3f} {ccm:.3f}")

    best = max(results.values(), key=lambda r: max(r['circ_concordance'], r['mlp_circ_concordance']))
    bcc = max(best['circ_concordance'], best['mlp_circ_concordance'])
    verdict = ("OPEN (phase-native weights plausible)" if bcc >= 0.5
               else "CLOSED (phase is the decoder's)" if bcc < 0.2
               else "MARGINAL")
    print(f"\nVERDICT: {verdict} (best circ-concordance {bcc})")
    (OUT / "results.json").write_text(json.dumps(
        {"results": results, "verdict": verdict, "n_tracks": len(Z),
         "split": "track-level halves (phase-fair)", "segment_s": SEG,
         "thresholds": {"open": 0.5, "closed": 0.2},
         "method": "SAME-encode 95s segments; ridge z->(cos,sin) of band-envelope Hilbert "
                   "phase (<4Hz) + beat-grid phase; held-out circular concordance",
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
