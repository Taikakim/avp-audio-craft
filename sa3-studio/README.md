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

## Layout

- `src/lib/types.ts` -- the data model (Clip/Lane), including the
  translation-invariance rule: a latent is valid only at the offset it was
  encoded at, so moving a clip marks it `stale` until the next RENDER.
- `src/lib/api.ts` -- typed client for the render server. Every shape here was
  read from `explorer_render_server.py` source, not inferred -- see
  `docs/sa3-studio/PLAN_CORRECTIONS.md` §1 for why that distinction matters.
- `src/lib/transport.ts` -- Web Audio playback engine. Schedules
  `AudioBufferSourceNode`s per clip per lane; this is the only place "the
  timeline is audio" actually happens.
- `src/lib/store.svelte.ts` -- reactive project state + the RENDER action.
- `src/lib/Timeline.svelte`, `TransportBar.svelte`, `Inspector.svelte`,
  `CropLibrary.svelte`, `src/App.svelte` -- UI.

## What's deliberately not here yet

- Waveform rendering (clips are flat blocks for now).
- `/a2a_track`, `/a2a_mix`, `/bend`, LatCH steering, FiLM/DoRA controls --
  the render contract for all of them is already read and typed in `api.ts`'s
  header comment territory; wiring them into the Inspector is the next slice.
- Per-lane crossfade / `reality_anchor` mixing
  (`mir-feature-extraction/scripts/latent_crossfader.py` prior art).
- Persistence -- there is no save/load yet; a session lives in memory only.
