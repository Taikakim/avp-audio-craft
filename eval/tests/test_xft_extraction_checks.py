"""eval/xft_extraction_checks.py: families, the shared SVD, padding, variant composition, the probe,
and the full-rank extract through the real SA3 LoRA loader on a tiny model (CPU)."""
import math

import pytest
import torch
from torch import nn

import forge_testutil  # noqa: F401
import extract_svd_adapters as xsvd
import xft_extraction_checks as xc


def test_family_rules():
    assert xc.family("model.transformer.layers.3.to_scale_shift_gate") == "adaln_gate"
    assert xc.family("model.transformer.memory_tokens") == "memory_tokens"
    assert xc.family("model.transformer.layers.3.self_attn.q_norm.gamma") == "qk_norm"
    assert xc.family("model.transformer.layers.3.pre_norm.gamma") == "norm"
    assert xc.family("model.transformer.layers.3.self_attn.to_qkv.weight") == "self_attn"
    assert xc.family("model.transformer.layers.3.cross_attn.to_kv.weight") == "cross_attn"
    assert xc.family("model.transformer.layers.3.ff.ff.0.proj.bias") == "ff"
    assert xc.family("conditioners.seconds_total.embedder.weight") == "conditioner"
    assert xc.attn_blocks("model.transformer.layers.0.self_attn.to_qkv") == ("q", "k", "v", "q2", "k2")
    assert xc.attn_blocks("model.transformer.layers.0.cross_attn.to_kv") == ("k", "k2", "v")
    assert xc.is_attn("model.transformer.layers.0.cross_attn.to_out") and not xc.is_attn("model.x.ff.y")


def test_svd_module_matches_the_extractor_and_full_rank_is_exact():
    g = torch.Generator().manual_seed(0)
    base, ft = torch.randn(10, 6, generator=g), torch.randn(10, 6, generator=g)
    B, A, kept, d, tot = xc.svd_module(base, ft, ranks=(2, 6))
    assert torch.allclose(B @ A, ft - base, atol=1e-5)
    assert kept[6] == pytest.approx(1.0) and 0 < kept[2] < 1
    A2, B2, _ = xsvd.extract_module(base, ft, 2)
    assert torch.allclose(B[:, :2], B2, atol=1e-6) and torch.allclose(A[:2], A2, atol=1e-6)


def test_block_errors_split_the_fused_rows():
    g = torch.Generator().manual_seed(1)
    base = torch.zeros(10, 4)
    ft = torch.zeros(10, 4)
    ft[:2] = torch.randn(2, 4, generator=g) * 10      # block q carries almost all the energy
    ft[2:] = torch.randn(8, 4, generator=g) * 0.1
    B, A, _, d, _ = xc.svd_module(base, ft, ranks=(2, 4))
    err = xc.block_errors(d, B, A, ("q", "k", "v", "q2", "k2"), ranks=(2, 4))
    assert err["r4_q"] < 1e-6 and err["r4_k2"] < 1e-6
    assert err["r2_q"] < 0.01 < err["r2_k"]          # rank goes to the loud block first


def test_pad_factors_keeps_the_product():
    B, A = torch.randn(5, 3), torch.randn(3, 4)
    Bp, Ap = xc.pad_factors(B, A, 6)
    assert Bp.shape == (5, 6) and Ap.shape == (6, 4) and torch.allclose(Bp @ Ap, B @ A)
    with pytest.raises(ValueError):
        xc.pad_factors(B, A, 2)


def _states():
    g = torch.Generator().manual_seed(2)
    base = {"model.a.weight": torch.randn(6, 4, generator=g), "model.a.bias": torch.zeros(6),
            "model.attn.self_attn.to_qkv.weight": torch.randn(10, 4, generator=g),
            "model.gate": torch.zeros(3)}
    ft = {k: v + 0.1 * torch.randn(v.shape, generator=g) for k, v in base.items()}
    targets = ["model.a", "model.attn.self_attn.to_qkv"]
    factors = {m: xc.svd_module(base[m + ".weight"], ft[m + ".weight"], (1, 4))[:2] for m in targets}
    return base, ft, targets, factors


