# Owner: KUANG (created 2026-10-17)
"""eval/adapter_spectrum_audit.py on synthetic checkpoints (CPU)."""
import os
import sys

import pytest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from adapter_spectrum_audit import audit, spectrum_metrics  # noqa: E402


def test_flat_vs_concentrated_spectrum():
    torch.manual_seed(0)
    Q1, _ = torch.linalg.qr(torch.randn(64, 16))
    Q2, _ = torch.linalg.qr(torch.randn(32, 16))
    flat = Q1 @ Q2.T                                   # 16 equal singular values
    conc = Q1 @ torch.diag(torch.tensor([10.0] + [0.1] * 15)) @ Q2.T
    f, c = spectrum_metrics(flat), spectrum_metrics(conc)
    assert f["stable_rank"] == pytest.approx(16.0, rel=1e-4) and abs(f["frob_nuclear"]) < 1e-5
    assert f["spectral_entropy"] == pytest.approx(1.0, abs=1e-5)
    assert c["stable_rank"] < 1.1 and c["frob_nuclear"] > 0.5 and c["condition"] == pytest.approx(100.0, rel=1e-3)
    # scale-invariant
    assert spectrum_metrics(3.0 * conc)["stable_rank"] == pytest.approx(c["stable_rank"])


def test_lora_pairs_use_the_product(tmp_path):
    torch.manual_seed(1)
    A, B = torch.randn(8, 48), torch.randn(40, 8)
    sd = {"blk.attn.to_q.lora_A": A, "blk.attn.to_q.lora_B": B, "blk.attn.to_q.weight": torch.randn(40, 48)}
    p = tmp_path / "ck.pt"
    torch.save({"state_dict": sd}, p)
    r = audit(str(p))
    assert len(r["matrices"]) == 1 and r["matrices"][0]["kind"] == "lora_BA"
    assert r["matrices"][0]["stable_rank"] == pytest.approx(spectrum_metrics(B @ A)["stable_rank"])


def test_delta_from_init(tmp_path):
    torch.manual_seed(2)
    W0 = torch.randn(32, 32)
    d = torch.randn(32, 1) @ torch.randn(1, 32)        # rank-1 change
    torch.save({"state_dict": {"adapter.w": W0 + d}}, tmp_path / "a.pt")
    torch.save({"state_dict": {"adapter.w": W0}}, tmp_path / "init.pt")
    init = torch.load(tmp_path / "init.pt")["state_dict"]
    r = audit(str(tmp_path / "a.pt"), init_sd=init)
    assert r["matrices"][0]["kind"] == "delta_from_init" and r["matrices"][0]["rank"] == 1
