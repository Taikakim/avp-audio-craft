#!/usr/bin/env python
"""melody_r2_vs_t.py — how recoverable is the MELODY SUBSPACE at each noise level, for a given model?
Writes the R²(t) curve that `train_lora.py --subspace-loss-tgate` turns into a noise-level gate on the
#59 subspace-weighted RF loss (stable_audio_3/training/tgate.py).

WHAT IS MEASURED (C, 2026-08-19; the E1 pre-test machinery, eval/e1_pretest_error_spectrum.py, on a
dense t grid and the melody-selective basis instead of the corpus eigenbasis):
  for corpus crops x (their own stored prompts), t on a grid, fixed ε per crop:
     z_t = (1−t)x + tε,   v̂ = model(z_t, t | prompt),   x̂0 = z_t − t·v̂     (RF, diffusion.py:544)
     e = x̂0 − x
     R²_melody(t) = 1 − Σ‖P e‖² / Σ‖P (x − x̄)‖²        P = melody basis rows (v3 npz `basis15`)
     R²_rest(t)   = 1 − Σ‖(I−P) e‖² / Σ‖(I−P)(x − x̄)‖²
     deficit(t)   = (err_mel/var_mel) / (err_rest/var_rest)   (>1: melody under-recovered relative
                                                              to the rest of the latent — E1's quantity)
  R² is 1 at t=0 by construction and falls toward 0 as t→1; the SHAPE (where it drops, and how much
  worse than the rest) is what the gate uses. Uses the model's own prediction, i.e. "learnable by THIS
  model at this t", not merely "linearly present in the noised latent".

USAGE (SA3 venv, GPU, hold the GPU mutex):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/melody_r2_vs_t.py \
      --out lumi/melody_r2_vs_t_medium-base.json [--lora <ckpt>] [--n-crops 48] [--frames 1024]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import glob
import json
import random
import time
from pathlib import Path

import numpy as np
import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--basis", default="/home/kim/Projects/SAO/lumi/melody_subspace15_selective_v3.npz")
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--lora", default=None, help="optional LoRA/DoRA ckpt to load on top")
    ap.add_argument("--n-crops", type=int, default=48)
    ap.add_argument("--frames", type=int, default=1024, help="random window length (frames)")
    ap.add_argument("--t-grid", type=int, default=19, help="points on (0,1): linspace(0.05,0.95,n)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from stable_audio_3 import StableAudioModel
    z = np.load(a.basis)
    B = z["basis15"] if "basis15" in z.files else z["melody_basis"][:15]           # [k, 256]
    ts = np.linspace(0.05, 0.95, a.t_grid).tolist()

    model = StableAudioModel.from_pretrained(a.model, device="cuda")
    if a.lora:
        model.load_lora(a.lora)
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    P = torch.tensor(np.ascontiguousarray(B), dtype=torch.float32, device=device)  # [k, C]

    files = sorted(glob.glob(str(Path(a.latents) / "*.npy")))
    files = [f for f in files if not f.endswith("silence.npy")]
    random.seed(a.seed)
    picks = random.sample(files, min(a.n_crops, len(files)))

    # pass 1: pooled mean of the clean latent over the sampled windows (for the variance terms)
    wins = []
    xsum = torch.zeros(256, dtype=torch.float64); nfr = 0
    for fi, f in enumerate(picks):
        x = np.squeeze(np.load(f)).astype(np.float32)
        if x.shape[0] != 256:
            x = x.T
        T = x.shape[1]
        rng = random.Random(a.seed * 1000 + fi)
        s0 = rng.randint(0, max(0, T - a.frames)) if T > a.frames else 0
        xw = x[:, s0:s0 + a.frames]
        wins.append((f, xw))
        xsum += torch.tensor(xw, dtype=torch.float64).sum(1); nfr += xw.shape[1]
    xbar = (xsum / nfr).float().to(device)                                          # [C]

    err_mel = np.zeros(len(ts)); err_rest = np.zeros(len(ts))
    var_mel = 0.0; var_rest = 0.0
    t0 = time.time()
    for fi, (f, xw) in enumerate(wins):
        meta = json.loads(Path(f.replace(".npy", ".json")).read_text())
        prompt = meta.get("prompt") or meta.get("caption") or "goa trance"
        seconds = xw.shape[1] / 10.7666015625
        xt_ = torch.tensor(xw[None]).to(device, mdtype)                              # [1,C,T]
        T = xw.shape[1]
        tensors = cdm.conditioner([{"prompt": prompt, "seconds_total": seconds}], str(device))
        tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
        tensors["inpaint_masked_input"] = [torch.zeros_like(xt_, device=device)]
        cond = cdm.get_conditioning_inputs(tensors)
        cond = {k: (v.type(mdtype) if torch.is_tensor(v) else v) for k, v in cond.items()}
        xc = (xt_[0].float() - xbar[:, None])                                        # [C,T] centred
        pm = P @ xc
        var_mel += float(pm.pow(2).sum()); var_rest += float(xc.pow(2).sum() - pm.pow(2).sum())
        g = torch.Generator(device="cpu").manual_seed(1000 + fi)
        eps = torch.randn(xt_.shape, generator=g).to(device, mdtype)
        for ti, t in enumerate(ts):
            zt = (1 - t) * xt_ + t * eps
            tt = torch.full((1,), float(t), device=device, dtype=mdtype)
            with torch.no_grad():
                v_hat = cdm.model(zt, tt, **cond)
            x0_hat = zt - t * v_hat
            e = (x0_hat - xt_)[0].float()                                            # [C,T]
            pe = P @ e
            em = float(pe.pow(2).sum())
            err_mel[ti] += em; err_rest[ti] += float(e.pow(2).sum()) - em
        if (fi + 1) % 8 == 0:
            print(f"[fwd] {fi+1}/{len(wins)}  {time.time()-t0:.0f}s", flush=True)

    r2m = (1.0 - err_mel / max(var_mel, 1e-12)).tolist()
    r2r = (1.0 - err_rest / max(var_rest, 1e-12)).tolist()
    deficit = ((err_mel / max(var_mel, 1e-12)) / np.maximum(err_rest / max(var_rest, 1e-12), 1e-12)).tolist()
    out = {"t": ts, "r2_melody": r2m, "r2_rest": r2r, "deficit": deficit,
           "n_crops": len(wins), "frames": a.frames, "model": a.model, "lora": a.lora,
           "basis": a.basis, "basis_rank": int(B.shape[0]), "seed": a.seed,
           "note": "R2 of the model's own x0-hat inside/outside the melody basis vs noise level t "
                   "(RF: z_t=(1-t)x+t*eps). Gate source for train_lora --subspace-loss-tgate.",
           "tool": "eval/melody_r2_vs_t.py"}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"\n{'t':>5} {'R2_melody':>10} {'R2_rest':>8} {'deficit':>8}")
    for t, m, r, d in zip(ts, r2m, r2r, deficit):
        print(f"{t:>5.2f} {m:>10.3f} {r:>8.3f} {d:>8.2f}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
