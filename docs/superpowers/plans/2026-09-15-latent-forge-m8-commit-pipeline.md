# Latent Forge M8 — Commit pipeline (server) Implementation Plan

> **STATUS 2026-09-15: IN PROGRESS — Tasks 1–4 written; Tasks 5–10 (hold/splice, overlap targets, GPU passes, commit orchestration, job runners, GPU smoke) follow in the next commit.**

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
| `eval/forge_api.py` (modify) | register the three runners in `bind` |
| `eval/forge/smoke_commit.py` | GPU smoke + fixtures |
| `eval/tests/test_forge_{render_settings,lanes,mixing,holdpass,overlap,passes,commit,clip_jobs}.py` | tests |

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
