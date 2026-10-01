import math

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import schedule as S
from forge.contract import ForgeError


def spec(**kw):
    return S.parse_spec(kw)


def test_defaults_and_model_shape():
    assert S.parse_spec(None) == S.DEFAULTS
    assert S.DEFAULTS == {"shape": "model", "rho": 1.0, "sigma_min": 0.01, "lam_min": -6.2, "lam_max": 2.0,
                          "stepped": False, "plateaus": 6, "tilt": 0.15}
    assert S.resolve_schedule({}, 24, 1.0) == (None, [])
    assert S.resolve_schedule({"schedule": {"shape": "model"}, "dist_shift": 3.0}, 24, 1.0) == (None, [])


@pytest.mark.parametrize("bad", [
    "x", {"shape": "karras"}, {"rho": 0.05}, {"sigma_min": 0.9}, {"lam_min": 1.0}, {"lam_max": -1.0},
    {"plateaus": 1}, {"plateaus": 2.5}, {"tilt": 1.5}, {"stepped": "yes"}, {"bogus": 1},
    {"lam_min": -2.0, "lam_max": 0.0} | {"lam_max": 0.0, "lam_min": 0.0},
])
def test_parse_rejects(bad):
    with pytest.raises(ForgeError) as e:
        S.parse_spec(bad)
    assert e.value.status == 400


def test_linear_values():
    a = S.sigmas(spec(shape="linear", sigma_min=0.1), 4, 1.0)
    np.testing.assert_allclose(a, [1.0, 0.775, 0.55, 0.325, 0.0])


def test_geometric_and_cosine_endpoints():
    g = S.sigmas(spec(shape="geometric", sigma_min=0.01), 10, 1.0)
    assert g[0] == 1.0 and g[-1] == 0.0
    assert g[5] == pytest.approx(math.exp(math.log(0.01) * 0.5))
    c = S.sigmas(spec(shape="cosine", sigma_min=0.02), 2, 1.0)
    np.testing.assert_allclose(c, [1.0, 0.02 + 0.98 * 0.5, 0.0])


def test_logsnr_matches_design_formula():
    a = S.sigmas(spec(shape="logsnr"), 8, 1.0)
    lam = -6.2 + 8.2 * (3 / 8)
    assert a[3] == pytest.approx(1 / (1 + math.exp(lam)))
    assert a[0] == 1.0 and a[-1] == 0.0


def test_logsnr_truncates_at_noise_level():
    a = S.sigmas(spec(shape="logsnr"), 8, 0.4)
    assert a[0] == 0.4
    assert a[1] < 0.4
    assert np.all(np.diff(a) <= 1e-12)


def test_log_and_exponential():
    lg = S.sigmas(spec(shape="log", sigma_min=0.0 + 0.01), 2, 1.0)
    assert lg[1] == pytest.approx(1.0 + (0.01 - 1.0) * math.log1p(9 * 0.5) / math.log(10))
    ex = S.sigmas(spec(shape="exponential", sigma_min=0.01), 2, 1.0)
    assert ex[1] == pytest.approx(1.0 + (0.01 - 1.0) * (math.exp(1.5) - 1) / (math.exp(3) - 1))


def test_rho_warps():
    a = S.sigmas(spec(shape="linear", sigma_min=0.1, rho=2.0), 4, 1.0)
    assert a[2] == pytest.approx(1.0 + (0.1 - 1.0) * 0.25)


def test_stepped_plateaus_and_flat_warnings():
    flat = spec(shape="linear", sigma_min=0.1, stepped=True, plateaus=2, tilt=0.0)
    a = S.sigmas(flat, 4, 1.0)
    # tau = min(1, floor(2w)/1): u=0,.25 -> 0 ; u=.5,.75 -> 1
    np.testing.assert_allclose(a, [1.0, 1.0, 0.1, 0.1, 0.0])
    assert S.sampler_warnings(a, flat, "euler") == ["flat plateaus are no-op steps on ODE samplers"]
    assert S.sampler_warnings(a, flat, None) == ["flat plateaus are no-op steps on ODE samplers"]
    assert S.sampler_warnings(a, flat, "pingpong") == []
    with pytest.raises(ForgeError) as e:
        S.sampler_warnings(a, flat, "dpmpp")
    assert e.value.status == 400
    # plateaus=4 (not 2): with 2 plateaus over 4 steps tau clamps at 1.0 for the last two steps by the
    # spec formula itself, so that array is flat at sigma_min whatever the tilt -- the plan's
    # arithmetic slip, corrected 2026-10-01. 4 plateaus over 4 steps is tau = 0, 1/3, 2/3, 1.
    tilted = spec(shape="linear", sigma_min=0.1, stepped=True, plateaus=4, tilt=0.5)
    assert S.sampler_warnings(S.sigmas(tilted, 4, 1.0), tilted, "dpmpp") == []


def test_sigma_max_range():
    with pytest.raises(ForgeError):
        S.sigmas(spec(shape="linear"), 4, 1.2)
    with pytest.raises(ForgeError):
        S.sigmas(spec(shape="linear", sigma_min=0.3), 4, 0.2)


def test_array_schedule_through_build_schedule():
    # Needs the real SA3 package (the fork on the GPU box); skipped where it is not installed.
    pytest.importorskip("stable_audio_3")
    from stable_audio_3.inference.sampling import build_schedule
    arr = S.sigmas(spec(shape="cosine"), 12, 1.0)
    out = build_schedule(steps=12, sigma_max=1.0, dist_shift=S.ArraySchedule(arr),
                         fallback_seq_len=512, include_endpoint=True, device="cpu")
    np.testing.assert_allclose(out.numpy(), arr, atol=1e-6)
    with pytest.raises(ValueError):
        S.ArraySchedule(arr).shift(torch.linspace(1, 0, 5), 512)


def test_resolve_schedule_conflict_and_object():
    with pytest.raises(ForgeError) as e:
        S.resolve_schedule({"schedule": {"shape": "logsnr"}, "dist_shift": 3.0}, 8, 1.0)
    assert "replaces dist_shift" in e.value.message
    obj, warns = S.resolve_schedule({"schedule": {"shape": "logsnr"}, "dist_shift": "default"}, 8, 1.0)
    assert isinstance(obj, S.ArraySchedule) and warns == []


def test_progress_to_cfg_interval():
    assert S.progress_to_cfg_interval(0.1, 0.85, 1.0) == pytest.approx((0.15, 0.9))
    assert S.progress_to_cfg_interval(0.0, 1.0, 0.4) == pytest.approx((0.0, 0.4))
    for bad in [(0.5, 0.4), (-0.1, 0.5), (0.2, 1.1)]:
        with pytest.raises(ForgeError):
            S.progress_to_cfg_interval(*bad, 1.0)


def test_vectors_file_matches_code():
    import json
    from forge.write_vectors import VECTOR_DIR, schedule_vectors
    path = VECTOR_DIR / "schedule.json"
    assert path.exists(), "run: $PY eval/forge/write_vectors.py"
    assert json.loads(path.read_text()) == schedule_vectors()
