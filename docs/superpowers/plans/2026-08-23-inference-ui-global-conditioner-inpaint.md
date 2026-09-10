# Global Conditioner + Inpaint/Outpaint for the SA3 Inference UI — Implementation Plan

> **STATUS 2026-08-26 (C): Task 1 is SATISFIED, but by a different mechanism than it specifies —
> read this before implementing it.** Its goal ("the server's own renders can be continued;
> `resp['latents']` exists; the save-z0-next-to-every-render directive is met") is delivered and
> verified. Its *design* is not, deliberately:
> - The plan wanted `generate_with_latents()` + `render_io.normalize_and_truncate()` — i.e. call
>   `return_latents=True` and re-do the peak-normalise, truncation and decode inside the server.
>   That is a SECOND implementation of a decode that already exists in two forms (the latch-guided
>   branch and `sample_diffusion` decode differently), and the two would agree on day one and drift
>   after. Kim approved the alternative: a **`latents_sink` list** threaded through
>   `model.py:generate()` and `sampling.py:sample_diffusion()`, appended to just before the decode.
>   The audio path is untouched, so there is nothing to drift — proved byte-identical (same sha256)
>   on BOTH branches under a same-seed A/B.
> - Shipped instead of `render_io.py`: `explorer_render_server.save_z0()` (fp16 `(256, T)`, per batch
>   item) and `resp["latents"]` at the top level of every response. `eval/continuation.py` recovers a
>   prefix's ckpt/dora from its sidecar. Verified: a 10 s `/generate` continued through `/longform
>   init_latent_path` returned 24 s with prefix correlation **1.000**.
> - **The a2a paths save no z0 ON PURPOSE** (the plan assumed they would): their output is a
>   crossfade of separately sampled windows, so no single latent produced it. `meta.z0_reason` says
>   so. Anything in Tasks 2–3 that assumes an a2a z0 exists needs rethinking, not patching.
> - Still genuinely open: **Task 2** (named control-adapter slots + batch/CFG alignment) and
>   **Task 3** (one checkpoint loader for control checkpoints). Note Task 2's "slots" are a
>   different thing from the adapter A/B slots shipped 2026-08-26 (`eval/adapter_slots.py`) — those
>   are LoRA/DoRA residency on one base; these are control-adapter branches. Reuse the naming
>   carefully or the two will be confused.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the existing SA3 inference app (Dash viewer :8051 + render server :8056) one declarative
**conditioner** interface that carries every SA3 conditioning inlet — so any control family, including
ones we have not trained yet, reaches t2a, a2a **and** longform through a single code path — plus
first-class **inpaint** and **outpaint** operations built on the already-proven primitives.

**Architecture:** A new library module `control/sa3_control/conditioning.py` defines a
`ConditionerFamily` registry and a `ConditioningBundle` that resolves a list of declarative specs into
exactly three artefacts a sampler can consume: `generate_kwargs` (for `StableAudioModel.generate`), a
`cond_hook` that mutates a `conditioning_tensors` dict (for the low-level `sample_diffusion` paths in
`stable_audio_3/inference/longform.py`), and a `context()` that activates control-adapter tokens. The
render server keeps ownership of all rendering; it gains `/inpaint` and routes its existing FiLM/text
handling through the bundle. The Dash panel is generated from `/info.conditioners`, so a new family
needs **zero UI code**. Nothing is re-implemented: LatCH gain normalisation stays in `resolve_latch`,
inpainting uses `model.generate(inpaint_audio=…)`, long outpaints use `LongFormRenderer` +
`InpaintContinuationGenerator`, crossfades reuse the equal-power join already in `_a2a_track_impl`.

**Tech Stack:** Python 3, PyTorch (ROCm 7.15 / torch 2.14 in `SAO/.venv`), FastAPI + uvicorn (render
server), Dash (viewer, `mir` venv), pytest, numpy, soundfile.

**Spec:** `docs/INFERENCE-SURFACE.md` (§0 the engine already exists; §4 the four control mechanisms;
§8 what is genuinely NOT unified; §9 NEEDS BUILDING items 2, 3, 6b). Companion prior art that this
plan **supersedes and absorbs**: `docs/superpowers/specs/2026-07-22-melody-ux-plan.md` Phase 2
(`resolve_melody` / a `melody` payload block) — never implemented; its open question Q3 ("stacking two
adapter families is untested") is answered by Task 2 here.

---

## Discovery phase — what already exists (read before designing; do not re-derive)

Searched `DISCOVERIES.md`, `EXPERIMENTS.md`, `WORKLOG.md`, `papers/knowledge.md`,
`profiles/*.journal.md`, `ARCHITECTURE.md`, `KIM-TASKLIST.md`, and read the server, the adapters, the
longform primitives, the DiT conditioning path, and the Dash tabs. Findings that constrain the design:

1. **The renderer exists.** `SAO/eval/explorer_render_server.py` :8056 (`SAO/.venv`, `medium-base`
   resident) is THE generation path — `/generate /a2a_track /a2a_mix /longform /decode /bend
   /schedule /ckpts /info /status /audio`. **HARD CONSTRAINT: extend it or write a thin client. Never
   a parallel renderer.** Its `resolve_latch()` NORMALISES gains (`rho = mu = slot-1 gain`, per-slot
   `weight = gain/g0`), so a raw `weight` computed anywhere else is a different scale.
2. **Inpaint machinery exists at two levels.** (a) `StableAudioModel.generate` natively accepts
   `inpaint_audio=(sr, wav)`, `inpaint_mask`, and **list-valued** `inpaint_mask_start_seconds` /
   `inpaint_mask_end_seconds` (multi-region, `model.py:196-233`). Mask polarity, verified:
   **1 = KEEP, 0 = REGENERATE** — the seconds path starts from `torch.ones` and zeroes each
   `[start, end)`. (b) `stable_audio_3/inference/longform.py` has `InpaintContinuationGenerator`,
   `SDEditReanchor`, `CrossfadeStitcher`, `PromptSchedule`, `LongFormRenderer`, `DriftMonitor`.
   *A full night was once lost re-inventing (b). Do not write a third inpainter.*
3. **SA3 inpaint SOFT-conditions the kept region** (WORKLOG: clamp-region mean-abs err ≈0.064) — it is
   not a hard clamp. So a user-facing inpaint MUST offer splicing the original samples back outside the
   edited regions, or every edit silently degrades the whole track. Precedent: the 2026-07-07 "PURE
   chroma transitions" work (originals bit-intact outside the window, only the bridge generated).
4. **The control-context slot is module-global on purpose.** `control/sa3_control/adapters.py:47`
   `_ACTIVE = {"tokens": None, "gain": 1.0}` with an explicit comment: a `ContextVar` is NOT preserved
   into `torch.utils.checkpoint`'s backward recompute, so the adapter branch would be skipped on
   recompute (`CheckpointError`). **Any redesign must stay a plain module global.** Consequence today:
   exactly one control adapter can be active.
5. **The adapter branch is ADDITIVE and per-cross-attn.** `ControlledCrossAttention.forward` does
   `base + gain * adapter(x, base, tokens)`; `install_adapters` wraps all 24 cross-attn modules and is
   idempotent. ⇒ N named branches summing is architecturally natural; the only blocker was the
   single-tensor global. (This answers melody-ux-plan open Q3.)
6. **Three live CFG/batch bugs in the current control path.** The DiT doubles its batch as
   `cat([x, x])` **only** when `cfg_scale != 1.0` AND `cfg_interval[0] <= sigma <= cfg_interval[1]`
   (`models/dit.py:493-497`). But `film_context()` (server `:447-459`) unconditionally builds
   `cat([ctrl, zeros])` at batch 2 and never repeats to `batch_size`. So control tokens have the wrong
   batch when (i) `cfg_scale == 1.0`, (ii) `batch_size > 1`, (iii) a `cfg_interval` is set and sampling
   leaves the interval. Fix belongs in ONE place — the adapter, which is the only code that knows the
   live query batch.
7. **`modular_local_cond` needs no fork change to reach t2a/a2a.**
   `ConditionedDiffusionModelWrapper.get_conditioning_inputs` reads
   `conditioning_tensors[key][0]` for every id in `modular_local_cond_ids` and **skips missing keys**
   (`models/diffusion.py:152-160`); `StableAudioModel.generate` accepts a pre-built
   `conditioning_tensors=` dict (`model.py:268`). ⇒ build the dict, inject `ct["mir_ctrl"] = [tensor]`,
   pass it in. Under CFG the DiT duplicates modular cond to BOTH halves (`dit.py:515-518`) — so this
   inlet is not CFG-scalable; its strength lever is scaling the tensor.
8. **`SDEditReanchor` builds its OWN conditioning dict** (inpaint mask + masked input only,
   `longform.py:316-330`), which is why EXPERIMENTS **D14 dropped its pianoroll arm** — it would have
   run unconditioned while looking like a working arm. EXPERIMENTS calls extending that conditioning
   path *"the single most valuable thing to build"*. Same seam applies to
   `InpaintContinuationGenerator._cond`.
9. **Joint Head-B + DoRA-rows checkpoints have a strict load ORDER** (`melody_pilot_eval.py:137-160`,
   crash reference: LUMI job 20328757): `add_lora(dit)` on the RAW DiT **before** `install_adapters`,
   but `dit.load_state_dict(ck["lora_state"], strict=False)` **after** the wrap (the saved keys carry
   the `cross_attn.base_attention.*` prefix). Three scripts each carry a copy of this; the plan
   factors it into one loader.
10. **`args["melody_vocab"]` is unreliable.** Verified against the real trained arm
    `<UUID>/lumi_runs/runs/headb_melody/riffer_final.pt`: `control_mode="melody_contour"`,
    `args["melody_vocab"] is None`, `dora_rank=128`, and 24 adapter branches. The vocab must be read
    from `state["conditioner.embed.weight"].shape[0]`. (`docs/INFERENCE-SURFACE.md` §5 says to match
    `args["melody_vocab"]` — that is wrong for this checkpoint and is corrected in Task 13.)
11. **The server never writes `.z0.npy`.** Grep-verified: `_generate_impl`, `_longform_impl`,
    `_a2a_*` all save only `.wav`. Yet `/longform init_latent_path` consumes *"a prior render's own
    `.z0.npy`"*, and the standing directive is *save z0 next to every render*. ⇒ the server's own
    output cannot currently be continued, inpainted or outpainted. This is Task 1 and it gates
    Tasks 9–10.
12. **`generate(return_latents=True)` skips decode, peak-normalise and truncation**
    (`model.py:385-405`), and `sample_diffusion` decodes with `pretransform.decode(sampled,
    chunked=chunked_decode)` where the default is `None`. ⇒ byte-parity re-decoding is achievable by
    calling `pre.decode(z, chunked=None)` and replaying the same normalise + truncate.
13. **The UI panel is already data-driven for heads.** `controls.py register()` fills the LatCH head
    dropdowns from `/info.latch_heads`, so a new head appears with zero UI code. The plan extends the
    same idea to conditioner families (`/info.conditioners`). `LATCH_SLOTS = 3` is a UI cap only.
14. **No prior work on OUTPAINTING** exists anywhere in the repo (grep: zero hits outside this plan).
    The server's 19 `inpaint` mentions are all the a2a **seam**-inpaint machinery inside
    `_a2a_mix_impl` (`seam_inpaint`, `mode="inpaint"`) — inpainting used internally to hide a
    transition join. There is **no user-facing inpaint/outpaint endpoint and no mask-region
    parameter** on :8056.
15. **A working inpaint UI already exists against THIS model family — in the SA3 fork's own gradio.**
    `stable-audio-3/stable_audio_3/interface/diffusion_cond.py`: an "Inpainting" accordion
    (`:682-684`) with `inpaint_audio_input`, `mask_maskstart_slider`, `mask_maskend_slider`, sliders
    whose ranges auto-update from `seconds_total` (`:643-652`), and the call site (`:278-285`) that
    forwards exactly `inpaint_audio` / `inpaint_mask_start_seconds` / `inpaint_mask_end_seconds` into
    `model.generate`. **This is the reference implementation for the server endpoint — copy its
    argument handling, do not re-derive it.**
16. **The older `stable-audio-tools` gradio has the same UX one model generation back.**
    `stable-audio-tools/stable_audio_tools/interface/interfaces/diffusion_cond.py` (our
    `audio-tools-avp` fork, already extended with rho/mu/gamma/n_iter + two LatCH slots) reaches
    inpainting through a *separate* entry point, `generate_diffusion_cond_inpaint`, gated on
    `model_config["model_type"] == "diffusion_cond_inpaint"` (`:19`, `:584`). **That is the SAT-1.x
    route and it is NOT the one to use for SA3** — SA3 folds inpainting into `generate()` itself.
    Useful only as UX prior art.
17. **Two UX affordances worth lifting, both absent from the explorer:**
    `send_to_init_button` / `send_to_inpaint_button` (`interface/diffusion_cond.py:790-794`) — one
    click chains a render's OUTPUT back in as the next render's init or inpaint source. The explorer
    has only a free-text `inf-init-path` field (`inference_tab.py:131`) with no way to fill it from a
    result. That chaining is what makes iterative editing usable. Also
    `cut_to_seconds_total` (`:606`), `Infinite Radio` (`:608`) and the file naming/format controls.
18. **The sigma-window shading is ALREADY DONE in the explorer — do not rebuild it.**
    `inference_tab.py:346-400` `_sigma_figure()` is an explicit plotly port of the gradio's
    `create_sigma_chart` and already draws the CFG-active band, each LatCH `start_pct/end_pct`
    window in gold, and their overlap in orange (`add_vrect` at `:380`, `:391`, `:397`), matching
    `interface/diffusion_cond.py:95-110`'s `axvspan` colours. The remaining gap is that it shades
    **LatCH** windows only — a conditioner family with its own time window must feed the same
    `latch_windows` list (Task 11).

---

## Global Constraints

- **Never build a parallel renderer or a second guidance driver.** Extend `SAO/eval/explorer_render_server.py`
  (:8056) or write a thin client of it. LatCH gain normalisation lives only in `resolve_latch`.
- **Venv-per-task.** Server + `sa3_control` + `stable_audio_3` code and their tests run under
  `/home/kim/Projects/SAO/.venv/bin/python`. Dash/viewer code and its tests run under
  `/home/kim/Projects/mir/bin/python`. Invoke by absolute path; never assume `python`.
- **Env before torch:** `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`, `PYTORCH_TUNABLEOP_ENABLED=0`,
  `MIOPEN_FIND_MODE=2`. **Never** set `HIP_VISIBLE_DEVICES=""` (flash_attn/aiter probes a Triton driver
  at import → crash).
- **The control-token holder stays a plain module global.** A `ContextVar` breaks gradient-checkpoint
  recompute (`adapters.py:41-46`). Any refactor keeps a module-level dict.
- **The trained null is ZERO TOKENS, not absence.** Under CFG the uncond half gets zeros.
- **`cross_attn_cond_mask` stays NULLed** (flash-attn; the learned pad token substitutes). Do not
  re-enable it.
- **Latent grid:** 256 channels, 4096× downsample, **FPS = 44100/4096 ≈ 10.7666** frames/sec, stereo.
  `MAX_DURATION_SEC = 378.0` per single window.
- **`sample_size` trap:** always pass `sample_size=budget_for(duration)`; the default silently clamps
  to 120 s.
- **Fail loud, never pad silence.** Every new path validates and raises with the offending value in
  the message; no silent fallbacks, no zero-filled outputs.
- **Save z0 next to every render** (standing directive) — fp16 `.z0.npy` sibling.
- **Back-compat is a hard requirement**, not a nicety: `control/sa3_control/train.py`,
  `lumi/render_morph.py`, `control/sa3_control/{generate,melody_pilot_eval,multi_adapter_onset_eval}.py`
  and `density_control_eval.py` all call `install_adapters` / `w.adapter` / `use_control_context` /
  `adapter_state_dict` / `load_adapter_state`. Their existing call signatures must keep working
  unchanged.
- **Repos and branches:** `SAO` on `sa3-style-adapter`; nested fork `SAO/stable-audio-3` on
  `latch-sa3-phase1`; `mir` on `sa3-latent-explorer`. Each repo gets its own commits.
- **Bungee only** for any pitch/time work; never sox.
- **Three-audience standard** applies to any eval/audition page this produces
  (`docs/superpowers/specs/2026-07-06-eval-tables-human-first.md` §14).

---

## File Structure

**New files**

| path | repo | responsibility |
|---|---|---|
| `control/sa3_control/conditioning.py` | SAO | `RenderContext`, `Contribution`, `ConditionerFamily`, the `FAMILIES` registry, `ConditioningBundle`. The one abstraction. No I/O, no HTTP. |
| `control/sa3_control/families.py` | SAO | The concrete families (text, film_scalar, the Head-B set, mir_ctrl, latch). Imports encoders + loaders; registers itself on import. |
| `control/sa3_control/loading.py` | SAO | Checkpoint introspection + install/load for control checkpoints, incl. the dora-rows ordering. Single source of truth, factored from three scripts. |
| `control/sa3_control/tests/test_conditioning.py` | SAO | CPU tests for registry, bundle, batch alignment, windowing. |
| `control/sa3_control/tests/test_slots.py` | SAO | CPU tests for named adapter slots + back-compat shims. |
| `control/sa3_control/tests/test_loading.py` | SAO | CPU tests for checkpoint introspection. |
| `eval/inpaint_ops.py` | SAO | Pure-numpy canvas/region/splice/crossfade helpers for `/inpaint`. No torch, no model — trivially testable. |
| `eval/tests/test_inpaint_ops.py` | SAO | CPU tests for the above. |
| `mir/plots/explorer_sa3/conditioner_panel.py` | mir | Generic Dash panel generated from `/info.conditioners`. |
| `mir/plots/explorer_sa3/inpaint_tab.py` | mir | The Inpaint/Outpaint tab. |
| `mir/tests/explorer_sa3/test_conditioner_panel.py` | mir | Panel schema→widgets→payload tests (no server). |
| `mir/tests/explorer_sa3/test_inpaint_tab.py` | mir | Payload-building tests (no server). |

**Modified files**

| path | repo | change |
|---|---|---|
| `control/sa3_control/adapters.py` | SAO | `_ACTIVE` → named slots; `align_control_batch`; `ControlledCrossAttention.adapters` ModuleDict + `.adapter` back-compat property; `use_control_slots`. |
| `control/sa3_control/inject.py` | SAO | `install_adapters(..., slot=)`; `adapter_state_dict(..., slot=)`; `freeze_base_train_adapters(..., slot=)`. |
| `control/sa3_control/generate.py` | SAO | `load_adapter_state(..., slot=)`; `build_conditioner` delegates to `loading.py`. |
| `eval/explorer_render_server.py` | SAO | z0 sidecars; bundle wiring; `/info.conditioners`; `/ckpts` family annotation; `/inpaint`; crossfade helper extraction. |
| `stable-audio-3/stable_audio_3/inference/longform.py` | SA3 fork | `cond_hook` on `InpaintContinuationGenerator` and `SDEditReanchor`; `LongFormRenderer` per-window hook. |
| `stable-audio-3/tests/test_longform.py` | SA3 fork | cond_hook tests. |
| `mir/plots/explorer_sa3/controls.py` | mir | Mount the conditioner panel; contract v3 (append-only). |
| `mir/plots/explorer_sa3/render_client.py` | mir | `inpaint()`; `_OPS` += `inpaint`. |
| `mir/plots/explorer_sa3/{inference_tab,a2a_tab}.py` | mir | Thread the conditioner block into payloads. |
| `mir/plots/explorer_sa3/app.py` | mir | Register the new tab. |
| `docs/INFERENCE-SURFACE.md`, `ARCHITECTURE.md`, `EXPERIMENTS.md`, `WORKLOG.md`, `KIM-TASKLIST.md`, `MASTER.md` | SAO | Index + truth updates (Task 13). |

---

## Design contract (read once; every task below implements a slice of this)

### (a) What a "global conditioner" is

SA3 has **five** conditioning inlets plus a guidance channel. A conditioner family declares which one
it uses; the bundle merges all of them so the sampler call never has to know:

| `inlet` value | reaches the DiT as | how the bundle delivers it |
|---|---|---|
| `cross_attn_text` | T5-Gemma cross-attention | `generate_kwargs["prompt"/"negative_prompt"]` |
| `global_cond` | `global_cond` (`prepend` \| `adaLN`) | `cond_tensors[<id>] = [tensor]` |
| `local_add_cond` | 257-ch inpaint_mask + masked_input | `generate_kwargs["inpaint_audio"/"inpaint_mask_*"]` |
| `prepend_cond` | `prepend_embeds` / `to_prepend_embed` | `cond_tensors[<id>] = [tensor, mask]` |
| `modular_local` | per-block `modular_local_embeds` | `cond_tensors[<id>] = [tensor]` |
| `control_tokens` | decoupled cross-attn adapter branch | `control_slots[slot] = (tokens, gain)` |
| `guidance` | LatCH gradient guidance | `generate_kwargs["latch_configs"/"latch_hparams"]` |

A **spec** is JSON the UI and the CLI both speak:

```json
{"family": "melody_contour", "enabled": true, "ckpt": "/…/riffer_final.pt",
 "gain": 1.5, "params": {"stream_path": "/…/000123.melody8.npy", "offset_frames": 0}}
```

A **`ConditioningBundle`** resolves a list of specs against a `RenderContext` and exposes exactly four
things. Every sampler in the codebase can be fed from these four:

```python
bundle.generate_kwargs()                # -> dict, splat into StableAudioModel.generate(**kw)
bundle.cond_hook()                      # -> Callable[[dict], dict], mutates a conditioning_tensors dict
with bundle.context():                  # -> control-adapter slots active for the sampling call
bundle.window(frame_offset, n_frames)   # -> a new bundle whose time-varying streams are re-sliced
```

`generate_kwargs()` covers `/generate`, `/a2a_track`, `/a2a_mix`, `/inpaint`. `cond_hook()` covers the
low-level `sample_diffusion` paths (`InpaintContinuationGenerator`, `SDEditReanchor`) that build their
own conditioning dicts. `context()` covers control adapters everywhere. `window()` exists because a
longform render calls the sampler once per window and a per-frame control stream must be sliced to
that window — a time-invariant family returns `self`.

### (b) Accommodating families we have not trained yet

Three mechanisms, all data-driven:

1. **Registry.** A new family is one class + `register(MyFamily())`. Nothing else in the server
   changes.
2. **`describe()` → `/info.conditioners` → generic UI.** Each family returns a JSON schema
   (`{name, label, inlet, needs_ckpt, ckpt_glob, params: [{key, type, label, default, min, max,
   options, help}]}`). `conditioner_panel.py` renders widgets from that schema and serialises them back
   into a spec. **A family trained next month appears in the UI with zero UI code**, exactly as LatCH
   heads do today.
3. **`detect(ckpt) -> bool`.** `/ckpts` annotates every scanned checkpoint with its family, so the
   picker can offer the right panel automatically instead of the user knowing which loader a file
   needs. Detection keys, verified: top-level `control_mode` ⇒ that Head-B family;
   `state_dict` keys containing `parametrizations.weight.0.lora_A` ⇒ adapter; a `mir_ctrl` entry in
   the run config ⇒ `mir_ctrl`; otherwise full-FT or base.

### (c) Multiple control adapters at once

**Yes, and the module-global reason does not stand in the way.** The reason `_ACTIVE` is a plain dict
rather than a `ContextVar` is gradient-checkpoint recompute — a property of *where* the state lives,
not of *how many* entries it holds. So:

- `_ACTIVE: dict[str, tuple[Tensor, float]]` — still a plain module global, still read live during
  recompute. Slot name → (cond tokens, gain).
- `ControlledCrossAttention.adapters: nn.ModuleDict` — one `DecoupledControlAdapter` branch per slot.
  Branches are additive (`out += gain_s * branch_s(...)`), which is what the architecture already does
  for one branch.
- Back-compat shims keep every existing caller working: `ControlContext(tokens, gain)` and
  `use_control_context(ctx)` map to slot `"default"`; `w.adapter` stays a property returning
  `adapters["default"]`; `install_adapters(sam, control_dim)` still installs the `"default"` slot.

**Honesty gate — this is a capability, not a validated result.** Each Head-B family was trained alone
against a frozen base; two loaded branches summing at inference is **out of distribution and
untested**. Therefore: single-slot is the default; activating >1 control-token family returns a
`warnings` entry in the response and is registered as an experiment (Task 13) with a kill criterion,
not advertised as working.

**Batch alignment is the other half of "multiple".** Control tokens are stored **cond-only, already
repeated to `batch_size`**; the adapter expands them to the DiT's live batch at use time:

```python
def align_control_batch(tokens, target_batch):
    b = tokens.shape[0]
    if target_batch == b:      return tokens                                    # CFG off / outside cfg_interval
    if target_batch == 2 * b:  return torch.cat([tokens, torch.zeros_like(tokens)], 0)   # CFG: trained null = zeros
    raise ValueError(f"control tokens batch {b} incompatible with DiT batch {target_batch}")
```

This single function fixes the three live bugs from discovery finding 6 (cfg_scale == 1.0,
batch_size > 1, cfg_interval gating) for every family at once.

### (d) Control surviving into a2a and longform

| path | today | after |
|---|---|---|
| t2a `/generate` | text + DoRA + FiLM + LatCH | + every registered family |
| a2a `/a2a_track`, `/a2a_mix` | same set (`_a2a_pass` threads `latch_cfgs`, `film_req`) | `_a2a_pass` takes the bundle; families ride `generate_kwargs` + `context()` |
| longform **a2a arc** | per-window `_a2a_pass` | per-window `bundle.window(...)` — streams sliced to the window |
| longform **t2a** | FiLM only; LatCH explicitly warned as unreachable | `cond_hook` reaches `InpaintContinuationGenerator._cond`, so `modular_local`/`prepend`/`global` families work; control-token families ride `context()`. LatCH stays unreachable (no hook in `sample_diffusion`) and keeps its explicit warning. |
| `SDEditReanchor` | builds its own cond dict — **control silently absent** (D14's blocker) | same `cond_hook` parameter |

### (e) Inpaint and outpaint as user-facing operations

**Why a new `/inpaint` endpoint rather than a mode on `/generate`.** The capability is already
first-class in `model.generate()` (discovery 2) and the SA3 gradio already drives it that way
(discovery 15), so a `mode` flag on `/generate` would be less code. It is still the wrong shape,
for three reasons that all cost correctness rather than tidiness:
(i) `/generate`'s contract is *"prompt in, N fresh clips out"* and its callers (`inference_tab`,
`bracket.py`'s sweep counter) assume `batch_size` clips of `duration` seconds — inpaint returns one
clip whose length is the CANVAS, not the request duration, and its `batch_size` semantics are
different (N variations of the same edit);
(ii) inpaint needs validation `/generate` must not grow — region bounds, overlap, source-vs-canvas
span — and a mode flag makes those conditionally-required parameters, the exact shape that produces
plausible-but-wrong output when one is omitted;
(iii) the >378 s case has to re-route to a completely different sampler (`LongFormRenderer`), which a
`/generate` mode cannot honestly express.
`/inpaint` also gives `render_client` a named method and the UI a tab, matching how `/bend` and
`/longform` were added. **Outpaint is a `mode` ON `/inpaint`, not its own endpoint** — same canvas,
same mask, same sampler; only the region derivation differs.

**Relationship to `/longform init_latent_path`.** That mode (added 2026-08-23) already covers
*extend-forwards-from-a-latent*. `/inpaint` does not duplicate it: `mode="outpaint_tail"` with a
canvas over 378 s **delegates to it**, and `meta["route"]` says so. Backwards outpaint genuinely
needs different treatment — `InpaintContinuationGenerator` clamps a *prefix* and generates the
*suffix* (`generate(prompt, prefix_latents, prefix_frames, n_frames, seed)`, `longform.py:282`), so
there is no backwards equivalent; within one 378 s window `generate(inpaint_audio=…)` handles it
natively because the mask is arbitrary, and beyond one window it raises rather than pretending.

One endpoint, `POST /inpaint`, over an explicit **canvas** model:

```
canvas:      [0 ................................ canvas_duration]
source:            [source_offset_sec .. source_offset_sec + source_duration]
regions:                  [start,end)   [start,end)          ← what gets REGENERATED (mask 0)
```

`mode` is a shortcut that derives `regions` when the user does not draw them:

| mode | regions |
|---|---|
| `inpaint` | taken verbatim from `regions` (required, ≥1) |
| `outpaint_tail` | `[[source_end, canvas_duration]]` |
| `outpaint_head` | `[[0, source_offset_sec]]` |
| `outpaint_both` | both of the above |

Two routes, both existing machinery, chosen by total length and announced in `meta["route"]`:

- **`single_window`** (`canvas_duration <= 378 s`): one `MODEL.generate()` with
  `inpaint_audio=(SR, canvas)` and list-valued `inpaint_mask_start_seconds` /
  `inpaint_mask_end_seconds`. Multi-region is native. Zero new sampler code.
- **`longform_continuation`** (`canvas_duration > 378 s`, tail-only): the existing
  `LongFormRenderer` + `InpaintContinuationGenerator` with `init_latents` = the source latent —
  i.e. the `/longform init_latent_path` mode. Head-outpaint and interior inpaint beyond 378 s raise
  with a message naming this limitation; they are not silently truncated.

**Splice (default ON).** Because SA3 inpaint soft-conditions the kept region (discovery finding 3), the
response by default returns the **source samples bit-intact outside the regions**, equal-power
crossfaded (`xfade_sec`, default 0.25 s) into each regenerated region. `splice: false` returns the
model's whole output for comparison. Both are saved when `both_outputs: true`, so Kim can A/B.

**Latent sources** are supported by decoding to audio first (`pretransform.decode`, the code
`_decode_impl` already runs) and then taking the single-window route — one inpaint implementation, not
two. The SAME decoder is noise-robust by construction so the round trip is acceptable; it is recorded
in `meta` as `source_roundtrip: true` so a listening verdict is never confounded by it unknowingly.

### (f) Staged rollout — nothing currently working breaks

Tasks are ordered so each one lands behind either an unchanged default or a new endpoint:

1. **Task 1** adds z0 sidecars — additive files only; guarded by a byte-parity test on `/generate`.
2. **Tasks 2–3** are library-only (`sa3_control`), default slot `"default"`, back-compat shims,
   no server behaviour change.
3. **Task 4** adds `conditioning.py` — new module, imported by nobody yet.
4. **Task 5** routes the server's *existing* text + FiLM through the bundle, gated on a **byte-parity
   regression test**: same request, same seed, identical audio before/after.
5. **Tasks 6–7** add families. Absent from a request ⇒ absent from behaviour.
6. **Task 8** adds an *optional* `cond_hook=None` parameter to the longform primitives — default None
   reproduces today exactly.
7. **Tasks 9–10** add `/inpaint`, a brand-new endpoint.
8. **Tasks 11–12** are UI-only, append-only to the steering contract (v2 → v3), new tab.
9. **Task 13** is docs + registry entries.

Rollback granularity is one commit per task, per repo.

---

## Task 1: Latent sidecars from the render server

Without this, the server's own renders cannot be continued, inpainted or outpainted — `/longform
init_latent_path` and everything in Tasks 9–10 need a `.z0.npy`. Also closes a standing-directive
violation ("save z0 next to every render").

**Files:**
- Create: `/home/kim/Projects/SAO/eval/render_io.py`
- Create: `/home/kim/Projects/SAO/eval/tests/test_render_io.py`
- Modify: `/home/kim/Projects/SAO/eval/explorer_render_server.py` (imports block ~line 50; `build_response` :528; `_generate_impl` :734; `_longform_impl` :944; `_a2a_track_impl` :866)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `render_io.normalize_and_truncate(result: torch.Tensor, duration_sec: float, sample_rate: int) -> torch.Tensor`
  - `render_io.save_z0(path: pathlib.Path, z: torch.Tensor) -> pathlib.Path` — writes fp16 `(256, T)`
  - `render_io.z0_path_for(wav_path: pathlib.Path) -> pathlib.Path` — `out_00.wav` → `out_00.z0.npy`
  - server: `decode_latents(z) -> torch.Tensor`, `generate_with_latents(kw: dict, duration: float) -> tuple[torch.Tensor, torch.Tensor]`
  - server: every render response gains `resp["latents"]: list[str]` (absolute paths, same order as `files`)

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/eval/tests/test_render_io.py`:

```python
import numpy as np
import torch

import sys
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from render_io import normalize_and_truncate, save_z0, z0_path_for


def test_normalize_only_scales_down():
    quiet = torch.full((1, 2, 100), 0.3)
    out = normalize_and_truncate(quiet, duration_sec=100 / 44100, sample_rate=44100)
    assert torch.allclose(out, quiet)                      # never scales UP


def test_normalize_divides_by_peak_when_over_full_scale():
    loud = torch.zeros(1, 2, 100)
    loud[0, 0, 0] = 2.0
    out = normalize_and_truncate(loud, duration_sec=100 / 44100, sample_rate=44100)
    assert abs(float(out.abs().amax()) - 1.0) < 1e-6


def test_normalize_is_per_item():
    x = torch.zeros(2, 2, 10)
    x[0] = 4.0
    x[1] = 0.5
    out = normalize_and_truncate(x, duration_sec=10 / 44100, sample_rate=44100)
    assert abs(float(out[0].abs().amax()) - 1.0) < 1e-6
    assert abs(float(out[1].abs().amax()) - 0.5) < 1e-6    # item 1 untouched


def test_truncate_to_duration():
    x = torch.zeros(1, 2, 44100)
    out = normalize_and_truncate(x, duration_sec=0.5, sample_rate=44100)
    assert out.shape[-1] == 22050


def test_save_z0_writes_2d_fp16(tmp_path):
    z = torch.randn(1, 256, 64)
    p = save_z0(tmp_path / "out_00.z0.npy", z)
    arr = np.load(p)
    assert arr.shape == (256, 64)
    assert arr.dtype == np.float16


def test_z0_path_for():
    from pathlib import Path
    assert z0_path_for(Path("/j/out_00.wav")).name == "out_00.z0.npy"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  .venv/bin/python -m pytest eval/tests/test_render_io.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'render_io'`.

- [ ] **Step 3: Write minimal implementation**

Create `/home/kim/Projects/SAO/eval/render_io.py`:

```python
"""Render-output I/O helpers shared by the render server.

`normalize_and_truncate` is StableAudioModel.generate's own post-sampling tail
(model.py:390-405) lifted verbatim, so a caller that samples with
return_latents=True and decodes itself gets BYTE-IDENTICAL audio to the
generate() call it replaced. Kept in its own module so it is testable without
importing the server (which pulls in the whole SA3 stack).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


def normalize_and_truncate(result: torch.Tensor, duration_sec: float,
                           sample_rate: int) -> torch.Tensor:
    """(B, C, N) -> normalized-down, duration-truncated audio. model.py:390-405.

    Normalizes DOWN instead of hard-clamping: SA3 raw output routinely peaks >1.0
    and clamp() flat-tops it before any writer's peak-normalize can help. Per-item
    scale, only when over full scale."""
    result = result.to(torch.float32)
    peak = result.abs().amax(dim=(1, 2), keepdim=True).clamp(min=1.0)
    result = result / peak
    return result[:, :, :int(duration_sec * sample_rate)]


def z0_path_for(wav_path: Path) -> Path:
    """out_00.wav -> out_00.z0.npy (the fleet-wide latent-sidecar convention)."""
    return Path(wav_path).with_suffix("").with_suffix(".z0.npy") \
        if Path(wav_path).suffixes[-2:] == [".z0", ".npy"] else \
        Path(wav_path).with_suffix(".z0.npy")


def save_z0(path: Path, z: torch.Tensor) -> Path:
    """Write one item's latent as fp16 (256, T). Accepts (C, T) or (1, C, T)."""
    a = z.detach().to(torch.float32).cpu()
    if a.dim() == 3:
        if a.shape[0] != 1:
            raise ValueError(f"save_z0 expects one item, got batch {a.shape[0]}")
        a = a[0]
    if a.dim() != 2:
        raise ValueError(f"save_z0 expects (C, T) or (1, C, T), got {tuple(a.shape)}")
    path = Path(path)
    np.save(path, a.numpy().astype(np.float16))
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /home/kim/Projects/SAO && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  .venv/bin/python -m pytest eval/tests/test_render_io.py -v
```
Expected: PASS, 6 passed.

- [ ] **Step 5: Wire the server to sample latents and save them**

In `/home/kim/Projects/SAO/eval/explorer_render_server.py`, add to the import block (after the
`import a2a_fulltrack as a2a_mod` line, ~line 50):

```python
from render_io import normalize_and_truncate, save_z0, z0_path_for  # noqa: E402
```

Add these helpers immediately before `def build_response` (~line 528):

```python
def decode_latents(z):
    """Latents -> audio, matching generate()'s internal decode exactly
    (sampling.py:519 calls pretransform.decode(sampled, chunked=chunked_decode);
    chunked_decode defaults to None, i.e. the pretransform's own default)."""
    pre = MODEL.model.pretransform
    with torch.inference_mode():
        return pre.decode(z.to(next(pre.parameters()).dtype), chunked=None)


def generate_with_latents(kw, duration):
    """MODEL.generate(...) returning BOTH the audio and the z0 latents.

    generate() returns one OR the other (model.py:390-405), so we sample with
    return_latents=True and replay its normalize+truncate tail via render_io —
    byte-identical audio, plus the latent the standing z0-with-audio directive
    (and /longform init_latent_path, and /inpaint) needs."""
    z = MODEL.generate(return_latents=True, **kw)
    audio = normalize_and_truncate(decode_latents(z), duration, SR)
    return audio, z
```

Change `build_response`'s signature and body to carry latents (`:528`):

```python
def build_response(job_id, jd, files, seed, t0, stages, warnings, meta, req, rebuilt,
                   latents=None):
    meta = dict(meta)
    meta.update({"dora_loaded": LOADED_DORA, "film_loaded": FILM_LOADED,
                 "model_rebuilt": bool(rebuilt), "params_echo": req})
    resp = {"status": "ok", "job_id": job_id,
            "files": [str(f) for f in files],
            "urls": [f"/audio/{job_id}/{Path(f).name}" for f in files],
            "latents": [str(p) for p in (latents or [])],
            "seed": seed,
            "timings": {"total_sec": round(time.time() - t0, 1),
                        "per_stage": {k: round(v, 1) for k, v in stages.items()}},
            "warnings": warnings, "meta": meta}
    (jd / "result.json").write_text(json.dumps(resp, indent=2, default=str))
    return resp
```

In `_generate_impl`, replace the generate + save block:

```python
        tg = time.time()
        with film_context(req.get("film")):
            out, z0 = generate_with_latents(with_lora_interval(kw), duration)
        stages["generate"] = time.time() - tg
        check_output_length(out, duration, "generate")
        files, latents = [], []
        for i in range(out.shape[0]):
            p = jd / f"out_{i:02d}.wav"
            save_audio(p, out[i].float().cpu(), SR, normalize=True)
            files.append(p)
            latents.append(save_z0(z0_path_for(p), z0[i:i + 1]))
        log(f"[gen {job_id}] done {time.time()-t0:.1f}s")
        return build_response(job_id, jd, files, seed, t0, stages, [],
                              {"op": "generate"}, req, rebuilt, latents=latents)
```

In `_longform_impl`'s t2a branch the latents already exist as `lat`; after `save_audio(p, out, SR,
normalize=True)` add:

```python
        lf_latents = []
        if audio_path is None:
            lf_latents.append(save_z0(z0_path_for(p), lat[0:1].detach().cpu()))
```
and pass `latents=lf_latents` to `build_response`.

- [ ] **Step 6: Verify byte-parity on the GPU, then that the sidecar is usable**

Launch the server (or restart it if running — check `/tmp/gpu.lock` and `rocm-smi --showpids` first,
per the GPU-lock convention):
```bash
cd /home/kim/Projects/SAO && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  MIOPEN_FIND_MODE=2 .venv/bin/python eval/explorer_render_server.py --port 8056
```
Then, from another shell:
```bash
curl -s -X POST localhost:8056/generate -H 'content-type: application/json' \
  -d '{"prompt":"psychedelic goa trance","duration":12,"steps":8,"cfg_scale":6,"seed":4242}' \
  | /home/kim/Projects/SAO/.venv/bin/python -c "import json,sys; r=json.load(sys.stdin); print(r['files'][0]); print(r['latents'][0])"
```
Expected: two paths printed; the `.z0.npy` exists and loads as `(256, 129)`
(`ceil(12 * 10.7666)` = 130 frames before truncation; assert `abs(T - 12*10.7666) < 2`):
```bash
/home/kim/Projects/SAO/.venv/bin/python -c "
import numpy as np, sys; a=np.load(sys.argv[1]); print(a.shape, a.dtype); assert a.dtype==np.float16 and a.shape[0]==256
" <the .z0.npy path>
```
Then confirm the audio path did not change: `git stash` the server change, re-run the same curl with
the same seed, `git stash pop`, and compare the two wavs:
```bash
/home/kim/Projects/SAO/.venv/bin/python -c "
import soundfile as sf, numpy as np, sys
a,_=sf.read(sys.argv[1]); b,_=sf.read(sys.argv[2])
print('shape', a.shape, b.shape, 'maxdiff', np.abs(a-b).max())
assert a.shape==b.shape and np.abs(a-b).max() < 1e-6
" <before.wav> <after.wav>
```
Expected: `maxdiff` ~0 (below 1e-6). If it is not, `chunked_decode` differs — pass the model config's
value explicitly to `pre.decode` rather than `None` and re-check. **Do not proceed past a failing
parity check**; a silent change to `/generate`'s output would invalidate every stored listening verdict.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/render_io.py eval/tests/test_render_io.py eval/explorer_render_server.py && \
git commit -m "render server: save .z0.npy next to every render (standing directive); byte-parity decode helper

Closes the gap that made /longform init_latent_path unusable on the server's own
output — it consumed a .z0.npy that no server endpoint ever wrote.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

## Task 2: Named control-adapter slots + batch/CFG alignment

Library-only. Turns the single-tensor module global into a named-slot dict (keeping the plain-global
property that gradient checkpointing requires) and moves batch handling into the one place that knows
the live DiT batch. No server behaviour changes in this task.

**Files:**
- Modify: `/home/kim/Projects/SAO/control/sa3_control/adapters.py` (whole control-token section, `:36-63`; `ControlledCrossAttention`, `:144-159`)
- Modify: `/home/kim/Projects/SAO/control/sa3_control/inject.py` (`install_adapters` `:27`, `freeze_base_train_adapters` `:47`, `adapter_state_dict` `:63`)
- Modify: `/home/kim/Projects/SAO/control/sa3_control/generate.py` (`load_adapter_state` `:54`)
- Create: `/home/kim/Projects/SAO/control/sa3_control/tests/test_slots.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `adapters.DEFAULT_SLOT: str = "default"`
  - `adapters.ControlContext(control_tokens: torch.Tensor | None, gain: float = 1.0, slot: str = DEFAULT_SLOT)`
  - `adapters.align_control_batch(tokens: torch.Tensor, target_batch: int) -> torch.Tensor`
  - `adapters.current_control_slots() -> dict[str, tuple[torch.Tensor, float]]`
  - `adapters.use_control_slots(mapping: dict[str, ControlContext])` — context manager, save/restore
  - `adapters.use_control_context(ctx: ControlContext | None)` — unchanged signature, maps to `DEFAULT_SLOT`
  - `adapters.current_control_context() -> ControlContext | None` — unchanged, reads `DEFAULT_SLOT`
  - `ControlledCrossAttention.adapters: nn.ModuleDict`, `.add_slot(slot, control_dim, position_encoding=True)`, `.adapter` (property → `adapters[DEFAULT_SLOT]`)
  - `inject.install_adapters(sam, control_dim, position_encoding=True, slot=DEFAULT_SLOT) -> list[ControlledCrossAttention]`
  - `inject.adapter_state_dict(wrappers, conditioner=None, slot=DEFAULT_SLOT) -> dict`
  - `inject.freeze_base_train_adapters(sam, wrappers, extra_trainable=(), slot=DEFAULT_SLOT) -> list`
  - `generate.load_adapter_state(state, wrappers, cond_enc, slot=DEFAULT_SLOT) -> None`

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/control/sa3_control/tests/test_slots.py`:

```python
import pytest
import torch
from torch import nn

from sa3_control.adapters import (DEFAULT_SLOT, ControlContext, align_control_batch,
                                  current_control_context, current_control_slots,
                                  use_control_context, use_control_slots)


def test_align_returns_tokens_when_batch_matches():
    t = torch.randn(2, 8, 16)
    assert align_control_batch(t, 2) is t


def test_align_appends_zero_null_when_cfg_doubles_the_batch():
    t = torch.ones(2, 8, 16)
    out = align_control_batch(t, 4)
    assert out.shape == (4, 8, 16)
    assert torch.all(out[:2] == 1.0)
    assert torch.all(out[2:] == 0.0)          # trained null = ZERO tokens, not absence


def test_align_raises_on_impossible_batch():
    with pytest.raises(ValueError, match="incompatible"):
        align_control_batch(torch.randn(2, 8, 16), 3)


def test_slots_are_isolated_and_restored():
    a = ControlContext(torch.ones(1, 4, 8), gain=2.0, slot="film")
    b = ControlContext(torch.zeros(1, 4, 8), gain=0.5, slot="melody")
    assert current_control_slots() == {}
    with use_control_slots({"film": a, "melody": b}):
        slots = current_control_slots()
        assert set(slots) == {"film", "melody"}
        assert slots["film"][1] == 2.0 and slots["melody"][1] == 0.5
    assert current_control_slots() == {}


def test_nested_use_restores_the_outer_state():
    outer = ControlContext(torch.ones(1, 4, 8), gain=1.0, slot="film")
    inner = ControlContext(torch.ones(1, 4, 8) * 3, gain=9.0, slot="film")
    with use_control_slots({"film": outer}):
        with use_control_slots({"film": inner}):
            assert current_control_slots()["film"][1] == 9.0
        assert current_control_slots()["film"][1] == 1.0


def test_legacy_use_control_context_still_targets_the_default_slot():
    ctx = ControlContext(torch.ones(1, 4, 8), gain=1.5)
    with use_control_context(ctx):
        assert DEFAULT_SLOT in current_control_slots()
        back = current_control_context()
        assert back is not None and back.gain == 1.5
    assert current_control_context() is None


# --- wrapper-level tests against a stand-in that mimics the fork's Attention ---

class _FakeAttention(nn.Module):
    dim, dim_heads, num_heads, kv_heads = 16, 4, 4, 4
    qk_norm, differential = "none", False

    def __init__(self):
        super().__init__()
        self.to_q = nn.Linear(self.dim, self.dim, bias=False)
        self.to_kv = nn.Linear(self.dim, 2 * self.dim, bias=False)

    def apply_attn(self, q, k, v, **kw):
        return torch.zeros_like(q)                 # deterministic: branch output = to_out(0) = 0

    def forward(self, x, context=None, **kw):
        return torch.zeros_like(x)


def test_wrapper_holds_multiple_named_branches_and_default_alias():
    from sa3_control.adapters import ControlledCrossAttention
    w = ControlledCrossAttention(_FakeAttention(), control_dim=8)
    assert set(w.adapters.keys()) == {DEFAULT_SLOT}
    assert w.adapter is w.adapters[DEFAULT_SLOT]       # back-compat alias every caller uses
    w.add_slot("melody", control_dim=12)
    assert set(w.adapters.keys()) == {DEFAULT_SLOT, "melody"}
    w.add_slot("melody", control_dim=12)               # idempotent
    assert len(w.adapters) == 2


def test_wrapper_ignores_slots_it_has_no_branch_for():
    from sa3_control.adapters import ControlledCrossAttention
    w = ControlledCrossAttention(_FakeAttention(), control_dim=8)
    x = torch.randn(2, 5, 16)
    with use_control_slots({"nosuchslot": ControlContext(torch.randn(2, 3, 8), 1.0)}):
        out = w(x)                                      # must not raise
    assert out.shape == x.shape


def test_install_adapters_is_idempotent_per_slot():
    from sa3_control.inject import install_adapters

    class _Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.cross_attn = _FakeAttention()

    class _Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList([_Block(), _Block()])

    class _SAM:
        def __init__(self):
            self.model = _Model()

    sam = _SAM()
    w1 = install_adapters(sam, control_dim=8)
    w2 = install_adapters(sam, control_dim=8)
    assert [id(a) for a in w1] == [id(a) for a in w2]
    w3 = install_adapters(sam, control_dim=12, slot="melody")
    assert [id(a) for a in w1] == [id(a) for a in w3]
    assert set(w1[0].adapters.keys()) == {DEFAULT_SLOT, "melody"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_slots.py -v
```
Expected: FAIL — `ImportError: cannot import name 'align_control_batch'`.

- [ ] **Step 3: Replace the control-token section of `adapters.py`**

Replace `adapters.py` lines 36-63 (the `ControlContext` dataclass through `use_control_context`) with:

```python
DEFAULT_SLOT = "default"


@dataclass
class ControlContext:
    control_tokens: Optional[torch.Tensor] = None   # (B, T_ctrl, control_dim), COND ONLY,
                                                    # already repeated to the request batch B
    gain: float = 1.0                               # generation-time strength (1.0 = as trained)
    slot: str = DEFAULT_SLOT                        # which adapter branch these tokens feed


# Module-global holder, slot -> (tokens, gain). We deliberately DON'T use a ContextVar:
# the DiT gradient-checkpoints every block, and torch.utils.checkpoint does NOT preserve
# ContextVar state into the backward RECOMPUTE, so the adapter branch would be skipped on
# recompute (saved-tensor count mismatch -> CheckpointError). A plain module global is read
# live during recompute, so the original forward and the recompute agree. Making it a DICT
# does not change that property — only how many branches may be active at once.
_ACTIVE: dict = {}


def current_control_slots() -> dict:
    """slot -> (tokens, gain) for every currently-active control source."""
    return _ACTIVE


def current_control_context() -> Optional[ControlContext]:
    """Back-compat: the DEFAULT_SLOT entry as a ControlContext, or None."""
    ent = _ACTIVE.get(DEFAULT_SLOT)
    return ControlContext(ent[0], ent[1], DEFAULT_SLOT) if ent is not None else None


@contextmanager
def use_control_slots(mapping):
    """Activate several named control sources at once. mapping: slot -> ControlContext.
    Saves and RESTORES the previous state so nesting composes (film_context inside a
    bundle context, etc.)."""
    prev = dict(_ACTIVE)
    for slot, ctx in (mapping or {}).items():
        if ctx is None or ctx.control_tokens is None:
            _ACTIVE.pop(slot, None)
        else:
            _ACTIVE[slot] = (ctx.control_tokens, float(ctx.gain))
    try:
        yield
    finally:
        _ACTIVE.clear()
        _ACTIVE.update(prev)


@contextmanager
def use_control_context(ctx: Optional[ControlContext]):
    """Back-compat single-source entry point (train.py, render_morph.py, generate.py,
    melody_pilot_eval.py, density_control_eval.py all call this). Targets ctx.slot,
    which defaults to DEFAULT_SLOT."""
    slot = getattr(ctx, "slot", DEFAULT_SLOT) if ctx is not None else DEFAULT_SLOT
    with use_control_slots({slot: ctx}):
        yield


def align_control_batch(tokens: torch.Tensor, target_batch: int) -> torch.Tensor:
    """Expand COND-ONLY control tokens to the DiT's live batch.

    The DiT runs cat([x, x]) only when cfg_scale != 1.0 AND sigma is inside cfg_interval
    (models/dit.py:493-497), so the live batch is B or 2B and BOTH occur within one render
    when a cfg_interval is set. The trained null is ZERO TOKENS, so the uncond half is zeros.
    Doing this here — the only place that sees the live batch — is what makes cfg_scale=1.0,
    batch_size>1 and cfg_interval gating all correct for every control family at once."""
    b = tokens.shape[0]
    if target_batch == b:
        return tokens
    if target_batch == 2 * b:
        return torch.cat([tokens, torch.zeros_like(tokens)], dim=0)
    raise ValueError(
        f"control tokens batch {b} incompatible with DiT batch {target_batch}; "
        "tokens must be cond-only and already repeated to the request's batch_size")
```

- [ ] **Step 4: Replace `ControlledCrossAttention` (adapters.py:144-159)**

```python
class ControlledCrossAttention(nn.Module):
    """Drop-in wrapper for an SA3 cross-attention module. Runs the (frozen) base
    cross-attn unchanged, then ADDS one branch per active control slot that this
    wrapper has a branch for. Branches are independent (own K/V, own zero-init out),
    so they sum — but note that each was trained ALONE against a frozen base, so
    >1 active slot is out-of-distribution and is gated at the server layer."""

    def __init__(self, base_attention: nn.Module, control_dim: int,
                 position_encoding: bool = True, slot: str = DEFAULT_SLOT):
        super().__init__()
        self.base_attention = base_attention
        self.adapters = nn.ModuleDict()
        self.add_slot(slot, control_dim, position_encoding)

    def add_slot(self, slot: str, control_dim: int,
                 position_encoding: bool = True) -> "DecoupledControlAdapter":
        """Idempotent: an existing slot is returned untouched (re-installing must never
        silently reset trained weights)."""
        if slot not in self.adapters:
            self.adapters[slot] = DecoupledControlAdapter(
                self.base_attention, control_dim, position_encoding)
        return self.adapters[slot]

    @property
    def adapter(self):
        """Back-compat alias: every existing caller (train.py, inject.adapter_state_dict,
        generate.load_adapter_state, render_morph.py, melody_pilot_eval.py) uses .adapter."""
        return self.adapters[DEFAULT_SLOT]

    def forward(self, x, context=None, **kwargs):
        out = self.base_attention(x, context=context, **kwargs)
        for slot, (tokens, gain) in current_control_slots().items():
            if slot not in self.adapters or tokens is None:
                continue
            branch = self.adapters[slot]
            out = out + gain * branch(x, self.base_attention,
                                      align_control_batch(tokens, x.shape[0]))
        return out
```

- [ ] **Step 5: Add the `slot` parameter to `inject.py` and `generate.py`**

In `inject.py`, replace `install_adapters`, and add `slot` to the two helpers:

```python
def install_adapters(sam, control_dim: int, position_encoding: bool = True,
                     slot: str = DEFAULT_SLOT):
    """Wrap every cross-attn in `sam.model` with a control adapter (idempotent).
    Installing a second `slot` on already-wrapped modules ADDS a branch in place —
    it does not re-wrap and does not disturb the existing branches."""
    targets = find_cross_attn(sam.model)
    if not targets:
        raise RuntimeError("no SA3 cross-attention modules found to wrap")
    wrappers = []
    for parent, attr, base in targets:
        if isinstance(base, ControlledCrossAttention):
            base.add_slot(slot, control_dim, position_encoding)
            wrappers.append(base)
            continue
        dev = next(base.parameters()).device
        w = ControlledCrossAttention(base, control_dim, position_encoding, slot=slot).to(device=dev)
        setattr(parent, attr, w)
        wrappers.append(w)
    return wrappers


def freeze_base_train_adapters(sam, wrappers, extra_trainable=(), slot: str = DEFAULT_SLOT):
    sam.model.requires_grad_(False)
    params = []
    for w in wrappers:
        for p in w.adapters[slot].parameters():
            p.requires_grad_(True)
            params.append(p)
    for mod in extra_trainable:
        for p in mod.parameters():
            p.requires_grad_(True)
            params.append(p)
    return params


def adapter_state_dict(wrappers, conditioner=None, slot: str = DEFAULT_SLOT):
    sd = {}
    for i, w in enumerate(wrappers):
        for k, v in w.adapters[slot].state_dict().items():
            sd[f"adapter.{i}.{k}"] = v.detach().cpu()
    if conditioner is not None:
        for k, v in conditioner.state_dict().items():
            sd[f"conditioner.{k}"] = v.detach().cpu()
    return sd
```
and update its import line to `from .adapters import ControlledCrossAttention, DEFAULT_SLOT`.

In `generate.py`:

```python
def load_adapter_state(state, wrappers, cond_enc, slot=DEFAULT_SLOT):
    for i, w in enumerate(wrappers):
        pfx = f"adapter.{i}."
        sub = {k[len(pfx):]: v for k, v in state.items() if k.startswith(pfx)}
        if sub:
            w.adapters[slot].load_state_dict(sub)
    csub = {k[len("conditioner."):]: v for k, v in state.items() if k.startswith("conditioner.")}
    if csub:
        cond_enc.load_state_dict(csub)
```
with `from sa3_control.adapters import ControlContext, DEFAULT_SLOT, use_control_context` at the top.

- [ ] **Step 6: Run the new tests AND the existing control tests to verify nothing broke**

Run:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/ -v
```
Expected: `test_slots.py` all PASS, and every pre-existing test in `sa3_control/tests/` still passes
(notably `test_conditioner.py`, `test_melody_contour_cpu.py`, `test_steered_generator.py`). A failure
here means a back-compat shim is wrong — fix the shim, never the caller.

- [ ] **Step 7: Verify the training path still checkpoints (the reason the global exists)**

Run the existing training smoke that exercises gradient checkpointing:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_melody_contour_cpu.py -v
```
Expected: PASS. If a `CheckpointError` about a saved-tensor count mismatch appears, the holder is no
longer read live during recompute — re-check that `_ACTIVE` is still a module-level dict mutated in
place (never rebound) in `use_control_slots`.

- [ ] **Step 8: Commit**

```bash
git add control/sa3_control/adapters.py control/sa3_control/inject.py \
  control/sa3_control/generate.py control/sa3_control/tests/test_slots.py && \
git commit -m "sa3_control: named control-adapter slots + batch-aware CFG alignment

_ACTIVE becomes slot -> (tokens, gain); still a plain module global, because the
reason for not using a ContextVar is gradient-checkpoint recompute, not arity.
align_control_batch() moves batch handling into the only place that sees the live
DiT batch, fixing control tokens under cfg_scale==1.0, batch_size>1 and
cfg_interval gating. All existing call sites keep working via .adapter /
use_control_context / install_adapters shims.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---

## Task 3: One checkpoint loader for control checkpoints

Three scripts each carry their own copy of "figure out what this `.pt` is and install it"
(`generate.build_conditioner`, `melody_pilot_eval.render`, the server's `_install_film`), and only one
of them knows the dora-rows ordering. Factor it into one module so a family implementation is three
lines.

**Files:**
- Create: `/home/kim/Projects/SAO/control/sa3_control/loading.py`
- Create: `/home/kim/Projects/SAO/control/sa3_control/tests/test_loading.py`
- Modify: `/home/kim/Projects/SAO/control/sa3_control/generate.py` (`build_conditioner` delegates)

**Interfaces:**
- Consumes: `adapters.DEFAULT_SLOT`, `inject.install_adapters(..., slot=)`, `generate.load_adapter_state(..., slot=)` (Task 2).
- Produces:
  - `loading.ControlCkptInfo` dataclass with fields: `path: str | None`, `control_mode: str`, `control_dim: int`, `n_tokens: int`, `vocab: int | None`, `fp_in_dim: int | None`, `scalar_norm: tuple[float, float] | None`, `dora_rank: int`, `dora_alpha: float | None`, `n_branches: int`, `raw: dict`
  - `loading.inspect_control_ckpt(src: str | Path | dict) -> ControlCkptInfo`
  - `loading.build_encoder(info: ControlCkptInfo, device, dtype) -> torch.nn.Module`
  - `loading.install_control_ckpt(sam, info: ControlCkptInfo, slot: str, device, dtype) -> torch.nn.Module` — returns the ready encoder; performs the full ordered install

- [ ] **Step 1: Write the failing test**

Create `/home/kim/Projects/SAO/control/sa3_control/tests/test_loading.py`:

```python
import pytest
import torch

from sa3_control.loading import ControlCkptInfo, build_encoder, inspect_control_ckpt


def _melody_ckpt(vocab=9, control_dim=768, dora_rank=0):
    """Mirrors the real trained arm at lumi_runs/runs/headb_melody/riffer_final.pt:
    control_mode set, args["melody_vocab"] MISSING (it is None there), the true vocab
    only discoverable from the conditioner embedding's row count."""
    return {
        "control_mode": "melody_contour",
        "args": {"control_dim": control_dim, "n_tokens": 256, "melody_vocab": None},
        "dora_rank": dora_rank,
        "dora_alpha": float(dora_rank) if dora_rank else None,
        "state": {
            "adapter.0.to_k.weight": torch.zeros(control_dim, control_dim),
            "adapter.1.to_k.weight": torch.zeros(control_dim, control_dim),
            "conditioner.embed.weight": torch.zeros(vocab, control_dim),
        },
    }


def test_melody_vocab_comes_from_the_embedding_not_from_args():
    info = inspect_control_ckpt(_melody_ckpt(vocab=15))
    assert info.control_mode == "melody_contour"
    assert info.vocab == 15                       # args["melody_vocab"] is None in the real ckpt
    assert info.control_dim == 768


def test_branch_count_is_read_from_the_state_keys():
    assert inspect_control_ckpt(_melody_ckpt()).n_branches == 2


def test_dora_rank_is_surfaced():
    info = inspect_control_ckpt(_melody_ckpt(dora_rank=128))
    assert info.dora_rank == 128 and info.dora_alpha == 128.0


def test_scalar_ckpt_carries_its_norm():
    ck = {"control_mode": "scalar", "args": {"control_dim": 768, "n_tokens": 16},
          "scalar_norm": [7.219, 1.424], "state": {}}
    info = inspect_control_ckpt(ck)
    assert info.control_mode == "scalar"
    assert info.scalar_norm == (7.219, 1.424)


def test_unknown_control_mode_raises_with_the_offending_value():
    with pytest.raises(ValueError, match="banana"):
        inspect_control_ckpt({"control_mode": "banana", "args": {}, "state": {}})


def test_build_encoder_melody_matches_the_ckpt_vocab():
    enc = build_encoder(inspect_control_ckpt(_melody_ckpt(vocab=15)), "cpu", torch.float32)
    assert enc.embed.weight.shape == (15, 768)


def test_build_encoder_scalar_shape():
    ck = {"control_mode": "scalar", "args": {"control_dim": 768, "n_tokens": 16},
          "scalar_norm": [7.2, 1.4], "state": {}}
    enc = build_encoder(inspect_control_ckpt(ck), "cpu", torch.float32)
    out = enc(torch.zeros(1))
    assert out.shape == (1, 16, 768)


def test_build_encoder_fingerprint_uses_fp_in_dim():
    ck = {"control_mode": "fingerprint", "args": {"control_dim": 768, "n_tokens": 16},
          "fp_in_dim": 15, "state": {}}
    enc = build_encoder(inspect_control_ckpt(ck), "cpu", torch.float32)
    assert enc(torch.zeros(1, 15)).shape == (1, 16, 768)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_loading.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sa3_control.loading'`.

- [ ] **Step 3: Write the implementation**

Create `/home/kim/Projects/SAO/control/sa3_control/loading.py`:

```python
"""One place that knows how to read a control checkpoint and install it.

Before this module the knowledge was split three ways — generate.build_conditioner
(encoder factory), melody_pilot_eval.render (the dora-rows ORDER), and the render
server's _install_film (FiLM only) — and only one of them had the ordering right.

TWO TRAPS this module exists to hold:
  1. args["melody_vocab"] is unreliable. The real trained arm
     (lumi_runs/runs/headb_melody/riffer_final.pt) has it set to None. The vocab is
     read from state["conditioner.embed.weight"].shape[0].
  2. Joint Head-B + dora-rows arms have a strict install order (train.py:374-401,
     melody_pilot_eval.py:137-160; crash reference LUMI job 20328757):
        add_lora(RAW dit)  ->  install_adapters(wrap)  ->  load lora_state
     add_lora must run on the raw DiT so the control-adapter Linears are NOT
     dora-parametrized, but the LOAD must run after the wrap because
     get_lora_state_dict serialized the keys post-wrap with a
     `cross_attn.base_attention.*` prefix. Loading before the wrap makes every key
     "unexpected".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import torch

from .adapters import DEFAULT_SLOT
from .generate import load_adapter_state
from .inject import install_adapters

CONTROL_MODES = ("scalar", "dual_scalar", "attribute", "fingerprint",
                 "metrical_position", "melody_contour", "audio_ref")


@dataclass
class ControlCkptInfo:
    control_mode: str
    control_dim: int
    n_tokens: int
    path: Optional[str] = None
    vocab: Optional[int] = None
    fp_in_dim: Optional[int] = None
    scalar_norm: Optional[tuple] = None
    dora_rank: int = 0
    dora_alpha: Optional[float] = None
    n_branches: int = 0
    raw: dict = field(default_factory=dict, repr=False)


def inspect_control_ckpt(src) -> ControlCkptInfo:
    """Read a control checkpoint (path or already-loaded dict) without touching a model."""
    if isinstance(src, dict):
        ck, path = src, None
    else:
        path = str(src)
        ck = torch.load(path, map_location="cpu", weights_only=False)
    mode = str(ck.get("control_mode", "audio_ref"))
    if mode not in CONTROL_MODES:
        raise ValueError(f"unknown control_mode {mode!r} (have {CONTROL_MODES})")
    cargs = ck.get("args", {}) or {}
    state = ck.get("state", {}) or {}
    control_dim = int(cargs.get("control_dim", 768))
    n_tokens = int(cargs.get("n_tokens", 256))
    emb = state.get("conditioner.embed.weight")
    vocab = int(emb.shape[0]) if emb is not None else None
    if vocab is None and cargs.get("melody_vocab"):
        vocab = int(cargs["melody_vocab"])
    branches = {k.split(".")[1] for k in state if k.startswith("adapter.")}
    sn = ck.get("scalar_norm")
    dr = int(ck.get("dora_rank", 0) or 0)
    return ControlCkptInfo(
        control_mode=mode, control_dim=control_dim, n_tokens=n_tokens, path=path,
        vocab=vocab, fp_in_dim=(int(ck["fp_in_dim"]) if ck.get("fp_in_dim") else None),
        scalar_norm=(float(sn[0]), float(sn[1])) if sn else None,
        dora_rank=dr, dora_alpha=(float(ck.get("dora_alpha") or dr) if dr else None),
        n_branches=len(branches), raw=ck)


def build_encoder(info: ControlCkptInfo, device, dtype):
    """Reconstruct the encoder architecture the checkpoint was trained with."""
    m, d, n = info.control_mode, info.control_dim, info.n_tokens
    if m == "fingerprint":
        from .conditioner import FingerprintEncoder
        if info.fp_in_dim is None:
            raise ValueError(f"fingerprint ckpt {info.path!r} has no fp_in_dim")
        enc = FingerprintEncoder(in_dim=info.fp_in_dim, control_dim=d, n_tokens=min(n, 16))
    elif m in ("scalar", "dual_scalar"):
        from .conditioner import ScalarAttributeEncoder
        enc = ScalarAttributeEncoder(control_dim=d, n_tokens=min(n, 16))
    elif m == "melody_contour":
        from .conditioner import MelodyContourEncoder
        enc = MelodyContourEncoder(control_dim=d, n_classes=int(info.vocab or 9))
    elif m == "metrical_position":
        from .conditioner import MetricalEncoder
        enc = MetricalEncoder(control_dim=d)
    elif m == "attribute":
        from .conditioner import AttributeEncoder
        enc = AttributeEncoder(control_dim=d)
    else:
        from .conditioner import AudioRefEncoder
        enc = AudioRefEncoder(256, d, n)
    return enc.to(device=device, dtype=dtype)


def install_control_ckpt(sam, info: ControlCkptInfo, slot: str = DEFAULT_SLOT,
                         device: str = "cuda", dtype=None):
    """Install one control checkpoint onto a loaded StableAudioModel and return its
    ready-to-call encoder. Performs the ordered dora-rows dance when the arm needs it."""
    dit = sam.model.model
    dtype = dtype or next(dit.parameters()).dtype
    ck = info.raw

    if info.dora_rank > 0:                       # BEFORE the wrap: raw DiT only
        from functools import partial
        from stable_audio_3.models.lora import LoRAParametrization, add_lora
        r, alpha = info.dora_rank, (info.dora_alpha or float(info.dora_rank))
        lcfg = {torch.nn.Linear: {"weight": partial(LoRAParametrization.from_linear,
                                                    rank=r, lora_alpha=alpha,
                                                    adapter_type="dora-rows")},
                torch.nn.Conv1d: {"weight": partial(LoRAParametrization.from_conv1d,
                                                    rank=r, lora_alpha=alpha,
                                                    adapter_type="dora-rows")}}
        add_lora(dit, lcfg)

    wrappers = install_adapters(sam, control_dim=info.control_dim, slot=slot)

    if info.dora_rank > 0:                       # AFTER the wrap: keys carry base_attention.*
        missing, unexpected = dit.load_state_dict(ck["lora_state"], strict=False)
        if unexpected:
            raise RuntimeError(f"unexpected lora keys after wrap: {unexpected[:4]}")

    enc = build_encoder(info, device, dtype)
    load_adapter_state(ck["state"], wrappers, enc, slot=slot)
    for w in wrappers:
        w.adapters[slot].to(device=device, dtype=dtype)
    return enc.to(device=device, dtype=dtype).eval()
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_loading.py -v
```
Expected: PASS, 8 passed.

- [ ] **Step 5: Delegate `generate.build_conditioner` so there is one implementation**

In `generate.py`, replace the body of `build_conditioner` (keeping its signature — eval scripts call
it):

```python
def build_conditioner(ck, device, dtype):
    """Factory: reconstruct the right conditioner from a checkpoint dict.
    Kept for back-compat; the implementation now lives in loading.py so the
    server, the eval scripts and the conditioner families all agree."""
    from .loading import build_encoder, inspect_control_ckpt
    return build_encoder(inspect_control_ckpt(ck), device, dtype)
```

- [ ] **Step 6: Verify against a REAL checkpoint (not a synthetic one)**

Run:
```bash
cd /home/kim/Projects/SAO/control && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  /home/kim/Projects/SAO/.venv/bin/python -c "
from sa3_control.loading import inspect_control_ckpt
U='/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d'
i = inspect_control_ckpt(U + '/lumi_runs/runs/headb_melody/riffer_final.pt')
print(i.control_mode, i.control_dim, i.n_tokens, 'vocab=', i.vocab, 'dora=', i.dora_rank, 'branches=', i.n_branches)
assert i.control_mode == 'melody_contour'
assert i.vocab is not None, 'vocab must come from the embedding — args[melody_vocab] is None here'
assert i.dora_rank == 128 and i.n_branches == 24
print('OK')
"
```
Expected: prints `melody_contour 768 256 vocab=<N> dora= 128 branches= 24` then `OK`. If the UUID
drive is not mounted, mount it or substitute another `riffer_final.pt` from
`/run/media/kim/Mantu/sa3_control_runs/` (those are `control_mode="scalar"` arms — then assert
`control_mode == 'scalar'` and `scalar_norm is not None` instead).

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/SAO && git add control/sa3_control/loading.py control/sa3_control/tests/test_loading.py \
  control/sa3_control/generate.py && \
git commit -m "sa3_control: single control-checkpoint loader (introspect + ordered install)

Holds the two traps that were previously spread across three scripts: melody vocab
must come from conditioner.embed.weight (args[melody_vocab] is None on the real
trained arm), and joint dora-rows arms must add_lora BEFORE install_adapters but
load lora_state AFTER the wrap (LUMI job 20328757).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YZt2NDGSLHURAf17mHjRms"
```

---
