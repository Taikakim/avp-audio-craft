# Latent Forge M3 — Sampling apparatus (server) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every ADVANCED SAMPLING field real on the server: schedule shapes (logSNR, geometric, linear, log, exponential, cosine) with ρ, λ, σ min/max and STEPPED/TILT/PLATEAUS; CFG interval expressed as progress; CFG RESCALE; LatCH gradient-norm logging — with `shape: "model"` byte-identical to today.

**Architecture:** `eval/forge/schedule.py` computes the σ array and wraps it in an `ArraySchedule` object that duck-types a distribution shift, so the existing `build_schedule(dist_shift=...)` call in both SA3 samplers (plain and LatCH-guided) consumes it without any change to the fork's sampling code. The server's resolvers gain a progress form of the CFG interval and a `resolve_shift` helper. One fork hook (stable-audio-3) forwards `scale_phi` on the LatCH-guided path.

**Tech Stack:** Python 3.13 (`SAO/.venv`), numpy, torch, FastAPI; stable-audio-3 fork in a dedicated git worktree.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` §5.3, §6.6. **Depends on:** M2 (forge package, `ForgeError`, `write_vectors.py`, `dev_server.sh`).

## Global Constraints

- Server work only in the worktree `/home/kim/Projects/sa3-studio-review`, branch `latent-forge`. Commit with `Misc/agent_commit.sh WINTERMUTE -m "..."`, explicit `git add` paths.
- Fork work only in the worktree `/home/kim/Projects/sa3-fork-forge`, branch `latent-forge-hooks`, created from the stable-audio-3 checkout's committed `HEAD`. Push only to remote **`fork`**, never any other remote. The venv imports `stable_audio_3` from a plain `.pth` path, so `PYTHONPATH=/home/kim/Projects/sa3-fork-forge` shadows it; `dev_server.sh` sets that automatically when the directory exists.
- `PY=/home/kim/Projects/SAO/.venv/bin/python`.
- Schedule spec fields, defaults and ranges exactly:
  `shape ∈ model|logsnr|geometric|linear|log|exponential|cosine` (default `model`), `rho` 1.0 in [0.1, 15], `sigma_min` 0.01 in [0.001, 0.5] and < sigma_max, `lam_min` −6.2 in [−12, 0], `lam_max` 2.0 in [0, 6] and > lam_min, `stepped` false, `plateaus` 6 integer in [2, 24], `tilt` 0.15 in [0, 1].
- σ formulas exactly as spec §5.3 (reproduced in Task 1). σ₀ forced to sigma_max, σ_N = 0.
- A non-model shape together with a `dist_shift` other than null/""/"default" is 400 `schedule.shape replaces dist_shift — send one or the other`.
- Flat plateau (a zero step before σ_N) with `dpmpp` is 400; with `euler`/`rk4`/default-RF it is allowed with the warning `flat plateaus are no-op steps on ODE samplers`.
- `cfg_interval_progress: [p_lo, p_hi]` → sigma gate `[σ₀·(1 − p_hi), σ₀·(1 − p_lo)]`; sending it with `cfg_interval` or `cfg_interval_min/max` is 400 `send cfg_interval_progress or cfg_interval, not both`.
- `scale_phi` ∈ [0, 1]; only forwarded when > 0 (keeps default requests byte-identical).
- Any active LatCH slot forces Euler; a non-euler `sampler_type` then yields the warning `LatCH guidance forces the euler sampler; sampler_type ignored`.

## File Structure

| File | Responsibility |
|---|---|
| `eval/forge/schedule.py` | spec parsing/validation, σ arrays, `ArraySchedule`, sampler warnings, `resolve_schedule`, `progress_to_cfg_interval` |
| `eval/forge/write_vectors.py` (modify) | adds `schedule.json` vectors |
| `eval/explorer_render_server.py` (modify) | `resolve_cfg_interval(req, sigma_max)`, `resolve_shift`, `scale_phi` + warnings in generate/a2a_track/a2a_mix/longform, `/schedule` shapes, `log_norms` |
| `eval/forge/smoke_schedule.py` | GPU smoke against the live dev server |
| `eval/tests/test_forge_schedule.py` | pure schedule tests + vectors check |
| `eval/tests/test_forge_server_sampling.py` | resolver and route tests with the model stubbed |
| fork `stable_audio_3/model.py` (modify) | forward `scale_phi` on the LatCH path |
| fork `tests/test_latent_forge_hooks.py` | stub test for that hook |

---

### Task 1: Schedule module

**Files:**
- Create: `eval/forge/schedule.py`, `eval/tests/test_forge_schedule.py`

**Interfaces:**
- Consumes: `forge.contract.ForgeError`.
- Produces: `SHAPES`, `DEFAULTS`, `RF_SAMPLERS`; `parse_spec(obj) -> dict`; `sigmas(spec, steps, sigma_max) -> np.ndarray (steps+1,) float64`; `sampler_warnings(arr, spec, sampler_type) -> list[str]` (raises `ForgeError` for dpmpp + flat); `class ArraySchedule(sigmas)` with `.shift(t, seq_len) -> torch.Tensor`; `resolve_schedule(req, steps, sigma_max, sampler_type=None) -> (ArraySchedule|None, list[str])`; `progress_to_cfg_interval(p_lo, p_hi, sigma_max) -> (float, float)`.

- [ ] **Step 1: Write the failing test**

```python
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
    tilted = spec(shape="linear", sigma_min=0.1, stepped=True, plateaus=2, tilt=0.5)
    assert S.sampler_warnings(S.sigmas(tilted, 4, 1.0), tilted, "dpmpp") == []