def test_compose_variants():
    base, ft, targets, factors = _states()
    specs = {s["name"]: s for s in xc.variant_specs([1]) if s["kind"] == "weights"}

    def build(name):
        s = specs[name]
        return xc.compose(base, ft, targets, factors, s["w"], s["n"])

    full = build("fullft")
    assert all(torch.equal(full[k], ft[k]) for k in base)
    mo = build("matrices_only")
    assert torch.equal(mo["model.a.weight"], ft["model.a.weight"]) and torch.equal(mo["model.gate"], base["model.gate"])
    nm = build("nonmatrix_only")
    assert torch.equal(nm["model.a.weight"], base["model.a.weight"]) and torch.equal(nm["model.a.bias"], ft["model.a.bias"])
    at = build("attn_r1")
    assert torch.equal(at["model.a.weight"], ft["model.a.weight"])
    assert not torch.allclose(at["model.attn.self_attn.to_qkv.weight"], ft["model.attn.self_attn.to_qkv.weight"])
    na = build("nonattn_r1")
    assert torch.equal(na["model.attn.self_attn.to_qkv.weight"], ft["model.attn.self_attn.to_qkv.weight"])
    r1 = build("all_r1")
    B, A = factors["model.a"]
    assert torch.allclose(r1["model.a.weight"], base["model.a.weight"] + B[:, :1] @ A[:1])
    # full rank in weight space is the fine-tune
    full_rank = xc.compose(base, ft, targets, factors, lambda m: 4, "ft")
    assert all(torch.allclose(full_rank[k], ft[k], atol=1e-5) for k in base)


def test_measure_and_summary_separate_target_from_omitted():
    base, ft, targets, _ = _states()
    rows = xc.measure(base, ft, targets)
    by = {r["name"]: r for r in rows}
    assert by["model.a.weight"]["target"] and not by["model.gate"]["target"]
    assert by["model.gate"]["bf16_floor"] == 0.0                   # zeros are exact in bf16
    s = xc.summarize(rows)
    assert s["_omitted_total"]["tensors"] == 2 and s["_omitted_total"]["changed"] == 2
    shares = sum(v["delta_energy_share"] for k, v in s.items() if not k.startswith("_"))
    assert shares == pytest.approx(1.0)


def test_split_state_online_ema_and_conditioner():
    raw = {"diffusion.model.model.x": torch.ones(1), "diffusion_ema.ema_model.model.x": torch.zeros(1),
           "diffusion.conditioner.conditioners.c.weight": torch.ones(1), "other": torch.ones(1)}
    on, ema = xc.split_state(raw), xc.split_state(raw, "ema")
    assert set(on) == {"model.x", "conditioners.c.weight"} and float(on["model.x"]) == 1.0
    assert float(ema["model.x"]) == 0.0 and "conditioners.c.weight" in ema


def test_recorder_and_probe_errors():
    lin = nn.Linear(3, 3)
    rec = xc.CallRecorder(lin)
    x = torch.randn(2, 3)
    y = lin(x)
    lin(input=x)                                                  # kwargs are recorded too
    rec.close()
    assert len(rec.calls) == 2
    outs = xc.replay(lin, rec.calls, "cpu")
    assert torch.allclose(outs[0], y)
    ref = [torch.ones(4)] * 3
    base = [torch.zeros(4)] * 3
    e = xc.probe_errors([torch.full((4,), 0.5)] * 3, ref, base, twin=ref)
    assert e["rel_change"]["mean"] == pytest.approx(0.5) and e["rel_ft"]["mean"] == pytest.approx(0.5)
    assert e["rel_twin"]["early"] == pytest.approx(0.5)


def test_audio_stats():
    sr = 44100
    t = torch.arange(sr) / sr
    a = torch.stack([torch.sin(2 * math.pi * 440 * t)] * 2)
    s = xc.audio_stats(a, sr)
    assert s["peak"] == pytest.approx(1.0, abs=1e-3) and s["hf16k_share"] < 1e-6 and s["nonfinite"] == 0


# ------------------------------------------------- the real loader, full rank, on a tiny model

