# Pianoroll + Contour conditioners in the inference UI — Implementation Plan

> **STATUS 2026-08-26 (C): Task 0 PROBE RUN — all four steps pass, the plan is GO.** Findings, with
> the two things the plan got wrong:
> - **Step 1 (contour ckpts): 32 `melody_contour` hits**, all on the UUID drive — `runs/headb_melody/`
>   (terminal + 15 step checkpoints, **vocab 9**) and 16 `morphcond/morph_{IOI3,L2,L3,L4}_{base,ft}_s*`
>   arms (vocab **5** for L2, **15** for IOI3/L3, **77** for L4; control_dim 768 throughout).
>   ⚠ `headb_melody` does NOT record `melody_vocab` in its args — recoverable only from
>   `state["conditioner.embed.weight"].shape[0]`. Task 3's loader must fall back to the embedding
>   shape, or it will silently reject the plan's own primary target.
> - **Step 2 (pianoroll): ALREADY PULLED**, contrary to the plan's expectation that it was still on
>   LUMI scratch. `<UUID>/lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s{1,2}`, terminal
>   `epoch=31-step=2688.ckpt`, **12.9 GB each and FAT**. No rsync needed, no KIM-TASKLIST item.
>   Both carry `control_ablation.jsonl`: control gain vs SHUFFLED settles at **+0.0068 (s1) /
>   +0.0112 (s2)** and vs ZERO at **+0.0018 / +0.0051**, monotone positive after step 800 in both
>   seeds. So the DiT demonstrably reads the roll — but that is a TRAINING-LOSS signal, not proof
>   the control is strong enough to steer melody audibly. Task 7's smoke test is what settles that.
> - **Step 3 (modular inlet): PASSES, but the plan's accessor is wrong by one level.** It says
>   `dw, tf = m.model, m.model.model`; `m.model.model` is a `DiTWrapper` with no `.dim`, so
>   `install_mir_control` dies with `AttributeError: 'DiTWrapper' object has no attribute 'dim'`.
>   The real chain is `StableAudioModel → ConditionedDiffusionModelWrapper → DiTWrapper →
>   DiffusionTransformer → ContinuousTransformer`, so use:
>   `dw, tf = m.model, m.model.model.model.transformer`. With that: `cond_ids: ['mir_ctrl']`,
>   **12 of 24 blocks installed (12–23, the `blocks="12-23"` default), 30,707,712 new trainable
>   params**, `tf.dim == 1536`.
> - **Step 4 (contour_streams): imports cleanly** from `SAO/.venv` with `mir` on the path. **No
>   vendoring needed** — skip the `contour_alphabet.py` copy the plan allows for.
> - **Environment trap found while probing, now in `MASTER.md` §5:** a cloned torchcodec SOURCE repo
>   at `SAO/torchcodec` shadows the real package as a namespace package whenever the SAO ROOT is the
>   cwd, which breaks `T5GemmaEncoderModel` and therefore every `from_pretrained` — but only for
>   `python -c` / heredoc invocations, not for scripts (whose `sys.path[0]` is the script's dir).
>   Run probe snippets from another cwd.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the two control families that are outside the render server — Head-B contour/morph
(`control_mode=melody_contour`) and pianoroll/`mir_ctrl` (128-ch note matrix via
`modular_local_embeds`) — into the :8056 contract, driven from a **loaded MIDI file** with a
**scrub offset** so the user picks where in the MIDI the render window starts.

**Architecture:** Two new `ConditionerFamily` implementations registered into the registry defined by
the sibling plan (`2026-08-23-inference-ui-global-conditioner-inpaint.md` §"Design contract"), plus
two new pure-numpy modules under `control/sa3_control/`: a **time base** (latent-frame arithmetic,
offset/window/zero-fill/optional stretch) and a **MIDI importer** (`.mid` → 128×T piano roll, and
`.mid` → skyline pitch → K&P contour symbol stream). No new renderer, no new guidance driver: the
server keeps calling `MODEL.generate(**kw)`; the families only add `control_slots` entries (Head-B)
and one `conditioning_tensors["mir_ctrl"]` entry (pianoroll).

**Tech Stack:** Python 3.11 · PyTorch 2.14/ROCm 7.15 (`SAO/.venv`) · FastAPI (render server) ·
Dash (viewer, `mir/mir/bin/python`) · `mido` (MIDI parsing, already a dependency of
`eval/build_pianoroll_ctrl.py`) · numpy · pytest.

**Spec:** `docs/INFERENCE-SURFACE.md` §9 "NEEDS BUILDING" items 2 and 3 (lines 450-454), §4(d)
control-context tokens (lines 188-197), §5 contour sidecar semantics (lines 233-237), §8 seam 1-2
(lines 283-297).

**Depends on (do not duplicate):**
- `docs/superpowers/plans/2026-08-23-inference-ui-global-conditioner-inpaint.md` — Task 1 (z0
  sidecars), Task 2 (named control-adapter slots + batch/CFG alignment), Task 3
  (`control/sa3_control/loading.py`, `ControlCkptInfo`, `build_conditioner_from_info`). **This plan
  starts where those end.** Its `ConditionerFamily` / `ConditioningBundle` contract is at lines
  211-260 of that file; read it once before Task 3 here.
- `docs/superpowers/plans/2026-08-23-inference-ui-model-db-and-ab-slots.md` — the multi-root /
  `.pt`-aware checkpoint scanner. Our checkpoints live in `<Mantu>/sa3_control_runs` (833 `.pt`,
  237 dirs) and on the UUID drive, **none of which the current scanner sees**
  (`explorer_render_server.py:93` `CKPT_SCAN_ROOT`). Until that lands, this plan's UI uses an
  explicit-path text field. Do not build a second scanner.

---

## Global Constraints

- **Extend :8056 or write a thin client. Never a second renderer / guidance driver.**
  `resolve_latch()` (`eval/explorer_render_server.py:463-519`) NORMALISES gains
  (`rho = mu = first slot's gain`, per-slot `weight = slot_gain / g0`); a raw weight computed
  elsewhere is a different scale. `eval/head_lab.py` was deleted for exactly this mistake.
- **Venvs by absolute path.** Server + `control/` tests: `/home/kim/Projects/SAO/.venv/bin/python`.
  Viewer + mir imports: `/home/kim/Projects/mir/mir/bin/python`. `mir/bin/python` does not exist.
- **`export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`** before any `import torch` in a GPU shell.
  **Never** `HIP_VISIBLE_DEVICES=""`.
- **No hardcoded drive paths.** The eval drive mounts as `Mantu` OR `Mantu1`; resolve via
  `_mantu_root()` (`eval/explorer_render_server.py:76-81`).
- **Save z0 next to every render** (standing directive). Delivered by sibling Task 1; this plan
  additionally writes the resolved conditioner spec into the render's manifest sidecar.
- **GPU lock via `Misc/gpu_guard.sh`.** Never hand-write `/tmp/gpu.lock`.
- **Latent rate is `FPS = 44100 / 4096 = 10.76660156… Hz`** — exactly as
  `eval/build_pianoroll_ctrl.py:23` and `eval/build_morph_streams.py`. T1024 ≈ 95.1 s,
  T2048 ≈ 190.2 s, T4096 ≈ 380.4 s. Never hardcode `10.766`.
- **Control-stream length must equal the render's latent length exactly.** A short stream is
  **LEFT-padded** by `_left_pad_to_match` (`stable-audio-3/stable_audio_3/models/transformer.py:1052`),
  i.e. silently aligned to the END of the render, not the start. Build streams at exact `n_frames`;
  never rely on padding.
- **The trained null is ZERO, not absence.** Head-B: zero control TOKENS
  (`lumi/render_morph.py:184`). `mir_ctrl`: an all-zero control array through the zero-init
  projection (`stable-audio-3/scripts/mir_control.py:181-183`).
- Tests are CPU-only and must run without a GPU or a mounted eval drive, except the Task 7 smoke.

---

## Discovery — measured facts this plan is built on

1. **The Head-B contour path already exists as a batch script.** `lumi/render_morph.py:109` reads
   `vocab = int(cargs.get("melody_vocab", 9))`; `:140-141` builds
   `MelodyContourEncoder(control_dim=…, n_classes=vocab)`; `:173-186` slices
   `<stem>.melody8.npy[i0:i0+frames]`, zero-pads, encodes, and under CFG does
   `torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)`. This plan lifts that arithmetic into a
   family; it does not re-derive it.
2. **`build_conditioner` drops the vocab — a live bug.** `control/sa3_control/generate.py:46-47`
   builds `MelodyContourEncoder(control_dim=control_dim)` with the default `n_classes=9`
   (`conditioner.py:120`), so any L3 (15) or L4 (77) checkpoint fails `load_state_dict` on
   `embed.weight`. The vocab must be read from `state["conditioner.embed.weight"].shape[0]` —
   **`args["melody_vocab"]` is `None` on the real trained arm** (sibling plan lines 84-90).
3. **Two DIFFERENT contour alphabets exist; do not mix them.**
   *K&P dense-rank (the trained morph arms)* — `eval/build_morph_streams.py`: voiced semitones →
   sparse grid (`STRIDE = 4`) → `contour_stream(semis, points, L, tol=0.5)` + `expand_to_frames`
   from `/home/kim/Projects/mir/src/conditioners/contour_streams.py`; encoding `0 = undefined`,
   `symbol → symbol+1`; vocab = Bell(L)+2 → **L2→5, L3→15, L4→77**; sidecars in
   `latents_sa3_morphL{2,3,4}/` + `latents_sa3_morphIOI3/`.
   *Interval-fold 9-class (the pilot only)* — `melody_pilot_eval.py:74-78` + `:251-276`; this is
   the `n_classes=9` default. The checkpoint's vocab decides which is legal; Task 2 refuses an
   unknown vocab loudly rather than emitting wrong symbols.
4. **MIDI → skyline pitch already exists** — `melody_pilot_eval.py:233-249` via
   `eval/musicology/hook_metric.notes_from_midi_bytes`, `LEAD_PITCH_MIN = 56`, non-drum.
5. **MIDI → piano roll already exists** — `eval/build_pianoroll_ctrl.py:29-46` `roll_of()`:
   `(128, 4096)` fp16, `velocity/64.0` while held, `mido` merged-track absolute seconds, notes held
   to the end filled to `T`, drums NOT filtered. Task 2 generalises both (offset, n, stretch) and
   keeps byte parity at the defaults.
6. **`mir_ctrl` needs NO fork change to reach t2a.**
   `get_conditioning_inputs` reads `conditioning_tensors[key][0]` for every id in
   `modular_local_cond_ids` and **skips missing keys**
   (`stable-audio-3/stable_audio_3/models/diffusion.py:152-161`); `generate` accepts a pre-built
   `conditioning_tensors=` (`model.py:268-269`); the DiT rearranges `b c t -> b t c`
   (`models/dit.py:239-244`) — so we hand it **(B, C, T)**.
7. **Under CFG the modular inlet is duplicated to BOTH halves** (`dit.py:515-518`), so the
   pianoroll inlet is **not CFG-scalable**; its only strength lever is scaling the control tensor.
   A real semantic difference from Head-B's `gain` — label it in the UI, don't smooth it over.
8. **Post-hoc install** is `install_mir_control(diffusion_wrapper, transformer, n_channels,
   cond_id="mir_ctrl", …)` (`stable-audio-3/scripts/mir_control.py:214-254`): the exact
   `Linear→SiLU→Linear` zero-init projection **per TransformerBlock, not global** (WORKLOG
   2026-08-21 trap 2), plus `cond_id` appended to `modular_local_cond_ids`.
   `N_CTRL_CHANNELS = 36` for the MIR pack (`mir_control.py:67`); the pianoroll arm is **128**.
9. **No trained pianoroll or morph checkpoint is on either local drive** (2026-08-24:
   `find -maxdepth 4 -iname "*pianoroll*" -o -iname "*morphcond*"` → empty).
   `EXPERIMENTS.md:560-590` puts `pianoroll_fullft/` and the `morphcond` run dirs on LUMI
   `$SCRATCH`, on the pull list ahead of the purge. The one confirmed Head-B checkpoint is the
   sibling plan's `<UUID>/lumi_runs/runs/headb_melody/riffer_final.pt`. **Task 0 resolves this.**
10. **Sidecars we own locally:** `latents_sa3_morphL{2,3,4}`, `latents_sa3_morphIOI3`, and
    `latents_sa3_proll` (5400 `.ctrl.npy` rolls) — the offline source when there is no MIDI.

### Sources in scope for "import data the contour conditioner needs"

| source | in scope | how |
|---|---|---|
| **`.mid` file** | **YES — primary** | Task 2 `skyline_pitch` → `contour_symbols` at the checkpoint's vocab |
| **`.melody8.npy` sidecar** | **YES** | already the trained format; windowed by Task 1 |
| **`.ctrl.npy` piano roll** | **YES** | `latents_sa3_proll/`; windowed by Task 1 |
| audio reference → f0 → contour | **NO** | needs a MIR f0 pass (`f0_other_ts`) under the mir venv; the render server has no MIR stack. Correct future shape: `/contour_from_audio` on the **mir** :7892 service. Follow-up in Task 8. |
| hand-drawn curve | **NO** | Kim's ask is "just support loading midi files"; a drawn-curve surface is a separate UX plan |

### Duration, scrub, and resampling — the explicit story

Ours is **not** steer-sao's problem. `control/RESEARCH_RADAR.md` §7 records that
`/home/kim/Projects/steer-sao` calls `resize_feature` to interpolate control features to the
requested latent length, because its features come from a fixed-length reference. Our sources
differ:

- **MIDI is authored in seconds** → rasterize *directly at the requested `n_frames`*. Exact, no
  interpolation, no fidelity cost. Strictly better than resizing.
- **A stored sidecar is a 4096-frame array at native FPS** → **slice a window, never squeeze**.
  Squeezing 380 s into 95 s triples the note rate and takes the control off the training manifold.
  Slicing is the trained operation (`lumi/render_morph.py:162,173-176` slices latent and stream by
  the same `i0`).
- **`time_scale` is offered but defaults to 1.0.** It rasterizes MIDI at `FPS / time_scale`. Cost,
  stated in the UI help: the K&P alphabet encodes *interval*, not duration, so pitch symbols
  survive a stretch — but **`morphIOI3` encodes inter-onset intervals and a stretch invalidates it
  outright**, and the roll's implied tempo drifts from the prompt's. Warn on `time_scale != 1.0`
  for an IOI checkpoint.
- **Scrub** = `offset_frames = round(offset_sec * FPS)`. Out-of-range frames zero-fill, which is
  exactly the trained null: scrubbing past the end degrades to unconditioned instead of crashing.
- **Longform** calls the sampler once per window; `bundle.window(frame_offset, n_frames)` re-slices
  with `frame_offset` **added to** the user's scrub offset (Task 5).
---

## File Structure

**New**

| path | repo | responsibility |
|---|---|---|
| `control/sa3_control/timebase.py` | SAO | Latent-frame arithmetic: `FPS`, `n_frames`, `frame_of`, `window_slice`, `resample_stream`. Pure numpy, no torch. |
| `control/sa3_control/midi_io.py` | SAO | `.mid` → notes → piano roll / skyline pitch / contour symbols. Pure numpy + `mido`. |
| `control/sa3_control/tests/test_timebase.py` | SAO | CPU tests. |
| `control/sa3_control/tests/test_midi_io.py` | SAO | CPU tests incl. parity against `build_pianoroll_ctrl.roll_of`. |
| `control/sa3_control/tests/test_families_contour.py` | SAO | CPU tests for both families (fake model). |
| `mir/plots/explorer_sa3/midi_panel.py` | mir | Dash sub-panel: source picker, upload, scrub slider, coverage readout. |
| `mir/tests/explorer_sa3/test_midi_panel.py` | mir | Payload-building tests, no server. |

**Modified**

| path | repo | change |
|---|---|---|
| `control/sa3_control/families.py` | SAO | `+ MelodyContourFamily`, `+ MirCtrlFamily`, both `register()`ed. |
| `control/sa3_control/generate.py:44-48` | SAO | Delete the vocab-dropping `melody_contour` branch; delegate to `loading.build_conditioner_from_info`. |
| `eval/explorer_render_server.py` | SAO | `+ /midi_preview`; thread conditioner specs through `_generate_impl` / `_longform_impl`; record the resolved spec in the manifest. |
| `mir/plots/explorer_sa3/render_client.py` | mir | `+ midi_preview()`; `_OPS += "midi_preview"`. |
| `mir/plots/explorer_sa3/controls.py` | mir | Mount `midi_panel` inside the conditioner panel. |
| `docs/INFERENCE-SURFACE.md`, `ARCHITECTURE.md`, `EXPERIMENTS.md`, `WORKLOG.md`, `KIM-TASKLIST.md` | SAO | Task 8. |

---

## Task 0: PROBE — locate the checkpoints and confirm the inlet is live

**No code.** This task exists because three facts are unknown and every later task's GPU step
depends on them. Record every answer in `docs/INFERENCE-SURFACE.md` §9 under a new
`#### PIANOROLL / CONTOUR CHECKPOINT INVENTORY (2026-08-24)` heading.

**Files:** Modify `docs/INFERENCE-SURFACE.md` (append to §9).

- [ ] **Step 1: Find every `melody_contour` checkpoint reachable locally**

```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
/home/kim/Projects/SAO/.venv/bin/python - <<'EOF'
import glob, torch, os
roots = ["/run/media/kim/Mantu/sa3_control_runs", "/run/media/kim/Mantu1/sa3_control_runs",
         "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs"]
for r in roots:
    for p in sorted(glob.glob(os.path.join(r, "**", "*.pt"), recursive=True)):
        try:
            ck = torch.load(p, map_location="cpu", weights_only=False)
        except Exception as e:
            print("SKIP", p, e); continue
        cm = ck.get("control_mode")
        if cm != "melody_contour":
            continue
        st = ck.get("state", {})
        w = st.get("conditioner.embed.weight")
        print(p, "vocab=", None if w is None else int(w.shape[0]),
              "args_vocab=", ck.get("args", {}).get("melody_vocab"),
              "control_dim=", ck.get("args", {}).get("control_dim"))
EOF
```

Expected: at least `<UUID>/lumi_runs/runs/headb_melody/riffer_final.pt` with a vocab in
{5, 9, 15, 77}. Record every hit and its vocab.

- [ ] **Step 2: Find a pianoroll / `mir_ctrl` checkpoint**

```bash
find /run/media/kim/Mantu /run/media/kim/Mantu1 /run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d \
     -maxdepth 6 \( -iname "*pianoroll*" -o -iname "*mirctrl*" -o -iname "*proll*" \) 2>/dev/null
```

If empty: the arm is still on LUMI `$SCRATCH` (`EXPERIMENTS.md:560-590`, `pianoroll_fullft/`,
jobs 21445517/18). **Craft the rsync pull command for Kim** per `.claude/skills/lumi-ops/SKILL.md`
(agents never run ssh/rsync themselves) and add a KIM-TASKLIST item. **Task 4 is implementable
without the checkpoint; Task 7's pianoroll smoke is blocked on it.**

- [ ] **Step 3: Confirm the modular inlet installs on a resident `medium-base`**

```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
/home/kim/Projects/SAO/.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3/scripts")
from stable_audio_3 import StableAudioModel
from mir_control import install_mir_control
m = StableAudioModel.from_pretrained("medium-base")
dw, tf = m.model, m.model.model
install_mir_control(dw, tf, n_channels=128, cond_id="mir_ctrl")
blocks = getattr(tf, "layers", None) or getattr(tf, "transformer", None)
print("cond_ids:", dw.modular_local_cond_ids)
print("per-block installs:", sum(1 for b in blocks if "mir_ctrl" in b.modular_local_embeds))
EOF
```

Expected: `cond_ids: ['mir_ctrl']` and a non-zero per-block count. If `layers` is not the right
attribute, read `stable-audio-3/scripts/mir_control.py:226-252` for how it discovers blocks and use
the same accessor. **If this fails, stop and report — Task 4 is not implementable as designed.**

- [ ] **Step 4: Confirm `contour_streams` is importable from the SAO venv**

```bash
/home/kim/Projects/SAO/.venv/bin/python -c "
import sys; sys.path.insert(0, '/home/kim/Projects/mir')
from src.conditioners.contour_streams import contour_stream, expand_to_frames
print('OK', contour_stream, expand_to_frames)"
```

Expected: `OK …`. If it pulls a heavy mir dependency, **vendor the two functions** into
`control/sa3_control/contour_alphabet.py` with a header citing
`mir/src/conditioners/contour_streams.py` as the origin, and note the copy in Task 8's doc update.

- [ ] **Step 5: Write the findings section and commit**

```bash
git add docs/INFERENCE-SURFACE.md
git commit -m "docs(INFERENCE-SURFACE): pianoroll/contour checkpoint inventory + modular-inlet probe"
```

---

## Task 1: `timebase.py` — latent-frame arithmetic, scrub and windowing

**Files:** Create `control/sa3_control/timebase.py`; Test `control/sa3_control/tests/test_timebase.py`

**Interfaces:** Consumes nothing. Produces `FPS: float`, `n_frames(sec)->int`, `frame_of(sec)->int`,
`seconds_of(frames)->float`, `window_slice(stream, offset, n, fill=0)->np.ndarray`,
`resample_stream(stream, n_out, kind)->np.ndarray` with `kind in {"nearest","linear"}`.

- [ ] **Step 1: Write the failing test**

```python
# control/sa3_control/tests/test_timebase.py
import numpy as np, pytest
from sa3_control.timebase import FPS, n_frames, frame_of, seconds_of, window_slice, resample_stream

def test_fps_and_canonical_frame_counts():
    assert FPS == 44100 / 4096
    for T in (1024, 2048, 4096):
        assert n_frames(seconds_of(T)) == T
    assert round(seconds_of(4096), 1) == 380.4

def test_frame_of_rounds_and_allows_preroll():
    assert (frame_of(0.0), frame_of(1.0), frame_of(-1.0)) == (0, 11, -11)

def test_window_slice_interior_tail_and_preroll():
    s = np.arange(4, dtype=np.int64)
    assert np.array_equal(window_slice(np.arange(100), 10, 3), np.array([10, 11, 12]))
    assert np.array_equal(window_slice(s, 2, 5), np.array([2, 3, 0, 0, 0]))   # 0 = trained null
    assert np.array_equal(window_slice(s, -2, 5), np.array([0, 0, 0, 1, 2]))

def test_window_slice_2d_slices_time_only_and_keeps_dtype():
    s = np.arange(20, dtype=np.float32).reshape(2, 10)
    out = window_slice(s, 8, 4)
    assert out.shape == (2, 4) and np.array_equal(out[0], np.array([8, 9, 0, 0], np.float32))
    assert window_slice(np.zeros((128, 16), np.float16), 0, 32).dtype == np.float16

def test_resample_nearest_keeps_symbols_and_linear_interpolates():
    out = resample_stream(np.array([1, 1, 2, 2], np.int64), 8, "nearest")
    assert set(np.unique(out)) <= {1, 2} and out.dtype == np.int64
    assert resample_stream(np.array([[0.0, 1.0]], np.float32), 3, "linear")[0, 1] == pytest.approx(0.5)

def test_resample_rejects_linear_on_a_symbol_stream():
    with pytest.raises(ValueError):
        resample_stream(np.array([1, 2], np.int64), 4, "linear")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_timebase.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa3_control.timebase'`.

- [ ] **Step 3: Write the implementation**

```python
# control/sa3_control/timebase.py
"""Latent-frame arithmetic for control streams. Rate = 44100/4096 Hz
(docs/INFERENCE-SURFACE.md:82-83). A stream SHORTER than the render is LEFT-padded by
transformer.py:1052 — i.e. silently aligned to the END. Always build at exact n_frames."""
from __future__ import annotations
import numpy as np

FPS: float = 44100 / 4096          # 10.76660156... never hardcode the decimal


def n_frames(duration_sec: float) -> int:
    return max(1, int(round(float(duration_sec) * FPS)))


def frame_of(sec: float) -> int:
    """Frame index of an absolute time. Negative is legal (pre-roll before the source)."""
    return int(round(float(sec) * FPS))


def seconds_of(frames: int) -> float:
    return float(frames) / FPS


def window_slice(stream: np.ndarray, offset: int, n: int, fill=0) -> np.ndarray:
    """`n` frames from frame `offset` on the LAST axis; out-of-range filled with `fill`
    (0 = trained null: undefined symbol / no note). Handles (T,) and (C, T). dtype preserved."""
    a = np.asarray(stream); n = int(n); offset = int(offset); T = a.shape[-1]
    out = np.full(a.shape[:-1] + (n,), fill, dtype=a.dtype)
    src0, src1 = max(0, offset), min(T, offset + n)
    if src1 > src0:
        d0 = src0 - offset
        out[..., d0:d0 + (src1 - src0)] = a[..., src0:src1]
    return out


def resample_stream(stream: np.ndarray, n_out: int, kind: str = "nearest") -> np.ndarray:
    """Resample the last axis. `nearest` is the ONLY legal mode for categorical symbol
    streams — interpolating symbol ids invents symbols that do not exist."""
    a = np.asarray(stream); n_out = int(n_out); T = a.shape[-1]
    if n_out == T:
        return a.copy()
    if kind == "nearest":
        idx = np.clip((np.arange(n_out) * (T / n_out)).astype(np.int64), 0, T - 1)
        return a[..., idx]
    if kind == "linear":
        if np.issubdtype(a.dtype, np.integer):
            raise ValueError("linear resampling of an integer symbol stream is never correct; "
                             "use kind='nearest'")
        x_new = np.linspace(0.0, T - 1.0, n_out); x_old = np.arange(T, dtype=np.float64)
        flat = a.reshape(-1, T)
        out = np.stack([np.interp(x_new, x_old, r) for r in flat], 0)
        return out.reshape(a.shape[:-1] + (n_out,)).astype(a.dtype)
    raise ValueError(f"unknown resample kind {kind!r}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_timebase.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO
git add control/sa3_control/timebase.py control/sa3_control/tests/test_timebase.py
git commit -m "feat(sa3_control): timebase — latent-frame arithmetic, scrub windowing, resampling"
```

---

## Task 2: `midi_io.py` — MIDI → piano roll and MIDI → contour symbols

**Files:** Create `control/sa3_control/midi_io.py`; Test `control/sa3_control/tests/test_midi_io.py`

**Interfaces:** Consumes `timebase.{FPS, frame_of, window_slice}`. Produces
`Note = NamedTuple(start, end, pitch, velocity, is_drum)`, `load_notes(path_or_bytes)->list[Note]`,
`span_seconds(notes)->float`,
`piano_roll(notes, n, offset_frames=0, time_scale=1.0, vel_div=64.0, n_pitches=128)->(n_pitches,n) float16`,
`skyline_pitch(notes, n, offset_frames=0, time_scale=1.0, pitch_min=56)->(n,) int64` (-1 = silent),
`contour_symbols(frame_pitch, vocab, stride=4, tol=0.5)->(n,) int64` (0 = undefined),
`VOCAB_TO_L = {5: 2, 15: 3, 77: 4}`.

- [ ] **Step 1: Write the failing test**

```python
# control/sa3_control/tests/test_midi_io.py
import numpy as np, pytest
from sa3_control.midi_io import (Note, piano_roll, skyline_pitch, contour_symbols,
                                 span_seconds, VOCAB_TO_L)
from sa3_control.timebase import FPS

def _notes():   # C4 1 s, G5 1 s (both above pitch_min=56), plus a drum hit
    return [Note(0.0, 1.0, 60, 100, False), Note(1.0, 2.0, 79, 80, False),
            Note(0.0, 2.0, 36, 100, True)]

def test_roll_shape_velocity_and_drum_parity():
    r = piano_roll(_notes(), n=32)
    assert r.shape == (128, 32) and r.dtype == np.float16
    assert r[60, 0] == np.float16(100 / 64.0) and r[79, 0] == 0.0
    assert r[36, 0] > 0        # build_pianoroll_ctrl.py:33-41 does NOT filter drums

def test_roll_offset_scrubs_and_past_the_end_is_the_trained_null():
    n1 = int(round(1.0 * FPS))
    assert piano_roll(_notes(), 8, offset_frames=n1)[79, 0] > 0
    assert not piano_roll(_notes(), 8, offset_frames=int(round(10.0 * FPS))).any()

def test_roll_time_scale_stretches():
    n1 = int(round(1.0 * FPS))
    assert piano_roll(_notes(), n1 + 4, time_scale=2.0)[60, n1 + 2] > 0

def test_skyline_is_highest_non_drum_above_pitch_min():
    assert skyline_pitch(_notes(), 8)[0] == 60
    assert skyline_pitch(_notes(), 8, pitch_min=70)[0] == -1
    assert skyline_pitch([], 4)[0] == -1

def test_contour_symbols_encoding_range_and_unvoiced():
    p = np.concatenate([np.full(40, x) for x in (60, 62, 64, 62)]).astype(np.int64)
    s = contour_symbols(p, vocab=15)
    assert s.shape == p.shape and s.dtype == np.int64 and 0 <= s.min() and s.max() < 15
    assert not contour_symbols(np.full(64, -1, dtype=np.int64), vocab=15).any()

def test_contour_symbols_rejects_an_unknown_vocab_and_maps_the_known_ones():
    assert VOCAB_TO_L == {5: 2, 15: 3, 77: 4}      # build_morph_streams.py:15
    with pytest.raises(ValueError, match="vocab"):
        contour_symbols(np.full(64, 60, dtype=np.int64), vocab=9)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_midi_io.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa3_control.midi_io'`.

- [ ] **Step 3: Write the implementation**

```python
# control/sa3_control/midi_io.py
"""MIDI -> control streams at the SAME latent rate, with a scrub offset.

piano_roll     <- eval/build_pianoroll_ctrl.py:29-46 (roll_of), made offset/length aware
skyline_pitch  <- control/sa3_control/melody_pilot_eval.py:233-249, made offset/length aware
contour_symbols uses the K&P alphabet of eval/build_morph_streams.py (the alphabet the trained
morph arms use). The 9-class interval fold in melody_pilot_eval.py is a DIFFERENT alphabet
belonging to the pilot only and is deliberately not emitted here.
"""
from __future__ import annotations
import sys
from typing import NamedTuple
import numpy as np
from .timebase import FPS

VOCAB_TO_L = {5: 2, 15: 3, 77: 4}      # build_morph_streams.py:15 — vocab = Bell(L) + 2
STRIDE = 4                             # build_morph_streams.py:26
TOL_SEMITONES = 0.5                    # build_morph_streams.py:27


class Note(NamedTuple):
    start: float; end: float; pitch: int; velocity: int; is_drum: bool


def load_notes(src) -> list[Note]:
    """`src` = path or raw .mid bytes. Absolute seconds (mido iteration yields delta seconds)."""
    import io, mido
    mf = mido.MidiFile(file=io.BytesIO(src)) if isinstance(src, (bytes, bytearray)) \
        else mido.MidiFile(str(src))
    out: list[Note] = []; t = 0.0; active: dict = {}
    for msg in mf:
        t += msg.time
        ch = getattr(msg, "channel", 0)
        if msg.type == "note_on" and msg.velocity > 0:
            active[(ch, msg.note)] = (t, msg.velocity)
        elif msg.type in ("note_off", "note_on"):
            k = (ch, getattr(msg, "note", None))
            if k in active:
                s0, vel = active.pop(k)
                out.append(Note(s0, t, int(msg.note), int(vel), ch == 9))
    for (ch, note), (s0, vel) in active.items():        # notes held to the end
        out.append(Note(s0, t, int(note), int(vel), ch == 9))
    return out


def span_seconds(notes) -> float:
    return max((n.end for n in notes), default=0.0)


def _fr(sec: float, time_scale: float) -> float:
    return sec * FPS / float(time_scale)


def piano_roll(notes, n: int, offset_frames: int = 0, time_scale: float = 1.0,
               vel_div: float = 64.0, n_pitches: int = 128) -> np.ndarray:
    """(n_pitches, n) float16, velocity/vel_div while held. Byte-parity with
    build_pianoroll_ctrl.roll_of at offset=0, n=4096, time_scale=1.0 (drums included)."""
    roll = np.zeros((int(n_pitches), int(n)), dtype=np.float16)
    for nt in notes:
        if not (0 <= nt.pitch < n_pitches):
            continue
        f0 = int(_fr(nt.start, time_scale)) - int(offset_frames)
        f1 = int(_fr(nt.end, time_scale)) + 1 - int(offset_frames)
        f0, f1 = max(0, f0), min(int(n), f1)
        if f1 > f0:
            roll[nt.pitch, f0:f1] = nt.velocity / vel_div
    return roll


def skyline_pitch(notes, n: int, offset_frames: int = 0, time_scale: float = 1.0,
                  pitch_min: int = 56) -> np.ndarray:
    """(n,) int64 highest sounding non-drum pitch >= pitch_min per frame, -1 = silent.
    pitch_min=56 is the prep_targets lead convention (melody_pilot_eval.py:72)."""
    best = np.full(int(n), -1, dtype=np.int64)
    for nt in notes:
        if nt.is_drum or nt.pitch < pitch_min:
            continue
        f0 = int(np.floor(_fr(nt.start, time_scale))) - int(offset_frames)
        f1 = int(np.ceil(_fr(nt.end, time_scale))) - int(offset_frames)
        f0, f1 = max(0, f0), min(int(n), max(f0 + 1, f1))
        if f1 > f0:
            seg = best[f0:f1]; np.maximum(seg, nt.pitch, out=seg)
    return best


def contour_symbols(frame_pitch: np.ndarray, vocab: int, stride: int = STRIDE,
                    tol: float = TOL_SEMITONES) -> np.ndarray:
    """(T,) int64 K&P contour symbols, 0 = undefined, symbol -> symbol+1. Exactly
    build_morph_streams.py:57-62 with MIDI pitch (already semitones) for 12*log2(f0/440)."""
    if int(vocab) not in VOCAB_TO_L:
        raise ValueError(f"vocab {vocab} has no K&P alphabet; known {sorted(VOCAB_TO_L)} "
                         f"(L2/L3/L4). A vocab-9 checkpoint uses the melody_pilot interval-fold "
                         f"alphabet, which MIDI import does not emit.")
    L = VOCAB_TO_L[int(vocab)]
    try:
        sys.path.insert(0, "/home/kim/Projects/mir")
        from src.conditioners.contour_streams import contour_stream, expand_to_frames
    except ImportError as e:                                    # pragma: no cover
        raise ImportError("contour_streams required for MIDI->contour; see Task 0 step 4 "
                          "(vendor into sa3_control/contour_alphabet.py)") from e
    p = np.asarray(frame_pitch); T = p.shape[0]
    semis = np.where(p >= 0, p.astype(np.float64), 0.0)
    points = np.flatnonzero(p >= 0)[::int(stride)]
    if points.size < L + 2:
        return np.zeros(T, dtype=np.int64)
    syms, anchors = contour_stream(semis, points, L=L, tol=tol)
    stream = expand_to_frames(syms, anchors, T)
    return np.where(stream < 0, 0, stream + 1).astype(np.int64)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_midi_io.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify byte parity against the trained builder**

```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
/home/kim/Projects/SAO/.venv/bin/python - <<'EOF'
import glob, sys, numpy as np
sys.path.insert(0, "/home/kim/Projects/SAO/eval"); sys.path.insert(0, "/home/kim/Projects/SAO/control")
from build_pianoroll_ctrl import roll_of
from sa3_control.midi_io import load_notes, piano_roll
p = sorted(glob.glob("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full/*.mid"))[0]
a, b = roll_of(p), piano_roll(load_notes(p), n=4096)
print(p, "maxdiff", float(np.abs(a.astype(np.float32) - b.astype(np.float32)).max()))
EOF
```

Expected: `maxdiff 0.0`. If non-zero, match `build_pianoroll_ctrl.py:38-45` exactly (note its
`int()` truncation, not rounding) — the trained arm's semantics win. Skip if the drive is unmounted.

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO
git add control/sa3_control/midi_io.py control/sa3_control/tests/test_midi_io.py
git commit -m "feat(sa3_control): midi_io — MIDI to piano roll and K&P contour symbols with scrub offset"
```

---

## Task 3: `MelodyContourFamily` — Head-B contour into the conditioner registry

**Files:** Modify `control/sa3_control/families.py` and `control/sa3_control/generate.py:44-48`;
Test `control/sa3_control/tests/test_families_contour.py`

**Interfaces:** Consumes `conditioning.{ConditionerFamily, RenderContext, Contribution, register}`
and `loading.{introspect, introspect_dict, build_conditioner_from_info}` (sibling plan Task 3),
`timebase.{frame_of, window_slice}`, `midi_io`. Produces family `"melody_contour"`,
`inlet="control_tokens"`, params `{source, midi_path, sidecar_path, offset_sec, time_scale,
pitch_min, gain}`, and `build_stream(spec, ctx, vocab, extra_frame_offset=0) -> (n,) int64`.

- [ ] **Step 1: Write the failing test**

```python
# control/sa3_control/tests/test_families_contour.py
import numpy as np, pytest
from sa3_control.conditioning import FAMILIES, RenderContext

def _ctx(n):
    return RenderContext(n_frames=n, duration_sec=n / (44100 / 4096), batch_size=1,
                         cfg_scale=7.0, device="cpu", dtype="float32")

def _midi(tmp_path, pitches=(60, 64, 67, 64, 60, 62, 65, 62)):
    import mido
    mf = mido.MidiFile(); tr = mido.MidiTrack(); mf.tracks.append(tr)
    for p in pitches:
        tr.append(mido.Message("note_on", note=p, velocity=90, time=0))
        tr.append(mido.Message("note_off", note=p, velocity=0, time=480))
    path = tmp_path / "m.mid"; mf.save(path); return str(path)

def test_family_is_registered_with_the_expected_schema():
    f = FAMILIES["melody_contour"]
    assert f.inlet == "control_tokens"
    keys = {p["key"] for p in f.describe()["params"]}
    assert {"source", "midi_path", "sidecar_path", "offset_sec", "time_scale", "gain"} <= keys

def test_sidecar_is_windowed_not_squeezed(tmp_path):
    side = tmp_path / "x.melody8.npy"
    full = (np.arange(4096) % 14 + 1).astype(np.int8); np.save(side, full)
    s = FAMILIES["melody_contour"].build_stream(
        {"source": "sidecar", "sidecar_path": str(side), "offset_sec": 10.0}, _ctx(512), vocab=15)
    assert s.shape == (512,) and s[0] == full[int(round(10.0 * 44100 / 4096))]

def test_extra_frame_offset_shifts_the_window_for_longform(tmp_path):
    side = tmp_path / "x.melody8.npy"; np.save(side, np.arange(4096, dtype=np.int8))
    f = FAMILIES["melody_contour"]
    spec = {"source": "sidecar", "sidecar_path": str(side), "offset_sec": 0.0}
    a = f.build_stream(spec, _ctx(64), vocab=15)
    b = f.build_stream(spec, _ctx(64), vocab=15, extra_frame_offset=64)
    assert int(b[0]) == int(a[0]) + 64

def test_midi_source_uses_the_checkpoint_vocab(tmp_path):
    s = FAMILIES["melody_contour"].build_stream(
        {"source": "midi", "midi_path": _midi(tmp_path), "offset_sec": 0.0, "pitch_min": 0},
        _ctx(256), vocab=15)
    assert s.shape == (256,) and s.max() < 15

def test_unknown_vocab_from_midi_raises(tmp_path):
    with pytest.raises(ValueError, match="vocab"):
        FAMILIES["melody_contour"].build_stream(
            {"source": "midi", "midi_path": _midi(tmp_path)}, _ctx(64), vocab=9)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_families_contour.py -v`
Expected: FAIL — `KeyError: 'melody_contour'`.

- [ ] **Step 3: Implement the family** — append to `control/sa3_control/families.py`

```python
import numpy as np
import torch
from .conditioning import ConditionerFamily, Contribution, register
from . import loading, midi_io
from .timebase import frame_of, window_slice


class MelodyContourFamily(ConditionerFamily):
    """Head-B contour adapter (control_mode='melody_contour'). Arithmetic lifted from
    lumi/render_morph.py:140-186: per-frame symbol stream -> encoder -> control tokens; the
    trained null is ZERO TOKENS and the cat([ctrl, zeros]) under CFG is done by the shared
    adapter-slot machinery (sibling plan Task 2), which knows the live query batch."""

    name = "melody_contour"
    label = "Melody contour (Head-B)"
    inlet = "control_tokens"
    needs_ckpt = True
    ckpt_glob = "riffer*.pt"

    def detect(self, ck: dict) -> bool:
        return ck.get("control_mode") == "melody_contour"

    def describe(self) -> dict:
        return {"name": self.name, "label": self.label, "inlet": self.inlet,
                "needs_ckpt": True, "ckpt_glob": self.ckpt_glob, "params": [
            {"key": "source", "type": "choice", "options": ["midi", "sidecar"], "default": "midi",
             "label": "Contour source",
             "help": "midi = derive the contour from a .mid; sidecar = a trained "
                     "<stem>.melody8.npy from latents_sa3_morphL{2,3,4}/ or morphIOI3/."},
            {"key": "midi_path", "type": "path", "label": "MIDI file", "default": ""},
            {"key": "sidecar_path", "type": "path", "label": "melody8 sidecar", "default": ""},
            {"key": "offset_sec", "type": "float", "label": "Start offset (s)", "default": 0.0,
             "min": -60.0, "max": 3600.0,
             "help": "Scrub: where in the source this render's window starts. Past the end "
                     "zero-fills, which is the trained null."},
            {"key": "time_scale", "type": "float", "label": "Time scale", "default": 1.0,
             "min": 0.25, "max": 4.0,
             "help": "MIDI only. The K&P alphabet encodes INTERVAL not duration so pitch symbols "
                     "survive a stretch; an IOI checkpoint is invalidated by it."},
            {"key": "pitch_min", "type": "int", "label": "Lead pitch floor", "default": 56,
             "min": 0, "max": 127, "help": "Skyline ignores non-drum notes below this."},
            {"key": "gain", "type": "float", "label": "Control gain", "default": 1.0,
             "min": 0.0, "max": 4.0, "help": "1.0 = as trained (render_morph uses 1 and 2)."},
        ]}

    def build_stream(self, spec: dict, ctx, vocab: int, extra_frame_offset: int = 0) -> np.ndarray:
        n = int(ctx.n_frames)
        off = frame_of(float(spec.get("offset_sec", 0.0))) + int(extra_frame_offset)
        src = spec.get("source", "midi")
        if src == "sidecar":
            path = spec.get("sidecar_path") or ""
            if not path:
                raise ValueError("melody_contour: source='sidecar' needs sidecar_path")
            return window_slice(np.load(path).astype(np.int64), off, n, fill=0)
        if src == "midi":
            path = spec.get("midi_path") or ""
            if not path:
                raise ValueError("melody_contour: source='midi' needs midi_path")
            pitch = midi_io.skyline_pitch(midi_io.load_notes(path), n, offset_frames=off,
                                          time_scale=float(spec.get("time_scale", 1.0)),
                                          pitch_min=int(spec.get("pitch_min", 56)))
            return midi_io.contour_symbols(pitch, vocab=int(vocab))
        raise ValueError(f"melody_contour: unknown source {src!r}")

    def contribute(self, spec: dict, ctx) -> Contribution:
        info = loading.introspect(spec["ckpt"])
        enc = loading.build_conditioner_from_info(info, device=ctx.device, dtype=ctx.dtype)
        stream = self.build_stream(spec, ctx, vocab=int(info.vocab),
                                   extra_frame_offset=int(getattr(ctx, "frame_offset", 0)))
        with torch.no_grad():
            tokens = enc(torch.from_numpy(stream)[None].to(ctx.device))
        return Contribution(
            control_slots={self.name: (tokens, float(spec.get("gain", 1.0)))},
            meta={"family": self.name, "ckpt": spec["ckpt"], "vocab": int(info.vocab),
                  "source": spec.get("source"),
                  "offset_sec": float(spec.get("offset_sec", 0.0)),
                  "time_scale": float(spec.get("time_scale", 1.0)),
                  "coverage": float((stream > 0).mean())})


register(MelodyContourFamily())
```

- [ ] **Step 4: Delete the vocab-dropping loader branch**

In `control/sa3_control/generate.py`, replace lines 44-48 — the `elif cm == "melody_contour":`
branch that builds `MelodyContourEncoder(control_dim=control_dim)` with the default `n_classes=9`
— with:

```python
    elif cm == "melody_contour":
        from . import loading
        return loading.build_conditioner_from_info(loading.introspect_dict(ck),
                                                   device=device, dtype=dtype)
```

Rationale: `args["melody_vocab"]` is `None` on the real trained arm; the vocab lives in
`state["conditioner.embed.weight"].shape[0]` (sibling plan lines 84-90).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_families_contour.py sa3_control/tests/test_loading.py -v`
Expected: all pass (`test_loading.py` is the sibling plan's and must stay green).

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO
git add control/sa3_control/families.py control/sa3_control/generate.py \
        control/sa3_control/tests/test_families_contour.py
git commit -m "feat(sa3_control): MelodyContourFamily — Head-B contour from MIDI or sidecar, with scrub offset"
```

---

## Task 4: `MirCtrlFamily` — the 128-ch piano roll into `modular_local_embeds`

**Files:** Modify `control/sa3_control/families.py`; Test append to
`control/sa3_control/tests/test_families_contour.py`

**Interfaces:** Consumes `midi_io.piano_roll`, `timebase.{frame_of, window_slice}`,
`stable-audio-3/scripts/mir_control.install_mir_control`. Produces family `"mir_ctrl"`,
`inlet="modular_local"`, params `{source, midi_path, ctrl_path, offset_sec, time_scale,
n_channels, strength}`, `build_array(spec, ctx, extra_frame_offset=0) -> (C, n) float32`, and
`Contribution.cond_tensors["mir_ctrl"] = [tensor (B, C, T)]`.

- [ ] **Step 1: Write the failing test (append)**

```python
def test_mir_ctrl_is_registered_with_the_expected_schema():
    f = FAMILIES["mir_ctrl"]
    assert f.inlet == "modular_local"
    keys = {p["key"] for p in f.describe()["params"]}
    assert {"source", "midi_path", "ctrl_path", "offset_sec", "strength", "n_channels"} <= keys

def test_ctrl_array_is_channels_by_time_and_strength_scales_the_tensor(tmp_path):
    arr = tmp_path / "x.ctrl.npy"; np.save(arr, np.ones((128, 4096), dtype=np.float16))
    f = FAMILIES["mir_ctrl"]
    spec = {"source": "ctrl", "ctrl_path": str(arr), "offset_sec": 0.0}
    assert f.build_array(spec, _ctx(512)).shape == (128, 512)
    assert float(f.build_array({**spec, "strength": 2.0}, _ctx(32)).max()) == 2.0

def test_channel_mismatch_is_fatal(tmp_path):
    arr = tmp_path / "x.ctrl.npy"; np.save(arr, np.ones((36, 4096), dtype=np.float16))
    with pytest.raises(ValueError, match="channels"):
        FAMILIES["mir_ctrl"].build_array(
            {"source": "ctrl", "ctrl_path": str(arr), "n_channels": 128}, _ctx(32))

def test_midi_source_produces_128_channels(tmp_path):
    a = FAMILIES["mir_ctrl"].build_array(
        {"source": "midi", "midi_path": _midi(tmp_path), "offset_sec": 0.0}, _ctx(64))
    assert a.shape == (128, 64) and a.any()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_families_contour.py -k mir_ctrl -v`
Expected: FAIL — `KeyError: 'mir_ctrl'`.

- [ ] **Step 3: Implement** — append to `control/sa3_control/families.py`

```python
class MirCtrlFamily(ConditionerFamily):
    """Per-frame control matrix through the DiT's native modular local inlet. Two trained
    shapes: the 128-ch MuScriptor PIANO ROLL (eval/build_pianoroll_ctrl.py) and the 36-ch MIR
    pack (mir_control.py:67). NOT CFG-scalable — dit.py:515-518 duplicates modular cond to BOTH
    halves — so the only strength lever is scaling the tensor, which is what `strength` does."""

    name = "mir_ctrl"
    label = "Note matrix / MIR control (modular inlet)"
    inlet = "modular_local"
    needs_ckpt = True
    ckpt_glob = "*.ckpt"

    def detect(self, ck: dict) -> bool:
        sd = ck.get("state_dict", ck.get("state", {})) or {}
        return any("modular_local_embeds.mir_ctrl" in k for k in sd)

    def describe(self) -> dict:
        return {"name": self.name, "label": self.label, "inlet": self.inlet,
                "needs_ckpt": True, "ckpt_glob": self.ckpt_glob, "params": [
            {"key": "source", "type": "choice", "options": ["midi", "ctrl"], "default": "midi",
             "label": "Note source",
             "help": "midi = load a .mid; ctrl = a prebuilt <stem>.ctrl.npy "
                     "(latents_sa3_proll/, 5400 rolls)."},
            {"key": "midi_path", "type": "path", "label": "MIDI file", "default": ""},
            {"key": "ctrl_path", "type": "path", "label": "ctrl array", "default": ""},
            {"key": "offset_sec", "type": "float", "label": "Start offset (s)", "default": 0.0,
             "min": -60.0, "max": 3600.0},
            {"key": "time_scale", "type": "float", "label": "Time scale", "default": 1.0,
             "min": 0.25, "max": 4.0, "help": "MIDI only; stretches the roll in time."},
            {"key": "n_channels", "type": "int", "label": "Channels", "default": 128,
             "min": 1, "max": 512,
             "help": "128 = piano roll, 36 = MIR pack. Read from the checkpoint when loaded."},
            {"key": "strength", "type": "float", "label": "Strength (tensor scale)",
             "default": 1.0, "min": 0.0, "max": 4.0,
             "help": "This inlet is duplicated across the CFG halves, so strength scales the "
                     "control TENSOR, not a guidance weight. 1.0 = as trained."},
        ]}

    def build_array(self, spec: dict, ctx, extra_frame_offset: int = 0) -> np.ndarray:
        n = int(ctx.n_frames)
        off = frame_of(float(spec.get("offset_sec", 0.0))) + int(extra_frame_offset)
        want_c = int(spec.get("n_channels", 128))
        src = spec.get("source", "midi")
        if src == "ctrl":
            path = spec.get("ctrl_path") or ""
            if not path:
                raise ValueError("mir_ctrl: source='ctrl' needs ctrl_path")
            full = np.load(path)
            if full.ndim != 2:
                raise ValueError(f"mir_ctrl: ctrl array must be (C, T), got {full.shape}")
            if full.shape[0] != want_c:
                raise ValueError(f"mir_ctrl: array has {full.shape[0]} channels, checkpoint "
                                 f"expects {want_c}")
            arr = window_slice(full.astype(np.float32), off, n, fill=0.0)
        elif src == "midi":
            path = spec.get("midi_path") or ""
            if not path:
                raise ValueError("mir_ctrl: source='midi' needs midi_path")
            if want_c != 128:
                raise ValueError(f"mir_ctrl: MIDI import produces 128 channels, checkpoint "
                                 f"expects {want_c} channels")
            arr = midi_io.piano_roll(midi_io.load_notes(path), n, offset_frames=off,
                                     time_scale=float(spec.get("time_scale", 1.0))
                                     ).astype(np.float32)
        else:
            raise ValueError(f"mir_ctrl: unknown source {src!r}")
        return arr * float(spec.get("strength", 1.0))

    def contribute(self, spec: dict, ctx) -> Contribution:
        arr = self.build_array(spec, ctx, int(getattr(ctx, "frame_offset", 0)))
        t = torch.from_numpy(arr)[None].to(device=ctx.device, dtype=ctx.dtype)
        t = t.repeat(int(ctx.batch_size), 1, 1)          # DiT rearranges b c t -> b t c
        return Contribution(
            cond_tensors={"mir_ctrl": [t]},
            install=lambda model: _install_mir_inlet(model, arr.shape[0]),
            meta={"family": self.name, "ckpt": spec.get("ckpt"),
                  "n_channels": int(arr.shape[0]), "source": spec.get("source"),
                  "offset_sec": float(spec.get("offset_sec", 0.0)),
                  "strength": float(spec.get("strength", 1.0)),
                  "active_frac": float((np.abs(arr) > 0).any(axis=0).mean())})


def _install_mir_inlet(model, n_channels: int):
    """Idempotent post-hoc install of the PER-BLOCK modular projection
    (stable-audio-3/scripts/mir_control.py:214-254). Per TransformerBlock, not global."""
    import sys
    sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3/scripts")
    from mir_control import install_mir_control
    dw = model.model
    if "mir_ctrl" in getattr(dw, "modular_local_cond_ids", []):
        return
    install_mir_control(dw, dw.model, n_channels=int(n_channels), cond_id="mir_ctrl")


register(MirCtrlFamily())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest sa3_control/tests/test_families_contour.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO
git add control/sa3_control/families.py control/sa3_control/tests/test_families_contour.py
git commit -m "feat(sa3_control): MirCtrlFamily — 128-ch piano roll through the modular local inlet"
```

---

## Task 5: Render-server wiring — `/midi_preview`, spec threading, longform windowing

**Files:**
- Modify: `eval/explorer_render_server.py` (new endpoint; `_generate_impl` at `:734`;
  `_longform_impl` at `:944`; `build_response` at `:528`)
- Test: `eval/tests/test_midi_preview.py`

**Interfaces:**
- Consumes: `ConditioningBundle` (sibling Task 1/3), `sa3_control.midi_io`, `sa3_control.timebase`.
- Produces: `POST /midi_preview {path|b64, duration_sec, offset_sec, time_scale, vocab?} ->
  {span_sec, n_notes, pitch_min, pitch_max, frames, coverage, active_frac, thumb}`;
  `req["conditioners"]: list[spec]` accepted by `/generate` and `/longform`;
  `.mmline.json` gains a `"conditioners": [meta,…]` array.

- [ ] **Step 1: Write the failing test**

```python
# eval/tests/test_midi_preview.py
import base64, sys
import mido
import pytest
sys.path.insert(0, "/home/kim/Projects/SAO/control")


def _midi_bytes(tmp_path):
    mf = mido.MidiFile(); tr = mido.MidiTrack(); mf.tracks.append(tr)
    for p in (60, 64, 67):
        tr.append(mido.Message("note_on", note=p, velocity=90, time=0))
        tr.append(mido.Message("note_off", note=p, velocity=0, time=960))
    path = tmp_path / "m.mid"; mf.save(path)
    return path.read_bytes(), str(path)


def test_preview_reports_span_and_pitch_range(tmp_path):
    from explorer_render_server import _midi_preview_impl
    _b, path = _midi_bytes(tmp_path)
    r = _midi_preview_impl({"path": path, "duration_sec": 47.0, "offset_sec": 0.0})
    assert r["n_notes"] == 3
    assert r["pitch_min"] == 60 and r["pitch_max"] == 67
    assert r["span_sec"] > 0
    assert r["frames"] == 506          # round(47.0 * 44100/4096)


def test_preview_accepts_base64_upload(tmp_path):
    from explorer_render_server import _midi_preview_impl
    b, _path = _midi_bytes(tmp_path)
    r = _midi_preview_impl({"b64": base64.b64encode(b).decode(), "duration_sec": 10.0})
    assert r["n_notes"] == 3


def test_preview_offset_past_the_end_reports_zero_activity(tmp_path):
    from explorer_render_server import _midi_preview_impl
    _b, path = _midi_bytes(tmp_path)
    r = _midi_preview_impl({"path": path, "duration_sec": 10.0, "offset_sec": 600.0})
    assert r["active_frac"] == 0.0


def test_preview_rejects_a_missing_file():
    from explorer_render_server import _midi_preview_impl
    with pytest.raises(Exception):
        _midi_preview_impl({"path": "/nope/none.mid", "duration_sec": 10.0})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_midi_preview.py -v`
Expected: FAIL — `ImportError: cannot import name '_midi_preview_impl'`.

- [ ] **Step 3: Implement the endpoint**

Add near `_decode_impl` (`eval/explorer_render_server.py:1538`):

```python
def _midi_preview_impl(req):
    """Parse a .mid and report what it would contribute to a render of `duration_sec`
    starting at `offset_sec`. Pure CPU — deliberately NOT under GPU_LOCK, so the UI can
    scrub while a render is running."""
    import base64
    import numpy as np
    from sa3_control import midi_io
    from sa3_control.timebase import frame_of, n_frames as _nf

    if req.get("b64"):
        src = base64.b64decode(req["b64"])
    else:
        p = require_path(req.get("path"), "midi path")
        src = str(p)
    notes = midi_io.load_notes(src)
    dur = _f(req, "duration_sec", 47.0)
    n = _nf(dur)
    off = frame_of(_f(req, "offset_sec", 0.0))
    ts = _f(req, "time_scale", 1.0)
    lead = [nt for nt in notes if not nt.is_drum]
    roll = midi_io.piano_roll(notes, n, offset_frames=off, time_scale=ts)
    active = (np.abs(roll.astype(np.float32)) > 0).any(axis=0)
    out = {
        "span_sec": midi_io.span_seconds(notes),
        "n_notes": len(notes),
        "pitch_min": int(min((nt.pitch for nt in lead), default=-1)),
        "pitch_max": int(max((nt.pitch for nt in lead), default=-1)),
        "frames": int(n),
        "active_frac": float(active.mean()),
        # 128 x 128 thumbnail for the scrub strip, max-pooled over time
        "thumb": np.max(roll.astype(np.float32).reshape(128, -1, max(1, n // 128))[:, :128],
                        axis=2).round(3).tolist() if n >= 128 else [],
    }
    vocab = req.get("vocab")
    if vocab:
        pitch = midi_io.skyline_pitch(notes, n, offset_frames=off, time_scale=ts,
                                      pitch_min=_i(req, "pitch_min", 56))
        sym = midi_io.contour_symbols(pitch, vocab=int(vocab))
        out["coverage"] = float((sym > 0).mean())
        out["vocab"] = int(vocab)
    return out


@app.post("/midi_preview")
def midi_preview(req: dict):
    return _midi_preview_impl(req)
```

Then, in `_generate_impl` (`:734`), after `latch_cfgs, latch_hp = resolve_latch(...)` and before
the `kw = dict(...)` build:

```python
        # ConditioningBundle + RenderContext come from the sibling plan's
        # control/sa3_control/conditioning.py; `import sa3_control.families` registers ours.
        import sa3_control.families  # noqa: F401  (registration side effect)
        from sa3_control.conditioning import ConditioningBundle, RenderContext
        ctx = RenderContext(n_frames=_nf(duration), duration_sec=duration, batch_size=batch,
                            cfg_scale=cfg, device=ARGS.device,
                            dtype=next(MODEL.model.model.parameters()).dtype)
        bundle = ConditioningBundle.resolve(req.get("conditioners") or [], ctx)
        bundle.install(MODEL)                       # mir_ctrl per-block inlet, idempotent
        kw.update(bundle.generate_kwargs())         # conditioning_tensors for modular_local
```

and replace `with film_context(req.get("film")):` with:

```python
        with film_context(req.get("film")), bundle.context():
```

Record the resolved specs in the manifest by passing `meta={"op": "generate",
"conditioners": bundle.meta()}` to `build_response` (`:781`).

In `_longform_impl` (`:944`), the per-window call must use `bundle.window(frame_offset, n_frames)`
where `frame_offset` is the window's start frame in the render's own timeline — so window 2 of a
contour render continues the MIDI rather than restarting it.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /home/kim/Projects/SAO/eval && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_midi_preview.py -v`
Expected: 4 passed.

- [ ] **Step 5: Smoke the endpoint against a live server**

```bash
cd /home/kim/Projects/SAO && .venv/bin/python eval/explorer_render_server.py &
sleep 20
curl -s -X POST localhost:8056/midi_preview -H 'content-type: application/json' \
  -d '{"path":"/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full/<pick-one>.mid","duration_sec":47,"offset_sec":30,"vocab":15}' | head -c 400
```

Expected: JSON with `span_sec`, `frames: 506`, `coverage` in (0, 1].

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO
git add eval/explorer_render_server.py eval/tests/test_midi_preview.py
git commit -m "feat(render-server): /midi_preview + conditioner specs on /generate and /longform"
```

---

## Task 6: Viewer — MIDI source picker, scrub slider, coverage readout

**Files:**
- Create: `/home/kim/Projects/mir/plots/explorer_sa3/midi_panel.py`
- Create: `/home/kim/Projects/mir/tests/explorer_sa3/test_midi_panel.py`
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/render_client.py` (add `midi_preview`)
- Modify: `/home/kim/Projects/mir/plots/explorer_sa3/controls.py` (mount the panel)

**Repo/venv:** the mir repo, branch `sa3-latent-explorer`, `/home/kim/Projects/mir/mir/bin/python`.

**Interfaces:**
- Consumes: `/midi_preview`, `/info.conditioners` (family schemas from Task 3/4).
- Produces: `midi_panel.layout(family_name)`, `midi_panel.payload(values) -> spec dict`
  matching the family param keys exactly (`source`, `midi_path`, `sidecar_path`/`ctrl_path`,
  `offset_sec`, `time_scale`, `pitch_min`, `gain`/`strength`).

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/mir/tests/explorer_sa3/test_midi_panel.py
import pytest
from plots.explorer_sa3 import midi_panel


def test_payload_keys_match_the_family_schema():
    spec = midi_panel.payload("melody_contour",
                              {"source": "midi", "midi_path": "/x.mid", "offset_sec": 12.5,
                               "time_scale": 1.0, "pitch_min": 56, "gain": 1.5})
    assert spec["family"] == "melody_contour"
    assert spec["params"]["offset_sec"] == 12.5
    assert spec["params"]["gain"] == 1.5


def test_offset_slider_max_follows_the_loaded_span():
    mx = midi_panel.offset_max(span_sec=190.0, duration_sec=47.0)
    assert mx == pytest.approx(190.0)          # scrubbing to the tail is allowed; it zero-fills


def test_disabled_when_no_source_selected():
    spec = midi_panel.payload("melody_contour", {"source": "midi", "midi_path": ""})
    assert spec["enabled"] is False


def test_mir_ctrl_uses_strength_not_gain():
    spec = midi_panel.payload("mir_ctrl",
                              {"source": "ctrl", "ctrl_path": "/x.ctrl.npy", "strength": 2.0})
    assert "strength" in spec["params"] and "gain" not in spec["params"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m pytest tests/explorer_sa3/test_midi_panel.py -v`
Expected: FAIL — `ImportError: cannot import name 'midi_panel'`.

- [ ] **Step 3: Implement the panel**

`midi_panel.py` must provide:

1. `layout(family_name)` — a `dcc.RadioItems` source selector (`midi` / `sidecar` or `ctrl`), a
   `dcc.Upload` **plus** a plain path `dcc.Input` (the render server and the viewer may be on the
   same box, so a path avoids a base64 round-trip for a 4096-frame roll), an `offset_sec`
   `dcc.Slider` with `dcc.Input` twin for exact entry, `time_scale`, `pitch_min` (contour only),
   and the strength control named per family (`gain` vs `strength`).
2. `offset_max(span_sec, duration_sec) -> float` — returns `span_sec` (scrubbing into the tail is
   legal and zero-fills).
3. A **coverage readout** driven by a debounced callback to `render_client.midi_preview(...)`,
   showing `span`, `frames`, `active_frac`, and for the contour family `coverage`. Colour it red
   below 0.2 — `lumi/render_morph.py:56` picks reference windows at `min_cov=0.8`, so a low-coverage
   scrub position is a weak conditioner and the user should see that before rendering.
4. A **scrub strip**: render `thumb` from `/midi_preview` as a `dcc.Graph` heatmap (pitch × time)
   so the user sees what the current window contains. Reuse the existing sigma-graph styling in
   `inference_tab.py` rather than inventing a second chart idiom.
5. `payload(family_name, values) -> {"family":…, "enabled": bool, "ckpt": …, "params": {…}}` —
   `enabled` is False when the selected source has no path. Param keys **must** match the family
   `describe()` keys from Tasks 3-4 exactly.

Add to `render_client.py`:

```python
def midi_preview(**kw):
    return _post("midi_preview", kw)
```
and append `"midi_preview"` to `_OPS`.

Mount in `controls.py` inside the conditioner panel from the sibling plan, gated on the family's
`inlet` being `control_tokens` or `modular_local`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m pytest tests/explorer_sa3/test_midi_panel.py -v`
Expected: 4 passed.

- [ ] **Step 5: Launch the viewer and eyeball the panel**

```bash
cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m plots.explorer_sa3.app
```
Open `http://localhost:8051`, inference tab. Expected: the conditioner panel lists
`melody_contour` and `mir_ctrl`; loading a `.mid` fills the coverage readout and the scrub strip;
moving the offset slider updates both without a render.

- [ ] **Step 6: Commit (mir repo)**

```bash
cd /home/kim/Projects/mir
git add plots/explorer_sa3/midi_panel.py plots/explorer_sa3/render_client.py \
        plots/explorer_sa3/controls.py tests/explorer_sa3/test_midi_panel.py
git commit -m "feat(explorer): MIDI source panel with scrub offset, coverage readout and note strip"
```

---

## Task 7: End-to-end GPU smoke — one contour render, one pianoroll render

**Files:** none created. Produces renders under the server's job dir.

**Preconditions:** Task 0 found a `melody_contour` checkpoint (and, for the second half, a
pianoroll checkpoint — if Task 0 step 2 came up empty, **do the contour half and stop**, and leave
the pianoroll half checked off as BLOCKED with the KIM-TASKLIST item referenced).

- [ ] **Step 1: Take the GPU lock and start the server**

```bash
cd /home/kim/Projects/SAO
bash Misc/gpu_guard.sh status
.venv/bin/python eval/explorer_render_server.py &
sleep 25 && curl -s localhost:8056/status
```

- [ ] **Step 2: Contour render — three arms at one scrub position**

```bash
CK=<the melody_contour ckpt from Task 0>
MID=<a .mid from muscriptor_full>
for G in 0 1 2; do
curl -s -X POST localhost:8056/generate -H 'content-type: application/json' -d "{
  \"prompt\": \"psychedelic goa trance lead melody\", \"duration\": 47, \"steps\": 24,
  \"cfg_scale\": 7, \"seed\": 1234,
  \"conditioners\": [{\"family\": \"melody_contour\", \"enabled\": true, \"ckpt\": \"$CK\",
    \"params\": {\"source\": \"midi\", \"midi_path\": \"$MID\", \"offset_sec\": 30.0,
                 \"gain\": $G}}]}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['files'], d['meta'])"
done
```

Expected: three jobs; `meta.conditioners[0]` carries `vocab`, `coverage`, `offset_sec: 30.0`; each
job dir has a `.wav` **and** a `.z0.npy` (sibling Task 1). `gain: 0` is the trained-null control —
it must sound like an unconditioned render, and `gain: 2` must differ audibly from `gain: 1`.
**If gain 0/1/2 are indistinguishable, the control is not reaching the sampler — stop and debug
before continuing** (this is trap 3 in `docs/INFERENCE-SURFACE.md:257`).

- [ ] **Step 3: Prove the scrub offset changes the output**

Repeat step 2 at `gain: 1` with `offset_sec` 0, 30, 120 and the same seed. Expected: three
different melodic shapes from one seed and one prompt. Same seed + same offset must be
bit-identical on repeat.

- [ ] **Step 4: Pianoroll render (if a checkpoint exists)**

Same shape, `"family": "mir_ctrl"`, `params: {"source": "midi", "midi_path": …,
"offset_sec": 0.0, "n_channels": 128, "strength": <0|1|2>}`. Expected: `meta.conditioners[0]`
carries `active_frac`; strength 0 = unconditioned.

- [ ] **Step 5: Longform continuity check**

One `/longform` call, `duration: 190`, same MIDI, `offset_sec: 0`. Expected: the manifest shows a
per-window `frame_offset` that increases monotonically, and the melody does not restart at each
window boundary.

- [ ] **Step 6: Record the smoke results**

Append the job ids, gains, and the listening verdict to `profiles/<handle>.tasks.md` and, if the
result is a finding, `profiles/<handle>.journal.md`.

---

## Task 8: Register, document, and close the loop

**Files:** Modify `docs/INFERENCE-SURFACE.md`, `ARCHITECTURE.md`, `EXPERIMENTS.md`, `WORKLOG.md`,
`KIM-TASKLIST.md`, `control/RESEARCH_RADAR.md`.

- [ ] **Step 1: `docs/INFERENCE-SURFACE.md`** — move §9 NEEDS-BUILDING items 2 and 3 into HAS;
  correct §5's *"must match the checkpoint's `args['melody_vocab']`"* (line 236) to
  *"read the vocab from `state['conditioner.embed.weight'].shape[0]` — `args['melody_vocab']` is
  `None` on the real trained arm"*; add the two-alphabet warning (K&P L2/L3/L4 vs the 9-class
  pilot fold); add `/midi_preview` to the endpoint list at line 42.

