# ORIENTATION — read this first, before searching for anything

*Written 2026-09-10 by Claude at the end of a long session, for the next session (mine or
anyone's). Its single purpose: **stop you searching for things that already exist.** Four
times in one day I concluded a capability was missing when it was one branch or one repo
away. Every such conclusion cost real work. If you are about to say "X doesn't exist",
check this file first.*

---

## 1. The repo map — and the one mapping that keeps getting missed

All under `C:\Users\kim.ake\OneDrive - Bluefors\Documents\py\` on Windows.

| repo | what it is | branch as of 2026-09-10 |
|---|---|---|
| **`avp-audio-craft`** | **= SAO.** The meta/coordination repo. Docs, `eval/` (313 files), the render server. README opens `# SAO — Audio Generation Pipeline` | `sa3-style-adapter` |
| `audio-tools-avp` | fork of `stable-audio-tools`. LatCH heads, FusionOpt, control adapters | `main`, 2 unpushed doc commits |
| `stable-audio-3` | fork of Stability's SA3. Model, training, `scripts/train_lora.py`, Gradio UI | `main` |
| `mir-feature-extraction` | MIR features, the **live Dash explorer**, latent servers, chroma extractor | `main` |
| `fusion-optimiser` | standalone FusionOpt (SHA-256 identical to the copies in `audio-tools-avp`) | `main` |

### >>> `~/Projects/SAO` on the Arch box **IS** `py/avp-audio-craft` <<<

This is the single highest-value fact here. Any doc, docstring or launch hint saying
`SAO/eval/...` or `/home/kim/Projects/SAO/...` means **this repo**. I twice told Kim the
render server was "in a repository nobody here can read". It is
`avp-audio-craft/eval/explorer_render_server.py`.

Also: `mir/` in SAO docs = `mir-feature-extraction`; `stable-audio-tools/` = `audio-tools-avp`.

### Branch discipline

The team works on long-lived feature branches and merges to `main` in bursts. On
2026-09-10 both `avp-audio-craft` and `mir-feature-extraction` had `main` **months stale**
while the real work sat on branches — then merged mid-session. **Always
`git fetch --all` and check `for-each-ref --sort=-committerdate refs/remotes/origin`
before concluding anything about what exists.**

`avp-audio-craft` cannot be checked out on Windows on branches predating `a61478b`
("papers: make the filenames Windows-safe") — 16 files under `papers/` had colons in the
names. Git rejects those at index-write, so `sparse-checkout` does NOT help. Fixed on
`sa3-style-adapter`; if `main` still has them, stay on the branch.

## 2. Where everything is

### The live tool (the thing being replaced)
- **`mir-feature-extraction/plots/explorer_sa3/`** — Plotly Dash, ~3,600 lines, SIX tabs:
  Viewer, Dataset, Analysis, **Inference** (`inference_tab.py`, 871 lines, ~85 components),
  **A2A Mix** (`a2a_tab.py`, 637), **Latent lab** (`bend_tab.py`, 231).
  `controls.py` (478) is the shared LatCH/FiLM/DoRA steering panel — a 35-value positional
  contract. `callbacks.py` (170) holds the load-bearing Dash id contract (~34 callbacks).
  `render_client.py` (313) is the HTTP client. **`UI_BRIEF.md` is Kim's own design brief.**
- Serves `localhost:8050`. Dash = Python that generates the web page; there is no separate
  HTML version.
- `plots/explorer/` is the OLDER SAO-Small (64-dim) explorer. Superseded, but see §4.

### The backend
- **`avp-audio-craft/eval/explorer_render_server.py`** — FastAPI, **2292 lines, 27 routes**,
  port **8056**. Holds medium-base resident. Tests in `eval/test_render_server_models_api.py`.
- Routes (grepped 2026-09-10):
  `GET /info /status /ckpts /presets /presets/{name} /slots /roots /models /models/{id} /audio/{job}/{file}`
  · `POST /presets /ab /slots` · `POST /generate /a2a_track /a2a_mix /longform /decode /bend`
  · `GET|POST /schedule` (via `@app.api_route` — a `@app.post` grep MISSES it)
  · `GET /crops /meta /player_status /decode /source /mix /steer` (lines 2157-2233)
- **`/mix` and `/steer` are LIVE here**, not on a separate player and not dead.
- **Genuinely absent: `/encode`, `/inpaint`, `/jobs`, n-way `/mix`, `/analyze`.**
- Second server `mir-feature-extraction/scripts/latent_server_sa3.py` (:7892) = VAE decode
  + LatCH `/steer`; `latent_server_onnx.py` (:7893) = low-VRAM ONNX variant.

### The design
- **`avp-audio-craft/docs/sa3-studio/design_handoff/`** — moved here 2026-09-10 from a loose
  unversioned folder. `SA3 Studio v3.dc.html` (2313 lines) is current and **loads
  `support.js`**; `phosphor-border.js` is declared production-ready (Kim: "needs work").
  `README.md` is the handoff spec. `.dc.html` is Claude Design's canvas format.
- **The design agent never saw the Dash app** — only the Gradio UI and inference scripts. So
  it misses real features and invents others. See `PLAN_CORRECTIONS.md` §5.

### This session's output
- `docs/sa3-studio/SA3_STUDIO_PORT_MAP.md` — 495 KB, **unverified agent output**. Six surface
  maps (598 controls with Dash ids, 108 rewrite hazards) + four build plans.
- `docs/sa3-studio/PLAN_CORRECTIONS.md` — **READ BEFORE THE PORT MAP.**
- `docs/sa3-studio/extract_port_map.py` — regenerates the port map from the workflow journal.

### Research and data
- **Chroma extractor EXISTS**: `mir-feature-extraction/scripts/gen_same_chroma_ts.py` +
  `src/harmonic/same_chroma.py`, merged `6c14e8b`. Recipe in
  `mir-feature-extraction/CHROMA_HANDOFF.md`: `n_fft=8192`, hop 4096 forced, `log1p`,
  `ChromaScale(n_chroma=128)`, centres `(1,5,9)`, widths `(1,1.5,1)` → `(3,128,T)`.
  (`audio-tools-avp/avp_sa3/sa3_control/dataset.py` says "data-gen TODO" — **that comment is
  stale**; the producer is in the mir repo.)
- **Phase/shift probes**: `avp-audio-craft/eval/phase_invariance_probe.py`,
  `phase_shift_sweep.py`, `phase_accuracy_hires.py`. Outputs live on the **Mantu removable
  drive**, not on the laptop.
- `avp-audio-craft/EXPERIMENTS.md` (~1431 lines) = forward-looking; `DISCOVERIES.md` = found.
  Filelock before editing: `python3 Misc/filelock.py acquire EXPERIMENTS.md --handle <you>`.
- `audio-tools-avp/docs/book/probes/` — two FusionOpt probes rebuilt after the scratchpad was
  lost; results in their docstrings.

## 3. Established facts — do not re-derive

- **Kim's authoritative workflow** (overrides the handoff README): clips load onto a
  timeline; latents are **decoded to audio on load**; **THE TIMELINE IS AUDIO**. All
  preview/scrub/mix is audio and is explicitly NOT the eventual output — its purpose is
  checking onset/downbeat alignment before committing. **RENDER commits**: it runs the real
  latent op / control heads / a2a pass server-side. Realtime latent decode + control heads
  are far too slow to be interactive. The app is a **compositor for an eventual latent
  mixdown**, not a realtime latent engine.
- **SAME latents are NOT translation-invariant.** Sub-frame circular roll moves **212/256
  dims**. Phase is stored as approximate 2-plane SO(2) rotations **only to ~7 kHz** (mean
  phase accuracy above 7 kHz ~0.58; nulls at 5.2/6.7/10.5/15.5 kHz). **A latent is valid
  only at the offset it was encoded at → re-encode, never reposition.**
- Latent frame = 44100/4096 = **92.9 ms** (10.7666 Hz). This does **NOT** constrain
  audio-domain placement — Kim corrected me on this and was right. Store position as
  frame + sample residual.
- **Untested premise** (the project's biggest risk): nobody has checked whether
  audio-domain alignment predicts latent-domain result quality well enough to justify a
  preview stage. Milestone M2 exists to test it. Partially de-risked by §4.
- **Rank-128 FusionOpt routing cliff**: `MIN_SPECTRAL_DIM=128` and a LoRA factor's
  `min(shape)` IS its rank, so at `--rank` 16/32/64 the spectral group is EMPTY and
  FusionOpt == ScheduleFree-AdamW. Does NOT affect the `onset_*`/LATCH control-head arms
  (`control_dim=768`). Detail in `audio-tools-avp/docs/book/SA3_OPTIMIZER_EMA_GROUND_TRUTH.md`
  — **but that note was written against a stale `main` and has known errors** (its
  "autoscale has no tests" and "`same_chroma_ts` has no producer" claims are both wrong).
- SAME latent covariance: ~786x anisotropic, 1/f slope alpha ~ -1.12, 188/256 eigendirections
  below the velocity-target noise floor.

## 4. Prior art that already works — CHECK BEFORE BUILDING

**`mir-feature-extraction/scripts/latent_crossfader.py`** (302 lines) — latent-space stem
crossfading with **per-stem weights**, `reality_anchor` (pull toward each source's full-mix
latent to restore colour), energy-preserving slerp, `STEMS = [drums, bass, other, vocals]`.
**`scripts/latent_server.py:438 beatmatch_crossfade_to_wav`** does audio-domain
pitch-shift + time-stretch per track → encode → latent crossfade — i.e. **the exact commit
pipeline this project designed independently**, already built and reported working, on
SAO-Small. `_apply_pitch_stretch` has a bungee→pedalboard→rubberband chain (= the design's
Bungee module, written). Caveat: SAO-Small is a 64-dim conv VAE; SAME is a soft-norm
bottleneck, so verify the slerp geometry transfers. Full detail: `PLAN_CORRECTIONS.md` §4b.

## 5. Decisions taken

- **New app, from scratch, cross-platform** (Arch / Windows / maybe macOS).
- **Stack: web frontend against the existing FastAPI.** Browser-first; wrap in Electron
  later if a window is wanted (Electron over Tauri — WebKitGTK is the weak engine for
  sustained canvas). PySide6 is the runner-up (PyQt6 precedent exists at
  `mir-feature-extraction/plots/roformer-test-gui/app.py`, 613 lines — but PyQt6 is GPL,
  use PySide6). Rejected Qt because the boundary is already HTTP and it throws away the
  2313-line prototype.
- **Working mode: linear, in the main stream.** Subagents only for genuine fan-out or a
  large read whose bulk isn't needed in context. A 12-agent workflow cost ~40 percentage
  points of a 5-hour window; the fan-out earned it only in the Map phase.
- Timeline-first spine, with M2 (the hypothesis test) kept early.

## 6. Open questions

1. Does the render step encode the **whole arrangement as one buffer**, or **per-lane
   buffers on a common origin**? Per-lane is what makes LANE CHAIN control heads real;
   one buffer makes the MIX panel just an audio mixer. **Not yet decided — ask Kim.**
2. Chroma data source for the CHROMA tab: SAME head forward pass per frame, or a local
   audio chromagram cached at analyze time? Different products.
3. `max_slots` real value; whether `LATCH_SLOTS=3` is a hard server limit. **Both now
   answerable by reading `explorer_render_server.py`.**
4. Whether SAME is shift-equivariant at **whole-frame** granularity — never tested; the
   probe only swept within one frame. One-line change (`SHIFTS` to multiples of 4096,
   compare `z(4096k)` vs `roll(z(0),k)`). Decides whether "snap to latent grid" can be a
   lossless-placement feature.
5. Whether to merge `sa3-style-adapter` → `main`, and the two unpushed commits on
   `audio-tools-avp` (whose note has known errors — fix before pushing).

## 7. Operating rules

- **NEVER use the M365 connector** (Outlook/Teams/SharePoint) during this work. Company
  laptop, personal project. Applies to **every subagent** — say so in their prompts.
- **Git identity**: global is unset/Bluefors. Set repo-local **`Kim` / `kim.ake@gmail.com`**
  before the first commit to any Taikakim repo, and verify with
  `git log -1 --format='%an <%ae>'`.
- **Wipe credentials after every push**: `cmdkey /delete:git:https://github.com`, then
  confirm `cmdkey /list | findstr github` is empty.
- **No GPU here** — Intel Xe only. Neither server runs locally. Everything on this laptop is
  read-and-reason. Don't propose running the model, and don't offer to.
- **The scratchpad is volatile** — it was silently emptied between sessions on 2026-09-10.
  Put anything worth keeping in a repo.
- Kim's token budget: a 5-hour window plus a **weekly cap that binds first**, replenishing
  **Saturday**. Be economical; say what things will cost before starting them.

## 8. The parked workflow

Run `wf_91eb340d-2ae`. Ten of twelve agents completed; **the two critic passes never ran**
(completeness + adversarial). Resume — cached agents replay free:

```
Workflow({scriptPath: "C:\\Users\\kim.ake\\.claude\\projects\\C--Users-kim-ake--local-bin\\d97c0469-ca75-4658-bd3f-85770fdc68dd\\workflows\\scripts\\sa3-studio-plan-wf_91eb340d-2ae.js",
          resumeFromRunId: "wf_91eb340d-2ae"})
```

Then re-run `extract_port_map.py` to fold the critics in as Part 3. Note the completeness
critic was aimed at exactly the class of error found in `PLAN_CORRECTIONS.md` §1.

## 9. Tomorrow's first action

**Read `avp-audio-craft/eval/explorer_render_server.py` (2292 lines) and rewrite the port
map's contract section from source.** Highest value per token available: it converts ~10
inferred response shapes into fact, settles the dead-surface question, answers open
questions 2 and 3, and re-scopes milestones M5 and M7. Runs fine on this laptop.

## 10. What the venvs actually import (2026-09-16, WINTERMUTE)

Several packages exist in more than one copy in this tree. Authority is decided by what the venvs
import, not by what a grep finds first — checked on the GPU box:

| Import | Resolves to | How |
|---|---|---|
| `stable_audio_3` | `/home/kim/Projects/SAO/stable-audio-3` | plain `.pth` in `SAO/.venv`, so `PYTHONPATH` can shadow it — which is how a fork worktree gets tested |
| `stable_audio_tools` | `/home/kim/Projects/SAO/stable-audio-tools/stable_audio_tools` | editable finder in `sat-venv` |
| `sa3_control` | `/home/kim/Projects/SAO/control/sa3_control` | `eval/chroma_morph_transitions.py:38` inserts `/home/kim/Projects/SAO/control`, and it is the superset: 45 modules against 26 in `stable-audio-tools/avp_sa3/sa3_control`, with `conditioner.py`, `dataset.py`, `generate.py`, `comprehensive_merit.py` and `checkpoint_trajectory_stats.py` all diverged. **Treat `avp_sa3/sa3_control` as stale by default.** |
| `apply_attn` | `stable-audio-3/stable_audio_3/models/transformer.py:617` | the only copy on this box; takes `padding_mask` / `varlen_metadata` |

`target_raw` (a raw per-frame LatCH target) IS handled, at `stable_audio_3/model.py:539-550` of that
first checkout, and is **linearly interpolated** to `latent_sample_size` — so a target built shorter
than the pass's padded window is stretched over it. See the 2026-09-16 dialogue entry on the
`/a2a_mix` chroma-morph. (The comment above that block says "nearest-resampled"; the code says
`mode="linear"`.)
