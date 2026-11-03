---
name: audio-review-encode-256kbps
description: "Encode audio for Kim's review pages/artifacts at 256kbps, not lower bitrates"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cd7a9ba8-7c77-4763-a269-4b41c0eb857d
  modified: 2026-09-16T21:07:24.998Z
---

Encode review-clip audio (mp3/m4a transcodes for Claude Artifacts or staged eval pages) at **256kbps**, not the lower bitrates used ad hoc earlier (160k stereo, 128k, 96k mono, 64k mono for large batches).

**Why:** Kim direct ask, 2026-09-16/17. Lower bitrates were chosen for file-size convenience (Artifact size caps, many-clip batches), but they cost him audible fidelity when judging things like HF harshness, resonance, and crossfade smoothness — exactly the kind of detail this project's review work depends on.

**How to apply:** Default to 256kbps for any new transcode going forward. When encoding many clips at once (e.g. 80+ clips for a tagging/audit page) and the Artifact size cap (64MB total, 15MB/file) is a real constraint, this may force going mono or trimming clip count rather than dropping bitrate — raise that tradeoff explicitly rather than silently reverting to a lower bitrate.
