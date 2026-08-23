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
| **Viewer** | `mir` branch `sa3-latent-explorer`, `plots/explorer_sa3/app.py` | 8051 · mir venv | Dash GUI. Tabs `inference_tab` · `a2a_tab` · `bend_tab`; `render_client.py` = client, `controls.py` = shared steering panel |
| **Latent player** | `mir/scripts/latent_server_sa3.py` (+ `latent_server_onnx.py`, low-VRAM) | 7892 · SA3 venv | **CROPS ONLY** — `/decode /mix /steer`. NOT the inference path. `/steer` = one head, one gradient step, gain only |
| **Render server** | `SAO/eval/explorer_render_server.py` | 8056 · `SAO/.venv` | **THE generation path.** `medium-base` resident on GPU |

**Render-server endpoints:** `/generate` · `/a2a_track` · `/a2a_mix` · `/longform` · `/decode` ·
`/bend` · `/schedule` · `/ckpts` · `/info` · `/status` · `/audio/{job}/{file}`.

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

**Bend** (`bend_tab` → `/bend`): track/crop pickers, latent path, seed.

**Shared steering panel** (inference + a2a): **3 LatCH slots** × (head · kind · value · gain ·
start · end · loss · w_sec) · **FiLM** (enable/value/gain) · **DoRA** (dropdown/strength/imin/imax) ·
advanced hparams rho · mu · gamma · n_iter. `steering_payload()` consumes 35 values.

**Latent player** (`:7892`): `/decode` · `/mix` (slerp) · `/steer` (single-head gradient nudge) ·
`/crops` · `/meta` · `/source`. Low-VRAM ONNX twin at `:7893`.

**Plumbing**: resident model, GPU lock, job log ring, `/audio` serving, `/schedule`, cached
checkpoint journal, `/info` + `/status`.

### NEEDS BUILDING — ranked by what it unblocks

1. **Checkpoint reach.** `/ckpts` accepts a `root` param and `render_client.ckpts()` forwards it,
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
4. **No batch / sweep surface.** A GUI is the wrong shape for "sweep one axis with everything else
   pinned", and there is no replayable per-render sidecar. Correct form: a thin CLI **client of
   `/generate`**, never a second guidance implementation (gains are normalised server-side).
5. **`LATCH_SLOTS = 3`** is a UI cap only — trivial to raise, but >3 slots wants a rethink of the
   panel layout.
6. **Two checkpoint naming conventions** — a scanner keyed on `epoch=*.ckpt` never sees the
   `riffer_*.pt` control runs.
7. **Head metadata is not surfaced.** Picking `same_chroma` (384-ch, cosine, unstandardised) versus
   a 1-ch scalar head changes what a target even means; the head's own metadata carries
   out_channels / loss_type / target_kind_default and the UI does not show it.
