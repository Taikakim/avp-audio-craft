# Animation module `lora-a-rotation`: contract for three parallel tracks

Owner: WINTERMUTE (created 2026-10-27). Spec: `docs/superpowers/specs/2026-10-26-help-pane-design.md` section 7, row
`lora-a-rotation`. Used by the glossary entry `lora-a` (`glossary/adapters.json`, CONTINUITY's file: read only).
Reference modules for style and structure: `site/help/viz/qkv-line.js`, `batch-noise.js` (and their tests). Shared helpers:
`lib/kit.js` (loop, realNote, lineChart, svg/el).
Sources of the measured numbers: `docs/training-findings.md` items 3-4, `docs/TRAINING.md` F14, `EXPERIMENTS.md` A14:
on one DoRA run (2026-09-22, the "audition" recipe) A's row space was 99.2% unchanged from step 240 to 1,440, against 35%
for B's column space; A carried about 7% of the step energy; A's norm starts large (about 99 over 229 adapters). With A's
step × 20, A rotated (overlap 0.67 at step 240) but the adapter's product B·A became 2.3 times larger and one 48 s render
went NaN, so the result is confounded. There is no AdamW control.

## The toy (computed live)

A rank-1 adapter on a 2-D input and a 2-D output: `B·A = b aᵀ` (A is a row `a`, B a column `b`). Target change
`T = b* a*ᵀ` with `a* = (cos 70°, sin 70°)` and `b* = (0.6, 0.8)`. Start: `a = (3, 0)` (large, like our A), `b = (0, 0)`
(zero, like our B). Loss `||b aᵀ − T||²` (identity input). Gradients `E = b aᵀ − T`, `g_b = E a`, `g_a = Eᵀ b`.
Each step is fixed-size, as in the Muon family (for a single row or column, orthogonalising = normalising to unit length):
`b −= lrB · f(s) · g_b / |g_b|`, `a −= lrA · mult · f(s) · g_a / |g_a|`, skipping a step whose gradient norm is below 1e-12,
with `f(s) = 1 − s / steps` (linear decay). Constants: steps 300, lrA 0.002, lrB 0.02, early step 50 (the toy's "step 240").
Measured with the reference code (2026-10-27): ×1: A turns 5.7°, overlap(a at 300, a at 50) = 0.995, loss left 0.81,
|B·A| 0.43; ×20: A turns 70.0°, overlap 0.648, loss 0.0000, |B·A| 1.00; |a| stays near 3 (3.00 / 3.13).
At step 0 B is zero, so A's gradient is zero and only B moves: "in the first steps all the learning happens in B".
Limitation the module must state: in this 2-D rank-1 toy B's direction is set by its first step and never turns, so the toy
shows B growing, not B rotating; our run's B kept changing direction (35% unchanged).

## What the reader sees

Two panels side by side (stacked below ~520 px): "A (reads the input)" and "B (writes the correction)". Each shows its arrow
from the origin, a fading trail of where the arrow's tip has been, and the target direction as a dashed line (labelled
"target direction"). A small chart below: loss over steps (`lineChart`, both the current run and, faint, the other setting's
run once it has been played, so ×1 and ×20 can be compared). Controls: a group "A's step size" with buttons "×1" and "×20"
(aria-pressed), and "Replay". Changing the setting restarts. One training step per animation frame (300 frames ≈ 5 s), then
idle.
Readouts: step "n of 300"; "A has turned <x>°"; "A's direction since step 50: <p>% unchanged" (100 × overlap, the same
measure as our run's 99.2%); "loss left: <v>"; "size of B·A: <v> (target 1)". A line under the readouts gives the run numbers:
"In our run: A 99.2% unchanged, B 35%. With A's step × 20, A turned, but B·A grew 2.3 times and one render failed."

## Track A: maths (`site/help/viz/lib/lora-rot.js` + `site/help/viz/tests/lora-rot.test.mjs`)

Pure functions, no DOM, no imports needed. Exports, exactly:

```js
export const ROT = { steps: 300, lrA: 0.002, lrB: 0.02, aStart: [3, 0], targetDeg: 70, bTarget: [0.6, 0.8], early: 50 };
export function targetA()                 // [cos 70°, sin 70°]
export function angleDeg(v)               // atan2(v[1], v[0]) in degrees
export function overlap(u, v)             // cos² of the angle between u and v (rank-1 subspace overlap); 0 if either is zero
export function lossOf(a, b)              // ||b aᵀ − T||²_F
export function createRotSim({ mult = 1 } = {})
  // -> { get t(), get done(), get a(), get b(), get aEarly(),  // aEarly: a at step ROT.early (null before it)
  //      trail: { a: [[x, y], ...], b: [[x, y], ...] },        // positions after every step, starting with the start
  //      losses: [...],                                        // loss after every step, starting with the start
  //      step() -> { t, a, b, loss, stepA, stepB } }           // stepA / stepB: length of this step's change of a / b
  // exactly the update rule in "The toy"; no randomness.
```

Node tests (`node --test site/help/viz/tests/`):
1. ×1 after 300 steps: A has turned less than 10°; overlap(a, aEarly) > 0.99; loss > 0.5.
2. ×20 after 300 steps: A's angle is within 2° of 70; overlap(a, aEarly) < 0.8; loss < 1e-3.
3. First step: `stepA` is 0 and `stepB` is lrB (B starts at zero, so A gets no gradient); after it, b points along b*
   (overlap(b, bTarget) > 0.999).
4. |a| stays between 2.9 and 3.3 for both settings at every step (fixed-size steps on a large A).
5. Determinism: two ×1 sims give identical trails.
6. `overlap` is 1 for parallel and antiparallel vectors and 0 for perpendicular ones; `angleDeg([0, 1])` = 90.
If 1 or 2 does not hold with these constants, report the numbers; do not tune silently.

## Track B: the module (`site/help/viz/lora-a-rotation.js`)

Follows `batch-noise.js` / `qkv-line.js` in style: `mount(container, params, help) -> { destroy() }`, `injectStyle`,
`applyColors`, `loop()` (pauses out of view; idle when the run is done; with `help.reducedMotion` nothing moves until the Step
button, and one Step advances 25 training steps), `realNote()` required. Imports only from `./lib/`. Never name a colour in
text (arrow vs target vs trail are told apart by line style and the labels; the chart's two runs by swatches beside "×1" and
"×20"). `help.openTerm` only for ids in the lora-a entry's text (fine not to call it).

DOM contract (track C tests against it; do not rename):
- root `div.vz-rot` with `data-step` (training steps done), `data-mult` (`1`|`20`).
- a `role=group` labelled "A's step size" with buttons "×1" and "×20", `aria-pressed`; a button "Replay".
- `svg.vz-rot-a` and `svg.vz-rot-b`, each with one `line.arrow`, one `line.target`, one `polyline.trail`; the A arrow carries
  `data-angle` (degrees, full precision).
- readouts `#vz-rot-step`, `#vz-rot-turn`, `#vz-rot-overlap` (a percentage), `#vz-rot-loss`, `#vz-rot-ba`.
- `svg.vz-chart` (from `lineChart`) for the loss.
- the "What's real here" note (via `realNote`).
Defaults: ×1. `params` may override: `{mult: 1|20}`; invalid values fall back to 1. Works at 360 px: no horizontal overflow,
text at least 11 px rendered.

"What's real here" content:
- Computed live: a toy adapter with one row in A and one column in B, trained with fixed-size steps (normalised, as Muon-family
  steps are for a single row or column), A large at the start and B zero, as in our adapters.
- From our own runs: on one DoRA run, A's input directions were 99.2% unchanged between steps 240 and 1,440, against 35% for B;
  A took about 7% of the step energy. With A's step 20 times larger, A turned, but the adapter's product grew 2.3 times and one
  render failed, so that result is not clean. We have no AdamW comparison, and an imbalance between A and B is known for
  AdamW too (LoRA+).
- Illustration only: the toy is 2-D with rank 1; its numbers are not our run's; in it B's direction is set by its first step,
  so it shows B growing, not turning; the toy's ×20 run does not grow too large or fail.

For local testing before track A lands, Track B may write a stub `lib/lora-rot.js` that follows the contract, but must NOT
commit it (only `lora-a-rotation.js` is committed).

## Track C: browser tests (`site/help/viz/tests/test_lora_a_rotation_browser.py`)

Use `from vizbrowser import open_page` (never `from conftest import ...`); fixtures `browser` and `base_url` from
`site/help/viz/tests/conftest.py`. Parse attributes with `float()`/`int()`. Tests (`dev.html?m=lora-a-rotation`):
1. Mounts with no console/page errors; `data-mult=1`; both panels; the note "What's real here".
2. `data-step` grows within 1 s; the run finishes (`data-step=300`) within 10 s (polling).
3. At the end of ×1: A arrow `data-angle` < 10; `#vz-rot-overlap` shows a percentage above 99.
4. "×20": `aria-pressed` flips, `data-mult=20`, `data-step` restarts below 50; at the end `data-angle` within 2 of 70 and the
   overlap percentage below 80.
5. "Replay" restarts (`data-step` drops below 50 right after the click).
6. `&rm=1`: `data-step` stays 0 for 1 s; one click on "Step" makes it 25.
7. After `window.__viz.destroy()`, no requestAnimationFrame callbacks are outstanding (RAF_SPY) and the root is gone.
8. Viewport 360 x 740: `document.documentElement.scrollWidth <= clientWidth`.
9. Keyboard: Tab reaches "×20"; Enter on it sets `data-mult=20`.
10. Params: `p={"mult":20}` starts at ×20; `p={"mult":5}` falls back to 1.
11. The note mentions "99.2%", "35%" and "not clean".
Until track B lands these tests fail; that is expected. Verify the file collects (`pytest --collect-only`).

Run browser tests with `/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/` (that directory on its own).

## All tracks

- Header line in every new file: `// Owner: WINTERMUTE (created 2026-10-27)` (`#` in Python).
- Plain JavaScript, no libraries, no CDNs. No storage of any kind.
- Commit with `Misc/agent_commit.sh WINTERMUTE -q -m "<message>" -- <explicit paths>` from the worktree root (`git add` new
  files first); never `-A`. Message ends with the two trailer lines given in the dispatch.
- No push, no merge; WINTERMUTE integrates.
