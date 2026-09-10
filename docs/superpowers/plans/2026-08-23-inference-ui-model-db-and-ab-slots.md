# Inference UI: multi-root model database + resident A/B slots — Implementation Plan

> **STATUS 2026-08-26 (C): ALL TASKS 1–9 DONE, nothing committed.** Tasks 1–4 landed 2026-08-25;
> 5–9 the same day Kim said "go ahead with the model.py edit, then A/B slots".
> Two of the plan's VRAM numbers were **measured and corrected**: an r128 DoRA costs **0.40 GB**,
> not 0.33 (the estimate counted adapter tensors and missed the per-module parametrization
> bookkeeping), and medium-base leaves **7.40 GB free**, so the baseline is ~8.5 GB rather than the
> assumed ~5.1 — which means ~3 resident adapters above the 6.0 GB floor, not 4+.
> `remove_lora_by_index` + reload was verified to revert the base weights exactly (max drift 0.0),
> the claim Step 5 said must not be taken on trust.
> **A bug the plan did not anticipate, found by testing the control arm:** a `slot: null` render
> came back BYTE-IDENTICAL to the previous slot-0 render — "base model" was quietly still the last
> adapter, because `ACTIVE_SLOT` kept its value outside slot mode. Same failure class as trap 1,
> now fixed and pinned by a test.
> Task 8 shipped as specified plus two things the plan did not anticipate: root options are marked
> `— DRIVE NOT MOUNTED` and the DoRA picker disables adapters on an absent drive (measured with
> Mantu unplugged: 692 of 797 adapters were being offered unloadable), and the model-info panel
> renders a dict-valued `recipe` one field per line rather than as a Python repr. The pickers also
> moved off fire-once `Input(<id>,"id")` onto a shared 5 s poller — that was the KNOWN BUG in
> `docs/INFERENCE-SURFACE.md`, now verified fixed without a page reload.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the SA3 inference UI reach over every trained checkpoint we own (multi-root, removable-drive-tolerant), a real model database behind the picker, and A/B switching between models with no offload and no reload.

**Architecture:** Three new importable modules under `SAO/eval/` (`model_roots.py`, `ckpt_probe.py`, `model_db.py`, plus `adapter_slots.py`), consumed by the EXISTING render server `SAO/eval/explorer_render_server.py` (:8056) through new endpoints, and by the EXISTING Dash viewer (mir branch `sa3-latent-explorer`) through the EXISTING `render_client.py`. No new renderer, no second guidance implementation — the A/B endpoint is a loop over the server's own `_generate` body. The A/B mechanism is the multi-LoRA support that ALREADY exists in the SA3 fork (`load_lora` assigns `lora_index=i`; `dit.py` gates per-index each step) — we are wiring it up, not inventing it.

**Tech Stack:** Python 3.13, FastAPI (server, `SAO/.venv`), Dash 2.x (viewer, mir venv), PyTorch 2.14/ROCm 7.15, `stable_audio_3` thin fork.

**Spec:** `docs/INFERENCE-SURFACE.md` (§0 the hard constraint, §2 model families, §9 "NEEDS BUILDING" items 1 + 6 + 6b). Kim's ask, verbatim: *"maybe just allow several root folders and build a database of models. How are with vram? could we keep two models or at least DoRAs in memory and allow A/B tests without offloading?"*

---

## Global Constraints

- **HARD: extend the :8056 endpoint set or write a thin client of it.** Never build a parallel renderer or a second guidance implementation. `resolve_latch()` NORMALISES gains (`rho = mu = first slot's gain`, per-slot `weight = slot_gain / g0`) — a raw `weight` from anywhere else is a different scale. (`docs/INFERENCE-SURFACE.md` §0.)
- **NO hardcoded drive paths in code.** Every filesystem root comes from a JSON config. Drives are removable and the eval drive mounts as `Mantu` OR `Mantu1` depending on mount order — resolve by probing a marker subdirectory (the generalisation of `explorer_render_server.py:_mantu_root()`, lines 73–81). (Standing project rule; C bug 2026-07-13.)
- **Venv-per-task.** Server + all `SAO/eval/*` code and tests: `/home/kim/Projects/SAO/.venv/bin/python`. Viewer code (`mir/plots/explorer_sa3/*`): `/home/kim/Projects/mir/bin/python`. Invoke by absolute path; never assume `python`.
- **`export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before any `import torch`** in a shell that will touch the GPU. Never set `HIP_VISIBLE_DEVICES=""`.
- **GPU sharing.** A non-team instance shares this GPU via `/tmp/gpu.lock`. Check it and `rocm-smi --showpids` before any test that allocates VRAM. All unit tests in this plan are CPU-only; GPU tests are explicitly marked and opt-in.
- **Backward compatibility is a requirement, not a nicety.** `GET /ckpts` called with no params must return a byte-identical response shape to today. A `dora` payload with no `slot` key must take today's code path. A missing config file must produce today's single-root behaviour.
- **Two checkpoint naming conventions exist.** `epoch=<N>-step=<M>.ckpt` (fat) / `.weights.ckpt` (slim) AND `riffer_final.pt` / `riffer_step<N>.pt` (control runs). A glob for `epoch=*.ckpt` finds ZERO control arms. (`docs/INFERENCE-SURFACE.md` §2.)
- **Repo/branch:** SAO on branch `sa3-style-adapter`; mir on branch `sa3-latent-explorer`. Commit to those branches.

---

## Discovery findings this plan is built on (read before starting)

Verified by reading code and disk on 2026-08-23. **Do not re-derive these.**

**A model database already exists — do not build a second one.**
`model_index.md` (repo root, 4358 lines) is generated by `Misc/build_model_index_page.py` from
`~/.cache/evals_aac/model_matrix/manifest_live.jsonl` joined to `Misc/models_index_overrides.json`.
It holds **377 board labels → 309 distinct trained models across 71 families**, each with a stable
ID (`M-XD7Y0P`), a real recipe extracted from the checkpoint, a plain-language "why it was made",
comparison targets, and Kim's by-ear verdicts. `Misc/extract_recipes.py` already does
checkpoint-reading recipe extraction (`lora_config`, optimizer param_groups, epoch/step, kind
detection) into `eval/extracted_recipes.staging.json` (144 entries).
**What is missing is not a database — it is a database KEYED BY CHECKPOINT PATH and served over
HTTP.** `extract_recipes.py` keys by *label* and records only the ckpt basename; the picker needs
`abs path → record`. This plan builds that join layer and reuses everything above as inputs.
It also fixes `Misc/extract_recipes.py:30` `DEFAULT_ROOT = "/run/media/kim/Mantu/sa3_lora_runs"`,
a hardcoded drive path that violates the standing rule.

**Multi-adapter residency already works in the fork.** `stable_audio_3/model.py:72 load_lora(paths)`
takes a **list** and `models/lora/loader.py:75` assigns `lora_index=i` from `enumerate(paths)`.
`set_lora_strength(s, lora_index=i)`, `enable_lora(m, lora_index=i)`, `disable_lora(m, lora_index=i)`
and `remove_lora_by_index(m, i)` all exist and are exported from `stable_audio_3.models.lora`.
`models/dit.py:472-486` gates per-index **inside the forward, every step**, from the
`lora_configs=[{"lora_index": i, "interval": (lo, hi), "layer_filter": str}]` kwarg.
⇒ A/B between adapters is a strength/interval flip, not a load.

**Two traps in that mechanism, both easy to miss and both silently wrong:**
1. `dit.py` only touches indices that appear in `lora_configs`. An index NOT in the list keeps
   whatever enable/disable state it had last → an "A vs B" render can silently be "A+B". The
   contract must be: **always pass a full `lora_configs` covering every resident index.**
2. `load_and_apply_loras` re-indexes from 0 on every call, so calling `load_lora([new])` a second
   time collides with index 0. **Incremental adds are unsafe.** Changing the resident SET must go
   through `remove_lora_by_index` for every existing index, then one `load_lora(full_new_list)`.
   *Switching between* already-resident adapters costs nothing.

**`explorer_render_server.py:388-393 with_lora_interval()` hardcodes `"lora_index": 0`.** It must be
generalised or a second slot will never be gated.

**Measured VRAM facts** (`rocm-smi`, HF blob sizes, `zipfile` header reads — all verified today):

| item | measurement | source |
|---|---|---|
| card VRAM total | **17.096 GB** | `rocm-smi --showmeminfo vram` |
| in use at rest (desktop + other) | 1.44 GB | same |
| `medium-base` safetensors | **9.222 GB fp32** = DiT 1.4 B + SAME-L 852 M ≈ 2.31 B params | HF blob |
| T5-Gemma `t5gemma-b-b-ul2` | **1.183 GB fp32** ≈ 295 M params | HF blob (from the `medium` repo) |
| server load precision | **half** — `StableAudioModel.from_pretrained(..., model_half=True)` is the default and the server does not override it | `model.py:39`, `explorer_render_server.py:1657` |
| DoRA r128 slim ckpt | **666.4 MB fp32**, 229 modules × (lora_A, lora_B, magnitude), `FloatStorage` | `zipfile` read of `bf16_twin/.../epoch=0-step=299.weights.ckpt` |
| DoRA r64 slim ckpt | 319 MB fp32 | `eval/extracted_recipes.staging.json` |
| full-FT slim ckpt | **4611 MB fp32** | `fullft/fullft_goa_t512/epoch=7-step=10800.weights.ckpt` |
| full-FT fat ckpt | up to **44.1 GB** (precision_ladder fp32, with optimizer state) | `find -printf %s` |
| host RAM | 93 GB total, **72 GB available** | `free -g` |

**Where the checkpoints actually are** (verified `ls`, 2026-08-23):

| root | contents | note |
|---|---|---|
| `<MANTU>/sa3_lora_runs` | 162 entries — today's `CKPT_SCAN_ROOT` | older local DoRA runs |
| `<UUID>/lumi_runs/runs` | **14 families**, 412 `.ckpt` (322 slim / 90 fat), **62 `run_meta.json`** | `adamw_bf16_sweep bf16_twin fp32_compare fp32_frames fp32_winning fullft headb_melody longctx_t1024_r128 longctx_t2048_r128 precision_ladder sanity16_dora sanity16_lora smoke_r256_a256_lr1e4_f512_bs8 subspace_loss_v3sel_grid_mt` |
| `<MANTU>/lumi_runs/runs/runs` | **23 families**, 0 `run_meta.json` | ARCHITECTURE.md calls this "an early **partial** LUMI grab, **superseded** — see UUID drive". Overlapping family names ⇒ must be deduped and ranked BELOW the UUID drive. |
| `<MANTU>/sa3_control_runs` | `riffer_*.pt` control adapters | invisible to an `epoch=*.ckpt` glob |

⚠️ **Correction to the brief:** the families `dorlor_ab` (32 arms), `lr5e5_allsets`,
`fullft_avp_subloss`, `subloss_k24`, `winning_fleet`, `fullft_fleet` are **NOT on either mounted
drive** under those names (only `<UUID>/lumi_runs/renders/dorlor_ab`, which is renders, not
checkpoints). They are presumably still on LUMI `/scratch` — which is under a purge deadline
(memory: purged ~a few weeks after 2026-08-07). **Raise this with Kim as a separate item; it is a
data-recovery question, not a UI question.** The design below tolerates their later arrival: adding
a root is a config edit, not a code change.

**`run_meta.json` shape is NOT uniform** — two variants live side by side and both must parse:
- reconstructed style (`longctx_t1024_r128/run_meta.json`): `purpose`, `hypothesis`,
  `reconstructed_by`, `provenance`, nested `training: {model, adapter, dora_rank, dora_alpha,
  optimizer, lr, base_precision, crop_frames, crop_seconds, corpus, n_files, seed,
  terminal_epoch, terminal_global_step}`, `checkpoints: {...}`, `task`, `status`, `kim_feedback`.
- launch-time style (`sanity16_lora/suomi/run_meta.json`): `run`, `created`, `slurm_job`,
  `purpose`, `hypothesis`, `dataset: {name, latents, ...}`, `recipe: {adapter, rank, alpha, lr,
  batch_size, frames, epochs, optimizer, precision}`, `script`, `result`, `kim_feedback`.
Some are reconstructions (`"reconstructed_by": "CONTINUITY-subagent 2026-08-04 from ckpt args"`),
so **every DB field must record where it came from** — a reconstructed `lr: null` is not the same
claim as a launch-time `lr: "1e-4"`.

**`.mmline.json` sidecar shape** (verified):
`{"model", "ckpt", "cfg", "strength", "prompt_id", "prompt_text", "seed", "steps", "duration", "duration_mode", "file"}`.

---

## VRAM budget and the A/B recommendation

Working budget: **17.096 − 1.44 ≈ 15.6 GB** for the render server. If the latent player (:7892,
a separate process holding SAME-L) is also up, subtract a further ~1.7–3.4 GB — the slot manager
must read live free VRAM rather than assume.

**Baseline resident (half precision): ~5.1 GB** — DiT ~2.8 + SAME-L ~1.7 + T5-Gemma ~0.6.
**Headroom for activations: ~10.5 GB.**

| option | what it means | extra VRAM | switch cost | verdict |
|---|---|---|---|---|
| **A — two backbones resident** | a second `StableAudioModel.from_pretrained` | **+5.1 GB** (→ 10.2 GB weights, ~5.4 GB headroom) | ~0 | ✗ **Rejected.** A 380 s / T4096 render under CFG will not fit reliably in 5.4 GB. Sharing SAME + conditioner across two DiTs would cut it to +2.8 GB but needs surgery inside `load_diffusion_cond` — a fork change for a case Option C already serves. |
| **B — one base + N adapters resident** | `load_lora([a, b, c, d])`, flip strengths | **+0.33 GB per r128 DoRA** (+0.16 GB per r64). 4 slots ≈ **1.3 GB** → 6.4 GB weights, ~9.2 GB headroom | **~0 (milliseconds)** — `set_lora_strength(0, idx)` + `lora_configs` | ✓ **RECOMMENDED.** Costs 2.5% of the card per extra model. Mechanism already exists and is already honoured by the sampler. Limited to adapters on a shared base. |
| **C — full-FT states pinned in HOST RAM** | keep N full-FT `state_dict`s on CPU, `load_state_dict` into the resident DiT to switch | **+0 GB VRAM**; 4.6 GB host RAM per fp32 state (2.3 GB if cast to half at pin time) | ~2–4 s (host→device copy, no disk read) | ✓ **RECOMMENDED for full-FT A/B**, which cannot be a slot. 72 GB host RAM available — this is nearly free. |

**Recommendation, with numbers: implement B for adapters and C for full-FT.** Together they cover
every family in the picker at a combined worst case of ~6.4 GB resident weights and ~9.2 GB
activation headroom — *more* headroom than today's design leaves after a rebuild, because
rebuild-per-switch currently re-reads 9.2 GB from disk and transiently double-allocates.

**Enforcement:** a configured `vram_floor_gb` (default **6.0**) checked against
`torch.cuda.mem_get_info()` before any slot add. Refuse the add with a clear message rather than
OOM mid-render. Default `max_resident_adapters = 4`; setting it to `1` reproduces today's exact
behaviour.

---

## File Structure

**New — `SAO/eval/` (server side, `SAO/.venv`):**

| file | responsibility |
|---|---|
| `eval/model_roots.json` | THE config. Logical mounts (candidates + marker dir) and checkpoint roots (`${MOUNT}`-templated path, priority, enabled). The only place a drive path is written. |
| `eval/model_roots.py` | Load the config; resolve mounts by probing markers; expand `${MOUNT}` templates; return `Root` records with `available`. ~120 lines. |
| `eval/ckpt_probe.py` | Classify ONE checkpoint file with no torch load and no GPU: family, rank/alpha, epoch/step, `control_mode`, slim-vs-fat. Reads the zip's `data.pkl` member / the safetensors JSON header only. ~150 lines. |
| `eval/model_db.py` | Assemble the database: scan roots → probe → walk up for `run_meta.json` → join `Misc/models_index_overrides.json` → stable ids → journal cache. Query/filter API. ~280 lines. |
| `eval/adapter_slots.py` | The resident-slot table: VRAM accounting, `set_slots`, `lora_configs_for(active)`, full-FT host-RAM pins. Pure logic + a thin model-touching layer so it is unit-testable without a GPU. ~220 lines. |
| `eval/test_model_roots.py`, `eval/test_ckpt_probe.py`, `eval/test_model_db.py`, `eval/test_adapter_slots.py` | CPU-only unit tests, tmp_path fixtures. |

**Modified — server:**

| file | change |
|---|---|
| `eval/explorer_render_server.py` | Replace `CKPT_SCAN_ROOT` literal with `model_roots`; extend `/ckpts`; add `/roots`, `/models`, `/models/{id}`, `GET+POST /slots`, `POST /ab`; generalise `with_lora_interval`; refactor `prepare_model` to consult the slot table. |
| `Misc/extract_recipes.py` | Replace hardcoded `DEFAULT_ROOT` with `model_roots` resolution (standing rule). |

**Modified — viewer (mir branch `sa3-latent-explorer`, mir venv):**

| file | change |
|---|---|
| `plots/explorer_sa3/render_client.py` | Add `roots()`, `models()`, `slots()`, `set_slots()`, `ab()`; extend `ckpts()` with `root_ids`. |
| `plots/explorer_sa3/inference_tab.py` | Root multi-select above the ckpt picker; DB-enriched option labels; a Model-info panel. |
| `plots/explorer_sa3/controls.py` | An "A/B slots" section in the shared steering panel; `steering_payload()` emits `dora.slot`. |

**Modified — docs (the discoverability rule):** `docs/INFERENCE-SURFACE.md`, `ARCHITECTURE.md`
(reuse index + doc map), `WORKLOG.md`, `KIM-TASKLIST.md`.

---

### Task 1: Mount + root resolution from config

**Files:**
- Create: `/home/kim/Projects/SAO/eval/model_roots.json`
- Create: `/home/kim/Projects/SAO/eval/model_roots.py`
- Test: `/home/kim/Projects/SAO/eval/test_model_roots.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass Root: id: str, label: str, path: str | None, priority: int, enabled: bool, available: bool, template: str, note: str`
  - `load_config(path: str | Path | None = None) -> dict`
  - `resolve_mounts(cfg: dict) -> dict[str, str | None]`
  - `expand(template: str, mounts: dict[str, str | None]) -> str | None`
  - `resolve_roots(cfg: dict | None = None) -> list[Root]` — sorted by `priority` descending
  - `DEFAULT_CONFIG_PATH: Path`

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_model_roots.py`:

