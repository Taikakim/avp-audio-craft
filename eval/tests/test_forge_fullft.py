"""eval/forge/fullft.py: full-finetune checkpoints load over the DiT, online by default."""
from types import SimpleNamespace

import pytest
import torch
from torch import nn

import forge_testutil  # noqa: F401
from forge.fullft import load_fullft


def fake_model():
    dit = nn.Sequential(nn.Linear(4, 4), nn.Linear(4, 2))
    cond = nn.Module()
    cond.emb = nn.Linear(2, 2)
    return SimpleNamespace(model=SimpleNamespace(model=dit, conditioner=cond))


def ckpt(prefix, value, extra=None):
    m = fake_model().model.model
    sd = {f"{prefix}{k}": torch.full_like(v, value) for k, v in m.state_dict().items()}
    sd.update(extra or {})
    return {"state_dict": sd}


def test_online_is_default_and_lumi_prefix_is_stripped(tmp_path):
    p = tmp_path / "a.ckpt"
    torch.save(ckpt("diffusion.model.", 1.0), p)
    sd = torch.load(p)["state_dict"]
    sd.update({f"diffusion_ema.ema_model.{k[len('diffusion.model.'):]}": torch.zeros_like(v) + 2.0
               for k, v in list(sd.items())})
    torch.save({"state_dict": sd}, p)
    m = fake_model()
    out = load_fullft(m, p, log=lambda *_: None)
    assert out["weights"] == "online" and out["has_ema"] and out["coverage"] == 1.0
    assert float(m.model.model[0].weight[0, 0]) == 1.0
    load_fullft(m, p, weights="ema", log=lambda *_: None)
    assert float(m.model.model[0].weight[0, 0]) == 2.0


def test_refuses_ema_when_absent_and_part_load(tmp_path):
    p = tmp_path / "b.ckpt"
    torch.save(ckpt("model.", 1.0), p)
    with pytest.raises(ValueError, match="no EMA"):
        load_fullft(fake_model(), p, weights="ema", log=lambda *_: None)
    partial = ckpt("model.", 1.0)
    partial["state_dict"] = {k: v for k, v in partial["state_dict"].items() if k.startswith("model.0")}
    torch.save(partial, p)
    with pytest.raises(ValueError, match="covers only"):
        load_fullft(fake_model(), p, log=lambda *_: None)


def test_conditioner_tensors_are_loaded(tmp_path):
    p = tmp_path / "c.ckpt"
    extra = {"conditioner.emb.weight": torch.full((2, 2), 3.0), "conditioner.emb.bias": torch.zeros(2)}
    torch.save(ckpt("model.", 1.0, extra), p)
    m = fake_model()
    assert load_fullft(m, p, log=lambda *_: None)["conditioner"] == 2
    assert float(m.model.conditioner.emb.weight[0, 0]) == 3.0
