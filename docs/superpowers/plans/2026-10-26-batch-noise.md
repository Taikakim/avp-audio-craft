# Animation module `batch-noise`: contract for three parallel tracks

Owner: WINTERMUTE (created 2026-10-26). Spec: `docs/superpowers/specs/2026-10-26-help-pane-design.md` section 7, row `batch-noise`.
Used by the glossary entry `momentum` (`glossary/optimisers.json`, CONTINUITY's file: read only).

## What the reader sees

A 2-D loss valley (elongated bowl, minimum at the centre). A ball descends it with gradient steps. At the ball, one bold
arrow shows the true step direction (minus the true gradient), and a cloud of thin arrows shows the step directions that
24 different minibatches of the chosen size would give. Controls:
- **Batch size** slider, 9 stops: 1, 2, 4, 8, 16, 32, 64, 128, 256.
- **Momentum** on/off. On: an exponential moving average with beta 0.9 (`m = 0.9 m + 0.1 g`, step along m). Off: plain steps.
- **Noise level**: "Early in training" / "Late in training" (our two measured levels).
- **Replay**.
A dashed reference path shows where the ball would go with no noise at all.

Readouts, at the ball's current position:
- signal-to-noise ratio of one minibatch gradient;
- the half-batch cosine (the number we measured in our runs) at this batch size;
- with momentum on: the SNR after averaging, labelled "at most", because the 4.4x gain assumes the signal holds still;
- a tag: at batch 64 "measured at this batch size"; at every other size "extrapolated with the noise model (1/sqrt(batch))".

Ruling (WINTERMUTE): the spec labels only sizes below 64 as extrapolated; sizes above 64 come from the same model and get
the same tag. Cost if wrong: one word on the page.

Defaults: batch 8, momentum off, noise level late (our runs train at batch 1 to 16; the entry is about momentum, so the
reader turns it on). `params` may override: `{batch: <one of the 9>, momentum: true|false, stage: 'early'|'late'}`;
invalid values fall back to the defaults.

## Track A: maths (`site/help/viz/lib/valley.js` + `site/help/viz/tests/valley.test.mjs`)

Pure functions, no DOM. Imports from `./noise.js` (`mulberry32`, `makeGauss`, `CALIBRATION`, `sigmaForHalfBatchCosine`,
`halfBatchCosine`, `minibatchNoiseStd`). Exports, exactly:

```js
export const VALLEY = { a: 1, b: 8, start: [-2.6, 0.9], lr: 0.08, steps: 240, cloudSize: 24, beta: 0.9 };
export const BATCHES = [1, 2, 4, 8, 16, 32, 64, 128, 256];
export function loss([x, y])            // 0.5 * (a x^2 + b y^2)
export function grad([x, y])            // [a x, b y]
export function sigmaForStage(stage)    // 'early' | 'late' -> per-example noise std sigma1, calibrated so that at
                                        // VALLEY.start, batch CALIBRATION.batch (64), the half-batch cosine equals
                                        // CALIBRATION[stage]; gRms = |grad(start)| / sqrt(2). Throws on unknown stage.
export function noisyGrad(p, sigma1, B, gauss)       // grad(p) + minibatchNoiseStd(sigma1, B) * gauss() per component
export function sampleCloud(p, sigma1, B, n, gauss)  // n independent noisyGrad samples, array of [gx, gy]
export function readouts(p, sigma1, B, beta)
  // -> { snr, halfCos, momentumSnr, measured }
  // snr = |grad(p)| / (minibatchNoiseStd(sigma1, B) * sqrt(2))
  // halfCos = halfBatchCosine(sigma1, B, |grad(p)| / sqrt(2))
  // momentumSnr = beta > 0 ? snr * sqrt((1 + beta) / (1 - beta)) : null
  // measured = (B === CALIBRATION.batch)
export function noiselessPath(steps = VALLEY.steps)  // plain gradient descent from start, array of steps+1 points
export function createValleySim({ stage = 'late', batch = 8, momentum = false, seed = 11 } = {})
  // -> { sigma1, batch, beta, get t(), get done(), get pos(), path,   // path: array of visited points incl. start
  //      step() -> { t, pos, trueGrad, usedGrad, loss } }             // usedGrad = the momentum buffer when on
  // momentum on: m = beta m + (1 - beta) g; pos -= lr * m. Off: pos -= lr * g. done when t >= VALLEY.steps.
  // Same seed, same arguments -> identical path.
```

Node tests (`node --test site/help/viz/tests/`), each a real check:
1. Calibration round trip: `halfBatchCosine(sigmaForStage(s), 64, |grad(start)|/sqrt 2)` equals `CALIBRATION[s]` (1e-12), both stages.
2. `readouts` SNR scales with sqrt(batch): ratio 256 vs 1 is 16 (1e-9); `measured` true only at 64.
3. `momentumSnr / snr` = sqrt(19) at beta 0.9; null with momentum off.
4. `noisyGrad` empirical std over 20,000 draws matches `minibatchNoiseStd` within 3%.
5. `noiselessPath` converges: final loss < 1e-3 * loss(start).
6. Determinism: two sims with the same arguments give identical paths; different seeds differ.
7. Mean final loss over 20 seeds, late noise: batch 256 < batch 1 (larger batch settles closer).
8. Mean final loss over 20 seeds, late noise, batch 4: momentum on < momentum off.
If 7 or 8 does not hold with these constants, report it with the numbers; do not tune constants silently.

## Track B: the module (`site/help/viz/batch-noise.js`)

Follows `step-size.js` exactly in style: `mount(container, params, help) -> { destroy() }`, CSS injected once with
`injectStyle`, colours from `help.colors` via `applyColors`, `loop()` from `lib/kit.js` (pauses out of view; with
`help.reducedMotion` nothing moves until the Step button), `realNote()` required. Imports only from `./lib/`.
Rules from `lib/kit.js`: never name a colour in text (swatches beside series names); `help.openTerm` only for ids in the
momentum entry's text (`gradient`, `orthogonal matrix` if needed; it is fine not to call it at all).

DOM contract (track C tests against it; do not rename):
- root `div.vz-noise` with `data-step`, `data-batch` (the number), `data-momentum` (`on`|`off`), `data-stage` (`early`|`late`).
- `input#vz-noise-batch[type=range]`, min 0, max 8, step 1 (index into BATCHES), with a `<label for>` "Batch size" and
  `aria-valuetext` "batch <n>"; `output#vz-noise-batch-out` shows the number.
- `button` with text "Momentum" and `aria-pressed`.
- a group with buttons "Early in training" and "Late in training", `aria-pressed`.
- `button` "Replay".
- `svg.vz-valley` containing `ellipse.contour` (several), exactly `VALLEY.cloudSize` `line.cloud`, one `line.true-grad`,
  `polyline.path`, `polyline.noiseless`, `circle.ball`.
- readouts: `#vz-noise-snr`, `#vz-noise-cos`, `#vz-noise-msnr` (empty or hidden when momentum is off), `#vz-noise-tag`.
- the "What's real here" note (via `realNote`).
Behaviour: one sim step per frame; the cloud is resampled at the ball every frame; changing batch, momentum or stage
restarts the sim (like Replay); the loop goes idle when the sim is done. Arrow length: scale so the true-gradient arrow at
the start is about a third of the plot width, clamp very long arrows. Works at 360 px wide (no horizontal overflow).

"What's real here" content (put the numbers in, from the imports, not typed in):
- Computed live: the descent and every minibatch gradient (seeded random noise); SNR and cosine from the noise model.
- From our own runs: the two noise levels are set so that at batch 64 two half batches agree as in our runs, cosine
  `CALIBRATION.early` early and `CALIBRATION.late` late (`CALIBRATION.source`). Only batch 64 is measured; every other size
  is extrapolated with the 1/sqrt(batch) noise model. The momentum gain sqrt((1+0.9)/(1-0.9)) = 4.4 assumes a steady signal.
- Illustration only: the valley is two weights, real heads have millions; the noise is set at the starting point, so as the
  ball nears the bottom the true gradient shrinks and the noise takes over, which is the qualitative point, not a measured
  curve; the learning rate is chosen for the picture.

For local testing before track A lands, Track B may write a stub `lib/valley.js` that follows the contract above, but must
NOT commit it (only `batch-noise.js` is committed).

## Track C: browser tests (`site/help/viz/tests/test_batch_noise_browser.py`)

Move the shared fixtures (`base_url`, `browser`, `chromium_path`, `open_page`, `RAF_SPY`) from `test_viz_browser.py` into a
new `site/help/viz/tests/conftest.py` and import nothing from test files; `test_viz_browser.py` keeps passing unchanged
otherwise. Tests against the DOM contract (`dev.html?m=batch-noise`, params via `&p=<json>`):
1. mounts with no console/page errors; 24 `line.cloud`, one `line.true-grad`, the note "What's real here".
2. `data-step` advances within 500 ms.
3. slider: set index 2 (batch 4) then 6 (batch 64): `data-batch` follows, `#vz-noise-snr` grows by about 4x (parse the
   first number; tolerance 10%, both read right after the change, before the ball moves far: compare at the same step or
   read the value the module computes for the start point), tag says "measured" at 64 and "extrapolated" at 4.
4. Momentum button toggles `aria-pressed` and `data-momentum`; `#vz-noise-msnr` shows a number only when on.
5. Stage buttons set `data-stage`; SNR at batch 64 is higher early than late.
6. `&rm=1`: `data-step` stays 0 for 500 ms; clicking "Step" advances it.
7. After `window.__viz.destroy()`, no requestAnimationFrame callbacks are outstanding (RAF_SPY) and the root is gone.
8. Viewport 360x740: `document.documentElement.scrollWidth <= clientWidth`.
9. Keyboard: Tab reaches the slider; ArrowRight raises `data-batch` to the next stop.
10. Params: `p={"batch":64,"momentum":true,"stage":"early"}` starts in that state; `p={"batch":5}` falls back to 8.
Until track B lands these tests fail; that is expected. Verify that the existing step-size tests still pass after the
fixture move, and that the new file at least collects (`pytest --collect-only`).

Run browser tests with `/home/kim/Projects/mir/mir/bin/python -m pytest site/help/viz/tests/`.

## All tracks

- Header line in every new file: `// Owner: WINTERMUTE (created 2026-10-26)` (`#` in Python); editing someone's file adds
  `Last edited: <who> 2026-10-26 -- <what>` under the existing lines.
- Plain JavaScript, no libraries, no CDNs. No storage of any kind.
- Commit with `Misc/agent_commit.sh WINTERMUTE -q -m "<message>" -- <explicit paths>` from the worktree root; never `-A`.
  Message ends with the two trailer lines given in the dispatch.
- No push, no merge; WINTERMUTE integrates.
