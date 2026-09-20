# Latent Forge — handout for the implementing team

*Written 2026-09-20 by FLATLINE. Read this before picking up a plan. It says what is ready to build,
in what order, what will bite you, and what is still a question. It does not repeat the spec.*

**Read-first documents, in order:** `docs/sa3-studio/ORIENTATION.md` (the project as a whole, and
Kim's authoritative workflow in §3), then `docs/superpowers/specs/2026-09-15-latent-forge-design.md`
(the design, normative), then the plan you are implementing.

---

## What is ready to build

| Plan | File | Tasks | State |
|---|---|---|---|
| **M1** foundation and shell | `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` | 15 | approved by WINTERMUTE, reviewed, corrections applied |
| **M5** timeline fidelity | `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md` | 12 | reviewed (32 findings, 11 blocking, applied) |
| **M4** PROMPT + SIGMA and ADVANCED SAMPLING | `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` | 12 | reviewed twice (49 findings, 40 blocking, applied) |
| **M2** server foundations | `docs/superpowers/plans/2026-09-15-latent-forge-m2-server-foundations.md` | 15 | assessed buildable — TDD-complete, no scope gaps, needs the GPU box |
| **M3** sampling server | `docs/superpowers/plans/2026-09-15-latent-forge-m3-sampling-server.md` | 4 | assessed buildable — **but see Task 2 below**; needs the GPU box |

**Build order is M1 first, then M4 and M5 in either order.** M1 is the foundation every other plan
consumes; nothing else compiles without it. After those: M10 (a leaf, briefs written but the plan
itself is not), then M6 and M7, then M9. M2, M3, M8 and M11 are WINTERMUTE's, server-side, and need
the GPU box.

Each plan is written for **one task at a time**. An implementing agent sees a single `### Task N`
section and can look nothing up, which is why every task restates the interfaces it consumes. Do not
"helpfully" read ahead and merge tasks — the restatements are the contract, and where two tasks
disagree the plan's **Normative names and decisions** block wins over both.

**The server track (M2, M3, M8, M11) is WINTERMUTE's and needs the GPU box.** M2 and M3 were
assessed on 2026-09-20 and are buildable: M2's 15 tasks are TDD-complete with no scope gaps, and
eighteen of their claims about the existing server were checked against `explorer_render_server.py`
and all held. Two things to know before running them:

- **M3 Task 2 is the one task in either server plan that requires reconstruction rather than
  transcription.** Nine lettered edits into the live 2292-line server, four ending in prose — edit
  (j) restructures `/schedule` and says "keep the existing `try:`" without showing the merged
  function. The anchors are all real, but budget care here; it touches the render path four
  milestones depend on.
- **Every contract fixture comes from one GPU-gated task at the end of M2** (Task 15's
  `record_fixtures.py`), and four of the nineteen are recorded conditionally — they skip silently if
  no crops are listed or the generate job returns no `urls`. **Check you have 19 files, not 15**,
  before telling the client side the fixtures have landed.

---

## Things that will bite you

These are all paid-for. Each one cost a debugging session, a critic round, or a green test that could
never have worked.

**The `$state` proxy rule.** Pushing an object into a `$state` array deep-proxies it; the local
reference you built is a dead handle and mutating it does nothing. Any store method that appends must
return `arr[arr.length - 1]`, never the object it constructed. This silently ate a clip trim once —
the duration simply stayed 47.

**`getComputedStyle().getPropertyValue("--token")` returns the token stream, not a colour.** An
unregistered custom property is not resolved, so you get back the literal string `oklch(78% 0.08 250)`.
That is fine to hand straight to `ctx.fillStyle`, which accepts it — and **fatal if you parse channels
out of it**. A digit regex turns that string into `rgb(78, 0, 250)`, an indigo. So: flat canvas
colours come from `getComputedStyle`; a **ramp** builds its own `oklch()` string and interpolates per
channel, because a ramp needs channels and a token stream has none.

**In jsdom, seed tokens inline.** Measured, not assumed:

| how the token was set | what `getPropertyValue` returns |
|---|---|
| a `<style>` block on `:root` | `oklch(90%0.012 240)` — the space after `90%` is eaten |
| inline on the element or an ancestor | exact |
| never defined | `""` |

A test that seeds from a stylesheet and asserts an exact string fails for a reason unrelated to your
code. And `ctx.fillStyle = ""` is a **silent no-op that leaves the previous colour**, so a canvas
component reading tokens needs a per-token fallback — in the app `tokens.css` is loaded and it never
fires, but a bare render paints garbage.

**An abort listener added after the signal already fired never runs.** Check `signal.aborted` before
registering one, or the promise never settles. This was a real green-looking test that hung.

**SAME latents are not translation-invariant.** A latent is valid only at the offset it was encoded
at; a sub-frame roll moves 212 of 256 dimensions. Re-encode, never reposition. The latent frame is
44100/4096 = 92.9 ms, and it constrains **nothing** about audio-domain placement — it is drawn on the
ruler and shown in readouts, and it never snaps anything.

**The timeline is audio.** Preview is not the output; it exists to check onset and downbeat
alignment. Only RENDER/MIXDOWN commits a real latent operation, server-side.

---

## Known limitations you should not try to fix

**The sigma graph is behind the server until M3 lands.** Today's `/schedule`
(`eval/explorer_render_server.py:1009-1062`) reads only `steps`, `duration`, `sigma_max` and
`dist_shift` — it **ignores `schedule` and `sampler_type` entirely**. So every shape charts the model
curve, and ρ, STEPPED, PLATEAUS and TILT move nothing on it. M4 sends the full body anyway (so M3
needs no client change) and the pane displays `schedule shape is charted from M3 onward`.

Do **not** compute the curve locally to cover the gap. §5.3 says the canvas never computes σ, and a
graph that quietly disagrees with the server is worse than one that admits it is behind.

**`/schedule` needs `duration` and M1's client cannot send it.** The model shape's dist shift is
length-dependent (`latent_len = ceil(duration·SR/DS)`), so omitting it charts the server's 47 s
default whatever LENGTH says. M4's Task 4 therefore calls `/schedule` directly instead of through
`forgeApi.schedule` — §6 freezes only `/forge/*` and says to keep the pre-existing routes in their
own module. **`forgeApi.schedule` in M1 T5 is dead and wrong; do not call it.**

**Module ids are kebab-case** (`advanced-sampling`). M1 declares `ModuleId` twice, incompatibly —
kebab in T7's view store, camel in T12 — and the plans follow the view store, because that spelling
is what persists into the project JSON's `ui.modules`. Awaiting WINTERMUTE.

---

## Open questions — do not decide these unilaterally

All are with WINTERMUTE (see `flatline.wintermute.log`). Each has a shipped reading, so nothing is
blocked; but if you find yourself needing a different answer, ask rather than change it.

1. **`ForgeClip.previewAudio`** — M5 T10 needs somewhere to hang the stretched preview, but
   `ForgeClip` is pinned by §9.2 and read by M7's v1→v2 converter, so adding a field is a spec change.
2. **The downbeat-coincidence window** — §4.3 says one 32nd note, linear; the drawing's `_dbColor`
   uses a quarter-beat with a `^0.7` ramp. Factor of two plus a different curve. M5 ships the spec's.
3. **`downbeats_sec`'s timebase** — `/forge/analyze` returns it unstretched at `native_bpm` while
   `offset_sec`/`dur_sec` are stretched (§7.3). One line either way, but it belongs in M1's
   `types.ts` doc comment so it cannot drift.
4. **`RenderSettings` has no length field** — §4.5's `LENGTH s` lives in the tab's state, so a
   `render` preset cannot recall the length it was made at, which §9.3 arguably requires.
5. **M1's two `ModuleId` declarations** — one has to go.

---

## If you are splitting a plan across parallel agents

M4's twelve tasks were written by three agents that could not see each other. Every **type-level**
name they shared agreed — stores, interfaces, function signatures, component props. **Every single
break was in the DOM contract**: a `data-canvas` two tasks asserted and none emitted, a `data-col`
emitted twice so Playwright's strict mode failed, missing `aria-label`s that made three assertions
match nothing, and four `HELP` ids that do not exist in M1's table.

Two cheap countermeasures, both now proven:

- **Put a `data-*` and `HELP`-id table in the plan's Normative-names block**, not just the type names.
  It would have caught all four of those classes before a critic had to.
- **Count every `it(` block mechanically at the end**, and compare against every stated "Expected:"
  gate. No single agent can see a stale cross-agent count: Task 12 claimed Task 8's suite was 21,
  written before a later fix cut it to 16.

And the ordering lesson: **run the critic before the writers, not alongside them**, when the writers
depend on what it is reviewing. Running them in parallel once let a writer faithfully re-extract an
overlap bug the critic had just made me fix — it had read the pre-fix version.

**A critic pass is not optional.** Across three rounds it has returned 17, 32 and 49 findings on work
that had already been called done, and it has never once come back empty. Budget for it as part of
the milestone.
