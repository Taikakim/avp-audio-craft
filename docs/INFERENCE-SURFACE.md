# Inference surface — what is callable, with what, producing what

**Audience: whoever builds a UI over this** (Kim 2026-08-23: *"document the code well, I will then
create a UI with Claude design"*). This is a CAPABILITY MAP, not a tutorial: every generation entry
point, every kind of model that can be loaded, every knob that actually changes the output, the
file conventions in and out, and the traps that produce plausible-but-wrong results.

Companion to F's relay of Kim's standing ask — that inference tooling should incorporate everything
we have trained rather than living in bespoke scripts. **That fragmentation is real and this document
describes it honestly rather than pretending a unified API exists.** Where two scripts do the same
thing differently, that is called out; a UI has to dispatch on those differences today.

Scope note: entries below were read from the code on 2026-08-23. Anything I did not verify is
marked ⚠️ UNVERIFIED rather than asserted.

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

⚠️ **These do not all compose.** `SDEditReanchor` builds its own conditioning dict (inpaint mask +
masked input only), so the **pianoroll / `mir_ctrl` path — which enters via `modular_local_embeds`
— is NOT carried through a2a**. D14 had to drop that arm for exactly this reason: it would have run
unconditioned while looking like a working arm. Closing this is the single highest-value item for
the unification Kim asked for.

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

## 8. Known fragmentation — the honest list

For the unification ask, these are the seams a UI would otherwise have to encode itself:

- **Four different checkpoint loaders** (base / adapter / full-FT / control adapter), dispatched on
  checkpoint shape rather than on any declared type.
- **Two checkpoint naming conventions** (`epoch=…ckpt`, `riffer_*.pt`).
- **Conditioning inlets are not unified**: cross-attn text, global cond (`prepend`|`adaLN`),
  `local_add_cond` (257-ch), the native prepend path, and control-context tokens each have their own
  call shape — and only some survive into the a2a/longform samplers.
- **Every renderer re-implements its own output naming and manifest.**

**A single conditioning inlet — one path that carries all of the above so a sampler call need not
know which head it serves — is the prerequisite for a unified renderer.** Every bespoke script above
exists because that layer is missing.