def test_sigma_max_range():
    with pytest.raises(ForgeError):
        S.sigmas(spec(shape="linear"), 4, 1.2)
    with pytest.raises(ForgeError):
        S.sigmas(spec(shape="linear", sigma_min=0.3), 4, 0.2)


def test_array_schedule_through_build_schedule():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/sa3-studio-review && $PY -m pytest eval/tests/test_forge_schedule.py -q`
Expected: FAIL — `No module named 'forge.schedule'`.

- [ ] **Step 3: Implement `eval/forge/schedule.py`**

```python
"""Schedule shapes for rectified-flow SA3 (spec §5.3).

The σ array reaches the samplers as a distribution-shift object: build_schedule() calls
dist_shift.shift(t, seq_len) with t = linspace(sigma_max, 0, steps+1) and then forces
t[0] = sigma_max. ArraySchedule ignores t (beyond its length) and returns our array, so
both sample_diffusion and the LatCH-guided sampler consume it with no fork change.
"""
import math

import numpy as np

from .contract import ForgeError

SHAPES = ("model", "logsnr", "geometric", "linear", "log", "exponential", "cosine")
DEFAULTS = {"shape": "model", "rho": 1.0, "sigma_min": 0.01, "lam_min": -6.2, "lam_max": 2.0,
            "stepped": False, "plateaus": 6, "tilt": 0.15}
_RANGES = {"rho": (0.1, 15.0), "sigma_min": (0.001, 0.5), "lam_min": (-12.0, 0.0),
           "lam_max": (0.0, 6.0), "plateaus": (2, 24), "tilt": (0.0, 1.0)}
RF_SAMPLERS = {"rectified_flow": ("euler", "rk4", "dpmpp", "pingpong"), "rf_denoiser": ("pingpong", "euler")}
FLAT_WARNING = "flat plateaus are no-op steps on ODE samplers"