```python
import json
from pathlib import Path

import pytest

import model_roots


def _cfg(tmp_path, mount_candidates, marker):
    return {
        "version": 1,
        "mounts": {"DRIVE": {"candidates": mount_candidates, "marker": marker}},
        "roots": [
            {"id": "runs", "label": "runs", "path": "${DRIVE}/runs", "priority": 20},
            {"id": "other", "label": "other", "path": "${DRIVE}/other", "priority": 10},
        ],
    }


def test_resolve_mounts_picks_the_candidate_carrying_the_marker(tmp_path):
    good = tmp_path / "Mantu1"
    (good / "sa3_lora_runs").mkdir(parents=True)
    bad = tmp_path / "Mantu"
    bad.mkdir()
    cfg = _cfg(tmp_path, [str(bad), str(good)], "sa3_lora_runs")
    assert model_roots.resolve_mounts(cfg) == {"DRIVE": str(good)}


def test_resolve_mounts_reports_none_when_no_candidate_is_mounted(tmp_path):
    cfg = _cfg(tmp_path, [str(tmp_path / "nope")], "sa3_lora_runs")
    assert model_roots.resolve_mounts(cfg) == {"DRIVE": None}


def test_expand_returns_none_for_an_unresolved_mount():
    assert model_roots.expand("${DRIVE}/runs", {"DRIVE": None}) is None
    assert model_roots.expand("${DRIVE}/runs", {"DRIVE": "/mnt/d"}) == "/mnt/d/runs"


def test_resolve_roots_marks_availability_and_sorts_by_priority(tmp_path):
    drive = tmp_path / "Mantu"
    (drive / "sa3_lora_runs").mkdir(parents=True)
    (drive / "runs").mkdir()
    cfg = _cfg(tmp_path, [str(drive)], "sa3_lora_runs")
    roots = model_roots.resolve_roots(cfg)
    assert [r.id for r in roots] == ["runs", "other"]
    assert roots[0].available is True and roots[0].path == str(drive / "runs")
    assert roots[1].available is False       # ${DRIVE}/other does not exist
    assert roots[1].path == str(drive / "other")


def test_disabled_roots_are_returned_but_flagged(tmp_path):
    drive = tmp_path / "Mantu"
    (drive / "sa3_lora_runs").mkdir(parents=True)
    (drive / "runs").mkdir()
    cfg = _cfg(tmp_path, [str(drive)], "sa3_lora_runs")
    cfg["roots"][0]["enabled"] = False
    roots = model_roots.resolve_roots(cfg)
    assert roots[0].enabled is False


def test_shipped_config_parses_and_declares_every_known_root():
    cfg = model_roots.load_config()
    ids = {r["id"] for r in cfg["roots"]}
    assert {"local_dora", "lumi_uuid", "lumi_mantu", "control"} <= ids
    for r in cfg["roots"]:
        assert r["path"].startswith("${"), f"{r['id']} must template a mount, not hardcode a drive"


def test_load_config_accepts_an_explicit_path(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"version": 1, "mounts": {}, "roots": []}))
    assert model_roots.load_config(p)["roots"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest test_model_roots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model_roots'`

- [ ] **Step 3: Write the config file**

Create `/home/kim/Projects/SAO/eval/model_roots.json`:

```json
{
  "version": 1,
  "_doc": "THE checkpoint-root config for the SA3 inference surface. Standing project rule: no drive paths in code. Drives are removable and the eval drive mounts as Mantu OR Mantu1 depending on mount order, so a mount is resolved by probing its marker subdirectory (generalisation of explorer_render_server._mantu_root). A root whose mount is absent stays listed with available=false and the picker serves its cached journal.",
  "mounts": {
    "MANTU": {
      "candidates": ["/run/media/kim/Mantu", "/run/media/kim/Mantu1"],
      "marker": "sa3_lora_runs"
    },
    "EVALUUID": {
      "candidates": ["/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d"],
      "marker": "lumi_runs"
    }
  },
  "roots": [
    {
      "id": "lumi_uuid",
      "label": "LUMI runs (UUID drive)",
      "path": "${EVALUUID}/lumi_runs/runs",
      "priority": 30,
      "enabled": true,
      "note": "14 families, 412 ckpts, 62 run_meta.json. The authoritative LUMI grab."
    },
    {
      "id": "local_dora",
      "label": "local DoRA runs",
      "path": "${MANTU}/sa3_lora_runs",
      "priority": 20,
      "enabled": true,
      "note": "162 entries. Was the pinned CKPT_SCAN_ROOT before multi-root."
    },
    {
      "id": "control",
      "label": "control adapters (riffer_*.pt)",
      "path": "${MANTU}/sa3_control_runs",
      "priority": 15,
      "enabled": true,
      "note": "control_mode adapters; invisible to an epoch=*.ckpt glob."
    },
    {
      "id": "lumi_mantu",
      "label": "LUMI runs (Mantu, partial/superseded)",
      "path": "${MANTU}/lumi_runs/runs/runs",
      "priority": 5,
      "enabled": true,
      "note": "23 families, no run_meta. ARCHITECTURE.md: an early PARTIAL grab, superseded by lumi_uuid. Ranked lowest so dedupe prefers the UUID copy."
    }
  ],
  "limits": {
    "max_resident_adapters": 4,
    "vram_floor_gb": 6.0
  }
}
```

- [ ] **Step 4: Write the module**

Create `/home/kim/Projects/SAO/eval/model_roots.py`:

```python
"""Mount + checkpoint-root resolution for the SA3 inference surface.

Standing project rule: NO drive paths in code. Everything comes from
eval/model_roots.json. Mounts are resolved by probing a marker subdirectory --
the generalisation of explorer_render_server._mantu_root(), which exists because
the eval drive mounts as Mantu or Mantu1 depending on mount order (C bug
2026-07-13). A root whose mount is absent is still returned, with
available=False, so callers can serve a cached journal instead of 404ing.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).with_name("model_roots.json")
_TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass
class Root:
    id: str
    label: str
    path: str | None          # expanded; None when the mount is unresolved
    priority: int
    enabled: bool
    available: bool           # path is not None AND is an existing directory
    template: str
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def load_config(path: str | Path | None = None) -> dict:
    """Read the roots config. Env SA3_MODEL_ROOTS overrides the default path."""
    p = Path(path or os.environ.get("SA3_MODEL_ROOTS") or DEFAULT_CONFIG_PATH)
    return json.loads(Path(p).read_text())


def resolve_mounts(cfg: dict) -> dict[str, str | None]:
    """Logical mount name -> the candidate that actually carries its marker."""
    out: dict[str, str | None] = {}
    for name, spec in (cfg.get("mounts") or {}).items():
        marker = spec.get("marker")
        chosen = None
        for cand in spec.get("candidates") or []:
            probe = Path(cand, marker) if marker else Path(cand)
            if probe.is_dir():
                chosen = cand
                break
        out[name] = chosen
    return out


def expand(template: str, mounts: dict[str, str | None]) -> str | None:
    """Substitute ${MOUNT} tokens. None if any token is unresolved."""
    missing = [m.group(1) for m in _TOKEN.finditer(template)
               if mounts.get(m.group(1)) is None]
    if missing:
        return None
    return _TOKEN.sub(lambda m: mounts[m.group(1)], template)


def resolve_roots(cfg: dict | None = None) -> list[Root]:
    """All configured roots, highest priority first, with availability filled in."""
    cfg = cfg if cfg is not None else load_config()
    mounts = resolve_mounts(cfg)
    roots: list[Root] = []
    for spec in cfg.get("roots") or []:
        template = spec["path"]
        path = expand(template, mounts)
        roots.append(Root(
            id=spec["id"],
            label=spec.get("label", spec["id"]),
            path=path,
            priority=int(spec.get("priority", 0)),
            enabled=bool(spec.get("enabled", True)),
            available=bool(path) and Path(path).is_dir(),
            template=template,
            note=spec.get("note", ""),
        ))
    roots.sort(key=lambda r: (-r.priority, r.id))
    return roots


def limits(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else load_config()
    lim = dict(cfg.get("limits") or {})
    lim.setdefault("max_resident_adapters", 4)
    lim.setdefault("vram_floor_gb", 6.0)
    return lim
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest test_model_roots.py -v`
Expected: 7 passed.

- [ ] **Step 6: Verify against the real drives**

Run:
```bash
cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -c "
import model_roots, json
for r in model_roots.resolve_roots():
    print(f'{r.available!s:5} {r.id:12} {r.path}')
print(model_roots.limits())
"
```
Expected: `lumi_uuid`, `local_dora`, `control`, `lumi_mantu` printed with `True` for each
currently-mounted drive, and paths matching the discovery table above. If a drive is unmounted the
row must print `False` with `path=None` and **must not raise**.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/model_roots.py eval/model_roots.json eval/test_model_roots.py
git commit -m "model_roots: config-driven multi-root + removable-drive mount resolution

No drive path in code (standing rule); mounts resolve by marker probe, the
generalisation of explorer_render_server._mantu_root. Absent drives stay listed
with available=false so callers can serve a cached journal.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 2: Cheap checkpoint probe (family detection without torch)

A 44 GB fat checkpoint must be classified in milliseconds. A Lightning `.ckpt` is a zip archive
whose `data.pkl` member is small even when the tensor payload is enormous — reading and
byte-scanning that one member classifies the file without unpickling anything. **Verified today**
on a 666 MB DoRA: 229 `lora_A` / 229 `magnitude` occurrences, `FloatStorage`, `lora_config`
present. A `.safetensors` file carries a JSON header whose length is the first 8 bytes.

**Files:**
- Create: `/home/kim/Projects/SAO/eval/ckpt_probe.py`
- Test: `/home/kim/Projects/SAO/eval/test_ckpt_probe.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `probe(path: str | Path) -> dict` with keys
  `family` (`"adapter" | "fullft" | "control_adapter" | "latch_head" | "unknown"`),
  `kind` (`"ckpt" | "safetensors" | "pt"`), `slim` (bool), `rank` (int|None),
  `alpha` (float|None), `adapter_type` (str|None), `control_mode` (str|None),
  `epoch` (int|None), `step` (int|None), `n_target_modules` (int|None),
  `dtype_hint` (str|None), `size` (int), `mtime` (float), `probe_error` (str|None).
  Also `FAMILIES: tuple[str, ...]`.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_ckpt_probe.py`:

```python
import os

import pytest
import torch

import ckpt_probe


def _save(path, obj):
    torch.save(obj, path)
    return str(path)


def _dora_sd(n_modules=3, rank=8, in_f=16, out_f=32):
    sd = {}
    for i in range(n_modules):
        base = f"model.transformer.layers.{i}.attn.to_qkv.parametrizations.weight.0"
        sd[f"{base}.lora_A"] = torch.zeros(rank, in_f)
        sd[f"{base}.lora_B"] = torch.zeros(out_f, rank)
        sd[f"{base}.magnitude"] = torch.zeros(out_f)
    return sd


def test_adapter_is_detected_with_rank_and_module_count(tmp_path):
    p = _save(tmp_path / "epoch=3-step=144.weights.ckpt", {
        "state_dict": _dora_sd(n_modules=3, rank=8),
        "epoch": 3, "global_step": 144,
        "lora_config": {"rank": 8, "alpha": 4.0, "adapter_type": "dora-rows"},
    })
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert r["rank"] == 8 and r["alpha"] == 4.0
    assert r["adapter_type"] == "dora-rows"
    assert r["n_target_modules"] == 3
    assert r["epoch"] == 3 and r["step"] == 144
    assert r["probe_error"] is None


def test_control_adapter_is_detected_from_the_top_level_control_mode_key(tmp_path):
    p = _save(tmp_path / "riffer_final.pt", {
        "state_dict": {"enc.0.weight": torch.zeros(2, 2)},
        "control_mode": "melody_contour",
        "args": {"melody_vocab": 77, "control_dim": 768},
    })
    r = ckpt_probe.probe(p)
    assert r["family"] == "control_adapter"
    assert r["control_mode"] == "melody_contour"
    assert r["kind"] == "pt"


def test_fullft_is_detected_when_the_state_dict_covers_the_dit_and_carries_no_lora(tmp_path):
    sd = {f"model.transformer.layers.{i}.attn.to_qkv.weight": torch.zeros(2, 2)
          for i in range(4)}
    sd["model.to_timestep_embed.0.weight"] = torch.zeros(2, 2)
    p = _save(tmp_path / "epoch=7-step=10800.weights.ckpt",
              {"state_dict": sd, "epoch": 7, "global_step": 10800})
    r = ckpt_probe.probe(p)
    assert r["family"] == "fullft"
    assert r["rank"] is None


def test_slim_vs_fat_is_read_from_the_optimizer_states_key(tmp_path):
    fat = _save(tmp_path / "epoch=0-step=1.ckpt", {
        "state_dict": _dora_sd(), "optimizer_states": [{"state": {}}],
        "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}})
    slim = _save(tmp_path / "epoch=0-step=1.weights.ckpt", {
        "state_dict": _dora_sd(),
        "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}})
    assert ckpt_probe.probe(fat)["slim"] is False
    assert ckpt_probe.probe(slim)["slim"] is True


def test_epoch_and_step_fall_back_to_the_filename_when_absent_from_the_payload(tmp_path):
    p = _save(tmp_path / "epoch=12-step=999.weights.ckpt", {"state_dict": _dora_sd()})
    r = ckpt_probe.probe(p)
    assert r["epoch"] == 12 and r["step"] == 999


def test_safetensors_adapter_is_probed_from_its_json_header(tmp_path):
    from safetensors.torch import save_file
    p = tmp_path / "extracted.safetensors"
    save_file({"model.a.parametrizations.weight.0.lora_A": torch.zeros(16, 8),
               "model.a.parametrizations.weight.0.lora_B": torch.zeros(8, 16)}, str(p))
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert r["kind"] == "safetensors"
    assert r["rank"] == 16


def test_an_unreadable_file_returns_unknown_and_an_error_rather_than_raising(tmp_path):
    p = tmp_path / "junk.ckpt"
    p.write_bytes(b"not a zip")
    r = ckpt_probe.probe(p)
    assert r["family"] == "unknown"
    assert r["probe_error"]


def test_probe_reads_only_the_pickle_member_not_the_tensor_payload(tmp_path):
    """A big payload must not make the probe slow -- it is the whole point."""
    big = {"state_dict": dict(_dora_sd(), pad=torch.zeros(8_000_000)),
           "lora_config": {"rank": 8, "alpha": 8.0, "adapter_type": "dora-rows"}}
    p = _save(tmp_path / "epoch=0-step=1.ckpt", big)
    assert os.path.getsize(p) > 30_000_000
    import time
    t0 = time.time()
    r = ckpt_probe.probe(p)
    assert r["family"] == "adapter"
    assert time.time() - t0 < 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_ckpt_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ckpt_probe'`

- [ ] **Step 3: Write the module**

Create `/home/kim/Projects/SAO/eval/ckpt_probe.py`:

