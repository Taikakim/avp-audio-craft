# Batch/Sweep Surface + LatCH Head Metadata — Implementation Plan

> **STATUS 2026-08-26 (C): Tasks 1–9 DONE, nothing committed.** Task 10 (docs/index) folded in as
> the work landed. What shipped, and where it departed from the plan:
> - **T1–T3** `eval/head_meta.py`, server `_head_entry` delegating to it, viewer LatCH panel.
>   Departures: `dcc.Input` has no `title` prop in this Dash version, so the hover help lives on the
>   label `Span`s (`-vlabel` / `-llabel`); the callback grew a 17th output because the target-KIND
>   dropdown must be gated by the same flag as the value box; `_slot_view` is a pure function so it
>   is unit-testable without a Dash harness.
> - **T4–T5** `eval/presets.py`, `GET/POST /presets`, the Preset row. Departure: a preset stores a
>   `form` snapshot as well as the payload, and Load restores the FORM. The plan's inverse mapping
>   would have been a second source of truth — `build_payload()` merges prompt+variation, resolves
>   dist-shift and collapses 35 steering states, so it is not invertible without loss. Load is two
>   chained callbacks; see the race note in `inference_tab.py`.
> - **T6–T9** `sweep_spec.py`, `sweep_run.py` (+`--models`), `build_sweep_page.py`. Departure: the
>   page reuses `build_evals`' `CSS`/`WAVEFORM_CSS`/`WAVEFORM_JS` rather than extracting
>   `audition_player.py` from the clarity page (whose players are entangled with its own data model)
>   — and loads it BY PATH, because `build_evals.py:21` prepends `Misc/` to `sys.path`, where a
>   first-party `filelock.py` shadows the pip package.
> - Verified end-to-end with real renders: a 2-cell sweep rendered, resumed (2 skipped), and built a
>   page whose two cfg cells are genuinely different audio.
> - **Open, needs Kim:** `/generate` and `/a2a_*` still save no z0 (see `KIM-TASKLIST.md`).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the SA3 inference tool (a) a resumable batch/sweep surface that renders *saved presets × a selection of models* as a thin HTTP client of the existing render server, landing in an auditable eval page, and (b) a LatCH panel that tells the truth about each head — its real dataset range, its real slider bounds, which controls it can't use, and whether it is healthy.

**Architecture:** Four new importable modules under `/home/kim/Projects/SAO/eval/` (`head_meta.py`, `presets.py`, `sweep_spec.py`, `sweep_run.py`) plus a page builder (`build_sweep_page.py`). `head_meta.py` is consumed by the EXISTING render server `eval/explorer_render_server.py` (:8056) at `_head_entry`; the sweep is a **CLI client of `POST /generate`** over HTTP — it never imports the model, never builds a guidance config of its own, and never touches `resolve_latch`. Presets are the render payload itself, versioned and stored as JSON; a sweep is a preset plus a list of axes and a list of models. Results are a JSONL manifest that a page builder renders per the eval-tables spec.

**Tech Stack:** Python 3.11 · FastAPI (server, already there) · Dash (viewer, mir repo) · `requests` (client) · pytest · plain HTML/JS for the results page (no build step, no CDN).

**Spec:**
- `/home/kim/Projects/SAO/docs/INFERENCE-SURFACE.md` — the capability map. §0 (the engine), §9 items 4 + 7, the "LatCH PANEL REQUIREMENTS" block, the measured 16-head table. **Read §0 and §9 before Task 1.**
- `/home/kim/Projects/SAO/docs/superpowers/specs/2026-07-06-eval-tables-human-first.md` — the eval-UI source of truth. §12 (layout + provenance), §13 (waveform popup player), §14 (THREE-AUDIENCE STANDARD), §16 (unaudited marker + manifest v2). The results page in Task 9 implements these; it does not invent a new viewer.

**Sibling plans this one CONSUMES (do not duplicate their work):**
- `/home/kim/Projects/SAO/docs/superpowers/plans/2026-08-23-inference-ui-model-db-and-ab-slots.md` — provides `eval/model_db.py` (`load_or_build()`, the record schema with `id/path/family/label/loadable/...`), multi-root `/ckpts`, `GET /models`, resident `/slots`, `POST /ab`. **Task 8 here is a client of `/models`; it must not build a second model registry.**
- `/home/kim/Projects/SAO/docs/superpowers/plans/2026-08-23-inference-ui-global-conditioner-inpaint.md` — provides `eval/render_io.py` (`save_z0`, `z0_path_for`, `normalize_and_truncate`) and makes every render response carry `resp["latents"]`. **Task 7 here consumes `resp["latents"]`; it must not re-implement z0 saving.** It also owns `ConditionerFamily` / `ConditioningBundle` in `control/sa3_control/conditioning.py` — the sweep passes conditioner specs through opaquely and never interprets them.

---

## Global Constraints

Every task's requirements implicitly include this section.

1. **NEVER a second renderer or a second guidance implementation.** `resolve_latch()` (`eval/explorer_render_server.py:463-518`) NORMALISES gains: `g0 = slots[0].gain`, per-slot `weight = gain / g0`, and `hparams["rho"] = hparams["mu"] = g0`. A raw `weight` computed anywhere else is a different scale. `eval/head_lab.py` was DELETED for exactly this mistake. The sweep speaks HTTP to `POST /generate` and passes the payload through untouched.
2. **Interpreters, always absolute.** Server code + all tests in this plan: `/home/kim/Projects/SAO/.venv/bin/python`. Viewer code (mir repo, branch `sa3-latent-explorer`): `/home/kim/Projects/mir/mir/bin/python`. `mir/bin/python` does not exist.
3. **`export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before any `import torch`.** Never `HIP_VISIBLE_DEVICES=""` (flash_attn/aiter probes a Triton driver at import → crash).
4. **No hardcoded drive paths.** The eval drive mounts as `Mantu` OR `Mantu1`. Use the existing `_mantu_root()` (`eval/explorer_render_server.py:76`) or `model_roots.resolve_roots()`. Task 2 fixes one live violation of this rule.
5. **Save the z0 latent next to every render** (standing directive). The sweep records the `latents` path from each response into its manifest; if a response carries no `latents` key the cell is marked `z0_missing: true` and a warning is printed — never silently dropped.
6. **GPU lock via `Misc/gpu_guard.sh`**; never hand-write `/tmp/gpu.lock`. The sweep does not take the lock itself — the render server already holds `GPU_LOCK` around every render (`_generate_impl:747`). The sweep must therefore tolerate long blocking calls.
7. **Design for interruption.** One RDNA4 GPU, 93 GB host RAM. The sweep MUST be resumable: kill it, restart it with the same command, and it skips every cell already rendered. Resume is keyed on a deterministic cell id, not on ordinal position.
8. **Launch commands (verified 2026-08-24), each from its own repo root:**
   - render server: `.venv/bin/python eval/explorer_render_server.py` (:8056)
   - latent player: `cd /home/kim/Projects/mir && /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python scripts/latent_server_sa3.py` (:7892)
   - viewer: `cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m plots.explorer_sa3.app` (:8051)
9. **Tests live in `/home/kim/Projects/SAO/eval/tests/`** (the convention the conditioner plan uses). `sys.path.insert(0, "/home/kim/Projects/SAO/eval")` at the top of each test file, because `eval/` is not a package.
10. **Every new artifact gets an index entry** (CLAUDE.md DISCOVERABILITY RULE). Task 10 does this; the plan is not done without it.

---

## Section 0 — What a "sweep surface" is, and why item 4 matters

*(Kim: "I don't understand what 4 is, but build what is required." This section is the answer; keep it in the shipped docs.)*

The GUI at :8051 renders **one thing at a time**. You set ~35 knobs, press Render, listen, change one knob, press Render again. That is the right shape for *exploring* — you are following your ears.

It is the wrong shape for **answering a question**. A question looks like: *"holding prompt, seed, steps, cfg and every LatCH setting fixed, what does adapter strength 0.5 / 1.0 / 1.5 / 2.0 actually do?"* — or Kim's own: *"I might want to try out the same adapter on two different full finetunes."* To answer that in the GUI you must reproduce 34 identical knob settings by hand, four (or twelve, or sixty) times, and trust that you did. You won't; and afterwards nothing on disk records what each file was.

A **sweep surface** is three things:

1. **A preset** — the whole render payload (prompt, duration, steps, cfg, seed, the 3 LatCH slots, FiLM, DoRA, advanced hparams) saved under a name, so "everything else fixed" is a *file*, not a memory.
2. **Axes** — a declaration of what varies: `strength = [0.5, 1.0, 1.5, 2.0]`, or `model = [these six checkpoints]`, or `cfg × seed`. The cross-product of the axes over the preset is the **cell set**.
3. **A runner** — a loop that POSTs each cell to the render server that the GUI already uses, writes one manifest line per cell, and can be killed and restarted without redoing work.

The payoff is that a sweep is **comparable by construction** (every cell went through the same normalised guidance path, because it went through the same server) and **auditable afterwards** (the manifest says exactly what produced each wav). This is the same reason `lumi/render_matrix_cells.py` exists for the cluster — item 4 is that capability for the local tool, aimed at the local server instead of at a bare model.

**Kim's preset-across-models ask is the headline case**, and he ranked it above model residency: one preset × N models = the matrix that tells you whether an adapter behaves the same on two different full fine-tunes. Task 8 is that feature; Tasks 6–7 are the machinery it stands on.

---

## Discovery findings this plan is built on

Read from the code 2026-08-24. Every claim here has a file:line — do not re-derive them.

**The 17th head is `chroma_other`, and it carries a dead path.**
`scan_latch_heads()` (`eval/explorer_render_server.py:305-312`) globs `MEDIUM_HEAD_DIR.glob("latch_sa3_*_best.pt")` → **16** files (the dir holds 30 entries; `f0_bass_ep{1,2,3}.pt` and the `bracket_*` dirs do not match `*_best.pt`), then adds a 17th by hand:
```python
HEADS["chroma_other"] = _head_entry("chroma_other", "chroma", cmt.CHROMA_HEAD, cmt.CHROMA_GAIN)
```
`cmt.CHROMA_HEAD` is `eval/chroma_morph_transitions.py:46`, a literal beginning `/run/media/kim/Mantu1/sa3_lora_runs/cu_reward_renders/analysis/` — **a hardcoded `Mantu1` path**, which is the mount name that does not exist today. `cmt.CHROMA_GAIN = 2048.0` (line 48) vs `512.0` for every medium head. So `chroma_other` is a different family, a different gain scale, and probably currently unloadable. Fixed in Task 2.

**The slider bounds are dead code that always falls through.**
`_head_entry` (`:274-303`) derives sliders from `md.get("slider_min")`, `md.get("slider_max")`, and `md.get("feature_stats", {})`. **`train_latch.py` writes none of those three keys.** Its save dict (`stable-audio-3/scripts/latch/train_latch.py:467-490`) writes exactly: `state_dict, ema, grad_accum, effective_batch, feature_name, noise_schedule, loss_type, optimizer, t_injection, in_channels, out_channels, standardized, std_mean, std_std, precision, seed, epoch, avg_loss, val_loss, val_split, selected_on`. So every head hits the final `else` branch and gets `-80.0 / 20.0 / -30.0`. That is why the slider is one-size-fits-all — not an oversight in the UI, a lookup for keys that were never written. **`std_mean` / `std_std` ARE written and are what the meter needs.**

**The typed `value` is in RAW feature units — so `std_mean ± kσ` is directly the right scale for the slider.**
`stable-audio-3/stable_audio_3/model.py:529-542`: the target is built by `_build_latch_target(kind, value, ...)` from the raw value, and *then*
```python
if meta.get("standardized"):
    target = (target - float(meta["std_mean"])) / (float(meta["std_std"]) or 1.0)
