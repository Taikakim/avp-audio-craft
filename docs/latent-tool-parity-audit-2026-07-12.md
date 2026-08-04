# Latent/inference tool parity audit — 2026-07-12

Read-only audit (no code changes, no GPU). Compares the three UIs against each other and
against what the inference code can already do, for Kim's asks: LatCH hyperparameter
exposure, prompt sequences, crossfade-failure experimental tools, latent data-bending.

**The three tools:**

- **A — SA3 latent explorer** (mir repo, branch `sa3-latent-explorer`, currently checked out).
  Dash viewer `/home/kim/Projects/mir/plots/explorer_sa3/` (5 tabs; ~85 components on the
  Inference tab) + torch player `mir/scripts/latent_server_sa3.py` (:7892, config
  `mir/latent_player_sa3.ini`) / ONNX player `mir/scripts/latent_server_onnx.py` (:7893)
  + model-resident render server `SAO/eval/explorer_render_server.py` (:8056, FastAPI,
  medium-base, endpoints `/generate /a2a_track /a2a_mix /decode /ckpts /schedule /info /status`).
  Design brief: `mir/plots/explorer_sa3/UI_BRIEF.md`, README same dir.
- **B — official Gradio UI**: `SAO/stable-audio-3/run_gradio.py` +
  `SAO/stable-audio-3/stable_audio_3/interface/diffusion_cond.py` (910 lines, one Generation tab).
- **C — Kim's bracketing fork**: branch **`avp/Gradio_Lab`** of
  `SAO/stable-audio-tools` (remote `avp`; merge `a4a89d1`). +2032 lines on
  `stable_audio_tools/interface/gradio.py`, +247 on `interface/interfaces/diffusion_cond.py`.
  **Pre-SA3** (Stability-AI stable-audio-tools era, ~4 months stale); parked un-merged —
  see WORKLOG 2026-06-22 ("needs a manual reconciliation + GUI launch-test").

---

## 1. Feature matrix (A = explorer, B = official Gradio, C = Gradio_Lab fork)

File refs: `inference_tab.py`/`a2a_tab.py`/`controls.py` = `mir/plots/explorer_sa3/`;
`server` = `SAO/eval/explorer_render_server.py`; `dc.py` = `stable_audio_3/interface/diffusion_cond.py`;
`gL` = `stable_audio_tools/interface/gradio.py` @ `avp/Gradio_Lab` (line refs omitted — branch not checked out).

