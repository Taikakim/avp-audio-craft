import pytest
import torch

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.mixing import lerp, mix_latents, normalise


def lat(v):
    return torch.full((1, 4, 3), float(v))


def nodes(**kw):
    base = {k: {"interp": "lerp", "t": 0.5} for k in ("M1", "M2", "MX")}
    base.update(kw)
    return base


def test_tree_lerp_weights():
    z, w = mix_latents([lat(1), lat(3), lat(5), lat(7)], {"order": "tree", "nodes": nodes(), "quad_weights": [1] * 4})
    assert torch.allclose(z, lat(4.0))
    assert w == pytest.approx([0.25, 0.25, 0.25, 0.25])


def test_cascade_t_semantics():
    z, w = mix_latents([lat(0), lat(10), lat(20), lat(30)],
                       {"order": "cascade", "nodes": nodes(M1={"interp": "lerp", "t": 0.0},
                                                           M2={"interp": "lerp", "t": 1.0},
                                                           MX={"interp": "lerp", "t": 0.25}),
                        "quad_weights": [1] * 4})
    # M1 = L1 (t=0) = 0 ; M2 = L3 (t=1) = 20 ; MX = .75*20 + .25*30 = 22.5
    assert torch.allclose(z, lat(22.5))
    assert w == pytest.approx([0.0, 0.0, 0.75, 0.25])


def test_unused_lanes_pass_through():
    z, w = mix_latents([None, lat(3), None, None], {"order": "tree", "nodes": nodes(), "quad_weights": [1] * 4})
    assert torch.allclose(z, lat(3)) and w == [0.0, 1.0, 0.0, 0.0]
    with pytest.raises(ForgeError):
        mix_latents([None] * 4, {"order": "tree", "nodes": nodes(), "quad_weights": [1] * 4})


def test_quad_and_zero_weights():
    z, w = mix_latents([lat(2), None, lat(6), None], {"order": "quad", "nodes": nodes(), "quad_weights": [3, 9, 1, 0]})
    assert torch.allclose(z, lat(0.75 * 2 + 0.25 * 6)) and w == pytest.approx([0.75, 0, 0.25, 0])
    z, w = mix_latents([lat(2), lat(4), None, None], {"order": "quad", "nodes": nodes(), "quad_weights": [0, 0, 0, 0]})
    assert torch.allclose(z, lat(3)) and w == pytest.approx([0.5, 0.5, 0, 0])


def test_slerp_fn_used():
    calls = []

    def fake_slerp(a, b, t):
        calls.append(t)
        return lerp(a, b, t)

    mix_latents([lat(1), lat(2), None, None],
                {"order": "tree", "nodes": nodes(M1={"interp": "slerp", "t": 0.3}), "quad_weights": [1] * 4},
                slerp_fn=fake_slerp)
    assert calls == [0.3]


def test_normalise_restores_norm():
    a = torch.zeros(1, 2, 2); a[0, 0] = 1.0
    b = torch.zeros(1, 2, 2); b[0, 1] = 1.0
    z = lerp(a, b, 0.5)                                  # norm 0.707 per frame
    out = normalise(z, [a, b, None, None], [0.5, 0.5, 0, 0])
    assert torch.allclose(out.norm(dim=1), torch.ones(1, 2), atol=1e-6)
