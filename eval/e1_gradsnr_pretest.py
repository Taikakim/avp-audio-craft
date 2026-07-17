#!/usr/bin/env python3
"""E1 gradient-SNR pre-test (C's design, plan §2-E1; model-free, zero renders).

Proxy for in-sampler z0_hat inputs: clean corpus latents + gamma-style Gaussian
noise at a ladder of levels (the sampler itself evaluates head(z0_hat + gamma
noise), gamma=0.3 default). Measures, per noise level:
  * grad SNR  = ||mean_k g_k|| / mean_k ||g_k - mean g||   (k = noise seeds)
  * line-search sanity: does a step along -g reduce the potential
  * rec-curve stats + in-band fraction vs the corpus q90 edge
Writes eval/e1_gradsnr_pretest.json. mir venv (ROCm torch).
"""
import json, sys
sys.path.insert(0, "/home/kim/Projects/mir/src")
from core.rocm_env import setup_rocm_env; setup_rocm_env()
import numpy as np, torch
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from stable_audio_3.inference.recurrence_potential import RecurrenceHead, band_hinge_loss

DEV = "cuda" if torch.cuda.is_available() else "cpu"
EDGE = json.load(open("/home/kim/Projects/SAO/eval/corpus_bands.json"))["bands"]["r_max"]["q90"]
head = RecurrenceHead().to(DEV)
import glob
lats = sorted(glob.glob("/home/kim/Projects/latents_sa3/*.npy"))[:4]
S_LEVELS = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8]
N_SEED = 4
rows = []
for li, p in enumerate(lats):
    z0 = torch.from_numpy(np.load(p).astype(np.float32)).unsqueeze(0).to(DEV)  # (1,256,T)
    for s in S_LEVELS:
        gs, pots, recs = [], [], []
        for k in range(N_SEED):
            g = torch.Generator(device="cpu").manual_seed(1000 * li + k)
            x = (z0 + s * torch.randn(z0.shape, generator=g).to(DEV)).requires_grad_(True)
            rec = head(x)
            pot = band_hinge_loss(rec, torch.tensor(EDGE, device=DEV))
            pot.backward()
            gs.append(x.grad.detach().clone()); pots.append(float(pot)); recs.append(rec.detach())
        G = torch.stack(gs); gm = G.mean(0)
        snr = float(gm.norm() / (G - gm).flatten(1).norm(dim=1).mean().clamp_min(1e-12))
        # line-search on seed 0
        x0 = (z0 + s * torch.randn(z0.shape, generator=torch.Generator(device="cpu").manual_seed(1000*li)).to(DEV))
        d = gs[0] / gs[0].norm().clamp_min(1e-12) * 0.02 * x0.norm()
        with torch.no_grad():
            p_before = float(band_hinge_loss(head(x0), torch.tensor(EDGE, device=DEV)))
            p_after = float(band_hinge_loss(head(x0 - d), torch.tensor(EDGE, device=DEV)))
        r = torch.cat(recs); inband = float((r <= EDGE).float().mean())
        rows.append({"latent": li, "s": s, "grad_snr": round(snr, 3),
                     "pot": round(float(np.mean(pots)), 5), "grad_norm": round(float(gm.norm()), 5),
                     "linesearch_delta": round(p_after - p_before, 6),
                     "rec_med": round(float(r.median()), 3), "rec_q95": round(float(r.quantile(0.95)), 3),
                     "frac_below_edge": round(inband, 3)})
        print(rows[-1], flush=True)
json.dump({"edge_q90_1s_stride": EDGE, "note": "head runs FRAME stride; edge offset visible in rec_med/q95",
           "rows": rows}, open("eval/e1_gradsnr_pretest.json", "w"), indent=1)
print("wrote eval/e1_gradsnr_pretest.json")
