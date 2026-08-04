#!/usr/bin/env python
"""e1_pretest_error_spectrum.py — E1 PRE-TEST (tier-0, Kim's lightweight-first directive;
spec docs/superpowers/specs/2026-07-31-reality-structured-model-experiments.md).

Question: does the v-trained base model's prediction error concentrate in the LOW-VARIANCE
eigendirections of the SAME latent, as JLT's mechanism (velocity target covariance = Σ + I,
the unit floor swamping directions with λ << 1) predicts? If yes → the 13 h x0-target arm
(E1) is strongly motivated; if error is flat across λ → E1 dies here, cheap.

Method: corpus latents (their own stored prompts), noise at σ ∈ {0.2, 0.5, 0.8}
(z_t = (1-σ)x + σε, RF target v = ε − x per training/diffusion.py:443), one conditioned
forward each with medium-base; project per-frame error e = v̂ − v onto the corpus
covariance EIGENBASIS (G1's measurement, recomputed + saved here); report per-direction
error energy vs λ. Headline stat: median relative error (err_i/λ-matched expectation) in
sub-floor directions (λ<0.5) vs high-λ directions (λ>2).

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/e1_pretest_error_spectrum.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import glob
import json
import random
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel

LATENTS = Path("/home/kim/Projects/latents_sa3")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/e1_pretest")
SIGMAS = [0.2, 0.5, 0.8]
N_CROPS = 48
EIG_CACHE = OUT / "corpus_eigbasis.npz"


def corpus_eigbasis():
    if EIG_CACHE.exists():
        z = np.load(EIG_CACHE)
        return z["vecs"], z["vals"]
    files = sorted(glob.glob(str(LATENTS / "*.npy")))
    random.seed(1)
    acc = []
    for f in random.sample(files, 220):
        z = np.squeeze(np.load(f)).astype(np.float32)
        if z.shape[0] != 256:
            z = z.T
        acc.append(z[:, ::4])
    Z = np.concatenate(acc, axis=1)
    C = np.cov(Z)
    vals, vecs = np.linalg.eigh(C)          # ascending
    vals, vecs = vals[::-1], vecs[:, ::-1]  # descending
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(EIG_CACHE, vecs=vecs, vals=vals)
    return vecs, vals


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vecs, vals = corpus_eigbasis()          # vecs [256,256] cols = eigvecs, vals desc
    print(f"[eig] spectrum: max {vals[0]:.1f} min {vals[-1]:.4f} "
          f"(<1: {(vals < 1).sum()}/256)")

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    V = torch.tensor(np.ascontiguousarray(vecs), dtype=torch.float32, device=device)   # [256,256]

    files = sorted(glob.glob(str(LATENTS / "*.npy")))
    random.seed(7)
    picks = random.sample(files, N_CROPS)

    # err_energy[sigma][i] accumulates squared error along eigendirection i
    err_energy = {s: np.zeros(256) for s in SIGMAS}
    n_frames = {s: 0 for s in SIGMAS}

    for fi, f in enumerate(picks):
        x = np.squeeze(np.load(f)).astype(np.float32)
        if x.shape[0] != 256:
            x = x.T
        meta = json.loads(Path(f.replace(".npy", ".json")).read_text())
        prompt = meta.get("prompt") or meta.get("caption") or "goa trance"
        seconds = x.shape[1] / 10.7666015625
        xt_ = torch.tensor(x[None]).to(device, mdtype)           # [1,256,T]

        tensors = cdm.conditioner([{"prompt": prompt, "seconds_total": seconds}], str(device))
        T = x.shape[1]
        tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
        tensors["inpaint_masked_input"] = [torch.zeros_like(xt_, device=device)]
        cond = cdm.get_conditioning_inputs(tensors)
        cond = {k: (v.type(mdtype) if torch.is_tensor(v) else v) for k, v in cond.items()}

        g = torch.Generator(device="cpu").manual_seed(1000 + fi)
        eps = torch.randn(xt_.shape, generator=g).to(device, mdtype)
        v_true = eps - xt_                                       # RF target (diffusion.py:443)
        for s in SIGMAS:
            zs = (1 - s) * xt_ + s * eps
            t = torch.full((1,), float(s), device=device, dtype=mdtype)
            with torch.no_grad():
                v_hat = cdm.model(zs, t, **cond)
            e = (v_hat - v_true)[0].float()                      # [256,T]
            proj = V.T @ e                                       # [256,T] eigen coords
            err_energy[s] += proj.pow(2).sum(dim=1).cpu().numpy()
            n_frames[s] += e.shape[1]
        if (fi + 1) % 8 == 0:
            print(f"[fwd] {fi+1}/{N_CROPS}", flush=True)

    results = {}
    print(f"\nper-eigendirection error vs lambda (mean over {N_CROPS} crops):")
    print(f"{'sigma':>6} {'err(lo λ<0.5)':>14} {'err(hi λ>2)':>12} {'ratio':>7} "
          f"{'rel-lo':>8} {'rel-hi':>8} {'rel-ratio':>10}")
    lo, hi = vals < 0.5, vals > 2.0
    for s in SIGMAS:
        err = err_energy[s] / n_frames[s]                        # per-direction MSE
        rel = err / np.maximum(vals, 1e-6)                       # error per unit signal variance
        row = {"err_lo": float(np.median(err[lo])), "err_hi": float(np.median(err[hi])),
               "rel_lo": float(np.median(rel[lo])), "rel_hi": float(np.median(rel[hi]))}
        row["err_ratio"] = row["err_lo"] / row["err_hi"]
        row["rel_ratio"] = row["rel_lo"] / row["rel_hi"]
        results[f"sigma_{s}"] = row
        print(f"{s:>6} {row['err_lo']:>14.4f} {row['err_hi']:>12.4f} {row['err_ratio']:>7.3f} "
              f"{row['rel_lo']:>8.3f} {row['rel_hi']:>8.3f} {row['rel_ratio']:>10.2f}")
        np.save(OUT / f"err_spectrum_sigma{s}.npy",
                np.stack([vals, err]))

    (OUT / "results.json").write_text(json.dumps(
        {"results": results, "n_crops": N_CROPS, "sigmas": SIGMAS,
         "interpretation": "rel-ratio >> 1 means the v-trained model recovers low-variance "
                           "eigendirections far worse PER UNIT SIGNAL than high-variance ones "
                           "(JLT mechanism live) -> E1 motivated. rel-ratio ~ 1 => flat "
                           "relative recovery -> E1 dies here.",
         "eigbasis": str(EIG_CACHE), "model": "medium-base (v-trained, no adapter)",
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
