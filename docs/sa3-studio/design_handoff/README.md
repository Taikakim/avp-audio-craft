# Handoff: SA3 Studio — Stable Audio 3 inference and latent workbench

## Overview

SA3 Studio is a desktop UI for running inference against Stable Audio 3 (small / medium /
large) and against custom fine-tunes and heads. It combines three things the existing
Gradio UI keeps apart:

1. **Generation** — prompt, negative prompt, sampler, schedule, seed, length.
2. **A four-lane arrangement workspace** — audio and latents are treated identically;
   clips are placed on a bar grid, tempo-matched, downbeat-aligned, mixed in latent
   space (lerp/slerp), and transformed with audio-to-audio.
3. **Editing** — inpainting between two clips across a user-sized overlap, outpainting
   past a clip's edge, and per-region step/CFG overrides.

Plus a statistics view for latent and chroma analysis, and a modular right-hand pane of
latent tooling (LatCH guidance heads, FiLM, LoRA/DoRA, Bungee time/pitch, sampling).

The design targets **1800×900 usable pixels** (1920×1080 minus OS chrome) with no
scrolling except in the right pane. It is intended to be cross-platform
(Linux/Windows/macOS) and open-source, so the layout is deliberately toolkit-neutral:
plain panes, text buttons, no icon font, nothing that depends on a specific widget set.

## About the design files

**The files in this bundle are design references created in HTML.** They are prototypes
showing intended look and behaviour — not production code to lift. Most of the "data" is
deterministic pseudo-random synthesis (waveform contours, chroma matrices, BPM values)
that exists purely so the layout can be judged with something plausible on screen.

The task is to **recreate these designs in the target codebase's environment**. If no
environment exists yet, pick the appropriate stack. For a cross-platform desktop app with
a Python inference backend the obvious candidates are Qt (PySide6/QML), Tauri + a web
frontend, or Electron; the layout was drawn with a Qt-style docking model in mind and
nothing in it requires a browser.

## Fidelity

**High-fidelity for layout, hierarchy, colour and type. Low-fidelity for data and
behaviour.**

- Colours, type scale, spacing, pane sizes, control grouping and copy are final —
  reproduce them.
- Everything behind the controls is mocked. No model is loaded, no audio decodes, no
  file system is read. Scrubbing, BPM stretch, chroma, alignment and the render progress
  are all simulated.

---

## Design tokens

Defined as CSS custom properties on the root element. All colours are oklch.

| Token | Value | Use |
|---|---|---|
| `--bg` | `oklch(96% 0.006 240)` | app background |
| `--panel` | `oklch(93% 0.008 240)` | pane background |
| `--panel2` | `oklch(90% 0.012 240)` | inputs, recessed areas |
| `--border` | `oklch(80% 0.014 240)` | all 1px borders |
| `--text` | `oklch(27% 0.02 250)` | primary text |
| `--text-dim` | `oklch(52% 0.016 250)` | labels, secondary text |
| `--turq-strong` | `oklch(55% 0.11 195)` | primary accent, active tabs, render |
| `--purple-strong` | `oklch(54% 0.10 300)` | secondary accent, envelopes, overlaps |
| `--green-strong` | `oklch(56% 0.11 150)` | lane 2, positive states |
| `--red` | `oklch(55% 0.20 25)` | clipping marks, destructive |
| `--warm` | `oklch(72% 0.15 75)` | LatCH slot 1 |

Lane identity colours (waveform ink, chips, lane chain headers):

| Lane | Colour |
|---|---|
| 1 | `oklch(54% 0.10 300)` purple |
| 2 | `oklch(56% 0.11 150)` green |
| 3 | `oklch(55% 0.11 195)` turquoise |
| 4 | `oklch(50% 0.02 250)` grey |

Other constants:

- Downbeat marker `oklch(78% 0.08 250)`; coincident downbeats interpolate toward
  `oklch(85% 0.17 95)` yellow over a window of one 32nd note at the mean project tempo.
- Clip (over-0 dBFS) marks: `oklch(55% 0.20 25)`, 2px, on the lane's top and bottom edge.
- LatCH slot identity colours: `['oklch(72% 0.15 75)', 'oklch(62% 0.14 330)']`.
- Overlapping waveform ink is the lane colour with lightness × 0.75.

