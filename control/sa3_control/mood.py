"""Mood control for the FiLM adapter (--control-mode mood). KUANG 2026-10-31.

ONE adapter learns every mood tag: the conditioning vector is [value_1..value_K, present_1..present_K]
(in_dim = 2K) into the existing FingerprintEncoder (learned tokens FiLM-modulated by the vector, decoupled
cross-attention, base frozen). The adapter + encoder save to their own .pt beside the untouched base, so the
head is detachable and gain-scalable like the density FiLM adapter.

  value_k   window mean of tag k's curve in the census spec's units: z-scored log-odds over the TRAIN
            split (stable-audio-3 scripts/latch/mood_targets.apply_spec), so +2 = two SD above the corpus.
  present_k 1 if the tag is set. Training keeps a random non-empty subset of tags per item (subset size
            uniform in 1..K), so "dark +2, everything else free" is in distribution; an absent tag has
            value 0 AND present 0, which is different from "set to the corpus mean" (value 0, present 1).

No mood at all is the existing per-item token dropout (--cfg-dropout zeroes the control tokens): the null
for CFG and for "this adapter off" is zero tokens, as in fingerprint mode.

The spec's mean/std are a unit, not labels: they come from the census split (LatCH's song-grouped split),
not from this trainer's track split, so a few of this run's val tracks may have contributed to the unit.
That does not leak targets; it is noted, not enforced.
"""
from __future__ import annotations

import os

import numpy as np
import torch

SA3_ROOT_DEFAULT = "/home/kim/Projects/SAO/stable-audio-3"


_MT = None


def mood_targets():
    """The census spec helpers live in stable-audio-3 (scripts/latch/mood_targets.py); one copy, no drift.
    SA3_ROOT names the checkout explicitly (loaded by file path, so another checkout's `scripts` package
    on sys.path cannot shadow it); otherwise an importable scripts.latch.mood_targets, else the desktop
    default checkout."""
    global _MT
    if _MT is not None:
        return _MT
    root = os.environ.get("SA3_ROOT")
    if not root:
        try:
            from scripts.latch import mood_targets as mt
            _MT = mt
            return mt
        except ImportError:
            root = SA3_ROOT_DEFAULT
    import importlib.util
    path = os.path.join(root, "scripts", "latch", "mood_targets.py")
    if not os.path.exists(path):
        raise ImportError(f"no {path}: set SA3_ROOT to a stable-audio-3 checkout with the mood census")
    spec = importlib.util.spec_from_file_location("sa3_mood_targets", path)
    mt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt)
    _MT = mt
    return mt


def in_dim(spec: dict) -> int:
    return 2 * len(spec["names"])


def window_values(curves: torch.Tensor, clip: float) -> torch.Tensor:
    """(B, K, T) spec-unit curves (already sliced to the trained window) -> (B, K) window means, clipped
    to +-clip so a rare extreme crop cannot teach the FiLM layer an out-of-range response."""
    return curves.float().mean(dim=-1).clamp(-clip, clip)


def sample_tag_mask(batch: int, k: int, device=None, generator=None) -> torch.Tensor:
    """(B, K) 0/1 masks: per item a subset of size uniform in 1..K, uniformly chosen. Never empty
    (the empty request is token dropout, not an all-absent vector)."""
    size = torch.randint(1, k + 1, (batch, 1), device=device, generator=generator)
    rank = torch.rand(batch, k, device=device, generator=generator).argsort(dim=1).argsort(dim=1)
    return (rank < size).float()


def build_vector(values: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """(B, K) values + (B, K) mask -> (B, 2K) conditioning vector."""
    return torch.cat([values * mask, mask], dim=1)


def request_vector(spec: dict, request: dict, clip: float = 3.0) -> torch.Tensor:
    """Inference: {"dark": 2.0, "energetic": -1.0} -> (2K,) vector; unnamed tags are absent.
    Values are clipped like training; an empty request has no vector (use zero control tokens)."""
    names = list(spec["names"])
    unknown = set(request) - set(names)
    if unknown:
        raise ValueError(f"not in this spec: {sorted(unknown)}; tags are {names}")
    if not request:
        raise ValueError("empty mood request: run without the adapter, or with zero control tokens")
    vals = torch.tensor([float(np.clip(request.get(n, 0.0), -clip, clip)) for n in names])
    mask = torch.tensor([1.0 if n in request else 0.0 for n in names])
    return build_vector(vals[None], mask[None])[0]


def parse_request(text: str) -> dict:
    """'dark=2,energetic=-1' -> {'dark': 2.0, 'energetic': -1.0}"""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, val = part.partition("=")
        if not val:
            raise ValueError(f"mood request item {part!r} is not name=value")
        out[name.strip()] = float(val)
    return out
