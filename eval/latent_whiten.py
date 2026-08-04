#!/usr/bin/env python
"""latent_whiten.py — post-hoc latent whitening reparam for the DiT-side HF fix (#65, Track B
of docs/clarity-recovery-plan-2026-08-02.md).

The SAME latent covariance is 786x anisotropic (1/f slope), so 188/256 directions sit below
the flow-target unit-noise floor and the DiT effectively uses only ~37/256 directions
(participation ratio, measured in latent_whitening_probe.py). Whitening Sigma->I between the
FROZEN encoder and the DiT forces equal capacity across all 256 directions; the exact inverse
is applied before the FROZEN decoder, so the codec is untouched (validated: W Sigma W^T = I to
4e-15, round-trip to 1.6e-14).

This module promotes that math to a save-able reparam:
  z_white = W (z - mean)                 # feed to DiT (train + sample in whitened space)
  z       = W_inv z_white + mean         # un-whiten before the frozen decoder (exact inverse)

`fit` from a corpus latent sample; buffers persist with the checkpoint.
Unit tests in test_latent_whiten.py.
"""
import numpy as np
import torch
import torch.nn as nn


class LatentWhitener(nn.Module):
    """Channel-whitening of a [B, C, T] latent (C=256 for SAME). Eigen-whitening:
    W = Lambda^-1/2 V^T, W_inv = V Lambda^1/2, from the corpus covariance."""
    def __init__(self, channels=256):
        super().__init__()
        self.register_buffer("mean", torch.zeros(channels))
        self.register_buffer("W", torch.eye(channels))
        self.register_buffer("W_inv", torch.eye(channels))
        self.fitted = False

    @torch.no_grad()
    def fit(self, latents, eps=1e-6):
        """latents: [N, C] (flatten time into N) or [N, C, T]. Computes mean + eigen-whitening."""
        x = latents
        if x.dim() == 3:                          # [N, C, T] -> [N*T, C]
            x = x.permute(0, 2, 1).reshape(-1, x.shape[1])
        x = x.double()
        mu = x.mean(0)
        xc = x - mu
        cov = (xc.T @ xc) / (xc.shape[0] - 1)
        evals, evecs = torch.linalg.eigh(cov)     # ascending; symmetric PSD
        evals = evals.clamp(min=eps)
        W = torch.diag(evals ** -0.5) @ evecs.T
        W_inv = evecs @ torch.diag(evals ** 0.5)
        self.mean.copy_(mu.to(self.mean.dtype))
        self.W.copy_(W.to(self.W.dtype))
        self.W_inv.copy_(W_inv.to(self.W_inv.dtype))
        self.fitted = True
        return self

    def forward(self, z):
        """z: [B, C, T] raw latent -> whitened [B, C, T] (feed to DiT)."""
        zc = z - self.mean.view(1, -1, 1)
        return torch.einsum("ij,bjt->bit", self.W.to(z.dtype), zc)

    def inverse(self, zw):
        """zw: [B, C, T] whitened -> raw [B, C, T] (feed to frozen decoder)."""
        z = torch.einsum("ij,bjt->bit", self.W_inv.to(zw.dtype), zw)
        return z + self.mean.view(1, -1, 1)


if __name__ == "__main__":
    print("latent_whiten.py — import OK; run test_latent_whiten.py for unit tests")