**Typography.** Space Grotesk throughout (`ui-monospace, monospace` fallback), loaded
from Google Fonts at 400/500/600/700. Sizes: 14px hover note, 12px body, 11px controls,
10px labels, 9px minimum (dense metadata, help notes). Nothing below 9px. Letter-spacing
0.04–0.16em on uppercase labels and the wordmark.

**Spacing.** 2/3/4/5/6/8/10/12px. Panes use 1px `--border`. No border radius anywhere —
square corners are part of the look. No shadows except pane elevation
`0 4px 14px oklch(60% 0.02 250 / 0.25)` on the floating FX panel.

---

## Screens

### 1. Top bar (42px, always visible)

Left to right: wordmark `SA3 STUDIO`; SESSION select; CLIP select (clips rendered this
session); MODEL select plus a free text field for a checkpoint folder path; MASTER PRESET
select; RENDER button; WORKSPACE / STATISTICS tabs; HELP toggle; FX toggle (temporary).

The RENDER button doubles as the progress indicator: while sampling it reads
`SAMPLING · N steps left` and is non-interactive.

### 2. Workspace (default view)

Three regions: a scrolling centre, a fixed-height bottom pane, and a fixed right pane.

**Centre, top to bottom:**

- **Master mix strip.** The result of the lane mix, with the a2a noise envelope drawn
  over it as a Bitwig-style node envelope — four draggable nodes, and each segment bends
  when you drag it vertically (linear by default, curved on pull).
- **Ruler.** Bar number, seconds, and latent frame index (`FRAME_HZ = 10.767`, i.e.
  44100/4096). Bar lines at every 4 beats, beat lines at 55% height.
- **Four lanes.** Each lane holds any number of clips positioned on the grid. Per lane:
  a colour chip, name, latent/audio tag, native BPM field, detune field (±100 cents),
  solo/mute, and the lane's active-chain indicator.

**Lane interaction:**

| Gesture | Effect |
|---|---|
| left-drag on a clip | scrub, looping |
| drag near a clip edge | trim |
| drag from the file pane | drop a clip at the pointer |
| middle-drag ↕ | zoom |
| middle-drag ↔ | scroll |
| shift + wheel | scroll |
| drag with SNAP on | snap to nearest downbeat within 5px, pull further to break the snap |

**Tempo and alignment.** A project BPM field stretches every clip from its native BPM.
MATCH BPM meets all clips at their mean native tempo (least total stretch). ALIGN
DOWNBEATS shifts each clip by the shortest path onto the circular mean of all clips'
downbeat phases. Downbeats that coincide glow yellow, brightest at exact coincidence,
falling off over one 32nd note.

**Overlap regions.** Where two clips in a lane overlap, the region is marked and becomes
a selectable inpaint target with its own crossfade curve, steps and CFG.

**Bottom pane (248px fixed, one tab at a time):** CHROMA · PROMPT + SIGMA ·
MIX + SIGNAL PATH · TERMINAL. Only one is shown at a time — the earlier stacked layout
was too cramped to work in.

- **CHROMA** — a heat map over the lanes with four band views: GLOBAL (all bands
  collapsed to 12 classes), BASS, MID, HIGH (the three octave-band chroma regressors the
  SA3 SAME heads are trained against, octaves 1/5/9, 128 bins each). Toggles for RAW vs
  12-class. Hovering shows the note name and frame index in a readout beside the strip,
  and draws a red vertical line at that position on the selected clip. A detune scan
  strip below shows the match score across ±100 cents with a BEST button and a
  HIGHEST / STEADIEST criterion toggle.
- **PROMPT + SIGMA** — prompt (full height), negative prompt (half), the numeric
  parameters in two rows, and the sigma graph pinned to the right edge at the height of
  both text boxes.
- **MIX + SIGNAL PATH** — the four-way mixer with a flow diagram for the mix order
  (e.g. 1+2 and 3+4, then a+b), lerp/slerp per node, and a position slider per node.
