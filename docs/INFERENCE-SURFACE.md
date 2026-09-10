# Inference surface — what is callable, with what, producing what

**Audience: whoever builds a UI over this** (Kim 2026-08-23: *"document the code well, I will then
create a UI with Claude design"*). This is a CAPABILITY MAP, not a tutorial: every generation entry
point, every kind of model that can be loaded, every knob that actually changes the output, the
file conventions in and out, and the traps that produce plausible-but-wrong results.

> **CORRECTION, 2026-08-23 (Kim + W).** The first version of this document said no unified engine
> existed and that a UI would have to dispatch across bespoke scripts. **That was wrong.** The
> inference UI exists and has for months — see §0. It was missed because the app is split across two
> repos and two venvs, so finding one half reads as "there is no generation path". A duplicate CLI
> was built and deleted the same day. The second wrong claim, also corrected below: LatCH guidance
> DOES reach a2a through the render server (`_a2a_pass` threads `latch_cfgs`).

Scope note: entries below were read from the code on 2026-08-23. Anything I did not verify is
marked ⚠️ UNVERIFIED rather than asserted.

---

## 0. START HERE — the engine already exists

**One app, a viewer and TWO backends** (two backends because SAME-L must run under the SA3 venv):

| piece | where | port · venv | role |
|---|---|---|---|
| **Viewer** | `mir` branch `sa3-latent-explorer`, `plots/explorer_sa3/app.py` | 8051 · `mir/mir/bin/python` | Dash GUI. Tabs `inference_tab` · `a2a_tab` · `bend_tab`; `render_client.py` = client, `controls.py` = shared steering panel |
| **Latent player** | ~~`mir/scripts/latent_server_sa3.py`~~ **retired 2026-08-25 — folded into the render server below**; `latent_server_onnx.py` remains as the low-VRAM alternative | ~~7892~~ → **8056** (ONNX: 7893) | **CROPS ONLY** — `/crops /meta /decode /source /mix /steer` as GET, same query contract. NOT the inference path. `/steer` = one head, one gradient step, gain only. The old process held a SECOND resident SAME-L (7.12 GB); it now reuses `MODEL.model.pretransform`. Crop dir from `eval/latent_player.ini` (`SA3_PLAYER_INI`) |
| **Render server** | `SAO/eval/explorer_render_server.py` | 8056 · `SAO/.venv` | **THE generation path.** `medium-base` resident on GPU |

**Launch (verified 2026-08-24, Kim direct) — each from its own repo root:**

```
.venv/bin/python eval/explorer_render_server.py
cd /home/kim/Projects/mir && /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python scripts/latent_server_sa3.py
cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m plots.explorer_sa3.app
```

Two traps this pins down: the latent player runs under **`stable-audio-3/.venv`**, not `SAO/.venv`;
and the mir interpreter is **`mir/mir/bin/python`** — `mir/bin/python` does not exist.


**Render-server endpoints:** `/generate` · `/a2a_track` · `/a2a_mix` · `/longform` · `/decode` ·
`/bend` · `/schedule` · `/ckpts` · `/info` · `/status` · `/audio/{job}/{file}`.

**`/longform` has THREE modes**, not two (the third added 2026-08-23, G):
`audio_path` → a2a-style window loop over the source's own duration · no `audio_path` → pure t2a
longform from t=0 · **`init_latent_path`** → **CONTINUE an existing render**: point it at a prior
render's own `.z0.npy` and `duration` becomes the FINAL total, so only the new tail is generated.
Only an overlap-sized tail of the prefix conditions the next window. The primitive always supported
this — `InpaintContinuationGenerator.generate(prompt, prefix_latents, …)` takes `prefix_latents`
as its second positional arg — the server just never passed one.

**Guidance contract:** `controls.steering_payload()` → `{latch: [...], film, dora}`, advanced
hparams (`rho`, `mu`, `gamma`, `n_iter`) top-level. Server-side, `resolve_latch()` takes a **LIST**
of slots — per slot `head`/`path` · `kind` · `value` · `start_pct` · `end_pct` · `gain` ·
`loss_type` · `w_sec`, plus parameterless `builtin` guides — against a `HEADS` registry carrying
per-head `default_gain`, `value_default`, `target_kind_default`.

⚠️ **`resolve_latch` NORMALISES gains**: `rho = mu = first slot's gain`, per-slot
`weight = slot_gain / g0`. **A raw `weight` passed by any other tool is a different scale and its
results will not be comparable.** This is the single strongest reason not to build a parallel driver.

`controls.py` `LATCH_SLOTS = 3` is a **UI cap, not a model cap** — raise the constant for more.

Render logic inside the server is IMPORTED from the proven eval scripts
(`chroma_morph_transitions.py`, `a2a_fulltrack.py`, `density_control_eval.py`), not re-derived.

**⇒ Extend the :8056 endpoint set, or write a thin CLIENT of it. A batch/sweep CLI over
`/generate` is legitimately additive; a second implementation of guidance is not.**

---

## 1. The mental model

Everything is the same three steps:

```
load a BACKBONE  →  optionally attach CONTROL  →  SAMPLE
```

- **Backbone** = the SA3 DiT (`medium-base` unless a full-FT state is loaded over it). Generates in
  the **SAME latent space**: 256 channels, 4096× downsample, **10.766 Hz**, stereo.
  T1024 ≈ 95 s · T2048 ≈ 190 s · T4096 ≈ 380 s.
- **Control** = zero or more of four independent mechanisms (§4). They are NOT interchangeable and
  today they do not compose in one code path.
- **Sample** = rectified flow, v-parameterised. Either from pure noise (t2a) or from an existing
  latent at a chosen noise level (a2a / SDEdit).

A UI's core job is: pick a backbone, pick a control, pick a sampling mode, set the knobs.

---

## 2. Model families — and how to TELL THEM APART

This is the first thing a UI must get right, because the four families load differently and a
checkpoint does not announce which it is in its filename alone.

| family | what it is | how to detect | how to load |
|---|---|---|---|
| **base** | stock `medium-base`, no training of ours | no ckpt | `StableAudioModel.from_pretrained("medium-base")` |
| **adapter** (LoRA / DoRA-rows) | our style/control adapters | Lightning ckpt, `state_dict` keys contain `parametrizations.weight.0.lora_A` / `lora_B` / `magnitude` | `model.load_lora([path])` — arch is read from the ckpt's own `lora_config`; **never hardcode rank/alpha** |
| **full-FT** | the whole 1.4B DiT fine-tuned | Lightning ckpt whose `state_dict` covers the DiT itself | load the state over the backbone (`--base-state-ckpt` in the renderers; `load_fullft_state` in `lumi/render_showcase.py`) |
| **control adapter (Head-B)** | adapter + a conditioning encoder | ckpt has a top-level **`control_mode`** key | `install_adapters()` → build the matching encoder → `load_adapter_state()` |

**`control_mode` values seen in `control/sa3_control/`:** `scalar`, `dual_scalar`, `attribute`,
`fingerprint`, `metrical_position`, `melody_contour`.

### ⚠️ Checkpoint naming is NOT uniform
- Most runs save `epoch=<N>-step=<M>.ckpt` (fat, with optimizer state) and
  `epoch=<N>-step=<M>.weights.ckpt` (slim, weights only).
- **`sa3_control/train.py` runs save `riffer_final.pt` / `riffer_step<N>.pt` instead.** A glob for
  `epoch=*.ckpt` finds **ZERO** morph/control arms. This has bitten submit-time job construction.
- **EMA:** many fat ckpts carry a `diffusion_ema.ema_model.*` shadow. `render_matrix_cells.py
  --use-ema` prefers it. The EMA weights are usually the ones you want to audition.

---

## 3. Generation entry points

**The primary surface is the render server (§0).** Everything below is the BATCH / HEADLESS tier —
these exist because LUMI jobs and sweeps need a CLI, not because the server lacks the capability.
Prefer the server for interactive work; prefer these for many-cell grids on a cluster.

| script | mode | what it produces |
|---|---|---|
| `lumi/render_matrix_cells.py` | t2a | the STANDARD eval grid for one (label, ckpt): prompts × cfg × adapter-strength |
| `lumi/render_showcase.py` | t2a | randomised "playlist" draws over a checkpoint list |
| `lumi/render_morph.py` | t2a + control | morph/contour arms conditioned on REAL contour streams, paired with decoded references |
| `lumi/a2a_bracket.py` | **a2a** | cross-prompt SDEdit bracket across model families (EXPERIMENTS D14) |
| `eval/a2a_fulltrack.py` | **a2a** | whole-track noise-ratio ladder, 380 s windows + equal-power crossfade |
| `control/sa3_control/generate.py` | t2a + control | single render steered by a REFERENCE track's latent |
| `control/sa3_control/steered_longform.py` | longform | onset-density control schedule over a long render |
| `stable_audio_3/inference/longform.py` | longform | `SDEditReanchor`, `LongFormRenderer`, `CrossfadeStitcher`, `PromptSchedule`, `InpaintContinuationGenerator` |

### Key arguments, by script

```
render_matrix_cells.py  --label --tag --ckpt --prompts --out
                        --strengths --steps --frames --only-cfgs --use-ema
                        --base-state-ckpt --fullft --pt-medium --force
a2a_bracket.py          --label --ckpt --base-state-ckpt --corpus (repeatable) --out
                        --n-crops --frames --noise-lo --noise-hi --anchors --anchor-frac
                        --cross-corpus-frac --steps --cfg --plan-seed --control-dir
                        --control-gain --refs
a2a_fulltrack.py        --track --ckpt --out-dir --prompt --seed
                        --noise-levels --steps --cfg-scale --device
sa3_control/generate.py --adapter --reference --ref-seconds --prompt --model
                        --duration --steps --cfg --gain --seed --out
render_morph.py         --ckpt --label --melody-dir --latent-dir --caption-sidecar --out
                        --n-refs --frames --gains --cfg --steps --seed --base-state-ckpt
```

### The lowest-level call worth exposing
`SDEditReanchor(model, steps, cfg_scale).reanchor(latents, sigma_peak, prompt, seed)` —
**latent in, latent out**, prompt-conditioned SDEdit at an arbitrary noise level. No audio
round-trip. This is the cleanest primitive in the codebase and `a2a_bracket.py` is built on it.

---

## 4. The four control mechanisms

They are genuinely independent. A UI should present them as separate sections, not one "strength".

**(a) Text + guidance** — the universal one. Prompt string, `cfg_scale`, `steps`, `seed`, duration.
Text enters via T5-Gemma **cross-attention**.

**(b) Adapter strength** — for adapter families only, `--strengths` (a.k.a. `w` in filenames,
`w100` = 1.0). Scales the adapter's contribution. Values above ~1.5 are where models start to
break, which is diagnostically useful (§7).

**(c) LatCH guidance** — steer a *measured feature* toward a target during sampling. Config dicts
via `latch_configs`, consumed by `stable_audio_3/inference/latch_guided.py`:

```
{ "head": <path or head>, "target": <tensor or spec>, "weight": float,
  "start_pct": float, "end_pct": float,        # the t-window to act in
  "loss_type": ..., "huber_beta": ..., "w_sec": ..., "fps": ... }
```
Targets come from `latch_targets.build_target(kind, value, ...)` with
`kind ∈ {constant, ramp_up, ramp_down, beat_grid}` (`beat_grid` takes BPM).
Available heads — `stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt`:
`beat_activation`, `downbeat_activation`, `hardness`, `hpcp`, `onset_envelope`,
`onset_envelope_drums`, `rms_drums`, `rms_energy_{air,bass,body,mid}`, `same_chroma`,
`spectral_{flatness,flux,kurtosis,skewness}`, plus `f0_bass_ep{1,2,3}` and a `bracket_*` set.
Load with `load_latch_from_checkpoint` (`stable_audio_3.models.latch`) — **never hardcode the
head architecture**, it is read from the checkpoint.

**(d) Control-context tokens (Head-B)** — the control adapters' own channel:
```python
ctrl = encoder(symbol_stream)                       # e.g. MelodyContourEncoder
with use_control_context(ControlContext(ctrl, gain=g)):
    ...sample...
```
`ControlContext(control_tokens=(B, T_ctrl, control_dim), gain=1.0)`; `gain` is generation-time
strength, 1.0 = as trained. Under CFG the tokens must be `cat([ctrl, zeros])`, and the trained
**null is zero tokens**, not absence.

### What actually composes — corrected 2026-08-23

**Through the render server (:8056), these compose today:** text + cfg · DoRA/LoRA adapter ·
**FiLM control** (via `ControlContext`) · **LatCH multi-head guidance** — and they compose in
**a2a as well as t2a**: `_a2a_pass(..., latch_cfgs, latch_hp, film_req, ...)` calls `apply_latch()`
on every pass, so guidance rides the a2a path. *(An earlier version of this doc claimed guidance
did not reach a2a. It does. That claim was true only of the standalone `lumi/a2a_bracket.py`, which
calls `SDEditReanchor` directly and builds no control at all.)*

**What is genuinely NOT in the server** — verified by grep, no references at all:
- **Head-B contour/morph adapters** (`control_mode=melody_contour`) — those live in
  `lumi/render_morph.py` and `control/sa3_control/generate.py`.
- **pianoroll / `mir_ctrl`**, which enters via `modular_local_embeds`.
The server's only `ControlContext` user is FiLM (scalar value → encoder → tokens, with the trained
null concatenated for CFG).

