"""Control-consistency probe — a frozen differentiable meter for onset density.

Spec: SAO/docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md (#1).

RF loss is blind to control quality (flat while authority drifts; the 6-9 onsets/s
saturation band). This module puts the meaning INTO the gradient: a small probe maps a
clean-latent window to the (normalized) onset_density scalar — the exact per-crop .json
quantity the FiLM conditioner is asked to control — and the trainer adds
``lambda_cc * MSE(probe(z0_hat), requested)`` for low-noise timesteps.

RF convention (train.py): ``noised = clean*(1-t) + noise*t``, ``v = noise - clean``
=> ``z0_hat = noised - t * v_pred`` (exact when v_pred is exact; biased at high t,
hence the t-gate).

Probe training: scripts side (train_cc_probe.py) — supervised regression on the
latents_sa3 clean latents vs the .json ``onset_density``, normalized with the SAME
scalar_norm as adapter training (mean/std stored in the probe checkpoint; verify at load).
Validate held-out before use: a weak meter gets reward-hacked (see spec, Risks).
"""
from __future__ import annotations

import torch
import torch.nn as nn


def rf_z0_hat(noised: torch.Tensor, v_pred: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    """Differentiable clean-latent estimate under the rectified-flow convention.

    noised: (B, C, T); v_pred: (B, C, T); t: (B,) in [0,1] (t=0 clean, t=1 noise).
    """
    tb = t.view(-1, *([1] * (noised.ndim - 1))).to(noised.dtype)
    return noised - tb * v_pred


class OnsetDensityProbe(nn.Module):
    """Small Conv1d stack -> GAP -> MLP; latent window (B, C, T) -> normalized scalar (B,).

    ~0.5M params at in_ch=256. Trained on CLEAN latents; consumers gate by t so it only
    ever sees decent z0_hat estimates. Stored checkpoint carries scalar_norm for
    apples-to-apples with the trainer's request scale.
    """

    def __init__(self, in_ch: int = 256, width: int = 192, depth: int = 3,
                 out_dim: int = 1):
        super().__init__()
        self.out_dim = out_dim
        layers, ch = [], in_ch
        for i in range(depth):
            layers += [nn.Conv1d(ch, width, kernel_size=5, stride=2 if i else 1, padding=2),
                       nn.GroupNorm(8, width), nn.SiLU()]
            ch = width
        self.body = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.Linear(width, width // 2), nn.SiLU(),
                                  nn.Linear(width // 2, out_dim))

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        h = self.body(z.float())
        h = h.mean(dim=-1)                     # GAP over time -> handles variable T
        out = self.head(h)
        return out.squeeze(-1) if self.out_dim == 1 else out   # scalar back-compat


def control_consistency_loss(probe: nn.Module, z0_hat: torch.Tensor,
                             scalar_request: torch.Tensor, t: torch.Tensor,
                             t_max: float = 0.5) -> torch.Tensor:
    """MSE(probe(z0_hat), requested) over rows with t < t_max; 0 if all rows gated.

    scalar_request must be on the probe's normalized scale (same scalar_norm).
    Returns a scalar tensor on z0_hat's device; safe to add to the RF loss (grad flows
    to z0_hat, i.e. into the DiT/adapters; the probe stays frozen — freeze it upstream).
    """
    gate = t < t_max
    if not bool(gate.any()):
        return z0_hat.new_zeros(())
    pred = probe(z0_hat[gate])
    return torch.nn.functional.mse_loss(pred, scalar_request[gate].to(pred.dtype))


def load_probe(path: str, device: str = "cpu") -> tuple[OnsetDensityProbe, tuple[float, float]]:
    """Load a trained probe checkpoint -> (frozen eval-mode probe, (scalar_mean, scalar_std))."""
    ck = torch.load(path, map_location="cpu", weights_only=True)
    probe = OnsetDensityProbe(**ck.get("arch", {}))
    probe.load_state_dict(ck["state"])
    probe.to(device).eval()
    for p in probe.parameters():
        p.requires_grad_(False)
    mean, std = ck.get("scalar_norm", (0.0, 1.0))
    return probe, (float(mean), float(std))
