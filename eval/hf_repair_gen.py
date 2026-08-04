#!/usr/bin/env python
"""hf_repair_gen.py — GENERATIVE HF-repair post-net components (task #62, Track A of
docs/clarity-recovery-plan-2026-08-02.md).

Why generative: eval/test_regression_phase_ceiling.py proved a regression post-net cannot
recover >7 kHz phase from ~0.05-coherence input (magnitude collapses to the mean). HF phase
must be GENERATED. This module supplies the three ingredients the plan + the (citation-
verified) Gemini answers prescribe, each a separate, CPU-unit-testable piece:

  1. Snake1dADAA        — anti-derivative anti-aliased SnakeBeta (validated in
                          test_adaa_snake_module.py: gradient-safe, f32-stable for alpha>=0.1).
  2. GenHFRepairNet     — ADAA-Snake dilated-conv refiner + LATENT CONDITIONING (Q1: feed the
                          256-ch SAME latent, upsampled, as a pristine pre-decoder prior) +
                          zero-init residual (identity at init).
  3. MultiPeriodDiscriminator + losses — the adversarial machinery that forces coherent phase
                          hallucination (vs the regression mean), plus an anti-wrapping
                          group-delay term used ONLY as a GAN phase-STABILIZER (not to regress
                          the unreachable original phase — that was shown inert/harmful).

NOTE: separate file so the in-flight regression run (train_hf_repair.py) is untouched. Unit
tests in test_hf_repair_gen.py. Not wired to a training entry yet (that's the next step once
the regression baseline + #64 land).
"""
import numpy as np
import torch
import torch.utils.checkpoint
import torch.nn as nn
import torch.nn.functional as F

SR = 44100


# --------------------------------------------------------------- ADAA-SnakeBeta (validated) --
class Snake1dADAA(nn.Module):
    """Anti-derivative anti-aliased Snake. Gradient-safe (double-where), f32-stable for
    alpha>=0.1. Operates on [B,C,T]; ADAA applied along T. (Full anti-aliasing wraps this in a
    2x resample stage per the Pupu-Vocoder result; the nonlinearity itself is validated here.)"""
    def __init__(self, channels, alpha_init=1.0, eps=1e-4):
        super().__init__()
        self.log_alpha = nn.Parameter(torch.full((1, channels, 1), float(np.log(alpha_init))))
        self.eps = eps

    def _snake(self, x, a):
        return x + (1.0 / a) * torch.sin(a * x) ** 2

    def _F(self, x, a):
        return x * x / 2.0 + x / (2.0 * a) - torch.sin(2.0 * a * x) / (4.0 * a * a)

    def forward(self, x):
        a = torch.exp(self.log_alpha).clamp(min=0.1)     # keep alpha>=0.1 (f32 stability)
        xm1 = torch.cat([x[..., :1], x[..., :-1]], dim=-1)
        dx = x - xm1
        big = dx.abs() > self.eps
        safe = torch.where(big, dx, torch.ones_like(dx))
        adaa = (self._F(x, a) - self._F(xm1, a)) / safe
        return torch.where(big, adaa, self._snake((x + xm1) / 2.0, a))


class ADAAResBlock(nn.Module):
    def __init__(self, channels, dilation):
        super().__init__()
        pad = (7 - 1) // 2 * dilation
        self.block = nn.Sequential(
            Snake1dADAA(channels),
            nn.Conv1d(channels, channels, 7, dilation=dilation, padding=pad),
            Snake1dADAA(channels),
            nn.Conv1d(channels, channels, 1),
        )

    def forward(self, x):
        return x + self.block(x)


# ------------------------------------------------------------------------ generator ----------
class GenHFRepairNet(nn.Module):
    """ADAA-Snake dilated refiner with optional SAME-latent conditioning. Zero-init output +
    global residual => identity at init (train only learns the correction).

    Inputs: audio [B, io_ch, T]; optional latent [B, latent_ch, Tl] (Tl << T, ~10.77 Hz).
    The latent is linearly upsampled to T and projected, then concatenated to the input conv."""
    def __init__(self, channels=160, dilations=(1, 3, 9), n_stacks=4, io_channels=2,
                 latent_ch=0, latent_proj=32):
        super().__init__()
        self.latent_ch = latent_ch
        in_ch = io_channels + (latent_proj if latent_ch else 0)
        if latent_ch:
            self.latent_proj = nn.Conv1d(latent_ch, latent_proj, 1)
        self.in_conv = nn.Conv1d(in_ch, channels, 7, padding=3)
        self.blocks = nn.ModuleList(
            [ADAAResBlock(channels, d) for _ in range(n_stacks) for d in dilations])
        self.out_snake = Snake1dADAA(channels)
        self.out_conv = nn.Conv1d(channels, io_channels, 7, padding=3)
        nn.init.zeros_(self.out_conv.weight)
        nn.init.zeros_(self.out_conv.bias)

    def forward(self, x, latent=None):
        h_in = x
        if self.latent_ch and latent is not None:
            up = F.interpolate(latent, size=x.shape[-1], mode="linear", align_corners=False)
            h_in = torch.cat([x, self.latent_proj(up)], dim=1)
        h = self.in_conv(h_in)
        for b in self.blocks:
            if self.training and h.requires_grad:
                h = torch.utils.checkpoint.checkpoint(b, h, use_reentrant=False)
            else:
                h = b(h)
        return x + self.out_conv(self.out_snake(h))       # identity at init


