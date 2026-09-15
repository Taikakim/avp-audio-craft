# Latent Forge M8 — Commit pipeline (server) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three render jobs that make Latent Forge more than a sequencer: `a2a_clip` (per-clip audio-to-audio with a noise envelope), `inpaint` (single-overlap preview) and `commit` (the per-lane MIXDOWN: decode → stretch → encode → lane chain + A2A pass → overlap inpaint → latent mix → master chain → decode).

**Architecture:** Pure, CPU-tested modules in `eval/forge/` (settings mapping, lane placement, mixing, hold/splice math, chroma targets, commit planning) plus one GPU module `passes.py` that drives `MODEL.generate` under `GPU_LOCK` using the server's existing resolvers. Two fork hooks let successive passes feed latents straight back in (`init_latents`, `inpaint_latents`). Runners register with the M2 job queue.

**Tech Stack:** Python 3.13 (`SAO/.venv`), numpy, torch, stable-audio-3 fork worktree, pytest.

**Spec:** §5.2, §5.5, §6.6–6.9, §7.1, §8. **Depends on:** M2 (jobs, services, envelope, chroma, stretch, progress), M3 (schedule resolvers, `resolve_shift`, `resolve_scale_phi`, `latch_sampler_warning`, fork worktree).

## Global Constraints

- Server work only in `/home/kim/Projects/sa3-studio-review` (branch `latent-forge`), fork work only in `/home/kim/Projects/sa3-fork-forge` (branch `latent-forge-hooks`, push to remote `fork` only). Commit via `Misc/agent_commit.sh WINTERMUTE -m "..."` with explicit paths.
- `PY=/home/kim/Projects/SAO/.venv/bin/python`. Fork tests run with `PYTHONPATH=/home/kim/Projects/sa3-fork-forge`.
- `SR = 44100`, `HOP = 4096`, `FPS = SR/HOP`, `T = ceil(duration_sec · SR / HOP)`.
- Cap 184.0 s for `a2a_clip` (clip length), `inpaint` (padded span) and `commit` (`duration_sec`), message `forge passes are capped at 184 s locally (T<2048)`.
- Commit stage labels, in order, exactly: `DECODE latent → audio`, `BUNGEE stretch / pitch`, `ENCODE audio → latent`, `LANE CHAINS`, `A2A RE-NOISE`, `INPAINT OVERLAPS`, `MIX`, `MASTER CHAIN`, `DECODE latent → audio`.
- `SPLICE_XFADE_FRAMES = 2` (from `forge.contract`).
- LatCH mapping: `gain_k = head.default_gain · weight_k`; `rho = ρ · gain_0`, `mu = μ · gain_0`; slots with head `none` or weight 0 omitted.
- Lane audibility: if any lane is soloed only soloed lanes are audible; otherwise non-muted lanes.
- Overlap audio: equal-power `gA = cos(v·π/2)`, `gB = sin(v·π/2)` with `v = sample_envelope(curve, n)`; chroma target inside the region `(1 − v)·A + v·B`, A before, B after; chroma head `chroma_other` at its registry `default_gain`, `end_pct = 0.6`.
- Mix: tree `M1=(L1,L2) M2=(L3,L4) MX=(M1,M2)`; cascade `M1=(L1,L2) M2=(M1,L3) MX=(M2,L4)`; `t = 0` → first input; unused input passes the other through; quad = normalised weighted lerp over used lanes, all-zero weights → equal.
- Norm: `z(:,f) *= Σ w_eff_i ‖L_i(:,f)‖₂ / max(‖z(:,f)‖₂, 1e-8)`. Master LatCH: `z += gain · ∂ mean(head(z, t=0.001)) / ∂z`.
- A non-finite latent after any pass aborts the job with `non-finite latents in <label> — refusing to continue`.
- Chroma `target_raw` must be padded (edge) to the pass's **actual** latent length (`MODEL._adapt_sample_size`), not the arrangement's T — the guided sampler linearly resamples a shorter target over the whole window, which would stretch it.

## File Structure

| File | Responsibility |
|---|---|
| fork `stable_audio_3/model.py` | `_fit_latents`, `generate(init_latents=, inpaint_latents=)` |
| fork `tests/test_latent_forge_hooks.py` (extend) | hook tests |
| `eval/forge/render_settings.py` | `parse_render`, `canonical_key`, `to_request`, `parse_chain`, `chain_to_request` |
| `eval/forge/lanes.py` | `place_lanes`, `place_single` |
| `eval/forge/mixing.py` | `mix_latents`, `normalise` |
| `eval/forge/holdpass.py` | `clip_frame_span`, `depth_for_spans`, `make_hold_callback`, `make_hold_renoise_hook` |
| `eval/forge/splice.py` | `splice_by_mask` |
| `eval/forge/overlap.py` | `region_frames`, `chroma_target`, `pad_target` |
| `eval/forge/passes.py` | GPU: `model_latent_frames`, `run_hold_pass`, `run_inpaint_pass`, `steer_master`, `decode_latent` |
| `eval/forge/commit.py` | `STAGES`, `validate_commit`, `plan_passes`, `run_commit` |
| `eval/forge/clip_jobs.py` | `validate_a2a_clip`, `run_a2a_clip`, `validate_inpaint`, `run_inpaint_preview` |
| `eval/forge/services.py` (modify) | `Services.stretched_path` (cached Bungee stretch for commit clips) |
| `eval/forge_api.py` (modify) | register the three runners in `bind` |
| `eval/forge/smoke_commit.py` | GPU smoke + fixtures |
| `eval/tests/test_forge_{render_settings,lanes,mixing,holdpass,overlap,passes,commit,commit_run,clip_jobs}.py` | tests |

---

### Task 1: Fork hooks — `init_latents` and `inpaint_latents`

**Files (fork worktree):** Modify `stable_audio_3/model.py`; extend `tests/test_latent_forge_hooks.py`.