```python
"""Classify ONE checkpoint file cheaply: no torch.load, no GPU, no unpickling.

A Lightning .ckpt (and a torch.save'd riffer_*.pt) is a zip archive whose
`data.pkl` member is small even when the tensor payload is 44 GB -- reading and
byte-scanning that one member is enough to tell the four families apart
(docs/INFERENCE-SURFACE.md section 2). A .safetensors file states its JSON
header length in its first 8 bytes.

Families: adapter (LoRA/DoRA) | fullft | control_adapter (Head-B) | latch_head |
unknown. A checkpoint does NOT announce its family in its filename -- that is
exactly why this exists.
"""
from __future__ import annotations

import json
import re
import struct
import zipfile
from pathlib import Path

FAMILIES = ("adapter", "fullft", "control_adapter", "latch_head", "unknown")

_EPOCH_STEP = re.compile(r"epoch=(\d+)-step=(\d+)")
_STEP_ONLY = re.compile(r"step(\d+)")
# Pickled str values appear verbatim in data.pkl; scan for ASCII runs.
_ASCII = re.compile(rb"[ -~]{4,}")
_LORA_A_KEY = re.compile(rb"parametrizations\.weight\.\d+\.lora_A")
_DIT_KEY = re.compile(rb"(transformer\.layers\.\d+|to_timestep_embed|to_cond_embed)")


def _blank(path: Path, kind: str) -> dict:
    try:
        st = path.stat()
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        size, mtime = 0, 0.0
    return {"family": "unknown", "kind": kind, "slim": None, "rank": None,
            "alpha": None, "adapter_type": None, "control_mode": None,
            "epoch": None, "step": None, "n_target_modules": None,
            "dtype_hint": None, "size": size, "mtime": mtime, "probe_error": None}


def _epoch_step_from_name(name: str) -> tuple[int | None, int | None]:
    m = _EPOCH_STEP.search(name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _STEP_ONLY.search(name)
    if m:
        return None, int(m.group(1))
    return None, None


def _strings(raw: bytes) -> list[bytes]:
    return _ASCII.findall(raw)


def _scalar_after(raw: bytes, key: bytes) -> bytes | None:
    """Bytes following a pickled key, for cheap value sniffing."""
    i = raw.find(key)
    return None if i < 0 else raw[i:i + 400]


def _probe_zip(path: Path, kind: str) -> dict:
    out = _blank(path, kind)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        pkl = next((n for n in names if n.endswith("data.pkl")), None)
        if pkl is None:
            out["probe_error"] = "no data.pkl member"
            return out
        raw = z.read(pkl)

    out["dtype_hint"] = next((d for d, tok in (
        ("float32", b"FloatStorage"), ("float16", b"HalfStorage"),
        ("bfloat16", b"BFloat16Storage")) if tok in raw), None)
    out["slim"] = b"optimizer_states" not in raw

    lora_a = _LORA_A_KEY.findall(raw)
    has_control_mode = b"control_mode" in raw
    has_latch = b"out_proj" in raw and b"feature_stats" in raw

    if has_control_mode:
        out["family"] = "control_adapter"
        blob = _scalar_after(raw, b"control_mode")
        for cand in (b"melody_contour", b"metrical_position", b"fingerprint",
                     b"dual_scalar", b"attribute", b"scalar"):
            if blob and cand in blob:
                out["control_mode"] = cand.decode()
                break
    elif lora_a:
        out["family"] = "adapter"
        out["n_target_modules"] = len(lora_a)
        blob = _scalar_after(raw, b"adapter_type")
        for cand in (b"dora-rows", b"dora-xs", b"lora-xs", b"dora", b"lora"):
            if blob and cand in blob:
                out["adapter_type"] = cand.decode()
                break
    elif has_latch:
        out["family"] = "latch_head"
    elif _DIT_KEY.search(raw):
        out["family"] = "fullft"

    for key, field, cast in ((b"epoch", "epoch", int), (b"global_step", "step", int)):
        i = raw.find(key)
        if i >= 0:
            # Lightning pickles these as ints immediately after the key; a full
            # unpickle is overkill, so fall back to the filename when unsure.
            pass
    ep, st = _epoch_step_from_name(path.name)
    out["epoch"], out["step"] = ep, st
    return out


def _probe_safetensors(path: Path) -> dict:
    out = _blank(path, "safetensors")
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n).decode("utf-8"))
    keys = [k for k in header if k != "__metadata__"]
    lora_a = [k for k in keys if "lora_A" in k]
    if lora_a:
        out["family"] = "adapter"
        out["n_target_modules"] = len(lora_a)
        out["rank"] = int(header[lora_a[0]]["shape"][0])
    elif any(re.search(r"transformer\.layers\.\d+", k) for k in keys):
        out["family"] = "fullft"
    out["slim"] = True
    md = header.get("__metadata__") or {}
    out["adapter_type"] = md.get("adapter_type")
    out["epoch"], out["step"] = _epoch_step_from_name(path.name)
    return out


def probe(path: str | Path) -> dict:
    """Classify one checkpoint. Never raises -- errors land in probe_error."""
    p = Path(path)
    suffix = p.suffix.lower()
    kind = {"safetensors": "safetensors", ".pt": "pt"}.get(
        suffix, "safetensors" if suffix == ".safetensors" else
        ("pt" if suffix == ".pt" else "ckpt"))
    try:
        if suffix == ".safetensors":
            return _probe_safetensors(p)
        out = _probe_zip(p, kind)
    except Exception as e:                      # unreadable / racing delete / not a zip
        out = _blank(p, kind)
        out["probe_error"] = f"{type(e).__name__}: {e}"
        return out

    # rank/alpha come from the pickled lora_config; read them with a bounded
    # torch.load of the METADATA ONLY when the cheap scan found an adapter.
    if out["family"] == "adapter" and out["rank"] is None:
        out.update(_lora_config_fields(p))
    return out


def _lora_config_fields(path: Path) -> dict:
    """rank/alpha/adapter_type from lora_config. Uses torch.load(mmap=True) so
    only the small config object is materialised, never the tensor payload."""
    try:
        import torch
        ck = torch.load(str(path), map_location="meta", weights_only=False, mmap=True)
    except Exception:
        try:
            import torch
            ck = torch.load(str(path), map_location="cpu", weights_only=False)
        except Exception as e:
            return {"probe_error": f"lora_config read failed: {type(e).__name__}: {e}"}
    lc = (ck or {}).get("lora_config") or {}
    sd = (ck or {}).get("state_dict") or {}
    rank = lc.get("rank")
    if rank is None:
        for k, v in sd.items():
            if "lora_A" in k and hasattr(v, "shape"):
                rank = int(v.shape[0])
                break
    out = {"rank": int(rank) if rank is not None else None,
           "alpha": float(lc["alpha"]) if lc.get("alpha") is not None else None}
    if lc.get("adapter_type"):
        out["adapter_type"] = lc["adapter_type"]
    ep, st = ck.get("epoch"), ck.get("global_step")
    if ep is not None:
        out["epoch"] = int(ep)
    if st is not None:
        out["step"] = int(st)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_ckpt_probe.py -v`
Expected: 8 passed. If `test_probe_reads_only_the_pickle_member_not_the_tensor_payload` fails on
time, the `mmap=True` fallback path is being hit — confirm `_probe_zip` set `rank` via
`n_target_modules` first, and that `_lora_config_fields` is only reached when `lora_config` is
genuinely needed.

- [ ] **Step 5: Verify against REAL checkpoints of every family**

Run:
```bash
cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -c "
import time, ckpt_probe
U='/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs'
for p in [
  U+'/bf16_twin/bf16cmp_avp_t512_bs8_lr1e4/epoch=0-step=299.weights.ckpt',
  U+'/fullft/fullft_goa_t512/epoch=7-step=10800.weights.ckpt',
  U+'/precision_ladder/precision_ladder_t256_fp32/epoch=9-step=4500.ckpt',
]:
    t0=time.time(); r=ckpt_probe.probe(p)
    print(f\"{time.time()-t0:5.2f}s {r['family']:16} slim={r['slim']} r={r['rank']} at={r['adapter_type']} ep={r['epoch']} step={r['step']}\")
"
```
Expected: `adapter` (slim=True, r=128, dora-rows, ep=0, step=299) · `fullft` (slim=True) ·
`fullft` or `adapter` for the 44 GB fat file with **slim=False**, and **every probe under ~1 s**
including the 44 GB one. If the 44 GB probe is slow, `_lora_config_fields` is being reached — that
is the bug to fix, not a tolerable cost.

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/ckpt_probe.py eval/test_ckpt_probe.py
git commit -m "ckpt_probe: classify a checkpoint family without torch.load

A Lightning .ckpt is a zip whose data.pkl is small even at 44 GB; byte-scanning
that one member separates adapter / fullft / control_adapter / latch_head in
milliseconds. Covers riffer_*.pt (which an epoch=*.ckpt glob never sees) and
safetensors headers.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 3: The model database

**Files:**
- Create: `/home/kim/Projects/SAO/eval/model_db.py`
- Test: `/home/kim/Projects/SAO/eval/test_model_db.py`

**Interfaces:**
- Consumes: `model_roots.resolve_roots`, `model_roots.Root`, `ckpt_probe.probe`.
- Produces:
  - `SCHEMA_VERSION: int = 2`
  - `JOURNAL_PATH: Path` (`/tmp/sa3_explorer_ckpt_journal.json` — the existing file, upgraded)
  - `scan_root(root: Root) -> list[dict]` — raw file entries (path/name/mtime/size/kind)
  - `record_for(path: str, root: Root, overrides: dict) -> dict` — one full DB record
  - `build(roots: list[Root] | None = None, overrides_path: str | Path | None = None) -> list[dict]`
  - `load_or_build(root_ids: list[str] | None = None, rescan: bool = False) -> dict`
    returning `{"schema": int, "roots": [Root.as_dict()], "models": [record], "stale_root_ids": [str]}`
  - `stable_id(path: str) -> str`
  - `find_run_meta(path: Path, root_path: Path) -> Path | None`
  - `parse_run_meta(data: dict) -> dict`
  - `dedupe(records: list[dict]) -> list[dict]`

**The record schema — what "a database of models" holds:**

```python
{
  "id": "MDB-3f9a21c7",          # stable, = sha1(abs path)[:8]
  "path": "/abs/path/to/epoch=7-step=288.weights.ckpt",
  "root_id": "lumi_uuid",
  "family_dir": "bf16_twin",     # top-level dir under the root == the run FAMILY
  "arm": "bf16cmp_avp_t512_bs8_lr1e4",   # the training RUN (leaf dir)
  "label": "bf16cmp_avp_t512_bs8_lr1e4", # join key into model_index / overrides
  "family": "adapter",           # from ckpt_probe -- DETECTED, never guessed
  "kind": "ckpt", "slim": True, "size": 666439005, "mtime": 1723...,
  "epoch": 0, "step": 299,
  "rank": 128, "alpha": 45.0, "adapter_type": "dora-rows", "control_mode": None,
  "corpus": "avp", "crop_frames": 512, "optimizer": "adamw",
  "lr": "1e-4", "precision": "bf16", "seed": 1, "n_files": 5400,
  "purpose": "...", "hypothesis": "...", "status": "...", "kim_feedback": None,
  "verdict": "...",              # from Misc/models_index_overrides.json "note"
  "recipe": "...",               # from overrides "recipe" (extracted, not written)
  "run_meta_path": "/abs/.../run_meta.json",
  "loadable": True,              # family in {adapter, fullft}; control/latch are not
                                 # loadable through the render server today
  "load_cost_gb": 0.33,          # half-precision residency estimate
  "provenance": {"corpus": "run_meta.training.corpus", "rank": "ckpt",
                 "verdict": "overrides", ...}
}
```

`provenance` is mandatory, not decoration: some `run_meta.json` files are reconstructions
(`"reconstructed_by": "CONTINUITY-subagent 2026-08-04 from ckpt args"`), so a field read from a
reconstruction is a weaker claim than one read from the checkpoint. Checkpoint-derived fields
always win a conflict; `run_meta` fills gaps; overrides supply human judgement only.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_model_db.py`:

```python
import json

import pytest
import torch

import model_db
from model_roots import Root


def _adapter_ckpt(path, rank=8, epoch=0, step=1):
    sd = {}
    for i in range(2):
        b = f"model.transformer.layers.{i}.attn.to_qkv.parametrizations.weight.0"
        sd[f"{b}.lora_A"] = torch.zeros(rank, 4)
        sd[f"{b}.lora_B"] = torch.zeros(4, rank)
        sd[f"{b}.magnitude"] = torch.zeros(4)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": sd, "epoch": epoch, "global_step": step,
                "lora_config": {"rank": rank, "alpha": float(rank),
                                "adapter_type": "dora-rows"}}, path)
    return path


def _root(tmp_path, rid="r1"):
    return Root(id=rid, label=rid, path=str(tmp_path), priority=10, enabled=True,
                available=True, template="${X}")


def test_scan_root_finds_ckpt_safetensors_and_pt(tmp_path):
    _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "ctrl").mkdir()
    torch.save({"control_mode": "melody_contour", "state_dict": {}},
               tmp_path / "ctrl" / "riffer_final.pt")
    (tmp_path / "x.safetensors").write_bytes(b"\x02\x00\x00\x00\x00\x00\x00\x00{}")
    names = {e["name"] for e in model_db.scan_root(_root(tmp_path))}
    assert "fam/arm/epoch=0-step=1.weights.ckpt" in names
    assert "ctrl/riffer_final.pt" in names, "riffer_*.pt must not be invisible"
    assert "x.safetensors" in names


def test_record_carries_family_arm_and_detected_fields(tmp_path):
    p = _adapter_ckpt(tmp_path / "bf16_twin" / "armA" / "epoch=3-step=144.weights.ckpt",
                      rank=16, epoch=3, step=144)
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["family"] == "adapter"
    assert rec["family_dir"] == "bf16_twin" and rec["arm"] == "armA"
    assert rec["label"] == "armA"
    assert rec["rank"] == 16 and rec["epoch"] == 3 and rec["step"] == 144
    assert rec["loadable"] is True
    assert rec["id"].startswith("MDB-")


def test_run_meta_is_found_by_walking_up_and_both_shapes_parse(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "fam" / "run_meta.json").write_text(json.dumps({
        "purpose": "recon style",
        "reconstructed_by": "someone",
        "training": {"corpus": "avp", "crop_frames": 512, "optimizer": "adamw",
                     "lr": None, "base_precision": "bf16", "seed": 1},
        "status": "COMPLETE", "kim_feedback": None}))
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["corpus"] == "avp" and rec["crop_frames"] == 512
    assert rec["precision"] == "bf16"
    assert rec["provenance"]["corpus"].startswith("run_meta")

    q = _adapter_ckpt(tmp_path / "fam2" / "arm" / "epoch=0-step=1.weights.ckpt")
    (tmp_path / "fam2" / "arm" / "run_meta.json").write_text(json.dumps({
        "run": "x", "purpose": "launch style",
        "dataset": {"name": "suomi"},
        "recipe": {"adapter": "lora", "rank": 16, "lr": "1e-4", "frames": 256,
                   "optimizer": "adamw", "precision": "bf16"}}))
    rec2 = model_db.record_for(str(q), _root(tmp_path), {})
    assert rec2["corpus"] == "suomi" and rec2["lr"] == "1e-4"
    assert rec2["crop_frames"] == 256


