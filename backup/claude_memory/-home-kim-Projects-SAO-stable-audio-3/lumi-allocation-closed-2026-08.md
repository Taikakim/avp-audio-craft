---
name: lumi-allocation-closed-2026-08
description: LUMI GPU allocation exhausted 2026-08-23 (4765/5000 hours) — no more compute, only transfers, until a new allocation
metadata:
  type: project
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-23T09:28:20.043Z
---

CONTINUITY reported (AGENT_DIALOGUE.md, 2026-08-23 11:03): `lumi-allocations` reads 4765/0 — 4765
of 5000 GPU-hours used, zero remaining, no further compute possible on project_465003186.
`/scratch` persists ~90 days so nothing already-rendered/trained is lost, but from this point
forward any LUMI activity is pull/transfer only — no new sbatch submissions will run.

**How to apply:** don't propose or craft new LUMI training/render jobs until a new allocation
exists — check with Kim/the fleet first if unsure whether one has landed. Final-day landings
worth knowing about (already pulling/scoring as of this session): ai-music corpus (195.6 GB,
9221 files, Music-Flamingo captioned + BS-RoFormer separated), A12 ep24 (walltime-killed ~ep15,
probe still rendered 2560 cells), A13 mellow-LR AVP full-FT (320 render cells), A11's `dorlor_ab`
factorial (2560 cells, first-ever audition), D14 cross-prompt a2a bracket (`renders/a2a_bracket`,
21 GB, 8 families — see [[experiment-d14-cross-prompt-a2a-scoring]]).

See [[fleet-comms-stay-responsive]] and [[experiment-d14-cross-prompt-a2a-scoring]].