- [ ] **Step 2: `ARCHITECTURE.md` reuse index** — one line each for
  `control/sa3_control/timebase.py`, `control/sa3_control/midi_io.py`, and
  `mir/plots/explorer_sa3/midi_panel.py`, cross-linked to this plan (DISCOVERABILITY RULE,
  `CLAUDE.md` §5).

- [ ] **Step 3: `EXPERIMENTS.md`** — the pianoroll and morph arms now have an interactive audition
  path; note it on their entries and record the D14 blocker's status (the `SDEditReanchor`
  conditioning seam is still open for a2a; this plan only covers t2a + longform).

- [ ] **Step 4: `KIM-TASKLIST.md`** — add (a) "pull `pianoroll_fullft/` + `morphcond` run dirs from
  LUMI `$SCRATCH` before the purge" with the rsync command, if Task 0 step 2 came up empty;
  (b) "listen: contour gain 0/1/2 at three scrub offsets" from Task 7.

- [ ] **Step 5: `control/RESEARCH_RADAR.md` §7** — record the resolution: MIDI is authored in
  seconds so we rasterize at the target length instead of `resize_feature`-ing a fixed-length
  reference; sidecars are WINDOWED, never squeezed. Open the follow-up: **steer-sao's multi-branch
  control-CFG vs our scalar gain**, and **contour-from-audio as a mir-side `/contour_from_audio`
  endpoint** (out of scope here — the render server has no MIR stack).

- [ ] **Step 6: `WORKLOG.md`** + a post to `AGENT_DIALOGUE.md` (Kim's public window), then commit.

```bash
cd /home/kim/Projects/SAO
git add docs/INFERENCE-SURFACE.md ARCHITECTURE.md EXPERIMENTS.md WORKLOG.md KIM-TASKLIST.md \
        control/RESEARCH_RADAR.md
git commit -m "docs: register the pianoroll + contour conditioners in the inference surface"
```

---

## Open questions for Kim

1. **Where are the trained pianoroll and morph checkpoints?** Neither is on a local drive
   (2026-08-24 find). `EXPERIMENTS.md:560-590` places them on LUMI `$SCRATCH`, on the pull list
   ahead of the purge. Task 7's pianoroll half is blocked until they are pulled.
2. **Which contour alphabet should MIDI import target by default** when several checkpoints are
   available — L2 (5), L3 (15) or L4 (77)? The plan reads the vocab from the checkpoint, so this is
   only a default-ordering question in the picker.
3. **Audio-reference contour import is deliberately out of scope** (needs an f0 pass under the mir
   venv). Confirm that MIDI + existing sidecars is enough for the first cut.
