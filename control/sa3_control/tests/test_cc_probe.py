# tests/test_cc_probe.py — control-consistency loss components (spec:
# SAO/docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md)
#
# RF convention (train.py:399-401):  noised = clean*(1-t) + noise*t ; v = noise - clean
# =>  z0_hat = noised - t * v_pred   (exact recovery when v_pred == v)
import torch

from sa3_control.cc_probe import OnsetDensityProbe, rf_z0_hat, control_consistency_loss


def test_rf_z0_hat_recovers_clean_exactly():
    torch.manual_seed(0)
    clean = torch.randn(2, 256, 512)
    noise = torch.randn_like(clean)
    t = torch.tensor([0.3, 0.8])
    tb = t.view(-1, 1, 1)
    noised = clean * (1 - tb) + noise * tb
    v_true = noise - clean
    z0 = rf_z0_hat(noised, v_true, t)
    assert torch.allclose(z0, clean, atol=1e-5), (z0 - clean).abs().max()


def test_probe_shapes_and_scalar_output():
    probe = OnsetDensityProbe(in_ch=256)
    z = torch.randn(3, 256, 512)
    out = probe(z)
    assert out.shape == (3,), out.shape
    # variable T (random-crop windows differ; GAP must handle it)
    assert probe(torch.randn(1, 256, 384)).shape == (1,)


def test_probe_is_small():
    n = sum(p.numel() for p in OnsetDensityProbe(in_ch=256).parameters())
    assert n < 1_000_000, f"probe too big: {n}"


def test_cc_loss_gates_by_t():
    """Rows with t >= t_max contribute nothing; all-gated batch -> loss 0 (no NaN)."""
    torch.manual_seed(0)
    probe = OnsetDensityProbe(in_ch=256).eval()
    z0 = torch.randn(2, 256, 128)
    scalar = torch.tensor([0.5, -0.2])
    # one row inside the gate, one outside
    loss_half = control_consistency_loss(probe, z0, scalar, t=torch.tensor([0.2, 0.9]), t_max=0.5)
    assert torch.isfinite(loss_half) and loss_half.item() >= 0.0
    # everything outside the gate -> exactly zero, still finite/differentiable-safe
    loss_none = control_consistency_loss(probe, z0, scalar, t=torch.tensor([0.9, 0.95]), t_max=0.5)
    assert loss_none.item() == 0.0


def test_cc_loss_backprops_to_z0():
    """The term must carry gradient to the latent estimate (i.e. into the DiT)."""
    probe = OnsetDensityProbe(in_ch=256).eval()
    for p in probe.parameters():
        p.requires_grad_(False)
    z0 = torch.randn(1, 256, 128, requires_grad=True)
    loss = control_consistency_loss(probe, z0, torch.tensor([0.7]), t=torch.tensor([0.1]), t_max=0.5)
    loss.backward()
    assert z0.grad is not None and torch.isfinite(z0.grad).all() and z0.grad.abs().sum() > 0


def test_probe_vector_output():
    """out_dim>1: latent window -> genre-fingerprint vector (the W pairing)."""
    probe = OnsetDensityProbe(in_ch=256, out_dim=12)
    out = probe(torch.randn(3, 256, 128))
    assert out.shape == (3, 12), out.shape


def test_cc_loss_vector_targets():
    """control_consistency_loss must accept (B, D) vector requests (genre fingerprints)."""
    probe = OnsetDensityProbe(in_ch=256, out_dim=12).eval()
    z0 = torch.randn(2, 256, 64, requires_grad=True)
    req = torch.rand(2, 12)
    loss = control_consistency_loss(probe, z0, req, t=torch.tensor([0.1, 0.2]), t_max=0.5)
    assert torch.isfinite(loss)
    loss.backward()
    assert z0.grad is not None and z0.grad.abs().sum() > 0