- **TERMINAL** — log output; collapsible and expandable to full screen.

**Right pane (296px):** collapsible modules, each with a lit dot when it holds active
settings. Currently: OVERLAP — INPAINT, FILES, GENERATION, LANE CHAIN (LatCH slots, FiLM,
LoRA, Bungee), MASTER CHAIN, ADVANCED SAMPLING. Selecting a lane switches the LANE CHAIN
module to that lane's chain.

### 3. Statistics view

Latent statistics with per-lane selection buttons. Same shell, different centre.

---

## Model parameters — what the paper actually supports

These were checked against the Stable Audio 3 paper and matter for the backend:

- **MODEL STAGE — POST / BASE.** The released checkpoints are adversarially
  post-trained: they sample with **ping-pong in 8 steps** on a **logSNR-uniform**
  schedule (N+1 equally spaced λ in [−6.2, 2.0], t = sigmoid(−λ)) and **use no CFG** —
  guidance is baked in during distillation. BASE is the pre-distillation flow-matching
  model: DPM++ over 50–100 steps with real CFG. The UI switches sampler, step count and
  schedule together and greys the CFG fields in POST mode.
- **σ is unitless** — a multiplier on the latent's own standard deviation. σmax = 100 is
  effectively pure noise; below ~10 the sampler starts near the data so more of the init
  audio survives. Above ~200 nothing changes except wasted steps.
- **Schedule shapes** are all closed-form monotone curves: logSNR-uniform, geometric,
  linear, cosine, log, exponential. `rho` warps the time axis. A **STEPPED** modifier
  quantises any of them into plateaus, with a **TILT** control for how much each plateau
  still travels. Flat plateaus (tilt 0) are a no-op on ODE solvers — dt = 0 — but are
  valid churn/restart steps under ping-pong; the UI warns when the combination is wrong.
- **Duration is conditioning, not a buffer.** It enters through both cross-attention and
  AdaLN, and the latent is `ceil((d + 6s) × 44100 / 4096)` frames, the trailing 6 s being
  silence padding trimmed after generation. Caps: 2 min (small), 6 min 20 s (medium,
  large).
- **Inpainting is native.** The mask is a binary channel concatenated to the 256-dim
  latent (257×L) and added at every block, so multiple masked regions in one pass is the
  supported case — which is what the overlap-region model relies on.
- **Chroma is a real SAME regression target**, as three octave-band regressors. The 12-
  class collapse in the GLOBAL view is the UI's own summary.
- **LatCH, FiLM, LoRA/DoRA and time-varying control are NOT stock SA3 features** — the
  paper explicitly excludes them as requiring fine-tuning. They are the user's own heads
  and the UI treats them as pluggable modules.
- **CFG interval** can be entered as a decimal fraction or directly in steps; the two
  representations stay in sync when the step count changes.

---

## Interactions and behaviour

**Drag-to-scale on every numeric field.** ~260px of horizontal travel (a wrist movement,
no elbow) sweeps that parameter's typical working range; holding shift drops it to
1/100th and adds two decimals. Decimal rounding derives from the range. A click without
movement focuses the field for typing. Ranges used:

| Field | Range |
|---|---|
| project / clip BPM | 60–200 |
| steps | 1–150 |
| CFG | 0–15 |
| CFG lo/hi | 0–1, or 0–steps |
| length | 1–180 s |
| seed | 0–999999 |
| σ min | 0.001–1 |
| σ max | 1–100 |
| rho | 1–15 |
| λ min / λ max | −12–0 / 0–6 |
| semitones | ±24 |
| overlap steps | 1–100 |
| overlap CFG | 0–15 |

**Help mode.** HELP toggles a hover-help layer: every control carries a `data-help`
string explaining what it is, how to use it, and — for the theoretical ones — a safe
value to return to if it gets changed by accident. Those strings are written and should
be carried over verbatim; they are in the HTML as `data-help` attributes.

**Presets** at three levels: prompt presets (prompt + negative prompt only), per-module
presets, and master presets (every lane chain, clip layout, mix order and node values,
master chain, sigma schedule and prompt in one recall).