def parse_spec(obj) -> dict:
    if obj is None:
        return dict(DEFAULTS)
    if not isinstance(obj, dict):
        raise ForgeError(400, "schedule must be an object")
    unknown = sorted(set(obj) - set(DEFAULTS))
    if unknown:
        raise ForgeError(400, f"unknown schedule field(s): {', '.join(unknown)}")
    spec = {**DEFAULTS, **obj}
    if spec["shape"] not in SHAPES:
        raise ForgeError(400, f"unknown schedule.shape {spec['shape']!r} (have {', '.join(SHAPES)})")
    if not isinstance(spec["stepped"], bool):
        raise ForgeError(400, "schedule.stepped must be true or false")
    p = spec["plateaus"]
    if isinstance(p, float) and p.is_integer():
        spec["plateaus"] = int(p)
    if isinstance(spec["plateaus"], bool) or not isinstance(spec["plateaus"], int):
        raise ForgeError(400, "schedule.plateaus must be an integer")
    for key, (lo, hi) in _RANGES.items():
        v = spec[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ForgeError(400, f"schedule.{key}={v!r} outside {lo}..{hi}")
        if key != "plateaus":
            spec[key] = float(v)
    if spec["lam_max"] <= spec["lam_min"]:
        raise ForgeError(400, "schedule.lam_max must be > lam_min")
    return spec


def sigmas(spec, steps, sigma_max) -> np.ndarray:
    shape = spec["shape"]
    if shape == "model":
        raise ValueError("the model shape has no explicit array — use build_schedule")
    n = int(steps)
    s_max = float(sigma_max)
    if n < 1:
        raise ForgeError(400, "steps must be >= 1")
    if not 0.0 < s_max <= 1.0:
        raise ForgeError(400, f"sigma_max {sigma_max!r} must be in (0, 1]")
    s_min = spec["sigma_min"]
    if shape != "logsnr" and s_min >= s_max:
        raise ForgeError(400, "schedule.sigma_min must be < sigma_max (the noise level)")
    u = np.arange(n, dtype=np.float64) / n
    w = u ** spec["rho"]
    if spec["stepped"]:
        P = spec["plateaus"]
        x = w * P
        fl = np.floor(x)
        tau = np.minimum(1.0, (fl + spec["tilt"] * (x - fl)) / (P - 1))
    else:
        tau = w
    if shape == "logsnr":
        lam_min = spec["lam_min"]
        if s_max < 1.0:
            lam_min = max(lam_min, math.log((1.0 - s_max) / s_max))
        if lam_min >= spec["lam_max"]:
            raise ForgeError(400, "noise level too low for this logSNR interval (raise lam_max)")
        sig = 1.0 / (1.0 + np.exp(lam_min + (spec["lam_max"] - lam_min) * tau))
    elif shape == "geometric":
        sig = np.exp(math.log(s_max) + (math.log(max(s_min, 1e-6)) - math.log(s_max)) * tau)
    elif shape == "linear":
        sig = s_max + (s_min - s_max) * tau
    elif shape == "log":
        sig = s_max + (s_min - s_max) * np.log1p(9.0 * tau) / math.log(10.0)
    elif shape == "exponential":
        sig = s_max + (s_min - s_max) * (np.exp(3.0 * tau) - 1.0) / (math.exp(3.0) - 1.0)
    else:  # cosine
        sig = s_min + (s_max - s_min) * (1.0 + np.cos(math.pi * tau)) / 2.0
    out = np.empty(n + 1, dtype=np.float64)
    out[:n] = sig
    out[0] = s_max
    out[n] = 0.0
    if np.any(np.diff(out) > 1e-12):
        raise ForgeError(400, "schedule is not non-increasing")
    return out


def _has_flat(arr) -> bool:
    return bool(np.any(np.diff(arr[:-1]) == 0.0))


def sampler_warnings(arr, spec, sampler_type):
    if not spec.get("stepped") or not _has_flat(arr):
        return []
    if sampler_type == "dpmpp":
        raise ForgeError(400, "flat plateaus (tilt 0) divide by zero in dpmpp — raise tilt or pick another sampler")
    if sampler_type in (None, "", "euler", "rk4"):
        return [FLAT_WARNING]
    return []


class ArraySchedule:
    def __init__(self, sigma_array):
        self.sigmas = np.asarray(sigma_array, dtype=np.float64)

    def shift(self, t, seq_len):
        import torch
        if t.dim() != 1 or t.shape[0] != len(self.sigmas):
            raise ValueError(f"ArraySchedule has {len(self.sigmas)} points; sampler asked for {tuple(t.shape)}")
        return torch.as_tensor(self.sigmas, dtype=t.dtype, device=t.device)


def resolve_schedule(req, steps, sigma_max, sampler_type=None):
    spec = parse_spec(req.get("schedule"))
    if spec["shape"] == "model":
        return None, []
    if req.get("dist_shift") not in (None, "", "default"):
        raise ForgeError(400, "schedule.shape replaces dist_shift — send one or the other")
    arr = sigmas(spec, steps, sigma_max)
    return ArraySchedule(arr), sampler_warnings(arr, spec, sampler_type)


def progress_to_cfg_interval(p_lo, p_hi, sigma_max):
    try:
        lo, hi, s = float(p_lo), float(p_hi), float(sigma_max)
    except (TypeError, ValueError):
        raise ForgeError(400, "cfg_interval_progress must be two numbers")
    if not (0.0 <= lo <= hi <= 1.0):
        raise ForgeError(400, f"cfg_interval_progress ({p_lo}, {p_hi}) must satisfy 0 <= lo <= hi <= 1")
    return (s * (1.0 - hi), s * (1.0 - lo))
```

- [ ] **Step 4: Add schedule vectors to `eval/forge/write_vectors.py`**

Add below the envelope section:
```python
from forge.schedule import parse_spec, sigmas as schedule_sigmas  # noqa: E402

SCHEDULE_CASES = [
    {"name": "logsnr_8", "spec": {"shape": "logsnr"}, "steps": 8, "sigma_max": 1.0},
    {"name": "logsnr_a2a", "spec": {"shape": "logsnr"}, "steps": 8, "sigma_max": 0.4},
    {"name": "geometric_12", "spec": {"shape": "geometric", "sigma_min": 0.01}, "steps": 12, "sigma_max": 1.0},
    {"name": "linear_rho", "spec": {"shape": "linear", "sigma_min": 0.1, "rho": 2.0}, "steps": 6, "sigma_max": 1.0},
    {"name": "log_10", "spec": {"shape": "log", "sigma_min": 0.02}, "steps": 10, "sigma_max": 1.0},
    {"name": "exponential_10", "spec": {"shape": "exponential", "sigma_min": 0.02}, "steps": 10, "sigma_max": 1.0},
    {"name": "cosine_stepped", "spec": {"shape": "cosine", "stepped": True, "plateaus": 4, "tilt": 0.15}, "steps": 16, "sigma_max": 1.0},
    {"name": "linear_flat", "spec": {"shape": "linear", "sigma_min": 0.1, "stepped": True, "plateaus": 2, "tilt": 0.0}, "steps": 4, "sigma_max": 1.0},
]


def schedule_vectors():
    return [{**c, "sigmas": [round(float(v), 9) for v in schedule_sigmas(parse_spec(c["spec"]), c["steps"], c["sigma_max"])]}
            for c in SCHEDULE_CASES]
```
And in `main()` add:
```python
    (VECTOR_DIR / "schedule.json").write_text(json.dumps(schedule_vectors(), indent=2) + "\n")
    print(f"wrote {VECTOR_DIR / 'schedule.json'}")
```

- [ ] **Step 5: Generate vectors and run tests**

Run:
```bash
$PY eval/forge/write_vectors.py
$PY -m pytest eval/tests/test_forge_schedule.py eval/tests/test_forge_envelope.py -q
```
Expected: two `wrote` lines; all passed.

- [ ] **Step 6: Commit**

```bash
git add eval/forge/schedule.py eval/forge/write_vectors.py eval/tests/test_forge_schedule.py docs/latent-forge/contract/vectors/schedule.json
Misc/agent_commit.sh WINTERMUTE -m "forge: schedule shapes, ArraySchedule, progress CFG interval + vectors"
```

---

### Task 2: Server integration

**Files:**
- Modify: `eval/explorer_render_server.py`
- Create: `eval/tests/test_forge_server_sampling.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `srv.resolve_cfg_interval(req, sigma_max=1.0)`, `srv.resolve_shift(req, steps, sigma_max, warnings) -> dist_shift obj | FluxDistributionShift | None`, `srv._a2a_pass(..., scale_phi=0.0)`. `/schedule` POST accepts `schedule` and returns `shape` and `warnings`. `/generate`, `/a2a_track`, `/a2a_mix`, `/longform` accept `schedule`, `cfg_interval_progress`, `scale_phi`. `resolve_latch` hparams include `log_norms`. Used by M8.

- [ ] **Step 1: Write the failing test**

```python
import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def srv():
    import explorer_render_server as srv
    return srv


def test_cfg_interval_progress(srv):
    assert srv.resolve_cfg_interval({"cfg_interval_progress": [0.1, 0.85]}) == pytest.approx((0.15, 0.9))
    assert srv.resolve_cfg_interval({"cfg_interval_progress": [0.0, 0.5]}, sigma_max=0.4) == pytest.approx((0.2, 0.4))
    assert srv.resolve_cfg_interval({"cfg_interval": [0.2, 0.8]}) == (0.2, 0.8)
    assert srv.resolve_cfg_interval({}) == (0.0, 1.0)
    from forge.contract import ForgeError
    with pytest.raises(ForgeError):
        srv.resolve_cfg_interval({"cfg_interval_progress": [0, 1], "cfg_interval": [0, 1]})


def test_resolve_shift_model_path_unchanged(srv):
    w = []
    assert srv.resolve_shift({}, 24, 1.0, w) is None and w == []
    flux = srv.resolve_shift({"dist_shift": 3.0}, 24, 1.0, w)
    assert type(flux).__name__ == "FluxDistributionShift"
    arr = srv.resolve_shift({"schedule": {"shape": "logsnr"}}, 8, 1.0, w)
    assert type(arr).__name__ == "ArraySchedule"


def test_log_norms_passthrough(srv):
    cfgs, hp = srv.resolve_latch([{"builtin": "recurrence", "gain": 10.0}], {"log_norms": True})
    assert hp["log_norms"] is True
    _, hp2 = srv.resolve_latch([{"builtin": "recurrence", "gain": 10.0}], {})
    assert hp2["log_norms"] is False


def test_schedule_route_shapes(srv):
    c = fastapi_testclient.TestClient(srv.app)
    r = c.post("/schedule", json={"steps": 8, "duration": 10.0, "schedule": {"shape": "logsnr"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["shape"] == "logsnr" and len(body["sigmas"]) == 9 and body["sigmas"][0] == 1.0
    assert body["warnings"] == []
    r = c.post("/schedule", json={"steps": 4, "duration": 10.0, "sampler_type": "dpmpp",
                                  "schedule": {"shape": "linear", "stepped": True, "plateaus": 2, "tilt": 0.0}})
    assert r.status_code == 400 and "dpmpp" in r.json()["error"]
    r = c.post("/schedule", json={"steps": 8, "duration": 10.0, "dist_shift": 3.0, "schedule": {"shape": "cosine"}})
    assert r.status_code == 400


def test_generate_passes_schedule_scale_phi_and_warnings(srv, monkeypatch, tmp_path):
    seen = {}

    class FakeModel:
        class model:
            diffusion_objective = "rectified_flow"
            sampling_dist_shift = None

        def generate(self, **kw):
            import torch
            seen.update(kw)
            kw["latents_sink"].append(torch.zeros(1, 256, 4))
            return torch.zeros(1, 2, int(44100 * 2.0))

    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    monkeypatch.setattr(srv, "prepare_model", lambda *a, **k: False)
    body = srv._generate_impl({"prompt": "x", "duration": 2.0, "steps": 8, "scale_phi": 0.7,
                               "sampler_type": "dpmpp", "cfg_interval_progress": [0.1, 0.9],
                               "schedule": {"shape": "logsnr"}})
    assert type(seen["dist_shift"]).__name__ == "ArraySchedule"
    assert seen["scale_phi"] == 0.7
    assert seen["cfg_interval"] == pytest.approx((0.1, 0.9))
    assert body["warnings"] == []
    seen.clear()
    srv._generate_impl({"prompt": "x", "duration": 2.0, "steps": 8})
    assert "scale_phi" not in seen and seen["dist_shift"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_server_sampling.py -q`
Expected: FAIL — `resolve_cfg_interval() got an unexpected keyword argument 'sigma_max'` / no `resolve_shift`.

- [ ] **Step 3: Implement the server edits**

(a) Imports: next to the M2 forge imports add
```python
from forge import schedule as forge_schedule  # noqa: E402
```

(b) Replace `resolve_cfg_interval` with:
```python
def resolve_cfg_interval(req, sigma_max=1.0):
    """(lo, hi) tuple in native SIGMA semantics — the DiT gates CFG on
    cfg_interval[0] <= sigma <= cfg_interval[1] (dit.py), NOT on step index.
    Accepts cfg_interval=[lo,hi], cfg_interval_min/cfg_interval_max, or (Latent Forge)
    cfg_interval_progress=[p_lo,p_hi] where progress = 1 - sigma/sigma_max."""
    cp = req.get("cfg_interval_progress")
    if cp is not None:
        if any(req.get(k) is not None for k in ("cfg_interval", "cfg_interval_min", "cfg_interval_max")):
            raise ForgeError(400, "send cfg_interval_progress or cfg_interval, not both")
        if not isinstance(cp, (list, tuple)) or len(cp) != 2:
            raise ForgeError(400, "cfg_interval_progress must be [lo, hi]")
        return forge_schedule.progress_to_cfg_interval(cp[0], cp[1], sigma_max)
    ci = req.get("cfg_interval")
    if ci is not None:
        lo, hi = float(ci[0]), float(ci[1])
    else:
        lo = _f(req, "cfg_interval_min", 0.0)
        hi = _f(req, "cfg_interval_max", 1.0)
    if not (0.0 <= lo <= hi <= 1.0):
        raise ValueError(f"cfg_interval ({lo}, {hi}) must satisfy 0 <= lo <= hi <= 1")
    return (lo, hi)
```

(c) Directly below `resolve_dist_shift` add:
```python
def resolve_shift(req, steps, sigma_max, warnings):
    """Schedule-shape object (Latent Forge) or today's dist_shift resolution, unchanged."""
    obj, w = forge_schedule.resolve_schedule(req, steps, sigma_max, req.get("sampler_type"))
    warnings.extend(w)
    return obj if obj is not None else resolve_dist_shift(req)


def resolve_scale_phi(req):
    v = _f(req, "scale_phi", 0.0)
    if not 0.0 <= v <= 1.0:
        raise ForgeError(400, f"scale_phi {v} outside 0..1")
    return v


def latch_sampler_warning(latch_cfgs, req, warnings):
    if latch_cfgs and req.get("sampler_type") not in (None, "", "euler"):
        warnings.append("LatCH guidance forces the euler sampler; sampler_type ignored")
```

(d) In `resolve_latch`, change the hparams line to:
```python
    hparams = {"rho": _f(req, "rho", g0), "mu": _f(req, "mu", g0),
               "gamma": _f(req, "gamma", 0.3), "n_iter": _i(req, "n_iter", 4),
               "log_norms": _b(req, "log_norms", False)}
```

(e) `_generate_impl`: after `latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req)` insert
```python
        warnings = []
        latch_sampler_warning(latch_cfgs, req, warnings)
```
In the `kw = dict(...)` call replace `dist_shift=resolve_dist_shift(req),` with `dist_shift=resolve_shift(req, steps, 1.0, warnings),`. After the `sampler_type` block add
```python
        scale_phi = resolve_scale_phi(req)
        if scale_phi > 0:
            kw["scale_phi"] = scale_phi
```
In the final `build_response(...)` call replace the `[]` warnings argument with `warnings`.

(f) `_a2a_pass`: add parameter `scale_phi=0.0` after `sampler_type=None`, and after the `kw = dict(...)` statement add
```python
    if scale_phi > 0:
        kw["scale_phi"] = scale_phi
```

(g) `_a2a_track_impl`: remove the lines `cfg_interval = resolve_cfg_interval(req)` and `dist_shift = resolve_dist_shift(req)` before the lock; after `latch_cfgs, latch_hp = resolve_latch(...)` add `scale_phi = resolve_scale_phi(req)`. Keep `files, warnings = [], []` and add `latch_sampler_warning(latch_cfgs, req, warnings)` right after it. Inside `for nl in nls:` before `pieces = []` add
```python
            cfg_interval = resolve_cfg_interval(req, sigma_max=nl)
            dist_shift = resolve_shift(req, steps, nl, warnings)
```
and in the `_a2a_pass(...)` call add `scale_phi=scale_phi,`.

(h) `_longform_impl` a2a branch: replace `cfg_interval = resolve_cfg_interval(req)` with `cfg_interval = resolve_cfg_interval(req, sigma_max=nl)` and `dist_shift = resolve_dist_shift(req)` with `dist_shift = resolve_shift(req, steps, nl, warnings)`; add `scale_phi=resolve_scale_phi(req),` to its `_a2a_pass(...)` call. In the t2a `else:` branch, first line:
```python
            if forge_schedule.parse_spec(req.get("schedule"))["shape"] != "model":
                raise ForgeError(400, "schedule shapes are not supported on the t2a longform path")
```

(i) `_a2a_mix_impl`: in the model-pass `kw = dict(...)` (the `else:` of construction) replace `cfg_interval=cfg_interval, dist_shift=dist_shift,` with
```python
                      cfg_interval=resolve_cfg_interval(req, sigma_max=(1.0 if mode == "inpaint" else nl)),
                      dist_shift=resolve_shift(req, steps, (1.0 if mode == "inpaint" else nl), warnings),
```
and after that `kw` add
```python
            if resolve_scale_phi(req) > 0:
                kw["scale_phi"] = resolve_scale_phi(req)
```

(j) `/schedule` route: **replace the whole `async def schedule(...)` with this.** The shape
branch has to run before the `MODEL is None` check (an array schedule needs no model, and the
GUI charts it during a backbone rebuild), and `steps`/`duration`/`sigma_max` are parsed once at
the top so both branches see the same values. Everything below the shape branch is the existing
function unchanged except for the two added response keys.

```python
@app.api_route("/schedule", methods=["GET", "POST"])
async def schedule(request: Request):
    """Real sigma schedule for the GUI chart — same build_schedule call the run
    makes: dist_shift is length-dependent, seq_len = ceil(duration*SR/DS) exactly
    as compute_effective_seq_len_from_conditioning derives it from seconds_total
    (generate() sets use_effective_length_for_schedule=True).

    POST JSON (the render_client contract): {"steps": int, "duration": float,
    "dist_shift": float|null (null/absent = model default; float = constant-alpha
    Flux shift, matching resolve_dist_shift on /generate), "sigma_max": float,
    "schedule": ScheduleSpec|null, "sampler_type": str|null}. A schedule whose
    shape is not "model" replaces dist_shift entirely and is computed here without
    the model. GET keeps the same keys as query params, plus the legacy shift=0
    flag (-> linear, no warp); GET never carries a schedule spec. For a2a previews
    pass sigma_max=init_noise_level (schedule truncates there)."""
    if request.method == "POST":
        try:
            req = json.loads((await request.body()) or b"{}")
        except Exception as e:
            return JSONResponse({"error": f"bad JSON body: {e}"}, status_code=400)
    else:
        req = dict(request.query_params)
    try:
        steps = max(1, _i(req, "steps", 24))
        duration = _f(req, "duration", 47.0)
        sigma_max = _f(req, "sigma_max", 1.0)
        spec = forge_schedule.parse_spec(req.get("schedule") if request.method == "POST" else None)
        if spec["shape"] != "model":
            if req.get("dist_shift") not in (None, "", "default"):
                raise ForgeError(400, "schedule.shape replaces dist_shift — send one or the other")
            arr = forge_schedule.sigmas(spec, steps, sigma_max)
            return {"ok": True, "steps": steps, "duration": duration, "sigma_max": sigma_max,
                    "dist_shift": None, "shape": spec["shape"],
                    "latent_len": max(1, math.ceil(duration * SR / DS)),
                    "sigmas": [float(s) for s in arr],
                    "warnings": forge_schedule.sampler_warnings(arr, spec, req.get("sampler_type"))}
    except ForgeError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)
    except (TypeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    m = MODEL
    if m is None:
        return JSONResponse({"error": "model not loaded (rebuild in progress?)"},
                            status_code=503)
    try:
        if str(req.get("shift", "1")) in ("0", "false", "False"):  # legacy GET flag
            ds_obj, ds_echo = None, "linear"
        else:
            ds_obj = resolve_dist_shift(req)
            if ds_obj is None:
                ds_echo = "model"
                ds_obj = m.model.sampling_dist_shift
            elif req.get("dist_shift") == "flux":
                ds_echo = "flux"
            else:
                ds_echo = float(req["dist_shift"])
    except (TypeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    latent_len = max(1, math.ceil(duration * SR / DS))
    sched = build_schedule(steps=steps, sigma_max=sigma_max,
                           dist_shift=ds_obj,
                           fallback_seq_len=latent_len,
                           include_endpoint=True, device="cpu")
    if sched.dim() == 2:
        sched = sched[0]
    sigmas = [float(s) for s in sched]
    return {"ok": True, "steps": steps, "duration": duration,
            "sigma_max": sigma_max, "dist_shift": ds_echo,
            "shape": "model", "latent_len": latent_len,
            "sigmas": sigmas, "warnings": []}
```

Two things to keep straight while transcribing. The original parsed `steps`/`duration`/`sigma_max`
*after* the `MODEL is None` check, inside the same `try:` as the dist_shift resolution; here they
move above it and the dist_shift resolution keeps its own `try:` so the legacy `float(req["dist_shift"])`
path still answers 400 rather than 500. And the response gains exactly two keys — `shape` and
`warnings` — on both branches, because `forgeApi.schedule` (M1 Task 5) declares them and the sigma
graph reads `warnings` to mark a sampler/shape mismatch.

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_server_sampling.py eval/tests/test_forge_schedule.py eval/tests/test_render_server_ab.py eval/tests/test_target_raw_passthrough.py eval/tests/test_latch_window_budget.py -q`
Expected: all passed (existing server tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add eval/explorer_render_server.py eval/tests/test_forge_server_sampling.py
Misc/agent_commit.sh WINTERMUTE -m "server: schedule shapes, cfg_interval_progress, scale_phi, log_norms on all render paths"
```

---

### Task 3: Fork hook — `scale_phi` on the LatCH-guided path

**Files (in `/home/kim/Projects/sa3-fork-forge`):**
- Modify: `stable_audio_3/model.py` (`generate` latch branch, `_latch_guided_generate`)
- Create: `tests/test_latent_forge_hooks.py`

**Interfaces:**
- Produces: `StableAudioModel._latch_guided_generate(..., scale_phi=0.0)` forwarding `scale_phi` to `sample_flow_euler_multi_latch_guided(**model_kwargs)` when non-zero; `generate()` pops `scale_phi` from `sampler_kwargs` for the latch branch.

- [ ] **Step 1: Create the fork worktree**

```bash
cd /home/kim/Projects/SAO/stable-audio-3
git status --short stable_audio_3/model.py        # must print nothing: model.py has no uncommitted edits
git worktree add -b latent-forge-hooks /home/kim/Projects/sa3-fork-forge HEAD
git -C /home/kim/Projects/sa3-fork-forge log --oneline -1
```
Expected: empty status line, worktree created. If `model.py` shows modifications, STOP and report BLOCKED (someone else is editing it).

- [ ] **Step 2: Write the failing test**

`/home/kim/Projects/sa3-fork-forge/tests/test_latent_forge_hooks.py`:
```python
"""Latent Forge hooks in the fork (avp-audio-craft spec 2026-09-15 §6.6)."""
import types

import torch

import stable_audio_3.model as m


def _stub():
    return types.SimpleNamespace(
        device="cpu",
        model=types.SimpleNamespace(pretransform=types.SimpleNamespace(downsampling_ratio=4096),
                                    sample_rate=44100, model=object(), diffusion_objective="rectified_flow"))


def _run(monkeypatch, **extra):
    seen = {}

    def fake_sampler(model, x, sigmas, guides, **kw):
        seen.update(kw)
        return x

    monkeypatch.setattr(m, "sample_flow_euler_multi_latch_guided", fake_sampler)
    m.StableAudioModel._latch_guided_generate(
        _stub(), noise=torch.zeros(1, 4, 8), cond_inputs={}, latch_configs=[], latch_hparams={},
        steps=4, cfg_scale=1.0, apg_scale=1.0, batch_size=1, latent_sample_size=8, dist_shift=None,
        return_latents=True, **extra)
    return seen


def test_latch_path_forwards_scale_phi(monkeypatch):
    assert _run(monkeypatch, scale_phi=0.7)["scale_phi"] == 0.7


def test_latch_path_omits_zero_scale_phi(monkeypatch):
    assert "scale_phi" not in _run(monkeypatch)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/kim/Projects/sa3-fork-forge && PYTHONPATH=/home/kim/Projects/sa3-fork-forge /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_latent_forge_hooks.py -q`
Expected: FAIL — `unexpected keyword argument 'scale_phi'`.

- [ ] **Step 4: Implement**

In `stable_audio_3/model.py`:

(a) `_latch_guided_generate` signature: after `callback=None,` add `scale_phi=0.0,`.

(b) In its call to `sample_flow_euler_multi_latch_guided(...)`, after `callback=callback, **hp, **cond_inputs,` add:
```python
                **({"scale_phi": float(scale_phi)} if scale_phi else {}),
```

(c) In `generate()`, in the `if latch_configs:` branch's `self._latch_guided_generate(...)` call, after `callback=sampler_kwargs.pop("callback", None),` add:
```python
                # CFG rescale rides **sampler_kwargs on the sample_diffusion path; the latch
                # path passes explicit kwargs only (Latent Forge, 2026-09-15).
                scale_phi=sampler_kwargs.pop("scale_phi", 0.0),
```

- [ ] **Step 5: Run test to verify it passes**

Run the Step 3 command. Expected: 2 passed.

- [ ] **Step 6: Commit in the fork and push to `fork` only**

```bash
cd /home/kim/Projects/sa3-fork-forge
git add stable_audio_3/model.py tests/test_latent_forge_hooks.py
git -c user.name=WINTERMUTE -c user.email=wintermute@aavepyora.online commit -m "latent-forge: forward scale_phi (CFG rescale) on the LatCH-guided path"
git remote -v | grep '^fork'          # must show Taikakim/stable-audio-3
git push fork latent-forge-hooks
```
Append the attribution lines from the session reminder to the commit message. Never push to `upstream` or bare `git push`.

---

### Task 4: GPU smoke on the live dev server

**Files:**
- Create: `eval/forge/smoke_schedule.py`

**Interfaces:**
- Consumes: M2 jobs API, Tasks 1–3. Produces: a pass/fail report; recorded fixtures `schedule_<shape>.json`.

- [ ] **Step 1: Write the smoke script**

```python
"""GPU smoke for the sampling apparatus against the LIVE dev server (M3 Task 4).

Run: /home/kim/Projects/SAO/.venv/bin/python eval/forge/smoke_schedule.py
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forge.record_fixtures import BASE, FIXTURE_DIR, redact  # noqa: E402

OUT = Path("/home/kim/Projects/sa3_render_out")


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def run_job(payload):
    s, sub = call("POST", "/forge/jobs", {"op": "generate", "payload": payload})
    assert s == 202, sub
    while True:
        _, rec = call("GET", f"/forge/jobs/{sub['job_id']}")
        if rec["state"] in ("done", "error"):
            break
        time.sleep(1)
    assert rec["state"] == "done", rec.get("error")
    res = rec["result"]
    wav = OUT / res["job_id"] / res["urls"][0].split("/")[-1]
    y, _ = sf.read(wav)
    z = np.load(res["latents"][0]).astype(np.float32)
    assert np.all(np.isfinite(y)) and np.all(np.isfinite(z)), "non-finite output"
    assert float(np.std(y)) > 1e-4 and abs(float(np.max(np.abs(y))) - 1.0) > 1e-6, "silent or DC output"
    return res, z


BASE_PAYLOAD = {"prompt": "hypnotic melodic goa trance, rolling bassline", "duration": 6.0, "steps": 8, "seed": 7}


def main():
    failures = []
    _, z_none = run_job(BASE_PAYLOAD)
    _, z_model = run_job({**BASE_PAYLOAD, "schedule": {"shape": "model"}})
    if not np.allclose(z_none, z_model, atol=1e-3):
        failures.append("shape=model differs from no schedule")
    for shape_spec in ({"shape": "logsnr"}, {"shape": "geometric", "sigma_min": 0.02},
                       {"shape": "cosine", "stepped": True, "plateaus": 4, "tilt": 0.15}):
        try:
            run_job({**BASE_PAYLOAD, "schedule": shape_spec})
            s, body = call("POST", "/schedule", {"steps": 8, "duration": 6.0, "schedule": shape_spec})
            (FIXTURE_DIR / f"schedule_{shape_spec['shape']}.json").write_text(
                json.dumps({"status": s, "body": redact(body)}, indent=1) + "\n")
        except AssertionError as e:
            failures.append(f"{shape_spec}: {e}")
    _, z_phi = run_job({**BASE_PAYLOAD, "scale_phi": 0.7})
    if float(np.mean(np.abs(z_phi - z_none))) < 1e-4:
        failures.append("scale_phi had no effect on the plain path")
    latch = [{"head": "rms_energy_bass", "gain": 512.0, "kind": "constant", "value": -12.0,
              "start_pct": 0.0, "end_pct": 0.6}]
    _, z_l0 = run_job({**BASE_PAYLOAD, "latch": latch})
    _, z_l7 = run_job({**BASE_PAYLOAD, "latch": latch, "scale_phi": 0.7})
    if float(np.mean(np.abs(z_l7 - z_l0))) < 1e-4:
        failures.append("scale_phi had no effect on the LatCH path (fork hook not loaded?)")
    s, body = call("POST", "/forge/jobs", {"op": "generate", "payload": {
        **BASE_PAYLOAD, "sampler_type": "dpmpp",
        "schedule": {"shape": "linear", "sigma_min": 0.1, "stepped": True, "plateaus": 2, "tilt": 0.0}}})
    if s == 202:
        _, rec = call("GET", f"/forge/jobs/{body['job_id']}")
        while rec["state"] not in ("done", "error"):
            time.sleep(1)
            _, rec = call("GET", f"/forge/jobs/{body['job_id']}")
        if rec["state"] != "error" or "dpmpp" not in (rec["error"] or ""):
            failures.append("dpmpp + flat plateaus was not refused")
    print("FAILURES:" if failures else "ALL SMOKE CHECKS PASSED")
    for f in failures:
        print("  -", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the smoke (swaps the resident server)**

```bash
cd /home/kim/Projects/SAO && Misc/gpu_guard.sh who WINTERMUTE
cd /home/kim/Projects/sa3-studio-review
eval/forge/dev_server.sh stop || true
eval/forge/dev_server.sh start
grep -m1 -o "sa3-fork-forge" /proc/$(pgrep -f "eval/explorer_render_server.py --port 8056")/environ && echo "fork on PYTHONPATH"
$PY eval/forge/smoke_schedule.py
```
Expected: `fork on PYTHONPATH`, then `ALL SMOKE CHECKS PASSED`. The rms_energy_bass head is the medium-family head from `/info`; if the eval drive is unmounted, heads still load from `stable-audio-3/latch_weights_sa3_medium` on the NVMe.

- [ ] **Step 3: Leak scan, commit**

```bash
grep -rn -e '/home/kim' -e '/run/media/kim' docs/latent-forge/contract/fixtures && echo LEAK || echo clean
git add eval/forge/smoke_schedule.py docs/latent-forge/contract/fixtures/schedule_*.json
Misc/agent_commit.sh WINTERMUTE -m "forge: sampling apparatus GPU smoke + schedule fixtures"
```

- [ ] **Step 4: Hand the GPU back** — `eval/forge/dev_server.sh stop` unless M8 starts immediately.
