"""dual_latch_guided_generate: the solver LOOP on a toy model (no SA3, no GPU).

SA3 / the LatCH loader / the DiT are replaced by a toy DiT (v = x - d for a fixed data tensor d), a toy
head (first K channels of x0) and fakes of the import surface. What this checks is the loop's own logic:
the guidance SIGN (guided < unguided < anti-guided final loss), the NaN guard, the loss switch, the diagnostics.
It says nothing about audio quality."""
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sa3_control.chroma_losses import chroma_loss_rung1  # noqa: E402

K, C, FPS = 8, 16, 44100 / 4096


class ToyDiT(torch.nn.Module):
    """Rectified-flow toy: data d (fixed, non-zero, zero-mean), v = x - d, so x0 = x - t*v = (1-t)x + t*d."""

    def __init__(self, nan_at=None):
        super().__init__()
        self.p = torch.nn.Parameter(torch.zeros(1))
        self.calls, self.nan_at, self.d = 0, nan_at, None

    def forward(self, x, t, **cond):
        self.calls += 1
        if self.d is None:
            self.d = torch.randn(x.shape, generator=torch.Generator().manual_seed(3))
        v = x - self.d
        if self.nan_at is not None and self.calls == self.nan_at:
            v[0, 0, 0] = float("nan")
        return v


class ToyHead(torch.nn.Module):
    def forward(self, x0, t):
        return x0[:, :K]


@pytest.fixture()
def gen(monkeypatch):
    def mod(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, m)
        return m

    mod("stable_audio_3", StableAudioModel=object)
    mod("stable_audio_3.models")
    mod("stable_audio_3.models.lora")
    mod("stable_audio_3.models.lora.model", set_lora_strength=lambda *a, **k: None)
    mod("stable_audio_3.inference")
    mod("stable_audio_3.inference.sampling",
        build_schedule=lambda steps, **k: torch.linspace(1.0, 0.0, steps + 1))
    mod("stable_audio_3.models.latch", load_latch_from_checkpoint=lambda path, device=None: ToyHead())
    mod("dual_conditioned_sample", _cond_inputs=lambda *a, **k: {})
    monkeypatch.delitem(sys.modules, "mixtape_v7_generative_inference", raising=False)
    return importlib.import_module("mixtape_v7_generative_inference")


def toy_model(dit):
    pre = SimpleNamespace(downsampling_ratio=4096, decode=lambda x: x)
    inner = SimpleNamespace(sample_rate=44100, pretransform=pre, io_channels=C, model=dit)
    return SimpleNamespace(device="cpu", model=inner, load_lora=lambda paths: None)


def target(frames):
    g = torch.Generator().manual_seed(7)
    return torch.rand(1, K, frames, generator=g) + 0.1


def final_loss(audio, tgt):
    return float(chroma_loss_rung1(audio[:K].T, tgt[0].T, FPS, w_sec=0.5))


def run(gen, dit=None, gain=50.0, **kw):
    dit = dit or ToyDiT()
    tgt = target(round(4.0 * FPS))
    diag = {}
    audio, sr = gen.dual_latch_guided_generate(
        toy_model(dit), "a", "b", "pa", "pb", 4.0, tgt, "head.pt",
        steps=24, latch_gain=gain, latch_end_pct=1.0, diag=diag, **kw)
    return audio, tgt, diag


def test_guidance_sign_guided_beats_unguided_beats_antiguided(gen):
    a0, tgt, _ = run(gen, gain=0.0)
    ap, _, dp = run(gen, gain=50.0)
    an, _, _ = run(gen, gain=-50.0)
    l0, lp, ln = final_loss(a0, tgt), final_loss(ap, tgt), final_loss(an, tgt)
    assert lp < l0 < ln, (lp, l0, ln)
    assert all(r > 0 for r in dp["guidance_rel"])


def test_nan_velocity_stops_at_the_step_it_happens(gen):
    with pytest.raises(FloatingPointError, match="step 2"):
        run(gen, dit=ToyDiT(nan_at=5))        # call 5 = step 2, second pass (calls come in A,B pairs): v_a at step 2 is call 5


def test_loss_switch_and_diagnostics_cover_the_guided_steps(gen):
    _, _, d = run(gen, loss="mse")
    assert len(d["guidance_rel"]) == 24 and len(d["loss"]) == 24     # latch_end_pct=1.0 -> every step but the last
    with pytest.raises(ValueError):
        run(gen, loss="bogus")


def test_guidance_stops_at_latch_end_pct(gen):
    diag = {}
    gen.dual_latch_guided_generate(toy_model(ToyDiT()), "a", "b", "pa", "pb", 4.0, target(round(4.0 * FPS)), "h.pt",
                                   steps=24, latch_gain=50.0, latch_end_pct=0.6, diag=diag)
    assert len(diag["guidance_rel"]) == 15                            # i / 24 <= 0.6  ->  i = 0..14