⚠️ And on the raw `SDEditReanchor` path specifically: it builds its own conditioning dict (inpaint
mask + masked input only), so a control adapter attached around it is **not conditioned**. D14
dropped its pianoroll arm for exactly this reason — it would have run unconditioned while looking
like a working arm.

---

## 5. Inputs a UI must supply

**Prompt sets** — JSON: `{"prompts": [...], "cfgs": [...], "steps": int, "duration": float, ...}`.
Existing: `lumi/matrix_prompts_snapshot.json` (20 prompts, cfg 1/7/16),
`lumi/suomisoundi_prompts_snapshot.json` (20, cfg 7/16), `lumi/suomi_full_prompts.json` (23, cfg 7).

**Caption sidecars** — `{stem: {"t1":…, "t2":…, "t3":…}}`, tiered. Per-source tiers matter: goa
rides `0,0,1`, avp `0,0.9,0.1`, suomi `0.25,0.45,0.30`, bigset `0,0,1`.

**Latents** — `<stem>.npy` `(256, T)` plus `<stem>.json` crop metadata; `.TIMESERIES.npz` where MIR
features exist. A2A reads these directly; no audio needed.

**Contour/control sidecars** — `<stem>.melody8.npy`, int8, one symbol per latent frame, **0 =
undefined**. Per-directory semantics: `latents_sa3_morphL{2,3,4}` and `latents_sa3_morphIOI3`.
Vocab is per-alphabet (L2→5, L3→15, L4→77) and **must match the checkpoint's `args["melody_vocab"]`**
or the encoder's embedding is the wrong size.

