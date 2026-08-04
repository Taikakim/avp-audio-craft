#!/usr/bin/env python
"""test_latent_whiten.py — CPU unit tests for the LatentWhitener reparam (#65).
Validates the module version of the whitening math (probe already proved the premise) is
correct, exactly invertible, and persists through save/load — before any DiT run.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_latent_whiten.py
"""
import sys
from pathlib import Path
import numpy as np
import torch
torch.manual_seed(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from latent_whiten import LatentWhitener

C = 64
ok = True


def chk(name, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


# build a synthetic anisotropic latent (known covariance) — mimic the 1/f SAME spectrum
rng = np.random.default_rng(0)
Q, _ = np.linalg.qr(rng.standard_normal((C, C)))
lam = np.arange(1, C + 1, dtype=np.float64) ** -1.1   # 1/f-ish eigenvalues
A = Q @ np.diag(np.sqrt(lam))
N, T = 4000, 8
raw = (rng.standard_normal((N * T, C)) @ A.T).astype(np.float32)      # cov ~ A A^T
latents = torch.tensor(raw).reshape(N, T, C).permute(0, 2, 1)          # [N, C, T]

w = LatentWhitener(channels=C).fit(latents)
chk("fit sets fitted flag", w.fitted)

# (1) whitened covariance ~ I
zw = w(latents)                                                        # [N, C, T]
flat = zw.permute(0, 2, 1).reshape(-1, C).double()
cov_w = torch.cov(flat.T)
ev = torch.linalg.eigvalsh(cov_w)
chk("whitened cov eigenvalues ~ 1", 0.9 < ev.min() and ev.max() < 1.1,
    f"[{ev.min():.3f}, {ev.max():.3f}]")
offdiag = (cov_w - torch.eye(C, dtype=cov_w.dtype)).abs()
offdiag.fill_diagonal_(0)
chk("whitened cov off-diagonal ~ 0 (finite-sample)", offdiag.max() < 0.1, f"{offdiag.max():.3f}")

# (2) EXACT inverse round-trip (the 'codec stays frozen' guarantee)
rt = w.inverse(w(latents))
chk("inverse round-trip exact", torch.allclose(rt, latents, atol=1e-4),
    f"max|rt-z|={ (rt-latents).abs().max():.2e}")

# (3) analytic identity W Sigma_sample W^T = I — against the SAMPLE cov the module fit on
# (comparing to the population A A^T would only match up to finite-sample error, ~2e-2 here).
Wd = w.W.double()
xs = latents.permute(0, 2, 1).reshape(-1, C).double()
cov_sample = torch.cov((xs - xs.mean(0)).T)
ident = Wd @ cov_sample @ Wd.T
chk("analytic W Sigma_sample W^T = I", torch.allclose(ident, torch.eye(C, dtype=torch.float64), atol=1e-5),
    f"max|.-I|={ (ident-torch.eye(C,dtype=torch.float64)).abs().max():.2e}")

# (4) participation ratio rises toward C after whitening (the capacity point)
def pr(cov):
    e = torch.linalg.eigvalsh(cov).clamp(min=0)
    return float((e.sum() ** 2) / (e ** 2).sum())
pr_raw = pr(torch.tensor(A @ A.T))
pr_white = pr(cov_w)
chk("participation ratio rises to ~C", pr_white > 0.9 * C and pr_white > 3 * pr_raw,
    f"raw {pr_raw:.1f} -> white {pr_white:.1f} of {C}")

# (5) buffers persist through save/load (checkpoint-safe)
buf = {}
sd = w.state_dict()
w2 = LatentWhitener(channels=C)
w2.load_state_dict(sd)
chk("save/load preserves transform", torch.allclose(w2(latents), zw, atol=1e-5))

print(f"\n{'ALL PASS — LatentWhitener reparam correct, exactly invertible, save-able (#65 ready)' if ok else 'FAILURES'}")
raise SystemExit(0 if ok else 1)
