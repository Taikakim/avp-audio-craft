import { expect, test, type Locator, type Page } from "@playwright/test";
import { convertProjectV1 } from "../src/lib/forge/convertProjectV1";

// dev:mock LISTS dub-sketch (a fixed fixture) but STORES nothing until a PUT (an empty Map), so
// beforeEach PUTs a real project under that name. One clip at tempo 137; backbone medium-base (the
// default stage, so loading it triggers no model rebuild).
const SEEDED = "dub-sketch";
function seededProject() {
  const p = convertProjectV1({
    version: 1,
    meter: { bpm: 137, beatsPerBar: 4 },
    clips: [{
      id: "clip_seed", laneId: "drums", startSec: 1, durationSec: 4, offsetSec: 0,
      source: { kind: "crop", cropId: "001077" }, latentState: "none",
      render: { op: "decode", prompt: "seeded", steps: 24, cfgScale: 6, seed: 1, noiseLevel: 0.4 },
    }],
  });
  p.name = SEEDED;
  return p;
}

async function storedSession(page: Page) {
  const res = await page.request.get(`/forge/sessions/${SEEDED}`);
  expect(res.ok()).toBe(true);
  return res.json();
}

// M5's ClipBox/OverlapBox have no data-testid; this is the markup they really emit.
const CLIP = '.clip[role="button"]';
const OVERLAP_BOX = '.overlap[role="button"]';

// ---- M5's helpers (tests/timeline.spec.ts), copied; dropClip gains `force: true` as the real one has ----
async function box(loc: Locator) {
  const b = await loc.boundingBox();
  if (!b) throw new Error("element has no bounding box");
  return b;
}

async function openFiles(page: Page) {
  const body = page.locator('[data-module-body="files"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="files"]').click();
  return body;
}

async function dropClip(page: Page, lane: number, x: number) {
  const files = await openFiles(page);
  const row = files.locator("[data-file-row]").first();
  const canvas = page.locator('[data-region="lane-canvas"]').nth(lane);
  const target = await box(canvas);
  // force: true, as in tests/timeline.spec.ts's real helper -- the second drop lands on top of the
  // first clip, and Playwright's own stricter-than-native "target is topmost" pre-check refuses it.
  await row.dragTo(canvas, { targetPosition: { x, y: target.height / 2 }, force: true });
}
// ------------------------------------------------------------------------------------------

test.beforeEach(async ({ page }) => {
  const put = await page.request.put(`/forge/sessions/${SEEDED}`, { data: seededProject() });
  expect(put.ok()).toBe(true);
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("launch never overwrites a saved session, and picking one actually loads it", async ({ page }) => {
  const select = page.locator('[data-testid="session-select"]');
  // M1's sessions[0] auto-select is gone (T9): a fresh tab is `unsaved` ...
  await expect(select).toHaveValue("");
  // ... and even past the 2 s autosave window, the seeded session is untouched on the server.
  await page.waitForTimeout(2600);
  const before = await storedSession(page);
  expect(before.clips).toHaveLength(1);
  expect(before.meter.bpm).toBe(137);

  await expect(page.locator(CLIP)).toHaveCount(0);
  await select.selectOption(SEEDED);
  await expect(page.locator(CLIP)).toHaveCount(1);   // the seeded clip, loaded from the server
});

test("unsaved until named; once loaded, an in-place edit autosaves to the server about 2 s later", async ({ page }) => {
  const select = page.locator('[data-testid="session-select"]');
  await expect(select.locator('option[value=""]')).toHaveText("unsaved");
  await select.selectOption(SEEDED);
  await expect(page.locator(CLIP)).toHaveCount(1);
  await expect(select.locator('option[value=""]')).toHaveCount(0);   // named now
  expect((await storedSession(page)).lanes[0].chain.latch_on).toBe(false);

  // An in-place chain edit -- exactly what a reference-only autosave effect never sees.
  const body = page.locator('[data-module-body="lane-chain"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="lane-chain"]').click();
  await page.locator('[data-testid="latch-toggle"]').click();

  await expect
    .poll(async () => (await storedSession(page)).lanes[0].chain.latch_on, { timeout: 6000 })
    .toBe(true);
  expect((await storedSession(page)).clips).toHaveLength(1);   // the rest of the session survived
});

test("the MASTER PRESET SAVE button is enabled and a saved preset round-trips", async ({ page }) => {
  const saveBtn = page.locator('[data-testid="master-preset-save"]');
  await expect(saveBtn).toBeEnabled();
  page.once("dialog", (d) => d.accept("smoke-test-preset"));
  await saveBtn.click();
  await expect(page.locator('[data-testid="master-preset-select"] option', { hasText: "smoke-test-preset" })).toHaveCount(1);
});

test("the FILES module lists mock files and rows stay draggable after M7's HELP additions", async ({ page }) => {
  const body = page.locator('[data-module-body="files"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="files"]').click();
  const rows = body.locator("[data-file-row]");
  await expect(rows.first()).toBeVisible();
  await expect(rows.first()).toHaveAttribute("draggable", "true");
  await expect(page.locator('[aria-label="file root"]')).toHaveAttribute("data-help", /.+/);
  await expect(page.locator('[aria-label="filter files"]')).toHaveAttribute("data-help", /.+/);
});

test("OVERLAP-INPAINT is absent without an overlap selected -- M1's frozen count-0 assertion, untouched", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
});

test("OVERLAP-INPAINT appears with its real content once two clips overlap and the overlap is clicked", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
  await dropClip(page, 2, 10);
  await dropClip(page, 2, 60);   // M5's own premise: close enough to overlap the first
  const overlap = page.locator(OVERLAP_BOX).first();
  await expect(overlap).toBeVisible();
  await overlap.click();
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(1);
  const body = page.locator('[data-module-body="overlap"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="overlap"]').click();
  await expect(page.locator('[data-testid="inpaint-overlap-button"]')).toHaveText("▸ INPAINT OVERLAP");
  // a never-edited overlap renders OVERLAP_DEFAULT (chroma crossfade on). OverlapBox's click has
  // already created its params (M5 T7), so this does NOT guard the body's no-seed rule --
  // rightPaneModules.test.ts's overlap case does, selecting through view.select (critic follow-up #11).
  await expect(page.locator('[data-testid="overlap-chroma-xfade"]')).toHaveText("[ON]");
});