## 6. Outputs — the file convention

Every renderer writes a `.wav` plus siblings:
- `.z0.npy` — the fp16 latent (standing directive: save z0 next to every render)
- `.mmline.json` (matrix cells) or `.json` (morph, a2a) — the manifest fragment: label, tag, ckpt,
  prompt, cfg, strength, seed, and mode-specific fields (sigma, donor stem, window, …)

Filename grammar, matrix cells:
`<label>__<tag>__cfg<C>__w<WWW>__<prompt-id>__s<seed>[…].wav` (`w100` = strength 1.0).
A2A bracket: `a2a__<label>__<stem>__sig<S>__from_<corpus>_<donor>__cfg<C>.wav`.

---

## 7. Traps — each of these produces plausible output, not an error

1. **The 120 s `sample_size` trap.** `generate(duration=…)` defaults `sample_size` to 5,292,032
   samples = **120 s**. A "T4096 render" silently comes out 120 s long unless `--frames` /
   `sample_size` is set. Cost us the 2026-07-22 native-cell bug.
2. **`riffer_final.pt` vs `epoch=*.ckpt`** — see §2. A glob finds zero control arms.
3. **Control loaded but never applied.** Attaching a control adapter without supplying a control
   stream conditions on nothing and looks like a working arm. `a2a_bracket.py` makes this FATAL.
4. **`refs/` subdirectories are NOT model output.** `render_morph.py` and `a2a_bracket.py` write
   decoded SOURCE crops there as listening references. Scoring them as generations poisons any
   comparison.