**Interfaces:**
- Produces: module function `_fit_latents(latents, frames, device, dtype) -> Tensor (1,C,frames)`; `StableAudioModel.generate(..., init_latents: Tensor|None = None, inpaint_latents: Tensor|None = None)` — each mutually exclusive with its audio counterpart (`ValueError`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_latent_forge_hooks.py`)

```python
import pytest


def test_fit_latents_pads_crops_and_casts():
    z = torch.arange(12, dtype=torch.float32).reshape(2, 6)
    out = m._fit_latents(z, 8, "cpu", torch.float16)
    assert out.shape == (1, 2, 8) and out.dtype == torch.float16
    assert float(out[0, 1, 5]) == 11.0 and float(out[0, 0, 7]) == 0.0
    assert m._fit_latents(z.unsqueeze(0), 4, "cpu", torch.float32).shape == (1, 2, 4)
    with pytest.raises(ValueError):
        m._fit_latents(torch.zeros(2, 2, 2, 2), 4, "cpu", torch.float32)


def test_generate_rejects_both_init_forms():
    with pytest.raises(ValueError, match="init_audio or init_latents"):
        m.StableAudioModel.generate(_stub(), prompt="x", init_audio=(44100, torch.zeros(2, 10)),
                                    init_latents=torch.zeros(1, 4, 2))


def test_generate_rejects_both_inpaint_forms():
    with pytest.raises(ValueError, match="inpaint_audio or inpaint_latents"):
        m.StableAudioModel.generate(_stub(), prompt="x", inpaint_audio=(44100, torch.zeros(2, 10)),
                                    inpaint_latents=torch.zeros(1, 4, 2))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/kim/Projects/sa3-fork-forge && PYTHONPATH=$PWD /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_latent_forge_hooks.py -q`
Expected: FAIL — no `_fit_latents`; unexpected keyword `init_latents`.

- [ ] **Step 3: Implement**

(a) After the imports of `stable_audio_3/model.py` add:
```python
def _fit_latents(latents, frames, device, dtype):
    """(C,T') or (1,C,T') -> (1,C,frames), zero-padded or cropped at the end (Latent Forge, 2026-09-15)."""
    z = torch.as_tensor(latents)
    if z.dim() == 2:
        z = z.unsqueeze(0)
    if z.dim() != 3 or z.shape[0] != 1:
        raise ValueError(f"latents must be (C,T) or (1,C,T), got {tuple(z.shape)}")
    z = z.to(device=device, dtype=dtype)
    if z.shape[-1] < frames:
        z = torch.nn.functional.pad(z, (0, frames - z.shape[-1]))
    return z[..., :frames].contiguous()
```

(b) In `generate`'s signature, directly after `inpaint_mask_end_seconds: tp.Optional[tp.Union[float, tp.List[float]]] = None,` add:
```python
        init_latents: tp.Optional[torch.Tensor] = None,
        inpaint_latents: tp.Optional[torch.Tensor] = None,
```

(c) Directly before `device = str(self.device)` in the body add:
```python
        if init_latents is not None and init_audio is not None:
            raise ValueError("pass init_audio or init_latents, not both")
        if inpaint_latents is not None and inpaint_audio is not None:
            raise ValueError("pass inpaint_audio or inpaint_latents, not both")
```

(d) Replace
```python
            init_audio = init_audio.repeat(batch_size, 1, 1)

        # Process inpaint audio
```
with
```python
            init_audio = init_audio.repeat(batch_size, 1, 1)
        elif init_latents is not None:
            # Latent Forge: successive passes over one latent never round-trip the decoder.
            init_audio = _fit_latents(init_latents, latent_sample_size, device,
                                      next(self.model.pretransform.parameters()).dtype).repeat(batch_size, 1, 1)

        # Process inpaint audio
```

(e) Replace
```python
            inpaint_audio = inpaint_audio.repeat(batch_size, 1, 1)
        else:
```
with
```python
            inpaint_audio = inpaint_audio.repeat(batch_size, 1, 1)
        elif inpaint_latents is not None:
            inpaint_audio = _fit_latents(inpaint_latents, latent_sample_size, device,
                                         next(self.model.pretransform.parameters()).dtype).repeat(batch_size, 1, 1)
            if inpaint_mask is not None:
                inpaint_mask = interpolate(
                    inpaint_mask.unsqueeze(1), size=latent_sample_size, mode="nearest"
                ).squeeze(1)
        else:
```

- [ ] **Step 4: Run tests** — Step 2 command. Expected: 5 passed.

- [ ] **Step 5: Commit and push to `fork`**

```bash
cd /home/kim/Projects/sa3-fork-forge
git add stable_audio_3/model.py tests/test_latent_forge_hooks.py
git -c user.name=WINTERMUTE -c user.email=wintermute@aavepyora.online commit -m "latent-forge: generate(init_latents=, inpaint_latents=) — passes without a decode round-trip"
git push fork latent-forge-hooks
```
(Append the session attribution lines to the message.)

---

### Task 2: Render settings and lane chain mapping

**Files:** Create `eval/forge/render_settings.py`, `eval/tests/test_forge_render_settings.py`.

**Interfaces:**
- Consumes: `forge.schedule.parse_spec`, `RF_SAMPLERS`; `ForgeError`.
- Produces: `RENDER_DEFAULTS`, `CHAIN_DEFAULTS`; `parse_render(obj) -> dict`; `canonical_key(render) -> str`; `to_request(render, seed:int) -> dict` (keys `prompt negative_prompt steps cfg_scale seed apg_scale cfg_interval_progress schedule scale_phi sampler_type`); `parse_chain(obj) -> dict|None`; `chain_to_request(chain, heads: dict) -> {"latch": list|None, "rho"?, "mu"?, "gamma"?, "n_iter"?, "log_norms"?, "film": dict|None, "dora": dict|None}`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

import forge_testutil  # noqa: F401
from forge import render_settings as R
from forge.contract import ForgeError

HEADS = {"rms_energy_bass": {"default_gain": 512.0}, "chroma_other": {"default_gain": 2048.0}}


def test_render_defaults_and_key():
    r = R.parse_render(None)
    assert r["steps"] == 24 and r["cfg_scale"] == 6.0 and r["schedule"]["shape"] == "model"
    assert R.canonical_key(R.parse_render({"prompt": "a", "steps": 8})) == \
        R.canonical_key(R.parse_render({"steps": 8, "prompt": "a"}))
    req = R.to_request(R.parse_render({"prompt": "pad"}), 77)
    assert req["seed"] == 77 and req["prompt"] == "pad" and req["cfg_interval_progress"] == [0.0, 1.0]


@pytest.mark.parametrize("bad", [
    {"steps": 0}, {"steps": 151}, {"cfg_scale": 65}, {"cfg_interval_progress": [0.6, 0.5]},
    {"sampler_type": "k-heun"}, {"scale_phi": 2}, {"bogus": 1}, {"schedule": {"shape": "karras"}},
])
def test_render_rejects(bad):
    with pytest.raises(ForgeError):
        R.parse_render(bad)


def chain(**kw):
    base = {"latch_on": True,
            "slots": [{"head": "rms_energy_bass", "kind": "constant", "value": -12.0, "weight": 2.0,
                       "start_pct": 0.0, "end_pct": 0.6},
                      {"head": "none", "kind": "constant", "value": 0.0, "weight": 1.0,
                       "start_pct": 0.0, "end_pct": 0.6}],
            "hparams": {"rho": 1.0, "mu": 0.5, "gamma": 0.3, "n_iter": 4, "log_norms": True}}
    base.update(kw)
    return R.parse_chain(base)


def test_chain_latch_gains():
    out = R.chain_to_request(chain(), HEADS)
    assert out["latch"] == [{"head": "rms_energy_bass", "kind": "constant", "value": -12.0, "gain": 1024.0,
                             "start_pct": 0.0, "end_pct": 0.6}]
    assert (out["rho"], out["mu"], out["gamma"], out["n_iter"], out["log_norms"]) == (1024.0, 512.0, 0.3, 4, True)
    assert out["film"] is None and out["dora"] is None


def test_chain_film_lora_and_off():
    c = chain(latch_on=False, film_on=True, film={"ckpt": None, "gain": 1.2, "value": 6.0},
              lora_on=True, lora={"ckpt_path": "/x.ckpt", "slot": None, "strength": 0.8})
    out = R.chain_to_request(c, HEADS)
    assert out["latch"] is None
    assert out["film"] == {"ckpt": None, "gain": 1.2, "value": 6.0}
    assert out["dora"] == {"ckpt_path": "/x.ckpt", "strength": 0.8}
    c2 = chain(latch_on=False, lora_on=True, lora={"ckpt_path": None, "slot": 1, "strength": 1.0})
    assert R.chain_to_request(c2, HEADS)["dora"] == {"slot": 1, "strength": 1.0}
    assert R.chain_to_request(None, HEADS) == {"latch": None, "film": None, "dora": None}


def test_chain_rejects():
    with pytest.raises(ForgeError):
        R.chain_to_request(chain(slots=[{"head": "nope", "kind": "constant", "value": 0, "weight": 1,
                                         "start_pct": 0, "end_pct": 0.6}] * 2), HEADS)
    with pytest.raises(ForgeError):
        chain(hparams={"rho": 31, "mu": 1, "gamma": 0.3, "n_iter": 4, "log_norms": False})
    with pytest.raises(ForgeError):
        chain(semitones=30)
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_render_settings.py -q` → module not found.

- [ ] **Step 3: Implement `eval/forge/render_settings.py`**

```python
"""RenderSettings / LaneChain (spec §6.1) -> request dicts for the server's resolvers (§5.5)."""
import json
import math

from .contract import ForgeError
from .schedule import RF_SAMPLERS, parse_spec

RENDER_DEFAULTS = {"prompt": "", "negative_prompt": "", "steps": 24, "cfg_scale": 6.0, "seed": -1,
                   "apg_scale": 1.0, "cfg_interval_progress": [0.0, 1.0], "schedule": {"shape": "model"},
                   "scale_phi": 0.0, "sampler_type": None}
SLOT_DEFAULT = {"head": "none", "kind": "constant", "value": 0.0, "weight": 1.0, "start_pct": 0.0, "end_pct": 0.6}
CHAIN_DEFAULTS = {"latch_on": False, "slots": [dict(SLOT_DEFAULT), dict(SLOT_DEFAULT)],
                  "hparams": {"rho": 1.0, "mu": 1.0, "gamma": 0.3, "n_iter": 4, "log_norms": False},
                  "film_on": False, "film": {"ckpt": None, "gain": 1.75, "value": 4.0},
                  "lora_on": False, "lora": {"ckpt_path": None, "slot": None, "strength": 1.0},
                  "bungee_on": False, "semitones": 0.0}
_SAMPLERS = sorted({s for v in RF_SAMPLERS.values() for s in v})


def _num(v, lo, hi, what, integer=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ForgeError(400, f"{what}={v!r} outside {lo}..{hi}")
    if integer:
        if float(v) != int(v):
            raise ForgeError(400, f"{what} must be an integer")
        return int(v)
    return float(v)


def _merge(defaults, obj, what):
    if obj is None:
        obj = {}
    if not isinstance(obj, dict):
        raise ForgeError(400, f"{what} must be an object")
    unknown = sorted(set(obj) - set(defaults))
    if unknown:
        raise ForgeError(400, f"unknown {what} field(s): {', '.join(unknown)}")
    return {**defaults, **obj}


def parse_render(obj) -> dict:
    r = _merge(RENDER_DEFAULTS, obj, "render")
    for k in ("prompt", "negative_prompt"):
        r[k] = "" if r[k] is None else r[k]
        if not isinstance(r[k], str):
            raise ForgeError(400, f"render.{k} must be a string")
    r["steps"] = _num(r["steps"], 1, 150, "render.steps", integer=True)
    r["cfg_scale"] = _num(r["cfg_scale"], 0, 64, "render.cfg_scale")
    r["seed"] = _num(r["seed"], -1, 2**31 - 1, "render.seed", integer=True)
    r["apg_scale"] = _num(r["apg_scale"], 0, 1, "render.apg_scale")
    r["scale_phi"] = _num(r["scale_phi"], 0, 1, "render.scale_phi")
    cip = r["cfg_interval_progress"]
    if not isinstance(cip, (list, tuple)) or len(cip) != 2:
        raise ForgeError(400, "render.cfg_interval_progress must be [lo, hi]")
    lo, hi = _num(cip[0], 0, 1, "cfg_interval_progress[0]"), _num(cip[1], 0, 1, "cfg_interval_progress[1]")
    if lo > hi:
        raise ForgeError(400, "render.cfg_interval_progress lo must be <= hi")
    r["cfg_interval_progress"] = [lo, hi]
    r["schedule"] = parse_spec(r["schedule"])
    if r["sampler_type"] in ("", None):
        r["sampler_type"] = None
    elif r["sampler_type"] not in _SAMPLERS:
        raise ForgeError(400, f"render.sampler_type {r['sampler_type']!r} not in {', '.join(_SAMPLERS)}")
    return r


def canonical_key(render) -> str:
    return json.dumps(render, sort_keys=True)


def to_request(render, seed) -> dict:
    keys = ("prompt", "negative_prompt", "steps", "cfg_scale", "apg_scale", "cfg_interval_progress",
            "schedule", "scale_phi", "sampler_type")
    return {**{k: render[k] for k in keys}, "seed": int(seed)}


def parse_chain(obj):
    if obj is None:
        return None
    c = _merge(CHAIN_DEFAULTS, obj, "chain")
    for flag in ("latch_on", "film_on", "lora_on", "bungee_on"):
        if not isinstance(c[flag], bool):
            raise ForgeError(400, f"chain.{flag} must be true or false")
    slots = c["slots"]
    if not isinstance(slots, list) or len(slots) != 2:
        raise ForgeError(400, "chain.slots must have exactly 2 entries")
    parsed = []
    for i, s in enumerate(slots):
        s = _merge(SLOT_DEFAULT, s, f"chain.slots[{i}]")
        s["weight"] = _num(s["weight"], 0, 50, f"slots[{i}].weight")
        s["start_pct"] = _num(s["start_pct"], 0, 1, f"slots[{i}].start_pct")
        s["end_pct"] = _num(s["end_pct"], 0, 1, f"slots[{i}].end_pct")
        s["value"] = _num(s["value"], -1e6, 1e6, f"slots[{i}].value")
        if s["start_pct"] > s["end_pct"]:
            raise ForgeError(400, f"slots[{i}] start_pct must be <= end_pct")
        parsed.append(s)
    c["slots"] = parsed
    hp = _merge(CHAIN_DEFAULTS["hparams"], c["hparams"], "chain.hparams")
    c["hparams"] = {"rho": _num(hp["rho"], 0, 30, "hparams.rho"), "mu": _num(hp["mu"], 0, 30, "hparams.mu"),
                    "gamma": _num(hp["gamma"], 0, 20, "hparams.gamma"),
                    "n_iter": _num(hp["n_iter"], 1, 80, "hparams.n_iter", integer=True),
                    "log_norms": bool(hp["log_norms"])}
    film = _merge(CHAIN_DEFAULTS["film"], c["film"], "chain.film")
    c["film"] = {"ckpt": film["ckpt"] or None, "gain": _num(film["gain"], 0, 2, "film.gain"),
                 "value": _num(film["value"], 0, 16, "film.value")}
    lora = _merge(CHAIN_DEFAULTS["lora"], c["lora"], "chain.lora")
    c["lora"] = {"ckpt_path": lora["ckpt_path"] or None,
                 "slot": None if lora["slot"] is None else _num(lora["slot"], 0, 63, "lora.slot", integer=True),
                 "strength": _num(lora["strength"], 0, 1, "lora.strength")}
    c["semitones"] = _num(c["semitones"], -24, 24, "chain.semitones")
    return c


def chain_to_request(chain, heads) -> dict:
    out = {"latch": None, "film": None, "dora": None}
    if chain is None:
        return out
    if chain["latch_on"]:
        latch = []
        for s in chain["slots"]:
            if s["head"] in (None, "", "none") or s["weight"] <= 0:
                continue
            entry = heads.get(s["head"])
            if entry is None:
                raise ForgeError(400, f"unknown LatCH head {s['head']!r}")
            latch.append({"head": s["head"], "kind": s["kind"], "value": s["value"],
                          "gain": float(entry["default_gain"]) * s["weight"],
                          "start_pct": s["start_pct"], "end_pct": s["end_pct"]})
        if latch:
            g0, hp = latch[0]["gain"], chain["hparams"]
            out.update(latch=latch, rho=hp["rho"] * g0, mu=hp["mu"] * g0, gamma=hp["gamma"],
                       n_iter=hp["n_iter"], log_norms=hp["log_norms"])
    if chain["film_on"]:
        out["film"] = dict(chain["film"])
    if chain["lora_on"]:
        lora = chain["lora"]
        if lora["slot"] is not None:
            out["dora"] = {"slot": lora["slot"], "strength": lora["strength"]}
        elif lora["ckpt_path"]:
            out["dora"] = {"ckpt_path": lora["ckpt_path"], "strength": lora["strength"]}
    return out
```

- [ ] **Step 4: Run tests** — expected all passed.

- [ ] **Step 5: Commit** — `git add eval/forge/render_settings.py eval/tests/test_forge_render_settings.py` then `Misc/agent_commit.sh WINTERMUTE -m "forge: render settings + lane chain -> server request mapping"`.

---

### Task 3: Lane placement

**Files:** Create `eval/forge/lanes.py`, `eval/tests/test_forge_lanes.py`.

**Interfaces:**
- Consumes: `forge.envelope.sample_envelope`.
- Produces: `place_lanes(clips, lanes, overlaps, n_samples, sr, clip_audio) -> list[np.ndarray (2,n_samples) | None]` (length 4); `place_single(clip, n_samples, sr, audio) -> np.ndarray (2,n_samples)`. `clip_audio(clip) -> np.ndarray (2,M)` float32; clip dicts use contract keys `id lane start_sec offset_sec dur_sec loop`; lane dicts `index muted solo gain`; overlap dicts `lane start_sec end_sec a_id b_id curve`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.lanes import place_lanes, place_single

SR = 100
LIN = {"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}


def lanes(**over):
    base = [{"index": i, "muted": False, "solo": False, "gain": 1.0} for i in range(4)]
    for i, patch in over.items():
        base[int(i[1:])].update(patch)
    return base


def ones(n):
    return np.ones((2, n), dtype=np.float32)


def clip(cid, lane, start, dur, offset=0.0, loop=False):
    return {"id": cid, "lane": lane, "start_sec": start, "offset_sec": offset, "dur_sec": dur, "loop": loop}


def test_placement_trim_and_gain():
    audio = {"a": np.arange(300, dtype=np.float32)[None].repeat(2, 0)}
    out = place_lanes([clip("a", 1, 0.5, 1.0, offset=0.2)], lanes(L1={"gain": 0.5}), [], 400, SR,
                      lambda c: audio[c["id"]])
    assert out[0] is None and out[2] is None and out[3] is None
    buf = out[1]
    assert buf.shape == (2, 400)
    assert buf[0, 49] == 0 and buf[0, 50] == pytest.approx(10.0) and buf[0, 149] == pytest.approx(59.5)
    assert buf[0, 150] == 0


def test_loop_fills_until_next_clip():
    seg = np.arange(10, dtype=np.float32)[None].repeat(2, 0)
    out = place_lanes([clip("a", 0, 0.0, 0.1, loop=True), clip("b", 0, 0.35, 0.05)],
                      lanes(), [], 50, SR, lambda c: seg if c["id"] == "a" else ones(5) * 9)
    b = out[0][0]
    np.testing.assert_allclose(b[:35], np.tile(np.arange(10), 4)[:35])
    np.testing.assert_allclose(b[35:40], 9.0)
    assert np.all(b[40:] == 0)


def test_mute_solo():
    cs = [clip("a", 0, 0, 0.1), clip("b", 2, 0, 0.1)]
    out = place_lanes(cs, lanes(L0={"muted": True}), [], 20, SR, lambda c: ones(10))
    assert out[0] is None and out[2] is not None
    out = place_lanes(cs, lanes(L2={"solo": True}), [], 20, SR, lambda c: ones(10))
    assert out[0] is None and out[2] is not None


def test_overlap_equal_power():
    cs = [clip("a", 0, 0.0, 1.0), clip("b", 0, 0.5, 1.0)]
    ov = [{"lane": 0, "start_sec": 0.5, "end_sec": 1.0, "a_id": "a", "b_id": "b", "curve": LIN}]
    out = place_lanes(cs, lanes(), ov, 150, SR, lambda c: ones(100))[0][0]
    assert out[49] == pytest.approx(1.0)
    assert out[50] == pytest.approx(1.0)                                 # v=0: cos 0 + sin 0 = 1
    v = 25 / 49
    assert out[75] == pytest.approx(np.cos(v * np.pi / 2) + np.sin(v * np.pi / 2), abs=1e-5)
    assert out[99] == pytest.approx(1.0, abs=1e-5)                        # v=1: 0 + 1
    assert out[120] == pytest.approx(1.0)


def test_place_single():
    buf = place_single(clip("a", 3, 0.2, 0.3), 100, SR, ones(50) * 2)
    assert buf[0, 19] == 0 and buf[0, 20] == 2 and buf[0, 49] == 2 and buf[0, 50] == 0
```

- [ ] **Step 2: Run to verify failure** — module not found.

- [ ] **Step 3: Implement `eval/forge/lanes.py`**

```python
"""Per-lane audio buffers on the common timeline origin (spec §8.1 S3)."""
import numpy as np

from .envelope import sample_envelope


def _segment(clip, audio, sr, n_samples, next_start):
    s = int(round(clip["start_sec"] * sr))
    off = int(round(clip["offset_sec"] * sr))
    d = int(round(clip["dur_sec"] * sr))
    seg = np.asarray(audio, dtype=np.float32)[:, off:off + d]
    if seg.shape[1] == 0 or s >= n_samples:
        return s, None
    if clip.get("loop"):
        span = max(seg.shape[1], min(next_start, n_samples) - s)
        seg = np.tile(seg, (1, int(np.ceil(span / seg.shape[1]))))[:, :span]
    return s, seg[:, : max(0, min(n_samples, s + seg.shape[1]) - s)]


def place_single(clip, n_samples, sr, audio):
    buf = np.zeros((2, n_samples), dtype=np.float32)
    s, seg = _segment({**clip, "loop": False}, audio, sr, n_samples, n_samples)
    if seg is not None:
        buf[:, s:s + seg.shape[1]] += seg
    return buf


def place_lanes(clips, lanes, overlaps, n_samples, sr, clip_audio):
    soloed = any(l["solo"] for l in lanes)
    audible = {l["index"]: (l["solo"] if soloed else not l["muted"]) for l in lanes}
    gains = {l["index"]: float(l["gain"]) for l in lanes}
    out = [None, None, None, None]
    for lane in range(4):
        if not audible.get(lane):
            continue
        cs = sorted((c for c in clips if c["lane"] == lane), key=lambda c: c["start_sec"])
        buf = np.zeros((2, n_samples), dtype=np.float32)
        used = False
        for k, c in enumerate(cs):
            nxt = int(round(cs[k + 1]["start_sec"] * sr)) if k + 1 < len(cs) else n_samples
            s, seg = _segment(c, clip_audio(c), sr, n_samples, nxt)
            if seg is None or seg.shape[1] == 0:
                continue
            e = s + seg.shape[1]
            w = np.ones(e - s, dtype=np.float32)
            for ov in overlaps:
                if ov["lane"] != lane or c["id"] not in (ov["a_id"], ov["b_id"]):
                    continue
                rs, re_ = int(round(ov["start_sec"] * sr)), int(round(ov["end_sec"] * sr))
                r0, r1 = max(rs, s), min(re_, e)
                if r1 <= r0:
                    continue
                v = sample_envelope(ov["curve"], max(re_ - rs, 1))[r0 - rs:r1 - rs]
                w[r0 - s:r1 - s] *= np.cos(v * np.pi / 2) if c["id"] == ov["a_id"] else np.sin(v * np.pi / 2)
            buf[:, s:e] += seg * w * gains[lane]
            used = True
        out[lane] = buf if used else None
    return out
```

- [ ] **Step 4: Run tests** — expected 5 passed.

- [ ] **Step 5: Commit** — `git add eval/forge/lanes.py eval/tests/test_forge_lanes.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: lane buffer placement (trim, loop, mute/solo, equal-power overlaps)"`.

---

### Task 4: Latent mixing and norm restoration

**Files:** Create `eval/forge/mixing.py`, `eval/tests/test_forge_mixing.py`.

**Interfaces:**
- Produces: `NODE_DEFS`; `lerp(a, b, t)`; `mix_latents(lanes: list[Tensor (1,C,T) | None] len 4, mix: dict, slerp_fn=None) -> (Tensor, w_eff: list[float] len 4)`; `normalise(z, lanes, w_eff) -> Tensor`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to verify failure** — module not found.

- [ ] **Step 3: Implement `eval/forge/mixing.py`**

```python
"""Latent mix tree and norm restoration (spec §8.1 S7-S8)."""
import torch

from .contract import ForgeError

NODE_DEFS = {"tree": [("M1", "L0", "L1"), ("M2", "L2", "L3"), ("MX", "M1", "M2")],
             "cascade": [("M1", "L0", "L1"), ("M2", "M1", "L2"), ("MX", "M2", "L3")]}


def lerp(a, b, t):
    return (1.0 - float(t)) * a + float(t) * b


def _default_slerp():
    from stable_audio_3.inference.longform import slerp
    return slerp


def mix_latents(lanes, mix, slerp_fn=None):
    order = mix.get("order")
    if order == "quad":
        used = [i for i in range(4) if lanes[i] is not None]
        if not used:
            raise ForgeError(400, "nothing to mix — every lane is empty or muted")
        raw = [max(0.0, float(mix["quad_weights"][i])) for i in used]
        total = sum(raw)
        ws = [1.0 / len(used)] * len(used) if total <= 0 else [r / total for r in raw]
        z = sum(w * lanes[i].float() for w, i in zip(ws, used))
        weff = [0.0] * 4
        for w, i in zip(ws, used):
            weff[i] = w
        return z, weff
    if order not in NODE_DEFS:
        raise ForgeError(400, f"unknown mix order {order!r}")
    vals = {f"L{i}": ((lanes[i].float(), {i: 1.0}) if lanes[i] is not None else (None, None)) for i in range(4)}
    for name, a, b in NODE_DEFS[order]:
        (za, wa), (zb, wb) = vals[a], vals[b]
        if za is None and zb is None:
            vals[name] = (None, None)
        elif zb is None:
            vals[name] = (za, wa)
        elif za is None:
            vals[name] = (zb, wb)
        else:
            node = mix["nodes"][name]
            t = float(node["t"])
            if node["interp"] == "slerp":
                z = (slerp_fn or _default_slerp())(za, zb, t)
            elif node["interp"] == "lerp":
                z = lerp(za, zb, t)
            else:
                raise ForgeError(400, f"unknown interp {node['interp']!r} at {name}")
            w = {k: v * (1.0 - t) for k, v in wa.items()}
            for k, v in wb.items():
                w[k] = w.get(k, 0.0) + v * t
            vals[name] = (z, w)
    z, w = vals["MX"]
    if z is None:
        raise ForgeError(400, "nothing to mix — every lane is empty or muted")
    return z, [float(w.get(i, 0.0)) for i in range(4)]


def normalise(z, lanes, w_eff):
    target = torch.zeros_like(z[:, :1, :].float())
    for i, lane in enumerate(lanes):
        if lane is not None and w_eff[i] > 0:
            target = target + w_eff[i] * lane.float().norm(dim=1, keepdim=True)
    cur = z.float().norm(dim=1, keepdim=True).clamp(min=1e-8)
    return z.float() * (target / cur)
```

- [ ] **Step 4: Run tests** — expected 6 passed.

- [ ] **Step 5: Commit** — `git add eval/forge/mixing.py eval/tests/test_forge_mixing.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: latent mix tree/cascade/quad + norm restoration"`.

---

### Task 5: Hold math and latent splice

**Files:** Create `eval/forge/holdpass.py`, `eval/forge/splice.py`, `eval/tests/test_forge_holdpass.py`.

**Interfaces:**
- Consumes: `forge.envelope.sample_envelope`, `forge.contract.SPLICE_XFADE_FRAMES`.
- Produces: `clip_frame_span(start_sec, dur_sec, fps) -> (f0:int, n:int)`; `depth_for_spans(spans: list[(f0, env, n)], T) -> np.ndarray float32 (T,)`; `make_hold_callback(z_ref (1,C,T) cpu, eps (1,C,T) cpu, depth (T,)) -> callable(state_dict)`; `make_hold_renoise_hook(z_ref, eps, depth) -> callable(denoised, t_next, x, i) -> Tensor`; `splice_by_mask(z_old, z_new, mask (T,) bool, xfade=SPLICE_XFADE_FRAMES) -> Tensor`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge.holdpass import (clip_frame_span, depth_for_spans, make_hold_callback,
                            make_hold_renoise_hook)
from forge.splice import splice_by_mask

FLAT = lambda v: {"points": [v] * 4, "curves": [0, 0, 0]}  # noqa: E731


def test_clip_frame_span():
    assert clip_frame_span(0.0, 1.0, 10.0) == (0, 10)
    assert clip_frame_span(0.25, 0.5, 10.0) == (2, 6)          # floor(2.5)=2, ceil(7.5)=8
    assert clip_frame_span(3.0, 0.0, 10.0) == (30, 1)


def test_depth_for_spans_max_and_clip():
    d = depth_for_spans([(2, FLAT(0.3), 4), (4, FLAT(0.6), 10)], 10)
    np.testing.assert_allclose(d, [0, 0, 0.3, 0.3, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6], atol=1e-6)
    assert d.dtype == np.float32


def test_hold_callback_holds_until_release():
    T = 4
    ref = torch.arange(T, dtype=torch.float32).view(1, 1, T)
    eps = torch.ones(1, 1, T)
    depth = np.array([0.0, 0.5, 1.0, 0.2], dtype=np.float32)
    cb = make_hold_callback(ref, eps, depth)
    x = torch.full((1, 1, T), 99.0)
    cb({"x": x, "t": torch.tensor([0.4])})
    # depth < t held to (1-t)*ref + t*eps ; depth >= t left alone
    expect = [0.6 * 0 + 0.4, 99.0, 99.0, 0.6 * 3 + 0.4]
    np.testing.assert_allclose(x.view(-1).numpy(), expect, atol=1e-6)
    x2 = torch.full((1, 1, T), 7.0)
    cb({"x": x2, "t": torch.tensor(0.1)})                         # 0-d t (pingpong-style) also works
    np.testing.assert_allclose(x2.view(-1).numpy(), [0.9 * 0 + 0.1, 7.0, 7.0, 7.0], atol=1e-6)


def test_renoise_hook_applies_hold_after_renoise():
    T = 3
    ref = torch.zeros(1, 1, T)
    eps = torch.full((1, 1, T), 2.0)
    depth = np.array([0.0, 0.9, 0.0], dtype=np.float32)
    hook = make_hold_renoise_hook(ref, eps, depth)
    torch.manual_seed(0)
    out = hook(torch.full((1, 1, T), 5.0), torch.tensor(0.5), torch.zeros(1, 1, T), 0)
    assert out[0, 0, 0].item() == pytest.approx(1.0) and out[0, 0, 2].item() == pytest.approx(1.0)
    assert out[0, 0, 1].item() != pytest.approx(1.0)              # released frame keeps the renoised draw


def test_splice_by_mask_crossfade():
    old = torch.zeros(1, 1, 10)
    new = torch.ones(1, 1, 10)
    mask = np.zeros(10, bool)
    mask[2:8] = True
    out = splice_by_mask(old, new, mask, xfade=2).view(-1).numpy()
    np.testing.assert_allclose(out, [0, 0, 1 / 3, 2 / 3, 1, 1, 2 / 3, 1 / 3, 0, 0], atol=1e-6)
    short = np.zeros(10, bool)
    short[4:6] = True
    out2 = splice_by_mask(old, new, short, xfade=2).view(-1).numpy()
    assert out2[:4].max() == 0 and out2[6:].max() == 0 and 0 < out2[4] <= 1
    assert torch.equal(splice_by_mask(old, new, np.zeros(10, bool)), old)
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_holdpass.py -q` → module not found.

- [ ] **Step 3: Implement**

`eval/forge/holdpass.py`:
```python
"""Graded-release hold for per-frame A2A noise (spec §8.1 S4-S5).

Generalises the /a2a_mix sinesweep hold (explorer_render_server.py 1793-1799): at step
time t, frames whose depth is below t are overwritten with (1-t)*z_ref + t*eps — they
have not been released yet. ODE samplers take it as the step callback; pingpong takes it
as a renoise_hook because its callback fires after the denoise, where edits to x are lost.
"""
import math

import numpy as np
import torch

from .envelope import sample_envelope


def clip_frame_span(start_sec, dur_sec, fps):
    f0 = int(math.floor(float(start_sec) * fps))
    f1 = int(math.ceil((float(start_sec) + float(dur_sec)) * fps))
    return f0, max(1, f1 - f0)


def depth_for_spans(spans, T):
    depth = np.zeros(int(T), dtype=np.float32)
    for f0, env, n in spans:
        vals = sample_envelope(env, n)
        lo, hi = max(0, f0), min(int(T), f0 + n)
        if hi > lo:
            depth[lo:hi] = np.maximum(depth[lo:hi], vals[lo - f0:hi - f0])
    return depth


def _scalar(t):
    return float(t.reshape(-1)[0]) if torch.is_tensor(t) else float(t)


class _Held:
    def __init__(self, z_ref, eps, depth):
        self.ref, self.eps = z_ref.float(), eps.float()
        self.depth = torch.as_tensor(np.asarray(depth, dtype=np.float32)).view(1, 1, -1)
        self._dev = None

    def on(self, device, dtype):
        if self._dev != (device, dtype):
            self.ref_d = self.ref.to(device, dtype)
            self.eps_d = self.eps.to(device, dtype)
            self.depth_d = self.depth.to(device)
            self._dev = (device, dtype)
        return self

    def apply(self, x, t):
        self.on(x.device, x.dtype)
        n = min(x.shape[-1], self.ref_d.shape[-1], self.depth_d.shape[-1])
        hold = self.depth_d[..., :n] < t
        target = (1.0 - t) * self.ref_d[..., :n] + t * self.eps_d[..., :n]
        x[..., :n] = torch.where(hold, target, x[..., :n])
        return x


def make_hold_callback(z_ref, eps, depth):
    held = _Held(z_ref, eps, depth)

    def callback(state):
        held.apply(state["x"], _scalar(state["t"]))
    return callback


def make_hold_renoise_hook(z_ref, eps, depth):
    held = _Held(z_ref, eps, depth)

    def hook(denoised, t_next, x, i):
        tn = _scalar(t_next)
        x_next = (1.0 - tn) * denoised + tn * torch.randn_like(x)
        return held.apply(x_next, tn)
    return hook
```

`eval/forge/splice.py`:
```python
"""Frame-level latent splice with a short linear crossfade inside region edges (spec §8.1 S5-S6)."""
import numpy as np
import torch

from .contract import SPLICE_XFADE_FRAMES


def _runs(mask):
    m = np.concatenate([[False], np.asarray(mask, bool), [False]])
    d = np.diff(m.astype(np.int8))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def splice_by_mask(z_old, z_new, mask, xfade=SPLICE_XFADE_FRAMES):
    mask = np.asarray(mask, bool)
    if not mask.any():
        return z_old
    T = z_old.shape[-1]
    w = np.zeros(T, dtype=np.float32)
    for a, b in _runs(mask[:T]):
        w[a:b] = 1.0
        n = b - a
        for k in range(min(int(xfade), n)):
            ramp = (k + 1) / (int(xfade) + 1)
            w[a + k] = min(w[a + k], ramp)
            w[b - 1 - k] = min(w[b - 1 - k], ramp)
    wt = torch.as_tensor(w, dtype=torch.float32).view(1, 1, -1)
    return (1.0 - wt) * z_old.float() + wt * z_new.float()
```

- [ ] **Step 4: Run tests** — expected 5 passed.

- [ ] **Step 5: Commit** — `git add eval/forge/holdpass.py eval/forge/splice.py eval/tests/test_forge_holdpass.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: graded-release hold (callback + pingpong renoise hook) and latent splice"`.

---

### Task 6: Overlap regions and chroma targets

**Files:** Create `eval/forge/overlap.py`, `eval/tests/test_forge_overlap.py`.

**Interfaces:**
- Consumes: `sample_envelope`.
- Produces: `region_frames(start_sec, end_sec, fps, T) -> (f0, f1)`; `chroma_target(cA (384,T), cB (384,T), f0, f1, curve) -> np.ndarray (384,T)`; `pad_target(target (C,T), frames) -> np.ndarray (C,frames)` (edge padding or crop).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np

import forge_testutil  # noqa: F401
from forge.overlap import chroma_target, pad_target, region_frames

LIN = {"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}


def test_region_frames_clamped():
    assert region_frames(0.25, 0.75, 10.0, 100) == (2, 8)
    assert region_frames(-1.0, 50.0, 10.0, 100) == (0, 100)


def test_chroma_target_ramps():
    A = np.zeros((384, 10), np.float32)
    B = np.ones((384, 10), np.float32)
    t = chroma_target(A, B, 3, 8, LIN)
    np.testing.assert_allclose(t[0], [0, 0, 0, 0, 0.25, 0.5, 0.75, 1, 1, 1], atol=1e-6)


def test_pad_target():
    x = np.arange(6, dtype=np.float32).reshape(2, 3)
    np.testing.assert_allclose(pad_target(x, 5), [[0, 1, 2, 2, 2], [3, 4, 5, 5, 5]])
    np.testing.assert_allclose(pad_target(x, 2), [[0, 1], [3, 4]])
```

- [ ] **Step 2: Run to verify failure** — module not found.

- [ ] **Step 3: Implement `eval/forge/overlap.py`**

```python
"""Overlap regions and the chroma-crossfade guidance target (spec §8.1 S6)."""
import math

import numpy as np

from .envelope import sample_envelope


def region_frames(start_sec, end_sec, fps, T):
    f0 = max(0, int(math.floor(float(start_sec) * fps)))
    f1 = min(int(T), int(math.ceil(float(end_sec) * fps)))
    return f0, max(f0, f1)


def chroma_target(cA, cB, f0, f1, curve):
    tgt = np.array(cA, dtype=np.float32, copy=True)
    tgt[:, f1:] = cB[:, f1:]
    n = f1 - f0
    if n > 0:
        v = sample_envelope(curve, n)[None, :]
        tgt[:, f0:f1] = (1.0 - v) * cA[:, f0:f1] + v * cB[:, f0:f1]
    return tgt


def pad_target(target, frames):
    t = np.asarray(target, dtype=np.float32)
    if t.shape[1] >= frames:
        return np.ascontiguousarray(t[:, :frames])
    return np.pad(t, ((0, 0), (0, frames - t.shape[1])), mode="edge")
```

- [ ] **Step 4: Run tests** — expected 3 passed.

- [ ] **Step 5: Commit** — `git add eval/forge/overlap.py eval/tests/test_forge_overlap.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: overlap region frames, chroma crossfade target, target padding"`.

---

### Task 7: GPU passes

**Files:** Create `eval/forge/passes.py`, `eval/tests/test_forge_passes.py`.

**Interfaces:**
- Consumes: server `srv` module functions `prepare_model, resolve_dora_req, resolve_latch, apply_latch, resolve_cfg_interval, resolve_shift, latch_sampler_warning, make_log_cb, film_context, with_lora_interval, budget_for, log, _player_steer_head`, globals `MODEL, GPU_LOCK, SR, DS, HEADS`; Tasks 5–6.
- Produces: `model_latent_frames(srv, req, duration) -> int`; `run_hold_pass(srv, z_lane, depth, req, warnings, label) -> Tensor (1,C,T) cpu float32`; `run_inpaint_pass(srv, z_lane, regions_sec: list[(s,e)], req, warnings, chroma_target=None, label) -> Tensor`; `steer_master(srv, z, head, gain) -> Tensor`; `decode_latent(srv, z, n_samples) -> torch.Tensor (2, n_samples) cpu float32`. `req` is a request dict: `render_settings.to_request(...)` merged with `chain_to_request(...)`.

- [ ] **Step 1: Write the failing test**

```python
import math
import types

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import passes
from forge.render_settings import parse_render, to_request

DS, SR = 4096, 44100


class FakePre(torch.nn.Module):
    downsampling_ratio = DS

    def __init__(self):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))

    def decode(self, z, chunked=True, chunk_size=128, overlap=32):
        return torch.full((1, 2, z.shape[-1] * DS), 0.25)


class FakeModel:
    def __init__(self, objective="rectified_flow", fill=5.0):
        self.calls, self.fill = [], fill
        self.model = types.SimpleNamespace(diffusion_objective=objective, sampling_dist_shift=None,
                                           pretransform=FakePre())

    def _build_conditioning_dicts(self, prompt, negative, duration, batch):
        return [{"prompt": prompt, "seconds_total": duration}], None

    def _adapt_sample_size(self, cond, sample_size, pad, allow_grow=False):
        return int(math.ceil((cond[0]["seconds_total"] + pad) * SR / DS)) * DS

    def generate(self, **kw):
        self.calls.append(kw)
        frames = kw["sample_size"] // DS
        kw["latents_sink"].append(torch.full((1, 8, frames), self.fill))
        return kw["latents_sink"][-1]


@pytest.fixture
def srv(monkeypatch):
    import explorer_render_server as srv
    monkeypatch.setattr(srv, "prepare_model", lambda *a, **k: False)
    return srv


def req(**kw):
    return to_request(parse_render(kw), seed=11)


def test_zero_depth_skips(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    z = torch.randn(1, 8, 20)
    out = passes.run_hold_pass(srv, z, np.zeros(20, np.float32), req(prompt="p"), [], "lane0")
    assert torch.equal(out, z) and fm.calls == []


def test_hold_pass_callback_path(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    z = torch.zeros(1, 8, 20)
    depth = np.zeros(20, np.float32)
    depth[5:15] = 0.4
    w = []
    out = passes.run_hold_pass(srv, z, depth, req(prompt="p", steps=8), w, "lane0")
    kw = fm.calls[0]
    assert kw["init_noise_level"] == pytest.approx(0.4)
    assert kw["init_latents"].shape == (1, 8, 20)
    assert "renoise_hook" not in kw and callable(kw["callback"])
    assert kw["cfg_interval"] == pytest.approx((0.0, 0.4))
    assert kw["return_latents"] is True
    assert torch.equal(out[..., :5], z[..., :5]) and torch.equal(out[..., 15:], z[..., 15:])
    assert float(out[0, 0, 10]) == pytest.approx(5.0)


@pytest.mark.parametrize("objective,sampler", [("rectified_flow", "pingpong"), ("rf_denoiser", None)])
def test_hold_pass_pingpong_uses_renoise_hook(srv, monkeypatch, objective, sampler):
    fm = FakeModel(objective)
    monkeypatch.setattr(srv, "MODEL", fm)
    depth = np.full(12, 0.3, np.float32)
    passes.run_hold_pass(srv, torch.zeros(1, 8, 12), depth, req(prompt="p", sampler_type=sampler), [], "l")
    assert callable(fm.calls[0]["renoise_hook"])


def test_non_finite_aborts(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel(fill=float("nan")))
    with pytest.raises(RuntimeError, match="non-finite latents in lane2"):
        passes.run_hold_pass(srv, torch.zeros(1, 8, 12), np.full(12, 0.5, np.float32), req(prompt="p"), [], "lane2")


def test_inpaint_pass_regions_and_chroma(srv, monkeypatch):
    fm = FakeModel()
    monkeypatch.setattr(srv, "MODEL", fm)
    monkeypatch.setitem(srv.HEADS, "chroma_other", {"path": "/x/chroma.pt", "default_gain": 2048.0})
    z = torch.zeros(1, 8, 40)
    tgt = np.ones((384, 40), np.float32)
    out = passes.run_inpaint_pass(srv, z, [(1.0, 2.0)], req(prompt="p", steps=8), [], chroma_target=tgt, label="ov")
    kw = fm.calls[0]
    assert kw["inpaint_mask_start_seconds"] == [1.0] and kw["inpaint_mask_end_seconds"] == [2.0]
    assert kw["cfg_interval"] == pytest.approx((0.0, 1.0))
    frames = passes.model_latent_frames(srv, req(prompt="p"), 40 * DS / SR)
    assert np.asarray(kw["latch_configs"][0]["target_raw"]).shape == (384, frames)
    f0, f1 = math.floor(1.0 * SR / DS), math.ceil(2.0 * SR / DS)
    assert float(out[0, 0, f0 + 3]) == pytest.approx(5.0) and float(out[0, 0, 0]) == 0.0 and float(out[0, 0, f1 + 1]) == 0.0


def test_inpaint_without_chroma_head_warns(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.delitem(srv.HEADS, "chroma_other", raising=False)
    w = []
    passes.run_inpaint_pass(srv, torch.zeros(1, 8, 40), [(1.0, 2.0)], req(prompt="p"), w,
                            chroma_target=np.ones((384, 40), np.float32), label="ov")
    assert any("chroma crossfade skipped" in m for m in w)


def test_steer_and_decode(srv, monkeypatch):
    monkeypatch.setattr(srv, "MODEL", FakeModel())
    monkeypatch.setattr(srv, "_player_steer_head", lambda name: (lambda z, t: z))
    z = torch.zeros(1, 2, 3)
    out = passes.steer_master(srv, z, "rms_energy_bass", 6.0)
    assert torch.allclose(out, torch.ones(1, 2, 3))
    audio = passes.decode_latent(srv, torch.zeros(1, 8, 3), 5000)
    assert audio.shape == (2, 5000) and float(audio[0, 0]) == 0.25
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_passes.py -q` → module not found.

- [ ] **Step 3: Implement `eval/forge/passes.py`**

```python
"""GPU passes of the commit pipeline and its preview jobs (spec §8.1). Every model call holds srv.GPU_LOCK."""
import numpy as np
import torch

from .holdpass import make_hold_callback, make_hold_renoise_hook
from .overlap import pad_target
from .splice import splice_by_mask


def _param(srv):
    return next(srv.MODEL.model.pretransform.parameters())


def _finite(z, label):
    if not torch.isfinite(z).all():
        raise RuntimeError(f"non-finite latents in {label} — refusing to continue")


def model_latent_frames(srv, req, duration):
    """The latent length generate() will actually use (sample_size is an explicit cap)."""
    cond, _ = srv.MODEL._build_conditioning_dicts(req["prompt"], req.get("negative_prompt") or None, duration, 1)
    return int(srv.MODEL._adapt_sample_size(cond, srv.budget_for(duration), 6.0, allow_grow=False) // srv.DS)


def _base_kwargs(srv, req, duration, sigma_max, warnings, latch_cfgs):
    steps = int(req["steps"])
    kw = dict(prompt=req["prompt"], duration=duration, steps=steps, cfg_scale=float(req["cfg_scale"]),
              seed=int(req["seed"]), batch_size=1, sample_size=srv.budget_for(duration),
              apg_scale=float(req["apg_scale"]),
              cfg_interval=srv.resolve_cfg_interval(req, sigma_max=sigma_max),
              dist_shift=srv.resolve_shift(req, steps, sigma_max, warnings))
    if req.get("negative_prompt"):
        kw["negative_prompt"] = req["negative_prompt"]
    if float(req.get("scale_phi") or 0.0) > 0:
        kw["scale_phi"] = float(req["scale_phi"])
    if req.get("sampler_type") and not latch_cfgs:
        kw["sampler_type"] = req["sampler_type"]
    srv.latch_sampler_warning(latch_cfgs, req, warnings)
    return kw


def _generate_latents(srv, kw, req, T, label):
    sink = []
    with srv.film_context(req.get("film")):
        srv.MODEL.generate(**srv.with_lora_interval(kw), latents_sink=sink, return_latents=True)
    z0 = sink[0][..., :T].float().cpu()
    _finite(z0, label)
    return z0


def run_hold_pass(srv, z_lane, depth, req, warnings, label="a2a"):
    depth = np.asarray(depth, dtype=np.float32)
    nl = float(depth.max()) if depth.size else 0.0
    if nl < 1e-3:
        return z_lane
    T = int(z_lane.shape[-1])
    duration = T * srv.DS / srv.SR
    ref = z_lane.float().cpu()
    eps = torch.randn(ref.shape, generator=torch.Generator().manual_seed(int(req["seed"])))
    steps = int(req["steps"])
    with srv.GPU_LOCK:
        srv.prepare_model(srv.resolve_dora_req(req), req.get("film"))
        latch_cfgs, latch_hp = srv.resolve_latch(req.get("latch"), req)
        kw = _base_kwargs(srv, req, duration, nl, warnings, latch_cfgs)
        kw.update(init_latents=ref.to(_param(srv).device), init_noise_level=nl)
        sampler = kw.get("sampler_type")
        pingpong = not latch_cfgs and (sampler == "pingpong" or
                                       (sampler is None and srv.MODEL.model.diffusion_objective == "rf_denoiser"))
        if pingpong:
            kw["renoise_hook"] = make_hold_renoise_hook(ref, eps, depth)
            kw["callback"] = srv.make_log_cb(steps)
        else:
            kw["callback"] = srv.make_log_cb(steps, extra=make_hold_callback(ref, eps, depth))
        srv.apply_latch(kw, latch_cfgs, latch_hp)
        srv.log(f"[forge] {label}: hold pass nl={nl:.2f} steps={steps} ({'renoise hook' if pingpong else 'callback'})")
        z0 = _generate_latents(srv, kw, req, T, label)
    return splice_by_mask(ref, z0, depth > 0)


def run_inpaint_pass(srv, z_lane, regions_sec, req, warnings, chroma_target=None, label="inpaint"):
    T = int(z_lane.shape[-1])
    fps = srv.SR / srv.DS
    mask = np.zeros(T, dtype=bool)
    for s, e in regions_sec:
        mask[max(0, int(np.floor(s * fps))):min(T, int(np.ceil(e * fps)))] = True
    if not mask.any():
        return z_lane
    duration = T * srv.DS / srv.SR
    ref = z_lane.float().cpu()
    with srv.GPU_LOCK:
        srv.prepare_model(srv.resolve_dora_req(req), req.get("film"))
        extra = None
        if chroma_target is not None:
            entry = srv.HEADS.get("chroma_other")
            if entry is None:
                warnings.append("chroma crossfade skipped: the chroma_other head is not registered "
                                "(is the eval drive mounted?)")
            else:
                frames = model_latent_frames(srv, req, duration)
                extra = ({"model_path": entry["path"], "target_raw": pad_target(chroma_target, frames),
                          "end_pct": 0.6}, float(entry["default_gain"]))
        latch_cfgs, latch_hp = srv.resolve_latch(req.get("latch"), req, extra_first=extra)
        kw = _base_kwargs(srv, req, duration, 1.0, warnings, latch_cfgs)
        kw.update(inpaint_latents=ref.to(_param(srv).device),
                  inpaint_mask_start_seconds=[float(s) for s, _ in regions_sec],
                  inpaint_mask_end_seconds=[float(e) for _, e in regions_sec],
                  callback=srv.make_log_cb(int(req["steps"])))
        srv.apply_latch(kw, latch_cfgs, latch_hp)
        srv.log(f"[forge] {label}: inpaint {len(regions_sec)} region(s)")
        z0 = _generate_latents(srv, kw, req, T, label)
    return splice_by_mask(ref, z0, mask)


def steer_master(srv, z, head, gain):
    with srv.GPU_LOCK:
        h = srv._player_steer_head(head)
        dev = _param(srv).device
        with torch.inference_mode(False), torch.enable_grad():
            zz = z.detach().float().to(dev).clone().requires_grad_(True)
            ts = torch.tensor([0.001], dtype=torch.float32, device=dev)
            h(zz, ts).mean().backward()
            out = (zz.detach() + float(gain) * zz.grad).cpu()
    _finite(out, "master chain")
    return out


def decode_latent(srv, z, n_samples):
    pre = srv.MODEL.model.pretransform
    p = _param(srv)
    with srv.GPU_LOCK, torch.inference_mode():
        audio = pre.decode(z.to(device=p.device, dtype=p.dtype), chunked=True, chunk_size=128, overlap=32)
    return audio[0, :, : int(n_samples)].float().cpu()
```

- [ ] **Step 4: Run tests** — expected 8 passed.

- [ ] **Step 5: Commit** — `git add eval/forge/passes.py eval/tests/test_forge_passes.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: GPU passes — hold/inpaint with latent splice, master steer, decode"`.

---

### Task 8: Commit validation and pass planning

**Files:** Create `eval/forge/commit.py` (validation + planning part), `eval/tests/test_forge_commit.py`.

**Interfaces:**
- Consumes: `render_settings.{parse_render, parse_chain, chain_to_request, canonical_key, _num}`, `envelope.validate_envelope`, `contract.check_cap`.
- Produces: `STAGES` (9 labels); `audible_lanes(lanes) -> dict[int,bool]`; `validate_commit(payload, heads) -> dict` (normalised: `project_bpm, duration_sec, defaults, lanes[4], clips, overlaps, mix, master, decode_lanes`); `plan_passes(v) -> {"a2a": [{"lane","key","render","clip_ids"}], "inpaint": [{"lane","key","render","overlap_keys","chroma"}], "steps_total"}`. Group keys: `lane<i>:a2a:<n>`, `lane<i>:ov:<overlap key>` (chroma), `lane<i>:inpaint:<n>` (plain).

- [ ] **Step 1: Write the failing test**

```python
import copy

import pytest

import forge_testutil  # noqa: F401
from forge import commit as C
from forge.contract import ForgeError

HEADS = {"rms_energy_bass": {"default_gain": 512.0}, "chroma_other": {"default_gain": 2048.0}}
ENV = {"points": [0.3, 0.3, 0.3, 0.3], "curves": [0, 0, 0]}


def payload():
    return {
        "project_bpm": 140.0, "duration_sec": 40.0, "defaults": {"prompt": "goa"},
        "lanes": [{"index": i, "muted": False, "solo": False, "gain": 1.0, "chain": None} for i in range(4)],
        "clips": [
            {"id": "a", "lane": 0, "start_sec": 0, "offset_sec": 0, "dur_sec": 20, "loop": False,
             "audio": {"kind": "upload", "sha256": "a" * 64}, "native_bpm": 140.0, "detune_cents": 0, "a2a": None},
            {"id": "b", "lane": 0, "start_sec": 16, "offset_sec": 0, "dur_sec": 20, "loop": False,
             "audio": {"kind": "upload", "sha256": "b" * 64}, "native_bpm": 138.0, "detune_cents": 12,
             "a2a": {"render": {"prompt": "acid", "steps": 8}, "envelope": ENV}},
            {"id": "c", "lane": 2, "start_sec": 0, "offset_sec": 0, "dur_sec": 30, "loop": True,
             "audio": {"kind": "crop", "crop_id": "000001"}, "native_bpm": None, "detune_cents": 0,
             "a2a": {"render": {"prompt": "acid", "steps": 8}, "envelope": ENV}},
        ],
        "overlaps": [{"key": "a-b", "lane": 0, "start_sec": 16, "end_sec": 20, "a_id": "a", "b_id": "b",
                      "curve": ENV, "chroma_xfade": True, "render": {"prompt": "blend", "steps": 12}}],
        "mix": {"order": "tree", "nodes": {k: {"interp": "slerp", "t": 0.5} for k in ("M1", "M2", "MX")},
                "quad_weights": [1, 1, 1, 1]},
        "master": {"latch_on": True, "head": "rms_energy_bass", "gain": 64, "norm_on": True},
        "decode_lanes": False,
    }


def test_stage_labels():
    assert C.STAGES == ["DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent", "LANE CHAINS",
                        "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN", "DECODE latent → audio"]


def test_validate_normalises():
    v = C.validate_commit(payload(), HEADS)
    assert [l["index"] for l in v["lanes"]] == [0, 1, 2, 3]
    assert v["lanes"][0]["chain"]["latch_on"] is False
    assert v["clips"][1]["a2a"]["render"]["steps"] == 8 and v["defaults"]["prompt"] == "goa"
    assert v["overlaps"][0]["render"]["steps"] == 12


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p.update(duration_sec=200), "capped at 184 s"),
    (lambda p: p["lanes"].pop(), "indexes 0, 1, 2, 3"),
    (lambda p: p.update(clips=[]), "no clips"),
    (lambda p: p["clips"][1].update(id="a"), "unique"),
    (lambda p: p["clips"][0].update(native_bpm=60.0), "stretch ratio"),
    (lambda p: p["overlaps"][0].update(b_id="c"), "both be on lane 0"),
    (lambda p: p["overlaps"][0].update(start_sec=21), "start_sec < end_sec"),
    (lambda p: p["mix"].update(order="spiral"), "mix order"),
    (lambda p: p["master"].update(head="nope"), "unknown master head"),
    (lambda p: p["lanes"][1].update(chain={"latch_on": True, "slots": [
        {"head": "nope", "kind": "constant", "value": 0, "weight": 1, "start_pct": 0, "end_pct": 0.6},
        {"head": "none", "kind": "constant", "value": 0, "weight": 1, "start_pct": 0, "end_pct": 0.6}]}),
     "unknown LatCH head"),
])
def test_validate_rejects(mutate, needle):
    p = payload()
    mutate(p)
    with pytest.raises(ForgeError) as e:
        C.validate_commit(p, HEADS)
    assert e.value.status == 400 and needle in e.value.message


def test_plan_groups_and_steps():
    plan = C.plan_passes(C.validate_commit(payload(), HEADS))
    assert [(g["lane"], g["key"], g["clip_ids"]) for g in plan["a2a"]] == [(0, "lane0:a2a:0", ["b"]),
                                                                           (2, "lane2:a2a:0", ["c"])]
    assert [(g["key"], g["overlap_keys"], g["chroma"]) for g in plan["inpaint"]] == [("lane0:ov:a-b", ["a-b"], True)]
    assert plan["steps_total"] == 8 + 8 + 12


def test_plan_merges_identical_renders_and_skips_inaudible():
    p = payload()
    p["clips"][0]["a2a"] = copy.deepcopy(p["clips"][1]["a2a"])
    p["overlaps"][0]["chroma_xfade"] = False
    p["lanes"][2]["muted"] = True
    plan = C.plan_passes(C.validate_commit(p, HEADS))
    assert [(g["key"], g["clip_ids"]) for g in plan["a2a"]] == [("lane0:a2a:0", ["a", "b"])]
    assert [(g["key"], g["chroma"]) for g in plan["inpaint"]] == [("lane0:inpaint:0", False)]
    p["lanes"][0]["solo"] = True
    p["lanes"][2]["muted"] = False
    assert [g["lane"] for g in C.plan_passes(C.validate_commit(p, HEADS))["a2a"]] == [0]
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_commit.py -q` → module not found.

- [ ] **Step 3: Implement the first part of `eval/forge/commit.py`**

```python
"""MIXDOWN commit: payload validation, pass planning and orchestration (spec §6.9, §8)."""
from .contract import CAP_SEC, ForgeError, check_cap
from .envelope import validate_envelope
from .render_settings import _num, canonical_key, chain_to_request, parse_chain, parse_render

STAGES = ["DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent", "LANE CHAINS",
          "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN", "DECODE latent → audio"]


def _bool(v, what):
    if not isinstance(v, bool):
        raise ForgeError(400, f"{what} must be true or false")
    return v


def audible_lanes(lanes):
    soloed = any(l["solo"] for l in lanes)
    return {l["index"]: (l["solo"] if soloed else not l["muted"]) for l in lanes}


def validate_commit(payload, heads):
    if not isinstance(payload, dict):
        raise ForgeError(400, "commit payload must be an object")
    bpm = _num(payload.get("project_bpm"), 20, 300, "project_bpm")
    duration = check_cap(payload.get("duration_sec"), "commit")
    defaults = parse_render(payload.get("defaults"))
    lanes_in = payload.get("lanes")
    if (not isinstance(lanes_in, list) or not all(isinstance(l, dict) for l in lanes_in)
            or sorted(l.get("index", -1) for l in lanes_in) != [0, 1, 2, 3]):
        raise ForgeError(400, "lanes must list indexes 0, 1, 2, 3 exactly once")
    lanes = []
    for l in sorted(lanes_in, key=lambda x: x["index"]):
        chain = parse_chain(l.get("chain") or {})
        chain_to_request(chain, heads)
        lanes.append({"index": int(l["index"]), "muted": _bool(l.get("muted", False), "lane.muted"),
                      "solo": _bool(l.get("solo", False), "lane.solo"),
                      "gain": _num(l.get("gain", 1.0), 0, 2, "lane.gain"), "chain": chain})
    clips, by_id = [], {}
    for c in payload.get("clips") or []:
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not cid or cid in by_id:
            raise ForgeError(400, "clip ids must be unique non-empty strings")
        native = c.get("native_bpm")
        native = None if native is None else _num(native, 20, 300, f"clip {cid} native_bpm")
        if native is not None and not 0.5 <= bpm / native <= 2.0:
            raise ForgeError(400, f"clip {cid}: stretch ratio {bpm / native:.3f} outside 0.5..2")
        if not isinstance(c.get("audio"), dict):
            raise ForgeError(400, f"clip {cid}: audio must be an AudioRef object")
        a2a = c.get("a2a")
        if a2a is not None:
            if not isinstance(a2a, dict):
                raise ForgeError(400, f"clip {cid}: a2a must be an object or null")
            a2a = {"render": parse_render(a2a.get("render")), "envelope": validate_envelope(a2a.get("envelope"))}
        clip = {"id": cid, "lane": _num(c.get("lane"), 0, 3, f"clip {cid} lane", integer=True),
                "start_sec": _num(c.get("start_sec"), 0, CAP_SEC, f"clip {cid} start_sec"),
                "offset_sec": _num(c.get("offset_sec", 0.0), 0, 1e5, f"clip {cid} offset_sec"),
                "dur_sec": _num(c.get("dur_sec"), 1e-3, CAP_SEC, f"clip {cid} dur_sec"),
                "loop": _bool(c.get("loop", False), f"clip {cid} loop"), "audio": c["audio"],
                "native_bpm": native, "detune_cents": _num(c.get("detune_cents", 0.0), -100, 100, f"clip {cid} detune"),
                "a2a": a2a}
        clips.append(clip)
        by_id[cid] = clip
    if not clips:
        raise ForgeError(400, "nothing to commit — the arrangement has no clips")
    overlaps = []
    for o in payload.get("overlaps") or []:
        key = o.get("key")
        lane = _num(o.get("lane"), 0, 3, f"overlap {key} lane", integer=True)
        a, b = by_id.get(o.get("a_id")), by_id.get(o.get("b_id"))
        if a is None or b is None or a["lane"] != lane or b["lane"] != lane:
            raise ForgeError(400, f"overlap {key}: clips must both be on lane {lane}")
        start, end = _num(o.get("start_sec"), 0, CAP_SEC, "overlap start"), _num(o.get("end_sec"), 0, CAP_SEC, "overlap end")
        if not start < end:
            raise ForgeError(400, f"overlap {key}: start_sec < end_sec required")
        overlaps.append({"key": str(key), "lane": lane, "start_sec": start, "end_sec": end, "a_id": a["id"],
                         "b_id": b["id"], "curve": validate_envelope(o.get("curve")),
                         "chroma_xfade": _bool(o.get("chroma_xfade", True), "overlap.chroma_xfade"),
                         "render": parse_render(o.get("render"))})
    mix = payload.get("mix") or {}
    if mix.get("order") not in ("tree", "cascade", "quad"):
        raise ForgeError(400, f"unknown mix order {mix.get('order')!r}")
    nodes = {}
    for name in ("M1", "M2", "MX"):
        node = (mix.get("nodes") or {}).get(name) or {}
        if node.get("interp") not in ("lerp", "slerp"):
            raise ForgeError(400, f"mix node {name}: interp must be lerp or slerp")
        nodes[name] = {"interp": node["interp"], "t": _num(node.get("t"), 0, 1, f"mix node {name} t")}
    weights = mix.get("quad_weights")
    if not isinstance(weights, list) or len(weights) != 4:
        raise ForgeError(400, "mix.quad_weights must have 4 numbers")
    master = payload.get("master") or {}
    latch_on = _bool(master.get("latch_on", False), "master.latch_on")
    if latch_on and master.get("head") not in heads:
        raise ForgeError(400, f"unknown master head {master.get('head')!r}")
    return {"project_bpm": bpm, "duration_sec": duration, "defaults": defaults, "lanes": lanes, "clips": clips,
            "overlaps": overlaps,
            "mix": {"order": mix["order"], "nodes": nodes,
                    "quad_weights": [_num(w, 0, 1e6, "quad weight") for w in weights]},
            "master": {"latch_on": latch_on, "head": master.get("head"),
                       "gain": _num(master.get("gain", 64), 0, 120, "master.gain"),
                       "norm_on": _bool(master.get("norm_on", True), "master.norm_on")},
            "decode_lanes": _bool(payload.get("decode_lanes", False), "decode_lanes")}


def plan_passes(v):
    audible = audible_lanes(v["lanes"])
    a2a, inpaint = [], []
    for lane in range(4):
        if not audible[lane]:
            continue
        groups = {}
        for c in sorted((c for c in v["clips"] if c["lane"] == lane), key=lambda c: c["start_sec"]):
            if c["a2a"] is not None:
                groups.setdefault(canonical_key(c["a2a"]["render"]), []).append(c)
        for n, members in enumerate(groups.values()):
            a2a.append({"lane": lane, "key": f"lane{lane}:a2a:{n}", "render": members[0]["a2a"]["render"],
                        "clip_ids": [c["id"] for c in members]})
        plain = {}
        for o in (o for o in v["overlaps"] if o["lane"] == lane):
            if o["chroma_xfade"]:
                inpaint.append({"lane": lane, "key": f"lane{lane}:ov:{o['key']}", "render": o["render"],
                                "overlap_keys": [o["key"]], "chroma": True})
            else:
                plain.setdefault(canonical_key(o["render"]), []).append(o)
        for n, members in enumerate(plain.values()):
            inpaint.append({"lane": lane, "key": f"lane{lane}:inpaint:{n}", "render": members[0]["render"],
                            "overlap_keys": [o["key"] for o in members], "chroma": False})
    return {"a2a": a2a, "inpaint": inpaint, "steps_total": sum(g["render"]["steps"] for g in a2a + inpaint)}
```

- [ ] **Step 4: Run tests** — expected all passed.

- [ ] **Step 5: Commit** — `git add eval/forge/commit.py eval/tests/test_forge_commit.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: commit payload validation and pass planning"`.

---

### Task 9: Commit orchestration

**Files:**
- Modify: `eval/forge/commit.py` (append `run_commit`), `eval/forge/services.py` (add `stretched_path`)
- Create: `eval/tests/test_forge_commit_run.py`

**Interfaces:**
- Consumes: Tasks 2–8; M2 `progress`, `chroma.chroma_384`, `stretch`, `hashing.file_sha256`; server `new_job, build_response, save_audio, resolve_seed, HEADS`.
- Produces: `Services.stretched_path(src: Path, speed, semitones) -> Path` (identity returns `src`); `run_commit(srv, svc, job_id, payload) -> JobResponse` with `files[0] = mix.wav`, `latents[0] = mix.z0.npy`, `meta.stages` (9 × `{label, on, note, seconds}`), `meta.lanes`, `meta.passes`, `meta.resolved_seeds`, `meta.mix_weights`.

- [ ] **Step 1: Write the failing test**

```python
import math
from pathlib import Path

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import commit as C
from forge import passes, progress
from forge.contract import ForgeError
from test_forge_commit import HEADS, payload


class FakeSvc:
    def __init__(self):
        self.stretch_calls = []

    def resolve_audio(self, ref):
        return Path(f"/fake/{(ref.get('sha256') or ref.get('crop_id'))[:4]}.wav")

    def stretched_path(self, p, speed, semis):
        self.stretch_calls.append((p.name, round(speed, 4), round(semis, 4)))
        return p if abs(speed - 1) < 5e-4 and abs(semis) < 1e-4 else p.with_suffix(".st.wav")

    def load_audio(self, p):
        return np.full((2, 44100 * 40), 0.1, np.float32)

    def encode_cached(self, buf):
        return torch.ones(1, 8, math.ceil(buf.shape[1] / 4096))


@pytest.fixture
def rig(monkeypatch, tmp_path):
    import explorer_render_server as srv
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    calls = {"hold": [], "inpaint": [], "steer": [], "decode": []}
    monkeypatch.setattr(passes, "run_hold_pass",
                        lambda s, z, d, r, w, label: (calls["hold"].append((label, d, r)), z * 2)[1])
    monkeypatch.setattr(passes, "run_inpaint_pass",
                        lambda s, z, reg, r, w, chroma_target=None, label="": (calls["inpaint"].append((label, reg, chroma_target)), z)[1])
    monkeypatch.setattr(passes, "steer_master", lambda s, z, h, g: (calls["steer"].append((h, g)), z)[1])
    monkeypatch.setattr(passes, "decode_latent", lambda s, z, n: (calls["decode"].append(n), torch.zeros(2, n))[1])
    monkeypatch.setattr(C, "chroma_384", lambda audio, sr, T: np.zeros((384, T), np.float32))
    return srv, calls


def test_commit_runs_all_stages(rig):
    srv, calls = rig
    svc = FakeSvc()
    res = C.run_commit(srv, svc, "forge-test-1", payload())
    assert Path(res["files"][0]).name == "mix.wav" and Path(res["files"][0]).is_file()
    assert Path(res["latents"][0]).name == "mix.z0.npy"
    meta = res["meta"]
    assert [s["label"] for s in meta["stages"]] == C.STAGES
    on = [s["on"] for s in meta["stages"]]
    assert on == [True, True, True, False, True, True, True, True, True]
    assert meta["stages"][3]["note"] == "all bypassed"
    T = math.ceil(40 * 44100 / 4096)
    labels = [c[0] for c in calls["hold"]]
    assert labels == ["lane0:a2a:0", "lane2:a2a:0"]
    depth0 = calls["hold"][0][1]
    assert depth0.shape == (T,) and depth0[0] == 0 and depth0[200] == pytest.approx(0.3)
    assert calls["hold"][0][2]["latch"] is None and calls["hold"][0][2]["seed"] >= 0
    assert calls["inpaint"][0][0] == "lane0:ov:a-b" and calls["inpaint"][0][2].shape == (384, T)
    assert calls["steer"] == [("rms_energy_bass", 64.0)]
    assert calls["decode"] == [40 * 44100]
    assert ("bbbb.wav", round(140 / 138, 4), 0.12) in svc.stretch_calls
    assert set(meta["resolved_seeds"]) == {"lane0:a2a:0", "lane2:a2a:0", "lane0:ov:a-b"}
    assert [l["used"] for l in meta["lanes"]] == [True, False, True, False]
    assert progress.snapshot() is None


def test_commit_all_muted_is_400(rig):
    srv, _ = rig
    p = payload()
    for lane in p["lanes"]:
        lane["muted"] = True
    with pytest.raises(ForgeError) as e:
        C.run_commit(srv, FakeSvc(), "forge-test-2", p)
    assert e.value.status == 400 and "every lane is empty or muted" in e.value.message
    assert progress.snapshot() is None
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_commit_run.py -q` → `AttributeError: module 'forge.commit' has no attribute 'run_commit'`.

- [ ] **Step 3: Add `Services.stretched_path` to `eval/forge/services.py`**

```python
    def stretched_path(self, src, speed, semitones):
        from . import stretch
        from .hashing import file_sha256
        src = Path(src)
        if stretch.is_identity(speed, semitones):
            return src
        stretch.validate(speed, semitones)
        sha = file_sha256(src)
        dst = self._paths().cache_dir("stretch") / f"{stretch.cache_key(sha, speed, semitones)}.wav"
        if not dst.exists():
            readable = src
            if src.suffix.lower() not in (".wav", ".flac"):
                readable = self._paths().cache_dir("decode") / f"{sha}.wav"
                if not readable.exists():
                    sf.write(readable, self.load_audio(src).T, self.srv.SR, subtype="FLOAT")
            stretch.stretch_file(readable, dst, speed, semitones)
        return dst
```

- [ ] **Step 4: Append `run_commit` to `eval/forge/commit.py`**

Add to the imports at the top of `commit.py`:
```python
import time

import numpy as np
import torch

from . import passes, progress
from .chroma import chroma_384
from .contract import FPS, HOP, SR, latent_frames
from .holdpass import clip_frame_span, depth_for_spans
from .lanes import place_lanes, place_single
from .mixing import mix_latents, normalise
from .overlap import chroma_target, region_frames
from .render_settings import to_request
```

Append:
```python
def _seed(srv, render):
    return int(render["seed"]) if render["seed"] >= 0 else int(srv.resolve_seed(-1))


def run_commit(srv, svc, job_id, payload):
    v = validate_commit(payload, srv.HEADS)
    plan = plan_passes(v)
    seeds = {g["key"]: _seed(srv, g["render"]) for g in plan["a2a"] + plan["inpaint"]}
    flags = [{"label": s, "on": False, "note": "", "seconds": 0.0} for s in STAGES]
    timings, warnings, passes_meta = {}, [], []
    t0 = time.time()
    progress.begin(job_id, "commit", plan["steps_total"], STAGES)

    def enter(i):
        progress.stage(i + 1, STAGES[i])
        return time.time()

    def leave(i, ts, on, note):
        flags[i].update(on=bool(on), note=note, seconds=round(time.time() - ts, 2))
        timings[f"S{i + 1}"] = flags[i]["seconds"]

    try:
        out_id, jd = srv.new_job("forgecommit")
        T = latent_frames(v["duration_sec"])
        n_samples = T * HOP
        clips = {c["id"]: c for c in v["clips"]}
        lanes = v["lanes"]

        ts = enter(0)
        paths = {cid: svc.resolve_audio(c["audio"]) for cid, c in clips.items()}
        crops = [cid for cid, c in clips.items() if c["audio"].get("kind") == "crop"]
        leave(0, ts, crops, f"{len(crops)} crop(s)" if crops else "no latents")

        ts = enter(1)
        audio, stretched = {}, []
        for cid, c in clips.items():
            chain = lanes[c["lane"]]["chain"]
            speed = v["project_bpm"] / c["native_bpm"] if c["native_bpm"] else 1.0
            semis = (chain["semitones"] if chain["bungee_on"] else 0.0) + c["detune_cents"] / 100.0
            path = svc.stretched_path(paths[cid], speed, semis)
            if path != paths[cid]:
                stretched.append(cid)
            audio[cid] = svc.load_audio(path)
        leave(1, ts, stretched, f"{len(stretched)} clip(s)" if stretched else "at tempo")

        ts = enter(2)
        bufs = place_lanes(v["clips"], lanes, v["overlaps"], n_samples, SR, lambda c: audio[c["id"]])
        z = [None if b is None else svc.encode_cached(b)[..., :T].float() for b in bufs]
        used = [i for i in range(4) if z[i] is not None]
        leave(2, ts, used, ", ".join(f"L{i + 1}" for i in used) or "idle")
        if not used:
            raise ForgeError(400, "nothing to commit — every lane is empty or muted")

        ts = enter(3)
        a2a_lanes = sorted({g["lane"] for g in plan["a2a"] if z[g["lane"]] is not None})
        chain_lanes = [i for i in used
                       if any(chain_to_request(lanes[i]["chain"], srv.HEADS)[k] for k in ("latch", "film", "dora"))]
        notes = [f"L{i + 1}" + ("" if i in a2a_lanes else " (idle — no A2A clip)") for i in chain_lanes]
        leave(3, ts, set(chain_lanes) & set(a2a_lanes), ", ".join(notes) or "all bypassed")

        ts = enter(4)
        for g in plan["a2a"]:
            lane = g["lane"]
            if z[lane] is None:
                continue
            spans = []
            for cid in g["clip_ids"]:
                f0, n = clip_frame_span(clips[cid]["start_sec"], clips[cid]["dur_sec"], FPS)
                spans.append((f0, clips[cid]["a2a"]["envelope"], n))
            req = {**to_request(g["render"], seeds[g["key"]]), **chain_to_request(lanes[lane]["chain"], srv.HEADS)}
            tp = time.time()
            z[lane] = passes.run_hold_pass(srv, z[lane], depth_for_spans(spans, T), req, warnings, label=g["key"])
            passes_meta.append({"lane": lane, "kind": "a2a", "key": g["key"], "seed": seeds[g["key"]],
                                "steps": g["render"]["steps"], "seconds": round(time.time() - tp, 2)})
        leave(4, ts, a2a_lanes, " ".join(f"L{i + 1}" for i in a2a_lanes) or "none")

        ts = enter(5)
        ovs = {o["key"]: o for o in v["overlaps"]}
        for g in plan["inpaint"]:
            lane = g["lane"]
            if z[lane] is None:
                continue
            group = [ovs[k] for k in g["overlap_keys"]]
            target = None
            if g["chroma"]:
                o = group[0]
                c_a = chroma_384(place_single(clips[o["a_id"]], n_samples, SR, audio[o["a_id"]]), SR, T)
                c_b = chroma_384(place_single(clips[o["b_id"]], n_samples, SR, audio[o["b_id"]]), SR, T)
                f0, f1 = region_frames(o["start_sec"], o["end_sec"], FPS, T)
                target = chroma_target(c_a, c_b, f0, f1, o["curve"])
            tp = time.time()
            z[lane] = passes.run_inpaint_pass(srv, z[lane], [(o["start_sec"], o["end_sec"]) for o in group],
                                              to_request(g["render"], seeds[g["key"]]), warnings,
                                              chroma_target=target, label=g["key"])
            passes_meta.append({"lane": lane, "kind": "inpaint", "key": g["key"], "seed": seeds[g["key"]],
                                "steps": g["render"]["steps"], "seconds": round(time.time() - tp, 2)})
        n_ov = len(v["overlaps"])
        leave(5, ts, plan["inpaint"], f"{n_ov} region{'s' if n_ov != 1 else ''}" if n_ov else "none")

        ts = enter(6)
        mixed, weff = mix_latents(z, v["mix"])
        note = "lerp" if v["mix"]["order"] == "quad" else "·".join(v["mix"]["nodes"][k]["interp"][0] for k in ("M1", "M2", "MX"))
        leave(6, ts, len(used) > 1, note)

        ts = enter(7)
        m = v["master"]
        if m["norm_on"]:
            mixed = normalise(mixed, z, weff)
        if m["latch_on"]:
            mixed = passes.steer_master(srv, mixed, m["head"], m["gain"])
        leave(7, ts, m["latch_on"] or m["norm_on"],
              " + ".join(x for x in ("latch" if m["latch_on"] else "", "norm" if m["norm_on"] else "") if x) or "bypassed")

        ts = enter(8)
        n_out = int(round(v["duration_sec"] * SR))
        mix_wav, mix_z = jd / "mix.wav", jd / "mix.z0.npy"
        srv.save_audio(mix_wav, passes.decode_latent(srv, mixed, n_out), SR, normalize=True)
        np.save(mix_z, mixed.squeeze(0).to(torch.float16).numpy())
        files, lanes_meta = [mix_wav], []
        for i in range(4):
            if z[i] is None:
                lanes_meta.append({"index": i, "used": False, "z0_path": None, "wav_path": None})
                continue
            zp = jd / f"lane{i}.z0.npy"
            np.save(zp, z[i].squeeze(0).to(torch.float16).numpy())
            wp = None
            if v["decode_lanes"]:
                wp = jd / f"lane{i}.wav"
                srv.save_audio(wp, passes.decode_latent(srv, z[i], n_out), SR, normalize=True)
                files.append(wp)
            lanes_meta.append({"index": i, "used": True, "z0_path": str(zp), "wav_path": str(wp) if wp else None})
        leave(8, ts, True, f"{v['duration_sec']:g}s")

        meta = {"op": "commit", "latents": [str(mix_z)], "stages": flags, "lanes": lanes_meta,
                "passes": passes_meta, "resolved_seeds": seeds, "mix_weights": weff}
        return srv.build_response(out_id, jd, files, None, t0, timings, warnings, meta, payload, False)
    finally:
        progress.end()
```

- [ ] **Step 5: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_commit_run.py eval/tests/test_forge_commit.py -q`
Expected: all passed.

- [ ] **Step 6: Commit** — `git add eval/forge/commit.py eval/forge/services.py eval/tests/test_forge_commit_run.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: commit orchestration — nine stages, per-lane passes, mix, master, decode"`.

---

### Task 10: `a2a_clip` and inpaint-preview jobs, registration

**Files:**
- Create: `eval/forge/clip_jobs.py`, `eval/tests/test_forge_clip_jobs.py`
- Modify: `eval/forge_api.py` (`bind` registers three runners)

**Interfaces:**
- Consumes: Tasks 2–7, 9 (`Services`), M2 `register_runner`.
- Produces: `validate_a2a_clip(payload, heads) -> dict`; `run_a2a_clip(srv, svc, job_id, payload) -> JobResponse` (`meta.op="a2a_clip"`, `meta.depth_max`, `meta.duration_sec`); `validate_inpaint(payload) -> dict` (adds `span_start`, `span_end`); `run_inpaint_preview(srv, svc, job_id, payload) -> JobResponse` (`meta.op="inpaint"`, `meta.span_start_sec`, `meta.span_end_sec`). Job ops `a2a_clip`, `inpaint`, `commit` accepted by `POST /forge/jobs`, with payload validation at submit.

- [ ] **Step 1: Write the failing test**

```python
import math
from pathlib import Path

import numpy as np
import pytest
import torch

import forge_testutil  # noqa: F401
from forge import clip_jobs as J
from forge import passes, progress
from forge.contract import ForgeError
from test_forge_commit import HEADS, payload as commit_payload
from test_forge_commit_run import FakeSvc

ENV = {"points": [0.2, 0.6, 0.6, 0.2], "curves": [0, 0, 0]}
REF_A = {"kind": "upload", "sha256": "a" * 64}
REF_B = {"kind": "upload", "sha256": "b" * 64}


@pytest.fixture
def rig(monkeypatch, tmp_path):
    import explorer_render_server as srv
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    calls = {"hold": [], "inpaint": []}
    monkeypatch.setattr(passes, "run_hold_pass",
                        lambda s, z, d, r, w, label: (calls["hold"].append((d, r)), z)[1])
    monkeypatch.setattr(passes, "run_inpaint_pass",
                        lambda s, z, reg, r, w, chroma_target=None, label="": (calls["inpaint"].append((reg, chroma_target)), z)[1])
    monkeypatch.setattr(passes, "decode_latent", lambda s, z, n: torch.zeros(2, n))
    monkeypatch.setattr(J, "chroma_384", lambda audio, sr, T: np.zeros((384, T), np.float32))
    return srv, calls


@pytest.mark.parametrize("bad,needle", [
    ({}, "audio"), ({"audio": REF_A, "noise_level": 1.5}, "noise_level"),
    ({"audio": REF_A, "envelope": {"points": [0, 0], "curves": [0]}}, "envelope"),
])
def test_validate_a2a_clip_rejects(bad, needle):
    with pytest.raises(ForgeError) as e:
        J.validate_a2a_clip(bad, HEADS)
    assert needle in e.value.message


def test_run_a2a_clip_flat_noise_and_ckpt(rig):
    srv, calls = rig
    res = J.run_a2a_clip(srv, FakeSvc(), "forge-t", {"audio": REF_A, "render": {"prompt": "acid", "steps": 8},
                                                     "envelope": None, "noise_level": 0.35,
                                                     "chain": None, "ckpt_path": "/x/dora.ckpt"})
    depth, req = calls["hold"][0]
    T = math.ceil(40 * 44100 / 4096)
    assert depth.shape == (T,) and np.allclose(depth, 0.35)
    assert req["ckpt_path"] == "/x/dora.ckpt" and req["seed"] >= 0
    assert Path(res["files"][0]).is_file() and res["meta"]["depth_max"] == pytest.approx(0.35)
    assert progress.snapshot() is None


def test_run_a2a_clip_envelope(rig):
    srv, calls = rig
    J.run_a2a_clip(srv, FakeSvc(), "forge-t", {"audio": REF_A, "render": {"prompt": "acid"}, "envelope": ENV})
    depth = calls["hold"][0][0]
    assert depth[0] == pytest.approx(0.2) and depth.max() == pytest.approx(0.6)


def inpaint_payload(**kw):
    p = {"a": {"audio": REF_A, "start_sec": 0.0, "offset_sec": 0.0, "dur_sec": 20.0},
         "b": {"audio": REF_B, "start_sec": 16.0, "offset_sec": 0.0, "dur_sec": 20.0},
         "region": {"start_sec": 16.0, "end_sec": 20.0}, "curve": ENV, "chroma_xfade": True,
         "render": {"prompt": "blend", "steps": 12}, "pad_sec": 8.0}
    p.update(kw)
    return p


def test_validate_inpaint():
    v = J.validate_inpaint(inpaint_payload())
    assert (v["span_start"], v["span_end"]) == (8.0, 28.0)
    with pytest.raises(ForgeError):
        J.validate_inpaint(inpaint_payload(region={"start_sec": 20.0, "end_sec": 16.0}))
    with pytest.raises(ForgeError) as e:
        J.validate_inpaint(inpaint_payload(region={"start_sec": 0.0, "end_sec": 180.0}))
    assert "capped at 184 s" in e.value.message


def test_run_inpaint_preview_shifts_to_span(rig):
    srv, calls = rig
    res = J.run_inpaint_preview(srv, FakeSvc(), "forge-t", inpaint_payload())
    regions, target = calls["inpaint"][0]
    assert regions == [(8.0, 12.0)]
    T = math.ceil(20 * 44100 / 4096)
    assert target.shape == (384, T)
    assert res["meta"]["span_start_sec"] == 8.0 and res["meta"]["op"] == "inpaint"


def test_submit_validation_for_new_ops(monkeypatch, tmp_path):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import explorer_render_server as srv
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    for k, v in HEADS.items():
        monkeypatch.setitem(srv.HEADS, k, v)
    forge_api.reset_queue()
    c = fastapi_testclient.TestClient(srv.app)
    bad_commit = commit_payload()
    bad_commit["duration_sec"] = 500
    for op, body in (("commit", bad_commit), ("a2a_clip", {"noise_level": 0.3}),
                     ("inpaint", inpaint_payload(pad_sec=100))):
        r = c.post("/forge/jobs", json={"op": op, "payload": body})
        assert r.status_code == 400, (op, r.text)
```

- [ ] **Step 2: Run to verify failure** — `$PY -m pytest eval/tests/test_forge_clip_jobs.py -q` → module not found.

- [ ] **Step 3: Implement `eval/forge/clip_jobs.py`**

```python
"""Per-clip A2A and single-overlap inpaint preview jobs (spec §6.7, §6.8)."""
import time

import numpy as np
import torch

from . import passes, progress
from .chroma import chroma_384
from .contract import FPS, HOP, SR, ForgeError, check_cap, latent_frames
from .envelope import sample_envelope, validate_envelope
from .lanes import place_lanes, place_single
from .overlap import chroma_target, region_frames
from .render_settings import _num, chain_to_request, parse_chain, parse_render, to_request

_LANES = [{"index": i, "muted": False, "solo": False, "gain": 1.0} for i in range(4)]


def _seed(srv, render):
    return int(render["seed"]) if render["seed"] >= 0 else int(srv.resolve_seed(-1))


def _save(srv, jd, z, n_samples):
    wav, zp = jd / "out_00.wav", jd / "out_00.z0.npy"
    srv.save_audio(wav, passes.decode_latent(srv, z, n_samples), SR, normalize=True)
    np.save(zp, z.squeeze(0).to(torch.float16).numpy())
    return wav, zp


def validate_a2a_clip(payload, heads):
    if not isinstance(payload, dict) or not isinstance(payload.get("audio"), dict):
        raise ForgeError(400, "a2a_clip needs an audio AudioRef object")
    env = payload.get("envelope")
    chain = parse_chain(payload.get("chain"))
    chain_to_request(chain, heads)
    ckpt = payload.get("ckpt_path")
    if ckpt is not None and not isinstance(ckpt, str):
        raise ForgeError(400, "ckpt_path must be a string or null")
    return {"audio": payload["audio"], "render": parse_render(payload.get("render")),
            "envelope": None if env is None else validate_envelope(env),
            "noise_level": _num(payload.get("noise_level", 0.4), 0, 1, "noise_level"),
            "chain": chain, "ckpt_path": ckpt or None}


def run_a2a_clip(srv, svc, job_id, payload):
    v = validate_a2a_clip(payload, srv.HEADS)
    seed = _seed(srv, v["render"])
    progress.begin(job_id, "a2a_clip", v["render"]["steps"])
    try:
        t0, warnings = time.time(), []
        audio = svc.load_audio(svc.resolve_audio(v["audio"]))
        duration = check_cap(audio.shape[1] / SR, "a2a_clip")
        T = latent_frames(duration)
        buf = np.zeros((2, T * HOP), dtype=np.float32)
        buf[:, :audio.shape[1]] = audio
        z = svc.encode_cached(buf)[..., :T].float()
        depth = (sample_envelope(v["envelope"], T) if v["envelope"] is not None
                 else np.full(T, v["noise_level"], dtype=np.float32))
        req = {**to_request(v["render"], seed), **chain_to_request(v["chain"], srv.HEADS)}
        if v["ckpt_path"] and not req.get("dora"):
            req["ckpt_path"] = v["ckpt_path"]
        out_id, jd = srv.new_job("forgea2a")
        z_new = passes.run_hold_pass(srv, z, depth, req, warnings, label="a2a_clip")
        wav, zp = _save(srv, jd, z_new, audio.shape[1])
        meta = {"op": "a2a_clip", "latents": [str(zp)], "depth_max": float(depth.max()) if depth.size else 0.0,
                "duration_sec": round(duration, 3)}
        return srv.build_response(out_id, jd, [wav], seed, t0, {}, warnings, meta, payload, False)
    finally:
        progress.end()


def _side(obj, what):
    if not isinstance(obj, dict) or not isinstance(obj.get("audio"), dict):
        raise ForgeError(400, f"inpaint.{what} needs an audio AudioRef object")
    return {"audio": obj["audio"], "start_sec": _num(obj.get("start_sec"), 0, 1e5, f"{what}.start_sec"),
            "offset_sec": _num(obj.get("offset_sec", 0.0), 0, 1e5, f"{what}.offset_sec"),
            "dur_sec": _num(obj.get("dur_sec"), 1e-3, 1e5, f"{what}.dur_sec")}


def validate_inpaint(payload):
    if not isinstance(payload, dict):
        raise ForgeError(400, "inpaint payload must be an object")
    region = payload.get("region") or {}
    rs = _num(region.get("start_sec"), 0, 1e5, "region.start_sec")
    re_ = _num(region.get("end_sec"), 0, 1e5, "region.end_sec")
    if not rs < re_:
        raise ForgeError(400, "region start_sec < end_sec required")
    pad = _num(payload.get("pad_sec", 8.0), 0, 60, "pad_sec")
    span_start, span_end = max(0.0, rs - pad), re_ + pad
    check_cap(span_end - span_start, "inpaint")
    chroma = payload.get("chroma_xfade", True)
    if not isinstance(chroma, bool):
        raise ForgeError(400, "chroma_xfade must be true or false")
    return {"a": _side(payload.get("a"), "a"), "b": _side(payload.get("b"), "b"),
            "region": (rs, re_), "curve": validate_envelope(payload.get("curve")), "chroma_xfade": chroma,
            "render": parse_render(payload.get("render")), "span_start": span_start, "span_end": span_end}


def _shifted(side, cid, s0):
    start, offset, dur = side["start_sec"] - s0, side["offset_sec"], side["dur_sec"]
    if start < 0:
        offset, dur, start = offset - start, dur + start, 0.0
    return {"id": cid, "lane": 0, "start_sec": start, "offset_sec": offset, "dur_sec": max(dur, 1e-3), "loop": False}


def run_inpaint_preview(srv, svc, job_id, payload):
    v = validate_inpaint(payload)
    seed = _seed(srv, v["render"])
    progress.begin(job_id, "inpaint", v["render"]["steps"])
    try:
        t0, warnings = time.time(), []
        s0 = v["span_start"]
        duration = v["span_end"] - s0
        T = latent_frames(duration)
        n = T * HOP
        clips = [_shifted(v["a"], "a", s0), _shifted(v["b"], "b", s0)]
        audio = {"a": svc.load_audio(svc.resolve_audio(v["a"]["audio"])),
                 "b": svc.load_audio(svc.resolve_audio(v["b"]["audio"]))}
        rs, re_ = v["region"][0] - s0, v["region"][1] - s0
        ov = {"lane": 0, "start_sec": rs, "end_sec": re_, "a_id": "a", "b_id": "b", "curve": v["curve"]}
        buf = place_lanes(clips, _LANES, [ov], n, SR, lambda c: audio[c["id"]])[0]
        if buf is None:
            raise ForgeError(400, "both clips fall outside the inpaint span")
        z = svc.encode_cached(buf)[..., :T].float()
        target = None
        if v["chroma_xfade"]:
            c_a = chroma_384(place_single(clips[0], n, SR, audio["a"]), SR, T)
            c_b = chroma_384(place_single(clips[1], n, SR, audio["b"]), SR, T)
            f0, f1 = region_frames(rs, re_, FPS, T)
            target = chroma_target(c_a, c_b, f0, f1, v["curve"])
        out_id, jd = srv.new_job("forgeinpaint")
        z_new = passes.run_inpaint_pass(srv, z, [(rs, re_)], to_request(v["render"], seed), warnings,
                                        chroma_target=target, label="inpaint")
        wav, zp = _save(srv, jd, z_new, int(round(duration * SR)))
        meta = {"op": "inpaint", "latents": [str(zp)], "span_start_sec": round(s0, 4),
                "span_end_sec": round(v["span_end"], 4)}
        return srv.build_response(out_id, jd, [wav], seed, t0, {}, warnings, meta, payload, False)
    finally:
        progress.end()
```

- [ ] **Step 4: Register the runners in `eval/forge_api.py`**

At the end of `bind(srv)`, before `reset_queue()`, add:
```python
    from forge import clip_jobs, commit as commit_mod
    register_runner("a2a_clip", lambda jid, p: clip_jobs.run_a2a_clip(SRV, services(), jid, p),
                    validator=lambda p: clip_jobs.validate_a2a_clip(p, SRV.HEADS))
    register_runner("inpaint", lambda jid, p: clip_jobs.run_inpaint_preview(SRV, services(), jid, p),
                    validator=clip_jobs.validate_inpaint)
    register_runner("commit", lambda jid, p: commit_mod.run_commit(SRV, services(), jid, p),
                    validator=lambda p: commit_mod.validate_commit(p, SRV.HEADS))
```

- [ ] **Step 5: Run the forge suite**

Run: `$PY -m pytest eval/tests/test_forge_*.py -q`
Expected: all passed.

- [ ] **Step 6: Commit** — `git add eval/forge/clip_jobs.py eval/forge_api.py eval/tests/test_forge_clip_jobs.py`; `Misc/agent_commit.sh WINTERMUTE -m "forge: a2a_clip and inpaint preview jobs; register a2a_clip/inpaint/commit"`.

---

### Task 11: GPU smoke and fixtures (live dev server)

**Files:** Create `eval/forge/smoke_commit.py`; fixtures `docs/latent-forge/contract/fixtures/forge_job_{a2a_clip,inpaint,commit}_done.json`.

**Interfaces:**
- Consumes: the live `/forge/jobs` API from Tasks 1–10 (server started with the fork worktree on `PYTHONPATH`).
- Produces: a pass/fail report covering the hold on the plain, pingpong and LatCH-guided samplers (risk R1), the inpaint preview, a full commit, and the three fixtures the client plans expect.

- [ ] **Step 1: Write `eval/forge/smoke_commit.py`**

```python
"""GPU smoke for the M8 jobs against the LIVE dev server.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/forge/smoke_commit.py
Prints ALL SMOKE CHECKS PASSED or a list of failures; writes three redacted fixtures.
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
FAIL = []


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def job(op, payload, fixture=None):
    s, sub = call("POST", "/forge/jobs", {"op": op, "payload": payload})
    if s != 202:
        raise AssertionError(f"{op} submit {s}: {sub}")
    while True:
        _, rec = call("GET", f"/forge/jobs/{sub['job_id']}")
        if rec["state"] in ("done", "error"):
            break
        time.sleep(2)
    if fixture:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / f"{fixture}.json").write_text(json.dumps({"status": 200, "body": redact(rec)}, indent=1) + "\n")
    if rec["state"] != "done":
        raise AssertionError(f"{op} failed: {rec['error']}")
    return rec["result"]


def check_audio(res, what):
    wav = OUT / res["job_id"] / Path(res["files"][0]).name
    y, _ = sf.read(wav)
    z = np.load(res["latents"][0]).astype(np.float32)
    if not (np.all(np.isfinite(y)) and np.all(np.isfinite(z))):
        FAIL.append(f"{what}: non-finite output")
    if float(np.std(y)) < 1e-4 or abs(float(np.max(np.abs(y))) - 1.0) < 1e-6:
        FAIL.append(f"{what}: silent or DC output")
    return z


def ref(res):
    return {"kind": "render", "job_id": res["job_id"], "file": Path(res["files"][0]).name}


def region_diff(za, zb, lo, hi):
    return float(np.mean(np.abs(za[:, lo:hi] - zb[:, lo:hi])))


def main():
    g1 = job("generate", {"prompt": "hypnotic melodic goa trance, rolling bassline", "duration": 20.0,
                          "steps": 16, "seed": 21})
    g2 = job("generate", {"prompt": "acid techno, squelchy 303 lead", "duration": 20.0, "steps": 16, "seed": 22})
    base = {"audio": ref(g1), "render": {"prompt": "psychedelic acid lead", "steps": 16, "seed": 5}}
    flat0 = {"points": [0, 0, 0, 0], "curves": [0, 0, 0]}
    graded = {"points": [0.05, 0.05, 0.9, 0.9], "curves": [0, 0, 0]}

    z_zero = check_audio(job("a2a_clip", {**base, "envelope": flat0}), "a2a_clip zero envelope")
    T = z_zero.shape[1]
    third = (T - 1) // 3
    latch_chain = {"latch_on": True, "slots": [
        {"head": "rms_energy_bass", "kind": "constant", "value": -12.0, "weight": 1.0, "start_pct": 0.0, "end_pct": 0.6},
        {"head": "none", "kind": "constant", "value": 0.0, "weight": 1.0, "start_pct": 0.0, "end_pct": 0.6}]}
    for label, extra in (("euler", {}), ("pingpong", {"render": {**base["render"], "sampler_type": "pingpong"}}),
                         ("guided", {"chain": latch_chain})):
        res = job("a2a_clip", {**base, **extra, "envelope": graded},
                  fixture="forge_job_a2a_clip_done" if label == "euler" else None)
        z = check_audio(res, f"a2a_clip {label}")
        low = region_diff(z, z_zero, 0, third)
        high = region_diff(z, z_zero, T - third, T)
        if not high > 0:
            FAIL.append(f"{label}: high-noise region did not change")
        elif low / high > 0.3:
            FAIL.append(f"{label}: hold ineffective (low/high diff ratio {low / high:.2f}) — R1")

    inp = job("inpaint", {"a": {"audio": ref(g1), "start_sec": 0.0, "offset_sec": 0.0, "dur_sec": 20.0},
                          "b": {"audio": ref(g2), "start_sec": 16.0, "offset_sec": 0.0, "dur_sec": 20.0},
                          "region": {"start_sec": 16.0, "end_sec": 20.0},
                          "curve": {"points": [0, 0.33, 0.66, 1], "curves": [0, 0, 0]}, "chroma_xfade": True,
                          "render": {"prompt": "goa trance transition", "steps": 16, "seed": 9}, "pad_sec": 8.0},
              fixture="forge_job_inpaint_done")
    check_audio(inp, "inpaint preview")
    if inp["meta"].get("span_start_sec") != 8.0:
        FAIL.append(f"inpaint span_start_sec {inp['meta'].get('span_start_sec')} != 8.0")

    lane = lambda i, chain=None: {"index": i, "muted": False, "solo": False, "gain": 1.0, "chain": chain}  # noqa: E731
    commit = {
        "project_bpm": 140.0, "duration_sec": 36.0, "defaults": {"prompt": "goa trance"},
        "lanes": [lane(0), lane(1, latch_chain), lane(2), lane(3)],
        "clips": [
            {"id": "c1", "lane": 0, "start_sec": 0.0, "offset_sec": 0.0, "dur_sec": 20.0, "loop": False,
             "audio": ref(g1), "native_bpm": None, "detune_cents": 0, "a2a": None},
            {"id": "c2", "lane": 0, "start_sec": 16.0, "offset_sec": 0.0, "dur_sec": 20.0, "loop": False,
             "audio": ref(g2), "native_bpm": None, "detune_cents": 0, "a2a": None},
            {"id": "c3", "lane": 1, "start_sec": 8.0, "offset_sec": 0.0, "dur_sec": 20.0, "loop": False,
             "audio": ref(g2), "native_bpm": None, "detune_cents": 0,
             "a2a": {"render": {"prompt": "rolling psy bassline", "steps": 16, "seed": 3},
                     "envelope": {"points": [0.3, 0.3, 0.3, 0.3], "curves": [0, 0, 0]}}},
        ],
        "overlaps": [{"key": "c1-c2", "lane": 0, "start_sec": 16.0, "end_sec": 20.0, "a_id": "c1", "b_id": "c2",
                      "curve": {"points": [0, 0.33, 0.66, 1], "curves": [0, 0, 0]}, "chroma_xfade": True,
                      "render": {"prompt": "goa trance transition", "steps": 16, "seed": 9}}],
        "mix": {"order": "tree", "nodes": {k: {"interp": "slerp", "t": 0.5} for k in ("M1", "M2", "MX")},
                "quad_weights": [1, 1, 1, 1]},
        "master": {"latch_on": True, "head": "rms_energy_bass", "gain": 32, "norm_on": True},
        "decode_lanes": True,
    }
    res = job("commit", commit, fixture="forge_job_commit_done")
    check_audio(res, "commit mix")
    meta = res["meta"]
    if [p["kind"] for p in meta["passes"]] != ["a2a", "inpaint"]:
        FAIL.append(f"commit passes {meta['passes']}")
    if [s["on"] for s in meta["stages"]] != [False, False, True, True, True, True, True, True, True]:
        FAIL.append(f"commit stage flags {[s['on'] for s in meta['stages']]}")
    if len(res["files"]) != 3:
        FAIL.append(f"commit files {res['files']} (expected mix + 2 lane wavs)")

    print("FAILURES:" if FAIL else "ALL SMOKE CHECKS PASSED")
    for f in FAIL:
        print("  -", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it (swaps the resident server)**

```bash
cd /home/kim/Projects/SAO && Misc/gpu_guard.sh who WINTERMUTE
cd /home/kim/Projects/sa3-studio-review
eval/forge/dev_server.sh stop || true
eval/forge/dev_server.sh start
$PY eval/forge/smoke_commit.py
```
Expected: `ALL SMOKE CHECKS PASSED`. If only the R1 line fails for `guided`, the LatCH sampler is not honouring in-place callback edits on this fork revision: add a `hold_fn` argument to `sample_flow_euler_multi_latch_guided` in the fork (applied to `x` right after the Euler update), thread it from `_latch_guided_generate`, test it the Task 1 way, push to `fork`, and re-run. If a pingpong line fails, report BLOCKED with the output.

- [ ] **Step 3: Listen** — play the commit's `mix.wav` and `lane0.wav` (the path is in `forge_job_commit_done.json`, `result.files`). Note in the final report whether the chroma-crossfaded seam at 16–20 s is audible; `SPLICE_XFADE_FRAMES` is the knob. Slerp-vs-lerp and seam quality are Kim's call by ear — do not change defaults from this listen.

- [ ] **Step 4: Leak scan and commit**

```bash
grep -rn -e '/home/kim' -e '/run/media/kim' docs/latent-forge/contract/fixtures && echo LEAK || echo clean
git add eval/forge/smoke_commit.py docs/latent-forge/contract/fixtures/forge_job_a2a_clip_done.json docs/latent-forge/contract/fixtures/forge_job_inpaint_done.json docs/latent-forge/contract/fixtures/forge_job_commit_done.json
Misc/agent_commit.sh WINTERMUTE -m "forge: M8 GPU smoke (hold on euler/pingpong/guided, inpaint, commit) + fixtures"
```

- [ ] **Step 5: Report a pre-existing issue found while planning** (do not fix it here): `/a2a_mix` passes its chroma-morph `target_raw` at the composite's frame length `Tz`, while `generate()` runs on `_adapt_sample_size(...)` frames (duration + 6 s padding, aligned). The guided sampler linearly resamples the target over the whole window, so the morph is stretched by roughly `(Tz + pad)/Tz` and lands late relative to the audio. Post it to the dialogue as a finding for whoever owns chroma-morph transitions, with the file and line (`explorer_render_server.py`, the `target = np.concatenate(...)` block in `_a2a_mix_impl`).

- [ ] **Step 6: Hand the GPU back** — `eval/forge/dev_server.sh stop` unless M9 integration testing follows immediately.
