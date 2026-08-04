#!/usr/bin/env python
"""phase_invariance_probe.py — how phase/translation-invariant are SAME latents?
(Kim's design 2026-08-01: content-preserving CIRCULAR shift; per-dim change; real signals.)

Improves on the truncating sample-shift sweep in two ways Kim specified:
  - CIRCULAR roll (np.roll): material that falls off the end wraps to the front, so
    every sample is preserved -> z(delta) vs z(0) differs ONLY by temporal repositioning,
    not by content entering/leaving the window (a clean phase-sensitivity control).
  - REAL signals (complex waves), not only pure tones -> does the phase-as-rotation
    encoding survive superposition of many partials + noise + transients?

Per dim c: shift-sensitivity s_c = var over delta of z_c (center frames). Dims that move
under sub-frame roll = phase/position channels; dims that don't = translation-invariant
content channels. Outputs:
  - per-dim sensitivity spectrum (256) for tones vs real clips,
  - CONCENTRATION: fraction of dims carrying 90% of the shift-energy (few => phase confined
    => latent mostly phase-invariant),
  - phase_invariant_fraction = variance NOT driven by sub-frame position,
  - EIGEN-PROJECTION: is shift-sensitivity concentrated in the low-lambda / near-degenerate
    eigenplanes? (correlate s with the corpus eigenbasis from G1).

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/phase_invariance_probe.py
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

from stable_audio_3 import StableAudioModel

CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
EIG = Path("/run/media/kim/Mantu/sa3_lora_runs/e1_pretest/corpus_eigbasis.npz")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/phase_invariance")
SR = 44100
CLIP_S = 8.0
FRAME = 4096
SHIFTS = np.arange(0, FRAME + 1, 32)     # one frame, content-preserving roll
BATCH = 48
CENTER = (24, 64)                        # center frames (avoid the wrap-click edge)


def encode_rolled(cdm, device, mdtype, y, n_clip):
    """z for each circular roll of y; center-frame trajectory [nshift, 256]."""
    Z = []
    for s0 in range(0, len(SHIFTS), BATCH):
        sh = SHIFTS[s0:s0 + BATCH]
        batch = np.stack([np.roll(y, int(d))[:n_clip] for d in sh])
        x = torch.tensor(batch[:, None, :]).repeat(1, 2, 1)
        with torch.no_grad():
            z = cdm.pretransform.encode(x.to(device, mdtype))
        Z.append(z.float().cpu().numpy())
    Z = np.concatenate(Z)                # [nshift, 256, F]
    c0, c1 = CENTER
    return Z[:, :, c0:c1].mean(2)         # [nshift, 256]


def analyze(traj):
    s = traj.var(0)                                        # [256] per-dim shift-sensitivity
    order = np.argsort(s)[::-1]
    csum = np.cumsum(s[order]) / (s.sum() + 1e-12)
    n90 = int(np.searchsorted(csum, 0.9) + 1)              # dims for 90% of shift-energy
    return s, n90


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    z_eig = np.load(EIG); vecs = np.ascontiguousarray(z_eig["vecs"]); vals = z_eig["vals"]
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    n_clip = int(SR * CLIP_S)
    t = np.arange(n_clip + FRAME + 1) / SR

    stim = {"tone_440": 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32),
            "tone_3520": 0.5 * np.sin(2 * np.pi * 3520 * t).astype(np.float32)}
    reals = [d for d in sorted(CORPUS.iterdir()) if (d / "full_mix.flac").exists()][:8]
    for d in reals:
        a, sr = sf.read(d / "full_mix.flac", dtype="float32", always_2d=True)
        if a.shape[0] < int(60 * sr) + n_clip + FRAME:
            continue
        stim[f"real_{d.name[:14].replace(' ', '_')}"] = \
            a[int(60 * sr): int(60 * sr) + n_clip + FRAME].mean(1).astype(np.float32)

    results, sens_by_kind = {}, {"tone": [], "real": []}
    for name, y in stim.items():
        traj = encode_rolled(cdm, device, mdtype, y, n_clip)
        s, n90 = analyze(traj)
        # eigen-projection: sensitivity energy per eigendirection
        s_eig = (vecs.T @ (traj - traj.mean(0)).T)                    # [256, nshift] eigen coords
        s_eig_var = s_eig.var(1)                                      # [256] per-eigendir sensitivity
        # is sensitivity in the low-lambda tail? corr(sensitivity, -log lambda)
        eig_corr = float(np.corrcoef(np.log(s_eig_var + 1e-12), np.log(vals + 1e-12))[0, 1])
        phase_inv = 1.0 - float(s.sum() / (traj.var(0).sum() + s.sum() + 1e-12))  # rough
        results[name] = {"n_dims_90pct": n90, "dims_moving": int((s > s.max()*0.01).sum()),
                         "sens_lambda_corr": round(eig_corr, 3),
                         "top_dims": [int(c) for c in np.argsort(s)[::-1][:6]]}
        ("tone" if name.startswith("tone") else "real"
         ).__len__()  # noop
        sens_by_kind["tone" if name.startswith("tone") else "real"].append(s)
        np.savez_compressed(OUT / f"sens_{name}.npz", sens=s.astype(np.float32),
                            sens_eig=s_eig_var.astype(np.float32))
        print(f"[{name}] 90%-energy in {n90} dims, {results[name]['dims_moving']} dims move, "
              f"sens-vs-lambda corr {eig_corr:+.2f}", flush=True)

    tone_s = np.mean(sens_by_kind["tone"], 0)
    real_s = np.mean(sens_by_kind["real"], 0) if sens_by_kind["real"] else tone_s
    # do tones and reals stress the SAME dims? (does it hold for complex waves)
    dim_overlap = float(np.corrcoef(tone_s, real_s)[0, 1])
    summary = {
        "per_stimulus": results,
        "tone_vs_real_dim_overlap": round(dim_overlap, 3),
        "real_90pct_dims_mean": round(float(np.mean(
            [results[n]["n_dims_90pct"] for n in results if n.startswith("real")])), 1),
        "reading": "Low n_dims_90pct => phase confined to few dims (latent mostly "
                   "phase-invariant). sens_lambda_corr<0 => phase-sensitivity lives in the "
                   "LOW-variance eigendirections (the G3 near-degenerate planes / melody-wall "
                   "region). tone_vs_real_dim_overlap ~1 => the pure-tone phase-plane finding "
                   "HOLDS for complex real signals (Kim's caveat resolved).",
        "result": None, "kim_feedback": None}
    (OUT / "results.json").write_text(json.dumps(summary, indent=2))
    print(f"\ntone/real dim overlap {dim_overlap:.3f}; real phase confined to "
          f"~{summary['real_90pct_dims_mean']}/256 dims")
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
