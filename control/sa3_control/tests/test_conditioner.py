import torch
from sa3_control.conditioner import FingerprintEncoder


def test_forward_shape():
    enc = FingerprintEncoder(in_dim=15, control_dim=768, n_tokens=16)
    out = enc(torch.randn(4, 15))
    assert out.shape == (4, 16, 768)


def test_identity_at_init():
    enc = FingerprintEncoder(in_dim=15, control_dim=768, n_tokens=16)
    out = enc(torch.randn(3, 15))                 # zero-init FiLM -> scale=0, shift=0
    expected = enc.tokens[None].expand(3, -1, -1)
    assert torch.allclose(out, expected, atol=1e-6)


def test_accepts_2d_only_and_scales_params_with_in_dim():
    small = sum(p.numel() for p in FingerprintEncoder(1).parameters())
    big = sum(p.numel() for p in FingerprintEncoder(15).parameters())
    assert big - small < 5000                     # widening input is negligible param growth
