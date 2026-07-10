"""
chroma_losses.py -- phase-tolerant chroma guidance losses (the T2 ladder).

Design: docs/chroma-phase-tolerant-matching.md (Kim's verdict: frame-rigid chroma
matching = melody mush; "same pitch-class content + same movement shape within a
sliding window" should count as a match). This module is the ladder's home:

  rung 1  chroma_loss_rung1  -- Hann-smoothed content matching (HERE, validated)
  rung 2  contour-delta matching (Δchroma movement shape)      -- stub below
  rung 3  windowed soft-DTW                                    -- stub below

All losses take (B, T, C) or (T, C) float tensors: pred = the head's chroma
prediction for the CURRENT output latent, target = source-track chroma resampled
to the same T. Differentiable end-to-end (guidance backprops through pred only).

The tolerance dial: `w_sec` -- Hann window width in seconds. W→0 = frame-rigid,
W large = bag-of-pitch-classes. Kim will want to HEAR ~1 beat vs ~2 beats, so
express it in beats where the caller knows bpm: w_sec = beats * 60 / bpm.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def _as_btc(x):
    if x.dim() == 2:
        x = x.unsqueeze(0)
    if x.dim() != 3:
        raise ValueError(f"chroma tensor must be (B,T,C) or (T,C), got {tuple(x.shape)}")
    return x


def hann_smooth(x, w_frames: int):
    """Depthwise Hann smoothing along time. x: (B, T, C). w_frames<=1 = no-op.
    Reflect padding so edges don't droop toward zero."""
    if w_frames <= 1:
        return x
    b, t, c = x.shape
    k = torch.hann_window(w_frames, periodic=False, dtype=x.dtype, device=x.device)
    k = (k / k.sum()).view(1, 1, -1).expand(c, 1, -1)          # (C,1,W) depthwise
    xt = x.transpose(1, 2)                                      # (B,C,T)
    pad = (w_frames - 1) // 2
    xt = F.pad(xt, (pad, w_frames - 1 - pad), mode="reflect")
    return F.conv1d(xt, k, groups=c).transpose(1, 2)            # (B,T,C)


def chroma_loss_rung1(pred, target, fps: float, w_sec: float = 0.5,
                      metric: str = "cosine", eps: float = 1e-8):
    """Rung-1 phase-tolerant chroma loss: Hann-smooth BOTH sequences over w_sec,
    then frame-wise distance on the smoothed trajectories, mean over frames.

    Any rearrangement of pitch-class content *within* the window is free (the
    phase tolerance Kim asked for); content differences beyond the window cost.

    pred, target : (B,T,C) or (T,C), same T (resample target beforehand).
    fps          : frames/sec of the chroma sequences.
    w_sec        : tolerance window. ~1 beat = 60/bpm (0.43 s @140 bpm); Kim's
                   ear arbitrates 1 vs 2 beats. Default 0.5 s ≈ 1 beat @120.
    metric       : "cosine" (1 - cossim per frame; scale-invariant, matches the
                   pitch-class DISTRIBUTION not its energy) or "l2".
    Returns scalar (mean over batch+frames). Differentiable.
    """
    pred, target = _as_btc(pred), _as_btc(target)
    if pred.shape != target.shape:
        raise ValueError(f"shape mismatch {tuple(pred.shape)} vs {tuple(target.shape)}")
    w_frames = max(1, int(round(w_sec * fps)))
    ps = hann_smooth(pred, w_frames)
    ts = hann_smooth(target, w_frames)
    if metric == "cosine":
        sim = F.cosine_similarity(ps, ts, dim=-1, eps=eps)      # (B,T)
        return (1.0 - sim).mean()
    if metric == "l2":
        return (ps - ts).pow(2).mean()
    raise ValueError(f"unknown metric {metric!r}")


# ── rung 2/3 stubs (build only if Kim's ear says rung 1 is order-mushy) ─────────
def chroma_loss_rung2_contour(pred, target, fps, w_sec=0.5, alpha=0.5, **kw):
    """Rung 2: rung-1 content term + Δchroma movement-shape term ("2-D note
    vectors"). L = (1-alpha)*rung1 + alpha*rung1(Δpred, Δtarget). Kim's contour
    intuition, still O(T)."""
    base = chroma_loss_rung1(pred, target, fps, w_sec=w_sec, **kw)
    dp, dt = _as_btc(pred).diff(dim=1), _as_btc(target).diff(dim=1)
    mov = chroma_loss_rung1(dp, dt, fps, w_sec=w_sec, **kw)
    return (1.0 - alpha) * base + alpha * mov


def chroma_loss_rung3_softdtw(*a, **kw):  # pragma: no cover
    raise NotImplementedError(
        "windowed soft-DTW: build only if rung 1/2 fail Kim's ear "
        "(docs/chroma-phase-tolerant-matching.md §3)")


if __name__ == "__main__":
    # self-test: same melody shifted by < W must cost far less than a different
    # melody; frame-rigid (w_sec=0) must NOT forgive the shift.
    torch.manual_seed(0)
    fps, T, C = 21.5, 256, 12
    t = torch.arange(T)
    mel = F.one_hot((t // 22) % C, C).float() * 2.0             # slow melody, ~1 s/note
    mel = mel + 0.05 * torch.randn(T, C)
    shift = 6                                                    # ~0.28 s offset
    mel_shift = torch.roll(mel, shift, dims=0)
    other = F.one_hot(torch.randint(0, C, (T,)), C).float() * 2.0

    for w in (0.0, 0.5, 1.0):
        same = chroma_loss_rung1(mel_shift, mel, fps, w_sec=w).item()
        diff = chroma_loss_rung1(other, mel, fps, w_sec=w).item()
        print(f"w_sec={w:3.1f}  shifted-same={same:.4f}  different={diff:.4f}  "
              f"ratio={diff / max(same, 1e-9):5.1f}x")
    g = torch.zeros(T, C, requires_grad=True)
    chroma_loss_rung1(g, mel, fps, w_sec=0.5).backward()
    print("grad ok:", g.grad is not None and torch.isfinite(g.grad).all().item())
