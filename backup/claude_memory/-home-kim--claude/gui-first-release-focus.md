---
name: gui-first-release-focus
description: "Kim 2026-10-29: next deliverable = first public version of the inference GUI, gated on 4 LatCH heads (chroma, onset, hardness, RMS) trained with good settings; plus a clean user-facing release repo separate from the private dev repos"
metadata:
  node_type: memory
  type: project
  originSessionId: de0a3788-0bd8-4798-abdc-e7ac96d27bc6
  modified: 2026-10-29T08:19:12.909Z
---

**Kim, 2026-10-29 (direct, to THE-FINN):** the near-term deliverable is a **first version of the GUI**
(the inference GUI W is building: weights picker, EMA/ckpt probe via C's `eval/ckpt_weights.py`), out
"as soon as" these heads are trained with good settings:
- **chroma** (E13 winner: d512/depth 8, ModularOptimizer lr 1e-3, ep10; hpcp revived by E21's A=0 bin fix)
- **onset**, **hardness**, **RMS** (the energy heads), which are still being experimented with.

**DECIDED (Kim, 2026-11-03):** SA3 Medium, both `medium-base` and post-trained `medium`. **Bring the project AS IS**: no feature pruning, no upstream port ("otherwise it becomes a mess burning tokens"); the real code job is the 76 hardcoded paths. Details: `SAO/docs/release/clean-repo-requirements.md` section 0. Do not reopen upstream-as-a-dependency for v1. Kuang runs the Intel and RTX machines, unreachable from the desktop, contact only via GitHub; the Intel test was never recorded.

**Update 2026-11-03 (Kim):** team discussion, DMs, tasklist, experiments and other dev files stay OUT (stale .md references are a later revision). And FIRST look at what upstream added and at aligning with it, so 'do not reopen upstream' above no longer holds: Kim is excited by the driver-free CPU runtime. Findings: requirements doc section 0b: 6-file trial merge; upstream's tflite runs Medium on CPU, post-trained only, no LatCH or FiLM hooks; no C++ source in the tree.

**Spikes done 2026-11-03 (doc section 0c):** LiteRT Medium on CPU about 2x realtime, AVP DoRA works on the legacy fp32 file; trial merge on local branch `align/upstream-2026-11`, worktree /home/kim/Projects/sa3-align, bit-identical at strength 1 and 0, GPU latents bit-identical too (05:03), branch not adopted yet; head gradient exports to ONNX at cosine 1.0000. Kim recalls LatCH works on the 8-step sampler, a bit weird. First full torch-free steered renders done 2026-11-03 (doc section 0d): right direction in 9 of 10, one gain-2048 runaway; not gated, not heard, head goa-trained.

Earlier framing, superseded where it conflicts: **Repo decision pending:** all dev repos except fusion-optimiser go PRIVATE (Kim is flipping them).
Users need ONE clonable repo for the GUI that does NOT carry fleet files, internal docs, test scripts,
DM logs, etc. Kim asked whether to make a fresh SA3 / stable-audio-tools fork from scratch. My
advice: don't fork again. Make a new **release repo** that depends on upstream SA3 + a small extracted
`latch-core` package (the dedup MASTER §1 already wants), weights on HF, and a curated export step
from the dev monorepo. Await Kim's choice before building anything.

**Rights answer (Kim, 2026-10-29):** the release heads get RE-TRAINED on the **AVP augmented set** (`Kosmos/latents/latents_avp`, 2,393 crops, timeseries present). Over time Kim adds permissively licensed music. The goa-trained heads stay private. Recorded in MASTER §4 rights tiers.

**Scope + WHY (Kim, 2026-10-29):** the release ships ONLY weights trained on Kim's own music (heads AND fine-tunes). First release can be rough, and later releases iterate on it. The goal is **speed**: get it public before big companies do, so the methods become **unpatentable prior art**, and hopefully **kickstart a hobby scene**. So dated public disclosure of the METHODS matters as much as the code. Favour shipping early over polish, and don't let release-repo design turn into a rabbit hole.

Supersedes the 2026-08-12 "two-week deliverable focus" (AVP model + density adapter + pitch head),
which expired 08-26 and was deleted. Constraint unchanged: weights trained on commercial goa music are
NEVER published (MASTER §4 rights tiers), so the public GUI ships the AVP-retrained heads (above).
Relates to [[kim-max-to-pro-downgrade-2026-08]], [[feedback-lightweight-first]].
