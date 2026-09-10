# SA3 Studio plan — corrections

*Written 2026-09-10, after the `sa3-studio-plan` workflow (run `wf_91eb340d-2ae`) produced
`SA3_STUDIO_PORT_MAP.md`. Read this BEFORE acting on the plan in that document.*

---

## 1. The load-bearing correction: the render server is in this repo

The synthesized plan is built throughout on the belief that the render server lives in
"the invisible repo", "a repository nobody here can read", and that ten of its response
shapes are inferred from `render_client.py` docstrings. **That is wrong.**

```
avp-audio-craft/eval/explorer_render_server.py     2292 lines, 27 route decorators
avp-audio-craft/eval/test_render_server_models_api.py
```

`avp-audio-craft` **is** SAO — its README opens `# SAO — Audio Generation Pipeline`, so
`~/Projects/SAO` on the Arch box is this repository. The server is readable, editable and
committable by us.

My error, and the third of the same kind in this session: I searched one repo and
generalised. Treat every "X does not exist" in the port map as "X was not found in the
files that agent read".

### The real route table (grepped, 2026-09-10)

```
GET  /info /status /ckpts /presets /presets/{name} /slots /roots /models
     /models/{model_id} /audio/{job_id}/{filename}
POST /presets /ab /slots
POST /generate /a2a_track /a2a_mix /longform /decode /bend
GET|POST /schedule                        (via @app.api_route — easy to miss)
GET  /crops /meta /player_status /decode /source /mix /steer     (lines 2157-2233)
```

Two surprises versus the plan:

- **`/mix` and `/steer` are live on :8056**, not dead and not on a separate player. The
  plan calls the second server "dropped entirely" and the mix/steer surface possibly
  "dead"; in fact the player endpoints (`/crops`, `/meta`, `/decode`, `/source`, `/mix`,
  `/steer`, `/player_status`) are folded into this same process. The plan's
  "SETTLE THE DEAD SURFACE" clarification item is answerable by reading, not by asking.
- **`/schedule` exists** and is `@app.api_route(methods=["GET","POST"])`, calling the same
  `build_schedule` the real run uses. The plan's sigma-chart design stands.

Still genuinely absent, as the plan says: **no `/encode`, no `/inpaint`, no `/jobs`,
no n-way `/mix`, no `/analyze`.**

## 2. What this changes in the plan

| plan item | as written | corrected |
|---|---|---|
| M0 Track B — capture contract via `openapi.json` + logging proxy at the Arch box | needs Kim + GPU box | **read the source.** Still capture golden payloads for regression, but the ten "inferred" shapes are now verifiable by reading, on this laptop, for free |
| M5 job API — "not our codebase and not our calendar" | off critical path for scheduling reasons | **ours.** Can be scheduled on merit |
| M7 latent path — "HARD-BLOCKED on the invisible repo" | last, 3+ weeks, blocked | **not blocked.** `/encode`, `/inpaint` and compose are changes we author here. Still real work, still hard, but a dependency we control |
| Biggest risk #2 — two ops missing in an unreadable repo | co-equal top risk | **substantially downgraded.** The ops are still missing; the unreadability is not |
| Open questions: `max_slots`, whether 3 LatCH slots is a server limit, the chroma data source | "confirm with the server author" | **answerable by reading `explorer_render_server.py`** |

**What does NOT change:** the first and largest risk stands untouched. Nobody has tested
whether audio-domain alignment predicts latent-domain result quality well enough to justify
a preview stage. That is still the project's core premise and M2 is still the milestone that
tests it. Keep M2 early; it remains the highest-information step in the plan.

The timeline-first spine also survives — it never depended on the server being unreadable.

## 3. First actions tomorrow

1. **Read `eval/explorer_render_server.py` (2292 lines) and rewrite the plan's contract
   section from source.** Highest value per token in the whole project: it converts ~10
   inferred response shapes into fact, settles the dead-surface question, and re-scopes M5
   and M7. Do this before anything else.
2. **Re-scope M7 and M5** now that they are ours.
3. **Decide the chroma data source** (M8's blocker): SAME head forward pass per frame, or a
   locally-computed audio chromagram cached at analyze time. Note `mir-feature-extraction`
   already has the extractor — `scripts/gen_same_chroma_ts.py` and
   `src/harmonic/same_chroma.py`, merged at `6c14e8b` — plus `CHROMA_HANDOFF.md` with the
   bit-exact recipe.
4. **Keep M2 where it is.**

## 4. Status of the plan itself — read this before trusting it

- `SA3_STUDIO_PORT_MAP.md` is **agent output that no human and no adversarial pass has
  verified.** Its Part 1 maps are mechanical inventories and should be reliable; Part 2's
  plans contain reasoning that has already been shown wrong once (above).
- **The two critic passes never ran.** The run was parked for token budget after the
  synthesis landed. Resume with
  `Workflow({scriptPath: ".../sa3-studio-plan-wf_91eb340d-2ae.js", resumeFromRunId: "wf_91eb340d-2ae"})`
  — ten cached agents replay free, only the critics run. Note the completeness critic was
  pointed at exactly the class of error found above.
- The plan's own specific claims — `_FORM_IDS` is a 30-tuple, `steering_states` is 35
  positional values, `LATCH_SLOTS=3`, gain defaults 512/2048, `gamma` default 0.3 breaking
  bit-reproducibility, the `(1−σ)/Σ(1−σ)` guidance-budget skew — are cited to specific files
  and look sound, but none has been independently checked. Spot-check before building on any
  of them.

## 5. Design-handoff corrections worth carrying forward

The synthesis found these independently and they match what we established in conversation;
they are the ones I would treat as settled:

- **No transport anywhere** in the design — no play/pause/stop, no `<audio>`, no scrub. For
  a tool whose stated purpose is auditioning alignment, this is the fatal gap.
- **No re-encode / staleness concept.** SAME latents are not translation-invariant (a
  sub-frame roll moves 212/256 dims; phase is ~2-plane SO(2) rotations only to ~7 kHz), so a
  latent is valid only at the offset it was encoded at. Clips need
  `latentState ∈ {none, valid, stale}` with `encodedAtOffsetSec`.
- **Placement stays audio-domain** — do not quantise to the 92.9 ms latent frame — but
  serialise position as frame + sample residual so the commit step is exact.
- **The σ apparatus (SHAPE/ρ/λ/STEPPED/TILT) is from a different backend.** The real control
  is `dist_shift`. Cut the invented surface.
- **Per-clip render state is missing** — prompt/steps/cfg/seed/sampler live in one global
  block in the prototype. The design's own `NOTE FOR THE REAL APP` says to fix this.
- **The design's data is all deterministic FNV-hash-of-filename synthesis**, including
  downbeat phase. MATCH DOWNBEATS is demonstrated aligning hashes.
- **The statistics view is a downgrade** of the working Dash Analysis tab.
