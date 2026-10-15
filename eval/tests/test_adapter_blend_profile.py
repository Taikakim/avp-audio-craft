# Owner: KUANG (created 2026-10-15)
"""Per-block DoRA profile (_apply_block_profile, GHOST-NOTE 2026-10-15) + the adapter-mixer phase-1 notification:
blend "interp" on an adapter type whose forward ignores `lora_interp` is reported in the request's warnings.

Runs where explorer_render_server imports (the desktop); skips elsewhere. The adapter class is faked, so no model or
GPU is needed.
"""
import types

import pytest

import forge_testutil  # noqa: F401  (puts this worktree's eval/ first on sys.path)

torch = pytest.importorskip("torch")
try:
    import explorer_render_server as S
except Exception as e:  # pragma: no cover - environment dependent
    pytest.skip(f"explorer_render_server not importable here: {e}", allow_module_level=True)


class FakeParam:
    def __init__(self, adapter_type):
        self.adapter_type = adapter_type
        self.lora_strength = torch.tensor(1.0)
        self.lora_interp = False


def fake_model(types_by_block):
    """model.model.named_modules() -> DiT linear layers `transformer.layers.<i>.ff`, one adapter each, plus a
    conditioner layer that must be skipped."""
    mods = []
    for i, kind in enumerate(types_by_block):
        m = types.SimpleNamespace(parametrizations=types.SimpleNamespace(weight=[FakeParam(kind)]))
        mods.append((f"transformer.layers.{i}.ff", m))
    cond = types.SimpleNamespace(parametrizations=types.SimpleNamespace(weight=[FakeParam("dora")]))
    mods.append(("conditioner.t5.layers.0.ff", cond))
    inner = types.SimpleNamespace(named_modules=lambda: iter(mods))
    return types.SimpleNamespace(model=inner), mods


@pytest.fixture(autouse=True)
def fake_lora_module(monkeypatch):
    mod = types.ModuleType("stable_audio_3.models.lora.model")
    mod.LoRAParametrization = FakeParam
    monkeypatch.setitem(__import__("sys").modules, "stable_audio_3.models.lora.model", mod)


def test_interp_on_dora_rows_and_lora_is_silent():
    model, mods = fake_model(["dora-rows", "lora", "dora"])
    S._apply_block_profile(model, 1.0, [0.5, 1.0, 0.25], "interp")
    assert S.profile_warnings() == []
    ps = [m.parametrizations.weight[0] for _, m in mods]
    assert [float(p.lora_strength) for p in ps[:3]] == [0.5, 1.0, 0.25]
    assert all(p.lora_interp for p in ps[:3])
    assert float(ps[3].lora_strength) == 1.0                  # the conditioner's layers.0 is not block 0


def test_interp_on_unsupported_types_is_reported():
    model, _ = fake_model(["dora-rows", "bora", "dora-rows-xs"])
    S._apply_block_profile(model, 1.0, [1.0] * 3, "interp")
    w = S.profile_warnings()
    assert len(w) == 1 and "bora" in w[0] and "dora-rows-xs" in w[0] and "direction" in w[0]


def test_direction_mode_and_clearing():
    model, _ = fake_model(["bora"])
    S._apply_block_profile(model, 1.0, [1.0], "interp")
    assert S.profile_warnings()
    S._apply_block_profile(model, 1.0, [1.0], None)           # direction mode: nothing to report
    assert S.profile_warnings() == []