5. **Nested vs flat render dirs.** `render_morph.py` writes `renders/morph/<ARM>/*.wav`; most others
   are flat. A top-level `*.wav` glob on a nested dir returns zero and reads as "empty".
6. **CFG 16 / strength 2 is a DIAGNOSTIC, not a mistake.** Kim's 2026-08-22 finding: the useful
   discriminator between checkpoints is which ones stay musical when guidance is pushed. Any eval
   surface should offer those cells, not only cfg 7 / w 1.0.
7. **A2A in the 0.5–0.9 band degrades by design.** The DiT abandons harmony mid-band (W,
   2026-07-30). Read family DELTAS at matched sigma, never absolute quality.

---

## 8. What is unified, and what genuinely is not

**Corrected 2026-08-23.** The earlier version of this section listed the whole surface as
fragmented. Much of it is not — the render server IS the unification layer, and it already carries
text, adapters, FiLM, LatCH guidance, a2a, longform and bend behind one HTTP contract, importing
its render logic from the eval scripts rather than re-deriving it.

**Genuinely unified (through :8056):** checkpoint loading (base · adapter · full-FT, via `/ckpts`
+ `resolve_dora_req`) · FiLM control · multi-head LatCH guidance · t2a · a2a · longform · bend ·
job/audio serving.

**Genuinely NOT unified — the real remaining seams:**
1. **Head-B contour/morph adapters and pianoroll/`mir_ctrl` are outside the server entirely.**
   They are reachable only from `lumi/render_morph.py` and `control/sa3_control/generate.py`, with
   their own vocab and checkpoint conventions. This is the biggest gap and the one that matters for
   Kim's "incorporate everything we have trained" ask.
2. **The `modular_local_embeds` inlet does not survive into the a2a/longform samplers** even
   in principle — `SDEditReanchor` builds inpaint-mask conditioning only. Any control-under-a2a
   test needs that conditioning path extended first.
3. **Two checkpoint naming conventions** — `epoch=<N>.ckpt` vs `riffer_*.pt` (control runs).
4. **Batch scripts each re-implement output naming and manifests** (`.mmline.json` vs `.json`).

**So the unification work is narrower than it looked:** not "build an engine" — the engine exists —
but **bring the contour/morph and pianoroll control families into the :8056 contract**, which means
giving the sampler one conditioning inlet that carries control tokens and modular embeds alongside
the text/global/inpaint conditioning it already handles.

---

## 9. State of the tool — what it HAS, and what needs building

Verified 2026-08-23 by reading the server, `controls.py` and the three tabs.

### HAS

**Text-to-audio** (`inference_tab` → `/generate`): base prompt + variation · negative prompt ·
checkpoint picker (dropdown + rescan + explicit path) · duration · steps · cfg · seed · batch ·
APG scale · duration padding · dist_shift + mode · **cfg_interval (σ) with a live sigma graph** ·
**weight mutation** (on/op/amount/target — the weight-garden glitch path).

**A2A from the same tab**: init path + init noise + **noise ladder** (routes to `/a2a_track`).

**A2A / transitions** (`a2a_tab` → `/a2a_mix`): A/B anchors with sliders · segment seconds · snap ·
transition range · quantize-to-bars · mode · noise level · seam size + seam noise · pure-basis
splice · interpolation · construction mode · separate eps seeds for body and seam · tempo match +
mode · fine align · **chroma target + chroma gain** · guidance end · prompt regions · whole-track.

**Longform** (`/longform`): prompt schedule / arc, window + overlap, and **continuation from an
existing render** via `init_latent_path` (fp16 `.z0.npy` cast to model dtype server-side).

**Bend** (`bend_tab` → `/bend`): track/crop pickers, latent path, seed.

**Shared steering panel** (inference + a2a): **3 LatCH slots** × (head · kind · value · gain ·
start · end · loss · w_sec) · **FiLM** (enable/value/gain) · **DoRA** (dropdown/strength/imin/imax) ·
advanced hparams rho · mu · gamma · n_iter. `steering_payload()` consumes 35 values.

**Latent player** (now on `:8056`, GET): `/decode` · `/mix` (slerp) · `/steer` (single-head gradient nudge) ·
`/crops` · `/meta` · `/source`. Low-VRAM ONNX twin at `:7893`.

**Plumbing**: resident model, GPU lock, job log ring, `/audio` serving, `/schedule`, cached
checkpoint journal, `/info` + `/status`.

### ~~KNOWN BUG~~ — FIXED 2026-08-26 (C): empty LoRA/LatCH pickers (reported by Kim 2026-08-24, backend cleared)

> **Fix:** the pickers filled from `Input(<id>, "id")`, which Dash fires exactly once
> per page load — with :8056 down at that moment they returned `[]` and Dash never
> re-fired, so the panel stayed empty forever with no error. A shared 5 s
> `dcc.Interval` (`{ns}-ctl-info-poll`) now drives all of them; each short-circuits on
> its own current value, so the steady-state cost is nil. `render_client.info()`
> memoises successes only, so the retry actually retries. Verified end-to-end without a
> page reload. Diagnosis below kept for the record.

Symptom: the viewer shows **no LoRAs and no LatCH adapters at all**. The backend is NOT at fault —
verified 2026-08-24 with the server warm: `GET /ckpts` → `count: 362`, root
`/run/media/kim/Mantu/sa3_lora_runs`, `cached: true`; `GET /info` → 16 `latch_heads`, each already
carrying `name / family / path / default_gain / out_channels / loss_type / target_kind_default /
slider_min / slider_max / value_default`.