**Render progress — C64 raster border.** While sampling, a full-screen canvas overlay
draws a Commodore 64 loader raster bar around the window border. See below.

---

## The raster border effect

`phosphor-border.js` is a standalone ES module and is the one file in this bundle that
**is** production-quality — it can be ported directly.

It simulates a CRT beam sweeping the whole raster with a colour register that is rewritten
every N raster lines, then masks the result down to a border ring. The colour can change
mid-line, which is why the full raster is simulated rather than just the border. A one-pole
low-pass along the beam path models the video amplifier's bandwidth (chroma slower than
luma, so colour rips are soft), and per-channel phosphor decay (green slowest, blue
fastest) means a white flash trails toward green.

Usage:

```js
import { createPhosphorBorder, PALETTES } from './phosphor-border.js';
const fx = createPhosphorBorder(canvas, { thickness: 4, palette: PALETTES.teal, alphaOut: true });
fx.start();
fx.set({ sweepHz: 40 });   // live
fx.stop(); fx.destroy();
```

Settled values (bracketed on the real UI):

```json
{"sweepStart":95,"sweepEnd":0,"dur":5,"thickness":4,"linesPerColour":3,
 "jitter":0.59,"persistence":0.002,"chromaBleed":1.5,"supersample":8,
 "gain":0.8,"spotSpread":0.16,"palette":"teal"}
```

The sweep rate falls linearly from `sweepStart` to `sweepEnd` over `dur` seconds, tied to
the remaining step count, so the bars start as a shimmer and slow to a standstill as the
last steps land. `alphaOut: true` makes dark phosphor transparent so the border settles
back into the light grey background rather than to black.

The canvas is a 300×170 backing stretched over the window with
`image-rendering: pixelated` and `pointer-events: none`.

---

## State

The prototype holds everything in one component's state. For a real app the meaningful
groupings are:

- **Session** — session id, rendered clips, master preset.
- **Transport / view** — project BPM, zoom, scroll position, grid and snap settings,
  selected lane, selected clip, selected overlap region.
- **Clips** — per clip: lane, start, length, native BPM, detune, loop flag, file path,
  latent-or-audio flag, a2a enable, a2a noise amount, a2a noise envelope.
- **Render settings** — prompt, negative prompt, steps, CFG, CFG interval (+ unit),
  length, seed, sampler, objective (post/base), sigma settings.
- **Lane chains** — one per lane: LatCH slots (kind, target, weight, window start/end,
  per-slot hyperparameters), FiLM, LoRA/DoRA (model + scale), Bungee (stretch, semitones).
- **Master chain** — same shape, applied after the mix.
- **Mix** — node graph (which lanes feed which node), per-node lerp/slerp and position.
- **Overlap regions** — keyed by clip pair: crossfade curve, steps, CFG.
- **UI** — which bottom tab, which right-pane modules are open, help mode, FX config.

There is a comment in the source (search `NOTE FOR THE REAL APP`) about per-target render
settings: in the prototype some settings are global that should be per-clip or
per-region. The per-clip a2a fields show the right shape to follow.

---

## Known gaps

Things discussed but not yet drawn, listed so they are not mistaken for oversights:

1. **Multiple LoRA slots** — a +/− control after the last loaded LoRA to add more.
2. **Per-LatCH hyperparameters** — currently one shared set; each slot should own its own.
3. **Fully modular right pane** — the user adding and removing module instances, so each
   LoRA, LatCH and FiLM is its own pane.
4. **RAM / VRAM meter** — a 10px bar in the top bar, two 5px lanes.
5. The **temporary RASTER FX panel** (FX button) is a tuning tool and should be removed.

---

## Assets

No images or icons — the design is deliberately icon-free, all controls are text.
One webfont: **Space Grotesk** (Google Fonts, weights 400/500/600/700).

## Files

| File | What it is |
|---|---|
| `SA3 Studio v3.dc.html` | the design. Opens directly in a browser. Template markup at the top, logic class in the `<script type="text/x-dc">` block below it. All `data-help` strings live here. |
| `phosphor-border.js` | the C64 raster border module. Portable as-is. |
| `latent_tool.txt` | the user's notes on the existing latent explorer, for reference. |
