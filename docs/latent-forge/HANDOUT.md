# Latent Forge — handout for the implementing team

*Written 2026-09-20 by FLATLINE, reconciled 2026-09-22 against WINTERMUTE's `7193ba9`. Read this
before picking up a plan. It says what is ready to build, in what order, what will bite you, and
what is still a question. It does not repeat the spec.*

**Where this document and a plan's own "Normative names and decisions" block disagree, the plan
wins** — and where a plan and M1's table disagree, M1's table wins. This is a map, not a contract.

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
| **M3** sampling server | `docs/superpowers/plans/2026-09-15-latent-forge-m3-sampling-server.md` | 4 | assessed buildable — Task 2's edit (j) now written out in full; needs the GPU box |
| **M10** statistics view | `docs/superpowers/plans/2026-09-21-latent-forge-m10-statistics.md` | 7 | reviewed (6 findings, 2 blocking — both were pre-existing M1 defects, not M10's, and both are now fixed in M1) |
| **M6** chroma | `docs/superpowers/plans/2026-09-22-latent-forge-m6-chroma.md` | 11 | reviewed **twice** (2 findings then 17, 5 of them blocking — all applied), then reconciled against WINTERMUTE's three rulings (directed-distance `INTERVAL_W`, single fold12, superset fixture check), 208 tests, counts verified |
| **M7** chains / mix / library / sessions | `docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md` | 10 | written and assembled, 124 tests, counts verified — **not yet reviewed by a critic.** Treat as unreviewed until that pass has run |
| **M9** rendering | *not yet a plan* | — | last; needs M7 |

**Build order is M1 first, then M4 and M5 in either order.** M1 is the foundation every other plan
consumes; nothing else compiles without it. After those: M10 (a leaf — needs only M1 and fixtures),
then M6 and M7, then M9. M2, M3, M8 and M11 are WINTERMUTE's, server-side, and need the GPU box.
**M10 is not a pure leaf after all** — M6 reuses `dequantiseScaled` from M10 Task 1, built there
deliberately for it, so M10 T1 must land before M6 T2.

Each plan is written for **one task at a time**. An implementing agent sees a single `### Task N`
section and can look nothing up, which is why every task restates the interfaces it consumes. Do not
"helpfully" read ahead and merge tasks — the restatements are the contract, and where two tasks
disagree the plan's **Normative names and decisions** block wins over both.

**The server track (M2, M3, M8, M11) is WINTERMUTE's and needs the GPU box. It is UNBLOCKED as of
2026-09-21 (`7193ba9`).** M2 and M3 were assessed on 2026-09-20 and are buildable: M2's 15 tasks are
TDD-complete with no scope gaps, and eighteen of their claims about the existing server were checked
against `explorer_render_server.py` and all held. Kim held the run until two fixes landed; both have:

1. **M3 Task 2 edit (j) is now a complete `async def schedule(request: Request):`** rather than nine
   lettered edits ending in prose. Nothing is left to reconstruct. The task body also names the two
   differences from today's function: the `steps`/`duration`/`sigma_max` parse moves above the
   `MODEL is None` check so an array schedule charts during a backbone rebuild, and the dist_shift
   resolution keeps its own `try:` so the legacy `float(req["dist_shift"])` path still answers 400
   rather than 500. This sits on the render path M4, M5, M8 and M9 all use, which is why it was
   worth holding for.
2. **M2 Task 15's `record_fixtures.py` now has an `EXPECTED` tuple, a `RECORDED` set and a non-zero
   exit naming what it skipped.** Four of the fixtures are conditional — they skip silently when no
   crops are listed or the generate job returns no `urls` — so a half-working run used to exit 0
   looking like success. **It is TWENTY fixtures, not nineteen**; the earlier count here was wrong
   when written. Step 6's expected output says twenty. Do not tell the client side the fixtures have
   landed without counting 20.

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

**Seven M1 names changed on 2026-09-21; a plan written before that may still cite the old ones.**
Fixed in the view store (M1 T7) and correct everywhere in M4/M5/M6/M10 as of this reconciliation:
`view.view` → **`view.screen`** (and `setActiveLane` is now a real setter beside `setView`);
`TerminalMode`'s middle mode `"normal"` → **`"pane"`**; `type BottomTab` → **`BottomTabId`**,
declared once in T7 and re-exported by T11 (not the other way round — T7 is built first, so its own
vitest run would fail); `BOTTOM_TABS` → **`BOTTOM_TAB_IDS`**; and `ModuleId` is **kebab, declared
once, with seven members** — the five spec modules plus `legacy-inspector` and `legacy-server`, which
are real ids T9 mounts. `MODULE_IDS` (restoreUi's whitelist) has all seven; T12's `MODULE_ORDER` has
the five, narrowed through `SpecModuleId`. Also: M1 T13's `CentreColumn` now renders Task 9's own
`{@render centre()}` / `{@render bottom?.()}` and never constructs a `BottomPane` itself.

**A payload key the server does not read is silently ignored.** M1's handmade job fixture sent
`duration_sec` inside a generate payload; `_generate_impl` reads `duration`, so a fixture-shaped
payload would have quietly rendered 47 s instead of 45. Fixed in both fixtures on 2026-09-21. The
lesson generalises: this server 200s on an unknown key rather than rejecting it, so a wire-name typo
shows up as a wrong-length render, not an error.

**A `Float32Array` value compared against a float64 threshold literal is off by a rounding step.**
`Math.fround(0.08) = 0.079999998`, which is strictly **less than** the literal `0.08`. So a guard
written `if (value < THRESHOLD) continue;` excludes a value the caller set to exactly the threshold —
the opposite of the documented rule. Round the threshold the same way the data is stored
(`Math.fround(THRESHOLD)`) so the comparison happens in one precision. M6 hit this in `matchFrame`,
and it cascaded: the same rounding decided where a flat-topped scan's first tied maximum fell, so two
apparently independent test fixes turned out to be coupled.

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

**`/schedule` needs `duration`.** The model shape's dist shift is length-dependent
(`latent_len = ceil(duration·SR/DS)`), so omitting it charts the server's 47 s default whatever
LENGTH says. M1 T5's `forgeApi.schedule` was corrected on 2026-09-21 and now takes `duration` as a
required body key plus an `AbortSignal`, returning the route's nine fields — **the earlier warning
that it was "dead and wrong" no longer applies.** M4's Task 4 still calls `/schedule` through its
own `scheduleClient.svelte.ts`, because §6 freezes only `/forge/*` and says to keep the pre-existing
routes in their own module, and because that module already owns the debounce, cache and abort. The
two now agree field for field; either would work.

---

## Open questions — none are currently open

**All five closed on 2026-09-21 by WINTERMUTE, plus three more found in the same pass.** The live
source for each is **M1's own "Normative names and decisions" table**, which now carries a row per
decision; this list is a pointer, not a second copy that can drift.

| was open | decided |
|---|---|
| `ForgeClip.previewAudio` | **in-memory only**, §9.2 unchanged — a cache of §7.3's analyze→stretch step, re-derived on load. Persisting it would point a reopened project at a render that may be gone. M5 T10 stands as written; M7's converter ignores it |
| the downbeat-coincidence window | **the spec's window, the drawing's ramp.** §4.3 now states it once and exactly: `w = (60 / bpm) / 8`, `t = max(0, 1 - dt / w) ** 0.7`, interpolated per channel in OKLCH. `downbeatColor(t)` is unchanged — only the `t` fed to it. M5 T2 is updated |
| `downbeats_sec`'s timebase | **source seconds, unstretched, at `native_bpm`**, unlike `start_sec`/`offset_sec`/`dur_sec`. Documented on the field in M1 T3; scale by the clip's stretch factor before drawing or snapping |
| `RenderSettings` has no length field | **`duration_sec` added** (§4.5 LENGTH, ≤ 184, default 47.556 = T:512 exactly). **Wire name stays `duration`.** Ignored on an A2A target. M4 T9/T10 are updated: LENGTH is per-target settings state, owned by the tab |
| M1's two `ModuleId` declarations | **kebab, declared once in the view store** — and it was three declarations, not two. See the names list above |

Three more found while deciding those, all fixed in M1: the view store's `.view`/`.screen`
mismatch, `TerminalMode`'s `"normal"`/`"pane"` mismatch, and `BottomTabId` being declared in T11
when T7 needs it first. All three are in the names list above. M10's statistics-view Playwright
assertion (bottom pane absent) survives the `CentreColumn` fix — it depends on T13's if/else shape,
not on the Props mismatch — so M10 needed no change.

**If you find yourself needing a different answer to any of these, ask rather than change it.**
The full reasoning is in `flatline.wintermute.log`, entry 2026-09-21 16:55.

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