It is a **viewer-side load-order fault**. Both pickers fill from callbacks that fire ONCE per page
load — `controls.py:230` (`Input(head_id, "id")`, i.e. a fire-once trigger) and
`inference_tab.py:432` (`Input("inf-ckpt-rescan", "n_clicks")`, `None` at load). Each calls
`render_client.info()` / `.ckpts()`, which return `None` when :8056 is unreachable, and the callback
then returns `[]`. `info()`'s memo caches only successes, so nothing is poisoned — but **Dash never
re-fires those callbacks**, so if the viewer was started before the render server, the dropdowns stay
empty forever with no error message. **Reload was tested 2026-08-24 and did NOT fix it** — so load-order is at most half the story; the
running app process (started 56 s before the server) still needs a restart to be ruled out.
Real fix belongs in the plans: give both callbacks a retry path (an interval, or fold them into the
existing `/status` poll) and surface "render server unreachable" in the UI instead of an empty list.

**Correction to item 7 below:** head metadata IS already surfaced through `/info` (the fields listed
above) and the option label is `name [family]`. What is genuinely missing is narrower — nothing
distinguishes WHICH chroma readout a 12-d head was trained against (Kim: "of the older 12d ones we
have trained them with two different chroma readouts"), and nothing warns that `same_chroma` is
384-ch/cosine/unstandardised while an HPCP head is 12-d.

### WHY NOTHING IS FOUND — there are THREE narrow discovery paths, and none of them scans (2026-08-24)

Kim: *"How would it know even where to look?"* It doesn't. Nothing searches for models.

1. **DoRA/LoRA picker — hardcoded twice, no scan at all.** The viewer's list is a literal Python
   list, `mir/plots/explorer_sa3/controls.py:41`
   `_DORA_OPTIONS = ["none", "hof", "newstack", "evr1x"]` — it does not even read `/info`'s `dora`
   key. Server-side that key is itself the hardcoded 4-entry `DORA_REGISTRY`
   (`explorer_render_server.py:83`), and `_dora_name()` (line 326) **raises on any name not in it**,
   so a correct path typed from outside is refused. This is what Kim sees.
2. **Checkpoint journal — ONE root, TWO extensions.** `CKPT_SCAN_ROOT = <Mantu>/sa3_lora_runs`
   (line 93), recursive over `*.ckpt` / `*.safetensors` only. Feeds a DIFFERENT dropdown
   (`inf-ckpt-dd`, `inference_tab.py:432`), currently 362 entries.
3. **LatCH heads — ONE dir.** `MEDIUM_HEAD_DIR.glob("latch_sa3_*_best.pt")` (line 306), 17 heads.

**Coverage against Kim's actual model locations (counted 2026-08-24):**

| root | dirs | `.ckpt` | `.pt` | `.safetensors` | visible in UI |
|---|---|---|---|---|---|
| `Mantu/sa3_lora_runs` | 162 | 302 | 79 | 60 | 362 (the `.pt` are skipped) |
| `Mantu/lumi_runs` | 8 | 400 | 0 | 0 | **none** |
| `<UUID 9a410a1d…>/lumi_runs` | 12 | 416 | 16 | 0 | **none** |
| `Mantu/sa3_control_runs` | 237 | 0 | 833 | 0 | **none** |

≈362 of ≈2106 model files reachable. Note the extension filter is a second, independent blocker:
**every control adapter is a `.pt`** (`riffer_final.pt` convention), so adding
`sa3_control_runs` as a root is not enough on its own — the scanner must accept `.pt` and
classify by shape (§2's four families), not by extension.

### LatCH PANEL REQUIREMENTS — ✅ SHIPPED 2026-08-26 (C). Original ask + evidence below.

**What landed** (plan `docs/superpowers/plans/2026-08-24-inference-ui-batch-sweep-and-head-metadata.md`,
Tasks 1-3; nothing committed — working tree only):

| Kim asked for | shipped as |
|---|---|
| dynamic range meter showing the dataset range | `eval/head_meta.py:slider_bounds` → per-head `slider_min/max/value_default` = `std_mean ± 2σ` in RAW units; the meter line under each slot reads `dataset -21.93 ± 14.53 dB · slider = mean ± 2σ · [-50.99, 7.141]`. The numeric `step` is derived from the range too (0.1 was three usable positions on `beat_activation`). |
| hover help for the loss curves | the `loss` label carries the head's TRAINED loss and what overriding means; the box is pre-filled with `loss_type` instead of blank. |
| disable them for heads which don't use them | `supports_scalar_target` (False when `out_channels > 1`) gates the **value AND target-kind** controls; `supports_loss_select` (False when `loss_type == "cosine"`) gates the loss dropdown. Verified live: `same_chroma` → all three disabled, `hpcp` → value+kind disabled, loss live, `rms_energy_bass` → all live. |
| suggested values + hover help for the advanced params | ρ/μ/γ/n_iter labels carry `_RHO_HELP` … `_NITER_HELP` in `controls.py`, each stating the **normalised** scale (`rho = mu = slot-1 gain`, per-slot `weight = slot_gain / slot-1 gain`) with concrete move-by-factors-of-2 advice. A test pins the wording so it can never drift into a raw-weight claim. |

**Two things shipped beyond the ask, both the same class of defect:**
- **Health badge.** `spectral_kurtosis` is flagged `⚠ undertrained` (orange) with the hover sentence
  *"trained only 3 epochs (others reached 20) and dataset sigma is 521.557"*; `hpcp` carries
  `readout: unrecorded` because `train_latch.py` never saved which chroma readout it was fit
  against. It does now (`target_source/chroma_dir/chroma_key/db_path` added to the save dict) —
  so the gap is closed forward, not backward.
- **The empty-picker KNOWN BUG below is FIXED.** All four pickers (3 LatCH heads + DoRA + ckpt)
  moved off `Input(<id>, "id")` onto a shared 5 s `dcc.Interval`. Verified by killing :8056,
  restarting the viewer, then restarting :8056: the head picker went 0 → 16 options **in the same
  browser session, no page reload**, and the placeholder said *"render server :8056 unreachable —
  retrying every 5 s"* while it was down.

**Also shipped 2026-08-26: named presets (plan Task 4-5).** `eval/presets.py` + `GET/POST
/presets` on :8056 + a Preset row (dropdown · Load · name box · Save) at the top of the inference
tab. A preset is the `/generate` payload under a name, **minus `seed`/`batch_size`** so it stays a
recipe. It also stores a `form` snapshot of the viewer's own controls, because `build_payload()`
merges the base prompt with the variation, resolves dist-shift and collapses 35 steering states into
three blocks — inverting that would be a second source of truth. Restoring the form and re-running
the same builder gives the same payload by construction; measured: **63/63 non-volatile fields
restored, rebuilt payload identical to the stored one**. Load is deliberately TWO callbacks: setting
a slot's head fires `_autofill_defaults`, which writes that slot's gain/kind/value from the head's
checkpoint defaults, so the preset's per-slot numbers are applied by a second callback that is
triggered by the slot meter — an Output of the first — and therefore cannot run too early.
`mir/tests/explorer_sa3/test_preset_form_partition.py` pins that split.

**Also shipped 2026-08-26: root selector + model-info panel (model-db plan, Task 8).** The
checkpoint picker was pinned to one root, which is why the 14 LUMI-trained families were reachable
only by typing a path (gap #1 in the ranked list below). The inference tab now has a **multi-select
`roots` dropdown** fed from `/roots` — each entry labelled with its live model count and marked
`— DRIVE NOT MOUNTED` when its removable drive is absent — and the ckpt picker rescopes to the
selected roots. Option labels now carry `family · corpus · rank · epoch` instead of a bare path, and
selecting one fills a **model-info panel** under the picker with the three-audience content the
eval-tables spec §14 asks for: what the model is (family/corpus/rank/epoch/resident cost), the
reproducible recipe, the plain-language *why*, the verdict and Kim's own feedback where the sidecars
carry them, a `file://` link to `run_meta.json`, and the provenance of each field.

**Findings from doing it — both need Kim:**
1. **The Mantu eval drive is NOT MOUNTED right now** (`/run/media/kim/` holds only the UUID drive
   and Lehto). Consequences seen live: `/ckpts` 404s, `chroma_other` is skipped at boot, and the
   DoRA picker offers **692 of 797 adapters that cannot load**. The picker now marks those
   `— drive offline`, disables them and sorts them last, and the ckpt status line reports the real
   cause instead of "server down?". Re-check `chroma_other` once the drive is back: its absence is
   **not** established, only unobservable while unmounted.
2. **`/info` returns 16 heads, not 17.** The 17th (`chroma_other`) lives at a `Mantu1` literal in
   `chroma_morph_transitions.py:46`; the server now re-roots it onto the live mount and logs a
   named SKIP when it is absent, rather than registering a head that can never load.

---

### ORIGINAL ASK (kept for the evidence table) — feasibility already checked

Kim's ask, verbatim: *"The LATCH value field should have a dynamic range meter which shows the
dataset range for the chosen parameter, as well as a hover help for the loss curves, and disable
them for heads which don't use them. Show also suggested values for the advanced LATCH parameters
and a hover help for what they are and how to pick functional values."*

**All of it is buildable from data we already have** — every head checkpoint carries its own
training statistics. Probed 2026-08-24 (`torch.load` of all 16 files in
`stable-audio-3/latch_weights_sa3_medium`; note `/info` reports 17 heads, so ONE head comes from
somewhere else and must be located): top-level keys are `feature_name, out_channels, loss_type,
standardized, std_mean, std_std, noise_schedule, optimizer, t_injection, in_channels, precision,
seed, epoch, avg_loss` + `state_dict`.

| head | out | loss | std? | dataset mean | dataset std | ep |
|---|---|---|---|---|---|---|
| beat_activation | 1 | smooth_l1 | True | 0.0439 | 0.0656 | 20 |
| downbeat_activation | 1 | smooth_l1 | True | 0.0109 | 0.0253 | 20 |
| hardness | 1 | mse | True | 66.19 | 3.488 | 20 |
| hpcp | 12 | smooth_l1 | True | 0.243 | 0.271 | 20 |
| onset_envelope | 1 | smooth_l1 | True | 1.324 | 0.549 | 20 |
| onset_envelope_drums | 1 | smooth_l1 | True | 1.444 | 1.130 | 20 |
| rms_drums | 1 | smooth_l1 | True | -31.44 | 18.21 | 20 |
| rms_energy_air | 1 | smooth_l1 | True | -32.96 | 26.15 | 20 |
| rms_energy_bass | 1 | smooth_l1 | True | -21.93 | 14.53 | 18 |
| rms_energy_body | 1 | smooth_l1 | True | -24.82 | 35.39 | 20 |
| rms_energy_mid | 1 | smooth_l1 | True | -28.46 | 22.57 | 18 |
| **same_chroma** | **384** | **cosine** | **False** | 0 | 1 | 20 |
| spectral_flatness | 1 | smooth_l1 | True | 0.2253 | 0.1297 | 19 |
| spectral_flux | 1 | smooth_l1 | True | 67.04 | 37.13 | 20 |
| **spectral_kurtosis** | 1 | smooth_l1 | True | 15.72 | **521.6** | **3** |
| spectral_skewness | 1 | smooth_l1 | True | 2.222 | 2.122 | 20 |

What this table settles for the implementer:

- **The range meter is `std_mean ± kσ` from the checkpoint**, per head, in the feature's own units.
  No new dataset pass is needed.
- **The current slider is one-size-fits-all and wrong for most heads.** `/info` hands the UI
  `slider_min -80 / slider_max 20 / value_default -30` — sane for the dB-valued `rms_*` family
  (mean ≈ -31, σ ≈ 18) and meaningless for `beat_activation` (0.044 ± 0.066), `hpcp` (0.24 ± 0.27),
  `hardness` (66.2 ± 3.5) or `spectral_flux` (67 ± 37). Derive the slider bounds from the head's own
  statistics instead of a shared default.
- **"Disable for heads that don't use them" has two concrete cases.** `same_chroma` is 384-ch,
  `cosine`, `standardized: False` — a scalar target value and the loss dropdown are both meaningless
  for it (it wants a 384-d chroma target). `hardness` was trained with `mse`, everything else with
  `smooth_l1` — the loss selector should default to, and warn when departing from, the head's own
  `loss_type`.
- **Surface `epoch` / `avg_loss` as a health flag.** `spectral_kurtosis` stopped at epoch 3 with
  σ = 521.6; a user should be told that head is undertrained rather than discovering it by ear.
- Advanced params `rho / mu / gamma / n_iter` (`controls.py:116-125`; defaults `rho=None`,
  `mu=None`, `gamma=0.3`, `n_iter=4`) need suggested values + hover help. Remember `resolve_latch()`
  NORMALISES: `rho = mu = first slot's gain`, per-slot `weight = slot_gain / g0` — so any suggested
  value must be expressed in the server's normalised scale, not a raw weight.

### NEEDS BUILDING — ranked by what it unblocks

1. ~~**Checkpoint reach.**~~ **DONE 2026-08-26 (C)** — multi-select `roots` dropdown in the inference tab fed from `/roots` (live counts, `— DRIVE NOT MOUNTED` marker), ckpt labels carrying family/corpus/rank/epoch, and a model-info panel on select. Original wording: `/ckpts` accepts a `root` param and `render_client.ckpts()` forwards it,
   but **no GUI control sets it** — the picker is pinned to `sa3_lora_runs` (162 older local DoRA
   runs). The 14 LUMI-trained families on the UUID drive (`lumi_runs/runs`: dorlor_ab's 32 arms,
   lr5e5_allsets, fullft_avp_subloss, subloss_k24, winning_fleet, …) are reachable only by typing a
   path. **A root selector / multi-root scan is the smallest change with the biggest effect on
   "experiment with what we have".**
2. **Contour/morph control (Head-B) is absent from the server** — `control_mode=melody_contour`
   arms (`morphcond`, `morph_head_sweep`, `riffer_*.pt`). Needs a control-adapter install path, a
   contour-stream input (sidecar or drawn), and vocab matching against `args["melody_vocab"]`.
3. **Pianoroll / `mir_ctrl` (note matrix) is absent** — enters via `modular_local_embeds`; needs
   the conditioning inlet extended. Same blocker that made D14 drop its pianoroll arm.
4. ~~**No batch / sweep surface.**~~ **DONE 2026-08-26 (C)** — `eval/sweep_spec.py` (axis grammar,
   cross-product, resume-safe `cell_id`) + `eval/sweep_run.py` (resumable CLI, a thin client of
   :8056 — it POSTs the same payload the GUI posts and never builds a guidance config, exactly as
   the original wording below demanded) + `eval/sweep_run.py --models id1,id2` (one preset across
   models from the model DB, failing loudly on an unresolved id before any render) +
   `eval/build_sweep_page.py` (three-audience results page reusing the shared same-playhead player).
   The per-render sidecar the wording asks for is `manifest.jsonl`: one fsynced line per cell holding
   the payload VERBATIM, so the page can be rebuilt even after the preset is edited. Original
   wording: No batch / sweep surface. A GUI is the wrong shape for "sweep one axis with everything else
   pinned", and there is no replayable per-render sidecar. Correct form: a thin CLI **client of
   `/generate`**, never a second guidance implementation (gains are normalised server-side).
4b. **A/B slots — NEW 2026-08-26 (C).** `eval/adapter_slots.py` + `GET/POST /slots` + `POST /ab` + an "A/B slots" panel in the inference tab. Several adapters resident on one base; switching costs milliseconds where the ckpt picker costs a multi-GB reload. Measured: 0.40 GB per r128 adapter (not the 0.33 the plan estimated), 7.40 GB free with medium-base resident, so ~3 adapters fit above the 6.0 GB floor. `null` is the control arm. The server refuses an over-budget or non-adapter set with a reason instead of OOMing.

5. **`LATCH_SLOTS = 3`** is a UI cap only — trivial to raise, but >3 slots wants a rethink of the
   panel layout.
6. **Two checkpoint naming conventions** — a scanner keyed on `epoch=*.ckpt` never sees the
   `riffer_*.pt` control runs.
6b. ~~**Continuation does not auto-recover the source clip's adapter.**~~ **DONE 2026-08-26 (C)** — `eval/continuation.py` recovers ckpt/dora from the prefix's `result.json` or `.mmline.json`; a request that says nothing inherits it, one that disagrees is obeyed but warned about by name. `/longform`'s t2a path also saves z0 now, so its own output is continuable. **Closed the same session (Kim approved the fork edit):** `latents_sink` in `model.py:generate()` / `sampling.py:sample_diffusion()` captures z0 without touching the audio path (byte-identical on both sampling branches, same-seed A/B), `/generate` writes `out_NN.z0.npy`, and every response carries a top-level `latents` list. The a2a paths save none ON PURPOSE — their output is a crossfade of separately sampled windows, so no single z0 produced it; `meta.z0_reason` says so. Original wording: `/longform
   init_latent_path` continues the LATENT but the caller must re-specify ckpt + strength by hand;
   the original clip's `.mmline.json` records label/tag/ckpt/strength, so wiring that recovery is
   the obvious next increment (G, 2026-08-23 — deliberately deferred as a one-off at the time).
   Until then a continuation can silently be rendered by a DIFFERENT model than its own prefix.
7. ~~**Head metadata is not surfaced.**~~ **DONE 2026-08-26 (C)** — `eval/head_meta.py` + the panel rework; see the shipped table above. Original wording: Picking `same_chroma` (384-ch, cosine, unstandardised) versus
   a 1-ch scalar head changes what a target even means; the head's own metadata carries
   out_channels / loss_type / target_kind_default and the UI does not show it.

#### PIANOROLL / CONTOUR CHECKPOINT INVENTORY (probe run 2026-08-26, C)

Task 0 of `docs/superpowers/plans/2026-08-24-inference-ui-pianoroll-and-contour.md`. All four steps
pass — the plan is GO — with two corrections to it.

**Contour (Head-B, `control_mode: melody_contour`) — 32 checkpoints, all on the UUID drive.**
Scanned 865 `.pt` files across `sa3_control_runs`, `lumi_runs` (both drives) WITHOUT `torch.load`,
by reading only each zip's `data.pkl` member (the `Misc/ckpt_probe.py` trick — a few KB per file
instead of hundreds of MB; on a spinning USB drive that is minutes instead of hours).

| run | vocab | `args["melody_vocab"]` | control_dim |
|---|---|---|---|
| `runs/headb_melody/` (terminal + 15 step ckpts) | **9** | **absent** | 768 |
| `morphcond/morph_L2_{base,ft}_s1` | 5 | 5 | 768 |
| `morphcond/morph_IOI3_{base,ft}_s1..s4` | 15 | 15 | 768 |
| `morphcond/morph_L3_{base,ft}_s{1,2}` | 15 | 15 | 768 |
| `morphcond/morph_L4_{base,ft}_s1` | 77 | 77 | 768 |

⚠ **`headb_melody` does not record `melody_vocab` in its args** — its vocab (9) is recoverable ONLY
from `state["conditioner.embed.weight"].shape[0]`. Task 3's loader must therefore treat the args key
as optional and fall back to the embedding shape; matching on `args["melody_vocab"]` alone would
silently reject the one checkpoint the plan names as its primary target.

**Pianoroll (`mir_ctrl`) — ALREADY LOCAL.** The plan assumed this arm was still on LUMI `$SCRATCH`
and budgeted an rsync. It is not: `<UUID>/lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s{1,2}`,
terminal `epoch=31-step=2688.ckpt`, **12.9 GB each and FAT** (resumable), with `run_meta.json`,
`report.{json,md}` and `control_ablation.jsonl`. **No pull needed, no KIM-TASKLIST item.**

Does the DiT actually read the roll? From `control_ablation.jsonl`, control gain = loss(ablated) −
loss(true), settling over the last five probes:

| seed | vs SHUFFLED roll | vs ZERO roll | monotone positive after step 800 |
|---|---|---|---|
| s1 | **+0.0068** | +0.0018 | yes |
| s2 | **+0.0112** | +0.0051 | yes |

Both seeds agree in sign and shape, and a WRONG roll hurts more than NO roll — which is what
genuine conditioning looks like. **But this is a training-loss signal, not proof the control is
strong enough to steer melody audibly.** Task 7's smoke render is what settles that, and it is the
first thing to run before building UI on top.

**The modular inlet installs — with a corrected accessor.** The plan's `dw, tf = m.model,
m.model.model` is wrong by one level: `m.model.model` is a `DiTWrapper` with no `.dim`, so
`install_mir_control` dies with `AttributeError: 'DiTWrapper' object has no attribute 'dim'`. The
real chain is `StableAudioModel → ConditionedDiffusionModelWrapper → DiTWrapper →
DiffusionTransformer → ContinuousTransformer`. Use:

```python
dw, tf = m.model, m.model.model.model.transformer
install_mir_control(dw, tf, n_channels=128, cond_id="mir_ctrl")
# -> cond_ids: ['mir_ctrl']; 12 of 24 blocks (12..23, the blocks="12-23" default);
#    30,707,712 new trainable params; tf.dim == 1536
```

**`contour_streams` imports cleanly** from `SAO/.venv` with `/home/kim/Projects/mir` on the path —
no vendoring, skip the `contour_alphabet.py` copy the plan permits.

**Environment trap found while probing** (full write-up in `MASTER.md` §5): a cloned torchcodec
SOURCE repo at `SAO/torchcodec` has no top-level `__init__.py`, so whenever the SAO repo root is the
cwd it becomes an implicit namespace package named `torchcodec`. `importlib.metadata.version(...)`
then raises, and transformers reports it as `Could not import module 'T5GemmaEncoderModel'` — which
names the wrong thing entirely and breaks every `StableAudioModel.from_pretrained`. It bites
`python -c` / heredoc runs from `SAO/` and NOT scripts (whose `sys.path[0]` is the script's own
directory), which is why the render server has never hit it. Run probe snippets from another cwd.

