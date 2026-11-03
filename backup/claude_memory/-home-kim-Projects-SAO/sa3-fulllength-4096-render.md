---
name: sa3-fulllength-4096-render
description: "Full-length 378 s / 4096-frame renders work locally BOTH windowed and single-shot on the current stack — the 2026-06-28 'single-shot breaks stereo' finding no longer reproduces."
metadata:
  type: project
---

Measured 2026-08-26 on the render server (`SAO/.venv`, torch 2.14 / ROCm 7.14 runtime, CK
flash-attn), medium-base, 378 s = 4070 latent frames, two adapters resident throughout:

| path | wall | VRAM peak | L/R corr | dead channels |
|---|---|---|---|---|
| windowed `/longform` 30 s/5 s | 20 s | 8.6 GB | +0.911 | none |
| single-shot `/generate` 12 steps | 10.7 s | 9.7 GB | +0.884 | none |
| single-shot 24 steps (seed 7) | ~19 s | 9.7 GB | +0.944 | none |
| single-shot 24 steps (seed 1234) | ~19 s | 9.7 GB | +0.862 | none |
| single-shot 24 steps (seed 99999) | ~19 s | 9.7 GB | +0.891 | none |

**The 2026-06-28 finding is STALE.** It recorded single-shot 4096 as corr ~0 with a channel silent
for minutes, for the pure base model too, and concluded medium-base "must be rendered windowed".
That does not reproduce across 4 independent single-shot renders: whole-file corr +0.862..+0.944,
per-minute +0.86..+0.97, no near-dead channel in any minute of any render. ONE honest caveat: seed
1234's FIRST minute reads +0.50 — wide, not broken (both channels well above the dead threshold),
but it shows the opening minute is the most variable, which is where you would look first if a
collapse ever returns. Most likely the stack — that result was on `stable-audio-3/.venv` (torch 2.10 / ROCm 7.2.3);
this is torch 2.14 / ROCm 7.14 with CK flash-attn. Cause NOT isolated, so treat this as "does not
reproduce on the current stack", not as an explanation.

Practical: single-shot is FASTER (no overlap re-render) and fits easily; windowed still edges it on
correlation at matched steps and stays the default for prompt-arc work. `MAX_DURATION_SEC = 378.0`
in `eval/explorer_render_server.py` caps just under the native 380.4 s / 4096 — a config constant,
not a capability limit. See [[sa3-fulllength-control-render]] for the older, superseded entry.
