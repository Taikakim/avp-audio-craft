# SA3 Studio

Four-lane audio arrangement compositor for SA3. Read
`../docs/sa3-studio/ORIENTATION.md` first if you're picking this up cold.

**The workflow this app encodes** (Kim, 2026-09-10): clips live on a timeline;
the timeline is audio. Every clip -- imported audio, a decoded latent crop, or
a prior render's output -- has an audio preview you can scrub and mix, purely
to check onset/downbeat alignment. Nothing about that preview is the eventual
output. **RENDER commits**: it calls the real server-side op
(`POST /generate` or `POST /decode` on `explorer_render_server.py`) and swaps
the clip's preview for the actual result.

## Run it

```bash
npm install
npm run dev
```

Needs `explorer_render_server.py` running (`avp-audio-craft/eval/`, default
port 8056) -- vite proxies every server route to it (see `vite.config.ts`).
Point at a different host with `SA3_RENDER_SERVER=http://host:port npm run dev`.

No GPU on this laptop -- `npm run dev` runs fine, but RENDER will only
complete against a server that has a model loaded.

## The one constraint that shapes the UI

`/a2a_track` and `/a2a_mix` take an **`audio_path` that the server resolves on
its own filesystem** (`require_path()`), and the server has no upload route. So
a clip imported through the browser's file picker genuinely cannot be a2a'd
until the server can see that file. The app says so up front (the Inspector's
blocked-reason box) instead of letting the button fail with a 500.

A clip becomes server-addressable when a job returns: `build_response`'s
`files` are absolute server paths, so decode/generate a clip once and its
`serverPath` is filled in for the next pass. You can also paste a path by hand
-- on your own desktop the browser and the server are the same machine.

## Layout

- `src/lib/types.ts` -- the data model (Clip/Lane/RenderParams/BendOp),
  including the translation-invariance rule: a latent is valid only at the
  offset it was encoded at, so moving a clip marks it `stale` until the next
  RENDER.
- `src/lib/api.ts` -- typed client for the render server. Every shape here was
  read from `explorer_render_server.py` source, not inferred -- see
  `docs/sa3-studio/PLAN_CORRECTIONS.md` §1 for why that distinction matters.
- `src/lib/musictime.ts` -- bar/beat/latent-frame maths, snapping, and the
  MATCH BPM (mean native tempo) and MATCH DOWNBEATS (circular-mean phase)
  operations.
- `src/lib/waveform.ts` -- peak extraction (cached per url+span+resolution),
  canvas drawing, and the offline mixdown for the master strip.
- `src/lib/transport.ts` -- Web Audio playback engine. Schedules
  `AudioBufferSourceNode`s per clip per lane, honouring per-clip trim; this is
  the only place "the timeline is audio" actually happens.
- `src/lib/store.svelte.ts` -- reactive project state, the RENDER dispatch for
  all six ops, and `renderBlock()` (what each op is still missing).
- UI: `Timeline.svelte` (ruler, grid, drag/trim), `ClipView.svelte` (waveform),
  `MasterStrip.svelte`, `TransportBar.svelte`, `Inspector.svelte`,
  `ServerPanel.svelte`, `CropLibrary.svelte`, `src/App.svelte`.

## What's wired

Six render ops, each mapped to a real endpoint: `generate`, `decode`,
`a2a_track`, `a2a_mix`, `longform`, `bend` (op vocabulary from
`eval/latent_bend.py`). Timeline with waveforms, bar/beat grid, latent-frame
ticks, zoom (ctrl+wheel or ±), snap (bar/beat/1-8/1-16/1-32/clip-edges/free,
alt-drag to bypass), clip move/trim/duplicate/delete, per-lane mute/solo/gain,
offline master mixdown with a clipping readout, the server's own `log_tail` as
a live terminal, and project save/load as JSON.

Keyboard: space play/pause, Delete removes the selected clip, Home rewinds,
`+`/`-` zoom, arrows nudge the playhead when a lane has focus.

In dev, `window.__sa3` is the live store -- handy for driving the arrangement
from the console when no render server is running.

## What's deliberately NOT here

- **No n-way latent mixdown.** The server has no such op: `/a2a_mix` is an A→B
  transition and `GET /mix` is a 2-crop slerp preview. The four-lane mix is
  audio-domain preview only until that endpoint exists (ORIENTATION.md's M7).
- **No `/encode`, `/inpaint`, `/analyze`, `/jobs`.** So clip BPM and downbeat
  are user-entered fields, not detected -- MATCH BPM/DOWNBEATS operate on what
  you tell them.
- No time-stretch or pitch-shift client-side (the real one lives server-side in
  the a2a path; `mir-feature-extraction/scripts/latent_server.py`'s
  `_apply_pitch_stretch` is the prior art to port).
- No LatCH/FiLM/DoRA steering panel yet -- `/steer` previews and the control
  heads are typed in `api.ts` but have no UI.
- No per-stem crossfade / `reality_anchor` panel
  (`mir-feature-extraction/scripts/latent_crossfader.py` prior art).
- Untested against a live render server -- there's no GPU on the laptop this
  was written on. Every request shape was read from the server source, but the
  first real round trip will be on your desktop.