class _Tiny(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = nn.Module()
        self.model.model = nn.Module()
        self.model.model.a = nn.Linear(4, 6, bias=False)
        self.model.model.b = nn.Linear(6, 3, bias=False)          # min dim 3 < the padded rank
        self.conditioner = nn.Module()
        self.conditioner.conditioners = nn.ModuleDict({"c": nn.Linear(2, 2, bias=False)})


@pytest.mark.parametrize("method,ext,tol", [("lora", ".ckpt", 1e-5), ("dora-rows", ".ckpt", 1e-5),
                                            ("lora", ".safetensors", 2e-2), ("dora-rows", ".safetensors", 2e-2)])
def test_full_rank_extract_through_the_loader_reproduces_the_finetune(tmp_path, method, ext, tol):
    loader = pytest.importorskip("stable_audio_3.models.lora.loader")
    torch.manual_seed(3)
    m = _Tiny()
    # the extractor's namespace: DiTWrapper-relative "model.X" (the loader gets the wrapper above it)
    base = {k: v.clone() for sub in (m.model, m.conditioner) for k, v in sub.state_dict().items()}
    ft = {k: v + 0.05 * torch.randn_like(v) for k, v in base.items()}
    targets = [k[: -len(".weight")] for k in base]
    full, pad = {}, 0
    for mod in targets:
        B, A, _, d, _ = xc.svd_module(base[mod + ".weight"], ft[mod + ".weight"], (1,))
        full[mod] = (B, A)
        pad = max(pad, min(d.shape))
    sd = xc.adapter_state(full, ft, None, method, pad_to=pad,
                          dtype=torch.float16 if ext == ".safetensors" else torch.float32)
    path = xc.write_adapter(sd, pad, method, tmp_path / f"a{ext}", "test")
    loader.load_and_apply_loras(m, [str(path)], "diffusion_cond")
    with torch.no_grad():
        for mod in targets:
            lin = (m.conditioner if mod.startswith("conditioners.") else m.model).get_submodule(mod)
            want, was = ft[mod + ".weight"], base[mod + ".weight"]
            err = float((lin.weight - want).norm() / (want - was).norm())
            assert err < tol, f"{mod}: effective weight is {err:.3g} of the delta away from the fine-tune"


# ------------------------------------------- render stage end to end on a fake StableAudioModel

class _FakeDiT(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = nn.Module()
        self.model.a = nn.Linear(4, 4)
        self.model.blk = nn.Module()
        self.model.blk.self_attn = nn.Module()
        self.model.blk.self_attn.to_qkv = nn.Linear(4, 10, bias=False)
        self.model.gate = nn.Parameter(torch.zeros(4))

    def forward(self, x, t, cond=None):
        h = self.model.a(x) * (1 + self.model.gate)
        return h + self.model.blk.self_attn.to_qkv(h)[:, :4] + 0 * t


class _FakeSA:
    def __init__(self):
        torch.manual_seed(0)
        self.model = nn.Module()
        self.model.model = _FakeDiT()
        self.model.conditioner = nn.Module()
        self.model.conditioner.conditioners = nn.ModuleDict({"c": nn.Linear(2, 2, bias=False)})
        self.model.sample_rate = 8000

    def load_lora(self, paths):
        from stable_audio_3.models.lora.loader import load_and_apply_loras
        load_and_apply_loras(self.model, paths, "diffusion_cond")

    @torch.inference_mode()
    def generate(self, prompt, duration, steps, cfg_scale, seed, latents_sink):
        torch.manual_seed(seed)
        x = torch.randn(1, 4)
        for i in range(steps):
            x = x - 0.1 * self.model.model(x, torch.tensor(1.0 - i / steps), cond={"prompt": prompt})
        latents_sink.append(x.clone())
        n = int(duration * self.model.sample_rate)
        t = torch.arange(n) / self.model.sample_rate
        return (0.5 * torch.tanh(x.sum()) * torch.sin(2 * math.pi * 220 * t)).expand(1, 2, n)


def test_render_stage_end_to_end_on_a_fake_model(tmp_path, monkeypatch):
    pytest.importorskip("stable_audio_3.models.lora.loader")
    pytest.importorskip("soundfile")
    from pathlib import Path
    from types import SimpleNamespace
    fake = _FakeSA()
    base = {k: v.detach().clone() for sub in (fake.model.model, fake.model.conditioner)
            for k, v in sub.state_dict().items()}
    g = torch.Generator().manual_seed(5)
    ft = {k: v + 0.2 * torch.randn(v.shape, generator=g) for k, v in base.items()}
    targets = ["model.a", "model.blk.self_attn.to_qkv", "conditioners.c"]
    monkeypatch.setattr(xc, "load_model", lambda args: _FakeSA())
    args = SimpleNamespace(stage="all", variants=None, svd_device="cpu", ckpt=Path("fake.ckpt"),
                           prompts=["p"], seeds=[1, 2], duration=0.05, steps=4, cfg=1.0, probe_renders=1,
                           fp32=True, device="cpu")
    xc.run_measure(args, base, ft, {}, targets, tmp_path / "measure", [1])
    trunc, adapters = xc.run_svd(args, base, ft, targets, tmp_path / "measure", [1])
    assert {"loader_lora_full_fp16", "loader_dora_full_fp32", "loader_dora_r1"} <= set(adapters)
    xc.run_render(args, base, ft, targets, trunc, adapters, tmp_path / "render", [1])
    import json
    rep = json.loads((tmp_path / "render" / "report.json").read_text())["variants"]
    probe = {n: next(iter(v["probe"].values())) for n, v in rep.items()}
    assert probe["fullft"]["rel_ft"]["mean"] < 1e-6                       # replay is deterministic
    assert probe["base"]["rel_change"]["mean"] == pytest.approx(1.0)
    assert probe["matrices_only"]["rel_change"]["mean"] > 0.01              # the gate delta is missing
    assert probe["loader_dora_full_fp32"]["rel_twin"]["mean"] < 1e-4         # loader == matrices_only
    assert probe["loader_lora_r1"]["rel_twin"]["mean"] < 2e-3                # fp16 file == merged all_r1
    assert (tmp_path / "render" / "fullft" / "p0_s2.wav").exists()
    assert "| loader_dora_full_fp16 |" in (tmp_path / "render" / "report.md").read_text()
