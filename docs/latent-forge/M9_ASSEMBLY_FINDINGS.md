# M9 assembly pass — findings by FLATLINE (not a critic pass)

*2026-09-27. Found while assembling, before the two critic passes reported. Each is fixed or has a
decided fix; none is waiting on anyone.*

## Fixed before assembly

**A1. `projectSerializer.svelte.ts` had two different paths. BLOCKING — fixed.**
Writer B's Task 6 cited `latent-forge/src/lib/stores/projectSerializer.svelte.ts` in three places.
M7 (`docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md`, 4 occurrences) and
Writer A's Task 3 (3 occurrences) both use `latent-forge/src/lib/forge/projectSerializer.svelte.ts`.
Task 6 would have edited a file that does not exist. All three rewritten to `forge/`.

**A2. Task 8's gate arithmetic was one short. Would have landed red — fixed.**
`previewActions.test.ts` specifies 22 `it()`; the gate said `Tests  21 passed (21)`. The task total
said `Tests 39 passed (39)` against a breakdown of 22 + 6 + 5 + 7 = 40. Both corrected, and the
per-file expectation line updated from 21 to 22.

## Corrected

**A3. WITHDRAWN. My first reading of this was wrong; the critics are right. Task 4's `drawPeaks`
call is a real bug and Known-incomplete item 5 must NOT be struck.**

I originally resolved Task 10's Known-incomplete item 5 — "`drawPeaks`' signature disagreement
between M5 T10's three-arg call and Writer A T4's four-arg one, one of the two is wrong" — as a
false alarm, on the grounds that the real v1 source declares a fourth parameter with a default:

```ts
// sa3-studio/src/lib/waveform.ts:80-84
export function drawPeaks(
  canvas: HTMLCanvasElement,
  peaks: Peaks,
  color: string,
  opts: { background?: string } = {},
```

That much is true, and it does mean M5 T10's `drawPeaks(canvas, peaks, color)` is valid. But I
checked only the **arity** and never looked at what Writer A actually passes. Writer A's Task 4,
Step 8 writes:

```ts
    if (peaks !== null) drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height);
```

That is a `CanvasRenderingContext2D` where an `HTMLCanvasElement` belongs, and two numbers where a
colour string and an options object belong. It is wrong on the first argument and on the last two —
the optional fourth parameter rescues nothing. Both critic passes found it independently, and both
ranked it BLOCKING: the MIXDOWN waveform never draws and `npm run check` fails.

**Correct resolution:** Task 4 Step 8's call is the defect. Fix it to M5 T10's form,
`drawPeaks(canvas, peaks, color)`, passing `canvasEl` rather than its context. Item 5 stays in
Known incomplete until that fix lands, then goes away because the disagreement is settled — not
because it was imaginary. Writer B's open question 5 is likewise a real question with a real answer,
not a question to strike.

**The lesson worth keeping:** "the signature tolerates N arguments" is not the same claim as "this
call site is correct". Checking arity alone let me file a live blocking bug as resolved.

## Resolved — no change needed
**A4. Known-incomplete item 7 is already satisfied.**
It asks the assembly to check that Writer A T3 *stated* the `workKey`-includes-`renders` decision
rather than only implementing it. A's Open question 5 states it explicitly, with the rationale in
Task 3's WHY and the opposing reading named. Item 7 can be marked satisfied rather than carried.

## Open — fix decided, applied after the critic passes report

**A5. Writer B's Open questions 1-6 are cited by number but never enumerated. BLOCKING for the
handover, not for the code.**
Task 6 cites "Open question 1" (twice) and "Open question 3"; Task 7 cites "Open question 2" and is
itself cited later for questions 2 and 5; Task 6's HELP step cites "Open question 6". No section
anywhere lists B's 1-6 — Writer B's first run ended at the budget line before writing one, and the
continuation run started its list at 7. So five questions exist only as forward references.
**Fix:** reconstruct 1, 2, 3, 5 and 6 from their citation sites (they are each stated in prose where
cited) and write the missing list. Number 4 was never used — say so rather than leaving a hole.

Reconstructed from the citation sites:
- **B1** — the OP's home on `ForgeClip` and its §9.2 serialisation (Task 6, lines citing "so the two
  halves of M9 do not ship two structurally identical types" and the `clips[]` amendment).
- **B2** — preview playback vs the timeline transport keeping the playhead (Task 7).
- **B3** — no bend-op editor, so `bendOps` is `[]` and `renderBlock` honestly refuses `bend` (Task 6).
- **B4** — never used.
- **B5** — the `drawPeaks` signature. A real question with a real answer (see A3): Writer A T4 calls it wrongly. Carried, not struck.
- **B6** — the `strings.test.ts` total must be recounted by the assembly, not asserted by a writer
  (Task 6's HELP step). This is the same question as Writer A's Open question 6.

**A6. The two open-question lists collide in numbering.**
Writer A's section numbers 1-9; Writer B's tasks number 1-15 in a separate sequence. In the
assembled plan a bare "Open question 7" is ambiguous — A's 7 is M2 T15's fixture-count discrepancy,
B's 7 is `dur_sec` on a REPLACE CLIP. Every in-text citation inside Tasks 6-10 means B's list and
every one inside Tasks 1-5 means A's, which is consistent but nowhere stated.
**Fix:** prefix the two lists `A1-A9` and `B1-B15`, add a consolidated index at the end of the plan,
and state the convention once. Do not renumber in place — the cross-references are load-bearing and
a mass renumber is how this kind of document gets quietly corrupted.

**A7. Several tasks state per-file gates but no task-level total.**
Tasks 1, 2, 6, 8, 9 and 10 each end with a task total. Tasks 3, 4, 5 and 7 state per-file gates only.
That is not wrong — the per-file numbers are what `vitest` prints — but the milestone's own
discipline is a per-task total that a reviewer can check without adding up. **Fix:** add the missing
four totals, taken from a mechanical count, not from arithmetic on the prose.

## Mechanical counts at assembly (`awk` over the assembled plan)

| task | `it()` | `it.skipIf` | Playwright |
|---|---|---|---|
| 1 | 47 | 4 | — |
| 2 | 16 | — | — |
| 3 | 17 | — | — |
| 4 | 21 | — | — |
| 5 | 18 | — | — |
| 6 | 23 | — | — |
| 7 | 14 | — | — |
| 8 | 40 | — | — |
| 9 | 27 | — | — |
| 10 | 11 | 4 | 6 |
| **total** | **234** | **8** | **6** |

Task 9's 27th `it()` is a quotation of M7's existing
`it("the INPAINT OVERLAP button is present, enabled, and a no-op this milestone")` inside its WHY
section, at the file's line 26 — well above Step 1 at line 202. **233 tests actually run.** The
in-file gate of 26 is correct; a naive `grep -c` is not. Anyone re-counting must exclude it.
