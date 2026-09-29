import { expect, test, type Locator, type Page } from "@playwright/test";

// Extends the M1 layout suite (tests/layout.spec.ts, left untouched) with the
// timeline behaviour this milestone adds: drag/trim/overlap, snapping, and
// the master strip's envelope overlay. Same 1800x900 viewport, same
// dev:mock server (playwright.config.ts, M1 T15).
//
// Clip and overlap boxes are selected by their REAL markup -- ClipBox and
// OverlapBox emit class + role="button", no data-testid (reconcile pass
// 2026-09-25). The OVERLAP module id is "overlap". snap-select is still an
// assumed hook: no task emits a SNAP select yet.

function expectPx(actual: number, expected: number, what: string) {
  expect(Math.abs(actual - expected), `${what}: expected ${expected}px, measured ${actual}px`).toBeLessThanOrEqual(1);
}

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

/** Drops the first FILES row onto lane `lane` at `x` px from the lane
 *  canvas's left edge (FILES rows are draggable -- layout.spec.ts already
 *  asserts this). Assumes the fixture's first file is at least a couple of
 *  seconds long, per M2's recorded crop fixtures. */
async function dropClip(page: Page, lane: number, x: number) {
  const files = await openFiles(page);
  const row = files.locator("[data-file-row]").first();
  const canvas = page.locator('[data-region="lane-canvas"]').nth(lane);
  const target = await box(canvas);
  // force: true -- a clip already on this lane can sit on top of the drop
  // point (deliberately, for the overlap test below) and Playwright's
  // default actionability check refuses to complete a drop whose target
  // point isn't topmost. A real browser's native drag/drop still delivers
  // dragover/drop to whatever element is under the cursor and bubbles to
  // `.lane-body`'s handler regardless of DOM layering, so this only skips
  // Playwright's own stricter-than-native pre-check, not the drop itself.
  await row.dragTo(canvas, { targetPosition: { x, y: target.height / 2 }, force: true });
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("timeline regions keep their M1 sizes once a clip is on them", async ({ page }) => {
  await dropClip(page, 0, 40);
  expectPx((await box(page.locator('[data-region="lane-canvas"]').first())).height, 62, "lane canvas");
  expectPx((await box(page.locator('[data-region="ruler-canvas"]').first())).height, 30, "ruler canvas");
  expectPx((await box(page.locator('[data-region="master-canvas"]').first())).height, 56, "master canvas");
});

test("a clip drags and lands snapped", async ({ page }) => {
  await page.locator('[data-testid="snap-select"]').selectOption("bar");
  await dropClip(page, 0, 10);

  const canvas = page.locator('[data-region="lane-canvas"]').first();
  const canvasBox = await box(canvas);
  const clip = page.locator('.clip[role="button"]').first();
  const before = await box(clip);

  // Drag the clip's body (well clear of either edge, so this moves rather
  // than trims) by 100px -- not a bar boundary at the default zoom (80px/s,
  // 120 BPM -> 160px/bar).
  await clip.hover({ position: { x: 30, y: 10 } });
  await page.mouse.down();
  await page.mouse.move(before.x + 30 + 100, before.y + 10, { steps: 8 });
  await page.mouse.up();

  const after = await box(clip);
  const xInCanvas = after.x - canvasBox.x;
  const barPx = 160;
  const nearestBar = Math.round(xInCanvas / barPx) * barPx;
  expect(
    Math.abs(xInCanvas - nearestBar),
    `clip left edge ${xInCanvas}px from canvas origin, nearest bar boundary ${nearestBar}px`,
  ).toBeLessThanOrEqual(2);
});

test("a trim changes width but not the left edge", async ({ page }) => {
  await dropClip(page, 1, 10);
  const clip = page.locator('.clip[role="button"]').first();
  const before = await box(clip);

  // Spec §4.3: a drag within 6px of the RIGHT edge trims instead of moving.
  await clip.hover({ position: { x: before.width - 3, y: before.height / 2 } });
  await page.mouse.down();
  await page.mouse.move(before.x + before.width + 40, before.y + before.height / 2, { steps: 8 });
  await page.mouse.up();

  const after = await box(clip);
  expectPx(after.x, before.x, "trim moved the left edge");
  expect(after.width, "trim did not change the width").toBeGreaterThan(before.width + 10);
});

test("an overlap region appears where two clips intersect, and clicking it selects it", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
  await dropClip(page, 2, 10);
  await dropClip(page, 2, 60); // close enough to overlap the first

  const overlap = page.locator('.overlap[role="button"]').first();
  await expect(overlap).toBeVisible();
  await overlap.click();
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(1);
});

test("the envelope overlay is inert until A2A is on", async ({ page }) => {
  await dropClip(page, 3, 10);
  await page.locator('.clip[role="button"]').first().click(); // select it

  const overlay = page.locator('[data-region="envelope-overlay"]');
  await expect(overlay).toHaveAttribute("data-active", "false");
  expect(await overlay.evaluate((el) => getComputedStyle(el).pointerEvents)).toBe("none");

  await page.locator('[data-testid="target-a2a-toggle"]').click();
  await expect(overlay).toHaveAttribute("data-active", "true");
  expect(await overlay.evaluate((el) => getComputedStyle(el).pointerEvents)).toBe("auto");
});