def test_checkpoint_derived_fields_beat_run_meta_on_conflict(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt", rank=8)
    (tmp_path / "fam" / "run_meta.json").write_text(json.dumps({
        "training": {"dora_rank": 999, "corpus": "goa"}}))
    rec = model_db.record_for(str(p), _root(tmp_path), {})
    assert rec["rank"] == 8, "the checkpoint is ground truth, run_meta may be reconstructed"
    assert rec["provenance"]["rank"] == "ckpt"
    assert rec["corpus"] == "goa"


def test_overrides_supply_verdict_and_recipe_but_never_detected_fields(tmp_path):
    p = _adapter_ckpt(tmp_path / "fam" / "armA" / "epoch=0-step=1.weights.ckpt", rank=8)
    ov = {"armA": {"note": "usable at ep3-7", "recipe": "adamw - lr 1e-4"}}
    rec = model_db.record_for(str(p), _root(tmp_path), ov)
    assert rec["verdict"] == "usable at ep3-7"
    assert rec["recipe"] == "adamw - lr 1e-4"
    assert rec["provenance"]["verdict"] == "overrides"
    assert rec["rank"] == 8


def test_dedupe_prefers_the_higher_priority_root_for_an_identical_arm_and_file(tmp_path):
    hi = tmp_path / "hi"
    lo = tmp_path / "lo"
    _adapter_ckpt(hi / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    _adapter_ckpt(lo / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    rh = Root("hi", "hi", str(hi), 30, True, True, "${X}")
    rl = Root("lo", "lo", str(lo), 5, True, True, "${X}")
    recs = model_db.build([rh, rl], overrides_path=None)
    kept = model_db.dedupe(recs)
    assert len(kept) == 1 and kept[0]["root_id"] == "hi"
    assert kept[0]["also_at"] == [str(lo / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")]


def test_load_cost_gb_scales_with_rank(tmp_path):
    small = model_db.record_for(
        str(_adapter_ckpt(tmp_path / "a" / "b" / "epoch=0-step=1.weights.ckpt", rank=8)),
        _root(tmp_path), {})
    assert 0.0 < small["load_cost_gb"] < 1.0


def test_an_unavailable_root_is_reported_stale_not_fatal(tmp_path):
    gone = Root("gone", "gone", None, 10, True, False, "${MISSING}")
    out = model_db.load_or_build([gone.id], rescan=True)  # no journal entry either
    assert "gone" in out["stale_root_ids"] or out["models"] == []


def test_journal_round_trips_and_rescan_forces_a_rewalk(tmp_path, monkeypatch):
    jp = tmp_path / "journal.json"
    monkeypatch.setattr(model_db, "JOURNAL_PATH", jp)
    r = _root(tmp_path)
    _adapter_ckpt(tmp_path / "fam" / "arm" / "epoch=0-step=1.weights.ckpt")
    monkeypatch.setattr(model_db, "resolve_roots", lambda: [r])
    first = model_db.load_or_build(rescan=True)
    assert len(first["models"]) == 1
    assert json.loads(jp.read_text())["schema"] == model_db.SCHEMA_VERSION
    _adapter_ckpt(tmp_path / "fam" / "arm2" / "epoch=0-step=2.weights.ckpt")
    cached = model_db.load_or_build(rescan=False)
    assert len(cached["models"]) == 1, "cached read must not re-walk"
    fresh = model_db.load_or_build(rescan=True)
    assert len(fresh["models"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_model_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model_db'`

- [ ] **Step 3: Write the module**

Create `/home/kim/Projects/SAO/eval/model_db.py`:

```python
"""The model database behind the SA3 inference picker.

A database of models keyed by ABSOLUTE CHECKPOINT PATH -- which is the piece that
was missing. It does NOT replace model_index.md (377 board labels / 309 models /
71 families, generated by Misc/build_model_index_page.py) or
Misc/models_index_overrides.json; it JOINS to them, so Kim's by-ear verdicts and
the extracted recipes reach the picker instead of living only in a 4358-line
markdown page.

Field precedence, deliberately:
  ckpt probe  >  run_meta.json  >  Misc/models_index_overrides.json
The checkpoint is ground truth. Some run_meta.json files are RECONSTRUCTIONS
("reconstructed_by": "...from ckpt args") and can be wrong. Overrides carry human
judgement (verdict / why) and never detected fields. Every field records where it
came from in record["provenance"].
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import ckpt_probe
from model_roots import Root, resolve_roots

SCHEMA_VERSION = 2
JOURNAL_PATH = Path("/tmp/sa3_explorer_ckpt_journal.json")
OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "Misc" / "models_index_overrides.json"

SCAN_SUFFIXES = (".ckpt", ".safetensors", ".pt")
LOADABLE_FAMILIES = ("adapter", "fullft")
# 229 target modules x (lora_A + lora_B + magnitude) at r128 measured 666.4 MB
# fp32 => 166 M params => 0.33 GB at half. Scale linearly in rank.
_GB_PER_RANK_HALF = 0.33 / 128.0
_FULLFT_GB_HALF = 2.8


def stable_id(path: str) -> str:
    return "MDB-" + hashlib.sha1(str(path).encode()).hexdigest()[:8]


def scan_root(root: Root) -> list[dict]:
    """Recursive scan for every checkpoint-shaped file under one root.

    Includes *.pt: control runs save riffer_final.pt / riffer_step<N>.pt and a
    glob for epoch=*.ckpt finds ZERO of them (INFERENCE-SURFACE section 2).
    """
    if not root.path or not Path(root.path).is_dir():
        return []
    base = Path(root.path)
    entries = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(SCAN_SUFFIXES):
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append({"path": str(p), "name": str(p.relative_to(base)),
                            "mtime": st.st_mtime, "size": st.st_size,
                            "kind": p.suffix.lstrip(".")})
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def find_run_meta(path: Path, root_path: Path) -> Path | None:
    """Walk up from the checkpoint to the root looking for run_meta.json."""
    cur = path.parent
    root_path = Path(root_path).resolve()
    while True:
        cand = cur / "run_meta.json"
        if cand.is_file():
            return cand
        if cur.resolve() == root_path or cur.parent == cur:
            return None
        cur = cur.parent


def parse_run_meta(data: dict) -> dict:
    """Normalise BOTH run_meta shapes onto one field set.

    reconstructed style: {"training": {corpus, crop_frames, optimizer, lr,
        base_precision, seed, n_files, dora_rank, adapter}, purpose, status, ...}
    launch style:        {"dataset": {name}, "recipe": {adapter, rank, alpha, lr,
        frames, optimizer, precision, batch_size, epochs}, purpose, script, ...}
    """
    tr = data.get("training") or {}
    rc = data.get("recipe") or {}
    ds = data.get("dataset") or {}
    out = {
        "corpus": tr.get("corpus") or ds.get("name"),
        "crop_frames": tr.get("crop_frames") or rc.get("frames"),
        "optimizer": tr.get("optimizer") or rc.get("optimizer"),
        "lr": tr.get("lr") if tr.get("lr") is not None else rc.get("lr"),
        "precision": tr.get("base_precision") or rc.get("precision"),
        "seed": tr.get("seed"),
        "n_files": tr.get("n_files"),
        "purpose": data.get("purpose"),
        "hypothesis": data.get("hypothesis"),
        "status": data.get("status"),
        "kim_feedback": data.get("kim_feedback"),
        "reconstructed": bool(data.get("reconstructed_by")),
        "slurm_job": data.get("slurm_job"),
    }
    return {k: v for k, v in out.items() if v is not None}


def _load_overrides(overrides_path) -> dict:
    if overrides_path is None:
        return {}
    p = Path(overrides_path)
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _load_cost_gb(family: str, rank: int | None) -> float:
    if family == "fullft":
        return _FULLFT_GB_HALF
    if family == "adapter":
        return round(_GB_PER_RANK_HALF * (rank or 128), 3)
    return 0.0


def record_for(path: str, root: Root, overrides: dict) -> dict:
    p = Path(path)
    base = Path(root.path)
    rel = p.relative_to(base)
    parts = rel.parts
    family_dir = parts[0] if len(parts) > 1 else ""
    arm = p.parent.name if p.parent != base else family_dir

    probe = ckpt_probe.probe(p)
    prov = {k: "ckpt" for k in
            ("family", "kind", "slim", "rank", "alpha", "adapter_type",
             "control_mode", "epoch", "step", "size", "mtime")
            if probe.get(k) is not None}

    rec = {
        "id": stable_id(str(p)), "path": str(p), "root_id": root.id,
        "family_dir": family_dir, "arm": arm, "label": arm,
        "family": probe["family"], "kind": probe["kind"], "slim": probe["slim"],
        "size": probe["size"], "mtime": probe["mtime"],
        "epoch": probe["epoch"], "step": probe["step"],
        "rank": probe["rank"], "alpha": probe["alpha"],
        "adapter_type": probe["adapter_type"], "control_mode": probe["control_mode"],
        "n_target_modules": probe["n_target_modules"],
        "probe_error": probe["probe_error"],
        "run_meta_path": None, "also_at": [],
    }

    rm_path = find_run_meta(p, base)
    if rm_path is not None:
        rec["run_meta_path"] = str(rm_path)
        try:
            rm = parse_run_meta(json.loads(rm_path.read_text()))
        except (OSError, json.JSONDecodeError):
            rm = {}
        src = "run_meta(reconstructed)" if rm.pop("reconstructed", False) else "run_meta"
        for k, v in rm.items():
            if rec.get(k) is None:          # ckpt wins every conflict
                rec[k] = v
                prov[k] = f"{src}.{k}"

    ov = overrides.get(arm) or overrides.get(family_dir) or {}
    if ov.get("note"):
        rec["verdict"] = ov["note"]
        prov["verdict"] = "overrides"
    if ov.get("recipe"):
        rec["recipe"] = ov["recipe"]
        prov["recipe"] = "overrides"

    rec["loadable"] = rec["family"] in LOADABLE_FAMILIES
    rec["load_cost_gb"] = _load_cost_gb(rec["family"], rec["rank"])
    rec["provenance"] = prov
    for k in ("corpus", "crop_frames", "optimizer", "lr", "precision", "seed",
              "purpose", "status", "kim_feedback", "verdict", "recipe"):
        rec.setdefault(k, None)
    return rec


def build(roots: list[Root] | None = None,
          overrides_path: str | Path | None = OVERRIDES_PATH) -> list[dict]:
    roots = roots if roots is not None else resolve_roots()
    overrides = _load_overrides(overrides_path)
    out: list[dict] = []
    for root in roots:
        if not root.enabled:
            continue
        for e in scan_root(root):
            out.append(record_for(e["path"], root, overrides))
    return out


def dedupe(records: list[dict], roots: list[Root] | None = None) -> list[dict]:
    """Collapse the same (arm, filename) seen under several roots.

    The Mantu lumi_runs copy is an early PARTIAL grab superseded by the UUID
    drive (ARCHITECTURE.md), so priority decides and the loser is recorded in
    the winner's "also_at".
    """
    roots = roots if roots is not None else resolve_roots()
    prio = {r.id: r.priority for r in roots}
    best: dict[tuple, dict] = {}
    for rec in records:
        key = (rec["family_dir"], rec["arm"], Path(rec["path"]).name)
        cur = best.get(key)
        if cur is None:
            best[key] = rec
        elif prio.get(rec["root_id"], 0) > prio.get(cur["root_id"], 0):
            rec["also_at"] = cur["also_at"] + [cur["path"]]
            best[key] = rec
        else:
            cur["also_at"] = cur["also_at"] + [rec["path"]]
    return list(best.values())


def _read_journal() -> dict:
    if not JOURNAL_PATH.exists():
        return {}
    try:
        j = json.loads(JOURNAL_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return j if j.get("schema") == SCHEMA_VERSION else {}


def _write_journal(j: dict) -> None:
    tmp = JOURNAL_PATH.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(j))
        tmp.replace(JOURNAL_PATH)       # atomic: readers see old or new, never half
    except OSError:
        pass


def load_or_build(root_ids: list[str] | None = None, rescan: bool = False) -> dict:
    """The server-facing entry point. Cached per root; unavailable roots serve
    their stale journal rather than failing the whole request."""
    roots = [r for r in resolve_roots() if root_ids is None or r.id in root_ids]
    journal = _read_journal()
    by_root = journal.get("roots", {})
    overrides = _load_overrides(OVERRIDES_PATH)
    models: list[dict] = []
    stale: list[str] = []
    changed = False

    for root in roots:
        cached = by_root.get(root.id)
        if not root.enabled:
            continue
        if root.available and (rescan or cached is None):
            recs = [record_for(e["path"], root, overrides) for e in scan_root(root)]
            by_root[root.id] = {"scanned_at": time.time(), "path": root.path,
                                "models": recs}
            changed = True
            models.extend(recs)
        elif cached is not None:
            if not root.available:
                stale.append(root.id)
            models.extend(cached["models"])
        elif not root.available:
            stale.append(root.id)

    if changed:
        _write_journal({"schema": SCHEMA_VERSION, "roots": by_root})
    return {"schema": SCHEMA_VERSION,
            "roots": [r.as_dict() for r in roots],
            "models": dedupe(models, roots),
            "stale_root_ids": stale}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_model_db.py -v`
Expected: 9 passed.

- [ ] **Step 5: Verify against the real drives**

Run:
```bash
cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -c "
import collections, time, model_db
t0=time.time(); out = model_db.load_or_build(rescan=True)
print(f'{len(out[\"models\"])} models in {time.time()-t0:.1f}s, stale={out[\"stale_root_ids\"]}')
print('by family :', collections.Counter(m['family'] for m in out['models']))
print('by root   :', collections.Counter(m['root_id'] for m in out['models']))
print('with meta :', sum(1 for m in out['models'] if m['run_meta_path']))
print('w/ verdict:', sum(1 for m in out['models'] if m['verdict']))
print('unknown   :', [m['path'] for m in out['models'] if m['family']=='unknown'][:5])
"
```
Expected: several hundred models; `adapter` and `fullft` both non-zero; `control_adapter` non-zero
if `sa3_control_runs` is mounted; ≥60 carrying `run_meta_path`; `unknown` a short list (investigate
any entry there before proceeding — an unknown family in the picker is a load failure later).

- [ ] **Step 6: Point `Misc/extract_recipes.py` at the config instead of a literal**

Edit `/home/kim/Projects/SAO/Misc/extract_recipes.py`, replacing line 30:

```python
DEFAULT_ROOT = "/run/media/kim/Mantu/sa3_lora_runs"
```

with:

```python
# Standing rule: no drive paths in code. eval/model_roots.json is the config.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from model_roots import resolve_roots as _resolve_roots  # noqa: E402


def _default_root() -> str:
    for r in _resolve_roots():
        if r.id == "local_dora" and r.available:
            return r.path
    raise SystemExit("no available checkpoint root — is the eval drive mounted? "
                     "(see eval/model_roots.json)")


DEFAULT_ROOT = None      # resolved lazily in main(); see _default_root()
```

and in `main()` replace `root = v.get("root") or DEFAULT_ROOT` with
`root = v.get("root") or _default_root()`.

Run: `cd /home/kim/Projects/SAO && /home/kim/Projects/SAO/.venv/bin/python Misc/extract_recipes.py --help`
Expected: help text prints, no import error, no drive access at import time.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/model_db.py eval/test_model_db.py Misc/extract_recipes.py
git commit -m "model_db: path-keyed model database over multi-root scan + run_meta + overrides

Joins to the EXISTING model index (model_index.md / models_index_overrides.json)
rather than starting a second one; adds what was missing, a database keyed by
absolute checkpoint path. Precedence ckpt > run_meta > overrides, with per-field
provenance because some run_meta files are reconstructions. Also removes the
hardcoded drive path from Misc/extract_recipes.py.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 4: Server — `/roots`, `/models`, multi-root `/ckpts` (compat preserved)

**Files:**
- Modify: `/home/kim/Projects/SAO/eval/explorer_render_server.py:93` (constants), `:583-627` (`/ckpts`)
- Test: `/home/kim/Projects/SAO/eval/test_render_server_models_api.py` (create)

**Interfaces:**
- Consumes: `model_roots.resolve_roots`, `model_db.load_or_build`.
- Produces (HTTP):
  - `GET /roots` → `{"ok": True, "roots": [{id,label,path,priority,enabled,available,note,count}]}`
  - `GET /models?root_ids=a,b&family=adapter&corpus=avp&q=str&rescan=0` →
    `{"ok": True, "count": int, "models": [record], "stale_root_ids": [...]}`
  - `GET /models/{model_id}` → `{"ok": True, "model": record}` or 404
  - `GET /ckpts` **unchanged** with no params; new optional `root_ids=` (comma-separated) returns
    the merged multi-root entry list in the SAME entry shape plus `root_id` per entry.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_render_server_models_api.py`:

```python
"""API-shape tests for the model/roots endpoints.

The server module imports torch and loads a model at __main__ time only, so the
FastAPI app object can be imported and exercised with TestClient on CPU.
"""
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_roots_lists_every_configured_root_with_availability(client):
    r = client.get("/roots")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    ids = {x["id"] for x in body["roots"]}
    assert {"local_dora", "lumi_uuid", "lumi_mantu", "control"} <= ids
    for x in body["roots"]:
        assert set(x) >= {"id", "label", "path", "available", "enabled", "priority"}


def test_models_returns_records_and_supports_family_filter(client):
    r = client.get("/models", params={"family": "adapter"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert all(m["family"] == "adapter" for m in body["models"])
    if body["models"]:
        m = body["models"][0]
        assert set(m) >= {"id", "path", "root_id", "family", "label",
                          "loadable", "load_cost_gb", "provenance"}


def test_models_by_id_round_trips(client):
    body = client.get("/models").json()
    if not body["models"]:
        pytest.skip("no checkpoints reachable — is a drive unmounted?")
    mid = body["models"][0]["id"]
    r = client.get(f"/models/{mid}")
    assert r.status_code == 200 and r.json()["model"]["id"] == mid
    assert client.get("/models/MDB-deadbeef").status_code == 404


def test_ckpts_with_no_params_keeps_its_legacy_response_shape(client):
    r = client.get("/ckpts")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert set(body) >= {"ok", "root", "cached", "scanned_at", "count", "ckpts"}
        if body["ckpts"]:
            assert set(body["ckpts"][0]) >= {"path", "name", "mtime", "size", "kind"}


def test_ckpts_with_root_ids_merges_roots_and_tags_each_entry(client):
    r = client.get("/ckpts", params={"root_ids": "local_dora,lumi_uuid"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "roots" in body
    if body["ckpts"]:
        assert all("root_id" in c for c in body["ckpts"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_models_api.py -v`
Expected: FAIL — `/roots` and `/models` return 404.

- [ ] **Step 3: Wire the modules into the server constants**

In `/home/kim/Projects/SAO/eval/explorer_render_server.py`, after the existing `_MANTU` block
(line 81), add:

```python
import model_db                                   # noqa: E402
import model_roots                                # noqa: E402

_ROOTS_CFG = model_roots.load_config()
_LIMITS = model_roots.limits(_ROOTS_CFG)


def _root_by_id(rid):
    for r in model_roots.resolve_roots(_ROOTS_CFG):
        if r.id == rid:
            return r
    return None


def _default_scan_root():
    """Backwards compat: the pinned root the picker used before multi-root."""
    r = _root_by_id("local_dora")
    return Path(r.path) if r and r.path else Path(f"{_MANTU}/sa3_lora_runs")
```

and replace line 93 `CKPT_SCAN_ROOT = Path(f"{_MANTU}/sa3_lora_runs")` with:

```python
CKPT_SCAN_ROOT = _default_scan_root()      # legacy single-root default (compat)
```

- [ ] **Step 4: Add the endpoints**

In the same file, immediately after the existing `/ckpts` handler (after line 627), add:

```python
@app.get("/roots")
def roots():
    """Configured checkpoint roots + live availability. The GUI's root selector
    is fed from here; an unmounted removable drive comes back available=false
    rather than as an error."""
    out = model_db.load_or_build(rescan=False)
    counts = {}
    for m in out["models"]:
        counts[m["root_id"]] = counts.get(m["root_id"], 0) + 1
    rows = []
    for r in model_roots.resolve_roots(_ROOTS_CFG):
        d = r.as_dict()
        d["count"] = counts.get(r.id, 0)
        rows.append(d)
    return {"ok": True, "roots": rows, "stale_root_ids": out["stale_root_ids"],
            "limits": _LIMITS}


@app.get("/models")
def models(root_ids: str = None, family: str = None, corpus: str = None,
           q: str = None, loadable: int = None, rescan: int = 0):
    """The model database. Every field is either detected from the checkpoint,
    read from the run's run_meta.json, or a human verdict from
    Misc/models_index_overrides.json -- record["provenance"] says which."""
    ids = [s for s in (root_ids or "").split(",") if s] or None
    out = model_db.load_or_build(ids, rescan=bool(rescan))
    ms = out["models"]
    if family:
        ms = [m for m in ms if m["family"] == family]
    if corpus:
        ms = [m for m in ms if (m.get("corpus") or "") == corpus]
    if loadable is not None:
        ms = [m for m in ms if bool(m["loadable"]) == bool(loadable)]
    if q:
        ql = q.lower()
        ms = [m for m in ms
              if ql in m["path"].lower() or ql in (m.get("label") or "").lower()]
    return {"ok": True, "count": len(ms), "models": ms,
            "stale_root_ids": out["stale_root_ids"]}


@app.get("/models/{model_id}")
def model_one(model_id: str):
    for m in model_db.load_or_build(rescan=False)["models"]:
        if m["id"] == model_id:
            return {"ok": True, "model": m}
    return JSONResponse({"ok": False, "error": f"no model {model_id!r}"},
                        status_code=404)
```

- [ ] **Step 5: Extend `/ckpts` without breaking it**

Replace the signature and opening of the existing `/ckpts` handler (line 583-587) with:

```python
@app.get("/ckpts")
def ckpts(rescan: int = 0, root: str = None, root_ids: str = None):
    """Checkpoint journal for the GUI picker.

    LEGACY (no params / root=): unchanged -- single root, the /tmp journal keyed
    by root path, rescan=1 re-walks. Callers written before multi-root see the
    exact same response shape.

    NEW (root_ids=a,b): merged multi-root listing from the model DB. Entries keep
    the legacy keys and gain root_id + family + label so the picker can render a
    useful option label without a second request.
    """
    if root_ids:
        ids = [s for s in root_ids.split(",") if s]
        out = model_db.load_or_build(ids, rescan=bool(rescan))
        entries = [{"path": m["path"],
                    "name": str(Path(m["path"]).relative_to(m["_root_path"]))
                            if m.get("_root_path") else Path(m["path"]).name,
                    "mtime": m["mtime"], "size": m["size"], "kind": m["kind"],
                    "root_id": m["root_id"], "family": m["family"],
                    "label": m["label"], "epoch": m["epoch"], "step": m["step"],
                    "rank": m["rank"], "corpus": m.get("corpus"),
                    "verdict": m.get("verdict")}
                   for m in out["models"]]
        entries.sort(key=lambda e: e["mtime"], reverse=True)
        return {"ok": True, "roots": out["roots"], "cached": not rescan,
                "scanned_at": time.time(), "count": len(entries),
                "ckpts": entries, "stale_root_ids": out["stale_root_ids"]}
    rootp = Path(root) if root else CKPT_SCAN_ROOT
    # ... existing body unchanged from here ...
```

Also add `"_root_path"` to each record in `model_db.record_for` (set it to `str(base)`) so `name`
can be made relative; keep it underscore-prefixed to mark it as an internal field.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_models_api.py test_model_db.py -v`
Expected: all passed.

- [ ] **Step 7: Live-verify against the running server**

Check `/tmp/gpu.lock` and `rocm-smi --showpids` first. Then start the server and probe it:

```bash
cd /home/kim/Projects/SAO && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  MIOPEN_FIND_MODE=2 .venv/bin/python eval/explorer_render_server.py --port 8056 &
sleep 90
curl -s localhost:8056/roots | python3 -m json.tool | head -40
curl -s 'localhost:8056/models?family=fullft' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["count"]); print(d["models"][0] if d["models"] else None)'
curl -s localhost:8056/ckpts | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["root"], d["count"])'
curl -s 'localhost:8056/ckpts?root_ids=lumi_uuid,local_dora' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["count"], sorted({c["root_id"] for c in d["ckpts"]}))'
```
Expected: `/roots` lists 4 roots with true/false availability; `/models?family=fullft` returns the
`fullft` arms from the UUID drive; legacy `/ckpts` reports ~162 under `sa3_lora_runs`; the merged
call reports several hundred across both root ids. **A stale server process silently ignoring new
keys has bitten this codebase before — confirm the process you are curling is the patched one
(`ps aux | grep explorer_render_server`).**

- [ ] **Step 8: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/explorer_render_server.py eval/test_render_server_models_api.py eval/model_db.py
git commit -m "render server: /roots + /models + multi-root /ckpts

Closes INFERENCE-SURFACE section 9 item 1 (the picker was pinned to
sa3_lora_runs; the LUMI families were reachable only by typing a path) and item 6
(riffer_*.pt control runs are now scanned). Legacy /ckpts with no params is
byte-shape identical.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 5: Resident adapter slots + VRAM budget

**Files:**
- Create: `/home/kim/Projects/SAO/eval/adapter_slots.py`
- Test: `/home/kim/Projects/SAO/eval/test_adapter_slots.py`

**Interfaces:**
- Consumes: `model_db` records (for `load_cost_gb`, `family`), `model_roots.limits`.
- Produces:
  - `@dataclass Slot: index: int, path: str, label: str, family: str, cost_gb: float, strength: float`
  - `class SlotTable`:
    - `__init__(self, max_slots: int = 4, vram_floor_gb: float = 6.0, free_gb_fn=None)`
    - `plan(self, specs: list[dict]) -> dict` — `{"ok": bool, "slots": [Slot], "reason": str, "projected_free_gb": float, "rebuild": bool}`; pure, no model touched
    - `apply(self, model, specs: list[dict]) -> dict` — clears via `remove_lora_by_index`, then ONE `load_lora(paths)`; returns the plan
    - `lora_configs(self, active: int | None) -> list[dict]` — **covers every resident index**
    - `strengths(self, active: int | None, strength: float) -> list[tuple[int, float]]`
    - `as_dict(self) -> dict`
  - `free_vram_gb() -> float`

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_adapter_slots.py`:

```python
import pytest

import adapter_slots


class FakeLoraModel:
    """Records the calls the slot table makes, so slot logic is testable on CPU."""
    def __init__(self):
        self.loaded = []
        self.removed = []
        self.strengths = {}

    def load_lora(self, paths):
        self.loaded.append(list(paths))

    def set_lora_strength(self, s, lora_index=None):
        self.strengths[lora_index] = s


def _specs(*paths):
    return [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.33}
            for p in paths]


def test_plan_accepts_slots_that_fit_the_vram_floor():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=6.0,
                                free_gb_fn=lambda: 10.0)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is True
    assert [s.index for s in plan["slots"]] == [0, 1, 2]
    assert plan["projected_free_gb"] == pytest.approx(10.0 - 3 * 0.33)


def test_plan_refuses_rather_than_oom_when_the_floor_would_be_crossed():
    t = adapter_slots.SlotTable(max_slots=8, vram_floor_gb=6.0,
                                free_gb_fn=lambda: 6.2)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is False
    assert "floor" in plan["reason"].lower()


def test_plan_refuses_more_than_max_slots():
    t = adapter_slots.SlotTable(max_slots=2, vram_floor_gb=0.0,
                                free_gb_fn=lambda: 99.0)
    plan = t.plan(_specs("a", "b", "c"))
    assert plan["ok"] is False and "max" in plan["reason"].lower()


def test_max_slots_of_one_reproduces_todays_single_adapter_behaviour():
    t = adapter_slots.SlotTable(max_slots=1, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    assert t.plan(_specs("a"))["ok"] is True
    assert t.plan(_specs("a", "b"))["ok"] is False


def test_apply_clears_every_existing_index_then_loads_the_full_list_once():
    """load_and_apply_loras re-indexes from 0 on each call, so an incremental add
    would collide with index 0. The only safe update is remove-all + one load."""
    m = FakeLoraModel()
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(m, _specs("a", "b"))
    t.apply(m, _specs("a", "b", "c"))
    assert m.loaded == [["a", "b"], ["a", "b", "c"]]
    assert m.removed == [0, 1], "both prior indices must be removed before reload"


def test_apply_is_a_noop_when_the_slot_set_is_unchanged():
    m = FakeLoraModel()
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(m, _specs("a", "b"))
    plan = t.apply(m, _specs("a", "b"))
    assert plan["rebuild"] is False
    assert m.loaded == [["a", "b"]], "an unchanged set must not reload"


def test_lora_configs_covers_every_resident_index_not_just_the_active_one():
    """dit.py only touches indices present in lora_configs; an omitted index keeps
    its last enable state, so 'A vs B' would silently become 'A+B'."""
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b", "c"))
    cfgs = t.lora_configs(active=1)
    assert sorted(c["lora_index"] for c in cfgs) == [0, 1, 2]
    active = [c for c in cfgs if c["lora_index"] == 1][0]
    assert active["interval"] == (0.0, 1.0)
    for c in cfgs:
        if c["lora_index"] != 1:
            lo, hi = c["interval"]
            assert lo > 1.0, "an inactive slot needs an interval sigma can never satisfy"


def test_lora_configs_honours_a_custom_interval_on_the_active_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b"))
    cfgs = t.lora_configs(active=0, interval=(0.25, 1.0))
    assert [c for c in cfgs if c["lora_index"] == 0][0]["interval"] == (0.25, 1.0)


def test_strengths_zero_every_inactive_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b", "c"))
    assert dict(t.strengths(active=2, strength=1.4)) == {0: 0.0, 1: 0.0, 2: 1.4}


def test_active_none_silences_every_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    t.apply(FakeLoraModel(), _specs("a", "b"))
    assert dict(t.strengths(active=None, strength=1.0)) == {0: 0.0, 1: 0.0}
    for c in t.lora_configs(active=None):
        assert c["interval"][0] > 1.0


def test_a_fullft_spec_is_rejected_as_a_slot():
    t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0,
                               free_gb_fn=lambda: 99.0)
    plan = t.plan([{"path": "f", "label": "f", "family": "fullft", "cost_gb": 2.8}])
    assert plan["ok"] is False and "fullft" in plan["reason"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_adapter_slots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapter_slots'`

- [ ] **Step 3: Write the module**

Create `/home/kim/Projects/SAO/eval/adapter_slots.py`:

```python
"""Resident adapter slots -- A/B between models with no offload and no reload.

The mechanism already exists in the SA3 fork and this module only drives it:

  stable_audio_3/model.py:72        load_lora(paths)  -> lora_index = enumerate(paths)
  models/lora/utils.py              enable_lora / disable_lora(model, lora_index=i)
  models/lora/model.py:530          set_lora_strength(s, lora_index=i)
  models/lora/model.py:507          remove_lora_by_index(model, i)
  models/dit.py:472-486             per-index gating INSIDE the forward, every step,
                                    from lora_configs=[{"lora_index", "interval",
                                    "layer_filter"}]

TWO TRAPS, both silent:

1. dit.py only touches indices that APPEAR in lora_configs. An omitted index keeps
   whatever enable/disable state it last had, so an "A vs B" render can quietly be
   "A+B". Therefore lora_configs() ALWAYS covers every resident index, and an
   inactive slot gets an interval sigma can never satisfy (plus strength 0).

2. load_and_apply_loras re-indexes from 0 on every call, so calling load_lora()
   again to ADD one adapter collides with index 0. Changing the resident SET must
   be remove_lora_by_index for every index, then ONE load_lora(full list).
   Switching between already-resident adapters costs nothing.

VRAM (measured 2026-08-23): baseline resident is ~5.1 GB (DiT ~2.8 + SAME-L ~1.7
+ T5-Gemma ~0.6, all half); a DoRA r128 adds ~0.33 GB, r64 ~0.16 GB. On a 17.1 GB
card that is ~2% per extra model, which is why "one base + N adapters" beats "two
backbones" (+5.1 GB) for A/B.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# An interval sigma is never inside, so dit.py calls disable_lora on this slot
# every step. Belt to the strength-0 braces.
_OFF_INTERVAL = (2.0, 3.0)
_ON_INTERVAL = (0.0, 1.0)


@dataclass
class Slot:
    index: int
    path: str
    label: str
    family: str
    cost_gb: float
    strength: float = 1.0

    def as_dict(self) -> dict:
        return asdict(self)


def free_vram_gb() -> float:
    """Live free VRAM. The latent player (:7892) and a non-team instance sharing
    this GPU both eat into it, so never assume -- measure."""
    try:
        import torch
        free, _total = torch.cuda.mem_get_info()
        return free / 1e9
    except Exception:
        return 0.0


class SlotTable:
    def __init__(self, max_slots: int = 4, vram_floor_gb: float = 6.0,
                 free_gb_fn=None):
        self.max_slots = int(max_slots)
        self.vram_floor_gb = float(vram_floor_gb)
        self._free_gb_fn = free_gb_fn or free_vram_gb
        self.slots: list[Slot] = []

    # ---------------------------------------------------------------- planning
    def plan(self, specs: list[dict]) -> dict:
        cur = [s.path for s in self.slots]
        want = [s["path"] for s in specs]
        rebuild = cur != want
        slots = [Slot(index=i, path=s["path"], label=s.get("label") or s["path"],
                      family=s.get("family", "adapter"),
                      cost_gb=float(s.get("cost_gb", 0.33)),
                      strength=float(s.get("strength", 1.0)))
                 for i, s in enumerate(specs)]
        bad = [s for s in slots if s.family != "adapter"]
        if bad:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": self._free_gb_fn(),
                    "reason": (f"{bad[0].family} cannot be a slot: only adapters share "
                               "one base. Use the full-FT backbone swap instead.")}
        if len(slots) > self.max_slots:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": self._free_gb_fn(),
                    "reason": f"{len(slots)} slots requested, max is {self.max_slots}"}
        free = self._free_gb_fn()
        added = sum(s.cost_gb for s in slots) - sum(s.cost_gb for s in self.slots)
        projected = free - max(added, 0.0)
        if projected < self.vram_floor_gb:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": round(projected, 2),
                    "reason": (f"would leave {projected:.2f} GB free, below the "
                               f"{self.vram_floor_gb:.1f} GB floor "
                               "(a T4096 render needs the headroom)")}
        return {"ok": True, "rebuild": rebuild, "slots": slots,
                "projected_free_gb": round(projected, 2), "reason": ""}

    # ---------------------------------------------------------------- applying
    def apply(self, model, specs: list[dict]) -> dict:
        plan = self.plan(specs)
        if not plan["ok"]:
            return plan
        if not plan["rebuild"]:
            self.slots = plan["slots"]
            return plan
        from stable_audio_3.models.lora import remove_lora_by_index
        for s in self.slots:
            remove_lora_by_index(model.model.model, s.index)
            remove_lora_by_index(model.model.conditioner, s.index)
            if hasattr(model, "removed"):        # test double
                model.removed.append(s.index)
        paths = [s.path for s in plan["slots"]]
        if paths:
            model.load_lora(paths)
        self.slots = plan["slots"]
        return plan

    # ---------------------------------------------------------------- driving
    def lora_configs(self, active: int | None,
                     interval: tuple[float, float] = _ON_INTERVAL,
                     layer_filter: str = "") -> list[dict]:
        """ALWAYS covers every resident index -- see trap 1 in the module docstring."""
        return [{"lora_index": s.index,
                 "interval": tuple(interval) if s.index == active else _OFF_INTERVAL,
                 "layer_filter": layer_filter if s.index == active else ""}
                for s in self.slots]

    def strengths(self, active: int | None, strength: float) -> list[tuple[int, float]]:
        return [(s.index, float(strength) if s.index == active else 0.0)
                for s in self.slots]

    def push_strengths(self, model, active: int | None, strength: float) -> None:
        for idx, val in self.strengths(active, strength):
            model.set_lora_strength(val, lora_index=idx)

    def as_dict(self) -> dict:
        return {"slots": [s.as_dict() for s in self.slots],
                "max_slots": self.max_slots,
                "vram_floor_gb": self.vram_floor_gb,
                "free_gb": round(self._free_gb_fn(), 2)}
```

Also add `self.removed = []` handling: the test double exposes `.removed`; the real
`StableAudioModel` does not, which the `hasattr` guard covers. Add `removed = []` to
`FakeLoraModel` (already in the test).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_adapter_slots.py -v`
Expected: 11 passed.

- [ ] **Step 5: GPU integration check — prove remove+reload really reverts the base weights**

This is the one claim that must not be taken on trust: `remove_lora_by_index` with
`leave_parametrized=False` is supposed to restore the original weight. If it does not, changing the
slot set silently corrupts the base. Check `/tmp/gpu.lock` and `rocm-smi --showpids` first, then:

```bash
cd /home/kim/Projects/SAO && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  .venv/bin/python - <<'PY'
import sys, torch
sys.path.insert(0, "eval")
from stable_audio_3 import StableAudioModel
from stable_audio_3.models.lora import remove_lora_by_index
import adapter_slots, model_db

m = StableAudioModel.from_pretrained("medium-base", device="cuda")
ref = {k: v.detach().clone() for k, v in list(m.model.model.state_dict().items())[:50]}
base_free = torch.cuda.mem_get_info()[0] / 1e9
print("free after base load: %.2f GB" % base_free)

adapters = [x["path"] for x in model_db.load_or_build()["models"]
            if x["family"] == "adapter" and x["slim"] and x["rank"] == 128][:2]
assert len(adapters) == 2, adapters
t = adapter_slots.SlotTable(max_slots=4, vram_floor_gb=0.0)
print(t.apply(m, [{"path": p, "label": p, "family": "adapter", "cost_gb": 0.33}
                  for p in adapters]))
two_free = torch.cuda.mem_get_info()[0] / 1e9
print("free with 2 resident adapters: %.2f GB  (delta %.2f GB)"
      % (two_free, base_free - two_free))

t.apply(m, [{"path": adapters[0], "label": "solo", "family": "adapter", "cost_gb": 0.33}])
after = m.model.model.state_dict()
maxdiff = max((ref[k] - after[k]).abs().max().item() for k in ref if k in after)
print("max |base weight drift| after remove+reload:", maxdiff)
assert maxdiff < 1e-5, "remove_lora_by_index did NOT revert the base weights"
print("OK")
PY
```
Expected: the two-adapter delta is **~0.6–0.7 GB** (2 × ~0.33), confirming the residency estimate,
and `max |base weight drift|` is ~0. **If the drift assertion fails, stop** — the slot design needs
a full `from_pretrained` on set change instead, and the plan's cost claims must be revised.

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/adapter_slots.py eval/test_adapter_slots.py
git commit -m "adapter_slots: N resident adapters on one base, A/B with no offload

Drives the multi-LoRA support that already exists in the fork (load_lora assigns
lora_index; dit.py gates per-index every step). Guards the two silent traps:
lora_configs always covers EVERY resident index (an omitted one keeps its last
enable state -> 'A vs B' becomes 'A+B'), and a set change is remove-all + one
load (load_and_apply_loras re-indexes from 0). ~0.33 GB per r128 adapter vs
+5.1 GB for a second backbone.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 6: Server — `/slots` and `dora.slot` on every render endpoint

**Files:**
- Modify: `/home/kim/Projects/SAO/eval/explorer_render_server.py` — globals (~line 105), `with_lora_interval` (388-393), `prepare_model` (394-441), `_resolve_dora` (316-330), new endpoints
- Test: `/home/kim/Projects/SAO/eval/test_render_server_slots_api.py` (create)

**Interfaces:**
- Consumes: `adapter_slots.SlotTable`, `model_db.load_or_build`, `model_roots.limits`.
- Produces (HTTP):
  - `GET /slots` → `{"ok": True, "slots": [...], "max_slots": int, "vram_floor_gb": float, "free_gb": float, "active": int|None, "backbone": str}`
  - `POST /slots` body `{"slots": [{"ckpt_path": str, "label": str?}], "activate": int|None}` → same shape, or 4xx with `reason`
  - render payload extension: `{"dora": {"slot": int, "strength": float, "interval_min": float, "interval_max": float}}`. `slot` absent ⇒ today's path exactly.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_render_server_slots_api.py`:

```python
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_slots_starts_empty_and_reports_the_budget(client):
    body = client.get("/slots").json()
    assert body["ok"] is True
    assert body["slots"] == []
    assert body["max_slots"] >= 1
    assert body["vram_floor_gb"] > 0
    assert body["active"] is None


def test_resolve_dora_req_passes_a_slot_through(client):
    import explorer_render_server as srv
    req = {"dora": {"slot": 2, "strength": 1.4}}
    out = srv.resolve_dora_req(req)
    assert out["slot"] == 2 and out["strength"] == 1.4


def test_resolve_dora_req_without_a_slot_is_unchanged(client):
    import explorer_render_server as srv
    assert srv.resolve_dora_req({"dora": {"name": "hof", "strength": 0.8}})["slot"] is None
    assert srv.resolve_dora_req({"ckpt_path": "/x.ckpt"})["ckpt_path"] == "/x.ckpt"
    assert srv.resolve_dora_req({})["slot"] is None


def test_posting_an_unknown_path_is_rejected_not_silently_ignored(client):
    r = client.post("/slots", json={"slots": [{"ckpt_path": "/does/not/exist.ckpt"}]})
    assert r.status_code >= 400
    assert "reason" in r.json() or "error" in r.json()


def test_posting_a_fullft_path_as_a_slot_is_rejected_with_a_useful_reason(client):
    import explorer_render_server as srv
    ms = [m for m in srv.model_db.load_or_build()["models"] if m["family"] == "fullft"]
    if not ms:
        pytest.skip("no fullft checkpoint reachable")
    r = client.post("/slots", json={"slots": [{"ckpt_path": ms[0]["path"]}]})
    assert r.status_code >= 400
    assert "fullft" in (r.json().get("reason", "") + r.json().get("error", "")).lower()


def test_with_lora_interval_is_no_longer_pinned_to_index_zero(client):
    import explorer_render_server as srv
    srv.SLOTS.slots = [
        srv.adapter_slots.Slot(0, "a", "a", "adapter", 0.33),
        srv.adapter_slots.Slot(1, "b", "b", "adapter", 0.33),
    ]
    srv.ACTIVE_SLOT = 1
    kw = srv.with_lora_interval({})
    idxs = sorted(c["lora_index"] for c in kw["lora_configs"])
    assert idxs == [0, 1], "every resident index must be gated, not just index 0"
    srv.SLOTS.slots, srv.ACTIVE_SLOT = [], None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_slots_api.py -v`
Expected: FAIL — `/slots` 404, `SLOTS` attribute missing.

- [ ] **Step 3: Add the slot globals and generalise `with_lora_interval`**

In `/home/kim/Projects/SAO/eval/explorer_render_server.py`, after the `LOADED_STRENGTH` globals
(~line 106) add:

```python
import adapter_slots                              # noqa: E402

SLOTS = adapter_slots.SlotTable(
    max_slots=int(_LIMITS["max_resident_adapters"]),
    vram_floor_gb=float(_LIMITS["vram_floor_gb"]))
ACTIVE_SLOT: int | None = None      # which resident slot renders; None = base only
```

Replace `with_lora_interval` (lines 388-393) entirely with:

```python
def with_lora_interval(kw):
    """Attach per-request LoRA gating.

    Slot mode: EVERY resident index is gated -- dit.py:472 only touches indices
    present in lora_configs, so an omitted slot keeps its last enable state and an
    'A vs B' render silently becomes 'A+B'.

    Legacy mode (no slots): unchanged -- index 0, sigma-interval gating only
    (Kim 2026-07-12; native sigma semantics, dit.py:466).
    """
    if SLOTS.slots:
        kw.setdefault("lora_configs",
                      SLOTS.lora_configs(ACTIVE_SLOT, interval=CURRENT_LORA_INTERVAL))
        return kw
    if LOADED_DORA not in (None, "none") and CURRENT_LORA_INTERVAL != (0.0, 1.0):
        kw.setdefault("lora_configs", [{"lora_index": 0,
                                        "interval": CURRENT_LORA_INTERVAL}])
    return kw
```

- [ ] **Step 4: Thread `slot` through `resolve_dora_req` and `prepare_model`**

In `resolve_dora_req` (line 190), ensure the returned dict carries `"slot"`:

```python
def resolve_dora_req(req):
    """Fold a top-level ckpt_path into the dora dict consumed by _resolve_dora (an
    explicit dora.ckpt_path still wins). Adds "slot": a resident-slot index, or
    None for the legacy single-adapter path."""
    d = dict(req.get("dora") or {})
    if not d.get("ckpt_path") and req.get("ckpt_path"):
        d["ckpt_path"] = req["ckpt_path"]
    d.setdefault("slot", None)
    if d["slot"] is not None:
        d["slot"] = int(d["slot"])
    return d
```

In `prepare_model` (line 394), add a slot short-circuit at the top of the body, after the
`CURRENT_LORA_INTERVAL` assignment:

```python
    global ACTIVE_SLOT
    slot = (dora_req or {}).get("slot")
    if slot is not None:
        if not any(s.index == slot for s in SLOTS.slots):
            raise ValueError(f"slot {slot} is not resident "
                             f"(have {[s.index for s in SLOTS.slots]}) — POST /slots first")
        ACTIVE_SLOT = slot
        SLOTS.push_strengths(MODEL, slot, _f(dora_req, "strength", 1.0))
        if film_req:
            film_ckpt = require_path(film_req.get("ckpt") or FILM_DEFAULT_CKPT,
                                     "FiLM checkpoint")
            if FILM_LOADED != film_ckpt:
                _install_film(film_ckpt)
        return False        # never a rebuild: this is the whole point of slots
```

- [ ] **Step 5: Add the `/slots` endpoints**

After `/models/{model_id}` add:

```python
def _slots_payload():
    d = SLOTS.as_dict()
    d.update(ok=True, active=ACTIVE_SLOT, backbone=ARGS.model if ARGS else None)
    return d


@app.get("/slots")
def slots_get():
    """The resident adapter table. A/B between these costs no reload and no
    offload: the render payload just names {"dora": {"slot": i}}."""
    return _slots_payload()


@app.post("/slots")
async def slots_post(request: Request):
    """Declare the resident adapter SET.

    Body: {"slots": [{"ckpt_path": str, "label": str?}], "activate": int|null}
    Changing the set costs one remove+reload (no disk re-read of the base);
    switching between already-resident slots costs nothing. fullft checkpoints
    are rejected -- they change the base and cannot share it.
    """
    global ACTIVE_SLOT
    req = json.loads((await request.body()) or b"{}")
    by_path = {m["path"]: m for m in model_db.load_or_build()["models"]}
    specs = []
    for s in req.get("slots") or []:
        p = s.get("ckpt_path")
        rec = by_path.get(p)
        if rec is None:
            if not p or not Path(p).is_file():
                return JSONResponse(
                    {"ok": False, "reason": f"unknown checkpoint {p!r} "
                     "(not in any configured root and not a readable path)"},
                    status_code=400)
            rec = {"family": ckpt_probe.probe(p)["family"], "load_cost_gb": 0.33,
                   "label": Path(p).stem}
        specs.append({"path": p, "label": s.get("label") or rec.get("label") or p,
                      "family": rec["family"],
                      "cost_gb": float(rec.get("load_cost_gb") or 0.33)})
    with GPU_LOCK:
        if MODEL is None:
            return JSONResponse({"ok": False, "reason": "model not loaded"},
                                status_code=503)
        plan = SLOTS.apply(MODEL, specs)
        if not plan["ok"]:
            return JSONResponse({"ok": False, "reason": plan["reason"],
                                 "projected_free_gb": plan["projected_free_gb"]},
                                status_code=400)
        act = req.get("activate")
        ACTIVE_SLOT = int(act) if act is not None else (0 if SLOTS.slots else None)
        SLOTS.push_strengths(MODEL, ACTIVE_SLOT, 1.0)
        # slots supersede the legacy single-adapter state machine
        global LOADED_DORA, LOADED_STRENGTH
        LOADED_DORA, LOADED_STRENGTH = "slots", 1.0
        log(f"[slots] {[s.label for s in SLOTS.slots]} active={ACTIVE_SLOT} "
            f"free={plan['projected_free_gb']} GB")
    return _slots_payload()
```

Add `import ckpt_probe  # noqa: E402` next to the other new imports.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_slots_api.py test_adapter_slots.py -v`
Expected: all passed.

- [ ] **Step 7: Live GPU verification of a no-reload A/B**

Check `/tmp/gpu.lock` + `rocm-smi --showpids`, restart the server on the patched code (a stale
process silently ignoring new keys has bitten this codebase — confirm with `ps aux`), then:

```bash
A=$(curl -s 'localhost:8056/models?family=adapter&loadable=1' | python3 -c 'import json,sys; m=[x for x in json.load(sys.stdin)["models"] if x["slim"]][:2]; print(m[0]["path"]); print(m[1]["path"])')
P1=$(echo "$A" | head -1); P2=$(echo "$A" | tail -1)
curl -s -X POST localhost:8056/slots -H 'content-type: application/json' \
  -d "{\"slots\":[{\"ckpt_path\":\"$P1\"},{\"ckpt_path\":\"$P2\"}],\"activate\":0}" | python3 -m json.tool
for S in 0 1; do
  /usr/bin/time -f "slot $S: %e s" curl -s -X POST localhost:8056/generate -H 'content-type: application/json' \
    -d "{\"prompt\":\"goa trance, 148 bpm\",\"duration\":30,\"steps\":16,\"cfg_scale\":7,\"seed\":4242,\"dora\":{\"slot\":$S,\"strength\":1.0}}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["urls"], d["meta"]["model_rebuilt"], d["meta"]["dora_loaded"])'
done
curl -s localhost:8056/slots | python3 -m json.tool
```
Expected: both renders report `model_rebuilt: false`; the two wavs differ audibly (same seed, same
prompt, different adapter); `free_gb` after loading two slots is ~0.66 GB below the one-slot value.
**The falsification to run explicitly:** render slot 0, then slot 1, then slot 0 again — the two
slot-0 renders must be bit-identical (`cmp` the `.z0.npy`). If they are not, `lora_configs` is not
covering every index and slot 1 is leaking into slot 0.

- [ ] **Step 8: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/explorer_render_server.py eval/test_render_server_slots_api.py
git commit -m "render server: /slots + dora.slot — A/B with no reload, no offload

prepare_model short-circuits on a slot: strengths flip, no rebuild.
with_lora_interval no longer pins lora_index 0. Legacy dora payloads (no slot)
take the unchanged path.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 7: Server — `POST /ab`, one payload rendered across slots

**Files:**
- Modify: `/home/kim/Projects/SAO/eval/explorer_render_server.py` — add `/ab` after `/generate` (line 703)
- Test: `/home/kim/Projects/SAO/eval/test_render_server_ab.py` (create)

**Interfaces:**
- Consumes: the server's existing `_generate` body, `SLOTS`, `resolve_seed`.
- Produces (HTTP): `POST /ab` body = any `/generate` payload plus
  `{"ab": {"slots": [int|null], "strengths": [float]?}}` →
  `{"ok": True, "job_id": str, "arms": [{"slot": int|null, "label": str, "files": [...], "urls": [...], "z0": [...]}], "seed": int, "timings": {...}}`.
  `null` in `slots` means the bare base (no adapter) — the control arm.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/test_render_server_ab.py`:

```python
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    import explorer_render_server as srv
    return fastapi_testclient.TestClient(srv.app)


def test_ab_rejects_a_slot_that_is_not_resident(client):
    r = client.post("/ab", json={"prompt": "x", "duration": 5,
                                 "ab": {"slots": [0, 9]}})
    assert r.status_code >= 400
    assert "resident" in (r.json().get("error", "") + r.json().get("reason", "")).lower()


def test_ab_requires_at_least_two_arms(client):
    r = client.post("/ab", json={"prompt": "x", "duration": 5, "ab": {"slots": [0]}})
    assert r.status_code >= 400


def test_ab_resolves_one_seed_and_reuses_it_across_arms(client):
    import explorer_render_server as srv
    payload = {"prompt": "x", "duration": 5, "seed": -1, "ab": {"slots": [None, None]}}
    seeds = srv._ab_arm_payloads(payload)
    assert len({p["seed"] for p in seeds}) == 1
    assert seeds[0]["seed"] > 0, "seed -1 must be resolved ONCE, not per arm"


def test_ab_arm_payloads_carry_the_slot_and_drop_the_ab_block(client):
    import explorer_render_server as srv
    payload = {"prompt": "x", "duration": 5, "seed": 7,
               "ab": {"slots": [0, 1], "strengths": [1.0, 1.5]}}
    arms = srv._ab_arm_payloads(payload)
    assert [a["dora"]["slot"] for a in arms] == [0, 1]
    assert [a["dora"]["strength"] for a in arms] == [1.0, 1.5]
    assert all("ab" not in a for a in arms)


def test_a_null_slot_arm_renders_the_bare_base_as_the_control(client):
    import explorer_render_server as srv
    arms = srv._ab_arm_payloads({"prompt": "x", "duration": 5, "seed": 7,
                                 "ab": {"slots": [None, 0]}})
    assert arms[0]["dora"]["name"] == "none"
    assert arms[0]["dora"]["slot"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_ab.py -v`
Expected: FAIL — `AttributeError: module 'explorer_render_server' has no attribute '_ab_arm_payloads'`

- [ ] **Step 3: Implement**

In `/home/kim/Projects/SAO/eval/explorer_render_server.py`, after the `/generate` route add:

```python
def _ab_arm_payloads(req):
    """Split one payload into per-arm payloads.

    The seed is resolved ONCE and shared -- an A/B on different noise is not an
    A/B. Everything else (prompt, cfg, steps, latch slots, film, duration) is
    identical by construction, which is the point: only the model varies.
    A null slot renders the bare base as the control arm.
    """
    ab = req.get("ab") or {}
    slots = ab.get("slots") or []
    strengths = ab.get("strengths") or [1.0] * len(slots)
    seed = resolve_seed(_i(req, "seed", -1))
    arms = []
    for i, s in enumerate(slots):
        p = {k: v for k, v in req.items() if k != "ab"}
        p["seed"] = seed
        st = float(strengths[i]) if i < len(strengths) else 1.0
        p["dora"] = ({"name": "none", "slot": None, "strength": st} if s is None
                     else {"slot": int(s), "strength": st})
        arms.append(p)
    return arms


@app.post("/ab")
async def ab(request: Request):
    """Render ONE payload across several resident models, same seed, one job.

    This is a LOOP over the server's own /generate body -- not a second renderer
    and not a second guidance implementation. Arms name resident slots (see
    POST /slots), so no arm costs a reload or an offload.
    """
    req = json.loads((await request.body()) or b"{}")
    ab_req = req.get("ab") or {}
    slots = ab_req.get("slots")
    if not slots or len(slots) < 2:
        return JSONResponse({"ok": False, "error": "ab.slots needs >= 2 arms"},
                            status_code=400)
    resident = {s.index for s in SLOTS.slots}
    bad = [s for s in slots if s is not None and int(s) not in resident]
    if bad:
        return JSONResponse(
            {"ok": False, "error": f"slot(s) {bad} not resident "
             f"(have {sorted(resident)}) — POST /slots first"}, status_code=400)

    t0 = time.time()
    job_id, jd = new_job("ab")
    arms_out, stages = [], {}
    for i, arm_req in enumerate(_ab_arm_payloads(req)):
        s = arm_req["dora"].get("slot")
        label = ("base" if s is None
                 else next(x.label for x in SLOTS.slots if x.index == s))
        ta = time.time()
        resp = _generate(arm_req, job_id=job_id, file_prefix=f"ab{i}_{label}")
        stages[f"arm{i}_{label}"] = time.time() - ta
        arms_out.append({"slot": s, "label": label, "strength": arm_req["dora"]["strength"],
                         "files": resp["files"], "urls": resp["urls"]})
    out = {"ok": True, "status": "ok", "job_id": job_id, "arms": arms_out,
           "seed": arms_out and _ab_arm_payloads(req)[0]["seed"],
           "timings": {"total_sec": round(time.time() - t0, 1),
                       "per_stage": {k: round(v, 1) for k, v in stages.items()}},
           "meta": {"slots": SLOTS.as_dict(), "params_echo": req}}
    (jd / "result.json").write_text(json.dumps(out, indent=2, default=str))
    return out
```

**Refactor prerequisite:** the current `/generate` route body must be extracted into a reusable
`_generate(req, job_id=None, file_prefix=None)` so `/ab` can call it without duplicating a line of
render logic. Extract it verbatim — move the body of the existing handler into `_generate`, have
the route become `return _generate(json.loads(await request.body() or b"{}"))`, and add the two
optional kwargs so an arm can write into an existing job dir under a distinguishing prefix. **Do
not reimplement any part of it.**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest test_render_server_ab.py test_render_server_slots_api.py -v`
Expected: all passed.

- [ ] **Step 5: Live GPU verification**

```bash
curl -s -X POST localhost:8056/ab -H 'content-type: application/json' -d '{
  "prompt":"goa trance, acid lead, 148 bpm","duration":30,"steps":16,"cfg_scale":7,
  "seed":4242,"ab":{"slots":[null,0,1]}}' | python3 -m json.tool
```
Expected: three arms, one job dir, one shared seed, per-arm timings where arms 2 and 3 are close to
arm 1 (no reload cost). Listen: the base arm must differ from both adapter arms.

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/explorer_render_server.py eval/test_render_server_ab.py
git commit -m "render server: POST /ab — one payload, N resident models, one seed

A loop over the server's own extracted _generate body; no second renderer and no
second guidance implementation (resolve_latch still normalises gains once).
A null arm renders the bare base as the control.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

> **AMENDMENT 2026-08-24 (C) — a gap in this plan, already fixed outside it.** No task in this
> plan touches `mir/plots/explorer_sa3/controls.py:41` `_DORA_OPTIONS = ["none","hof","newstack",
> "evr1x"]` (zero references across all 3237 lines). Task 8 wires the *checkpoint* dropdown
> (`inf-ckpt-dd`), so the **DoRA picker** — the thing Kim actually reported as "no LoRAs or adapters
> at all" — would have stayed hardcoded through all ten tasks. Fixed directly: `controls.py` gained
> `_dora_options()` (model DB via `render_client.models(family="adapter", loadable=True)`, falling
> back to the four registry names when the server is unreachable, so the picker is never empty) and
> `steering_payload()` now sends a real path as `ckpt_path` and a bare registry name as `name`.
> No server change was needed — `_resolve_dora` (`explorer_render_server.py:338-342`) already
> accepts an arbitrary `ckpt_path` and bypasses `DORA_REGISTRY`. **Do not revert this while doing
> Tasks 8/9.**

### Task 8: Viewer — root selector + model-info panel

Runs in the **mir** repo, branch `sa3-latent-explorer`, **mir venv**.

**Files:**
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/render_client.py`
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/inference_tab.py:82-92` (picker), `:432-449` (journal callback)
- Test: `/home/kim/Projects/mir/plots/explorer_sa3/test_render_client_models.py` (create)

**Interfaces:**
- Consumes: `GET /roots`, `GET /models`, `GET /ckpts?root_ids=`.
- Produces:
  - `render_client.roots(timeout=10.0) -> dict | None`
  - `render_client.models(root_ids=None, family=None, corpus=None, q=None, rescan=False, timeout=60.0) -> dict | None`
  - `render_client.ckpts(rescan=False, root=None, root_ids=None, timeout=60.0) -> dict | None` (extended)
  - New Dash ids: `inf-root-dd` (multi), `inf-model-info`.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/mir/plots/explorer_sa3/test_render_client_models.py`:

```python
import types

import pytest

import render_client


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._p


def test_roots_hits_the_roots_endpoint(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen["url"], seen["params"] = url, params
        return _Resp({"ok": True, "roots": []})

    monkeypatch.setattr(render_client.requests, "get", fake_get)
    assert render_client.roots()["ok"] is True
    assert seen["url"].endswith("/roots")


def test_models_forwards_every_filter(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(url=url, params=params)
        return _Resp({"ok": True, "models": [], "count": 0})

    monkeypatch.setattr(render_client.requests, "get", fake_get)
    render_client.models(root_ids=["a", "b"], family="adapter", q="dora", rescan=True)
    assert seen["url"].endswith("/models")
    assert seen["params"]["root_ids"] == "a,b"
    assert seen["params"]["family"] == "adapter"
    assert seen["params"]["q"] == "dora"
    assert seen["params"]["rescan"] == 1


def test_ckpts_still_works_with_no_arguments(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(params=params)
        return _Resp({"ok": True, "ckpts": [], "root": "/r"})

    monkeypatch.setattr(render_client.requests, "get", fake_get)
    render_client.ckpts()
    assert seen["params"] == {"rescan": 0}, "legacy call must not gain params"


def test_ckpts_forwards_root_ids_as_a_comma_list(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(params=params)
        return _Resp({"ok": True, "ckpts": []})

    monkeypatch.setattr(render_client.requests, "get", fake_get)
    render_client.ckpts(root_ids=["lumi_uuid", "local_dora"])
    assert seen["params"]["root_ids"] == "lumi_uuid,local_dora"


def test_unreachable_server_returns_none_not_an_exception(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(render_client.requests, "get", boom)
    assert render_client.roots() is None
    assert render_client.models() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/mir/plots/explorer_sa3 && /home/kim/Projects/mir/bin/python -m pytest test_render_client_models.py -v`
Expected: FAIL — `AttributeError: module 'render_client' has no attribute 'roots'`

- [ ] **Step 3: Extend the client**

In `/home/kim/Projects/mir/plots/explorer_sa3/render_client.py`, replace the `ckpts` function and
add the new ones:

```python
def ckpts(rescan: bool = False, root: str | None = None,
          root_ids: list[str] | None = None, timeout: float = 60.0) -> dict | None:
    """GET /ckpts — checkpoint journal.

    Legacy: no args, or root= to override the single scan folder (server-side
    default is the <eval-drive>/sa3_lora_runs root from eval/model_roots.json;
    the drive is removable and mounts as Mantu or Mantu1).
    Multi-root: root_ids=["lumi_uuid", ...] returns the merged listing, each entry
    tagged with root_id/family/label/epoch/step/rank/corpus/verdict.
    Returns None when the server is unreachable."""
    params: dict = {"rescan": int(bool(rescan))}
    if root:
        params["root"] = root
    if root_ids:
        params["root_ids"] = ",".join(root_ids)
    try:
        r = requests.get(f"{BASE}/ckpts", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def roots(timeout: float = 10.0) -> dict | None:
    """GET /roots — configured checkpoint roots + live availability + limits."""
    try:
        r = requests.get(f"{BASE}/roots", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def models(root_ids: list[str] | None = None, family: str | None = None,
           corpus: str | None = None, q: str | None = None,
           loadable: bool | None = None, rescan: bool = False,
           timeout: float = 60.0) -> dict | None:
    """GET /models — the model database (family/corpus/epoch/step/run/provenance)."""
    params: dict = {"rescan": int(bool(rescan))}
    if root_ids:
        params["root_ids"] = ",".join(root_ids)
    for k, v in (("family", family), ("corpus", corpus), ("q", q)):
        if v:
            params[k] = v
    if loadable is not None:
        params["loadable"] = int(bool(loadable))
    try:
        r = requests.get(f"{BASE}/models", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/mir/plots/explorer_sa3 && /home/kim/Projects/mir/bin/python -m pytest test_render_client_models.py -v`
Expected: 5 passed.

- [ ] **Step 5: Add the root selector and model-info panel to the tab**

In `/home/kim/Projects/mir/plots/explorer_sa3/inference_tab.py`, insert directly above the existing
checkpoint row (before line 82's `html.Span("checkpoint", ...)`):

```python
        html.Div([
            html.Span("roots", title=(
                "Which checkpoint root folders the picker scans. Configured in "
                "SAO/eval/model_roots.json; unavailable = that removable drive is "
                "not mounted (the cached journal is still served)."),
                style={"minWidth": "60px", "fontWeight": "bold"}),
            dcc.Dropdown(id="inf-root-dd", options=[], value=[], multi=True,
                         placeholder="all available roots",
                         style={"flex": "1", "minWidth": "320px"}),
        ], style={"display": "flex", "gap": "6px", "alignItems": "center",
                  "margin": "2px 0"}),
```

and directly below the checkpoint row:

```python
        html.Div(id="inf-model-info",
                 style={"fontSize": "11px", "margin": "2px 0 6px 0",
                        "padding": "4px 6px", "background": "#f6f6f6",
                        "borderLeft": "3px solid #999"}),
```

Then replace the `_ckpt_journal` callback (lines 432-449) with:

```python
    @app.callback(Output("inf-root-dd", "options"),
                  Input("inf-ckpt-rescan", "n_clicks"))
    def _root_options(_n):
        resp = render_client.roots()
        if resp is None:
            return []
        return [{"label": (f"{r['label']} ({r['count']})"
                           + ("" if r["available"] else "  — DRIVE NOT MOUNTED")),
                 "value": r["id"], "disabled": not (r["available"] or r["count"])}
                for r in resp.get("roots", [])]

    @app.callback(Output("inf-ckpt-dd", "options"),
                  Output("inf-ckpt-status", "children"),
                  Input("inf-ckpt-rescan", "n_clicks"),
                  Input("inf-root-dd", "value"))
    def _ckpt_journal(n_clicks, root_ids):
        # fires once at load (n_clicks=None -> cached journal), then on button/roots
        resp = render_client.ckpts(rescan=bool(n_clicks), root_ids=root_ids or None)
        if resp is None:
            return [], "ckpt journal unavailable (server down?)"
        root = (resp.get("root") or "").rstrip("/")
        opts = []
        for c in resp.get("ckpts", []):
            path = c.get("path", "")
            label = path[len(root) + 1:] if root and path.startswith(root + "/") else path
            bits = [b for b in (c.get("family"), c.get("corpus"),
                                f"r{c['rank']}" if c.get("rank") else None,
                                f"ep{c['epoch']}" if c.get("epoch") is not None else None,
                                "verdict" if c.get("verdict") else None) if b]
            if bits:
                label += "   [" + " · ".join(bits) + "]"
            size = c.get("size")
            if size:
                label += f"  ({size / 1e6:.0f} MB)"
            opts.append({"label": label, "value": path})
        stale = resp.get("stale_root_ids") or []
        note = f" · STALE (unmounted): {', '.join(stale)}" if stale else ""
        scope = ", ".join(root_ids) if root_ids else (root or "default root")
        return opts, f"{len(opts)} ckpts · {scope}{note}"

    @app.callback(Output("inf-model-info", "children"),
                  Input("inf-ckpt-dd", "value"),
                  Input("inf-ckpt-path", "value"))
    def _model_info(dd_val, free_path):
        """Three-audience standard (eval-tables spec section 14): what this model is,
        the reproducible recipe, and the plain-language why."""
        path = (free_path or "").strip() or (dd_val or "").strip()
        if not path:
            return "no checkpoint selected — renders use the base model (medium-base)."
        resp = render_client.models(q=path)
        recs = [m for m in ((resp or {}).get("models") or []) if m["path"] == path]
        if not recs:
            return f"not in the model DB: {path}"
        m = recs[0]
        head = " · ".join(str(x) for x in (
            m["family"], m.get("corpus") or "corpus?",
            f"r{m['rank']}/a{m['alpha']}" if m.get("rank") else None,
            m.get("adapter_type"),
            f"ep{m['epoch']} step{m['step']}" if m.get("epoch") is not None else None,
            f"{m['load_cost_gb']} GB resident") if x)
        rows = [html.B(m["label"]), html.Span("  " + head)]
        for field, prefix in (("recipe", "recipe: "), ("purpose", "why: "),
                              ("verdict", "verdict: "), ("kim_feedback", "Kim: ")):
            if m.get(field):
                rows += [html.Br(), html.Span(prefix + str(m[field]))]
        if m.get("run_meta_path"):
            rows += [html.Br(),
                     html.A("run_meta.json", href="file://" + m["run_meta_path"],
                            target="_blank")]
        rows += [html.Br(),
                 html.Span("provenance: " + ", ".join(
                     f"{k}={v}" for k, v in sorted((m.get("provenance") or {}).items())),
                     style={"color": "#777"})]
        return rows
```

- [ ] **Step 6: Headless boot verification**

Run:
```bash
cd /home/kim/Projects/mir && /home/kim/Projects/mir/bin/python -c "
import sys; sys.path.insert(0, 'plots')
from explorer_sa3 import app as A
a = A.build_app() if hasattr(A, 'build_app') else A.app
ids = {c.id for c in a.layout.children if hasattr(c, 'id')} if hasattr(a.layout, 'children') else set()
print('app built OK')
"
```
Expected: `app built OK` with no duplicate-callback-output or missing-id errors. Then start the
viewer (`/home/kim/Projects/mir/bin/python plots/explorer_sa3/app.py`) with the render server up,
open `http://localhost:8051`, and confirm: the roots dropdown lists 4 roots with counts, unmounted
ones say `DRIVE NOT MOUNTED`, selecting `lumi_uuid` repopulates the ckpt dropdown with LUMI arms,
and selecting one fills the model-info panel with family/corpus/rank/epoch/verdict.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/mir && git add plots/explorer_sa3/render_client.py plots/explorer_sa3/inference_tab.py plots/explorer_sa3/test_render_client_models.py
git commit -m "explorer: root selector + model-info panel over the new /roots + /models

The picker was pinned to sa3_lora_runs; the 14 LUMI families were reachable only
by typing a path. Option labels now carry family/corpus/rank/epoch and the panel
shows recipe + why + verdict + provenance (three-audience standard).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 9: Viewer — A/B slot panel

**Files:**
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/render_client.py`
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/controls.py:80-130` (panel), `:145-210` (`steering_payload`)
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/inference_tab.py` (A/B render button + results)
- Test: `/home/kim/Projects/mir/plots/explorer_sa3/test_controls_slots.py` (create)

**Interfaces:**
- Consumes: `POST /slots`, `GET /slots`, `POST /ab`.
- Produces:
  - `render_client.slots(timeout=10.0) -> dict | None`
  - `render_client.set_slots(specs: list[dict], activate: int | None = None, timeout=300.0) -> dict`
  - `render_client.ab(payload: dict, timeout=7200.0) -> dict`
  - `controls.AB_SLOTS: int = 4`; `controls.steering_payload(vals)` emits `dora["slot"]`
  - New Dash ids: `{ns}-ab-slot{i}-ckpt`, `{ns}-ab-load`, `{ns}-ab-status`, `{ns}-ctl-dora-slot`, `inf-ab-render`, `inf-ab-out`

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/mir/plots/explorer_sa3/test_controls_slots.py`:

```python
import pytest

import controls


def _vals(dora_dd="none", slot=None):
    """A full steering_payload input vector with the two fields under test set."""
    v = controls.default_state_values()
    v[controls.IDX_DORA_DD] = dora_dd
    v[controls.IDX_DORA_SLOT] = slot
    return v


def test_payload_without_a_slot_is_byte_identical_to_the_pre_slot_contract():
    out = controls.steering_payload(_vals(dora_dd="hof", slot=None))
    assert out["dora"]["name"] == "hof"
    assert out["dora"]["slot"] is None


def test_payload_with_a_slot_carries_it_and_drops_the_registry_name():
    out = controls.steering_payload(_vals(dora_dd="hof", slot=1))
    assert out["dora"]["slot"] == 1
    assert "name" not in out["dora"], "a slot supersedes the registry dropdown"


def test_slot_zero_is_not_treated_as_absent():
    out = controls.steering_payload(_vals(slot=0))
    assert out["dora"]["slot"] == 0


def test_ab_slots_constant_matches_the_panel_rows():
    assert controls.AB_SLOTS >= 2
    panel = controls.steering_panel("inf")
    ids = controls.collect_ids(panel)
    for i in range(controls.AB_SLOTS):
        assert f"inf-ab-slot{i}-ckpt" in ids
    assert "inf-ab-load" in ids and "inf-ab-status" in ids
```

`controls.default_state_values()`, `controls.IDX_DORA_DD`, `controls.IDX_DORA_SLOT` and
`controls.collect_ids()` are new helpers introduced in Step 3 — `steering_payload` currently
consumes a bare 35-value positional list with hardcoded slicing (`vals[27:31]`), and that is what
makes it untestable and brittle. Introducing named indices is part of this task.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/mir/plots/explorer_sa3 && /home/kim/Projects/mir/bin/python -m pytest test_controls_slots.py -v`
Expected: FAIL — `AttributeError: module 'controls' has no attribute 'default_state_values'`

- [ ] **Step 3: Add the client calls, the named indices, and the panel**

In `render_client.py` add:

```python
def slots(timeout: float = 10.0) -> dict | None:
    """GET /slots — the resident adapter table + VRAM budget."""
    try:
        r = requests.get(f"{BASE}/slots", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def set_slots(specs: list[dict], activate: int | None = None,
              timeout: float = 300.0) -> dict:
    """POST /slots — declare the resident adapter SET.

    specs: [{"ckpt_path": str, "label": str?}]. Changing the set costs one
    remove+reload; switching between resident slots afterwards costs nothing.
    Raises RenderError with the server's reason on refusal (over the VRAM floor,
    over max_slots, or a fullft path, which cannot share the base)."""
    body = {"slots": specs}
    if activate is not None:
        body["activate"] = int(activate)
    try:
        r = requests.post(f"{BASE}/slots", json=body, timeout=timeout)
    except Exception as e:
        raise RenderError(f"render server unreachable: {e}") from e
    j = r.json() if r.content else {}
    if r.status_code >= 400 or not j.get("ok"):
        raise RenderError(j.get("reason") or j.get("error") or f"HTTP {r.status_code}")
    return j


def ab(payload: dict, timeout: float = 7200.0) -> dict:
    """POST /ab — one payload rendered across resident slots, one shared seed."""
    try:
        r = requests.post(f"{BASE}/ab", json=payload, timeout=timeout)
    except Exception as e:
        raise RenderError(f"render server unreachable: {e}") from e
    j = r.json() if r.content else {}
    if r.status_code >= 400 or not j.get("ok"):
        raise RenderError(j.get("reason") or j.get("error") or f"HTTP {r.status_code}")
    return j
```

In `controls.py`, add near the top:

```python
AB_SLOTS = 4

# steering_payload consumes a positional State vector. It used to slice it with
# bare literals (vals[27:31]), which broke every time a control was inserted.
# Name the indices instead; append-only, never reorder.
IDX_DORA_DD = 27
IDX_DORA_STRENGTH = 28
IDX_DORA_IMIN = 29
IDX_DORA_IMAX = 30
IDX_DORA_SLOT = 31
_N_STATE = 32


def default_state_values() -> list:
    """A neutral input vector, for tests and for resetting the panel."""
    v = [None] * _N_STATE
    v[IDX_DORA_DD] = "none"
    v[IDX_DORA_STRENGTH] = 1.0
    v[IDX_DORA_IMIN], v[IDX_DORA_IMAX] = 0.0, 1.0
    v[IDX_DORA_SLOT] = None
    return v


def collect_ids(component) -> set:
    """Every component id in a Dash tree — used by layout tests."""
    out = set()
    stack = [component]
    while stack:
        c = stack.pop()
        cid = getattr(c, "id", None)
        if isinstance(cid, str):
            out.add(cid)
        kids = getattr(c, "children", None)
        if isinstance(kids, (list, tuple)):
            stack.extend(kids)
        elif kids is not None:
            stack.append(kids)
    return out
```

Add the A/B section inside `steering_panel(ns, ...)`, after the DoRA row:

```python
        html.Details([
            html.Summary("A/B slots — several models resident, switch with no reload"),
            html.Div(
                "Load up to %d adapters onto the ONE resident base model. Switching "
                "between them is a strength flip (milliseconds), not a reload: about "
                "0.33 GB of VRAM per rank-128 DoRA, versus 5.1 GB for a second "
                "backbone. Full-FT checkpoints cannot be slots — they change the base "
                "itself. Pick the same prompt, cfg and seed and only the model varies, "
                "which is what makes the comparison mean anything." % AB_SLOTS,
                style={"fontSize": "11px", "color": "#555", "margin": "2px 0 6px 0"}),
            *[html.Div([
                html.Span(f"slot {i}", style={"minWidth": "48px"}),
                dcc.Dropdown(id=f"{ns}-ab-slot{i}-ckpt", options=[], value=None,
                             clearable=True, placeholder="(empty)",
                             style={"flex": "1", "minWidth": "300px"}),
              ], style={"display": "flex", "gap": "6px", "alignItems": "center"})
              for i in range(AB_SLOTS)],
            html.Div([
                html.Button("Load slots", id=f"{ns}-ab-load"),
                html.Span("active slot", style={"marginLeft": "10px"}),
                dcc.Dropdown(id=f"{ns}-ctl-dora-slot", options=[], value=None,
                             clearable=True, placeholder="none (registry DoRA)",
                             style={"width": "180px"}),
            ], style={"display": "flex", "gap": "6px", "alignItems": "center",
                      "margin": "4px 0"}),
            html.Div(id=f"{ns}-ab-status", style={"fontSize": "11px"}),
        ], open=False),
```

Update `steering_payload` to use the named indices and emit the slot:

```python
    dora_dd = vals[IDX_DORA_DD]
    dora_strength = vals[IDX_DORA_STRENGTH]
    dora_imin, dora_imax = vals[IDX_DORA_IMIN], vals[IDX_DORA_IMAX]
    dora_slot = vals[IDX_DORA_SLOT] if len(vals) > IDX_DORA_SLOT else None
    dora = None
    if dora_slot is not None:
        # A resident slot supersedes the registry dropdown entirely: the server
        # flips strengths instead of rebuilding, so a "name" here would be a lie.
        dora = {"slot": int(dora_slot),
                "strength": float(dora_strength) if dora_strength is not None else 1.0}
    elif dora_dd == "none":
        dora = {"name": "none", "slot": None,
                "strength": float(dora_strength) if dora_strength is not None else 1.0}
    elif dora_dd:
        dora = {"name": dora_dd, "ckpt_path": None, "slot": None,
                "strength": float(dora_strength) if dora_strength is not None else 1.0}
    if dora is not None and dora.get("slot") is None:
        dora["interval_min"] = float(dora_imin) if dora_imin is not None else 0.0
        dora["interval_max"] = float(dora_imax) if dora_imax is not None else 1.0
```

Add the corresponding `State(f"{ns}-ctl-dora-slot", "value")` to the panel's State list (append at
the end, index `IDX_DORA_SLOT`), and add the load callback in `controls.register_callbacks` (or the
tab's callback module, matching the existing pattern):

```python
    @app.callback(Output(f"{ns}-ab-status", "children"),
                  Output(f"{ns}-ctl-dora-slot", "options"),
                  Input(f"{ns}-ab-load", "n_clicks"),
                  *[State(f"{ns}-ab-slot{i}-ckpt", "value") for i in range(AB_SLOTS)],
                  prevent_initial_call=True)
    def _load_slots(_n, *paths):
        specs = [{"ckpt_path": p} for p in paths if p]
        if not specs:
            return "pick at least one checkpoint", []
        try:
            resp = render_client.set_slots(specs, activate=0)
        except render_client.RenderError as e:
            return html.Span(f"REFUSED: {e}", style={"color": "#a00"}), []
        rows = resp["slots"]
        opts = [{"label": f"{s['index']}: {s['label']}", "value": s["index"]}
                for s in rows]
        return (f"{len(rows)} resident · {resp['free_gb']} GB free "
                f"(floor {resp['vram_floor_gb']} GB) · active {resp['active']}"), opts
```

Populate the slot dropdowns' `options` from the same source as `inf-ckpt-dd` by adding
`Output(f"{ns}-ab-slot{i}-ckpt", "options")` for each `i` to the existing `_ckpt_journal` callback,
returning the same `opts` list.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/kim/Projects/mir/plots/explorer_sa3 && /home/kim/Projects/mir/bin/python -m pytest test_controls_slots.py test_render_client_models.py -v`
Expected: all passed.

- [ ] **Step 5: Add the A/B render button to the inference tab**

In `inference_tab.py`, next to the existing render button add:

```python
            html.Button("A/B render (all slots + base)", id="inf-ab-render"),
```

and a callback that reuses the existing payload builder — **do not rebuild the payload**:

```python
    @app.callback(Output("inf-ab-out", "children"),
                  Input("inf-ab-render", "n_clicks"),
                  *_INFERENCE_STATES,          # the SAME State list /generate uses
                  prevent_initial_call=True)
    def _ab_render(_n, *vals):
        common = _build_generate_payload(vals)      # existing helper, unchanged
        srv = render_client.slots() or {}
        idxs = [s["index"] for s in srv.get("slots", [])]
        if len(idxs) < 1:
            return "no resident slots — load some in the A/B slots panel first"
        common["ab"] = {"slots": [None] + idxs}     # base is the control arm
        try:
            resp = render_client.ab(common)
        except render_client.RenderError as e:
            return html.Span(str(e), style={"color": "#a00"})
        return [html.Div([html.B(a["label"]),
                          html.Audio(src=render_client.audio_url(a["urls"][0]),
                                     controls=True, style={"width": "100%"})])
                for a in resp["arms"]]
```

If `_build_generate_payload` does not already exist as a separate helper, extract it from the
current render callback first — the A/B path must construct its payload from the identical code, or
the two will drift.

- [ ] **Step 6: End-to-end verification with the real stack**

With the render server on :8056 and the viewer on :8051: load two adapters into slots, press
**A/B render**, and confirm three players appear (base + 2), the server log shows no
`[model] rebuild` between arms, and the arms sound different. Then reload the page and confirm a
plain single render with no slot selected still works exactly as before (regression check on the
compat requirement).

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/mir && git add plots/explorer_sa3/controls.py plots/explorer_sa3/inference_tab.py plots/explorer_sa3/render_client.py plots/explorer_sa3/test_controls_slots.py
git commit -m "explorer: A/B slot panel — N models resident, switch with no reload

steering_payload gains dora.slot and named state indices (the bare vals[27:31]
slicing broke on every control insertion). The A/B render button reuses the same
payload builder as /generate so the arms cannot drift.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

### Task 10: Documentation and index registration

Nothing here is optional: the discoverability rule says a new artifact is not DONE until it has an
index entry, and the post-task protocol names the exact update set.

**Files:**
- Modify: `/home/kim/Projects/SAO/docs/INFERENCE-SURFACE.md` (§0 endpoint list, §9 HAS/NEEDS)
- Modify: `/home/kim/Projects/SAO/ARCHITECTURE.md` (reuse index + doc map)
- Modify: `/home/kim/Projects/SAO/WORKLOG.md`
- Modify: `/home/kim/Projects/SAO/KIM-TASKLIST.md`
- Modify: `/home/kim/Projects/SAO/profiles/<handle>.tasks.md` and `<handle>.journal.md`

- [ ] **Step 1: Update `docs/INFERENCE-SURFACE.md`**

- §0 endpoint table: add `/roots · /models · /models/{id} · /slots · /ab` to the render-server
  endpoint list.
- §0: add a paragraph stating that A/B is done with **resident slots**, that
  `lora_configs` must cover every resident index (or A/B silently becomes A+B), and that
  `load_and_apply_loras` re-indexes from 0 so incremental adds are unsafe.
- §9 HAS: move item 1 ("Checkpoint reach") out of NEEDS BUILDING into HAS, and add
  "multi-root picker + model database (`eval/model_db.py`, config `eval/model_roots.json`)" and
  "resident A/B slots (`eval/adapter_slots.py`)".
- §9 NEEDS: strike item 6 (the `riffer_*.pt` blind spot — now scanned). Leave 6b, 2, 3, 4, 5, 7.
- Add a short **VRAM budget** subsection carrying the measured table from this plan, so the next
  instance does not re-measure.

- [ ] **Step 2: Register in `ARCHITECTURE.md`**

Reuse index (§C, eval tooling) — four one-liners:

```
- `eval/model_roots.py` + `eval/model_roots.json` — THE config for checkpoint roots and removable-drive mount resolution. No drive path belongs in code; add a root here, not in a script.
- `eval/ckpt_probe.py` — classify a checkpoint (adapter / fullft / control_adapter / latch_head) in milliseconds without torch.load, even at 44 GB. Covers riffer_*.pt.
- `eval/model_db.py` — the model database keyed by absolute checkpoint path (family/corpus/epoch/step/run/provenance), joined to model_index.md's verdicts. Served by :8056 /models.
- `eval/adapter_slots.py` — N adapters resident on one base; A/B with no reload and no offload (~0.33 GB per r128 DoRA). Guards the two silent multi-LoRA traps.
```

Doc map: add this plan and cross-link `docs/INFERENCE-SURFACE.md`.

- [ ] **Step 3: Append to `WORKLOG.md`** (filelock first; this file is PUBLIC — no secrets, no
credential-revealing paths)

```
- [2026-08-DD] (<handle>) INFERENCE UI: multi-root model DB + resident A/B slots. The picker was pinned to sa3_lora_runs (162 local DoRA runs); the 14 LUMI families on the UUID drive were reachable only by typing a path. Now: eval/model_roots.json (config, no drive paths in code, marker-probe mount resolution) + eval/ckpt_probe.py (family detection in ms without torch.load, incl. riffer_*.pt) + eval/model_db.py (path-keyed DB joined to model_index.md's verdicts) behind new :8056 endpoints /roots /models /slots /ab, and a root selector + model-info + A/B panel in the explorer. A/B is N adapters resident on ONE base (~0.33 GB per r128 DoRA, measured) — NOT a second backbone (+5.1 GB on a 17.1 GB card). Two traps documented in eval/adapter_slots.py: dit.py only gates indices present in lora_configs (omit one and "A vs B" is silently "A+B"), and load_and_apply_loras re-indexes from 0 so incremental adds collide. Full-FT cannot be a slot — use the host-RAM state swap (72 GB available, 0 GB VRAM).
```

- [ ] **Step 4: Add the two follow-ups to `KIM-TASKLIST.md`** (filelock first)

```
- [ ] The families dorlor_ab (32 arms), lr5e5_allsets, fullft_avp_subloss, subloss_k24, winning_fleet, fullft_fleet are NOT on either mounted drive — only <UUID>/lumi_runs/renders/dorlor_ab (renders, not checkpoints). Presumably still on LUMI /scratch, which is under a purge deadline. **Decision needed: pull them before the purge?** Once local, adding them to the picker is a one-line edit in eval/model_roots.json.
- [ ] Ears wanted: the /ab endpoint renders base + N adapters at one seed. Worth a pass at cfg 16 / strength 1.5 (Kim 2026-08-22: the useful discriminator is which checkpoints stay musical when guidance is pushed).
```

- [ ] **Step 5: Personal journal + task log**

Journal entry (detailed, negatives included) covering: what the discovery phase found that changed
the design (`model_index.md` already IS the model database — 309 models, 71 families, stable ids,
Kim's verdicts — so this work JOINS to it rather than starting a second one); the measured VRAM
numbers; the two multi-LoRA traps; and the negative result that six named families are not on disk.
Then a one-line entry in `profiles/<handle>.tasks.md`.

- [ ] **Step 6: Commit and post to the chat**

```bash
cd /home/kim/Projects/SAO && git add docs/INFERENCE-SURFACE.md ARCHITECTURE.md WORKLOG.md KIM-TASKLIST.md profiles/
git commit -m "docs: register the multi-root model DB + A/B slots work

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

Then post a short summary to the common `AGENT_DIALOGUE.md` channel — the chat is Kim's public
window, and work that lives only in logs is invisible.

---

## Out of scope (deliberately, with reasons)

- **Head-B contour/morph adapters and pianoroll/`mir_ctrl` in the server** (`INFERENCE-SURFACE`
  §9 items 2–3). The DB now *lists* `control_adapter` checkpoints with their `control_mode`, but
  `loadable` is `False` for them — the server has no install path and no contour-stream input.
  Bringing them in needs the sampler's conditioning inlet extended, which is its own plan.
- **Full-FT host-RAM backbone swap (Option C).** Recommended above and costed (0 GB VRAM, ~2–4 s,
  4.6 GB host RAM per pinned state, 72 GB available), but it is a separate mechanism from adapter
  slots and belongs in its own plan so the A/B work can land first. The `/slots` refusal message
  already names it, so the seam is visible rather than silent.
- **Recovering the six missing LUMI families from `/scratch`.** A data-recovery question for Kim
  (raised in `KIM-TASKLIST.md`), not a UI change — adding them later is a config edit.
- **A batch/sweep CLI** (`INFERENCE-SURFACE` §9 item 4). Legitimately additive as a thin client of
  `/generate`, but independent of this work.

## Self-review notes

- Spec coverage: (a) multi-root + absent drives → Tasks 1, 3, 4 (`available=false` + stale journal
  service). (b) database contents + population → Task 3 (record schema, `run_meta` both shapes,
  overrides join, provenance) — `.mmline.json` harvest was folded into "out of scope" only for the
  *render-history* view; the fields the brief named (family, corpus, epoch/step, training run,
  provenance) are all in the record. (c) VRAM budget + A/B design with numbers → the budget section
  + Task 5. (d) GUI + HTTP exposure → Tasks 4, 6, 7 (HTTP) and 8, 9 (GUI). (e) migration/compat →
  the Global Constraints bullet, `/ckpts` legacy branch, `dora.slot` absent path,
  `max_resident_adapters: 1`, journal `schema` bump.
- Naming is consistent across tasks: `Root`, `Slot`, `SlotTable`, `record_for`, `load_or_build`,
  `lora_configs`, `strengths`, `push_strengths`, `_ab_arm_payloads`, `_generate`.
- The one claim that could invalidate Task 5's cost model — that `remove_lora_by_index` truly
  reverts the base weights — is an explicit assert-or-stop step (Task 5 Step 5), not an assumption.