# ------------------------------------------------------- multi-period discriminator ----------
class PeriodDisc(nn.Module):
    """HiFi-GAN-style sub-discriminator: reshape 1D -> 2D by period, strided 2D convs."""
    def __init__(self, period, ch=(32, 128, 512, 1024)):
        super().__init__()
        self.period = period
        cs = [1, *ch]
        self.convs = nn.ModuleList(
            [nn.Conv2d(cs[i], cs[i + 1], (5, 1), (3, 1), padding=(2, 0)) for i in range(len(ch))])
        self.post = nn.Conv2d(ch[-1], 1, (3, 1), padding=(1, 0))

    def forward(self, x):                                  # x: [B, 1, T]
        b, c, t = x.shape
        if t % self.period:
            x = F.pad(x, (0, self.period - t % self.period), mode="reflect")
        x = x.view(b, c, x.shape[-1] // self.period, self.period)
        feats = []
        for conv in self.convs:
            x = F.leaky_relu(conv(x), 0.1)
            feats.append(x)
        return self.post(x), feats                         # score map, feature maps


class MultiPeriodDiscriminator(nn.Module):
    def __init__(self, periods=(2, 3, 5, 7, 11)):
        super().__init__()
        self.subs = nn.ModuleList([PeriodDisc(p) for p in periods])

    def forward(self, x):                                  # x: [B, 1, T] (mono)
        return [s(x) for s in self.subs]                   # list of (score, feats)


# ------------------------------------------------------------------------ losses -------------
def lsgan_disc_loss(real_outs, fake_outs):
    """LS-GAN discriminator loss: real->1, fake->0."""
    loss = 0.0
    for (r, _), (f, _) in zip(real_outs, fake_outs):
        loss = loss + ((r - 1) ** 2).mean() + (f ** 2).mean()
    return loss / max(len(real_outs), 1)


def lsgan_gen_loss(fake_outs):
    """LS-GAN generator loss: fool disc -> fake->1."""
    loss = 0.0
    for f, _ in fake_outs:
        loss = loss + ((f - 1) ** 2).mean()
    return loss / max(len(fake_outs), 1)


def feature_matching_loss(real_outs, fake_outs):
    """L1 between disc feature maps (stabilises GAN training, HiFi-GAN)."""
    loss = 0.0
    n = 0
    for (_, rf), (_, ff) in zip(real_outs, fake_outs):
        for r, f in zip(rf, ff):
            loss = loss + F.l1_loss(f, r.detach())
            n += 1
    return loss / max(n, 1)


def anti_wrapping_gd_loss(pred, target, n_fft=1024, hop=256):
    """Anti-wrapping GROUP-DELAY continuity term = GAN phase STABILISER (NOT a regression of
    the original phase). Penalises the wrapped difference of the across-frequency phase
    derivative, keeping the GAN's hallucinated group delay structurally continuous.
    pred/target: [B, T] mono."""
    w = torch.hann_window(n_fft, device=pred.device, dtype=pred.dtype)
    P = torch.stft(pred, n_fft, hop, n_fft, w, return_complex=True)
    T = torch.stft(target, n_fft, hop, n_fft, w, return_complex=True)
    # group delay = phase diff across adjacent frequency bins
    gp = torch.angle(P[:, 1:] * P[:, :-1].conj())
    gt = torch.angle(T[:, 1:] * T[:, :-1].conj())
    d = gp - gt
    wrapped = torch.atan2(torch.sin(d), torch.cos(d))     # shortest-path on the circle
    return wrapped.abs().mean()


if __name__ == "__main__":
    print("hf_repair_gen.py — import OK; run test_hf_repair_gen.py for unit tests")