```
Confirmed: no double-standardisation risk, and the meter reads in the feature's own units (dB for `rms_*`, BPM for `beat_grid`, etc.).

**Which chroma readout a 12-d head was trained against is NOT RECORDED — anywhere.**
`train_latch.py:509-519` has `--chroma-dir`, `--chroma-key` (`other` / `bass` / `full_mix`, line 511) and `--target-source {db,npz,chroma,scalar_json}` (line 519), and `latch_dataset.py:92-99,162-166` resolves the target from them. **None of these four values is in the save dict** (`:467-490`) — only `feature_name` is. So for an existing 12-d head the readout is unrecoverable from the checkpoint. Task 1 handles this honestly (an overrides file + an explicit `unknown` state); Task 1 Step 9 fixes it going forward.

**`loss_type` cfg override beats head metadata, deliberately.** `model.py:551`: `"loss_type": cfg.get("loss_type") or meta.get("loss_type", "mse")` — comment says this is the 2026-07-10 scalar-pooled fix. So the UI must WARN when the user departs from the head's own loss, not forbid it.

**Nothing in the viewer knows what a preset is.** `grep -rn "preset" /home/kim/Projects/mir/plots/explorer_sa3/*.py` → zero hits. Presets are new.

**`POST /generate` today writes wav only.** `_generate_impl` (`:734-782`) saves `out_{i:02d}.wav` and nothing else; `grep -n "z0" eval/explorer_render_server.py` finds only `/longform`'s *reads* of `init_latent_path`. The conditioner plan's Task 1 adds `resp["latents"]`. Constraint 5 above defines the behaviour until it lands.

**There is no generic eval-page module to reuse.** `eval/build_dora_table_page.py`, `eval/build_clarity_audit_page.py` (369 lines, same-playhead player at `:60`) and friends are each bespoke and hardcode their own `OUT`. The spec is the shared thing, not the code. Task 9 therefore writes a new builder that CONFORMS to the spec and lifts the same-playhead player from `build_clarity_audit_page.py`.

**Existing payload shape** (`_generate_impl:734-770`, `resolve_dora_req:190`, `resolve_mutate:358`): top-level `prompt, negative_prompt, duration, steps, cfg_scale, batch_size, seed, apg_scale, duration_padding_sec, sampler_type, cfg_interval*, dist_shift*, ckpt_path, rho, mu, gamma, n_iter`; blocks `latch: [slot,...]`, `film: {...}`, `dora: {name|ckpt_path, strength}`, `mutate: {...}`, `preserve: {...}`. Per-slot latch keys (`resolve_latch:485-511`): `head|path, kind, value, gain, start_pct, end_pct, loss_type, w_sec`, or `builtin`.

---

## File Structure

| file | repo | responsibility |
|---|---|---|
| `SAO/eval/head_meta.py` | SAO | Read a LatCH checkpoint's metadata into ONE enriched dict: real slider bounds from `std_mean±kσ`, capability flags, health flag, family, readout provenance. No HTTP, no Dash. ~200 lines. |
| `SAO/Misc/latch_head_overrides.json` | SAO | Human-supplied facts checkpoints don't carry — chiefly which chroma readout a 12-d head used. Data, not code. |
| `SAO/eval/presets.py` | SAO | Preset = a render payload + name + notes + schema version. Save/load/list/validate/redact. ~150 lines. |
| `SAO/eval/sweep_spec.py` | SAO | The sweep grammar: axes → cells, deterministic cell ids, JSON round-trip. Pure functions, no I/O beyond file read/write. ~200 lines. |
| `SAO/eval/sweep_run.py` | SAO | The CLI. HTTP client of :8056, resumable, writes `manifest.jsonl`. ~300 lines. |
| `SAO/eval/build_sweep_page.py` | SAO | Manifest → three-audience eval page per the eval-tables spec. ~350 lines. |
| `SAO/eval/tests/test_head_meta.py`, `test_presets.py`, `test_sweep_spec.py`, `test_sweep_run.py` | SAO | CPU-only unit tests, `tmp_path` fixtures, no GPU, no live server. |
| `SAO/eval/explorer_render_server.py` | SAO | Modify: `_head_entry` delegates to `head_meta`; `scan_latch_heads` fixes the chroma path; add `GET/POST /presets`. |
| `mir/plots/explorer_sa3/controls.py` | mir | Modify: per-head bounds + range meter + capability gating + health flag + hover help + a retry path for the empty-dropdown bug. |
| `mir/plots/explorer_sa3/render_client.py` | mir | Modify: add `presets_list()`, `preset_save()`, `preset_load()`. |

---

## Task 1: `head_meta.py` — one honest description of a LatCH head

**Files:**
- Create: `/home/kim/Projects/SAO/eval/head_meta.py`
- Create: `/home/kim/Projects/SAO/Misc/latch_head_overrides.json`
- Test: `/home/kim/Projects/SAO/eval/tests/test_head_meta.py`

**Interfaces:**
- Consumes: `stable_audio_3.models.latch.load_latch_from_checkpoint` (already imported by the server).
- Produces:
  - `SCHEMA_VERSION: int = 1`
  - `OVERRIDES_PATH: Path` = `/home/kim/Projects/SAO/Misc/latch_head_overrides.json`
  - `describe(name: str, family: str, path: str, default_gain: float, *, metadata: dict | None = None, overrides: dict | None = None, sigma_k: float = 2.0) -> dict`
  - `load_overrides(path: str | Path | None = None) -> dict`
  - `slider_bounds(std_mean: float, std_std: float, sigma_k: float = 2.0) -> tuple[float, float, float]`

**The enriched entry.** `describe()` returns the server's existing `/info` head dict (every key kept, same names — the viewer's `_autofill_defaults` at `controls.py:243` depends on them) plus these new keys:

```python
{
  # --- unchanged, existing consumers rely on these ---
  "name": "rms_energy_bass", "family": "medium", "path": "/abs/...",
  "default_gain": 512.0, "out_channels": 1, "loss_type": "smooth_l1",
  "target_kind_default": "constant",
  "slider_min": -50.99, "slider_max": 7.13, "value_default": -21.93,   # NOW DERIVED
  # --- new ---
  "std_mean": -21.93, "std_std": 14.53, "standardized": True,
  "sigma_k": 2.0,                       # bounds are std_mean +/- sigma_k*std_std
  "units": "dB",                        # "dB" | "bpm" | "" — from the name, see below
  "epoch": 18, "avg_loss": 0.0421, "val_loss": None, "selected_on": "train_loss",
  "health": "ok",                       # "ok" | "undertrained" | "unstable" | "unknown"
  "health_reason": "",                  # human sentence, "" when ok
  "supports_scalar_target": True,       # False when out_channels > 1
  "supports_loss_select": True,         # False when loss_type == "cosine"
  "supports_kinds": ["constant", "ramp_up", "ramp_down", "beat_grid"],
  "readout": "unknown",                 # "hpcp" | "same_chroma_other" | ... | "n/a" | "unknown"
  "readout_source": "not-recorded",     # "checkpoint" | "overrides" | "not-recorded" | "n/a"
  "gain_scale_note": "auto rho/mu = this slot's gain (512.0)",
  "schema": 1,
}
```

**Rules, each with its evidence:**

- `slider_bounds`: `lo = std_mean - k*std_std`, `hi = std_mean + k*std_std`, `default = std_mean`, `k = 2.0`. When `std_std <= 0` or either is non-finite, fall back to `(-80.0, 20.0, -30.0)` — the current server default (`explorer_render_server.py:277`) — so nothing regresses. Valid because the typed value is in raw units (`model.py:529-542`).
- `health`: `"undertrained"` when `epoch < 10` (evidence: `spectral_kurtosis` stopped at epoch 3 while every other head reached 18–20 — see the measured table in `docs/INFERENCE-SURFACE.md`); `"unstable"` when `std_std > 100.0` (`spectral_kurtosis` σ = 521.6, next-largest is `rms_energy_body` at 35.4); `"unknown"` when `epoch` is absent. Both conditions may hold — report `"undertrained"` and put the σ in `health_reason`. `health_reason` for the kurtosis case must read like: `"trained only 3 epochs (others reached 20) and dataset sigma is 521.6 — treat its output as unreliable"`.
- `supports_scalar_target = (out_channels == 1)`. `same_chroma` is 384-ch: a scalar `value` is meaningless for it (`docs/INFERENCE-SURFACE.md`, LatCH panel block). When False, `supports_kinds = []` — `build_target` broadcasts a scalar across all channels (`latch_targets.py:29`), which for a 384-d chroma target means "every pitch class equally loud", i.e. nothing musical.
- `supports_loss_select = (loss_type != "cosine")`. Cosine is the 384-d chroma objective; swapping it for `smooth_l1` on a 384-d head is not a knob, it is a bug.
- `units`: `"dB"` if the name starts with `rms_`, `"bpm"` if `target_kind_default == "beat_grid"`, else `""`. Anything more clever is guessing.
- `readout`: for `out_channels == 1`, `"n/a"` / `"n/a"`. For a multi-channel head, look up `overrides[name]["readout"]`; if present → `readout_source = "overrides"`. Else, if the metadata itself carries `chroma_key` or `target_source` (future checkpoints, Step 9) → `"checkpoint"`. Else `"unknown"` / `"not-recorded"`.
- `gain_scale_note` is always phrased in the **normalised** scale. Exact string: `f"auto rho/mu = this slot's gain ({default_gain:g}); per-slot weight = slot_gain / slot-1 gain"` (source: `resolve_latch:514-517`).

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_head_meta.py`:

```python
import json
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import head_meta


def _md(**kw):
    base = {"feature_name": "rms_energy_bass", "out_channels": 1,
            "loss_type": "smooth_l1", "standardized": True,
            "std_mean": -21.93, "std_std": 14.53, "epoch": 18, "avg_loss": 0.04}
    base.update(kw)
    return base


def d(**kw):
    return head_meta.describe("rms_energy_bass", "medium", "/tmp/x.pt", 512.0,
                              metadata=_md(**kw), overrides={})


def test_slider_bounds_are_two_sigma_around_the_dataset_mean():
    h = d()
    assert h["slider_min"] == -50.99
    assert h["slider_max"] == 7.13
    assert h["value_default"] == -21.93


def test_degenerate_sigma_falls_back_to_the_servers_old_default():
    h = d(std_std=0.0)
    assert (h["slider_min"], h["slider_max"], h["value_default"]) == (-80.0, 20.0, -30.0)


def test_a_384_channel_cosine_head_disables_scalar_target_and_loss_select():
    h = head_meta.describe("same_chroma", "medium", "/tmp/c.pt", 512.0,
                           metadata=_md(feature_name="same_chroma", out_channels=384,
                                        loss_type="cosine", standardized=False,
                                        std_mean=0.0, std_std=1.0, epoch=20),
                           overrides={})
    assert h["supports_scalar_target"] is False
    assert h["supports_loss_select"] is False
    assert h["supports_kinds"] == []


def test_an_undertrained_head_is_flagged_with_a_reason_naming_both_facts():
    h = d(feature_name="spectral_kurtosis", epoch=3, std_mean=15.72, std_std=521.6)
    assert h["health"] == "undertrained"
    assert "3" in h["health_reason"] and "521.6" in h["health_reason"]


def test_a_healthy_scalar_head_is_ok_with_an_empty_reason():
    h = d()
    assert h["health"] == "ok" and h["health_reason"] == ""


def test_chroma_readout_is_reported_as_not_recorded_when_nothing_knows_it():
    h = head_meta.describe("hpcp", "medium", "/tmp/h.pt", 512.0,
                           metadata=_md(feature_name="hpcp", out_channels=12), overrides={})
    assert h["readout"] == "unknown"
    assert h["readout_source"] == "not-recorded"


def test_an_override_supplies_the_readout_and_says_so():
    ov = {"hpcp": {"readout": "essentia_hpcp_12"}}
    h = head_meta.describe("hpcp", "medium", "/tmp/h.pt", 512.0,
                           metadata=_md(feature_name="hpcp", out_channels=12), overrides=ov)
    assert h["readout"] == "essentia_hpcp_12"
    assert h["readout_source"] == "overrides"


def test_a_scalar_head_reports_readout_not_applicable():
    assert d()["readout"] == "n/a"


def test_the_gain_note_is_in_the_normalised_scale():
    note = d()["gain_scale_note"]
    assert "512" in note and "slot-1 gain" in note


def test_rms_heads_are_labelled_dB():
    assert d()["units"] == "dB"


def test_every_legacy_info_key_survives():
    h = d()
    for k in ("name", "family", "path", "default_gain", "out_channels",
              "loss_type", "target_kind_default", "slider_min", "slider_max",
              "value_default"):
        assert k in h, k


def test_load_overrides_returns_empty_dict_when_the_file_is_absent(tmp_path):
    assert head_meta.load_overrides(tmp_path / "nope.json") == {}


def test_load_overrides_reads_the_file(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps({"hpcp": {"readout": "x"}}))
    assert head_meta.load_overrides(p)["hpcp"]["readout"] == "x"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_head_meta.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'head_meta'`.

- [ ] **Step 3: Implement `head_meta.py`**

Write `/home/kim/Projects/SAO/eval/head_meta.py`. Key parts (`describe` is the only entry point the server calls):

```python
"""One honest description of a LatCH head, from its own checkpoint metadata.

Why this exists: explorer_render_server._head_entry derived its slider from
md["slider_min"] / md["feature_stats"], and scripts/latch/train_latch.py:467-490
writes NEITHER — so every head fell through to a shared -80/20/-30 default that is
right for the dB-valued rms_* family and wrong for everything else. The keys that
ARE written are std_mean / std_std, and the value the user types is in RAW feature
units (model.py:529-542 standardizes it after target construction), so the dataset
range is directly the right slider range.
"""
from __future__ import annotations
import json, math
from pathlib import Path

SCHEMA_VERSION = 1
OVERRIDES_PATH = Path("/home/kim/Projects/SAO/Misc/latch_head_overrides.json")
_FALLBACK = (-80.0, 20.0, -30.0)       # explorer_render_server.py:277, kept for parity
UNDERTRAINED_EPOCHS = 10               # others reach 18-20; spectral_kurtosis stopped at 3
UNSTABLE_SIGMA = 100.0                 # next-largest real sigma is 35.4


def _num(v, default=None):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def slider_bounds(std_mean, std_std, sigma_k=2.0):
    m, s = _num(std_mean), _num(std_std)
    if m is None or s is None or s <= 0.0:
        return _FALLBACK
    return (round(m - sigma_k * s, 6), round(m + sigma_k * s, 6), round(m, 6))


def load_overrides(path=None):
    p = Path(path) if path is not None else OVERRIDES_PATH
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _health(epoch, std_std):
    e, s = _num(epoch), _num(std_std)
    bits = []
    if s is not None and s > UNSTABLE_SIGMA:
        bits.append(f"dataset sigma is {s:g}")
    if e is None:
        return ("unknown", "checkpoint records no epoch count")
    if e < UNDERTRAINED_EPOCHS:
        bits.insert(0, f"trained only {e:g} epochs (others reached 20)")
        return ("undertrained", " and ".join(bits) + " -- treat its output as unreliable")
    if bits:
        return ("unstable", " and ".join(bits) + " -- targets far from the mean will be violent")
    return ("ok", "")


def _units(name, kind_default):
    if name.startswith("rms_"):
        return "dB"
    if kind_default == "beat_grid":
        return "bpm"
    return ""


def describe(name, family, path, default_gain, *, metadata=None,
             overrides=None, sigma_k=2.0):
    md = dict(metadata or {})
    ov = (overrides if overrides is not None else load_overrides()).get(name, {})
    out_ch = int(_num(md.get("out_channels"), 1) or 1)
    loss = md.get("loss_type")
    kind_default = md.get("target_kind_default", "constant")
    smin, smax, sval = slider_bounds(md.get("std_mean"), md.get("std_std"), sigma_k)
    health, reason = _health(md.get("epoch"), md.get("std_std"))
    scalar_ok = out_ch == 1
    if not scalar_ok:
        readout = ov.get("readout") or md.get("chroma_key") or md.get("target_source")
        src = ("overrides" if ov.get("readout") else
               "checkpoint" if readout else "not-recorded")
        readout = readout or "unknown"
    else:
        readout, src = "n/a", "n/a"
    return {
        "name": name, "family": family, "path": str(path),
        "default_gain": float(default_gain), "out_channels": out_ch,
        "loss_type": loss, "target_kind_default": kind_default,
        "slider_min": smin, "slider_max": smax, "value_default": sval,
        "std_mean": _num(md.get("std_mean")), "std_std": _num(md.get("std_std")),
        "standardized": bool(md.get("standardized", False)), "sigma_k": float(sigma_k),
        "units": _units(name, kind_default),
        "epoch": _num(md.get("epoch")), "avg_loss": _num(md.get("avg_loss")),
        "val_loss": _num(md.get("val_loss")), "selected_on": md.get("selected_on"),
        "health": health, "health_reason": reason,
        "supports_scalar_target": scalar_ok,
        "supports_loss_select": loss != "cosine",
        "supports_kinds": ["constant", "ramp_up", "ramp_down", "beat_grid"] if scalar_ok else [],
        "readout": readout, "readout_source": src,
        "gain_scale_note": (f"auto rho/mu = this slot's gain ({float(default_gain):g}); "
                            f"per-slot weight = slot_gain / slot-1 gain"),
        "schema": SCHEMA_VERSION,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_head_meta.py -v`
Expected: 13 passed.

- [ ] **Step 5: Create the overrides file with the honest current state**

Write `/home/kim/Projects/SAO/Misc/latch_head_overrides.json`:

```json
{
  "_README": "Facts a LatCH checkpoint does not carry. scripts/latch/train_latch.py:467-490 saves feature_name but NOT --target-source / --chroma-dir / --chroma-key, so for heads trained before 2026-08-24 the chroma readout is unrecoverable from the file. Fill 'readout' here only from a training log or run script you actually read; leave it out rather than guess. 'readout' values seen in train_latch.py:511 are the --chroma-key choices: other / bass / full_mix; a 12-d head is an HPCP readout, not a SAME-chroma one.",
  "same_chroma": {
    "readout": "same_chroma_3band_384",
    "note": "3-band SAME chroma, octave centres 1/5/9, 128 bins each. Cosine loss, unstandardised. Needs a 384-d target, not a scalar."
  }
}
```

- [ ] **Step 6: PROBE — recover the 12-d heads' readouts if a training log records it**

Kim: *"of the older 12d ones we have trained them with two different chroma readouts"*. The checkpoints do not say which. Before concluding, check the two logs that might:

Run: `grep -n "chroma-key\|chroma_key\|target-source\|--feature hpcp\|--feature .*chroma" /home/kim/Projects/SAO/stable-audio-3/latch_sweep_train.log /home/kim/Projects/SAO/stable-audio-3/latch_ema_sweep.log /home/kim/Projects/SAO/stable-audio-3/latch_sweep_train.sh /home/kim/Projects/SAO/stable-audio-3/latch_ema_sweep.sh 2>/dev/null | head -40`

Then locate every 12-d head across the five head dirs:

Run: `cd /home/kim/Projects/SAO/stable-audio-3 && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -c "
import torch, glob
for p in sorted(glob.glob('latch_weights_*/**/*.pt', recursive=True)):
    try: r = torch.load(p, map_location='cpu', weights_only=True)
    except Exception: continue
    if not isinstance(r, dict) or 'state_dict' not in r: continue
    oc = r.get('out_channels')
    if oc in (12, 384): print(oc, r.get('feature_name'), r.get('loss_type'), p)
"`

- If a log names the `--chroma-key` / `--target-source` for a head: add it to `latch_head_overrides.json` with `\"source\": \"<log path>:<line>\"`.
- If nothing records it: **leave the entry out.** `readout_source: "not-recorded"` is the correct, honest answer and the UI will say so. Write the conclusion into `docs/INFERENCE-SURFACE.md` in Task 10 either way.

- [ ] **Step 7: Write the failing test for future-proofing the trainer**

Append to `/home/kim/Projects/SAO/eval/tests/test_head_meta.py`:

```python
def test_a_future_checkpoint_that_records_its_readout_is_believed():
    h = head_meta.describe("hpcp2", "medium", "/tmp/h2.pt", 512.0,
                           metadata={"out_channels": 12, "loss_type": "smooth_l1",
                                     "std_mean": 0.24, "std_std": 0.27, "epoch": 20,
                                     "chroma_key": "full_mix"},
                           overrides={})
    assert h["readout"] == "full_mix"
    assert h["readout_source"] == "checkpoint"
```

- [ ] **Step 8: Run it**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_head_meta.py -v`
Expected: 14 passed (the implementation in Step 3 already reads `chroma_key`).

- [ ] **Step 9: Make the trainer record it from now on**

Edit `/home/kim/Projects/SAO/stable-audio-3/scripts/latch/train_latch.py`, in the `torch.save({...})` dict at `:467-490`, immediately after `"feature_name": args.feature,`:

```python
                # Provenance for the target itself. Before 2026-08-24 only
                # feature_name was saved, so a 12-d head could not be traced back
                # to WHICH chroma readout it was trained against (Kim, 2026-08-24).
                "target_source": args.target_source,
                "chroma_dir": args.chroma_dir,
                "chroma_key": args.chroma_key,
                "feature_db": getattr(args, "feature_db", None),
```

If `args.feature_db` does not exist, drop that line rather than inventing an attribute — verify with `grep -n "feature.db\|feature_db" /home/kim/Projects/SAO/stable-audio-3/scripts/latch/train_latch.py` first.

- [ ] **Step 10: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/head_meta.py eval/tests/test_head_meta.py Misc/latch_head_overrides.json stable-audio-3/scripts/latch/train_latch.py
git commit -m "feat(latch): head_meta -- real per-head slider bounds, capability + health flags, readout provenance"
```

---

## Task 2: Server — `/info` tells the truth, and the chroma head stops pointing at a dead path

**Files:**
- Modify: `/home/kim/Projects/SAO/eval/explorer_render_server.py` — imports (~line 50), `_head_entry` (`:274-303`), `scan_latch_heads` (`:305-312`)
- Test: `/home/kim/Projects/SAO/eval/tests/test_server_heads.py` (create)

**Interfaces:**
- Consumes: `head_meta.describe`, `head_meta.load_overrides` (Task 1); the existing `_mantu_root()` (`:76`).
- Produces: `GET /info` → `latch_heads: [<the Task-1 dict>]`, every legacy key preserved; `srv._chroma_head_path() -> str | None`.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_server_heads.py`:

```python
import sys
import pytest

sys.path.insert(0, "/home/kim/Projects/SAO/eval")


def test_chroma_head_path_is_resolved_against_the_live_mount_not_a_literal():
    import explorer_render_server as srv
    p = srv._chroma_head_path()
    assert p is None or "Mantu1" not in p or srv._mantu_root().endswith("Mantu1")


def test_head_entry_carries_the_new_metadata_keys(monkeypatch):
    import explorer_render_server as srv

    class FakeHead:
        metadata = {"out_channels": 1, "loss_type": "smooth_l1", "std_mean": -21.93,
                    "std_std": 14.53, "epoch": 18, "avg_loss": 0.04, "standardized": True}
        class out_proj:
            weight = type("W", (), {"shape": (1, 1)})()

    monkeypatch.setattr(srv, "load_latch_from_checkpoint", lambda *a, **k: FakeHead())
    e = srv._head_entry("rms_energy_bass", "medium", "/tmp/x.pt", 512.0)
    assert e["slider_min"] == -50.99 and e["slider_max"] == 7.13
    assert e["health"] == "ok" and e["supports_scalar_target"] is True
    assert "512" in e["gain_scale_note"]


def test_an_unloadable_head_still_yields_an_entry_with_a_scan_error(monkeypatch):
    import explorer_render_server as srv

    def boom(*a, **k):
        raise FileNotFoundError("gone")

    monkeypatch.setattr(srv, "load_latch_from_checkpoint", boom)
    e = srv._head_entry("ghost", "chroma", "/nope.pt", 2048.0)
    assert "scan_error" in e and e["name"] == "ghost"
    assert e["slider_min"] == -80.0          # documented fallback, unchanged
```

- [ ] **Step 2: Run it**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_server_heads.py -v`
Expected: FAIL — `_chroma_head_path` does not exist; `slider_min` is `-80.0` not `-50.99`.

- [ ] **Step 3: Rewrite `_head_entry` to delegate**

Replace the body of `_head_entry` (`explorer_render_server.py:274-303`) with:

```python
def _head_entry(name, family, path, default_gain):
    """Enriched head description. The slider derivation moved to head_meta.py:
    the old md["slider_min"] / md["feature_stats"] lookup read keys that
    scripts/latch/train_latch.py:467-490 never writes, so every head silently
    got the same -80/20/-30 range (Kim, 2026-08-24)."""
    try:
        head = load_latch_from_checkpoint(str(path), device="cpu")  # never hardcode arch
        md = dict(getattr(head, "metadata", None) or {})
        md.setdefault("out_channels", int(head.out_proj.weight.shape[0]))
        del head
        info = head_meta.describe(name, family, path, default_gain,
                                  metadata=md, overrides=_HEAD_OVERRIDES)
    except Exception as e:                      # unmounted drive etc: keep the entry
        info = head_meta.describe(name, family, path, default_gain,
                                  metadata={}, overrides=_HEAD_OVERRIDES)
        info["scan_error"] = str(e)
        info["health"] = "unknown"
        info["health_reason"] = f"checkpoint could not be read: {e}"
    return info
```

Add near the other module constants (after `MEDIUM_HEAD_DIR` at `:71`):

```python
import head_meta                                  # eval/ is on sys.path already
_HEAD_OVERRIDES = head_meta.load_overrides()
```

- [ ] **Step 4: Fix the chroma head's hardcoded `Mantu1`**

`eval/chroma_morph_transitions.py:46` hardcodes `/run/media/kim/Mantu1/...`, which violates the no-hardcoded-drive-paths rule and is the mount name that does not exist today. Do NOT edit `chroma_morph_transitions.py` (other consumers depend on the constant); resolve it at the server boundary. Replace `scan_latch_heads` (`:305-312`) with:

```python
def _chroma_head_path():
    """cmt.CHROMA_HEAD is a literal under /run/media/kim/Mantu1 (chroma_morph_
    transitions.py:46). The eval drive mounts as Mantu OR Mantu1 depending on
    label collision at mount time, so re-root it onto whichever is live."""
    raw = str(cmt.CHROMA_HEAD)
    if os.path.exists(raw):
        return raw
    for stale in ("/run/media/kim/Mantu1", "/run/media/kim/Mantu"):
        if raw.startswith(stale):
            cand = _MANTU + raw[len(stale):]
            if os.path.exists(cand):
                return cand
    return None


def scan_latch_heads():
    for p in sorted(MEDIUM_HEAD_DIR.glob("latch_sa3_*_best.pt")):
        name = p.stem[len("latch_sa3_"):-len("_best")]
        HEADS[name] = _head_entry(name, "medium", p, 512.0)
    n_medium = len(HEADS)
    # The 17th head. NOT from MEDIUM_HEAD_DIR -- a different family, a different
    # default gain (2048 vs 512), and its own readout. Kept explicit so the UI can
    # say so instead of showing it as a peer of the 16 medium heads.
    cp = _chroma_head_path()
    if cp:
        HEADS["chroma_other"] = _head_entry("chroma_other", "chroma", cp, cmt.CHROMA_GAIN)
    else:
        log(f"[boot] chroma_other SKIPPED: {cmt.CHROMA_HEAD} not found under {_MANTU}")
    gc.collect()
    log(f"[boot] latch registry: {len(HEADS)} heads ({n_medium} medium + "
        f"{len(HEADS) - n_medium} chroma)")
```

Confirm `import os` is already at the top of the file (it is — `_mantu_root` at `:76` uses `os.path.isdir`).

- [ ] **Step 5: Run the tests**

Run: `cd /home/kim/Projects/SAO/eval && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_server_heads.py tests/test_head_meta.py -v`
Expected: all pass.

- [ ] **Step 6: Verify against the live server**

Start it: `cd /home/kim/Projects/SAO && .venv/bin/python eval/explorer_render_server.py`
Then in another shell:

```bash
curl -s localhost:8056/info | /home/kim/Projects/SAO/.venv/bin/python -c "
import json,sys
h = json.load(sys.stdin)['latch_heads']
print(len(h), 'heads')
for e in h:
    print(f\"{e['name']:24s} {e.get('family'):8s} out={e['out_channels']:<4} \"
          f\"[{e['slider_min']:.3g}, {e['slider_max']:.3g}] def={e['value_default']:.3g} \"
          f\"health={e['health']}\")
"
```
Expected: 17 heads (16 medium + 1 chroma), `rms_energy_bass` at roughly `[-50.99, 7.13]`, `spectral_kurtosis` `health=undertrained`, `same_chroma` `supports_scalar_target=False`. If `chroma_other` is absent, the boot log names the missing path — that is a real finding, record it in Task 10, don't paper over it.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/explorer_render_server.py eval/tests/test_server_heads.py
git commit -m "fix(server): per-head slider bounds from checkpoint stats; re-root the chroma head off the dead Mantu1 literal"
```

---

## Task 3: Viewer — the LatCH panel stops lying

**Files:**
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/controls.py` — `_latch_slot` (`:45-60`), the advanced-hparam row (`:110-135`), `register()` (`:225-254`)
- Test: manual, plus the PROBE in Step 7 (Dash callbacks are not unit-testable here without a harness this repo does not have)

**Interfaces:**
- Consumes: the Task-2 `/info` head dicts via the existing `render_client.info()`.
- Produces: per-slot ids `{ns}-ctl-latch{i}-meter` (a `html.Div`) and `{ns}-ctl-latch{i}-health` (a `html.Span`). `steering_states(ns)` must still return EXACTLY the same 23 States in the same order — the meter and health are OUTPUTS only, never States. Breaking that breaks `steering_payload` and every tab.

Work in the mir repo on branch `sa3-latent-explorer`. Run the viewer with `/home/kim/Projects/mir/mir/bin/python`.

- [ ] **Step 1: Add the meter and health elements to each slot**

In `_latch_slot` (`controls.py:45`), after the `-value` `dcc.Input`, add:

```python
        html.Div(id=f"{p}-meter", style={"minWidth": "260px", "fontSize": "11px",
                                         "color": "#888"}),
        html.Span(id=f"{p}-health", style={"fontSize": "11px", "fontWeight": "bold"}),
```

- [ ] **Step 2: Extend the autofill callback to drive bounds, meter, health and gating**

Replace the `_autofill_defaults` callback in `register()` (`controls.py:238-254`) with one that also sets the numeric input's `min`/`max`/`step`, its `disabled` flag, the loss dropdown's `disabled` flag, the kind dropdown's `options`, and the two new display elements:

```python
        @app.callback(
            Output(f"{ns}-ctl-latch{i}-gain", "value"),
            Output(f"{ns}-ctl-latch{i}-kind", "value"),
            Output(f"{ns}-ctl-latch{i}-kind", "options"),
            Output(f"{ns}-ctl-latch{i}-value", "value"),
            Output(f"{ns}-ctl-latch{i}-value", "min"),
            Output(f"{ns}-ctl-latch{i}-value", "max"),
            Output(f"{ns}-ctl-latch{i}-value", "step"),
            Output(f"{ns}-ctl-latch{i}-value", "disabled"),
            Output(f"{ns}-ctl-latch{i}-value", "title"),
            Output(f"{ns}-ctl-latch{i}-loss", "value"),
            Output(f"{ns}-ctl-latch{i}-loss", "disabled"),
            Output(f"{ns}-ctl-latch{i}-loss", "title"),
            Output(f"{ns}-ctl-latch{i}-meter", "children"),
            Output(f"{ns}-ctl-latch{i}-health", "children"),
            Output(f"{ns}-ctl-latch{i}-health", "style"),
            Input(head_id, "value"))
        def _autofill_defaults(head):
            blank = (no_update,) * 15
            if head in (None, "none", ""):
                return blank
            srv = render_client.info()
            if not srv:
                return blank
            h = next((x for x in srv.get("latch_heads", []) if x["name"] == head), None)
            if h is None:
                return blank
            return _slot_view(h)
```

- [ ] **Step 3: Write `_slot_view` — the pure function that turns a head dict into 15 outputs**

Add above `register()` in `controls.py`. Keeping it pure and separate is what makes Step 7 checkable without a browser.

```python
_HEALTH_COLOR = {"ok": "#3a3", "undertrained": "#c60", "unstable": "#c00",
                 "unknown": "#888"}


def _slot_view(h: dict) -> tuple:
    """head dict from /info -> the 15 Outputs of _autofill_defaults."""
    scalar = h.get("supports_scalar_target", True)
    loss_ok = h.get("supports_loss_select", True)
    lo, hi = h.get("slider_min"), h.get("slider_max")
    units = h.get("units") or ""
    step = round(max((hi - lo) / 200.0, 1e-4), 6) if (lo is not None and hi is not None) else 0.1
    kinds = h.get("supports_kinds") or _KIND_OPTIONS

    if scalar and h.get("std_mean") is not None:
        m, s, k = h["std_mean"], h.get("std_std") or 0.0, h.get("sigma_k", 2.0)
        meter = f"dataset {m:.4g} ± {s:.4g}{(' ' + units) if units else ''}  ·  slider = mean ± {k:g}σ"
        vtitle = (f"Target value in the head's own units{(' (' + units + ')') if units else ''}. "
                  f"Dataset mean {m:.4g}, σ {s:.4g}. The server standardises this for you "
                  f"(model.py:539-541) — type raw units. Values far outside ±2σ are "
                  f"out-of-distribution: the head will still push, but toward audio it never saw.")
    elif not scalar:
        meter = (f"{h['out_channels']}-channel head — a single number cannot be a target for it. "
                 f"Use a measured curve (target_raw) instead.")
        vtitle = ("Disabled: this head predicts a vector per frame, so a scalar target means "
                  "'every channel equally', which is not musically meaningful.")
    else:
        meter = "no dataset statistics in this checkpoint — slider is the generic fallback"
        vtitle = "This checkpoint records no std_mean/std_std; bounds are the generic default."

    if loss_ok:
        ltitle = (f"Loss shaping. This head was TRAINED with '{h.get('loss_type')}' — leaving the "
                  f"box empty uses it. Overriding is legal and sometimes right (scalar_pooled is "
                  f"the 2026-07-10 fix for constant targets on scalar heads), but any other choice "
                  f"is a departure from how the head was fit.")
    else:
        ltitle = (f"Disabled: '{h.get('loss_type')}' is this head's objective, not a preference. "
                  f"Swapping it on a {h['out_channels']}-channel head is a bug, not a knob.")

    hl = h.get("health", "unknown")
    badge = "" if hl == "ok" else f"⚠ {hl}"
    hstyle = {"fontSize": "11px", "fontWeight": "bold",
              "color": _HEALTH_COLOR.get(hl, "#888"), "cursor": "help",
              "marginLeft": "6px"}
    if h.get("readout_source") == "not-recorded":
        badge = (badge + "  readout: unrecorded").strip()
    return (h.get("default_gain"), h.get("target_kind_default", "constant"), kinds,
            h.get("value_default"), lo, hi, step, not scalar, vtitle,
            h.get("loss_type") or "", not loss_ok, ltitle,
            meter, badge, hstyle)
```

The health badge's own hover text is the head's `health_reason`; wire it by adding a 16th Output `Output(f"{ns}-ctl-latch{i}-health", "title")` returning `h.get("health_reason") or ""` and returning 16 values from `_slot_view`. Do this now rather than later so the tuple width is settled once.

- [ ] **Step 4: Fix the empty-dropdown bug while you are in this callback**

`docs/INFERENCE-SURFACE.md` "KNOWN BUG": the head options callback (`controls.py:230`, `Input(head_id, "id")`) fires exactly once per page load and returns `[]` when :8056 is down, and Dash never re-fires it — so the panel stays empty forever with no error. Add a retry.

In `_latch_slot`, add one shared poller to the panel body (once per namespace, not per slot):

```python
        dcc.Interval(id=f"{ns}-ctl-info-poll", interval=5000, n_intervals=0,
                     max_intervals=-1),
```

and change the options callback to:

```python
        @app.callback(Output(head_id, "options"),
                      Output(head_id, "placeholder"),
                      Input(f"{ns}-ctl-info-poll", "n_intervals"),
                      prevent_initial_call=False)
        def _fill_options(_n):
            srv = render_client.info()
            if not srv:
                return [], "render server :8056 unreachable — start it, this retries every 5 s"
            return ([{"label": f"{h['name']} [{h.get('family', '?')}]", "value": h["name"]}
                     for h in srv.get("latch_heads", [])], "head (off)")
```

`render_client.info()` memoises successes only (per the doc), so the poll costs one HTTP round-trip every 5 s until the server answers and nothing after.

- [ ] **Step 5: Same retry for the checkpoint picker**

`inference_tab.py:432` fills `inf-ckpt-dd` from `Input("inf-ckpt-rescan", "n_clicks")`, which is `None` at load — the same fire-once trap. Add `Input(f"inf-ctl-info-poll", "n_intervals")` as a second Input to that callback and make the body tolerate `n_clicks is None` (rescan only when `n_clicks` actually changed — use `dash.callback_context` to distinguish). If the poller id is not in scope from `inference_tab.py`, add a dedicated `dcc.Interval(id="inf-ckpt-poll", interval=5000, max_intervals=-1)` to that tab's layout instead; do not reach across modules for an id.

- [ ] **Step 6: Advanced hparams — suggested values and hover help, in the NORMALISED scale**

In the "LatCH adv" row (`controls.py:110-125`), give each input a `title`. Verbatim strings (they encode `resolve_latch:514-517` and must not be paraphrased into a raw-weight claim):

```python
_RHO_HELP = ("ρ — guidance step size. LEAVE EMPTY. Empty means 'auto', and auto = slot 1's "
             "gain (512 for the medium heads, 2048 for chroma_other). The server sets "
             "rho = mu = slot-1 gain and then scales every other slot as "
             "slot_gain / slot-1 gain, so gains here are RELATIVE, not absolute — a raw "
             "weight taken from another tool is a different scale and will not reproduce. "
             "Override only to decouple step size from the slot balance; start at the "
             "auto value and move by factors of 2.")
_MU_HELP  = ("μ — proximal/consistency term, auto-tied to ρ (both default to slot 1's gain). "
             "Raising μ above ρ pulls harder toward the current latent, i.e. guidance bites "
             "less; lowering it lets guidance dominate and is where artefacts start. "
             "Change it only after ρ is settled, and change one at a time.")
_GAMMA_HELP = ("γ — inner-loop damping, default 0.3. Range 0.05–0.6 is usable. Lower = the "
               "correction is applied more gently over more iterations (safer, slower to "
               "take effect); higher = faster convergence and more risk of overshoot on "
               "heads with a large dataset σ. Try 0.15 for heads flagged unstable.")
_NITER_HELP = ("n_iter — guidance iterations per sampling step, default 4. Cost is roughly "
               "linear: 8 doubles the guidance cost of a render. 2 for a quick look, 4 to "
               "work, 8 when a target is being ignored and you have already tried raising "
               "the slot gain. Above 8 the returns are small and the artefacts are not.")
```

Attach with `dcc.Input(..., title=_RHO_HELP)` etc., and keep `placeholder="auto"` on ρ and μ — "auto" is the correct default and the help says so.

- [ ] **Step 7: PROBE the rendered panel end-to-end**

There is no Dash test harness in this repo, so verify by hand and record the result:

1. Start the render server, then the viewer (Global Constraints §8).
2. Open `http://localhost:8051`, Inference tab, expand "Steering (LatCH / FiLM / DoRA)".
3. Check, and write the outcome into the Task-10 doc update:
   - selecting `rms_energy_bass` → value box bounds ≈ `-50.99 … 7.13`, meter reads `dataset -21.93 ± 14.53 dB · slider = mean ± 2σ`;
   - selecting `same_chroma` → value box **disabled**, loss dropdown **disabled**, meter explains why;
   - selecting `spectral_kurtosis` → orange `⚠ undertrained` badge, hovering it gives the epoch-3 sentence;
   - selecting `hpcp` → badge includes `readout: unrecorded`;
   - hovering ρ/μ/γ/n_iter shows the four help strings;
   - killing the render server and reloading shows the "unreachable — retries every 5 s" placeholder, and restarting the server refills the dropdowns **without** a page reload.
4. The last one is the actual fix for the known bug — if it does not refill, the fault is not load-order and that is a finding worth its own line in `docs/INFERENCE-SURFACE.md`.

- [ ] **Step 8: Commit (mir repo)**

```bash
cd /home/kim/Projects/mir && git add plots/explorer_sa3/controls.py plots/explorer_sa3/inference_tab.py
git commit -m "feat(explorer): per-head LatCH bounds + range meter + health badge + capability gating; retry empty pickers"
```

---

## Task 4: `presets.py` — a render payload with a name

**Files:**
- Create: `/home/kim/Projects/SAO/eval/presets.py`
- Test: `/home/kim/Projects/SAO/eval/tests/test_presets.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `SCHEMA_VERSION: int = 1`
  - `PRESET_DIR: Path` = `/home/kim/Projects/SAO/eval/presets/`
  - `save(name: str, payload: dict, *, notes: str = "", dir: Path | None = None) -> Path`
  - `load(name: str, *, dir: Path | None = None) -> dict` → `{"schema", "name", "notes", "created", "payload"}`
  - `list_presets(dir: Path | None = None) -> list[dict]` — `{"name","notes","created","prompt"}`, newest first
  - `slug(name: str) -> str`
  - `VOLATILE_KEYS: frozenset` — keys stripped on save because they describe *this* render, not the recipe

**What a preset holds and what it deliberately drops.** A preset is the `/generate` payload verbatim, minus `VOLATILE_KEYS = frozenset({"seed", "batch_size", "job_id"})`. Seed is dropped because a preset is a *recipe*, and a sweep supplies its own seeds; a preset that pinned a seed would silently make every "seed" axis a no-op. Everything else — including `ckpt_path` and the whole `dora` block — is kept, because "the same preset on a different model" (Task 8) works by *overriding* those, and you want to see what the preset was authored against.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_presets.py`:

```python
import sys, time
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import presets


PAYLOAD = {"prompt": "goa lead", "duration": 47.0, "steps": 24, "cfg_scale": 7.0,
           "seed": 12345, "batch_size": 2,
           "latch": [{"head": "rms_energy_bass", "kind": "constant", "value": -18.0,
                      "gain": 512.0, "start_pct": 0.0, "end_pct": 0.6}],
           "dora": {"name": "hof", "strength": 1.0}, "gamma": 0.3, "n_iter": 4}


def test_saving_strips_the_seed_because_a_preset_is_a_recipe(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    p = presets.load("A", dir=tmp_path)["payload"]
    assert "seed" not in p and "batch_size" not in p


def test_saving_keeps_the_latch_block_intact(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    p = presets.load("A", dir=tmp_path)["payload"]
    assert p["latch"][0]["gain"] == 512.0 and p["latch"][0]["value"] == -18.0


def test_saving_does_not_mutate_the_callers_dict(tmp_path):
    before = dict(PAYLOAD)
    presets.save("A", PAYLOAD, dir=tmp_path)
    assert PAYLOAD == before and PAYLOAD["seed"] == 12345


def test_a_preset_round_trips_with_its_notes_and_schema(tmp_path):
    presets.save("My Preset", PAYLOAD, notes="the good one", dir=tmp_path)
    got = presets.load("My Preset", dir=tmp_path)
    assert got["notes"] == "the good one"
    assert got["schema"] == presets.SCHEMA_VERSION
    assert got["name"] == "My Preset"


def test_names_are_slugged_for_the_filename_but_kept_verbatim_inside(tmp_path):
    path = presets.save("Goa / lead #2", PAYLOAD, dir=tmp_path)
    assert path.name == "goa-lead-2.json"
    assert presets.load("Goa / lead #2", dir=tmp_path)["name"] == "Goa / lead #2"


def test_saving_the_same_name_twice_overwrites_rather_than_duplicating(tmp_path):
    presets.save("A", PAYLOAD, dir=tmp_path)
    presets.save("A", {**PAYLOAD, "steps": 40}, dir=tmp_path)
    assert presets.load("A", dir=tmp_path)["payload"]["steps"] == 40
    assert len(presets.list_presets(tmp_path)) == 1


def test_listing_is_newest_first_and_carries_the_prompt(tmp_path):
    presets.save("old", PAYLOAD, dir=tmp_path)
    time.sleep(0.01)
    presets.save("new", {**PAYLOAD, "prompt": "psy bass"}, dir=tmp_path)
    got = presets.list_presets(tmp_path)
    assert [g["name"] for g in got] == ["new", "old"]
    assert got[0]["prompt"] == "psy bass"


def test_an_empty_prompt_is_refused(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        presets.save("bad", {"prompt": "  ", "duration": 10}, dir=tmp_path)


def test_a_missing_preset_raises_a_named_error(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        presets.load("nope", dir=tmp_path)


def test_a_corrupt_preset_file_is_skipped_by_the_listing_not_fatal(tmp_path):
    presets.save("good", PAYLOAD, dir=tmp_path)
    (tmp_path / "junk.json").write_text("{ not json")
    assert [g["name"] for g in presets.list_presets(tmp_path)] == ["good"]
```

- [ ] **Step 2: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_presets.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'presets'`.

- [ ] **Step 3: Implement**

```python
"""A preset is a /generate payload with a name. Nothing more.

Deliberately NOT a new parameter model: the payload is passed to the render
server untouched, so a preset stays valid as the server grows knobs. seed and
batch_size are stripped because a preset is a recipe -- a pinned seed would make
a sweep's seed axis a silent no-op.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path

SCHEMA_VERSION = 1
PRESET_DIR = Path("/home/kim/Projects/SAO/eval/presets")
VOLATILE_KEYS = frozenset({"seed", "batch_size", "job_id"})


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")
    return s or "preset"


def _dir(d):
    p = Path(d) if d is not None else PRESET_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(name, payload, *, notes="", dir=None):
    if not str(payload.get("prompt", "")).strip():
        raise ValueError("a preset needs a non-empty prompt")
    body = {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
    p = _dir(dir) / f"{slug(name)}.json"
    p.write_text(json.dumps({"schema": SCHEMA_VERSION, "name": str(name),
                             "notes": str(notes), "created": time.time(),
                             "payload": body}, indent=2, sort_keys=True))
    return p


def load(name, *, dir=None):
    p = _dir(dir) / f"{slug(name)}.json"
    if not p.exists():
        raise FileNotFoundError(f"no preset {name!r} at {p}")
    return json.loads(p.read_text())


def list_presets(dir=None):
    out = []
    for p in _dir(dir).glob("*.json"):
        try:
            d = json.loads(p.read_text())
            out.append({"name": d["name"], "notes": d.get("notes", ""),
                        "created": d.get("created", 0.0),
                        "prompt": d.get("payload", {}).get("prompt", ""),
                        "path": str(p)})
        except (ValueError, KeyError):
            continue
    return sorted(out, key=lambda d: d["created"], reverse=True)
```

- [ ] **Step 4: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_presets.py -v`
Expected: 10 passed.

- [ ] **Step 5: Add `/presets` to the server**

In `eval/explorer_render_server.py`, after the `/ckpts` endpoint (`:584`):

```python
@app.get("/presets")
def presets_list():
    return {"presets": presets.list_presets()}


@app.get("/presets/{name}")
def presets_get(name: str):
    try:
        return presets.load(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/presets")
async def presets_post(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        p = presets.save(name, body.get("payload") or {}, notes=body.get("notes", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "name": name, "path": str(p)}
```

Add `import presets` next to `import head_meta`. Verify `HTTPException` is imported — `grep -n "HTTPException" eval/explorer_render_server.py`; if it is not, add it to the existing `from fastapi import ...` line.

- [ ] **Step 6: Verify against the live server**

```bash
curl -s -X POST localhost:8056/presets -H 'content-type: application/json' \
  -d '{"name":"smoke","payload":{"prompt":"a test tone","duration":10,"steps":8,"cfg_scale":7,"seed":1}}'
curl -s localhost:8056/presets
curl -s localhost:8056/presets/smoke
```
Expected: `ok:true`; the listing shows `smoke`; the fetch shows a payload with **no `seed` key**.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/presets.py eval/tests/test_presets.py eval/explorer_render_server.py
git commit -m "feat(presets): named render payloads + GET/POST /presets"
```

---

## Task 5: Viewer — save and load a preset from the tab you are already in

**Files:**
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/render_client.py` (add three functions after `ckpts()` at `:122`)
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/inference_tab.py` (preset row in the layout + two callbacks)

**Interfaces:**
- Consumes: `GET/POST /presets` (Task 4).
- Produces: `render_client.presets_list() -> list[dict] | None`, `render_client.preset_load(name) -> dict | None`, `render_client.preset_save(name, payload, notes="") -> dict | None`.

- [ ] **Step 1: Add the three client functions**

Follow the existing shape of `render_client.ckpts()` exactly — same timeout handling, same "return None on failure" convention (`controls.py` relies on falsy-means-unreachable):

```python
def presets_list(timeout: float = 5.0) -> list[dict] | None:
    try:
        r = requests.get(f"{BASE}/presets", timeout=timeout)
        r.raise_for_status()
        return r.json().get("presets", [])
    except Exception:
        return None


def preset_load(name: str, timeout: float = 5.0) -> dict | None:
    try:
        r = requests.get(f"{BASE}/presets/{name}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def preset_save(name: str, payload: dict, notes: str = "",
                timeout: float = 10.0) -> dict | None:
    try:
        r = requests.post(f"{BASE}/presets",
                          json={"name": name, "payload": payload, "notes": notes},
                          timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
```

Confirm the module's import name for the HTTP library first: `grep -n "^import\|^from" /home/kim/Projects/mir/plots/explorer_sa3/render_client.py` and match it (do not assume `requests`).

- [ ] **Step 2: Add the preset row to `inference_tab.py`**

A dropdown of saved presets, a Load button, a name box, a Save button, a status span:

```python
html.Div([
    html.Span("Preset", style={"minWidth": "60px", "fontWeight": "bold"}),
    dcc.Dropdown(id="inf-preset-dd", options=[], value=None, clearable=True,
                 placeholder="saved presets", style={"width": "300px"}),
    html.Button("Load", id="inf-preset-load", n_clicks=0),
    dcc.Input(id="inf-preset-name", type="text", placeholder="save as…",
              style={"width": "200px"}),
    html.Button("Save", id="inf-preset-save", n_clicks=0),
    html.Span(id="inf-preset-status", style={"fontSize": "11px", "color": "#888"}),
], style={"display": "flex", "gap": "6px", "alignItems": "center",
          "marginBottom": "6px"}),
```

- [ ] **Step 3: Wire Save**

Save reuses the tab's EXISTING payload builder — find it with `grep -n "steering_payload\|def _payload\|payload = " /home/kim/Projects/mir/plots/explorer_sa3/inference_tab.py`. The Save callback must take the SAME `State`s the render button takes and call the SAME builder function. **Do not write a second payload builder** — a preset that does not round-trip to the same render is worse than no preset. If the render callback builds its payload inline, extract that block into a module-level `def build_payload(*vals) -> dict` first, have the render callback call it, and only then add Save. That extraction is part of this step.

- [ ] **Step 4: Wire Load**

Load fans the stored payload back out to every control. Emit one `Output(id, "value")` per control in the same order `build_payload` consumes them, using `.get(key, no_update)` so a preset saved before a knob existed leaves that knob alone. Populate the dropdown's options from `presets_list()` on the same 5 s poller added in Task 3 Step 5, so the list refreshes after a save without a reload.

- [ ] **Step 5: Manual verification**

Set a distinctive configuration (prompt, cfg 12, two LatCH slots with non-default gains, γ 0.15, n_iter 8), Save as `roundtrip-test`, change every control, Load it back, and confirm all of it returns. Then render once from the preset and once from a hand-restored configuration with the same explicit seed and confirm the two wavs are byte-identical:
`cmp <(sha256sum a.wav | cut -d' ' -f1) <(sha256sum b.wav | cut -d' ' -f1)`.
If they differ, the payload builder is not the single source of truth — fix that before continuing, because Tasks 6–8 all assume a preset is exactly what the GUI would have sent.

- [ ] **Step 6: Commit (mir repo)**

```bash
cd /home/kim/Projects/mir && git add plots/explorer_sa3/render_client.py plots/explorer_sa3/inference_tab.py
git commit -m "feat(explorer): save/load named presets against the render server"
```

---

## Task 6: `sweep_spec.py` — axes, cells, and a resumable identity

**Files:**
- Create: `/home/kim/Projects/SAO/eval/sweep_spec.py`
- Test: `/home/kim/Projects/SAO/eval/tests/test_sweep_spec.py`

**Interfaces:**
- Consumes: `presets.load` (Task 4) at the CLI boundary only; this module takes a payload dict.
- Produces:
  - `SCHEMA_VERSION: int = 1`
  - `AXIS_KINDS: dict[str, str]` — axis name → dotted payload path
  - `expand(payload: dict, axes: dict[str, list], *, seeds: list[int] | None = None) -> list[dict]` → cells, each `{"cell_id", "coords", "payload"}`
  - `cell_id(coords: dict) -> str`
  - `set_path(payload: dict, dotted: str, value) -> dict` (returns a deep copy; never mutates)
  - `load_spec(path) -> dict`, `validate_spec(spec: dict) -> list[str]` (returns problems; empty = ok)

**Axis grammar.** An axis is a name and a list of values. Names map to dotted paths in the payload:

```python
AXIS_KINDS = {
    "strength":  "dora.strength",
    "cfg":       "cfg_scale",
    "steps":     "steps",
    "duration":  "duration",
    "prompt":    "prompt",
    "apg":       "apg_scale",
    "gamma":     "gamma",
    "n_iter":    "n_iter",
    "rho":       "rho",
    "mu":        "mu",
    "latch1_value": "latch.0.value",
    "latch1_gain":  "latch.0.gain",
    "latch1_head":  "latch.0.head",
    "latch2_value": "latch.1.value",
    "latch2_gain":  "latch.1.gain",
    "film_value":   "film.value",
    "film_gain":    "film.gain",
    "model":     "ckpt_path",       # Task 8 rewrites this from a model-db id
}
```
An integer path segment indexes a list (`latch.0.value`). A raw dotted path not in `AXIS_KINDS` is allowed and used verbatim — the map is ergonomics, not a whitelist, so the sweep does not need editing every time the server grows a knob.

**Seeds are a separate argument, not an axis**, because they multiply every other axis and because a preset has no seed (Task 4). `seeds=None` means one cell per coord-combination with `seed: -1` (the server resolves it and reports it back).

**`cell_id` is the resume key**: `sha1` of the JSON-canonical `coords` dict, first 12 hex chars, prefixed by a readable stem. E.g. `strength1.5__cfg7__s42__a91c3f0d1e22`. Readable prefix for humans, hash suffix for correctness — two cells differing only in a float that formats identically must still get different ids.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_sweep_spec.py`:

```python
import sys
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import sweep_spec


BASE = {"prompt": "goa", "duration": 20.0, "steps": 24, "cfg_scale": 7.0,
        "dora": {"name": "hof", "strength": 1.0},
        "latch": [{"head": "rms_energy_bass", "value": -20.0, "gain": 512.0}]}


def test_one_axis_expands_to_one_cell_per_value():
    cells = sweep_spec.expand(BASE, {"strength": [0.5, 1.0, 1.5]})
    assert len(cells) == 3
    assert [c["payload"]["dora"]["strength"] for c in cells] == [0.5, 1.0, 1.5]


def test_two_axes_expand_to_the_cross_product():
    cells = sweep_spec.expand(BASE, {"strength": [0.5, 1.0], "cfg": [7, 16]})
    assert len(cells) == 4
    assert {(c["coords"]["strength"], c["coords"]["cfg"]) for c in cells} == \
        {(0.5, 7), (0.5, 16), (1.0, 7), (1.0, 16)}


def test_seeds_multiply_every_combination_and_land_in_the_payload():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[11, 22, 33])
    assert len(cells) == 6
    assert sorted({c["payload"]["seed"] for c in cells}) == [11, 22, 33]


def test_no_seeds_means_one_cell_per_combination_with_server_resolved_seed():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16]})
    assert len(cells) == 2 and all(c["payload"]["seed"] == -1 for c in cells)


def test_expansion_never_mutates_the_base_payload():
    before = sweep_spec._canon(BASE)
    sweep_spec.expand(BASE, {"strength": [9.0]})
    assert sweep_spec._canon(BASE) == before


def test_a_list_indexed_axis_reaches_into_a_latch_slot():
    cells = sweep_spec.expand(BASE, {"latch1_value": [-30.0, -10.0]})
    assert [c["payload"]["latch"][0]["value"] for c in cells] == [-30.0, -10.0]
    assert cells[0]["payload"]["latch"][0]["gain"] == 512.0     # siblings untouched


def test_a_raw_dotted_path_is_accepted_verbatim():
    cells = sweep_spec.expand(BASE, {"mutate.amount": [0.1, 0.4]})
    assert [c["payload"]["mutate"]["amount"] for c in cells] == [0.1, 0.4]


def test_cell_ids_are_deterministic_across_calls():
    a = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[1])
    b = sweep_spec.expand(BASE, {"cfg": [7, 16]}, seeds=[1])
    assert [c["cell_id"] for c in a] == [c["cell_id"] for c in b]


def test_cell_ids_are_unique_within_a_sweep():
    cells = sweep_spec.expand(BASE, {"cfg": [7, 16], "strength": [0.5, 1.0]}, seeds=[1, 2])
    assert len({c["cell_id"] for c in cells}) == len(cells) == 8


def test_cell_ids_distinguish_values_that_format_identically():
    a = sweep_spec.expand(BASE, {"cfg": [7.0]})[0]["cell_id"]
    b = sweep_spec.expand(BASE, {"cfg": [7.0000001]})[0]["cell_id"]
    assert a != b


def test_cell_ids_survive_reordering_the_axis_dict():
    a = sweep_spec.expand(BASE, {"cfg": [7], "strength": [1.0]})[0]["cell_id"]
    b = sweep_spec.expand(BASE, {"strength": [1.0], "cfg": [7]})[0]["cell_id"]
    assert a == b, "resume must not break because the axes were typed in another order"


def test_validate_rejects_an_empty_axis():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": []}})


def test_validate_rejects_a_nonlist_axis():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": 7}})


def test_validate_accepts_a_minimal_spec():
    assert sweep_spec.validate_spec({"preset": "x", "axes": {"cfg": [7, 16]}}) == []
```

- [ ] **Step 2: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_sweep_spec.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Key detail — `_canon` must be used for BOTH the mutation guard and the id, and `set_path` must deep-copy:

```python
from __future__ import annotations
import copy, hashlib, itertools, json, re
from pathlib import Path

SCHEMA_VERSION = 1
AXIS_KINDS = { ... }        # exactly the table above


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=repr)


def set_path(payload, dotted, value):
    out = copy.deepcopy(payload)
    node = out
    parts = dotted.split(".")
    for i, key in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if key.isdigit():
            node = node[int(key)]
            continue
        if key not in node or not isinstance(node[key], (dict, list)):
            node[key] = [] if nxt.isdigit() else {}
        node = node[key]
    last = parts[-1]
    if last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value
    return out


def _stem(coords):
    bits = []
    for k in sorted(coords):
        v = coords[k]
        s = re.sub(r"[^A-Za-z0-9.+-]+", "", str(v))[:16]
        bits.append(f"{k}{s}" if k != "seed" else f"s{s}")
    return "__".join(bits)[:80] or "cell"


def cell_id(coords):
    h = hashlib.sha1(_canon(coords).encode()).hexdigest()[:12]
    return f"{_stem(coords)}__{h}"


def expand(payload, axes, *, seeds=None):
    names = sorted(axes)                       # sorted => order-independent ids
    for n in names:
        if not isinstance(axes[n], list) or not axes[n]:
            raise ValueError(f"axis {n!r} must be a non-empty list")
    combos = list(itertools.product(*(axes[n] for n in names))) or [()]
    seed_list = list(seeds) if seeds else [-1]
    cells = []
    for combo in combos:
        for sd in seed_list:
            coords = dict(zip(names, combo))
            coords["seed"] = sd
            p = copy.deepcopy(payload)
            for n, v in zip(names, combo):
                p = set_path(p, AXIS_KINDS.get(n, n), v)
            p["seed"] = sd
            cells.append({"cell_id": cell_id(coords), "coords": coords, "payload": p})
    return cells


def validate_spec(spec):
    problems = []
    if not spec.get("preset") and not spec.get("payload"):
        problems.append("spec needs either 'preset' (a name) or an inline 'payload'")
    axes = spec.get("axes") or {}
    if not isinstance(axes, dict):
        problems.append("'axes' must be an object")
        return problems
    for n, v in axes.items():
        if not isinstance(v, list):
            problems.append(f"axis {n!r} must be a list, got {type(v).__name__}")
        elif not v:
            problems.append(f"axis {n!r} is empty")
    if spec.get("seeds") is not None and not isinstance(spec["seeds"], list):
        problems.append("'seeds' must be a list of integers")
    return problems


def load_spec(path):
    return json.loads(Path(path).read_text())
```

- [ ] **Step 4: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_sweep_spec.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/sweep_spec.py eval/tests/test_sweep_spec.py
git commit -m "feat(sweep): axis grammar, cross-product expansion, deterministic cell ids"
```

---

## Task 7: `sweep_run.py` — the resumable CLI, a thin client of :8056

**Files:**
- Create: `/home/kim/Projects/SAO/eval/sweep_run.py`
- Test: `/home/kim/Projects/SAO/eval/tests/test_sweep_run.py`

**Interfaces:**
- Consumes: `presets.load`, `sweep_spec.expand`, `sweep_spec.validate_spec`.
- Produces:
  - `run(spec: dict, out_dir: Path, *, base_url: str = "http://localhost:8056", post=None, dry_run: bool = False, limit: int | None = None) -> dict`
  - `done_ids(manifest_path: Path) -> set[str]`
  - `append_line(manifest_path: Path, record: dict) -> None`
  - `manifest_path_for(out_dir: Path) -> Path` (= `out_dir / "manifest.jsonl"`)
  - CLI: `python eval/sweep_run.py --spec S.json --out DIR [--dry-run] [--limit N] [--base-url U] [--force]`

**The manifest record** — one JSON object per line, append-only, the thing the page builder and the resume logic both read:

```python
{"schema": 1, "cell_id": "...", "coords": {...}, "status": "ok"|"error",
 "files": ["/abs/out_00.wav"], "latents": ["/abs/out_00.z0.npy"], "z0_missing": false,
 "seed": 12345, "job_id": "gen-...", "elapsed_sec": 41.2,
 "sweep": {"name": "...", "preset": "...", "started": 1724...},
 "payload": {...},            # exactly what was POSTed -- the reproducibility contract
 "server": {"dora_loaded": ..., "film_loaded": ..., "model_rebuilt": ...},
 "error": null, "t": 1724...}
```
`payload` is stored verbatim per cell. It is redundant with `coords` + the preset, and that redundancy is the point: a year from now the preset may have been edited, and the manifest must still say what actually ran (eval-tables spec §12, provenance).

**Resume:** on start, read every line of `manifest.jsonl`, collect `cell_id` where `status == "ok"`, skip those cells. Errors are NOT skipped — a re-run retries them, which is what you want after fixing a bad path. `--force` ignores the manifest entirely.

**Interruption:** flush and `os.fsync` after every line. Catch `KeyboardInterrupt` around the POST loop, print `N done, M remaining — rerun the same command to continue`, and exit 130. A cell killed mid-render leaves no line, so it is simply retried.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_sweep_run.py`. All tests inject a fake `post` — **no test in this file may touch the network or the GPU**:

```python
import json, sys
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import sweep_run


SPEC = {"name": "t", "payload": {"prompt": "goa", "duration": 10.0, "steps": 8,
                                 "cfg_scale": 7.0, "dora": {"name": "hof", "strength": 1.0}},
        "axes": {"strength": [0.5, 1.0]}, "seeds": [7]}


def _ok_post(calls):
    def post(url, payload, timeout=None):
        calls.append(payload)
        n = len(calls)
        return {"status": "ok", "job_id": f"gen-{n}", "seed": payload.get("seed", 1),
                "files": [f"/tmp/j{n}/out_00.wav"], "latents": [f"/tmp/j{n}/out_00.z0.npy"],
                "meta": {"dora_loaded": "hof"}, "timings": {"total_sec": 1.0}}
    return post


def test_a_dry_run_posts_nothing_and_reports_the_cell_count(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), dry_run=True)
    assert r["planned"] == 2 and r["rendered"] == 0 and calls == []


def test_every_cell_is_posted_once_and_written_once(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["rendered"] == 2 and len(calls) == 2
    lines = (tmp_path / "manifest.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2 and all(json.loads(l)["status"] == "ok" for l in lines)


def test_rerunning_skips_everything_already_done(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["skipped"] == 2 and r["rendered"] == 0 and calls == []


def test_force_reruns_everything(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), force=True)
    assert r["rendered"] == 2 and len(calls) == 2


def test_a_failed_cell_is_recorded_as_error_and_retried_next_run(tmp_path):
    def bad(url, payload, timeout=None):
        raise RuntimeError("server said no")
    r = sweep_run.run(SPEC, tmp_path, post=bad)
    assert r["errors"] == 2 and r["rendered"] == 0
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip().split("\n")[0])
    assert rec["status"] == "error" and "server said no" in rec["error"]
    calls = []
    r2 = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert len(calls) == 2, "errors must be retried, not treated as done"


def test_one_bad_cell_does_not_abort_the_rest(tmp_path):
    n = {"i": 0}
    def flaky(url, payload, timeout=None):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("boom")
        return {"status": "ok", "job_id": "g", "seed": 7, "files": ["/tmp/a.wav"],
                "latents": ["/tmp/a.z0.npy"], "meta": {}, "timings": {}}
    r = sweep_run.run(SPEC, tmp_path, post=flaky)
    assert r["rendered"] == 1 and r["errors"] == 1


def test_a_response_without_latents_is_flagged_not_dropped(tmp_path):
    def no_z0(url, payload, timeout=None):
        return {"status": "ok", "job_id": "g", "seed": 7, "files": ["/tmp/a.wav"],
                "meta": {}, "timings": {}}
    r = sweep_run.run(SPEC, tmp_path, post=no_z0)
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip().split("\n")[0])
    assert rec["status"] == "ok" and rec["z0_missing"] is True
    assert r["z0_missing"] == 2


def test_the_manifest_stores_the_exact_payload_that_was_posted(tmp_path):
    calls = []
    sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    recs = [json.loads(l) for l in (tmp_path / "manifest.jsonl").read_text().strip().split("\n")]
    assert [r["payload"]["dora"]["strength"] for r in recs] == \
           [c["dora"]["strength"] for c in calls]


def test_limit_caps_the_number_of_renders(tmp_path):
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls), limit=1)
    assert r["rendered"] == 1 and len(calls) == 1


def test_an_invalid_spec_raises_before_any_render(tmp_path):
    import pytest
    calls = []
    with pytest.raises(ValueError):
        sweep_run.run({"payload": {"prompt": "x"}, "axes": {"cfg": []}}, tmp_path,
                      post=_ok_post(calls))
    assert calls == []


def test_a_corrupt_manifest_line_does_not_break_resume(tmp_path):
    sweep_run.run(SPEC, tmp_path, post=_ok_post([]))
    with open(tmp_path / "manifest.jsonl", "a") as f:
        f.write("{ not json\n")
    calls = []
    r = sweep_run.run(SPEC, tmp_path, post=_ok_post(calls))
    assert r["skipped"] == 2 and calls == []
```

- [ ] **Step 2: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_sweep_run.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Batch/sweep CLI. A THIN CLIENT of the render server at :8056 -- it POSTs the
same payload the GUI posts and stores what came back. It does NOT import the
model, build a guidance config, or compute a weight. That is deliberate:
resolve_latch() (explorer_render_server.py:463-518) normalises gains
(rho = mu = slot-1 gain, per-slot weight = slot_gain / g0), so any second
implementation would silently be on a different scale. eval/head_lab.py was
deleted for exactly that mistake.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import presets, sweep_spec

SCHEMA_VERSION = 1
DEFAULT_BASE = "http://localhost:8056"
RENDER_TIMEOUT = 3600.0


def manifest_path_for(out_dir):
    return Path(out_dir) / "manifest.jsonl"


def done_ids(manifest_path):
    out = set()
    p = Path(manifest_path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue                      # a torn last line from a kill -- ignore
        if rec.get("status") == "ok" and rec.get("cell_id"):
            out.add(rec["cell_id"])
    return out


def append_line(manifest_path, record):
    with open(manifest_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())              # survive a kill mid-sweep


def _http_post(url, payload, timeout=RENDER_TIMEOUT):
    import requests
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _payload_for(spec):
    if spec.get("payload"):
        return dict(spec["payload"])
    return dict(presets.load(spec["preset"])["payload"])


def run(spec, out_dir, *, base_url=DEFAULT_BASE, post=None, dry_run=False,
        limit=None, force=False):
    problems = sweep_spec.validate_spec(spec)
    if problems:
        raise ValueError("bad sweep spec: " + "; ".join(problems))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mpath = manifest_path_for(out_dir)
    post = post or _http_post
    url = f"{base_url.rstrip('/')}/generate"

    payload = _payload_for(spec)
    cells = sweep_spec.expand(payload, spec.get("axes") or {}, seeds=spec.get("seeds"))
    already = set() if force else done_ids(mpath)
    todo = [c for c in cells if c["cell_id"] not in already]
    if limit is not None:
        todo = todo[:limit]

    stats = {"planned": len(cells), "skipped": len(cells) - len(todo),
             "rendered": 0, "errors": 0, "z0_missing": 0,
             "manifest": str(mpath), "out_dir": str(out_dir)}
    if dry_run:
        for c in todo:
            print(f"  {c['cell_id']}  {c['coords']}")
        return stats

    started = time.time()
    sweep_meta = {"name": spec.get("name", out_dir.name),
                  "preset": spec.get("preset"), "started": started}
    try:
        for i, c in enumerate(todo, 1):
            t0 = time.time()
            print(f"[{i}/{len(todo)}] {c['cell_id']}  {c['coords']}", flush=True)
            rec = {"schema": SCHEMA_VERSION, "cell_id": c["cell_id"],
                   "coords": c["coords"], "payload": c["payload"],
                   "sweep": sweep_meta, "t": time.time()}
            try:
                resp = post(url, c["payload"], timeout=RENDER_TIMEOUT)
                lat = resp.get("latents") or []
                rec.update(status="ok", files=resp.get("files", []), latents=lat,
                           z0_missing=not lat, seed=resp.get("seed"),
                           job_id=resp.get("job_id"),
                           server={k: resp.get("meta", {}).get(k) for k in
                                   ("dora_loaded", "film_loaded", "model_rebuilt")},
                           elapsed_sec=round(time.time() - t0, 1), error=None)
                stats["rendered"] += 1
                if not lat:
                    stats["z0_missing"] += 1
                    print("  WARNING: response carried no z0 latent "
                          "(standing directive: save z0 next to every render)")
            except Exception as e:
                rec.update(status="error", files=[], latents=[], z0_missing=True,
                           seed=None, job_id=None, server={},
                           elapsed_sec=round(time.time() - t0, 1), error=repr(e))
                stats["errors"] += 1
                print(f"  ERROR {e!r}")
            append_line(mpath, rec)
    except KeyboardInterrupt:
        left = len(todo) - stats["rendered"] - stats["errors"]
        print(f"\ninterrupted: {stats['rendered']} done, {left} remaining — "
              f"rerun the same command to continue")
        stats["interrupted"] = True
        return stats
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sweep one or more axes over a saved preset, via the render "
                    "server at :8056. Resumable: rerun to continue.")
    ap.add_argument("--spec", required=True, help="sweep spec JSON")
    ap.add_argument("--out", required=True, help="output dir (holds manifest.jsonl)")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--dry-run", action="store_true", help="list cells, render nothing")
    ap.add_argument("--limit", type=int, default=None, help="render at most N cells")
    ap.add_argument("--force", action="store_true", help="ignore the manifest, redo all")
    a = ap.parse_args(argv)
    stats = run(sweep_spec.load_spec(a.spec), a.out, base_url=a.base_url,
                dry_run=a.dry_run, limit=a.limit, force=a.force)
    print(json.dumps(stats, indent=2))
    return 1 if stats.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note `run()` accepts `force` — add it to the test-facing signature exactly as written; the test `test_force_reruns_everything` depends on it.

- [ ] **Step 4: Run the tests**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_sweep_run.py -v`
Expected: 11 passed.

- [ ] **Step 5: Write an example spec and dry-run it**

Create `/home/kim/Projects/SAO/eval/sweeps/example-strength-ladder.json`:

```json
{
  "name": "strength-ladder",
  "preset": "smoke",
  "axes": {"strength": [0.5, 1.0, 1.5, 2.0], "cfg": [7, 16]},
  "seeds": [11, 22],
  "notes": "Adapter strength x cfg, two seeds. cfg 16 / strength 2 are DIAGNOSTIC cells (INFERENCE-SURFACE trap 6): the discriminator between checkpoints is which stay musical when guidance is pushed."
}
```

Run: `cd /home/kim/Projects/SAO && .venv/bin/python eval/sweep_run.py --spec eval/sweeps/example-strength-ladder.json --out /tmp/sweep-dry --dry-run`
Expected: 16 cells listed, `"rendered": 0`.

- [ ] **Step 6: Smoke it against the live server, then kill it and prove resume**

With the render server up:

```bash
cd /home/kim/Projects/SAO
.venv/bin/python eval/sweep_run.py --spec eval/sweeps/example-strength-ladder.json \
    --out /run/media/kim/Mantu/sa3_lora_runs/sweeps/smoke --limit 3
# Ctrl-C during cell 2 or 3, then:
.venv/bin/python eval/sweep_run.py --spec eval/sweeps/example-strength-ladder.json \
    --out /run/media/kim/Mantu/sa3_lora_runs/sweeps/smoke --limit 3
```
Expected: the second run reports `skipped` equal to the number of completed cells and re-renders only what was missing. Use a short `duration` in the `smoke` preset (10 s) so this costs minutes, not hours. Resolve the output root through `_mantu_root()` semantics — if the drive is mounted as `Mantu1`, use that; do not hardcode.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/sweep_run.py eval/tests/test_sweep_run.py eval/sweeps/
git commit -m "feat(sweep): resumable batch CLI over POST /generate, JSONL manifest"
```

---

## Task 8: Preset × models — the matrix Kim asked for

**Files:**
- Modify: `/home/kim/Projects/SAO/eval/sweep_run.py` (model resolution + a `--models` CLI path)
- Test: `/home/kim/Projects/SAO/eval/tests/test_sweep_run.py` (append)

**Interfaces:**
- Consumes: `model_db.load_or_build()` and `GET /models` from the model-DB plan; `sweep_spec.expand`.
- Produces:
  - `resolve_models(spec: dict, *, fetch=None) -> list[dict]` → `[{"id","label","path","family"}]`
  - `models_axis(models: list[dict]) -> tuple[str, list]` → `("ckpt_path", [paths])` plus a `coords` label map
  - CLI: `--models id1,id2,...` and spec key `"models": ["<model-db id or path>", ...]`

**Design.** A `models` list in the spec is expanded as an ordinary axis on `ckpt_path`, so nothing in Task 7 changes structurally. Two additions:

1. **Resolution.** A model entry may be a model-db `id`, a `label`, or an absolute path. `resolve_models` asks `GET /models` (falling back to `model_db.load_or_build()` if the endpoint is absent), matches on `id` then `label` then `path`, and **fails loudly on an unresolved entry before any render** — a typo that silently renders 40 cells on the base model is exactly the failure this feature exists to prevent.
2. **Labelling.** `coords["model"]` stores the model's **label**, not its path, because the label is what the results table shows and what a human recognises. The path lives in `payload["ckpt_path"]`, which the manifest also stores.

**Non-loadable models are refused up front.** The model-db record carries `loadable: bool` (`family in {adapter, fullft}`); control-adapter and latch families cannot be loaded through `/generate` today. Refuse them at resolution with a message naming the family and the sibling plan that will add them, rather than letting the server 500 forty times.

**Interaction with `POST /ab` and resident slots** (model-DB plan Tasks 5–7): `/ab` is the *interactive* answer — two or three models held resident, one payload, instant comparison, bounded by VRAM. The sweep is the *batch* answer — arbitrarily many models, one at a time, resumable, minutes to hours. They are complementary and share the model DB. **Do not route the sweep through `/ab`**: `/ab` requires every arm resident simultaneously, which is precisely the constraint a batch sweep exists to escape. If `/ab` exists when this task runs, add `--via-ab` as an *optimisation* that groups cells whose models are already resident — but only after the plain path passes Step 5.

- [ ] **Step 1: Write the failing tests**

Append to `/home/kim/Projects/SAO/eval/tests/test_sweep_run.py`:

```python
MODELS = [
    {"id": "MDB-aaaa1111", "label": "dorlor_ab_r128", "path": "/m/a.ckpt",
     "family": "adapter", "loadable": True},
    {"id": "MDB-bbbb2222", "label": "fullft_avp_subloss", "path": "/m/b.ckpt",
     "family": "fullft", "loadable": True},
    {"id": "MDB-cccc3333", "label": "morphcond_riffer", "path": "/m/c.pt",
     "family": "control", "loadable": False},
]


def _fetch(_url=None):
    return {"models": MODELS}


def test_models_resolve_by_id_label_or_path():
    got = sweep_run.resolve_models(
        {"models": ["MDB-aaaa1111", "fullft_avp_subloss", "/m/a.ckpt"]}, fetch=_fetch)
    assert [m["label"] for m in got] == ["dorlor_ab_r128", "fullft_avp_subloss",
                                         "dorlor_ab_r128"]


def test_an_unknown_model_fails_before_any_render():
    import pytest
    with pytest.raises(ValueError) as e:
        sweep_run.resolve_models({"models": ["MDB-aaaa1111", "typo"]}, fetch=_fetch)
    assert "typo" in str(e.value)


def test_a_non_loadable_family_is_refused_with_its_family_named():
    import pytest
    with pytest.raises(ValueError) as e:
        sweep_run.resolve_models({"models": ["morphcond_riffer"]}, fetch=_fetch)
    assert "control" in str(e.value)


def test_a_preset_across_two_models_yields_one_cell_per_model(tmp_path):
    calls = []
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0},
            "models": ["MDB-aaaa1111", "MDB-bbbb2222"], "seeds": [7]}
    r = sweep_run.run(spec, tmp_path, post=_ok_post(calls), fetch=_fetch)
    assert r["rendered"] == 2
    assert sorted(c["ckpt_path"] for c in calls) == ["/m/a.ckpt", "/m/b.ckpt"]


def test_the_model_coordinate_is_the_label_not_the_path(tmp_path):
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0},
            "models": ["MDB-aaaa1111"], "seeds": [7]}
    sweep_run.run(spec, tmp_path, post=_ok_post([]), fetch=_fetch)
    rec = json.loads((tmp_path / "manifest.jsonl").read_text().strip())
    assert rec["coords"]["model"] == "dorlor_ab_r128"
    assert rec["payload"]["ckpt_path"] == "/m/a.ckpt"


def test_models_cross_with_other_axes(tmp_path):
    calls = []
    spec = {"name": "x", "payload": {"prompt": "goa", "duration": 10.0,
                                     "dora": {"name": "none", "strength": 1.0}},
            "models": ["MDB-aaaa1111", "MDB-bbbb2222"],
            "axes": {"strength": [1.0, 1.5]}, "seeds": [7]}
    r = sweep_run.run(spec, tmp_path, post=_ok_post(calls), fetch=_fetch)
    assert r["rendered"] == 4
```

- [ ] **Step 2: Run them**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_sweep_run.py -v`
Expected: the six new tests FAIL (`resolve_models` missing, `run()` has no `fetch`).

- [ ] **Step 3: Implement**

Add to `sweep_run.py`:

```python
MODELS_TIMEOUT = 30.0


def _fetch_models(base_url=DEFAULT_BASE):
    """GET /models (model-DB plan Task 4). Falls back to the local DB so the
    sweep works with the server down for planning."""
    try:
        import requests
        r = requests.get(f"{base_url.rstrip('/')}/models", timeout=MODELS_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        import model_db
        return model_db.load_or_build()


def resolve_models(spec, *, fetch=None, base_url=DEFAULT_BASE):
    want = spec.get("models") or []
    if not want:
        return []
    db = (fetch or (lambda: _fetch_models(base_url)))()
    recs = db.get("models", db if isinstance(db, list) else [])
    by = {}
    for m in recs:
        for k in ("id", "label", "path"):
            if m.get(k):
                by.setdefault(str(m[k]), m)
    out = []
    for w in want:
        m = by.get(str(w))
        if m is None:
            raise ValueError(
                f"unknown model {w!r} — not an id, label or path in the model DB. "
                f"List them with: curl -s {base_url}/models | head")
        if not m.get("loadable", True):
            raise ValueError(
                f"model {w!r} has family {m.get('family')!r}, which cannot be loaded "
                f"through /generate today. Control/contour families are the subject of "
                f"docs/superpowers/plans/2026-08-23-inference-ui-global-conditioner-inpaint.md")
        out.append({"id": m.get("id"), "label": m.get("label") or Path(m["path"]).stem,
                    "path": m["path"], "family": m.get("family")})
    return out
```

In `run()`, after `payload = _payload_for(spec)` and before `expand`:

```python
    models = resolve_models(spec, fetch=fetch, base_url=base_url)
    axes = dict(spec.get("axes") or {})
    label_by_path = {}
    if models:
        axes["model"] = [m["path"] for m in models]
        label_by_path = {m["path"]: m["label"] for m in models}
    cells = sweep_spec.expand(payload, axes, seeds=spec.get("seeds"))
    for c in cells:
        if "model" in c["coords"]:
            c["coords"]["model"] = label_by_path[c["coords"]["model"]]
```

`AXIS_KINDS["model"] = "ckpt_path"` already maps the path into the payload (Task 6). **The coords rewrite must happen AFTER `expand`** so `cell_id` is computed from the label — stable even if the drive remounts under a different name and the path string changes. Add `fetch=None` to `run()`'s signature and thread it through. Add the `--models` CLI flag: `ap.add_argument("--models", default=None, help="comma-separated model ids/labels/paths; overrides the spec's models list")`, folded into the spec dict before `run()`.

- [ ] **Step 4: Run all the tests**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Live check — one preset across two real models**

```bash
cd /home/kim/Projects/SAO
curl -s localhost:8056/models | .venv/bin/python -c "
import json,sys
for m in json.load(sys.stdin)['models'][:20]:
    print(m['id'], m['family'], m['loadable'], m['label'])"
# pick two loadable ids, then:
.venv/bin/python eval/sweep_run.py --spec eval/sweeps/example-strength-ladder.json \
  --models <ID1>,<ID2> --out /run/media/kim/Mantu/sa3_lora_runs/sweeps/two-models --limit 4
```
Expected: four wavs, four manifest lines, `coords.model` showing two distinct labels, and the server's `meta.model_rebuilt` flipping true when the checkpoint changes.

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/sweep_run.py eval/tests/test_sweep_run.py
git commit -m "feat(sweep): render a saved preset across a selection of models from the model DB"
```

---

## Task 9: `build_sweep_page.py` — the results surface, per the eval-tables spec

**Files:**
- Create: `/home/kim/Projects/SAO/eval/build_sweep_page.py`
- Test: `/home/kim/Projects/SAO/eval/tests/test_build_sweep_page.py`

**Interfaces:**
- Consumes: a `manifest.jsonl` from Task 7/8.
- Produces: `build(manifest_path, out_html, *, title=None, public=False) -> Path`; helpers `read_manifest(path) -> list[dict]`, `pivot(records) -> dict` (`{"rows","cols","cells","axes"}`), `explainer_html(spec_meta) -> str`.
- CLI: `python eval/build_sweep_page.py --manifest M.jsonl [--out P.html] [--public]`

**Spec conformance — this is not a new viewer.** Implement `/home/kim/Projects/SAO/docs/superpowers/specs/2026-07-06-eval-tables-human-first.md`:
- **§14 THREE AUDIENCES.** The page carries, above the table: (1) the TOOL — a same-playhead player; (2) the RESOURCE — the full preset payload rendered as a `<pre>`, the axis definitions, the model labels + paths, and a `file://` link to the exact `sweep_run.py` command that produced it; (3) the LEARNING block — plain-language "what this sweep tests / why / how to read it", auto-composed from the axis names with a per-axis sentence (e.g. `strength`: *"Adapter strength. w1.0 is as trained. Above ~1.5 models start to break — which is the point: the useful discriminator is which checkpoints stay musical when pushed."*).
- **§12 layout + provenance.** Full viewport width; every cell shows its seed and its `cell_id`; the header shows manifest path, render dates, and counts of ok/error/`z0_missing`.
- **§13 waveform popup player** and the same-playhead behaviour: lift the player from `/home/kim/Projects/SAO/eval/build_clarity_audit_page.py:60` (the "same-playhead players" block) rather than writing a third one. Read that block first; if it is entangled with that page's data model, extract it into `eval/audition_player.py` as part of this task and have `build_clarity_audit_page.py` import it — that is a strict improvement and the spec's whole point.
- **§16 unaudited marker.** Cells not yet listened to get the red exclamation; the marker's state lives in the page's own `localStorage`, matching the existing pages.
- **Redaction.** `--public` applies the same redaction as `build_dora_table_page.py:50` (`redact_public`) — import it, do not re-derive the rules.

**Table shape.** With one axis: a single row of cells. With two: rows = axis A, columns = axis B. With three or more: rows = the cross-product of all but the last axis (labelled `a=…, b=…`), columns = the last. `model`, when present, is always a column axis — comparing models side by side is the point of Task 8.

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_build_sweep_page.py`:

```python
import json, sys
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import build_sweep_page as B


def _manifest(tmp_path, recs):
    p = tmp_path / "manifest.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return p


def _rec(**kw):
    base = {"schema": 1, "cell_id": "c1", "coords": {"strength": 1.0, "seed": 7},
            "status": "ok", "files": ["/tmp/a.wav"], "latents": ["/tmp/a.z0.npy"],
            "z0_missing": False, "seed": 7, "payload": {"prompt": "goa"},
            "sweep": {"name": "s", "preset": "p"}}
    base.update(kw)
    return base


def test_reading_skips_corrupt_lines(tmp_path):
    p = _manifest(tmp_path, [_rec()])
    with open(p, "a") as f:
        f.write("{ nope\n")
    assert len(B.read_manifest(p)) == 1


def test_two_axes_pivot_to_rows_and_columns(tmp_path):
    recs = [_rec(cell_id=f"c{i}", coords={"strength": s, "cfg": c, "seed": 7})
            for i, (s, c) in enumerate([(0.5, 7), (0.5, 16), (1.0, 7), (1.0, 16)])]
    piv = B.pivot(recs)
    assert piv["rows"] == [0.5, 1.0] and piv["cols"] == [7, 16]


def test_the_model_axis_is_always_the_column_axis(tmp_path):
    recs = [_rec(cell_id=f"c{i}", coords={"model": m, "strength": s, "seed": 7})
            for i, (m, s) in enumerate([("A", 0.5), ("B", 0.5), ("A", 1.0), ("B", 1.0)])]
    piv = B.pivot(recs)
    assert piv["cols"] == ["A", "B"]


def test_the_page_carries_all_three_audience_blocks(tmp_path):
    p = _manifest(tmp_path, [_rec()])
    out = tmp_path / "page.html"
    B.build(p, out)
    html = out.read_text()
    assert "what this sweep tests" in html.lower()          # audience 3: learning
    assert "goa" in html                                     # audience 2: the payload
    assert "playhead" in html.lower()                        # audience 1: the tool
    assert "sweep_run.py" in html                            # reproduction command


def test_errors_and_missing_z0_are_visible_not_hidden(tmp_path):
    p = _manifest(tmp_path, [_rec(status="error", error="boom", files=[]),
                             _rec(cell_id="c2", z0_missing=True)])
    out = tmp_path / "page.html"
    B.build(p, out)
    html = out.read_text()
    assert "boom" in html and "z0" in html.lower()


def test_a_strength_axis_gets_its_plain_language_sentence(tmp_path):
    assert "as trained" in B.explainer_html({"axes": ["strength"]}).lower()


def test_an_empty_manifest_produces_a_page_that_says_so_rather_than_crashing(tmp_path):
    p = tmp_path / "manifest.jsonl"
    p.write_text("")
    out = tmp_path / "page.html"
    B.build(p, out)
    assert "no cells" in out.read_text().lower()
```

- [ ] **Step 2: Run it**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_build_sweep_page.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Read the player you are reusing**

Run: `sed -n '40,120p' /home/kim/Projects/SAO/eval/build_clarity_audit_page.py`
Decide, and record the decision in the module docstring: import it, or extract to `eval/audition_player.py` and have both pages import that. Do not copy-paste a third copy.

- [ ] **Step 4: Implement**

Structure: `read_manifest` → `pivot` → `explainer_html` → `build`. `PER_AXIS_HELP` is a literal dict of plain-language sentences keyed by axis name, covering at minimum `strength, cfg, steps, seed, model, prompt, gamma, n_iter, rho, mu, latch1_value, latch1_gain, film_value`. Each sentence says what the axis is, what the neutral value is, and what a reader should listen for. The `strength` and `cfg` entries must carry `docs/INFERENCE-SURFACE.md` trap 6 (cfg 16 / w 2 are diagnostic cells, not mistakes). Any axis without an entry gets `"(no explainer written for this axis yet — add one to PER_AXIS_HELP in eval/build_sweep_page.py)"`, which is honest and self-correcting.

The reproduction line is built from `sweep["name"]` and the manifest path:
`.venv/bin/python eval/sweep_run.py --spec <spec> --out <dir>` — and rendered as both text and a `file://` link to the spec, per §14's reproducibility requirement.

- [ ] **Step 5: Run the tests**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_build_sweep_page.py -v`
Expected: 7 passed.

- [ ] **Step 6: Build a page from the real smoke sweep and look at it**

```bash
cd /home/kim/Projects/SAO
.venv/bin/python eval/build_sweep_page.py \
  --manifest /run/media/kim/Mantu/sa3_lora_runs/sweeps/two-models/manifest.jsonl \
  --out /run/media/kim/Mantu/sa3_lora_runs/sweeps/two-models/index.html
xdg-open /run/media/kim/Mantu/sa3_lora_runs/sweeps/two-models/index.html
```
Check by eye against the spec: full width, every cell playable, same playhead across a row, seeds visible, the explainer above the table, the payload below it.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/build_sweep_page.py eval/tests/test_build_sweep_page.py eval/audition_player.py
git commit -m "feat(eval): sweep results page -- three-audience, same-playhead, per eval-tables spec"
```

---

## Task 10: Documentation and index registration

**Files:**
- Modify: `/home/kim/Projects/SAO/docs/INFERENCE-SURFACE.md`
- Modify: `/home/kim/Projects/SAO/ARCHITECTURE.md` (reuse index + Doc map)
- Modify: `/home/kim/Projects/SAO/WORKLOG.md`
- Modify: `/home/kim/Projects/SAO/EXPERIMENTS.md` (only if a sweep run here answers a registered experiment)
- Modify: `/home/kim/Projects/SAO/KIM-TASKLIST.md` (the open questions below)

Nothing in this plan is DONE until this task is (CLAUDE.md §5 + the DISCOVERABILITY RULE: *if you'd have to grep to find it next month, it isn't registered*).

- [ ] **Step 1: Update `docs/INFERENCE-SURFACE.md`**

- §9 NEEDS BUILDING item **4** → move to a new "HAS" line naming `eval/sweep_run.py`, `eval/sweep_spec.py`, `eval/presets.py`, `eval/build_sweep_page.py`, with the one-command usage.
- §9 item **7** → rewrite: head metadata IS surfaced, and now correctly (Tasks 1–3). Replace the "slider is one-size-fits-all" paragraph with the real cause: `train_latch.py:467-490` never wrote `slider_min` / `feature_stats`, which `_head_entry` was reading.
- The **KNOWN BUG** block → record the Task 3 Step 7 result for the empty pickers: fixed by the poller, or not fixed and therefore not load-order.
- Add a short **"The 17th head"** paragraph: `chroma_other`, family `chroma`, gain 2048 not 512, sourced from `chroma_morph_transitions.py:46`, re-rooted off the dead `Mantu1` literal by `_chroma_head_path()`.
- Add the **chroma-readout verdict** from Task 1 Step 6, verbatim about what is and is not recoverable, and note that `train_latch.py` now records `target_source` / `chroma_dir` / `chroma_key` going forward.
- Paste Section 0 of this plan ("What a sweep surface is") in as the sweep's own explainer — Kim asked what item 4 was, and the answer should live in the doc, not only in the plan.

- [ ] **Step 2: Register in `ARCHITECTURE.md`**

Add to the reuse index (§A–F, in the eval tooling section), one line each:

```
- eval/head_meta.py — one honest description of a LatCH head from its checkpoint
  (real slider bounds = std_mean±2σ, capability + health flags, readout provenance).
  Consumed by explorer_render_server._head_entry -> /info -> the viewer's LatCH panel.
- eval/presets.py — named /generate payloads (seed stripped). GET/POST /presets on :8056.
- eval/sweep_spec.py — sweep axis grammar, cross-product expansion, deterministic cell ids.
- eval/sweep_run.py — RESUMABLE batch/sweep CLI. A thin HTTP client of :8056 /generate;
  renders a preset across axes AND across a selection of models from the model DB.
  NEVER a second guidance implementation (resolve_latch normalises gains).
- eval/build_sweep_page.py — sweep manifest -> three-audience eval page (eval-tables spec).
- Misc/latch_head_overrides.json — human-supplied head facts checkpoints don't carry.
```
Add this plan to the **Doc map**.

- [ ] **Step 3: WORKLOG line**

Append one dated line: what landed, the two headline fixes (per-head bounds were dead code, not a UI oversight; the chroma head pointed at a nonexistent mount), and the one-liner for running a sweep.

- [ ] **Step 4: Add the open questions to `KIM-TASKLIST.md`**

Filelock first. Add the four items from "Open questions" below.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add docs/INFERENCE-SURFACE.md ARCHITECTURE.md WORKLOG.md KIM-TASKLIST.md
git commit -m "docs: register the sweep surface + head metadata work; correct INFERENCE-SURFACE items 4 and 7"
```

---

## Open questions for Kim (put these in KIM-TASKLIST.md, do not guess)

1. **Where do sweep outputs live?** The plan writes to `<Mantu>/sa3_lora_runs/sweeps/<name>/`, resolved through the live mount. Confirm, or name a different root (the UUID drive has more room).
2. **σ multiplier for the slider bounds.** `k = 2.0` covers ~95% of the training distribution. Kim may want `k = 3` so the diagnostic out-of-distribution cells stay reachable with the slider rather than by typing. One-line change (`head_meta.describe(..., sigma_k=)`).
3. **The 12-d chroma readouts.** If Task 1 Step 6's probe finds nothing, only Kim knows which of the older 12-d heads used which readout. Filling `Misc/latch_head_overrides.json` needs him — or the answer is permanently "unknown", which the UI will then display honestly.
4. **Sweep × A/B slots.** `POST /ab` (sibling plan) compares resident models instantly; the sweep compares arbitrarily many, slowly. This plan keeps them separate and does NOT route the sweep through `/ab`. Confirm that split before anyone builds `--via-ab`.
5. **Should presets be committed?** `eval/presets/` is currently untracked. A preset is a research artifact — recommend committing it (they are small JSON), but that is Kim's call.

---

## Self-review notes

**Spec coverage.** §9 item 4 → Section 0 (the explanation Kim asked for) + Tasks 6, 7, 9. Kim's preset-across-models ask → Tasks 4, 5, 8. §9 item 7 and the LatCH PANEL REQUIREMENTS block → dynamic range meter (Task 1 `std_mean±kσ`, Task 3 `_slot_view`); per-head slider bounds replacing `-80/20/-30` (Task 1 `slider_bounds`, Task 2); hover help for the loss curves + disable for heads that don't use them (Task 3, `supports_loss_select` / `supports_scalar_target`); health flag from `epoch`/`avg_loss` (Task 1 `_health`); suggested values + hover help for `rho/mu/gamma/n_iter` in the normalised scale (Task 3 Step 6); the two-chroma-readouts question (Task 1 Steps 5–6, 9 — answered as *not recorded, here is how we record it now*); the 17th head located and made explicit (Task 2 Step 4). Eval-tables spec §12/§13/§14/§16 → Task 9.

**Dependencies.** Tasks 1→2→3 are a chain. Tasks 4→5 are a chain. Task 6 is independent. Task 7 needs 4 and 6. Task 8 needs 7 plus the model-DB plan's `/models`. Task 9 needs 7. Task 10 is last. Tasks 1–3 and 4–6 can run in parallel with each other.

**Type consistency.** The head dict's key names are fixed in Task 1 and consumed unchanged in Tasks 2 and 3. `cell_id` / `coords` / `payload` are fixed in Task 6 and consumed in 7, 8, 9. `resolve_models` returns `{"id","label","path","family"}` and only `path` and `label` are used downstream.

**Constraint audit.** No second renderer (Task 7 is HTTP-only, stated in its docstring). No second guidance implementation (`rho/mu` help texts are in the normalised scale; the sweep never computes a weight). No hardcoded drive paths (Task 2 Step 4 removes one, Tasks 7–9 resolve output roots through the live mount). z0 honoured (Constraint 5, Task 7's `z0_missing`). Resumable (Task 7 Steps 3, 6). Absolute interpreter paths in every Run line.