| Feature | A explorer | B official | C Gradio_Lab |
|---|---|---|---|
| Text-to-audio prompt + negative prompt | **yes** (`inference_tab.py:61,72`) | **yes** (`dc.py:461-462`) | **yes** (gL prompt/negative_prompt) |
| Second "variation" prompt field | **yes** (`inference_tab.py:67`) | no | no |
| LLM prompt assistant (Qwen reprompt) | no | **yes** (`dc.py:463,805-824`) | no |
| Duration / steps / CFG / seed | **yes** (`inference_tab.py:92-100`) | **yes** (`dc.py:473-485,503`) | **yes** (+ seconds_start) |
| Batch size | **yes** 1–4 (`inference_tab.py:102`) | **partial** — hidden `gr.State(1)`, no control (`dc.py:597`) | **yes** 1–8 slider |
| CFG interval (min/max) | **yes** — draggable range on live sigma chart (`inference_tab.py:133-146`, server `/schedule` :560) | **yes** sliders (`dc.py:505-506`) | **yes** + pre-render visualization (`create_cfg_interval_visualization`) |
| CFG rescale / CFG norm threshold | no (server doesn't accept either) | **yes** (`dc.py:509-510`) | **yes** (cfg_rescale, bracketable) |
| APG scale | **yes** (`inference_tab.py:105`) | **yes** (`dc.py:511`) | no (pre-APG) |
| Sampler type selection | **no** (server accepts `sampler_type`, UI never sends it; `server:689`) | **yes** (`dc.py:516-531`) | **yes** — multi-sampler CHECKBOXES (bracket axis) |
| Sigma max | no | **yes** (`dc.py:532`) | **yes** (bracketable list) |
| Dist-shift / schedule shaping | **partial** — single float = constant-α Flux (`inference_tab.py:113`, `server:160`) | **yes** — full LogSNR/Flux/Full param rows (`dc.py:549-594`) | **partial** (rho slider, k-diffusion era) |
| Sigma-schedule chart | **yes, live** Plotly, pre-render (`inference_tab.py:139`) | **partial** — post-render matplotlib image incl. LatCH∩CFG bands (`dc.py:52-123,663`) | **yes**, pre-render |
| Init audio / a2a | **yes** — path-based + full-track windowed >MAX with crossfade join (`inference_tab.py:119-126`, `server:787-849`) | **yes** — upload widget (`dc.py:612-624`) | **yes** — upload |
| Noise-level LADDER (multi-nl in one job) | **yes** (`inference_tab.py:126`, `server:792`) | no | no (bracket axes don't include nl) |
| RF-Inversion mode (steps/gamma/unconditional) | no | **yes** (`dc.py:618-636`) | no |
| Inpainting (mask start/end) | **partial** — only inside `/a2a_mix` `mode=inpaint` + seam strips; no general inpaint UI (`server:1089-1142`) | **yes** (`dc.py:638-652`) | **yes** |
| Continuation (inpaint past source end) | no | **partial** (mask end > source length; CLI-documented) | **partial** (same mechanism) |
| Send-output-to-init / to-inpaint loop | **partial** (history list; re-render from result path) | **yes** buttons (`dc.py:790-794`) | partial |
| Two-track DJ transition (beatmatch, bungee tempo ramp, downbeat snap, bar quantize, slerp window, sinesweep/refine/inpaint modes, seam-inpaint, pure-basis splice, chroma-morph guidance, whole-track pass) | **YES — unique** (`a2a_tab.py`, `server:857-1263`) | no | no |
| Latent dataset browse / decode / A-B source compare | **yes** (viewer/dataset tabs; player `/decode /source`, `latent_server_sa3.py:43-73`) | no | no |
| Latent interpolation (slerp/lerp two crops) | **yes** (player `/mix`, `latent_server_sa3.py:87-99`) | no | no |
| Offline LatCH gradient nudge on an existing latent | **yes** (player `/steer`, `latent_server_sa3.py:130-147`) | no | no |
| LatCH guidance during generation | **yes** — 3 slots: head/kind/value/gain/start/end (`controls.py:16,31-53`) | **yes** — 2 slots + kind/target/weight/start/end (`dc.py:654-732`) | no |
| LatCH ρ/μ/γ/n_iter exposed | **no** — server ties ρ=μ=slot-1 gain, γ/n_iter accepted but UI never sends (`server:448-451`, `controls.py:105-141`) | **yes** — ρ, μ, γ, n_iter, log_norms sliders (`dc.py:658-662`) | no |
| LatCH loss_type / scalar_pooled / chroma_rung / w_sec | **no** (server `resolve_latch` drops them, `server:440-444`) | **no** (not in the accordion; code supports it, `model.py:515`) | no |
| Per-head metadata-driven slider ranges | **partial** — default gain/kind/value autofill from `/info` (`controls.py:158-173`) | **yes** — slider min/max/mean from ckpt metadata (`dc.py:689-732`) | no |
| Head dir correctness | **yes** — production `latch_weights_sa3_medium` (`server:70`) | **⚠ wrong dir** — `LATCH_DIR = latch_weights_sa3` = old epoch-snapshot family, NOT the production `_medium` heads (`dc.py:26`) | n/a |
| FiLM density control adapter | **yes** — enable/value/gain (`controls.py:62-72`, `server:398-410`) | no | no |
| DoRA/LoRA at runtime — registry + arbitrary ckpt | **yes** — dropdown over ~121-ckpt journal + free path + strength; hot reload (`inference_tab.py:78-86,399-401`, `server:72-77,175-184,353-395,518-557`) | **partial** — LoRAs fixed at launch (`--lora-ckpt-path`), per-LoRA strength/interval/layer-filter (`dc.py:487-498`) | **yes** — config+ckpt scan dropdowns, load/unload buttons |
| Per-LoRA step interval + layer filter | no | **yes** (`dc.py:495-497`) | no |
| Per-checkpoint provenance/journal info box | **yes** (UI_BRIEF §4; reads `run_meta.json` convention) | no | partial (params echo per output) |
| **DUAL-MODEL A/B comparison** (two resident models, active toggles) | no (one resident model) | no | **YES — unique** (`load_model_a/b`, `create_dual_model_interface`) |
| **Parameter BRACKETING** (comma lists: steps × cfg × cfg_rescale × σmin × σmax × samplers → grid, count display, per-output param dropdown, lazy generation) | **partial** — only the 1-axis noise ladder | no | **YES — unique** (`Bracketing Settings` accordion, `calculate_generation_count`, `generate_audio_lazy`) |
| Presets (save/load named settings) | no | no | **YES — unique** (`load_preset/save_preset`) |
| Weight-garden databending (DiT weight mutation) | **partial** — shuffle only: amount/target/seed/decay (`inference_tab.py:147-163`, `server:340-385`); code has drift/blur/contrast/tilt/life too (`stable-audio-3/scripts/weight_mutations.py:106-176`) — UI/server hardcode `op:"shuffle"` (`server:378`) | no | no |
| Rhythm-preserve selection steering (K candidates vs source envelope) | **yes — unique** (`inference_tab.py:168-181`, `server:711-757`) | no | no |
| Spectrogram preview / preview-every | no | **yes** (`dc.py:604,221-242`) | yes |
| Infinite radio / autoplay / auto-download / CarPlay keys | no | **yes** (`dc.py:607-609,834-898`) | no |
| Output format/naming (flac/mp3/aac, verbose names) | no (server saves normalized wav; `server:700`) | **yes** (`dc.py:602-603,371-388`) | **yes** + format-support detection, save-permanently |
| Same-playhead result players + render history | **yes** (UI_BRIEF §"result players") | no | no |
| Peak-normalize on save (clipping gotcha, MASTER §5) | **yes** (`save_audio(normalize=True)`, `server:700,842`) | **no** — clamp to [-1,1] (`dc.py:364`) | fixed in gL (the branch carries the fp16-clip fix) |

**Summary:** A ⊃ B in steering/adapters/a2a/library, but B exposes sampler internals
(sampler type, σmax, full dist-shift, cfg-rescale, RF-Inversion, inpaint UI, ρ/μ/γ/n_iter)
that A hides; C's unique value is entirely in **comparison machinery** (dual model, brackets,
presets, per-output param recall) and none of it has been ported to the SA3 era.

---

## 2. LatCH guidance — every parameter that exists in code (D)

Entry point a UI calls: **`StableAudioModel.generate(latch_configs=[...], latch_hparams={...})`**
(`stable_audio_3/model.py:109-110`, dispatch at `:322`, resolution at `:400-540`) — or over HTTP,
`POST /generate` with a `latch` list (`explorer_render_server.py:414-452`).

### Per-guide (`latch_configs` entries — `model.py:468-518`)
| key | meaning | values / notes |
|---|---|---|
| `model_path` | head ckpt | load via `load_latch_from_checkpoint` (auto-detects arch; NEVER hardcode dims — MASTER §5) |
| `kind` | synthetic target shape | `constant`, `ramp_up`, `ramp_down`, `beat_grid` (BPM impulse train) — `inference/latch_targets.py:13-48` |
| `value` | target value (or BPM for beat_grid) | head metadata gives slider min/max/mean (`dc.py:689-711`) |
| `target_raw` | **raw per-frame [C,T] target curve** — resampled to the latent grid + standardized | `model.py:477-488`; used internally by a2a_mix chroma-morph; NOT exposed to any UI payload |
| `weight` | per-guide gradient multiplier | server derives: `weight = slot_gain / slot1_gain` (`server:448-449`) |
| `start_pct` / `end_pct` | step-% window the guide is active | defaults 0.0 / 0.6 |
| `loss_type` | guidance loss (overrides head metadata) | `mse`, `bce_logits`, `smooth_l1`, `cosine`, **`scalar_pooled`** (W's 2026-07-10 buzz fix — mandatory for scalar heads), **`chroma_rung1` / `chroma_rung2`** (T2 phase-tolerant chroma) — `inference/latch_guided.py:34-69`; override seam at `model.py:515` |
| `huber_beta` | smooth_l1 beta | from head metadata |
| `w_sec` | chroma-rung tolerance window (≈ beats·60/bpm) | `latch_guided.py:57-64` |
| `fps` | latent frame rate for chroma losses | default 10.767 |

### Global (`latch_hparams` — `model.py:521-525`, sampler `latch_guided.py:72-189`)
| key | meaning | default | operating notes |
|---|---|---|---|
| `rho` (ρ) | variance-guidance strength on z_t (head at true t) | 1.0 | energy heads want **≈512** (MASTER §5; 48–96 is the old low estimate, 128 a dead zone) |
| `mu` (μ) | mean-guidance strength on clean estimate (head at t=0) | 1.0 | server ties ρ=μ=slot-1 gain |
| `gamma` (γ) | noise augmentation on clean-head eval | 0.3 | γ>0 ⇒ non-deterministic across identical seeds |
| `n_iter` | mean-guidance inner iterations | 4 | |
| `log_norms` | per-step grad-norm printout | False | B exposes; A doesn't |

### Single-guide sampler extras NOT reachable from `generate()` (verify-script path only)
`sample_flow_euler_latch_guided` (`latch_guided.py:211-302`): `window=(sigma_lo, sigma_hi)`
(sigma-domain gating instead of step-%), `normalize` (dimensionless unit-norm gain — gain
transfers across features), loss types `l1`/`huber`. Worth porting into the multi-guide path
if hyperparam exploration becomes a UI activity.

### Head registries
- Production: `stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt` (adaln_zero, standardized, depth 4).
- Server scan + per-head default gain/kind/value → `/info.latch_heads` (`server:259-298`); explorer autofills from it (`controls.py:158-173`).
- B's `LATCH_DIR` points at the *other* family (`latch_weights_sa3`, `dc.py:26`) — epoch snapshots, concat keys. Known trap (memory `sa3-latch-head-families`).

---

## 3. What's missing for Kim's asks

### 3a. LatCH hyperparameter exposure
- **Explorer (A)**: no ρ/μ decoupling, no γ, no n_iter, no loss_type, no w_sec, no
  σ-domain window, no `normalize`. Two cut points: the UI's 23-state steering contract
  (`controls.py:90-141`) never collects them, and the server's `resolve_latch`
  (`server:440-451`) drops `loss_type`/`w_sec` even if sent and hardwires ρ=μ=g0.
- **Consequence today**: scalar heads (hardness/depth/booming) can't run `scalar_pooled`
  from any UI → the "buzz" failure mode is un-navigable interactively; chroma_rung1/2
  (already wired into `_make_latch_criterion`) has no UI at all.
- **B** exposes ρ/μ/γ/n_iter but is on the wrong head dir and has no loss_type either.

### 3b. Prompt SEQUENCES / scheduling
- **No UI has it.** A has main+variation (2 fields), a2a dual prompts + whole-track prompt; that's it.
- Already built, CLI-only:
  - `control/sa3_control/steered_longform.py` — **`--prompt '0:A|t:B'` arc schedule** with
    per-transition `--xfade-sec`, plus `--chroma` progression + `--chroma-head/--chroma-rho`
    (windowed longform, the proven path per DISCOVERIES §"Long-form").
  - `eval/breathing_v2_blockbuild.py` — measure-aligned prompt arcs from
    `eval/prompts_arc_v2_blockbuild.json` (shared-spine block prompts, per-layer staggered
    LoRA strength staircase).
  - Longform-quality companions ready to ride along: `inference/incantation_mask.py`
    (bar time-varying prompt from clamped history) and `inference/rope_jitter.py`
    (loop-attractor mitigation).
- Missing: a `/longform` (or `/prompt_arc`) endpoint on the render server + a schedule
  editor in the explorer. The server currently has no longform op at all.

### 3c. Crossfade-failure experimental tools
- Covered already by `/a2a_mix`: 3 modes (sinesweep graded-clamp / refine / inpaint),
  seam-inpaint strips, pure-basis splice, chroma-morph guidance, tempo ramp/follow,
  bar-quantize on/off, fine-align.
- Not surfaced: slerp-vs-lerp interp choice (lerp exists in `mir/scripts/latent_crossfader.py:76-84`
  and the player `/mix` takes `interp=`, but a2a_mix hardcodes slerp `server:1057`);
  the transition_lab v1/v2/v3 arms as selectable constructions (`eval/transition_lab.py`);
  the on-manifold bridge experiments (`onnx/beat_bridge.py`, `onnx/bridge_crossfade.py`);
  eps-seed control for the graded clamps (hardcoded 4242/2424, `server:1100,1207`);
  longform SDEdit crossfade (`inference/longform.py`) as a UI op.

### 3d. Latent data-bending — **does not exist anywhere**
- Searched mir + SAO: no channel-swap / noise / quantize / bitcrush / reverse / smear
  utility operating on `(1,256,T)` latents. All existing "databending" is **weight**-space
  (`stable-audio-3/scripts/weight_mutations.py` — drift/shuffle/blur/contrast/tilt/life,
  with decay profiles; UI+server expose only `shuffle`).
- Nearest latent primitives to build on: player `/mix` (slerp/lerp) + `/steer` (gradient
  nudge) in `latent_server_sa3.py`; `latent_crossfader.py` slerp/lerp/reality-anchor;
  chunked decode paths in both the player and `server:_decode_impl` (`server:1267-1304`);
  analysis priors in `mir/stats/latent_noise_fragility.csv` + `latent_dim_feature_xcorr.csv`
  (which dims are fragile/feature-correlated — a natural op-targeting map).

---

## 4. Build plan sketch

Ordered by leverage; every item lands in an existing file. The explorer (A) is the build
target — Kim's daily tool, already talking to the model-resident server. B gets at most a
head-dir fix; C's ideas port as features, not as a merge (the branch is pre-SA3;
reconciliation was already judged a manual job, WORKLOG 2026-06-22).

1. **LatCH hyperparams end-to-end** (small, ½ day)
   - `eval/explorer_render_server.py::resolve_latch` (:414-452): pass through per-slot
     `loss_type`, `w_sec`; accept top-level `rho`,`mu` (fall back to today's ρ=μ=g0), keep
     `gamma`/`n_iter` (already read :451).
   - `mir/plots/explorer_sa3/controls.py`: add per-slot loss-type dropdown
     (auto-default `scalar_pooled` for out_dim==1 heads via `/info` metadata) + w_sec input;
     one "advanced" row: ρ, μ, γ, n_iter. This grows the frozen 23-state contract —
     append-only at the end of `steering_states` to keep existing indices valid, bump the
     length check in `steering_payload` (`controls.py:107`).
   - Optional B fix while there: `dc.py:26` LATCH_DIR → `latch_weights_sa3_medium`.

2. **Prompt-sequence (arc) rendering** (medium, 1–2 days)
   - Server: new `POST /longform` in `explorer_render_server.py`, wrapping the
     `steered_longform.py` window loop (or `inference/longform.py` generators) with the
     existing dora/film/latch resolution; payload = `[{t_sec, prompt}, ...]` +
     window/overlap/xfade + optional incantation-mask + rope-jitter flags.
   - UI: `inference_tab.py` — a small schedule editor (textarea, one `t: prompt` per line,
     same grammar as `steered_longform._parse_prompt_arc` so CLI/UI stay interchangeable)
     + the op switch that already picks generate/a2a_track (`inference_tab.py:405-430`).

3. **Latent bend module + Latent-lab tab** (medium, 1–2 days)
   - New `SAO/eval/latent_bend.py` (or `control/sa3_control/`): pure tensor ops on
     `(1,256,T)` — channel swap/permute (seeded), per-dim/per-band noise, quantize/bitcrush,
     time reverse/stutter/smear (blur along T), dim zeroing, xcorr-targeted ops keyed off
     `latent_dim_feature_xcorr.csv`. Mirror `weight_mutations.py`'s spec format
     (`{"op":..., "amount":...}` list) so the two benders read the same.
   - Server: extend `_decode_impl` (`server:1267`) with an optional `bend: [...]` op list
     (decode-after-bend); same hook into `/a2a_mix`'s composite z before the mode pass
     (`server:1058`) for bent transitions.
   - UI: new "Latent lab" tab (crop picker reused from a2a tab) or a bend section on the
     Viewer tab; ops stack + decode/play via the existing result-player component.
   - Cheap variant to start: add the op list to the torch **player** (`latent_server_sa3.py::_decode_latent`)
     — no render server needed, works with the low-VRAM ONNX player pattern too.

4. **Weight garden: expose the other five ops** (tiny, hours)
   - `server:resolve_mutate/prepare_model` (:340-385): accept `op` (default shuffle) —
     `apply_condition` already dispatches drift/blur/contrast/tilt/life.
   - `inference_tab.py:147-163`: op dropdown next to amount.

5. **Bracketing + presets (the Gradio_Lab port, as explorer features)** (medium, 1–2 days)
   - Generalize the noise-ladder pattern (`inference_tab.py:126`, `server:792`): accept
     comma-lists for cfg/steps/seed/latch-gain client-side, fan out to N queued `/generate`
     calls, tag results with their param combo (the server already echoes `params_echo`,
     `server:466`), render as a labeled same-playhead grid. Dual-MODEL compare is already
     ~free: the DoRA/ckpt picker hot-swaps adapters per render (base-vs-ckpt A/B in one
     ladder); true two-resident-model compare doesn't fit 16 GB with medium and should not
     be ported.
   - Presets: JSON blob of the full payload, saved server-side next to `OUT_DIR`; load =
     re-fill the form (Dash `Store` + one callback).

6. **Crossfade-failure lab knobs** (small, ½–1 day)
   - `a2a_tab.py` + `server:_a2a_mix_impl`: interp dropdown (slerp/lerp), eps-seed inputs
     for the graded clamps (:1100, :1207), and a "construction" selector exposing the
     transition_lab arms (v1 hard-cut inpaint already ≈ mode=inpaint; v2 audio-crossfade
     as a no-model baseline; v3 = current sinesweep).

Effort total: ~1 week of focused sessions; items 1 and 4 are same-day wins.

---

## 5. Landed: latent bend module (item 3, module half) — 2026-07-13

`SAO/eval/latent_bend.py` now exists — pure CPU tensor ops on SA3 latents
(`(1, 256, T)` or `(C, T)`, torch or numpy, any float dtype; returns the same
type/shape/dtype). Entry point **`apply_bends(latent, ops, seed=1234, second=None)`**;
op-spec mirrors `weight_mutations.py`'s Condition ops — an ordered list of
`{"op": ..., "amount": ..., + op-specific keys}` — so weight and latent benders read
the same recipe grammar. One CPU `torch.Generator(seed)` drives all randomness, ops
consume it in list order → `(ops, seed)` reproduces exactly.

| op | spec keys | what it does |
|---|---|---|
| `channel_swap` | `amount` (frac of C) | swap random channel pairs (value-preserving) |
| `channel_roll` | `k`, `shift` (frames; omit → random per ch, ±`max_shift`, default T//8) | roll k random channels along T |
| `noise` | `amount` (× per-ch std), `channels` (opt subset) | add gaussian per channel |
| `quantize` | `bits` (levels = 2^bits over per-ch range), `amount` (wet/dry) | bit-crush values |
| `segment_shuffle` | `seg` (frames), `amount` (frac of segments) | shuffle fixed-length time segments |
| `splice` | `spans` `[[t0,t1),...]` (frames), `xfade` (frames, default 8), `other`/`second=` | crossfade a second latent in over spans |
| `band_scale` | `channels` (explicit list), `amount` (multiplier) | scale a channel subset — target features via `mir/stats/latent_dim_feature_xcorr.csv` |

Unknown op names fail loud. Smoke test in `__main__` (run under `SAO/.venv/bin/python`):
asserts shape/dtype preservation, input non-mutation, per-seed determinism (torch and
numpy/fp16 paths), per-op determinism. Still open from item 3: the server `bend:` hook
in `_decode_impl` / `/a2a_mix`, and the explorer Latent-lab tab.

*Audit by CONTINUITY subagent, 2026-07-12. Sources: files cited inline; WORKLOG 2026-06-22
(Gradio_Lab parked), DISCOVERIES §long-form, MASTER §5 (gain ≈512, scalar_pooled fix
2026-07-10), `mir/plots/explorer_sa3/UI_BRIEF.md` (2026-07-08).*
