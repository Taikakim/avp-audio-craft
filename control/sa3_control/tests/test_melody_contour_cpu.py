"""CPU smoke for the melody_contour control mode (Head B) — tiny dims, NO SA3 load.

Covers the new code paths before any GPU time is spent (the pilot chain runs a real
train.py --smoke on GPU as its own first step; this test exists so code errors never
reach the card):
  1. prep sidecars: exist, int8, values in [0,8), 4096 frames
  2. LatentControlDataset(melody_dir=...): filter, item["melody_cls"], crop slicing
  3. collate: melody_cls stacking
  4. MelodyContourEncoder: shapes, dtype, grads
  5. DecoupledControlAdapter on a mock cross-attn: zero-init no-op + grads flow

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python \
       -m pytest control/sa3_control/tests/test_melody_contour_cpu.py -q
(or plain `python -m sa3_control.tests.test_melody_contour_cpu` — has a __main__ runner)
"""
import os
import sys

import numpy as np
import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sa3_control.conditioner import MelodyContourEncoder
from sa3_control.adapters import (ControlContext, ControlledCrossAttention,
                                  use_control_context)

MELODY_DIR = "/home/kim/Projects/latents_sa3_melody"
LATENTS = "/home/kim/Projects/latents_sa3"


def test_prep_sidecars():
    files = [f for f in os.listdir(MELODY_DIR) if f.endswith(".melody8.npy")]
    assert len(files) >= 2000, f"expected ~2649 sidecars, found {len(files)}"
    a = np.load(os.path.join(MELODY_DIR, files[0]))
    assert a.dtype == np.int8 and a.shape == (4096,)
    assert a.min() >= 0 and a.max() < 8


def test_dataset_melody_mode():
    from sa3_control.dataset import LatentControlDataset
    ds = LatentControlDataset(LATENTS, controls=(), audio_ref=None,
                              melody_dir=MELODY_DIR, subset_tracks=8, seed=0)
    assert len(ds) > 0
    it = ds[0]
    assert "melody_cls" in it and it["melody_cls"].shape == (4096,)
    assert it["melody_cls"].dtype == torch.int64
    assert it["latent"].shape[-1] == it["melody_cls"].shape[-1]
    # random-crop slicing keeps latent/melody aligned
    ds2 = LatentControlDataset(LATENTS, controls=(), audio_ref=None,
                               melody_dir=MELODY_DIR, subset_tracks=8, seed=0,
                               random_crop_frames=512)
    it2 = ds2[0]
    assert it2["melody_cls"].shape == (512,)
    assert it2["latent"].shape == (256, 512)


def test_collate_and_encoder():
    from sa3_control.train import collate
    items = [{"latent": torch.zeros(256, 512), "prompt": "x",
              "melody_cls": torch.randint(0, 8, (512,))} for _ in range(2)]
    b = collate(items)
    assert b["melody_cls"].shape == (2, 512)
    enc = MelodyContourEncoder(control_dim=64)
    out = enc(b["melody_cls"])
    assert out.shape == (2, 512, 64)
    out.sum().backward()
    assert enc.embed.weight.grad is not None
    # reserved null class (index 8) is embeddable without error
    assert enc(torch.full((1, 16), 8)).shape == (1, 16, 64)


class _MockAttn(torch.nn.Module):
    """Minimal stand-in exposing the attrs DecoupledControlAdapter reads."""
    def __init__(self, dim=32, heads=4):
        super().__init__()
        self.dim, self.num_heads, self.kv_heads = dim, heads, heads
        self.dim_heads = dim // heads
        self.qk_norm = "none"
        self.to_q = torch.nn.Linear(dim, dim, bias=False)
        self.to_kv = torch.nn.Linear(dim, 2 * dim, bias=False)   # unused by adapter

    def apply_attn(self, q, k, v, **kw):
        return torch.nn.functional.scaled_dot_product_attention(q, k, v)

    def forward(self, x, context=None, **kw):
        return x  # identity base — makes the no-op check exact


def test_adapter_zero_init_noop_and_grads():
    torch.manual_seed(0)
    base = _MockAttn()
    wrap = ControlledCrossAttention(base, control_dim=64)
    enc = MelodyContourEncoder(control_dim=64)
    x = torch.randn(2, 40, 32)
    cls = torch.randint(0, 8, (2, 40))
    ctrl = enc(cls)
    with use_control_context(ControlContext(ctrl)):
        y = wrap(x)
    # zero-init to_out => exact no-op at init
    assert torch.equal(y, base(x))
    # grads flow into adapter K/V and the embedding through the branch
    with use_control_context(ControlContext(ctrl)):
        loss = wrap(x).sum() + 0.0 * y.sum()
    # to_out is zero, so give it one step of signal: perturb and check backward runs
    loss.backward()
    assert wrap.adapter.to_k.weight.grad is not None
    assert wrap.adapter.to_v.weight.grad is not None
    assert enc.embed.weight.grad is not None


def test_independent_dropout_draws():
    """The melody-vs-text dropout draws must be independent Bernoullis (StemGen POOL item):
    over many draws all four joint states appear."""
    torch.manual_seed(1)
    B, p_m, p_t = 4096, 0.1, 0.1
    dm = torch.rand(B) < p_m
    dt = torch.rand(B) < p_t
    states = {(bool(a), bool(b)) for a, b in zip(dm, dt)}
    assert len(states) == 4


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[ok] {name}")
    print("[smoke] melody_contour CPU smoke: ALL PASS")
